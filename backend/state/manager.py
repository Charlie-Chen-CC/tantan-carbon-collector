"""
状态管理模块 - 碳管师收资系统
使用Redis管理会话状态和表单进度
"""

import os
import json
import redis
from typing import Dict, Any, Optional, List
from datetime import datetime

from tantan.backend.utils import get_logger

logger = get_logger(__name__)

# 会话过期时间配置（秒）
SESSION_EXPIRE_SECONDS = int(os.getenv("SESSION_EXPIRE_SECONDS", 86400 * 7))  # 默认7天


class RedisStateManager:
    """Redis状态管理器"""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.key_prefix = "form"

    def _get_key(self, session_id: str, suffix: str = "") -> str:
        """生成Redis键"""
        if suffix:
            return f"{self.key_prefix}:{session_id}:{suffix}"
        return f"{self.key_prefix}:{session_id}"

    def create_session(self, session_id: str, initial_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建新会话"""
        key = self._get_key(session_id)

        session_data = {
            "session_id": session_id,
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

        self.redis.hset(key, mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in session_data.items()})
        self.redis.expire(key, SESSION_EXPIRE_SECONDS)

        return session_data

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话数据"""
        key = self._get_key(session_id)
        data = self.redis.hgetall(key)

        if not data:
            return None

        result = {}
        for k, v in data.items():
            try:
                result[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                result[k] = v

        return result

    def update_progress(self, session_id: str, section: int, status: str) -> None:
        """更新部分进度"""
        key = self._get_key(session_id)
        self.redis.hset(key, f"progress:{section}", status)
        self.redis.hset(key, "updated_at", datetime.now().isoformat())

    def get_progress(self, session_id: str) -> Dict[str, str]:
        """获取进度状态"""
        key = self._get_key(session_id)
        progress = self.redis.hgetall(key)

        result = {}
        for k, v in progress.items():
            if k.startswith("progress:"):
                section = k.replace("progress:", "")
                result[section] = v

        return result

    def set_current_section(self, session_id: str, section: int) -> None:
        """设置当前部分"""
        key = self._get_key(session_id)
        self.redis.hset(key, "current_section", section)
        self.redis.hset(key, "updated_at", datetime.now().isoformat())

    def get_current_section(self, session_id: str) -> int:
        """获取当前部分"""
        key = self._get_key(session_id)
        current = self.redis.hget(key, "current_section")
        return int(current) if current else 1

    def save_form_data(self, session_id: str, section: int, data: Dict[str, Any]) -> None:
        """保存表单数据"""
        key = self._get_key(session_id)
        section_key = f"data:{section}"

        existing = self.redis.hget(key, section_key)
        if existing:
            try:
                existing_data = json.loads(existing)
                existing_data.update(data)
                data = existing_data
            except json.JSONDecodeError:
                pass

        self.redis.hset(key, section_key, json.dumps(data, ensure_ascii=False))
        self.redis.hset(key, "updated_at", datetime.now().isoformat())

    def get_form_data(self, session_id: str, section: Optional[int] = None) -> Dict[str, Any]:
        """获取表单数据"""
        key = self._get_key(session_id)

        if section:
            data = self.redis.hget(key, f"data:{section}")
            if data:
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    return {}
            return {}

        # 获取所有部分的数据
        result = {}
        for i in range(1, 10):
            data = self.redis.hget(key, f"data:{i}")
            if data:
                try:
                    result[str(i)] = json.loads(data)
                except json.JSONDecodeError:
                    result[str(i)] = {}
            else:
                result[str(i)] = {}

        return result

    def add_history(self, session_id: str, action: Dict[str, Any]) -> None:
        """添加操作历史"""
        key = self._get_key(session_id, "history")
        self.redis.rpush(key, json.dumps(action, ensure_ascii=False))
        self.redis.expire(key, 86400 * 7)

    def get_history(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取操作历史"""
        key = self._get_key(session_id, "history")
        history = self.redis.lrange(key, 0, limit - 1)

        return [json.loads(h) for h in history]

    def delete_session(self, session_id: str) -> None:
        """删除会话"""
        key = self._get_key(session_id)
        history_key = self._get_key(session_id, "history")

        self.redis.delete(key, history_key)


class InMemoryStateManager:
    """内存状态管理器（用于开发/测试）"""

    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(self, session_id: str, initial_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建新会话"""
        session_data = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "current_section": 1,
            "progress": {str(i): "not_started" for i in range(1, 10)},
            "form_data": {str(i): {} for i in range(1, 10)}
        }

        if initial_data:
            session_data.update(initial_data)

        self.sessions[session_id] = session_data
        return session_data

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话数据"""
        return self.sessions.get(session_id)

    def update_progress(self, session_id: str, section: int, status: str) -> None:
        """更新部分进度"""
        if session_id in self.sessions:
            self.sessions[session_id]["progress"][str(section)] = status
            self.sessions[session_id]["updated_at"] = datetime.now().isoformat()

    def get_progress(self, session_id: str) -> Dict[str, str]:
        """获取进度状态"""
        if session_id in self.sessions:
            return self.sessions[session_id].get("progress", {})
        return {}

    def set_current_section(self, session_id: str, section: int) -> None:
        """设置当前部分"""
        if session_id in self.sessions:
            self.sessions[session_id]["current_section"] = section
            self.sessions[session_id]["updated_at"] = datetime.now().isoformat()

    def get_current_section(self, session_id: str) -> int:
        """获取当前部分"""
        if session_id in self.sessions:
            return self.sessions[session_id].get("current_section", 1)
        return 1

    def save_form_data(self, session_id: str, section: int, data: Dict[str, Any]) -> None:
        """保存表单数据"""
        if session_id in self.sessions:
            section_key = str(section)
            if section_key not in self.sessions[session_id]["form_data"]:
                self.sessions[session_id]["form_data"][section_key] = {}
            self.sessions[session_id]["form_data"][section_key].update(data)
            self.sessions[session_id]["updated_at"] = datetime.now().isoformat()

    def get_form_data(self, session_id: str, section: Optional[int] = None) -> Dict[str, Any]:
        """获取表单数据"""
        if session_id not in self.sessions:
            return {} if section is None else {}

        if section:
            return self.sessions[session_id]["form_data"].get(str(section), {})

        return self.sessions[session_id]["form_data"]

    def add_history(self, session_id: str, action: Dict[str, Any]) -> None:
        """添加操作历史"""
        if session_id in self.sessions:
            if "history" not in self.sessions[session_id]:
                self.sessions[session_id]["history"] = []
            self.sessions[session_id]["history"].append(action)

    def get_history(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取操作历史"""
        if session_id in self.sessions:
            history = self.sessions[session_id].get("history", [])
            return history[-limit:]
        return []

    def delete_session(self, session_id: str) -> None:
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]


# 根据环境选择状态管理器
# 改用数据库管理器实现会话持久化
from tantan.backend.state.database_manager import DatabaseStateManager
StateManager = DatabaseStateManager
