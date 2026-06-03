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
from tantan.backend.utils import log_exception

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
            raise HTTPException(status_code=400, detail="无效的部分编号（1-9）")

        session_data = state_manager.get_session(current_user.id, session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="会话不存在")

        content = await file.read()

        extractor = FileExtractAgent(section)
        result = extractor.process(content, filename=file.filename)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

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

        raise HTTPException(status_code=400, detail="文件提取失败")
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
