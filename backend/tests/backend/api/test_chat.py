"""
Chat API 集成测试 - 普通 chat / 流式 chat

注意：chat 端点依赖 LLM 真实响应（dashscope API）。
在没有 mock 的情况下，测试只验证：
  - 端点可达 + 鉴权拦截
  - 请求体校验
  - 响应结构（可能因网络/LLM 失败而跳过）
"""
import json

import pytest
from fastapi.testclient import TestClient


class TestChatAuth:
    """聊天鉴权"""

    def test_chat_without_auth(self, client: TestClient):
        """未登录 chat 应 401"""
        resp = client.post(
            "/api/chat",
            json={"session_id": "fake", "message": "hi"},
        )
        assert resp.status_code == 401

    def test_chat_missing_session_id(self, registered_user):
        """缺 session_id 应 422"""
        client = registered_user["client"]
        resp = client.post("/api/chat", json={"message": "hi"})
        assert resp.status_code == 422

    def test_chat_session_not_found(self, registered_user):
        """不存在的 session_id 应 404"""
        client = registered_user["client"]
        resp = client.post(
            "/api/chat",
            json={"session_id": "nonexistent_session", "message": "hi"},
        )
        # 期望 404；如后端先鉴权也接受 401
        assert resp.status_code in (404, 401, 400), f"未预期状态码: {resp.status_code} {resp.text}"


class TestChatStream:
    """流式 chat 鉴权 + 响应格式"""

    def test_stream_without_auth(self, client: TestClient):
        """未登录流式 chat 应 401"""
        resp = client.post(
            "/api/chat/stream",
            json={"session_id": "fake", "message": "hi"},
        )
        assert resp.status_code == 401

    def test_stream_session_not_found(self, registered_user):
        """不存在的 session_id 应 404"""
        client = registered_user["client"]
        resp = client.post(
            "/api/chat/stream",
            json={"session_id": "nonexistent_session", "message": "hi"},
        )
        assert resp.status_code in (404, 401, 400)

    def test_stream_chitchat_emits_sse_events(self, registered_user):
        """Phase 5.3 真实流式：chitchat 意图应依次 yield intent → message → done"""
        client = registered_user["client"]
        sess = client.post("/api/session").json()
        session_id = sess["session_id"]

        with client.stream(
            "POST", "/api/chat/stream",
            json={"session_id": session_id, "message": "你好"},
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")

            events = []
            for line in resp.iter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    events.append(("event", line.split(":", 1)[1].strip()))
                elif line.startswith("data:"):
                    events.append(("data", line.split(":", 1)[1].strip()))

        event_types = [e[1] for e in events if e[0] == "event"]
        assert event_types == ["intent", "message", "done"], f"实际事件序列: {event_types}"

        data_by_event: dict[str, str] = {}
        current = None
        for kind, val in events:
            if kind == "event":
                current = val
                data_by_event.setdefault(current, "")
            elif kind == "data" and current:
                data_by_event[current] += val

        intent_payload = json.loads(data_by_event["intent"])
        assert intent_payload["intent"] == "chitchat"

        message_payload = json.loads(data_by_event["message"])
        assert "chunk" in message_payload
        assert message_payload["chunk"]

        done_payload = json.loads(data_by_event["done"])
        assert "full_content" in done_payload
        assert done_payload["full_content"] == message_payload["chunk"]

    def test_stream_chitchat_persists_history(self, registered_user):
        """流式响应完成后应持久化到 history（action=chat）"""
        client = registered_user["client"]
        sess = client.post("/api/session").json()
        session_id = sess["session_id"]

        with client.stream(
            "POST", "/api/chat/stream",
            json={"session_id": session_id, "message": "你好"},
        ) as resp:
            assert resp.status_code == 200
            for _ in resp.iter_lines():
                pass

        hist = client.get(f"/api/history/{session_id}")
        assert hist.status_code == 200, hist.text
        body = hist.json()
        history_items = body.get("history", []) if isinstance(body, dict) else body
        actions = [h.get("action") for h in history_items if isinstance(h, dict)]
        assert "chat" in actions, f"未持久化 chat history: {actions}"

    def test_stream_guidance_no_llm_needed(self, registered_user):
        """guidance 意图（规则回答）也应走真实流式通道"""
        client = registered_user["client"]
        sess = client.post("/api/session").json()
        session_id = sess["session_id"]

        with client.stream(
            "POST", "/api/chat/stream",
            json={"session_id": session_id, "message": "怎么填这部分"},
        ) as resp:
            assert resp.status_code == 200
            body_chunks = list(resp.iter_lines())

        body = "\n".join(body_chunks)
        assert "event: intent" in body
        assert "event: message" in body
        assert "event: done" in body
