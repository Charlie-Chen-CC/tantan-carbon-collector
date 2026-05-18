# Queue - Celery任务队列

异步任务处理队列（预留，当前未启用）。

## 任务示例

```python
from tantan.backend.queue.celery_app import app

@app.task
def process_file_task(session_id: str, file_path: str):
    # 异步处理文件
    pass
```

## 配置

需要在 `.env` 中配置 `REDIS_URL`。