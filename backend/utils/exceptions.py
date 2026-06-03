"""
统一错误处理体系 - 碳管师收资系统

设计目标：
- 替代散乱的 `return {"error": str(e)}` 和 `raise HTTPException(400, "...")`
- `error_code` 给前端做 i18n / 路由跳转
- `user_message` 直接展示给用户
- `developer_message` 仅写入日志，不返回前端（避免泄露 SQL/文件路径/堆栈）

使用方式：
    from tantan.backend.utils.exceptions import AppException, ErrorCode

    raise AppException(ErrorCode.SESSION_NOT_FOUND, "会话不存在，请重新创建")
    raise AppException(ErrorCode.EXTRACTION_FAILED, "文件提取失败",
                       developer_message=f"section={section}, file={filename}")
"""
from enum import Enum
from fastapi import HTTPException


class ErrorCode(str, Enum):
    """错误码枚举（前端可基于此做 i18n）"""
    # 通用
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"

    # 认证
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_USER_DISABLED = "AUTH_USER_DISABLED"

    # 会话
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    SESSION_INVALID_SECTION = "SESSION_INVALID_SECTION"

    # 文件
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    FILE_EMPTY = "FILE_EMPTY"
    FILE_CONTENT_MISMATCH = "FILE_CONTENT_MISMATCH"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"

    # 提取 / 表单
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    FORM_FILL_FAILED = "FORM_FILL_FAILED"

    # 资源
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    OPERATION_NOT_ALLOWED = "OPERATION_NOT_ALLOWED"


class AppException(HTTPException):
    """业务异常 - 携带 error_code + user_message

    响应体形如：
    {
      "error_code": "FILE_TOO_LARGE",
      "user_message": "文件大小超过限制(10MB)"
    }
    """
    def __init__(
        self,
        error_code: ErrorCode,
        user_message: str,
        status_code: int = 400,
        developer_message: str | None = None,
    ):
        self.error_code = error_code
        self.user_message = user_message
        self.developer_message = developer_message or user_message
        super().__init__(
            status_code=status_code,
            detail={
                "error_code": error_code.value,
                "user_message": user_message,
            }
        )
