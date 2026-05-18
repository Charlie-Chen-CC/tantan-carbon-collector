"""
API路由 - 碳管师收资系统
"""

import uuid
import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends
from fastapi.responses import StreamingResponse
import json

from pydantic import BaseModel
from sse_starlette.sse import ServerSentEvent

# 导入Agent和状态管理器
from tantan.backend.agents import (
    OrchestratorAgent,
    FileExtractAgent,
    FormFillAgent,
    QAAgent,
    ModifyAgent
)
from tantan.backend.agents.file_processor import BatchFileProcessor
from tantan.backend.state.manager import StateManager
from tantan.backend.api.auth import get_current_user
from tantan.backend.models.database import User
from tantan.backend.utils import get_logger, log_exception

# 配置日志
logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api")

# 全局状态管理器
state_manager = StateManager()

# 全局Agent实例
modify_agent = ModifyAgent()
qa_agent = QAAgent()

# 文件上传配置
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'.xlsx', '.xls', '.pdf', '.docx', '.doc', '.pptx', '.md', '.png', '.jpg', '.jpeg'}
ALLOWED_MIME_TYPES = {
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
    'application/vnd.ms-excel',  # .xls
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
    'application/msword',  # .doc
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',  # .pptx
    'text/plain',  # .md
    'image/png',  # .png
    'image/jpeg',  # .jpg/.jpeg
}

def validate_file(file: UploadFile) -> str:
    """验证文件类型和大小"""
    # 检查文件扩展名
    _, ext = os.path.splitext(file.filename or '')
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}，仅支持 xlsx/xls/pdf/docx/doc/pptx/md/png/jpg/jpeg")

    # 检查MIME类型
    if file.content_type not in ALLOWED_MIME_TYPES:
        logger.warning(f"文件MIME类型不匹配: {file.content_type}")

    return ext


# ============== 请求/响应模型 ==============

class CreateSessionResponse(BaseModel):
    session_id: str
    progress: Dict[str, Any]
    current_section: int
    created_at: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class SectionConfirmRequest(BaseModel):
    data: Dict[str, Any]


class ChatRequest(BaseModel):
    session_id: str
    message: str
    context: Optional[Dict[str, Any]] = None


class ModifyRequest(BaseModel):
    section: int
    field: str
    old_value: Any
    new_value: Any
    reason: Optional[str] = ""


# ============== 会话管理API ==============

@router.post("/session", response_model=CreateSessionResponse)
async def create_session(current_user: User = Depends(get_current_user)):
    """创建新会话"""
    try:
        session_id = str(uuid.uuid4())
        session_data = state_manager.create_session(
            user_id=current_user.id,
            session_id=session_id
        )

        logger.info(f"创建会话: session_id={session_id}, user_id={current_user.user_id}")

        return CreateSessionResponse(
            session_id=session_id,
            progress=session_data["progress"],
            current_section=session_data["current_section"],
            created_at=session_data["created_at"]
        )
    except Exception as e:
        log_exception(logger, e, {"user_id": current_user.user_id, "action": "create_session"})
        raise HTTPException(status_code=500, detail=f"会话创建失败: {str(e)}")


@router.get("/session/{session_id}")
async def get_session(session_id: str, current_user: User = Depends(get_current_user)):
    """获取会话状态"""
    try:
        session_data = state_manager.get_session(current_user.id, session_id)

        if not session_data:
            raise HTTPException(status_code=404, detail="会话不存在")

        return session_data
    except HTTPException:
        raise
    except Exception as e:
        log_exception(logger, e, {"session_id": session_id, "user_id": current_user.user_id, "action": "get_session"})
        raise HTTPException(status_code=500, detail=f"获取会话失败: {str(e)}")


@router.get("/sessions")
async def get_user_sessions(current_user: User = Depends(get_current_user)):
    """获取用户的所有会话"""
    sessions = state_manager.get_user_sessions(current_user.id)
    return {"sessions": sessions}


# ============== 文件上传API ==============

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
        raise HTTPException(status_code=400, detail="无效的部分编号（1-9）")

    # 验证会话是否属于当前用户
    session_data = state_manager.get_session(current_user.id, session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 验证文件
    try:
        validate_file(file)
    except HTTPException as e:
        logger.warning(f"文件验证失败: {e.detail}")
        raise e

    # 检查文件大小
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"文件大小超过限制(50MB)")

    # 保存文件
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)

    file_id = str(uuid.uuid4())
    # 清理文件名，防止路径遍历
    safe_filename = "".join(c for c in file.filename if c.isalnum() or c in '._-')
    file_path = os.path.join(upload_dir, f"{file_id}_{safe_filename}")

    with open(file_path, "wb") as f:
        f.write(content)

    logger.info(f"文件保存成功: {file_path}")

    # 更新状态
    state_manager.update_progress(current_user.id, session_id, section, "in_progress")
    state_manager.save_form_data(current_user.id, session_id, section, {"_file_path": file_path})

    return {
        "file_id": file_id,
        "file_path": file_path,
        "status": "processing"
    }


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """获取任务状态"""
    return TaskStatusResponse(
        task_id=task_id,
        status="completed",
        result={"message": "文件处理完成"}
    )


