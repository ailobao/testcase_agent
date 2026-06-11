import sys
import os
from dotenv import load_dotenv

# 加载 .env
load_dotenv()


def _env(key: str, default: str = "") -> str:
    """获取环境变量：os.environ -> st.secrets -> default（st.secrets 在 Streamlit Cloud 上才可用）"""
    val = os.getenv(key)
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default


# ======================
# LLM 配置（懒加载，通过 __getattr__）
# ======================
# 以下常量通过模块 __getattr__ 延迟解析，确保 Streamlit 运行时已初始化
# （在 Streamlit Cloud 上，st.secrets 在模块 import 时尚未就绪）
_LLM_DEFAULTS = {
    "LLM_MODEL": "qwen-max",
    "LLM_API_KEY": "",  # 使用 _resolve_api_key 处理
    "LLM_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "LLM_TEMPERATURE": "0.1",
    "LLM_MAX_TOKENS": "16000",
}


def _resolve_api_key() -> str:
    """解析 LLM API Key：LLM_API_KEY -> DASHSCOPE_API_KEY -> ''"""
    return _env("LLM_API_KEY") or _env("DASHSCOPE_API_KEY")


def __getattr__(name):
    if name == "LLM_API_KEY":
        return _resolve_api_key()
    if name in _LLM_DEFAULTS:
        if name in ("LLM_TEMPERATURE", "LLM_MAX_TOKENS"):
            return type(_LLM_DEFAULTS[name])(os.getenv(name, _LLM_DEFAULTS[name]))
        return _env(name, _LLM_DEFAULTS[name])
    if name in ("LLM_RETRY_COUNT", "LLM_RETRY_DELAY", "LLM_TIMEOUT",
                "MAX_CONCURRENT_TASKS", "MAX_WORKERS",
                "DEFAULT_CASE_LIMIT", "MAX_CASE_LIMIT"):
        return type(_NON_LLM_DEFAULTS[name])(os.getenv(name, _NON_LLM_DEFAULTS[name]))
    if name == "DEBUG_MODE":
        return os.getenv("TEST_AGENT_DEBUG", "false").lower() == "true"
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ======================
# LLM 重试配置
# ======================
_NON_LLM_DEFAULTS = {
    "LLM_RETRY_COUNT": "3",
    "LLM_RETRY_DELAY": "1.0",
    "LLM_TIMEOUT": "30",
    "MAX_CONCURRENT_TASKS": "3",
    "MAX_WORKERS": "3",
    "DEFAULT_CASE_LIMIT": "10",
    "MAX_CASE_LIMIT": "50",
}

# ======================
# 路径配置
# ======================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
DATA_DRIVER_DIR = os.path.join(BASE_DIR, "data_driver")
PYTEST_DIR = os.path.join(BASE_DIR, "pytest_scripts")
LOG_DIR = os.path.join(BASE_DIR, "logs")
KNOWLEDGE_BASE_DIR = os.path.join(BASE_DIR, "knowledge_base")  # 新增

# 确保目录存在
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DATA_DRIVER_DIR, exist_ok=True)
os.makedirs(PYTEST_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)