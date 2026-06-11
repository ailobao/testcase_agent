# src/utils/trace.py
"""请求追踪 ID 管理"""
import uuid
import logging
from contextvars import ContextVar
from typing import Optional
from datetime import datetime

# 上下文变量，存储当前请求的 trace_id
_trace_id: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)


def generate_trace_id() -> str:
    """生成唯一的追踪 ID"""
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def set_trace_id(trace_id: Optional[str] = None) -> str:
    """设置当前请求的追踪 ID"""
    if trace_id is None:
        trace_id = generate_trace_id()
    _trace_id.set(trace_id)
    return trace_id


def get_trace_id() -> Optional[str]:
    """获取当前请求的追踪 ID"""
    return _trace_id.get()


def clear_trace_id():
    """清除当前请求的追踪 ID"""
    _trace_id.set(None)


class TraceAdapter(logging.LoggerAdapter):
    """自动添加 trace_id 到日志的适配器"""

    def __init__(self, logger: logging.Logger, extra: dict = None):
        super().__init__(logger, extra or {})

    def process(self, msg, kwargs):
        """在日志消息前添加 trace_id"""
        trace_id = get_trace_id()
        if trace_id:
            return f"[{trace_id}] {msg}", kwargs
        return msg, kwargs