# ============== 表单API ==============

@router.get("/form/{session_id}")
async def get_form(session_id: str, current_user: User = Depends(get_current_user)):
    """获取表单状态"""
    session_data = state_manager.get_session(current_user.id, session_id)

    if not session_data:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {
        "session_id": session_id,
        "progress": session_data.get("progress", {}),
        "current_section": session_data.get("current_section", 1),
        "form_data": session_data.get("form_data", {})
    }


@router.patch("/form/{session_id}/section/{section}")
async def update_section(
    session_id: str,
    section: int,
    field: str = Form(...),
    value: Any = Form(...),
    current_user: User = Depends(get_current_user)
):
    """更新部分数据"""
    if not 1 <= section <= 9:
        raise HTTPException(status_code=400, detail="无效的部分编号（1-9）")

    session_data = state_manager.get_session(current_user.id, session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 获取当前部分数据
    current_data = state_manager.get_form_data(current_user.id, session_id, section)
    current_value = current_data.get(field)

    # 调用修改Agent处理
    result = modify_agent.process_modify_request(
        section=section,
        field=field,
        old_value=current_value,
        new_value=value
    )

    if result["success"]:
        # 保存修改后的数据
        current_data[field] = value
        state_manager.save_form_data(current_user.id, session_id, section, current_data)

        # 记录历史
        state_manager.add_history(current_user.id, session_id, {
            "action": "update_field",
            "section": section,
            "field": field,
            "old_value": current_value,
            "new_value": value,
            "timestamp": datetime.now().isoformat()
        })

    return result


@router.post("/form/{session_id}/section/{section}/confirm")
async def confirm_section(
    session_id: str,
    section: int,
    confirm_data: SectionConfirmRequest,
    current_user: User = Depends(get_current_user)
):
    """确认部分完成"""
    logger.info(f"确认部分完成: session_id={session_id}, section={section}")

    if not 1 <= section <= 9:
        raise HTTPException(status_code=400, detail="无效的部分编号（1-9）")

    session_data = state_manager.get_session(current_user.id, session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 保存表单数据
    state_manager.save_form_data(current_user.id, session_id, section, confirm_data.data)

    # 更新进度
    state_manager.update_progress(current_user.id, session_id, section, "completed")

    # 确定下一个部分
    current_section = state_manager.get_current_section(current_user.id, session_id)
    next_section = section + 1 if section < 9 else section

    if section == current_section and section < 9:
        state_manager.set_current_section(current_user.id, session_id, section + 1)
        state_manager.update_progress(current_user.id, session_id, section + 1, "in_progress")

    return {
        "success": True,
        "completed_section": section,
        "next_section": next_section,
        "progress": state_manager.get_progress(current_user.id, session_id)
    }


@router.post("/form/{session_id}/current-section")
async def set_current_section(
    session_id: str,
    section: int,
    current_user: User = Depends(get_current_user)
):
    """切换当前部分"""
    if not 1 <= section <= 9:
        raise HTTPException(status_code=400, detail="无效的部分编号（1-9）")

    session_data = state_manager.get_session(current_user.id, session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="会话不存在")

    state_manager.set_current_section(current_user.id, session_id, section)
    state_manager.update_progress(current_user.id, session_id, section, "in_progress")

    return {
        "success": True,
        "current_section": section
    }


# ============== 对话API ==============

@router.post("/chat")
async def chat(request: ChatRequest, current_user: User = Depends(get_current_user)):
    """发送消息"""
    try:
        session_data = state_manager.get_session(current_user.id, request.session_id)

        if not session_data:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 设置会话ID
        qa_agent.set_session(request.session_id)

        # 生成回复
        response = qa_agent.generate_response(
            request.message,
            {"current_section": session_data.get("current_section", 1)}
        )

        # 记录对话历史
        state_manager.add_history(current_user.id, request.session_id, {
            "action": "chat",
            "user_message": request.message,
            "assistant_message": response["content"],
            "intent": response["intent"],
            "timestamp": datetime.now().isoformat()
        })

        return response
    except HTTPException:
        raise
    except Exception as e:
        log_exception(logger, e, {"session_id": request.session_id, "user_id": current_user.user_id, "action": "chat"})
        raise HTTPException(status_code=500, detail=f"AI响应失败: {str(e)}")


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, current_user: User = Depends(get_current_user)):
    """流式对话响应（SSE）"""
    try:
        session_data = state_manager.get_session(current_user.id, request.session_id)

        if not session_data:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 设置会话ID
        qa_agent.set_session(request.session_id)

        # 生成回复
        response = qa_agent.generate_response(
            request.message,
            {"current_section": session_data.get("current_section", 1)}
        )

        async def event_generator():
            yield ServerSentEvent(
                event="intent",
                data=json.dumps({"intent": response["intent"]})
            )

            content = response["content"]
            for i in range(0, len(content), 10):
                chunk = content[i:i+10]
                yield ServerSentEvent(
                    event="message",
                    data=json.dumps({"chunk": chunk})
                )

            yield ServerSentEvent(
                event="done",
                data=json.dumps({"full_content": content})
            )

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        log_exception(logger, e, {"session_id": request.session_id, "user_id": current_user.user_id, "action": "chat_stream"})
        raise HTTPException(status_code=500, detail=f"流式响应失败: {str(e)}")


# ============== 文件提取API ==============

@router.post("/extract/{session_id}/section/{section}")
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

        # 读取文件内容
        content = await file.read()

        # 调用文件提取Agent（传入文件名以便正确解析格式）
        extractor = FileExtractAgent(section)
        result = extractor.process(content, filename=file.filename)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        # 如果提取成功，调用表单填报Agent
        if result["status"] == "completed":
            filler = FormFillAgent(section)
            fill_result = filler.fill_form(result["data"])

            # 保存提取的数据
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


@router.post("/extract/{session_id}/section/{section}/batch")
async def extract_batch(
    session_id: str,
    section: int,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user)
):
    """批量提取文件数据（支持SSE进度）"""
    async def event_generator():
        try:
            # 验证会话
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

            # 创建批量处理器
            processor = BatchFileProcessor(section=section)

            # 准备文件列表
            file_list = []
            for f in files:
                content = await f.read()
                file_list.append({
                    "filename": f.filename,
                    "content": content,
                    "file_type": f.content_type
                })

            # 处理并推送进度
            processed = 0
            async def progress_callback(p, t):
                yield ServerSentEvent(event="progress", data=json.dumps({
                    "status": "processing",
                    "processed": p,
                    "total": t,
                    "current_file": files[p-1].filename if p <= total else ""
                }))

            result = await processor.process_batch(file_list)

            # 返回结果
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


