"""
AppException 单元测试 - S3.12 错误处理统一

关键断言：
- AppException 继承 HTTPException，status_code 可定制
- 响应体只暴露 error_code + user_message（developer_message 不外露）
- ErrorCode 枚举值稳定（前端可基于此做 i18n）
"""
import pytest
from fastapi import HTTPException

from tantan.backend.utils.exceptions import AppException, ErrorCode


class TestAppExceptionShape:
    """AppException 数据契约"""

    def test_default_status_400(self):
        e = AppException(ErrorCode.INTERNAL_ERROR, "服务暂时不可用")
        assert e.status_code == 400
        assert e.detail == {
            "error_code": "INTERNAL_ERROR",
            "user_message": "服务暂时不可用",
        }

    def test_custom_status(self):
        e = AppException(ErrorCode.SESSION_NOT_FOUND, "会话不存在", status_code=404)
        assert e.status_code == 404

    def test_developer_message_defaults_to_user(self):
        e = AppException(ErrorCode.INTERNAL_ERROR, "失败")
        assert e.developer_message == "失败"

    def test_developer_message_kept_internal(self):
        """developer_message 不应出现在 detail 中（仅写日志）"""
        e = AppException(
            ErrorCode.INTERNAL_ERROR,
            user_message="服务暂时不可用",
            developer_message="SQL: SELECT * FROM secret_table",
        )
        # 关键断言：detail 不应泄露 developer_message
        assert "SQL" not in str(e.detail)
        assert "secret_table" not in str(e.detail)
        assert e.developer_message == "SQL: SELECT * FROM secret_table"

    def test_inherits_http_exception(self):
        e = AppException(ErrorCode.INTERNAL_ERROR, "x")
        assert isinstance(e, HTTPException)

    def test_error_code_in_detail(self):
        e = AppException(ErrorCode.FILE_TOO_LARGE, "文件过大", status_code=413)
        assert e.detail["error_code"] == "FILE_TOO_LARGE"
        assert e.detail["user_message"] == "文件过大"


class TestErrorCodeEnum:
    """ErrorCode 枚举值稳定（前端契约）"""

    def test_all_error_codes_have_string_values(self):
        for code in ErrorCode:
            assert isinstance(code.value, str)
            assert len(code.value) > 0

    @pytest.mark.parametrize("code_name", [
        "INTERNAL_ERROR", "INVALID_REQUEST",
        "AUTH_REQUIRED", "AUTH_TOKEN_EXPIRED",
        "SESSION_NOT_FOUND", "SESSION_INVALID_SECTION",
        "FILE_TOO_LARGE", "UNSUPPORTED_FILE_TYPE",
        "EXTRACTION_FAILED", "FORM_FILL_FAILED",
    ])
    def test_required_codes_exist(self, code_name: str):
        """前端用到的关键错误码必须存在"""
        assert hasattr(ErrorCode, code_name)
        assert isinstance(getattr(ErrorCode, code_name).value, str)
