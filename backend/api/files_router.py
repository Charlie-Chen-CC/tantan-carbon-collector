"""文件路由 - 上传/下载/列表/删除

- POST   /api/upload                       上传文件
- GET    /api/task/{task_id}               获取任务状态
- GET    /api/files/{file_id}              下载文件
- GET    /api/files/{session_id}/section/{section}  列出会话某 section 文件
- DELETE /api/files/{file_id}              删除文件
"""
import logging
import os
import uuid
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from tantan.backend.api.auth import get_current_user
from tantan.backend.api.validation import validate_file, MAX_FILE_SIZE
from tantan.backend.models.database import User, get_db_context
from tantan.backend.state.database_manager import DatabaseStateManager
from tantan.backend.utils import log_exception
from tantan.backend.utils.exceptions import AppException, ErrorCode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["files"])
state_manager = DatabaseStateManager()


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    section: int = Form(...),
    session_id: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    """上传文件"""
    logger.info(f"文件上传请求: session_id={session_id}, section={section}, filename={file.filename}")

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

    try:
        ext, safe_filename = validate_file(file)
    except AppException as e:
        logger.warning(f"文件验证失败: {e.user_message}")
        raise

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise AppException(
            ErrorCode.FILE_TOO_LARGE,
            f"文件大小超过限制(10MB)",
            status_code=400,
        )

    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)

    file_id = uuid.uuid4().hex
    file_path = os.path.join(upload_dir, f"{file_id}{ext}")

    with open(file_path, "wb") as f:
        f.write(content)

    try:
        with get_db_context() as db:
            from tantan.backend.models.database import UploadedFile, Session as DBSession
            db_session = db.query(DBSession).filter(
                DBSession.session_id == session_id,
                DBSession.user_id == current_user.id
            ).first()
            if db_session:
                uploaded_file = UploadedFile(
                    session_id=db_session.id,
                    file_name=safe_filename,
                    file_path=file_path,
                    file_size=len(content),
                    file_type=file.content_type,
                    section_number=section,
                    status="pending"
                )
                db.add(uploaded_file)
                db.commit()
    except Exception as e:
        logger.warning(f"记录文件元数据失败: {e}，但文件已保存")

    logger.info(f"文件保存成功: {file_path}")

    state_manager.update_progress(current_user.id, session_id, section, "in_progress")
    state_manager.save_form_data(current_user.id, session_id, section, {"_file_path": file_path})

    return {
        "file_id": file_id,
        "file_path": file_path,
        "status": "processing"
    }


@router.get("/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """获取任务状态"""
    return TaskStatusResponse(
        task_id=task_id,
        status="completed",
        result={"message": "文件处理完成"}
    )


@router.get("/files/{file_id}")
async def download_file(
    file_id: str,
    current_user: User = Depends(get_current_user)
):
    """下载文件（需认证）"""
    upload_dir = "uploads"
    if not os.path.exists(upload_dir):
        raise AppException(
            ErrorCode.FILE_NOT_FOUND,
            "文件不存在",
            status_code=404,
        )

    found_path = None
    for filename in os.listdir(upload_dir):
        if filename.startswith(file_id + "_"):
            found_path = os.path.join(upload_dir, filename)
            break

    if not found_path:
        raise AppException(
            ErrorCode.FILE_NOT_FOUND,
            "文件不存在",
            status_code=404,
        )

    try:
        with get_db_context() as db:
            from tantan.backend.models.database import UploadedFile, Session as DBSession
            file_record = db.query(UploadedFile).filter(
                UploadedFile.file_path == found_path
            ).first()
            if not file_record:
                raise AppException(
                    ErrorCode.FILE_NOT_FOUND,
                    "文件不存在",
                    status_code=404,
                )
            session_record = db.query(DBSession).filter(
                DBSession.id == file_record.session_id,
                DBSession.user_id == current_user.id
            ).first()
            if not session_record:
                raise AppException(
                    ErrorCode.OPERATION_NOT_ALLOWED,
                    "无权访问此文件",
                    status_code=403,
                )
    except AppException:
        raise
    except Exception as e:
        logger.error(f"文件权限验证失败: {e}", exc_info=True)
        raise AppException(
            ErrorCode.INTERNAL_ERROR,
            "文件访问验证失败",
            status_code=500,
            developer_message=str(e),
        )

    async def file_iterator():
        with open(found_path, "rb") as f:
            while chunk := f.read(8192):
                yield chunk

    return StreamingResponse(
        file_iterator(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={os.path.basename(found_path)}"}
    )


@router.get("/files/{session_id}/section/{section}")
async def get_section_files(
    session_id: str,
    section: int,
    current_user: User = Depends(get_current_user)
):
    """获取指定部分的已上传文件列表"""
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

        with get_db_context() as db:
            from tantan.backend.models.database import UploadedFile, Session as DBSession
            db_session = db.query(DBSession).filter(
                DBSession.session_id == session_id,
                DBSession.user_id == current_user.id
            ).first()

            if not db_session:
                raise AppException(
                    ErrorCode.SESSION_NOT_FOUND,
                    "会话不存在",
                    status_code=404,
                )

            files = db.query(UploadedFile).filter(
                UploadedFile.session_id == db_session.id,
                UploadedFile.section_number == section
            ).order_by(UploadedFile.created_at.desc()).all()

            return {
                "files": [
                    {
                        "id": f.id,
                        "name": f.file_name,
                        "size": f.file_size,
                        "type": f.file_type,
                        "status": f.status,
                        "created_at": f.created_at.isoformat() if f.created_at else None
                    }
                    for f in files
                ]
            }
    except AppException:
        raise
    except Exception as e:
        log_exception(logger, e, {"session_id": session_id, "section": section, "user_id": current_user.user_id, "action": "get_section_files"})
        raise AppException(
            ErrorCode.INTERNAL_ERROR,
            "获取文件列表失败，请稍后重试",
            status_code=500,
            developer_message=str(e),
        )


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_user)
):
    """删除上传的文件"""
    try:
        with get_db_context() as db:
            from tantan.backend.models.database import UploadedFile, Session as DBSession

            file_record = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
            if not file_record:
                raise AppException(
                    ErrorCode.FILE_NOT_FOUND,
                    "文件不存在",
                    status_code=404,
                )

            session_record = db.query(DBSession).filter(
                DBSession.id == file_record.session_id,
                DBSession.user_id == current_user.id
            ).first()
            if not session_record:
                raise AppException(
                    ErrorCode.OPERATION_NOT_ALLOWED,
                    "无权删除此文件",
                    status_code=403,
                )

            file_path = file_record.file_path
            if os.path.exists(file_path):
                os.remove(file_path)

            db.delete(file_record)
            db.commit()

            logger.info(f"文件删除成功: file_id={file_id}")

            return {"success": True, "message": "文件删除成功"}
    except AppException:
        raise
    except Exception as e:
        log_exception(logger, e, {"file_id": file_id, "user_id": current_user.user_id, "action": "delete_file"})
        raise AppException(
            ErrorCode.INTERNAL_ERROR,
            "删除文件失败，请稍后重试",
            status_code=500,
            developer_message=str(e),
        )
