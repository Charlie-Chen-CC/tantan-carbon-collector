# Queue - 异步任务队列

**Phase 5 待重建**。

Phase 0-4 期间：
- `celery_app.py` 已删除
- `celery[redis]` 已从 `requirements.txt` 移除
- LLM/文件处理全部走同步 `await` + 短超时

Phase 5 将：
- 新建 `celery_app.py`（接 Redis broker）
- 把 `agents/*.py` 里的耗时操作（LLM 推理、向量检索）改 `ainvoke().delay()`
- 本目录重新启用
