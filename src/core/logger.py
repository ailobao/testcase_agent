# src/core/logger.py
"""统一日志配置 - 支持请求追踪"""
import os
import logging
from datetime import datetime
from typing import List, Dict
from src.config.settings import LOG_DIR
from src.utils.trace import TraceAdapter, get_trace_id

os.makedirs(LOG_DIR, exist_ok=True)

# 全局日志器实例
_main_logger = None
_ai_logger = None
_code_logger = None


def setup_loggers(trace_id: str = None):
    """配置日志器，支持追踪 ID"""
    global _main_logger, _ai_logger, _code_logger

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    trace_suffix = f"_{trace_id}" if trace_id else ""

    MAIN_LOG_FILE = os.path.join(LOG_DIR, f"testcase_gen_{timestamp}{trace_suffix}.log")
    AI_LOG_FILE = os.path.join(LOG_DIR, f"ai_thinking_{timestamp}{trace_suffix}.log")

    # 主日志器
    main_logger = logging.getLogger("main")
    main_logger.setLevel(logging.DEBUG)
    main_logger.handlers.clear()

    main_file_handler = logging.FileHandler(MAIN_LOG_FILE, encoding='utf-8')
    main_file_handler.setLevel(logging.DEBUG)
    main_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))

    main_logger.addHandler(main_file_handler)
    main_logger.addHandler(console_handler)

    # AI 思考日志器
    ai_logger = logging.getLogger("ai")
    ai_logger.setLevel(logging.DEBUG)
    ai_logger.handlers.clear()
    ai_file_handler = logging.FileHandler(AI_LOG_FILE, encoding='utf-8')
    ai_file_handler.setLevel(logging.DEBUG)
    ai_file_handler.setFormatter(logging.Formatter('%(asctime)s\n%(message)s\n' + '=' * 80 + '\n'))
    ai_logger.addHandler(ai_file_handler)
    ai_logger.propagate = False

    # 代码日志器
    code_logger = logging.getLogger("code")
    code_logger.setLevel(logging.DEBUG)
    code_logger.handlers.clear()
    code_logger.addHandler(logging.NullHandler())

    # 包装为 TraceAdapter
    _main_logger = TraceAdapter(main_logger)
    _ai_logger = TraceAdapter(ai_logger)
    _code_logger = code_logger

    return _main_logger, _ai_logger, _code_logger


def get_main_logger():
    """获取主日志器（带追踪 ID）"""
    global _main_logger
    if _main_logger is None:
        setup_loggers()
    return _main_logger


def get_ai_logger():
    """获取 AI 日志器（带追踪 ID）"""
    global _ai_logger
    if _ai_logger is None:
        setup_loggers()
    return _ai_logger


# 为了兼容性，创建默认实例
main_logger = get_main_logger()
ai_logger = get_ai_logger()
code_logger = logging.getLogger("code")
code_logger.addHandler(logging.NullHandler())


# ======================
# 兼容旧接口的函数
# ======================

def log_ai_prompt(prompt: str):
    """记录 AI 收到的提示词"""
    ai_logger.info(f"【AI 提示词】\n{prompt}")


def log_ai_response(response: str):
    """记录 AI 返回的原始内容"""
    ai_logger.info(f"【AI 原始响应】\n{response}")


def log_ai_parsed(cases: List[Dict]):
    """记录 AI 解析后的用例"""
    ai_logger.info(f"【AI 解析结果】共 {len(cases)} 条用例")
    for i, case in enumerate(cases, 1):
        ai_logger.info(f"  {i}. {case.get('title', '无标题')}")


def log_code_generation(case_type: str, count: int, details: List[str] = None):
    """记录代码生成的统计"""
    code_logger.info(f"{case_type}: 生成 {count} 条")
    if details:
        for detail in details:
            code_logger.info(f"  - {detail}")


def log_summary(total: int, code_count: int, ai_count: int):
    """记录最终统计"""
    main_logger.info("=" * 60)
    main_logger.info(f"生成完成！总计 {total} 条用例")
    main_logger.info(f"  - 代码生成: {code_count} 条")
    main_logger.info(f"  - AI 生成: {ai_count} 条")
    main_logger.info("=" * 60)
    main_logger.info(f"日志文件位置:")
    main_logger.info(f"  - 主日志: {LOG_DIR}")
    main_logger.info(f"  - AI 日志: {LOG_DIR}")


def log_step(step_name: str, message: str = ""):
    """记录步骤信息"""
    main_logger.info(f"【步骤】{step_name} - {message}")


def log_error(error_type: str, error_msg: str):
    """记录错误"""
    main_logger.error(f"【错误】{error_type}: {error_msg}")


def debug_log(msg: str, data=None):
    """调试日志"""
    from src.config.settings import DEBUG_MODE
    if DEBUG_MODE:
        main_logger.debug(msg)
        if data:
            main_logger.debug(f"       {data}")