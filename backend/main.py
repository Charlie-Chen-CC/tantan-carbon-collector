"""
碳管师收资系统 - FastAPI主入口
"""

import os
import logging
import uuid
import time
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from tantan.backend.api.routes import api_router
from tantan.backend.config import get_config
from tantan.backend.models.database import init_db, User, get_db_context
from tantan.backend.utils import (
    get_logger,
    TraceContext,
    configure_default_logging,
    is_telemetry_configured,
    is_metrics_configured,
    is_ratelimit_configured,
    setup_telemetry,
    setup_metrics,
    setup_ratelimit,
)
from tantan.backend.utils.exceptions import AppException, ErrorCode

# 确保 logs 目录存在
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 配置日志
configure_default_logging()
logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件，注入 trace_id 并记录请求/响应

    Phase 5.4：用 token-based reset 替换 clear()，避免在异常路径下污染下一个请求的 trace_id。
    """

    async def dispatch(self, request: Request, call_next):
        # 生成 trace_id
        trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
        token = TraceContext.set_trace_id(trace_id)

        # 记录请求开始
        request_id = str(uuid.uuid4())
        start_time = time.time()

        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "trace_id": trace_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else None
            }
        )

        try:
            response = await call_next(request)

            # 记录请求完成
            duration = time.time() - start_time
            logger.info(
                f"Request completed: {request.method} {request.url.path} - {response.status_code} ({duration:.3f}s)",
                extra={
                    "trace_id": trace_id,
                    "status_code": response.status_code,
                    "duration": duration
                }
            )

            # 在响应头中添加 trace_id
            response.headers["X-Trace-ID"] = trace_id

            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} - {type(e).__name__}: {str(e)}",
                exc_info=True,
                extra={
                    "trace_id": trace_id,
                    "duration": duration,
                    "exception_type": type(e).__name__
                }
            )
            raise
        finally:
            TraceContext.reset(token)

# 创建FastAPI应用
app = FastAPI(
    title="碳管师收资系统",
    description="Multi-Agent碳排放资料收集系统",
    version="0.1.0"
)

# Phase 5.6：OTel 默认关闭；OTEL_ENABLED=true 启动
if is_telemetry_configured():
    setup_telemetry(app)
    logger.info("OpenTelemetry 已启用")

# Phase 5.7：Prometheus metrics 默认关闭；METRICS_ENABLED=true 启动
if is_metrics_configured():
    setup_metrics(app)
    logger.info("Prometheus metrics 已启用 (/metrics)")

# Phase 5.8：slowapi 速率限制默认开启；RATELIMIT_ENABLED=false 关闭
if is_ratelimit_configured():
    setup_ratelimit(app)
    logger.info("速率限制已启用")


# ============== 统一错误处理 ==============

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """AppException 处理器：developer_message 仅写日志，响应体只给 user_message"""
    logger.error(
        f"AppException: {exc.error_code.value} | {exc.developer_message}",
        extra={
            "error_code": exc.error_code.value,
            "path": request.url.path,
        }
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code.value,
            "user_message": exc.user_message,
        }
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """未捕获异常兜底：绝不向客户端泄露堆栈/SQL/路径"""
    logger.exception(
        f"Unhandled exception on {request.method} {request.url.path}: {type(exc).__name__}: {exc}"
    )
    return JSONResponse(
        status_code=500,
        content={
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "user_message": "服务暂时不可用，请稍后重试",
        }
    )


# 添加请求日志中间件
app.add_middleware(RequestLoggingMiddleware)

# 配置CORS - 从环境变量读取允许的域名
def _resolve_allowed_origins() -> list[str]:
    """解析 ALLOWED_ORIGINS：dev 默认 3000-3010；生产要求显式设置

    start.sh/start.bat 会探测 3000-3010 找可用端口；dev 必须放行这段区间
    否则前端从 3000 切到 3001 就会跨域。生产（ENVIRONMENT=production）必须
    显式设置 ALLOWED_ORIGINS，否则启动 fail-fast——不允许默认配置上线。
    """
    raw = os.getenv("ALLOWED_ORIGINS", "").strip()
    env = os.getenv("ENVIRONMENT", "development").lower()
    if not raw:
        if env == "production":
            raise ValueError(
                "生产环境必须显式设置 ALLOWED_ORIGINS（逗号分隔），"
                "例如：https://app.example.com,https://admin.example.com"
            )
        # dev 默认放行 3000-3010（start 脚本自动探测区间）
        return [f"http://localhost:{port}" for port in range(3000, 3011)]
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return origins


ALLOWED_ORIGINS = _resolve_allowed_origins()

# 安全检查：credentials=True 时不允许通配符
if "*" in ALLOWED_ORIGINS:
    raise ValueError(
        "CORS配置错误：allow_credentials=True时，不允许使用通配符'*'作为allow_origins。"
        "请在ALLOWED_ORIGINS环境变量中明确指定允许的域名。"
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Trace-ID"],
)

# 挂载路由器
app.include_router(api_router)

# 配置静态文件服务 - 已移除公开访问，改为通过 /api/files/{file_id} 受保护访问

# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "tantan"}


@app.on_event("startup")
async def startup_event():
    """启动时初始化"""
    logger.info("碳管师收资系统启动中...")
    init_db()

    # S5：生产环境禁止默认凭证
    config = get_config()
    if config.REQUIRE_NON_DEFAULT_CREDENTIALS and config.ENVIRONMENT == "production":
        with get_db_context() as db:
            user = db.query(User).filter(User.username == "tantan_user").first()
            if user and User.verify_password("tantan_password", user.password_hash):
                raise RuntimeError(
                    "生产环境禁止使用默认凭证 tantan_user/tantan_password，"
                    "请修改密码或将 REQUIRE_NON_DEFAULT_CREDENTIALS 设为 false"
                )

    logger.info("碳管师收资系统启动成功")


if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    uvicorn.run(app, host="0.0.0.0", port=args.port)
