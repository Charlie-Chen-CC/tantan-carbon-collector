"""文件提取路由

- POST /api/extract/{session_id}/section/{section}        提取单个文件（接受 file_id 或 file）
- POST /api/extract/{session_id}/section/{section}/batch  批量提取（SSE）
"""
import json
import logging
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
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


def _resolve_file_path(file_id: str) -> Optional[str]:
    """根据 file_id 在 uploads/ 目录找文件

    P0-9 修复：upload 阶段把文件以 {file_id}{ext} 存到 uploads/，
    extract 阶段不再要求前端重传文件，直接按 file_id 找盘上文件。
    """
    upload_dir = "uploads"
    if not os.path.isdir(upload_dir):
        return None
    for entry in os.listdir(upload_dir):
        if entry.startswith(file_id + "."):
            return os.path.join(upload_dir, entry)
    return None


@router.post("/{session_id}/section/{section}")
async def extract_section(
    session_id: str,
    section: int,
    file_id: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user)
):
    """提取文件中的部分数据

    P0-9 修复：接受 `file_id` (form field) 而非要求前端重传 file。
    修前：前端 await upload(file) 之后再 await extract(file) → 同一文件 HTTP 传两次
    修后：前端 await upload(file) 拿 file_id，再 await extract(file_id) → 1 次上传
    兼容：若前端仍传 file（老调用方），仍按 multipart 方式处理
    """
    try:
        if not 1 <= section <= 9:
            raise HTTPException(status_code=400, detail="无效的部分编号（1-9）")

        session_data = state_manager.get_session(current_user.id, session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 优先用 file_id 路径（P0-9 主推）
        if file_id:
            file_path = _resolve_file_path(file_id)
            if not file_path:
                raise HTTPException(status_code=404, detail=f"file_id={file_id} 对应文件不存在")
            with open(file_path, "rb") as f:
                content = f.read()
            filename = os.path.basename(file_path)
        elif file is not None:
            # 兼容老调用方
            content = await file.read()
            filename = file.filename or "uploaded"
        else:
            raise HTTPException(status_code=400, detail="必须提供 file_id 或 file")

        extractor = FileExtractAgent(section)
        result = extractor.process(content, filename=filename)

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
