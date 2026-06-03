"""
Auth API 集成测试 - 注册 / 登录 / 登出 / me / cookie
"""
import pytest
from fastapi.testclient import TestClient


class TestRegister:
    """注册流程"""

    def test_register_success_sets_cookie(self, client: TestClient, test_user: dict):
        """注册成功应返回 token + 设置 httpOnly cookie"""
        resp = client.post("/api/auth/register", json=test_user)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "access_token" in body
        assert body["username"] == test_user["username"]
        assert "user_id" in body

        # 验证 cookie
        cookies = resp.cookies
        assert "auth_token" in cookies, f"未设置 auth_token cookie, cookies={dict(cookies)}"
        assert cookies["auth_token"] == body["access_token"]

    def test_register_duplicate_username(self, client: TestClient, test_user: dict):
        """重复注册相同用户名应 400"""
        resp1 = client.post("/api/auth/register", json=test_user)
        assert resp1.status_code == 200
        resp2 = client.post("/api/auth/register", json=test_user)
        assert resp2.status_code == 400
        assert "已存在" in str(resp2.json())

    def test_register_missing_field(self, client: TestClient, test_user: dict):
        """缺必填字段应 422"""
        incomplete = {"username": test_user["username"]}
        resp = client.post("/api/auth/register", json=incomplete)
        assert resp.status_code == 422


class TestLogin:
    """登录流程"""

    def test_login_success(self, client: TestClient, test_user: dict):
        """登录成功应返回 token + 设置 cookie"""
        # 先注册
        client.post("/api/auth/register", json=test_user)

        # 再登录（清空 cookie 模拟不同 session）
        client.cookies.clear()
        resp = client.post(
            "/api/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["username"] == test_user["username"]
        assert "auth_token" in resp.cookies

    def test_login_wrong_password(self, client: TestClient, test_user: dict):
        """密码错误应 401"""
        client.post("/api/auth/register", json=test_user)
        resp = client.post(
            "/api/auth/login",
            json={"username": test_user["username"], "password": "wrong_password"},
        )
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client: TestClient):
        """不存在的用户应 401"""
        resp = client.post(
            "/api/auth/login",
            json={"username": "ghost_user_xxx", "password": "any"},
        )
        assert resp.status_code == 401


class TestGetMe:
    """获取当前用户"""

    def test_get_me_with_cookie(self, registered_user):
        """带 cookie 调 /me/cookie 应成功"""
        client = registered_user["client"]
        resp = client.get("/api/auth/me/cookie")
        assert resp.status_code == 200, resp.text
        assert resp.json()["username"] == registered_user["user"]["username"]

    def test_get_me_without_cookie(self, client: TestClient):
        """无 cookie 调 /me 应 401"""
        resp = client.get("/api/auth/me/cookie")
        assert resp.status_code == 401


class TestLogout:
    """登出"""

    def test_logout_clears_cookie(self, registered_user):
        """登出应清除 cookie"""
        client = registered_user["client"]
        resp = client.post("/api/auth/logout")
        # 登出接口可能 200 或 204
        assert resp.status_code in (200, 204), resp.text
        # 验证 Set-Cookie 头包含 max-age=0 或 expires 过期
        set_cookie = resp.headers.get("set-cookie", "")
        assert "auth_token" in set_cookie.lower()
        # cookie 应被清除
        assert "auth_token" not in client.cookies or client.cookies.get("auth_token") in ("", None)
