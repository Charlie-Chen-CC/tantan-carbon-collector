"""文件提取路由

- POST /api/extract/{session_id}/section/{section}        提取单个文件
- POST /api/extract/{session_id}/section/{section}/batch  批量提取（SSE）
"""
import json
import logging
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sse_starlette.sse import ServerSentEvent

from tantan.backend.agents import FileExtractAgent, FormFillAgent
from tantan.backend.agents.file_processor import BatchFileProcessor
from tantan.backend.api.auth import get_current_user
from tantan.backend.models.database import User
from tantan.backend.state.database_manager import DatabaseStateManager
from tantan.backend.utils import log_exception, get_trace_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/extract", tags=["extract"])
state_manager = DatabaseStateManager()


def _bad_request(detail: str) -> HTTPException:
    """400 with trace_id 注入到 detail 末尾，便于客户端贴后端日志定位"""
    trace_id = get_trace_id()
    suffix = f" [trace_id={trace_id}]" if trace_id else ""
    return HTTPException(status_code=400, detail=f"{detail}{suffix}")


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
            raise _bad_request("无效的部分编号（1-9）")

        session_data = state_manager.get_session(current_user.id, session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="会话不存在")

        content = await file.read()

        # 请求级日志：filename + content_size + 前 50 字节 hex（便于排查编码/损坏）
        logger.info(
            f"[extract] session_id={session_id} section={section} "
            f"filename={file.filename!r} content_type={file.content_type!r} "
            f"size={len(content)} head_hex={content[:50].hex()}"
        )

        extractor = FileExtractAgent(section)
        result = extractor.process(content, filename=file.filename)

        if result.get("error"):
            # 把 result 完整内容打到日志（status/error/data keys），便于排查
            logger.warning(
                f"[extract] FileExtractAgent 返回 error: "
                f"filename={file.filename!r} result={result!r}"
            )
            raise _bad_request(result["error"])

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

        logger.warning(
            f"[extract] 未知 result.status: filename={file.filename!r} result={result!r}"
        )
        raise _bad_request("文件提取失败")
    except HTTPException:
        raise
    except Exception as e:
        log_exception(logger, e, {"session_id": session_id, "section": section, "user_id": current_user.user_id, "action": "extract_section"})
        raise HTTPException(status_code=500, detail=f"文件提取失败: {str(e)}")


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
                yield ServerSentEvent(event="error", data=json.dumps({"error": "会话不存在"}))
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

            processed = 0
            async def progress_callback(p, t):
                yield ServerSentEvent(event="progress", data=json.dumps({
                    "status": "processing",
                    "processed": p,
                    "total": t,
                    "current_file": files[p-1].filename if p <= total else ""
                }))

            result = await processor.process_batch(file_list)

            yield ServerSentEvent(event="complete", data=json.dumps({
                "status": result.status,
                "extracted": result.extracted,
                "warnings": result.warnings,
                "failed_files": result.failed_files
            }))

        except Exception as e:
            logger.error(f"批量提取失败: {e}")
            yield ServerSentEvent(event="error", data=json.dumps({"error": str(e)}))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )
