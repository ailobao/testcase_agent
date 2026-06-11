import sys
import os
from dotenv import load_dotenv

# 加载 .env
load_dotenv()

# 如果在 Streamlit Cloud 运行，也读取 st.secrets（它不会自动注入 os.environ）
try:
    import streamlit as st
    _secrets = dict(st.secrets)
except Exception:
    _secrets = {}

def _env(key: str, default: str = "") -> str:
    """优先 os.environ（.env/系统变量），其次 st.secrets（Streamlit Cloud），最后 default"""
    return os.getenv(key) or _secrets.get(key) or default

# ======================
# LLM 配置
# ======================
LLM_MODEL = _env("LLM_MODEL", "qwen-max")
LLM_API_KEY = _env("LLM_API_KEY") or _env("DASHSCOPE_API_KEY")
LLM_BASE_URL = _env("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "16000"))

# ======================
# LLM 重试配置（新增）
# ======================
LLM_RETRY_COUNT = int(os.getenv("LLM_RETRY_COUNT", "3"))
LLM_RETRY_DELAY = float(os.getenv("LLM_RETRY_DELAY", "1.0"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))

# ======================
# 并发配置（新增）
# ======================
MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "3"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "3"))

# ======================
# 用例数量配置（新增）
# ======================
DEFAULT_CASE_LIMIT = int(os.getenv("DEFAULT_CASE_LIMIT", "10"))
MAX_CASE_LIMIT = int(os.getenv("MAX_CASE_LIMIT", "50"))

# ======================
# 调试模式
# ======================
DEBUG_MODE = os.getenv("TEST_AGENT_DEBUG", "false").lower() == "true"

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