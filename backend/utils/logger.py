"""
统一日志模块 - 碳管师收资系统
提供结构化日志、请求追踪、异常堆栈记录
"""

import os
import sys
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from functools import wraps

# 确保 logs 目录存在
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 日志文件路径
LOG_FILE = LOG_DIR / "app.log"


class TraceContext:
    """请求追踪上下文，使用 thread-local 存储 trace_id"""

    import threading
    _local = threading.local()

    @classmethod
    def get_trace_id(cls) -> Optional[str]:
        return getattr(cls._local, 'trace_id', None)

    @classmethod
    def set_trace_id(cls, trace_id: str) -> None:
        cls._local.trace_id = trace_id

    @classmethod
    def clear(cls) -> None:
        cls._local.trace_id = None


def get_trace_id() -> Optional[str]:
    """获取当前请求的 trace_id"""
    return TraceContext.get_trace_id()


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        trace_id = get_trace_id()
        if trace_id:
            record.trace_id = trace_id
        else:
            record.trace_id = "-"

        # 添加时间戳
        record.timestamp = datetime.now().isoformat()

        # 格式化异常堆栈
        if record.exc_info:
            record.stack_trace = self.formatException(record.exc_info)
        else:
            record.stack_trace = ""

        return super().format(record)


class JsonFormatter(StructuredFormatter):
    """JSON格式日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_data = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "trace_id": get_trace_id() or "-",
            "message": record.getMessage(),
        }

        if record.stack_trace:
            log_data["stack_trace"] = record.stack_trace

        # 添加 extra 字段
        if hasattr(record, 'extra_data'):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data, ensure_ascii=False)


def setup_logger(
    name: str,
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    use_json: bool = False
) -> logging.Logger:
    """
    设置日志记录器

    Args:
        name: 日志记录器名称
        level: 日志级别
        log_file: 日志文件路径（默认使用 logs/app.log）
        use_json: 是否使用 JSON 格式

    Returns:
        配置好的 logger 实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 控制台 Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if use_json:
        formatter = JsonFormatter()
    else:
        formatter = StructuredFormatter(
            '%(timestamp)s | %(trace_id)s | %(levelname)-8s | %(name)s | %(message)s'
        )

        if hasattr(logging.LogRecord, 'stack_trace'):
            formatter._fmt += ' | %(stack_trace)s'

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件 Handler
    file_path = log_file or str(LOG_FILE)
    file_handler = logging.FileHandler(file_path, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    获取日志记录器

    Args:
        name: 日志记录器名称（通常使用 __name__）
        level: 日志级别（默认使用环境变量 LOG_LEVEL 或 INFO）

    Returns:
        Logger 实例
    """
    if level is None:
        level_str = os.getenv("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_str, logging.INFO)

    return setup_logger(name, level)


class Logger:
    """
    日志工具类，提供便捷的日志记录方法
    """

    @staticmethod
    def error(logger: logging.Logger, message: str, exc_info: Optional[Exception] = None, **kwargs) -> None:
        """记录错误日志"""
        if exc_info:
            extra_data = {"exc_info": str(exc_info), "traceback": traceback.format_exc()}
            extra_data.update(kwargs)
            # 使用 extra 传递额外数据
            if hasattr(logger, '_log'):
                for key, value in extra_data.items():
                    setattr(logging.LogRecord, f'extra_{key}', value)
        logger.error(message, exc_info=exc_info is not None)

    @staticmethod
    def info(logger: logging.Logger, message: str, **kwargs) -> None:
        """记录信息日志"""
        logger.info(message)

    @staticmethod
    def warning(logger: logging.Logger, message: str, **kwargs) -> None:
        """记录警告日志"""
        logger.warning(message)

    @staticmethod
    def debug(logger: logging.Logger, message: str, **kwargs) -> None:
        """记录调试日志"""
        logger.debug(message)


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
    """装饰器：为函数调用自动注入 trace_id"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        trace_id = kwargs.pop('trace_id', None)
        if trace_id:
            TraceContext.set_trace_id(trace_id)
        try:
            return func(*args, **kwargs)
        finally:
            if trace_id:
                TraceContext.clear()
    return wrapper


# 默认日志配置
def configure_default_logging():
    """配置默认日志系统"""
    # 根日志级别
    root_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, root_level, logging.INFO),
        format='%(asctime)s | %(trace_id)s | %(levelname)-8s | %(name)s | %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(str(LOG_FILE), encoding='utf-8')
        ]
    )


# 导出便捷函数
def get_logger_for_module(module_name: str) -> logging.Logger:
    """为模块获取日志记录器，模块名使用点分隔路径"""
    return get_logger(module_name)