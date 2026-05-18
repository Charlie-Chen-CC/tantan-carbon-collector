# State - 状态管理

会话状态管理，支持内存和Redis两种模式。

## 状态管理器

### InMemoryStateManager
开发环境使用，数据存储在内存中。
- 重启后数据丢失
- 适合开发调试

### RedisStateManager
生产环境使用，数据存储在Redis。
- 支持会话持久化
- 支持跨进程共享
- 7天数据过期

## 会话数据结构

```python
{
    "session_id": str,
    "created_at": ISO8601时间,
    "updated_at": ISO8601时间,
    "current_section": int,  # 1-9
    "progress": {
        "1": "not_started|in_progress|completed",
        "2": "...",
        ...
    },
    "form_data": {
        "1": {字段名: 值, ...},
        "2": {...},
        ...
    }
}
```

## 主要方法

```python
state_manager.create_session(session_id)  # 创建会话
state_manager.get_session(session_id)     # 获取会话
state_manager.update_progress(session_id, section, status)  # 更新进度
state_manager.set_current_section(session_id, section)       # 设置当前部分
state_manager.save_form_data(session_id, section, data)      # 保存表单数据
state_manager.get_form_data(session_id, section)             # 获取表单数据
state_manager.add_history(session_id, action)                # 添加操作历史
state_manager.get_history(session_id, limit)                 # 获取历史
```

## 切换模式

默认使用 `InMemoryStateManager`。如需切换到Redis，修改导入：
```python
from tantan.backend.state.manager import StateManager
StateManager = RedisStateManager  # 需要配置REDIS_URL环境变量
```