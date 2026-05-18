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
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from tantan.backend.api.routes import router
from tantan.backend.api.auth import router as auth_router
from tantan.backend.models.database import init_db
from tantan.backend.utils import get_logger, TraceContext, configure_default_logging

# 确保 logs 目录存在
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 配置日志
configure_default_logging()
logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件，注入 trace_id 并记录请求/响应"""

    async def dispatch(self, request: Request, call_next):
        # 生成 trace_id
        trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
        TraceContext.set_trace_id(trace_id)

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
            TraceContext.clear()

# 创建FastAPI应用
app = FastAPI(
    title="碳管师收资系统",
    description="Multi-Agent碳排放资料收集系统",
    version="0.1.0"
)

# 添加请求日志中间件
app.add_middleware(RequestLoggingMiddleware)

# 配置CORS - 从环境变量读取允许的域名
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由器
app.include_router(router)
app.include_router(auth_router)

# 配置静态文件服务
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "tantan"}


@app.on_event("startup")
async def startup_event():
    """启动时初始化"""
    logger.info("碳管师收资系统启动中...")
    init_db()
    logger.info("碳管师收资系统启动成功")


if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    uvicorn.run(app, host="0.0.0.0", port=args.port)
