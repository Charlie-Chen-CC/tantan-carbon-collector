"""
API Pydantic 模型 - 碳管师收资系统

所有路由的请求/响应模型集中在此文件，便于前后端契约核对。
"""
from typing import Any, Dict, Optional

from pydantic import BaseModel


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


class UploadResponse(BaseModel):
    file_id: str
    file_path: str
    status: str
