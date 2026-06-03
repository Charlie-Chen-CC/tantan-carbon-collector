"""
Form API 集成测试 - CRUD

- POST /api/session         创建会话
- GET  /api/session/{id}    获取会话
- GET  /api/form/{id}       获取表单
- PATCH /api/form/{id}/section/{n}  更新字段
- POST /api/form/{id}/section/{n}/confirm  确认部分
- POST /api/form/{id}/current-section     切换
"""
import pytest
from fastapi.testclient import TestClient


class TestSessionCRUD:
    """会话 CRUD"""

    def test_create_session(self, registered_user):
        """创建会话应返回 session_id + 进度"""
        client = registered_user["client"]
        resp = client.post("/api/session")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "session_id" in body
        assert "progress" in body
        assert "current_section" in body
        assert body["current_section"] == 1

    def test_get_session(self, registered_user):
        """获取刚创建的会话应成功"""
        client = registered_user["client"]
        sess = client.post("/api/session").json()
        resp = client.get(f"/api/session/{sess['session_id']}")
        assert resp.status_code == 200
        assert resp.json()["session_id"] == sess["session_id"]

    def test_get_nonexistent_session(self, registered_user):
        """不存在的 session 应 404"""
        client = registered_user["client"]
        resp = client.get("/api/session/ghost_session_xxx")
        assert resp.status_code in (404, 400)

    def test_create_session_without_auth(self, client: TestClient):
        """未登录创建会话应 401"""
        resp = client.post("/api/session")
        assert resp.status_code == 401


class TestFormGet:
    """表单获取"""

    def test_get_form(self, registered_user):
        """获取表单应返回 form_data 结构"""
        client = registered_user["client"]
        sess = client.post("/api/session").json()

        resp = client.get(f"/api/form/{sess['session_id']}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["session_id"] == sess["session_id"]
        assert "progress" in body
        assert "current_section" in body
        assert "form_data" in body

    def test_get_form_nonexistent(self, registered_user):
        """获取不存在会话的表单应 404"""
        client = registered_user["client"]
        resp = client.get("/api/form/ghost_xxx")
        assert resp.status_code in (404, 400)


class TestSectionUpdate:
    """section 数据更新"""

    def test_update_section(self, registered_user):
        """PATCH section 应更新 form_data（field/value 用 form 而非 json）"""
        client = registered_user["client"]
        sess = client.post("/api/session").json()

        resp = client.patch(
            f"/api/form/{sess['session_id']}/section/1",
            data={"field": "enterpriseName", "value": "测试企业"},
        )
        assert resp.status_code == 200, resp.text

        # 再 GET 验证写入
        form = client.get(f"/api/form/{sess['session_id']}").json()
        assert form["form_data"].get("1", {}).get("enterpriseName") == "测试企业"


class TestSectionConfirm:
    """section 确认"""

    def test_confirm_section(self, registered_user):
        """confirm 应返回 200 + 进度更新"""
        client = registered_user["client"]
        sess = client.post("/api/session").json()

        resp = client.post(
            f"/api/form/{sess['session_id']}/section/1/confirm",
            json={"data": {"enterpriseName": "已确认企业"}},
        )
        assert resp.status_code == 200, resp.text
        # 验证进度更新
        form = client.get(f"/api/form/{sess['session_id']}").json()
        assert form["progress"].get("1") in ("completed", "in_progress")


class TestCurrentSection:
    """切换当前 section"""

    def test_switch_section(self, registered_user):
        """切换到 section 2 应成功（section 是 query 参数）"""
        client = registered_user["client"]
        sess = client.post("/api/session").json()

        resp = client.post(
            f"/api/form/{sess['session_id']}/current-section?section=2",
        )
        assert resp.status_code == 200, resp.text

        form = client.get(f"/api/form/{sess['session_id']}").json()
        assert form["current_section"] == 2

    def test_switch_invalid_section(self, registered_user):
        """切换到非法 section 应 400"""
        client = registered_user["client"]
        sess = client.post("/api/session").json()

        resp = client.post(
            f"/api/form/{sess['session_id']}/current-section?section=99",
        )
        assert resp.status_code in (400, 422)
