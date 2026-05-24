# logger_config.py - 统一日志配置
import os
import logging
from datetime import datetime
from typing import List, Dict

# 日志目录
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# 生成日志文件名（按时间）
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
MAIN_LOG_FILE = os.path.join(LOG_DIR, f"testcase_gen_{timestamp}.log")
AI_LOG_FILE = os.path.join(LOG_DIR, f"ai_thinking_{timestamp}.log")
CODE_LOG_FILE = os.path.join(LOG_DIR, f"code_gen_{timestamp}.log")


def setup_loggers():
    """配置所有日志器"""

    # 主日志器（记录整体流程）
    main_logger = logging.getLogger("main")
    main_logger.setLevel(logging.DEBUG)

    # 文件处理器
    main_file_handler = logging.FileHandler(MAIN_LOG_FILE, encoding='utf-8')
    main_file_handler.setLevel(logging.DEBUG)
    main_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))

    main_logger.addHandler(main_file_handler)
    main_logger.addHandler(console_handler)

    # AI 思考日志器（记录 AI 原始输入输出）
    ai_logger = logging.getLogger("ai")
    ai_logger.setLevel(logging.DEBUG)
    ai_file_handler = logging.FileHandler(AI_LOG_FILE, encoding='utf-8')
    ai_file_handler.setLevel(logging.DEBUG)
    ai_file_handler.setFormatter(logging.Formatter('%(asctime)s\n%(message)s\n' + '=' * 80 + '\n'))
    ai_logger.addHandler(ai_file_handler)
    ai_logger.propagate = False

    # 代码生成日志器（记录代码生成的统计）
    code_logger = logging.getLogger("code")
    code_logger.setLevel(logging.INFO)
    code_file_handler = logging.FileHandler(CODE_LOG_FILE, encoding='utf-8')
    code_file_handler.setLevel(logging.INFO)
    code_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    code_logger.addHandler(code_file_handler)
    code_logger.propagate = False

    return main_logger, ai_logger, code_logger


# 初始化日志器
main_logger, ai_logger, code_logger = setup_loggers()


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
    main_logger.info(f"  - 主日志: {MAIN_LOG_FILE}")
    main_logger.info(f"  - AI 日志: {AI_LOG_FILE}")
    main_logger.info(f"  - 代码日志: {CODE_LOG_FILE}")


def log_step(step_name: str, message: str = ""):
    """记录步骤信息"""
    main_logger.info(f"【步骤】{step_name} - {message}")


def log_error(error_type: str, error_msg: str):
    """记录错误"""
    main_logger.error(f"【错误】{error_type}: {error_msg}")