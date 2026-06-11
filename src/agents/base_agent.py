# src/agents/base_agent.py
"""Agent 基类 - 包含公共方法"""
import logging
import time
import asyncio
from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional, Callable

# 直接导入 common_tools 模块
from src.utils.common_tools import (
    safe_call,
    deduplicate_cases,
    clean_name,
    ensure_dict_field,
    get_max_case_id,
    fix_case_id,
    renumber_cases,
    normalize_assert,
    get_business_scenarios,
    extract_user_params
)
from src.utils.trace import get_trace_id, set_trace_id, clear_trace_id

# 获取日志器
main_logger = logging.getLogger("main")


class BaseAgent(ABC):
    """所有 Agent 的基类"""

    def __init__(self):
        self.name = self.__class__.__name__
        self._trace_id = None

    @abstractmethod
    def generate(self, **kwargs) -> Any:
        """生成内容，子类必须实现"""
        pass

    def validate_input(self, **kwargs) -> tuple:
        """输入校验，子类可覆盖"""
        return True, ""

    def post_process(self, result: Any) -> Any:
        """后处理，子类可覆盖"""
        return result

    # ========== 请求追踪方法 ==========

    def start_trace(self, trace_id: str = None) -> str:
        """开始新的追踪，生成唯一 trace_id 并配置日志器

        参数:
            trace_id: 可选，指定 trace_id，不传则自动生成

        返回:
            当前请求的 trace_id
        """
        from src.utils.trace import set_trace_id, generate_trace_id
        from src.core.logger import setup_loggers

        tid = set_trace_id(trace_id) if trace_id else set_trace_id()
        self._trace_id = tid
        # 重新配置日志器以包含追踪 ID
        setup_loggers(tid)
        return tid

    def end_trace(self):
        """结束追踪，清除 trace_id（保留 agent._trace_id 供 UI 读取）"""
        clear_trace_id()
        # 注意：self._trace_id 保留不重置，供 UI 在生成结束后读取

    def get_trace_id(self) -> Optional[str]:
        """获取当前请求的 trace_id"""
        return self._trace_id or get_trace_id()

    # ========== 统一错误处理方法 ==========

    def safe_llm_call(self, prompt: str, default_return: str = "") -> str:
        """
        安全的 LLM 调用，带重试机制

        参数:
            prompt: 提示词
            default_return: 失败时的默认返回值

        返回:
            LLM 响应内容或默认值
        """
        from src.core.llm_client import call_llm_with_prompt

        def _call():
            return call_llm_with_prompt(prompt)

        result = safe_call(
            func=_call,
            error_msg=f"LLM 调用失败 [{self.name}]",
            default_return=default_return,
            retry_count=3,  # 可从配置读取
            retry_delay=1.0
        )
        return result if result is not None else default_return

    def safe_llm_json_call(self, prompt: str,
                          fallback_cases_func: Optional[Callable[[], List[Dict]]] = None) -> List[Dict]:
        """
        调用 LLM 并自动解析 JSON，失败时调用降级函数生成用例。

        参数:
            prompt: 提示词
            fallback_cases_func: 降级函数，签名为 () -> List[Dict]，返回默认用例列表

        返回:
            解析后的用例列表（保证是 List[Dict]）
        """
        from src.utils.json_parser import universal_json_parse

        response = self.safe_llm_call(prompt, default_return="")
        if not response:
            self.log_warning("LLM响应为空", "将使用降级用例")
            return fallback_cases_func() if fallback_cases_func else []

        cases = universal_json_parse(response, default_return=[])
        if cases:
            return cases

        # 解析失败，使用降级策略
        self.log_warning("JSON解析失败", f"响应前200字符: {response[:200]}")
        if fallback_cases_func:
            return fallback_cases_func()
        return []

    # ========== 异步 LLM 调用方法 ==========

    async def async_safe_llm_call(self, prompt: str, default_return: str = "") -> str:
        """
        异步安全的 LLM 调用，带重试机制

        参数:
            prompt: 提示词
            default_return: 失败时的默认返回值

        返回:
            LLM 响应内容或默认值
        """
        from src.core.llm_client import async_call_llm_with_prompt

        for attempt in range(3):
            try:
                return await async_call_llm_with_prompt(prompt)
            except Exception as e:
                if attempt == 2:
                    main_logger.error(f"异步 LLM 调用失败 [{self.name}]: {e}")
                    return default_return
                main_logger.warning(f"异步 LLM 重试 {attempt + 1}/3 [{self.name}]: {e}")
                await asyncio.sleep(1.0)
        return default_return

    async def async_safe_llm_json_call(
        self, prompt: str,
        fallback_cases_func: Optional[Callable[[], List[Dict]]] = None
    ) -> List[Dict]:
        """
        异步调用 LLM 并自动解析 JSON，失败时调用降级函数。

        参数:
            prompt: 提示词
            fallback_cases_func: 降级函数，签名为 () -> List[Dict]

        返回:
            解析后的用例列表
        """
        from src.utils.json_parser import universal_json_parse

        response = await self.async_safe_llm_call(prompt, default_return="")
        if not response:
            self.log_warning("异步LLM响应为空", "将使用降级用例")
            return fallback_cases_func() if fallback_cases_func else []

        cases = universal_json_parse(response, default_return=[])
        if cases:
            return cases

        self.log_warning("异步JSON解析失败", f"响应前200字符: {response[:200]}")
        if fallback_cases_func:
            return fallback_cases_func()
        return []

    def safe_export_excel(self, export_func: Callable, *args, **kwargs) -> Optional[str]:
        """
        安全的 Excel 导出，带错误处理
        """
        try:
            result = export_func(*args, **kwargs)
            return result
        except Exception as e:
            main_logger.error(f"Excel 导出失败 [{self.name}]: {e}")
            return None

    def log_error(self, step: str, error: Exception, context: str = ""):
        """统一错误日志记录"""
        error_msg = f"【错误】步骤: {step}"
        if context:
            error_msg += f", 上下文: {context}"
        error_msg += f", 错误: {type(error).__name__}: {error}"
        main_logger.error(error_msg)

    def log_warning(self, step: str, message: str):
        """统一警告日志记录"""
        main_logger.warning(f"【警告】步骤: {step}, 信息: {message}")

    def log_info(self, step: str, message: str):
        """统一信息日志记录"""
        main_logger.info(f"【信息】步骤: {step}, 信息: {message}")

    # ========== 公共工具方法 ==========

    def deduplicate_cases(self, cases: List[Dict], key_fields: List[str] = None) -> List[Dict]:
        """去重用例"""
        return deduplicate_cases(cases, key_fields)

    def clean_name(self, name: str) -> str:
        """清理文件名"""
        return clean_name(name)

    def ensure_dict_field(self, value: Any, default: dict = None) -> dict:
        """确保字段是字典"""
        return ensure_dict_field(value, default)

    def get_max_case_id(self, cases: List[Dict], prefix: str = "TC_") -> int:
        """获取最大用例编号"""
        return get_max_case_id(cases, prefix)

    def fix_case_id(self, cases: List[Dict], start_id: int = 1, prefix: str = "TC_") -> List[Dict]:
        """修复用例编号"""
        return fix_case_id(cases, start_id, prefix)

    def renumber_cases(self, cases: List[Dict], prefix: str = "TC_", start: int = 1) -> List[Dict]:
        """重新编号用例"""
        return renumber_cases(cases, prefix, start)

    def normalize_assert(self, assert_dict: dict, method: str) -> dict:
        """规范化断言"""
        return normalize_assert(assert_dict, method)

    def get_business_scenarios(self, module_name: str, is_login_module: bool) -> str:
        """获取业务场景"""
        return get_business_scenarios(module_name, is_login_module)

    def extract_user_params(self, ai_cases: List[Dict], business_rules: str, default_body: dict):
        """提取用户参数"""
        return extract_user_params(ai_cases, business_rules, default_body)

    # ========== 公共方法（规则合并等） ==========

    def _merge_rules(self, db_rule: Optional[Dict], user_rules: str) -> str:
        """合并数据库规则和用户规则（公共方法）"""
        if not db_rule:
            return user_rules if user_rules else ""

        parts = []
        if db_rule.get('input_fields'):
            parts.append(f"【强制规则】输入字段只能是：{db_rule.get('input_fields')}")
        if db_rule.get('verification_code'):
            parts.append(f"【强制规则】验证码来源：{db_rule.get('verification_code')}")
        if db_rule.get('constraints'):
            parts.append(f"【强制规则】约束：{db_rule.get('constraints')}")
        if user_rules:
            parts.append(f"【补充规则】\n{user_rules}")

        return "\n".join(parts)

    # ========== case_strategy 后处理 ==========

    def _enforce_case_strategy(self, cases: List[Dict]) -> List[Dict]:
        """
        只确保至少1条正向用例存在，不截断任何类型。
        边界值由模型基于业务规则常识自动推导，不设比例限制。
        """
        if not cases:
            return cases

        has_positive = any("正向" in c.get("title", "") or "成功" in c.get("title", "") for c in cases)
        if not has_positive:
            main_logger.warning("未检测到正向用例，保留全部原始用例")
        return cases