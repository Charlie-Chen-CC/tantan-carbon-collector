# Models - 数据库模型

使用SQLAlchemy ORM定义PostgreSQL数据库模型。

## 数据表

### Session
会话表，存储每次填报会话的基本信息。
- `session_id` - 唯一会话标识
- `enterprise_name` - 企业名称
- `industry` - 所属行业
- `current_section` - 当前部分(1-9)
- `status` - 状态(active/completed/archived)

### SectionData
部分数据表，存储每个部分的表单数据。
- `session_id` - 外键关联Session
- `section_number` - 部分编号(1-9)
- `data` - JSON格式的表单数据
- `status` - not_started/in_progress/completed
- `file_path` - 上传的文件路径

### OperationHistory
操作历史表，记录所有用户操作。
- `session_id` - 外键关联Session
- `action_type` - file_upload/form_fill/chat/modify
- `section_number` - 相关部分
- `details` - JSON格式的详细信息

### UploadedFile
上传文件表。
- `session_id` - 外键关联Session
- `file_name` / `file_path` - 文件信息
- `file_type` / `file_size` - 文件元数据
- `status` - pending/processed/failed

### ConversationHistory
对话历史表。
- `session_id` - 外键关联Session
- `role` - user/assistant
- `message` - 消息内容
- `intent` - 意图类型

## 数据库初始化

```python
from tantan.backend.models.database import init_db, get_db
init_db()  # 创建所有表
```

## 获取会话

```python
for db in get_db():
    # 使用会话
    pass
```