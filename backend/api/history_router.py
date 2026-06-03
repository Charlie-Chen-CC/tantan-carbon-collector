"""历史路由

- GET /api/history/{session_id}  获取操作历史
"""
import logging

from fastapi import APIRouter, Depends, HTTPException

from tantan.backend.api.auth import get_current_user
from tantan.backend.models.database import User
from tantan.backend.state.database_manager import DatabaseStateManager
from tantan.backend.utils import log_exception

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/history", tags=["history"])
state_manager = DatabaseStateManager()


@router.get("/{session_id}")
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
