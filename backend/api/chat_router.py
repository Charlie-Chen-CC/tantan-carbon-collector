"""聊天 + 修改 路由

- POST /api/chat         非流式聊天
- POST /api/chat/stream  流式聊天（SSE）
- POST /api/modify/{session_id}  表单修改
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import ServerSentEvent

from tantan.backend.agents import QAAgent, ModifyAgent
from tantan.backend.api.auth import get_current_user
from tantan.backend.models.database import User
from tantan.backend.state.database_manager import DatabaseStateManager
from tantan.backend.utils import log_exception, record_chat_stream_chunk

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])
state_manager = DatabaseStateManager()


class ChatRequest(BaseModel):
    session_id: str
    message: str
    context: Optional[Dict[str, Any]] = None


class ModifyRequest(BaseModel):
    section: int
    field: str
    old_value: Any
    new_value: Any
    reason: Optional[str] = ""


@router.post("/chat")
async def chat(request: ChatRequest, current_user: User = Depends(get_current_user)):
    """发送消息"""
    try:
        session_data = state_manager.get_session(current_user.id, request.session_id)

        if not session_data:
            raise HTTPException(status_code=404, detail="会话不存在")

        qa_agent = QAAgent()
        qa_agent.set_session(request.session_id)

        response = qa_agent.generate_response(
            request.message,
            {"current_section": session_data.get("current_section", 1)}
        )

        state_manager.add_history(current_user.id, request.session_id, {
            "action": "chat",
            "user_message": request.message,
            "assistant_message": response["content"],
            "intent": response["intent"],
            "timestamp": datetime.now().isoformat()
        })

        return response
    except HTTPException:
        raise
    except Exception as e:
        log_exception(logger, e, {"session_id": request.session_id, "user_id": current_user.user_id, "action": "chat"})
        raise HTTPException(status_code=500, detail=f"AI响应失败: {str(e)}")


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, current_user: User = Depends(get_current_user)):
    """流式对话响应（SSE）- Phase 5.3 真实流式：LLM token-by-token

    注：使用 StreamingResponse + 预编码 bytes 而非 EventSourceResponse。
    sse_starlette 1.8+ 的 EventSourceResponse 内部有 AppStatus.should_exit_event
    类级 anyio.Event 单例，跨测试时会被绑定到已关闭的事件循环上抛 RuntimeError。
    直接 yield ServerSentEvent.encode() 的 bytes，绕过 EventSourceResponse 的
    ping/exit_signal 后台任务，行为等价但更稳。
    """
    try:
        session_data = state_manager.get_session(current_user.id, request.session_id)

        if not session_data:
            raise HTTPException(status_code=404, detail="会话不存在")

        qa_agent = QAAgent()
        qa_agent.set_session(request.session_id)

        context = {"current_section": session_data.get("current_section", 1)}

        def event_generator():
            full_content = ""
            intent = None
            msg_id = None
            for event in qa_agent.generate_response_stream(request.message, context):
                event_type = event.get("event")
                if event_type == "intent":
                    intent = event.get("intent")
                    msg_id = event.get("msg_id")
                    sse = ServerSentEvent(
                        event="intent",
                        data=json.dumps({
                            "intent": intent,
                            "msg_id": msg_id,
                            "session_id": event.get("session_id"),
                        }),
                    )
                elif event_type == "message":
                    chunk = event.get("chunk", "")
                    full_content += chunk
                    record_chat_stream_chunk(intent or "unknown")
                    sse = ServerSentEvent(
                        event="message",
                        data=json.dumps({"chunk": chunk}),
                    )
                elif event_type == "done":
                    sse = ServerSentEvent(
                        event="done",
                        data=json.dumps({"full_content": event.get("full_content", full_content)}),
                    )
                else:
                    continue
                yield sse.encode()

            try:
                state_manager.add_history(current_user.id, request.session_id, {
                    "action": "chat",
                    "user_message": request.message,
                    "assistant_message": full_content,
                    "intent": intent,
                    "msg_id": msg_id,
                    "timestamp": datetime.now().isoformat(),
                })
            except Exception as hist_err:
                logger.error(f"保存 chat history 失败: session_id={request.session_id}, error: {hist_err}", exc_info=True)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        log_exception(logger, e, {"session_id": request.session_id, "user_id": current_user.user_id, "action": "chat_stream"})
        raise HTTPException(status_code=500, detail=f"流式响应失败: {str(e)}")


@router.post("/modify/{session_id}")
async def modify_form(
    session_id: str,
    request: ModifyRequest,
    current_user: User = Depends(get_current_user)
):
    """修改表单数据"""
    try:
        session_data = state_manager.get_session(current_user.id, session_id)

        if not session_data:
            raise HTTPException(status_code=404, detail="会话不存在")

        current_data = state_manager.get_form_data(current_user.id, session_id, request.section)

        modify_agent = ModifyAgent()
        result = modify_agent.process_modify_request(
            section=request.section,
            field=request.field,
            old_value=request.old_value,
            new_value=request.new_value,
            reason=request.reason or "",
            current_data=current_data
        )

        if result["success"]:
            current_data[request.field] = request.new_value
            state_manager.save_form_data(current_user.id, session_id, request.section, current_data)

            state_manager.add_history(current_user.id, session_id, {
                "action": "modify",
                "section": request.section,
                "field": request.field,
                "old_value": request.old_value,
                "new_value": request.new_value,
                "reason": request.reason,
                "timestamp": datetime.now().isoformat()
            })

        return result
    except HTTPException:
        raise
    except Exception as e:
        log_exception(logger, e, {"session_id": session_id, "user_id": current_user.user_id, "action": "modify_form"})
        raise HTTPException(status_code=500, detail=f"修改表单失败: {str(e)}")
