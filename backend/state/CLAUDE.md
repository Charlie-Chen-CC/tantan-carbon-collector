# State - 状态管理

会话状态管理。**Phase 2 起统一使用 PostgreSQL 持久化**，无内存/Redis 分支。

## 状态管理器

### DatabaseStateManager
唯一状态管理器，PG 持久化 + SQLAlchemy ORM。
- 单实例，零状态（每次方法调用都从 `get_db_context()` 取 session）
- 支持会话级数据、表单数据、操作历史、上传文件
- 7天数据过期（通过 `created_at` + LRU 在应用层清理；DB 不主动删）

## 会话数据结构

```python
{
    "session_id": str,
    "created_at": ISO8601时间,
    "updated_at": ISO8601时间,
    "current_section": int,  # 1-9
    "progress": {
        "1": "not_started|in_progress|completed",
        ...
    },
    "form_data": {
        "1": {字段名: 值, ...},
        ...
    }
}
```

## 主要方法

```python
from tantan.backend.state.database_manager import DatabaseStateManager

sm = DatabaseStateManager()
sm.create_session(user_id, session_id)                # 创建会话
sm.get_session(user_id, session_id)                   # 获取会话
sm.get_user_sessions(user_id)                         # 用户的全部会话
sm.update_progress(user_id, session_id, section, status)   # 更新进度
sm.set_current_section(user_id, session_id, section)  # 设置当前部分
sm.save_form_data(user_id, session_id, section, data) # 保存表单数据
sm.get_form_data(user_id, session_id, section)        # 获取表单数据
sm.add_history(user_id, session_id, action)            # 添加操作历史
sm.get_history(user_id, session_id, limit)            # 获取历史
```

## 切换说明

- **历史**：曾有 `InMemoryStateManager` / `RedisStateManager` / `StateManager` shim，Phase 2 已统一删除
- 新代码直接 `from tantan.backend.state.database_manager import DatabaseStateManager`
- Phase 5 接入真实 Celery 时，状态接口不变，DB 写入异步化
