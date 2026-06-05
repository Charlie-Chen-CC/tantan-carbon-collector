"""文件提取路由

- POST /api/extract/{session_id}/section/{section}        提取单个文件
- POST /api/extract/{session_id}/section/{section}/batch  批量提取（SSE）
"""
import json
import logging
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sse_starlette.sse import ServerSentEvent

from tantan.backend.agents import FileExtractAgent, FormFillAgent
from tantan.backend.agents.file_processor import BatchFileProcessor
from tantan.backend.api.auth import get_current_user
from tantan.backend.models.database import User
from tantan.backend.state.database_manager import DatabaseStateManager
from tantan.backend.utils import log_exception
from tantan.backend.utils.exceptions import AppException, ErrorCode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/extract", tags=["extract"])
state_manager = DatabaseStateManager()


@router.post("/{session_id}/section/{section}")
async def extract_section(
    session_id: str,
    section: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """提取文件中的部分数据"""
    try:
        if not 1 <= section <= 9:
            raise AppException(
                ErrorCode.SESSION_INVALID_SECTION,
                "无效的部分编号（1-9）",
                status_code=400,
            )

        session_data = state_manager.get_session(current_user.id, session_id)
        if not session_data:
            raise AppException(
                ErrorCode.SESSION_NOT_FOUND,
                "会话不存在",
                status_code=404,
            )

        content = await file.read()

        extractor = FileExtractAgent(section)
        result = extractor.process(content, filename=file.filename)

        if "error" in result:
            raise AppException(
                ErrorCode.EXTRACTION_FAILED,
                result["error"],
                status_code=400,
            )

        if result["status"] == "completed":
            filler = FormFillAgent(section)
            fill_result = filler.fill_form(result["data"])

            state_manager.save_form_data(current_user.id, session_id, section, fill_result.get("filled_data", {}))
            state_manager.update_progress(current_user.id, session_id, section, "awaiting_confirm")

            return {
                "success": True,
                "extracted_data": result["data"],
                "filled_data": fill_result.get("filled_data", {}),
                "errors": fill_result.get("errors", [])
            }

        raise AppException(
            ErrorCode.EXTRACTION_FAILED,
            "文件提取失败",
            status_code=400,
        )
    except AppException:
        raise
    except Exception as e:
        log_exception(logger, e, {"session_id": session_id, "section": section, "user_id": current_user.user_id, "action": "extract_section"})
        raise AppException(
            ErrorCode.INTERNAL_ERROR,
            "文件提取失败，请稍后重试",
            status_code=500,
            developer_message=str(e),
        )


@router.post("/{session_id}/section/{section}/batch")
async def extract_batch(
    session_id: str,
    section: int,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user)
):
    """批量提取文件数据（支持SSE进度）"""
    async def event_generator():
        try:
            session_data = state_manager.get_session(current_user.id, session_id)
            if not session_data:
                yield ServerSentEvent(event="error", data=json.dumps({
                    "error_code": ErrorCode.SESSION_NOT_FOUND.value,
                    "user_message": "会话不存在"
                }))
                return

            total = len(files)
            yield ServerSentEvent(event="progress", data=json.dumps({
                "status": "started",
                "total": total,
                "processed": 0
            }))

            processor = BatchFileProcessor(section=section)

            file_list = []
            for f in files:
                content = await f.read()
                file_list.append({
                    "filename": f.filename,
                    "content": content,
                    "file_type": f.content_type
                })

            # 注：P0-4 batch SSE 假流式修复见 fix/phase1-p0-4-batch-sse 分支，
            # 本次 P0-1 只做异常体系切换。progress_callback 仍是死代码，会在 P0-4 一并修。
            result = await processor.process_batch(file_list)

            yield ServerSentEvent(event="complete", data=json.dumps({
                "status": result.status,
                "extracted": result.extracted,
                "warnings": result.warnings,
                "failed_files": result.failed_files
            }))

        except Exception as e:
            # SSE error 事件也走 user_message，不暴露 str(e)
            logger.error(f"批量提取失败: {e}", exc_info=True)
            yield ServerSentEvent(event="error", data=json.dumps({
                "error_code": ErrorCode.INTERNAL_ERROR.value,
                "user_message": "批量提取失败，请稍后重试"
            }))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )
