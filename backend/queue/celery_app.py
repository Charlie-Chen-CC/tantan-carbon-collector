"""
Celery配置 - 碳管师收资系统
使用Redis作为消息队列
"""

import os
from celery import Celery
from kombu import Exchange, Queue

# 从环境变量读取配置，允许使用默认值
def _get_redis_url(db: int = 0) -> str:
    """获取Redis URL"""
    return os.environ.get("REDIS_URL", f"redis://localhost:6379/{db}")

# Celery配置
broker_url = _get_redis_url(1)
result_backend = _get_redis_url(2)

# 任务路由
task_routes = {
    "tantan.file_extract.*": {"queue": "file_extract"},
    "tantan.form_fill.*": {"queue": "form_fill"},
    "tantan.qa.*": {"queue": "qa"},
    "tantan.modify.*": {"queue": "modify"},
    "tantan.orchestrator.*": {"queue": "orchestrator"},
}

# 队列定义
task_queues = (
    Queue("orchestrator", Exchange("orchestrator"), routing_key="orchestrator"),
    Queue("file_extract", Exchange("file_extract"), routing_key="file_extract"),
    Queue("form_fill", Exchange("form_fill"), routing_key="form_fill"),
    Queue("qa", Exchange("qa"), routing_key="qa"),
    Queue("modify", Exchange("modify"), routing_key="modify"),
)

# 创建Celery应用
celery_app = Celery(
    "tantan",
    broker=broker_url,
    backend=result_backend,
    include=[
        "tantan.backend.queue.celery_app",
    ]
)

# 配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5分钟超时
    task_soft_time_limit=240,  # 4分钟软超时
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)


@celery_app.task(name="tantan.file_extract.process")
def process_file_extract(msg_id: str, section: int, session_id: str, file_path: str):
    """处理文件提取任务"""
    from tantan.backend.agents.file_extractor import FileExtractAgent

    agent = FileExtractAgent(section)

    with open(file_path, "rb") as f:
        file_content = f.read()

    result = agent.process(file_content)

    return {
        "msg_id": msg_id,
        "section": section,
        "session_id": session_id,
        "result": result
    }


@celery_app.task(name="tantan.form_fill.process")
def process_form_fill(msg_id: str, section: int, session_id: str, data: dict):
    """处理表单填报任务"""
    from tantan.backend.agents.form_filler import FormFillAgent

    agent = FormFillAgent(section)
    result = agent.fill_form(data)

    return {
        "msg_id": msg_id,
        "section": section,
        "session_id": session_id,
        "result": result
    }


@celery_app.task(name="tantan.qa.process")
def process_qa(msg_id: str, session_id: str, message: str, context: dict):
    """处理对话问答任务"""
    from tantan.backend.agents.qa_agent import QAAgent

    agent = QAAgent()
    agent.set_session(session_id)

    result = agent.generate_response(message, context)

    return {
        "msg_id": msg_id,
        "session_id": session_id,
        "result": result
    }


@celery_app.task(name="tantan.modify.process")
def process_modify(msg_id: str, session_id: str, section: int, field: str, old_value, new_value: str):
    """处理修改任务"""
    from tantan.backend.agents.modify_agent import ModifyAgent

    agent = ModifyAgent()

    result = agent.process_modify_request(
        section=section,
        field=field,
        old_value=old_value,
        new_value=new_value
    )

    return {
        "msg_id": msg_id,
        "session_id": session_id,
        "result": result
    }


@celery_app.task(name="tantan.orchestrator.route")
def route_message(msg_id: str, session_id: str, message_type: str, payload: dict):
    """路由消息到合适的Agent"""
    from tantan.backend.agents.orchestrator import OrchestratorAgent

    # 这里应该从Redis获取OrchestratorAgent实例
    agent = OrchestratorAgent(session_id)

    result = agent.route_message(message_type, payload)

    return {
        "msg_id": msg_id,
        "session_id": session_id,
        "result": result
    }
