"""表单路由 - 获取/更新/确认/切换

- GET    /api/form/{session_id}                                  获取表单状态
- PATCH  /api/form/{session_id}/section/{section}                更新部分数据
- POST   /api/form/{session_id}/section/{section}/confirm        确认部分完成
- POST   /api/form/{session_id}/current-section                  切换当前部分
"""
import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, Form
from pydantic import BaseModel

from tantan.backend.agents import ModifyAgent
from tantan.backend.api.auth import get_current_user
from tantan.backend.models.database import User
from tantan.backend.state.database_manager import DatabaseStateManager
from tantan.backend.utils import log_exception
from tantan.backend.utils.exceptions import AppException, ErrorCode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/form", tags=["form"])
state_manager = DatabaseStateManager()


class SectionConfirmRequest(BaseModel):
    data: Dict[str, Any]


@router.get("/{session_id}")
async def get_form(session_id: str, current_user: User = Depends(get_current_user)):
    """获取表单状态"""
    session_data = state_manager.get_session(current_user.id, session_id)

    if not session_data:
        raise AppException(
            ErrorCode.SESSION_NOT_FOUND,
            "会话不存在",
            status_code=404,
        )

    return {
        "session_id": session_id,
        "progress": session_data.get("progress", {}),
        "current_section": session_data.get("current_section", 1),
        "form_data": session_data.get("form_data", {})
    }


@router.patch("/{session_id}/section/{section}")
async def update_section(
    session_id: str,
    section: int,
    field: str = Form(...),
    value: Any = Form(...),
    current_user: User = Depends(get_current_user)
):
    """更新部分数据"""
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

    current_data = state_manager.get_form_data(current_user.id, session_id, section)
    current_value = current_data.get(field)

    modify_agent = ModifyAgent()
    result = modify_agent.process_modify_request(
        section=section,
        field=field,
        old_value=current_value,
        new_value=value
    )

    if result["success"]:
        current_data[field] = value
        state_manager.save_form_data(current_user.id, session_id, section, current_data)

        state_manager.add_history(current_user.id, session_id, {
            "action": "update_field",
            "section": section,
            "field": field,
            "old_value": current_value,
            "new_value": value,
            "timestamp": datetime.now().isoformat()
        })

    return result


@router.post("/{session_id}/section/{section}/confirm")
async def confirm_section(
    session_id: str,
    section: int,
    confirm_data: SectionConfirmRequest,
    current_user: User = Depends(get_current_user)
):
    """确认部分完成"""
    logger.info(f"确认部分完成: session_id={session_id}, section={section}")

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

    state_manager.save_form_data(current_user.id, session_id, section, confirm_data.data)
    state_manager.update_progress(current_user.id, session_id, section, "completed")

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


@router.post("/{session_id}/current-section")
async def set_current_section(
    session_id: str,
    section: int,
    current_user: User = Depends(get_current_user)
):
    """切换当前部分"""
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

    state_manager.set_current_section(current_user.id, session_id, section)
    state_manager.update_progress(current_user.id, session_id, section, "in_progress")

    return {
        "success": True,
        "current_section": section
    }