# ============== 修改API ==============

@router.post("/modify/{session_id}")
async def modify_form(
    session_id: str,
    request: ModifyRequest,
    current_user: User = Depends(get_current_user)
):
    """修改表单数据"""
    try:
        session_data = state_manager.get_session(current_user.id, session_id)

        if not session_data:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 获取当前数据
        current_data = state_manager.get_form_data(current_user.id, session_id, request.section)

        # 调用修改Agent
        result = modify_agent.process_modify_request(
            section=request.section,
            field=request.field,
            old_value=request.old_value,
            new_value=request.new_value,
            reason=request.reason or "",
            current_data=current_data
        )

        if result["success"]:
            # 更新数据
            current_data[request.field] = request.new_value
            state_manager.save_form_data(current_user.id, session_id, request.section, current_data)

            # 记录历史
            state_manager.add_history(current_user.id, session_id, {
                "action": "modify",
                "section": request.section,
                "field": request.field,
                "old_value": request.old_value,
                "new_value": request.new_value,
                "reason": request.reason,
                "timestamp": datetime.now().isoformat()
            })

        return result
    except HTTPException:
        raise
    except Exception as e:
        log_exception(logger, e, {"session_id": session_id, "user_id": current_user.user_id, "action": "modify_form"})
        raise HTTPException(status_code=500, detail=f"修改表单失败: {str(e)}")


@router.get("/history/{session_id}")
async def get_history(
    session_id: str,
    limit: int = 100,
    current_user: User = Depends(get_current_user)
):
    """获取操作历史"""
    try:
        session_data = state_manager.get_session(current_user.id, session_id)

        if not session_data:
            raise HTTPException(status_code=404, detail="会话不存在")

        history = state_manager.get_history(current_user.id, session_id, limit)

        return {
            "session_id": session_id,
            "history": history
        }
    except HTTPException:
        raise
    except Exception as e:
        log_exception(logger, e, {"session_id": session_id, "user_id": current_user.user_id, "action": "get_history"})
        raise HTTPException(status_code=500, detail=f"获取历史失败: {str(e)}")