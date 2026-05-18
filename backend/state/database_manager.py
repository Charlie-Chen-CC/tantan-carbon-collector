"""
状态管理模块 - 碳管师收资系统
使用数据库管理会话状态和表单进度
"""

import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from sqlalchemy.orm import Session
from tantan.backend.models.database import (
    Session as DBSession,
    SectionData,
    OperationHistory,
    User,
    get_db_context
)
from tantan.backend.utils import get_logger

logger = get_logger(__name__)


class DatabaseStateManager:
    """数据库状态管理器"""

    def __init__(self):
        pass

    def create_session(self, user_id: int, session_id: str, initial_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建新会话"""
        try:
            with get_db_context() as db:
                # 检查是否已存在会话
                existing = db.query(DBSession).filter(
                    DBSession.session_id == session_id
                ).first()

                if existing:
                    # 如果会话已存在，更新关联的用户
                    existing.user_id = user_id
                    db.commit()
                    logger.info(f"会话已存在，更新用户关联: session_id={session_id}, user_id={user_id}")
                    return self._session_to_dict(existing)

                # 创建新会话
                session_data = {
                    "session_id": session_id,
                    "user_id": user_id,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "current_section": 1,
                    "progress": {
                        str(i): "not_started" for i in range(1, 10)
                    },
                    "form_data": {str(i): {} for i in range(1, 10)}
                }

                if initial_data:
                    session_data.update(initial_data)

                db_session = DBSession(
                    session_id=session_id,
                    user_id=user_id,
                    current_section=1,
                    status="active"
                )
                db.add(db_session)
                db.commit()
                db.refresh(db_session)

                logger.info(f"创建会话成功: session_id={session_id}, user_id={user_id}")
                return session_data
        except Exception as e:
            logger.error(f"创建会话失败: session_id={session_id}, user_id={user_id}, error: {str(e)}", exc_info=True)
            raise

    def get_session(self, user_id: int, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话数据"""
        with get_db_context() as db:
            db_session = db.query(DBSession).filter(
                DBSession.session_id == session_id,
                DBSession.user_id == user_id
            ).first()

            if not db_session:
                return None

            return self._session_to_dict(db_session)

    def get_user_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """获取用户的所有会话"""
        with get_db_context() as db:
            sessions = db.query(DBSession).filter(
                DBSession.user_id == user_id
            ).order_by(DBSession.created_at.desc()).all()

            return [self._session_to_dict(s) for s in sessions]

    def update_progress(self, user_id: int, session_id: str, section: int, status: str) -> None:
        """更新部分进度"""
        with get_db_context() as db:
            db_session = db.query(DBSession).filter(
                DBSession.session_id == session_id,
                DBSession.user_id == user_id
            ).first()

            if not db_session:
                return

            # 更新或创建 SectionData 记录
            section_data = db.query(SectionData).filter(
                SectionData.session_id == db_session.id,
                SectionData.section_number == section
            ).first()

            if section_data:
                section_data.status = status
            else:
                section_data = SectionData(
                    session_id=db_session.id,
                    section_number=section,
                    status=status
                )
                db.add(section_data)

            db_session.updated_at = datetime.now()
            db.commit()

    def get_progress(self, user_id: int, session_id: str) -> Dict[str, str]:
        """获取进度状态"""
        with get_db_context() as db:
            db_session = db.query(DBSession).filter(
                DBSession.session_id == session_id,
                DBSession.user_id == user_id
            ).first()

            if not db_session:
                return {}

            progress = {}
            for i in range(1, 10):
                section_data = db.query(SectionData).filter(
                    SectionData.session_id == db_session.id,
                    SectionData.section_number == i
                ).first()
                progress[str(i)] = section_data.status if section_data else "not_started"

            return progress

    def set_current_section(self, user_id: int, session_id: str, section: int) -> None:
        """设置当前部分"""
        with get_db_context() as db:
            db_session = db.query(DBSession).filter(
                DBSession.session_id == session_id,
                DBSession.user_id == user_id
            ).first()

            if not db_session:
                return

            db_session.current_section = section
            db_session.updated_at = datetime.now()
            db.commit()

    def get_current_section(self, user_id: int, session_id: str) -> int:
        """获取当前部分"""
        with get_db_context() as db:
            db_session = db.query(DBSession).filter(
                DBSession.session_id == session_id,
                DBSession.user_id == user_id
            ).first()

            if not db_session:
                return 1

            return db_session.current_section

    def save_form_data(self, user_id: int, session_id: str, section: int, data: Dict[str, Any]) -> None:
        """保存表单数据"""
        try:
            with get_db_context() as db:
                db_session = db.query(DBSession).filter(
                    DBSession.session_id == session_id,
                    DBSession.user_id == user_id
                ).first()

                if not db_session:
                    logger.warning(f"保存表单数据失败：会话不存在: session_id={session_id}, user_id={user_id}")
                    return

                # 查找或创建 SectionData
                section_data = db.query(SectionData).filter(
                    SectionData.session_id == db_session.id,
                    SectionData.section_number == section
                ).first()

                if section_data:
                    # 合并数据
                    existing_data = section_data.data or {}
                    existing_data.update(data)
                    section_data.data = existing_data
                else:
                    section_data = SectionData(
                        session_id=db_session.id,
                        section_number=section,
                        data=data,
                        status="in_progress"
                    )
                    db.add(section_data)

                db_session.updated_at = datetime.now()
                db.commit()

                logger.debug(f"保存表单数据成功: session_id={session_id}, section={section}, data_keys={list(data.keys())}")
        except Exception as e:
            logger.error(f"保存表单数据失败: session_id={session_id}, section={section}, error: {str(e)}", exc_info=True)
            raise

    def get_form_data(self, user_id: int, session_id: str, section: Optional[int] = None) -> Dict[str, Any]:
        """获取表单数据"""
        with get_db_context() as db:
            db_session = db.query(DBSession).filter(
                DBSession.session_id == session_id,
                DBSession.user_id == user_id
            ).first()

            if not db_session:
                return {} if section is None else {}

            if section:
                section_data = db.query(SectionData).filter(
                    SectionData.session_id == db_session.id,
                    SectionData.section_number == section
                ).first()
                return section_data.data if section_data else {}
            else:
                # 获取所有部分的数据
                result = {}
                for i in range(1, 10):
                    section_data = db.query(SectionData).filter(
                        SectionData.session_id == db_session.id,
                        SectionData.section_number == i
                    ).first()
                    result[str(i)] = section_data.data if section_data else {}

                return result

    def add_history(self, user_id: int, session_id: str, action: Dict[str, Any]) -> None:
        """添加操作历史"""
        try:
            with get_db_context() as db:
                db_session = db.query(DBSession).filter(
                    DBSession.session_id == session_id,
                    DBSession.user_id == user_id
                ).first()

                if not db_session:
                    logger.warning(f"添加历史记录失败：会话不存在: session_id={session_id}, user_id={user_id}")
                    return

                history = OperationHistory(
                    session_id=db_session.id,
                    action_type=action.get("action", "unknown"),
                    section_number=action.get("section"),
                    details=action
                )
                db.add(history)
                db.commit()

                logger.debug(f"添加操作历史: session_id={session_id}, action={action.get('action')}")
        except Exception as e:
            logger.error(f"添加操作历史失败: session_id={session_id}, action={action}, error: {str(e)}", exc_info=True)
            # 不抛出异常，避免影响主流程

    def get_history(self, user_id: int, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取操作历史"""
        with get_db_context() as db:
            db_session = db.query(DBSession).filter(
                DBSession.session_id == session_id,
                DBSession.user_id == user_id
            ).first()

            if not db_session:
                return []

            history = db.query(OperationHistory).filter(
                OperationHistory.session_id == db_session.id
            ).order_by(OperationHistory.created_at.desc()).limit(limit).all()

            return [h.details for h in history]

    def delete_session(self, user_id: int, session_id: str) -> None:
        """删除会话"""
        with get_db_context() as db:
            db_session = db.query(DBSession).filter(
                DBSession.session_id == session_id,
                DBSession.user_id == user_id
            ).first()

            if db_session:
                db.delete(db_session)
                db.commit()

    def _session_to_dict(self, db_session: DBSession) -> Dict[str, Any]:
        """将数据库会话转换为字典"""
        # 获取进度和表单数据
        progress = {}
        form_data = {}

        for section_data in db_session.section_data:
            progress[str(section_data.section_number)] = section_data.status
            form_data[str(section_data.section_number)] = section_data.data or {}

        # 确保所有部分都有默认值
        for i in range(1, 10):
            if str(i) not in progress:
                progress[str(i)] = "not_started"
            if str(i) not in form_data:
                form_data[str(i)] = {}

        return {
            "session_id": db_session.session_id,
            "created_at": db_session.created_at.isoformat() if db_session.created_at else "",
            "updated_at": db_session.updated_at.isoformat() if db_session.updated_at else "",
            "current_section": db_session.current_section,
            "status": db_session.status,
            "progress": progress,
            "form_data": form_data
        }


# 导出状态管理器
StateManager = DatabaseStateManager