"""
统一日志模块 - 碳管师收资系统
提供结构化日志、请求追踪、异常堆栈记录、日志轮转
"""

import os
import sys
import logging
import traceback
from contextvars import ContextVar, Token
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from functools import wraps
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

# 确保 logs 目录存在
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 日志文件路径
LOG_FILE = LOG_DIR / "app.log"

# 按模块分类的日志文件
LOG_FILES = {
    "api": LOG_DIR / "api.log",
    "agent": LOG_DIR / "agent.log",
    "state": LOG_DIR / "state.log",
    "rag": LOG_DIR / "rag.log",
    "error": LOG_DIR / "error.log",
    "security": LOG_DIR / "security.log",
}

# Phase 5.4：trace_id 改用 contextvars 而非 threading.local
# 原因：在 async 上下文中，asyncio.Task 可在 await 边界跨线程（如 run_in_executor），
# threading.local 无法跨线程传播 trace_id。ContextVar 随 Task 一起传播，是 async 安全的。
_trace_id_var: ContextVar[Optional[str]] = ContextVar("tantan_trace_id", default=None)


class TraceContext:
    """请求追踪上下文

    Phase 5.4：底层从 threading.local 切到 contextvars.ContextVar，
    解决 async 跨线程时 trace_id 丢失的问题。
    """

    @classmethod
    def get_trace_id(cls) -> Optional[str]:
        return _trace_id_var.get()

    @classmethod
    def set_trace_id(cls, trace_id: str) -> Token:
        """设置 trace_id，返回 Token（与 ContextVar.set 约定一致）"""
        return _trace_id_var.set(trace_id)

    @classmethod
    def reset(cls, token: Token) -> None:
        """用 Token 还原到 set 之前的状态（推荐用于嵌套/异常路径）"""
        _trace_id_var.reset(token)

    @classmethod
    def clear(cls) -> None:
        """清空 trace_id（设为 None，保持与旧 API 兼容）"""
        _trace_id_var.set(None)


def get_trace_id() -> Optional[str]:
    """获取当前请求的 trace_id"""
    return TraceContext.get_trace_id()


class TraceContextFilter(logging.Filter):
    """日志过滤器：自动注入 trace_id"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id() or "-"
        return True


class ConsoleFormatter(logging.Formatter):
    """控制台格式：人类可读"""

    def format(self, record: logging.LogRecord) -> str:
        record.trace_id = get_trace_id() or "-"

        # 颜色码（只在TTY输出时启用）
        RESET = "\033[0m" if sys.stdout.isatty() else ""
        RED = "\033[31m" if sys.stdout.isatty() else ""
        YELLOW = "\033[33m" if sys.stdout.isatty() else ""
        BLUE = "\033[34m" if sys.stdout.isatty() else ""
        GREEN = "\033[32m" if sys.stdout.isatty() else ""

        level_colors = {
            "ERROR": RED,
            "WARNING": YELLOW,
            "INFO": GREEN,
            "DEBUG": BLUE,
        }
        color = level_colors.get(record.levelname, "")

        # 简化时间
        dt = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")

        msg = f"{color}[{dt}] [{record.trace_id[:8]}] {record.levelname:8} {record.name}: {record.getMessage()}{RESET}"

        if record.exc_info:
            msg += f"\n{''.join(traceback.format_exception(*record.exc_info))}"

        return msg


class JsonFormatter(logging.Formatter):
    """JSON格式日志：便于程序解析"""

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "trace_id": get_trace_id() or "-",
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_data["stack_trace"] = "".join(traceback.format_exception(*record.exc_info))

        return json.dumps(log_data, ensure_ascii=False)


def _get_log_level() -> int:
    """从环境变量获取日志级别"""
    level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_str, logging.INFO)


def _setup_module_logger(name: str) -> logging.Logger:
    """
    为单个模块设置日志记录器
    会自动分类写入对应文件
    """
    logger = logging.getLogger(name)
    logger.setLevel(_get_log_level())
    logger.propagate = False

    if logger.handlers:
        return logger

    # 添加 trace_id 过滤器
    trace_filter = TraceContextFilter()
    logger.addFilter(trace_filter)

    # 控制台 Handler（人类可读）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(_get_log_level())
    console_handler.setFormatter(ConsoleFormatter())
    logger.addHandler(console_handler)

    # 根据模块名决定写入哪个文件
    log_file = None
    if name.startswith("tantan.backend.api") or name == "api":
        log_file = LOG_FILES["api"]
    elif name.startswith("tantan.backend.agents") or name.startswith("tantan.backend.agent"):
        log_file = LOG_FILES["agent"]
    elif name.startswith("tantan.backend.state"):
        log_file = LOG_FILES["state"]
    elif name.startswith("tantan.backend.rag"):
        log_file = LOG_FILES["rag"]
    elif "auth" in name.lower() or "login" in name.lower() or "logout" in name.lower():
        log_file = LOG_FILES["security"]
    else:
        log_file = LOG_FILE

    # 文件 Handler（JSON格式，支持轮转）
    # 按日期轮转，保留30天
    file_handler = TimedRotatingFileHandler(
        filename=str(log_file),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8"
    )
    file_handler.setLevel(_get_log_level())
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(file_handler)

    # 错误日志同时写入 error.log
    if _get_log_level() <= logging.ERROR:
        error_handler = TimedRotatingFileHandler(
            filename=str(LOG_FILES["error"]),
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JsonFormatter())
        logger.addHandler(error_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    获取日志记录器

    Args:
        name: 日志记录器名称（通常使用 __name__）

    Returns:
        Logger 实例
    """
    return _setup_module_logger(name)


