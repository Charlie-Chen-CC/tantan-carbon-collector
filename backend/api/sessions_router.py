"""会话管理路由

- POST /api/session - 创建新会话
- GET /api/session/{session_id} - 获取会话状态
- GET /api/sessions - 获取用户所有会话
"""
import logging
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from tantan.backend.api.auth import get_current_user
from tantan.backend.models.database import User
from tantan.backend.state.database_manager import DatabaseStateManager
from tantan.backend.utils import log_exception

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["sessions"])
state_manager = DatabaseStateManager()


class CreateSessionResponse(BaseModel):
    session_id: str
    progress: Dict[str, Any]
    current_section: int
    created_at: str


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
