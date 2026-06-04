"""
统一错误处理测试 - P0-1 回归保护

目的：
1. 强制所有 router 使用 AppException，禁止直接 raise HTTPException
2. 禁止任何异常构造包含 str(e) → 不允许把内部异常原文（SQL/路径/堆栈）暴露给前端
3. 校验 AppException 响应体只包含 error_code + user_message，不含 developer_message

这是 S3.12 / 3.1 报告里 3 Agent 独立交叉验证的 P0 修复的守门员。
"""
import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tantan.backend.main import app
from tantan.backend.utils.exceptions import AppException, ErrorCode


# 路由文件白名单（应全部用 AppException）
ROUTER_FILES = [
    "backend/api/auth.py",
    "backend/api/chat_router.py",
    "backend/api/extract_router.py",
    "backend/api/files_router.py",
    "backend/api/form_router.py",
    "backend/api/history_router.py",
    "backend/api/sessions_router.py",
    "backend/api/validation.py",
]


def _project_root() -> Path:
    """tantan 项目根（tantan/backend/tests/backend/api/... → tantan/）"""
    # 实际路径: .../tantan/backend/tests/backend/api/test_exceptions.py
    # parents[4] = .../tantan/  ← project root
    return Path(__file__).resolve().parents[4]


def _collect_raise_calls(tree: ast.AST) -> list[ast.Call]:
    """收集 AST 中所有 raise <expr> 里的 <expr>"""
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and node.exc is not None:
            if isinstance(node.exc, ast.Call):
                calls.append(node.exc)
    return calls


def _call_name(node: ast.Call) -> str | None:
    """提取调用名（如 'HTTPException' / 'AppException'）"""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


class TestRoutersUseAppException:
    """所有 router 禁止 raise HTTPException，必须用 AppException"""

    @pytest.mark.parametrize("rel_path", ROUTER_FILES)
    def test_no_http_exception_in_router(self, rel_path: str):
        full = _project_root() / rel_path
        if not full.exists():
            pytest.skip(f"router file not found: {rel_path}")

        tree = ast.parse(full.read_text(encoding="utf-8"))
        violations = []
        for call in _collect_raise_calls(tree):
            name = _call_name(call)
            if name == "HTTPException":
                # 报告行号便于定位
                line = call.lineno
                violations.append(f"{rel_path}:{line} → raise HTTPException(...)")

        assert not violations, (
            "Router 文件禁止直接 raise HTTPException，请改用 AppException:\n  "
            + "\n  ".join(violations)
        )


class TestNoStrELeakInRaises:
    """任何 raise AppException/HTTPException 的响应体都不应包含 str(...) 表达式

    str(e) 会把内部异常原文吐给前端，是 S3.12 / 6.3 报告的核心问题。
    规则：
    - HTTPException 的 detail 参数禁止包含 str(...)
    - AppException 的 user_message 参数禁止包含 str(...)
    - AppException 的 developer_message 参数允许 str(...)
      （developer_message 仅写日志，不出现在响应体）
    """

    # 各异常类里"对外可见"的参数名（响应体中能看到的内容）
    PUBLIC_PARAMS = {
        "HTTPException": {"detail"},
        "AppException": {"user_message"},
    }

    @pytest.mark.parametrize("rel_path", ROUTER_FILES)
    def test_no_str_call_in_user_visible_params(self, rel_path: str):
        full = _project_root() / rel_path
        if not full.exists():
            pytest.skip(f"router file not found: {rel_path}")

        tree = ast.parse(full.read_text(encoding="utf-8"))
        violations = []
        for call in _collect_raise_calls(tree):
            name = _call_name(call)
            if name not in self.PUBLIC_PARAMS:
                continue
            forbidden = self.PUBLIC_PARAMS[name]
            for kw in call.keywords:
                if kw.arg not in forbidden:
                    continue
                for sub in ast.walk(kw.value):
                    if isinstance(sub, ast.Call) and _call_name(sub) == "str":
                        line = call.lineno
                        violations.append(
                            f"{rel_path}:{line} → {name}({kw.arg}=...) contains str(...) call"
                        )

        assert not violations, (
            "异常响应对外可见参数禁止包含 str(...)（会泄露内部信息到前端），"
            "改用 AppException 的 developer_message:\n  "
            + "\n  ".join(violations)
        )


class TestAppExceptionResponseShape:
    """AppException 响应体只含 error_code + user_message"""

    def test_app_exception_response_omits_developer_message(self):
        """developer_message 只能写日志，不出现在响应体"""
        exc = AppException(
            ErrorCode.INTERNAL_ERROR,
            user_message="服务暂时不可用",
            status_code=500,
            developer_message="secret internal SQL: SELECT * FROM x WHERE y=internal_path",
        )

        sentinel_path = "/_test_app_exception_response_sentinel"
        # 注入临时路由
        @app.get(sentinel_path)
        def _route():
            raise exc

        try:
            with TestClient(app) as client:
                resp = client.get(sentinel_path)
                body = resp.json()
                assert "developer_message" not in body, (
                    f"developer_message 不应出现在响应体: {body}"
                )
                assert body.get("error_code") == ErrorCode.INTERNAL_ERROR.value
                assert body.get("user_message") == "服务暂时不可用"
                assert resp.status_code == 500
        finally:
            # 清理临时路由
            app.router.routes = [
                r for r in app.router.routes
                if getattr(r, "path", None) != sentinel_path
            ]

    def test_errorcode_enum_is_stable(self):
        """ErrorCode 枚举值不能轻易改（前端 i18n 依赖）"""
        assert ErrorCode.INTERNAL_ERROR.value == "INTERNAL_ERROR"
        assert ErrorCode.AUTH_REQUIRED.value == "AUTH_REQUIRED"
        assert ErrorCode.SESSION_NOT_FOUND.value == "SESSION_NOT_FOUND"
        assert ErrorCode.FILE_NOT_FOUND.value == "FILE_NOT_FOUND"

    def test_unauth_returns_app_exception_format(self):
        """未认证请求应返回 AppException 格式而非 FastAPI 默认 401"""
        with TestClient(app) as client:
            resp = client.get("/api/session/missing-session-id")
            assert resp.status_code == 401
            body = resp.json()
            assert "error_code" in body, f"应包含 error_code: {body}"
            assert body["error_code"] == ErrorCode.AUTH_REQUIRED.value
            assert "user_message" in body
            assert "developer_message" not in body, (
                f"developer_message 不应出现在 401 响应: {body}"
            )

    def test_404_session_returns_app_exception_format(self, registered_user):
        """访问不存在的 session 应返回 SESSION_NOT_FOUND 错误码"""
        client = registered_user["client"]
        resp = client.get("/api/session/fake-session-id-that-does-not-exist")
        assert resp.status_code == 404
        body = resp.json()
        assert body.get("error_code") == ErrorCode.SESSION_NOT_FOUND.value
        assert "user_message" in body
        assert "developer_message" not in body
