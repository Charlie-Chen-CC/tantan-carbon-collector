"""
API 集成测试 conftest - 共享 TestClient + 测试用户 fixture
"""
import time
import pytest
from fastapi.testclient import TestClient

from tantan.backend.main import app
from tantan.backend.models.database import get_db
from tantan.backend.utils.ratelimit import reset_limiter


@pytest.fixture(autouse=True)
def _clear_ratelimit_state():
    """每个测试前清空 slowapi 限流计数

    测试套件共享 127.0.0.1，连续注册/登录会很快耗尽 5/min 的 AUTH_DEFAULT。
    """
    reset_limiter()
    yield
    reset_limiter()


@pytest.fixture(scope="function")
def client():
    """FastAPI TestClient - 每个测试独立实例避免状态污染"""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def test_user() -> dict:
    """生成唯一测试用户（带时间戳避免冲突）"""
    suffix = str(int(time.time() * 1000))[-8:]
    return {
        "username": f"api_test_{suffix}",
        "password": "TestPwd123!",
        "email": f"api_test_{suffix}@example.com",
        "enterprise_name": "API测试企业",
        "industry": "测试行业",
    }


@pytest.fixture(scope="function")
def registered_user(client: TestClient, test_user: dict):
    """注册并返回 client + user_info（已自动登录带 cookie）"""
    resp = client.post("/api/auth/register", json=test_user)
    assert resp.status_code == 200, f"注册失败: {resp.text}"
    return {"client": client, "user": resp.json(), "password": test_user["password"]}


@pytest.fixture(scope="function")
def db_session():
    """直接给一个 DB session（用于清理测试数据）"""
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()