def log_exception(logger: logging.Logger, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
    """
    记录异常日志，包含完整堆栈信息

    Args:
        logger: 日志记录器
        error: 异常对象
        context: 额外的上下文信息
    """
    trace_id = get_trace_id()

    extra_info = {
        "trace_id": trace_id or "-",
        "exception_type": type(error).__name__,
        "exception_message": str(error),
        "traceback": traceback.format_exc()
    }

    if context:
        extra_info["context"] = context

    logger.error(
        f"Exception occurred: {type(error).__name__}: {str(error)}",
        exc_info=True
    )


def with_trace_id(func):
    """装饰器：为函数调用自动注入 trace_id（Phase 5.4 用 token-based reset）"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        trace_id = kwargs.pop('trace_id', None)
        token = TraceContext.set_trace_id(trace_id) if trace_id else None
        try:
            return func(*args, **kwargs)
        finally:
            if token is not None:
                TraceContext.reset(token)
    return wrapper


def configure_default_logging():
    """配置默认日志系统（启动时调用一次）"""
    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(_get_log_level())

    # 清除已有的 handlers
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    # 控制台（生产环境可关闭）
    if os.getenv("LOG_CONSOLE", "true").lower() != "false":
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(_get_log_level())
        console.setFormatter(ConsoleFormatter())
        root_logger.addHandler(console)

    # 全局错误日志文件
    error_handler = TimedRotatingFileHandler(
        filename=str(LOG_FILES["error"]),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(error_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)


# 便捷函数
def get_logger_for_module(module_name: str) -> logging.Logger:
    """为模块获取日志记录器，模块名使用点分隔路径"""
    return get_logger(module_name)


# 日志查询工具函数
def search_logs(
    keyword: str,
    log_file: str = "api.log",
    level: Optional[str] = None,
    trace_id: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    查询日志（用于调试）

    Args:
        keyword: 搜索关键词
        log_file: 日志文件名
        level: 过滤日志级别
        trace_id: 过滤trace_id
        limit: 返回条数限制

    Returns:
        匹配的日志条目列表
    """
    import json

    results = []
    log_path = LOG_DIR / log_file

    if not log_path.exists():
        return results

    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # 关键词过滤
            if keyword and keyword.lower() not in entry.get("message", "").lower():
                continue

            # 级别过滤
            if level and entry.get("level") != level.upper():
                continue

            # trace_id过滤
            if trace_id and entry.get("trace_id") != trace_id:
                continue

            results.append(entry)

            if len(results) >= limit:
                break

    return results