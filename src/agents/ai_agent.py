# src/agents/ai_agent.py
"""AI系统测试用例生成 Agent"""
import sys
import os
import re
import json
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# 将项目根目录添加到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.agents.base_agent import BaseAgent
from src.tools.rule_manager import get_rule
from src.config.settings import DEBUG_MODE, MAX_CONCURRENT_TASKS
from src.core.prompt_loader import prompt_loader
from src.core.logger import main_logger, debug_log
from src.utils.common_tools import deduplicate_cases
from src.utils.excel_exporter import ExcelExporter


class AITestAgent(BaseAgent):
    """AI系统测试用例生成 Agent"""

    def __init__(self):
        super().__init__()

    def generate(self, project_name: str, module_name: str,
                 description: str, limits: Dict[str, int],
                 need_analysis: bool = True,
                 business_rules: str = "",
                 progress_callback=None) -> Dict:
        """
        生成AI测试用例

        参数:
        - project_name: 项目名称
        - module_name: 模块名称
        - description: 系统描述
        - limits: 各维度用例上限 {"功能": 10, "准确性": 8, ...}
        - need_analysis: 是否需要生成分析报告
        - business_rules: 业务规则
        - progress_callback: 进度回调函数

        返回:
        - {"analysis": "分析报告内容", "cases": [...]}
        """
        # 开始追踪
        trace_id = self.start_trace()
        main_logger.info(f"开始生成AI测试用例: {project_name}/{module_name} (trace_id: {trace_id})")
        main_logger.info(f"需要分析报告: {need_analysis}")
        main_logger.info(f"用例上限: {limits}")

        # 1. 输入校验
        valid, msg = self.validate_input(
            project=project_name,
            module=module_name,
            business_rules=business_rules
        )
        if not valid:
            debug_log(f"输入校验失败: {msg}")
            if progress_callback:
                progress_callback(1.0, f"输入校验失败: {msg}")
            return {"analysis": "", "cases": []}

        # 2. 获取数据库规则并合并
        db_rule = get_rule(project_name, module_name)
        merged_rules = self._merge_rules(db_rule, business_rules)

        result = {"analysis": "", "cases": []}

        # 3. 生成分析报告（串行）
        if need_analysis:
            if progress_callback:
                progress_callback(0.1, "正在生成四大维度分析报告...")
            try:
                result["analysis"] = self._generate_analysis(project_name, module_name, description)
                debug_log("分析报告生成成功")
            except Exception as e:
                debug_log(f"分析报告生成失败: {e}")
                result["analysis"] = f"## 分析报告生成失败\n\n错误信息：{str(e)}"

        # 4. 准备并行生成各维度用例
        dimensions = ["功能", "准确性", "鲁棒性", "用户体验", "安全"]
        active_dimensions = [(dim, limits.get(dim, 0)) for dim in dimensions if limits.get(dim, 0) > 0]

        if not active_dimensions:
            if progress_callback:
                progress_callback(1.0, "没有需要生成的用例维度")
            return result

        if progress_callback:
            progress_callback(0.2, f"开始并行生成 {len(active_dimensions)} 个维度的测试用例...")

        # 5. 并行执行
        all_cases = []

        if progress_callback:
            progress_callback(0.2, f"开始并行生成 {len(active_dimensions)} 个维度的测试用例...")

        def _generate_dimension_wrapper(dim, max_num):
            """线程池包装函数"""
            try:
                cases = self._generate_dimension_cases(
                    project_name, module_name, description, dim, max_num, merged_rules
                )
                if len(cases) > max_num:
                    cases = cases[:max_num]
                return dim, cases, None
            except Exception as e:
                debug_log(f"{dim}维度生成异常: {e}")
                return dim, [], str(e)

        dimension_results = []
        with ThreadPoolExecutor(max_workers=min(len(active_dimensions), MAX_CONCURRENT_TASKS)) as executor:
            future_to_dim = {
                executor.submit(_generate_dimension_wrapper, dim, max_num): dim
                for dim, max_num in active_dimensions
            }
            for future in as_completed(future_to_dim):
                dim_result = future.result()
                dimension_results.append(dim_result)
        completed = 0
        for dim, cases, error in dimension_results:
            completed += 1
            if error:
                debug_log(f"{dim}维度生成失败: {error}")
                if progress_callback:
                    progress_callback(0.2 + (completed / len(active_dimensions)) * 0.8,
                                      f"{dim}维度生成失败，跳过")
            else:
                all_cases.extend(cases)
                debug_log(f"{dim}维度完成 ({len(cases)}条)")
                if progress_callback:
                    progress_callback(0.2 + (completed / len(active_dimensions)) * 0.8,
                                      f"✅ {dim}维度完成 ({len(cases)}条)")

        # 6. 补充缺失的测试ID
        for i, case in enumerate(all_cases, 1):
            if not case.get("测试ID"):
                case["测试ID"] = f"AI_TC_{i:03d}"

        # 7. 去重处理
        original_count = len(all_cases)
        seen = set()
        unique_cases = []
        for case in all_cases:
            key = f"{case.get('测试标题', '')}_{case.get('测试步骤', '')}"
            if key not in seen:
                seen.add(key)
                unique_cases.append(case)
        all_cases = unique_cases
        debug_log(f"去重: 原始 {original_count} 条 → 去重后 {len(all_cases)} 条")

        result["cases"] = all_cases

        if progress_callback:
            progress_callback(1.0, f"✅ 全部完成！生成 {len(all_cases)} 条用例")

        self.end_trace()
        return result

    def _generate_analysis(self, project: str, module: str, description: str) -> str:
        """生成四大维度分析报告"""
        prompt = prompt_loader.get_task_prompt(
            "ai_analysis",
            project=project,
            module=module,
            description=description
        )
        debug_log(f"分析报告提示词长度: {len(prompt)}")
        response = self.safe_llm_call(prompt, default_return="## 分析报告生成失败\n\n请稍后重试")
        return response

    def _generate_dimension_cases(self, project: str, module: str, description: str,
                                  dimension: str, max_num: int, merged_rules: str = "") -> List[Dict]:
        """生成单个维度的测试用例"""
        prompt = prompt_loader.get_task_prompt(
            "ai_test_case",
            project=project,
            module=module,
            description=description,
            dimension=dimension,
            merged_rules=merged_rules,
            max_num=max_num
        )

        defense_rules = prompt_loader.get_defense_rules()
        case_strategy = prompt_loader.get_case_strategy()
        prompt = f"{prompt}\n\n{defense_rules}\n\n{case_strategy}"

        # 各维度场景类型检查清单（确保输出多样性，避免同一维度只做单一类型）
        dimension_quality_rules = {
            "功能": "\n\n【功能维度场景检查】必须覆盖以下至少2种场景类型：\n- 正向场景（正常输入、正确输出）\n- 异常输入（空值、边界值、格式错误）\n- 业务规则验证（是否符合描述中的业务逻辑）",
            "准确性": "\n\n【准确性维度场景检查】必须覆盖以下至少2种场景类型：\n- 确定性问答（有标准答案的问题，验证正确性）\n- 一致性验证（相同输入多次提问，结果是否一致）\n- 幻觉检测（超出知识范围的问题，是否编造信息）",
            "鲁棒性": "\n\n【鲁棒性维度场景检查】必须覆盖以下至少3种场景：\n- 异常输入（空输入、超长输入、特殊字符）\n- 并发请求（快速重复提交、多次同时请求）\n- 稳定性（断网恢复、超时处理、服务降级）",
            "用户体验": "\n\n【用户体验维度场景检查】必须覆盖以下至少3种场景：\n- 响应反馈（加载状态、等待提示、进度展示）\n- 错误提示（错误信息是否友好、易懂、有建设性）\n- 交互易用性（操作流程直观性、新用户上手难度）",
            "安全": "\n\n【安全维度场景检查】必须覆盖以下至少3种场景：\n- 提示词注入（Prompt Injection、越狱攻击）\n- 数据安全（用户隐私保护、敏感信息脱敏）\n- 内容安全（违规内容生成、有害信息过滤）",
        }
        dim_rule = dimension_quality_rules.get(dimension, "")
        if dim_rule:
            prompt += dim_rule

        debug_log(f"{dimension}维度提示词长度: {len(prompt)}")

        # 定义降级函数
        def fallback_cases():
            """生成降级用例，确保维度不为空"""
            main_logger.warning(f"{dimension}维度 AI 响应解析失败，使用降级用例")
            return [self._create_fallback_case(dimension, max_num)]

        # 使用基类的安全 JSON 调用
        cases = self.safe_llm_json_call(prompt, fallback_cases)

        # 确保返回的是列表
        if not cases:
            return []

        # 后处理：确保必要的字段存在
        for case in cases:
            if not case.get("测试类型"):
                case["测试类型"] = dimension

            # 安全用例强制 P0
            if dimension == "安全":
                case["优先级"] = "P0"

            # 正向用例 P0
            if "正向" in case.get("测试标题", "") or "正常" in case.get("测试标题", ""):
                if not case.get("优先级") or case.get("优先级") == "P2":
                    case["优先级"] = "P0"

            # 补充默认字段
            if not case.get("关联需求"):
                case["关联需求"] = "无"
            if not case.get("前置条件"):
                case["前置条件"] = "无"
            if not case.get("实际结果"):
                case["实际结果"] = ""
            if not case.get("执行人"):
                case["执行人"] = ""

        return cases

    async def async_generate_dimension_cases(self, project: str, module: str, description: str,
                                             dimension: str, max_num: int, merged_rules: str = "") -> List[Dict]:
        """异步生成单个维度的测试用例（与 _generate_dimension_cases 功能一致，但使用异步 LLM 调用）"""
        prompt = prompt_loader.get_task_prompt(
            "ai_test_case",
            project=project,
            module=module,
            description=description,
            dimension=dimension,
            merged_rules=merged_rules,
            max_num=max_num
        )

        defense_rules = prompt_loader.get_defense_rules()
        case_strategy = prompt_loader.get_case_strategy()
        prompt = f"{prompt}\n\n{defense_rules}\n\n{case_strategy}"

        # 各维度场景类型检查清单（确保输出多样性，避免同一维度只做单一类型）
        dimension_quality_rules = {
            "功能": "\n\n【功能维度场景检查】必须覆盖以下至少2种场景类型：\n- 正向场景（正常输入、正确输出）\n- 异常输入（空值、边界值、格式错误）\n- 业务规则验证（是否符合描述中的业务逻辑）",
            "准确性": "\n\n【准确性维度场景检查】必须覆盖以下至少2种场景类型：\n- 确定性问答（有标准答案的问题，验证正确性）\n- 一致性验证（相同输入多次提问，结果是否一致）\n- 幻觉检测（超出知识范围的问题，是否编造信息）",
            "鲁棒性": "\n\n【鲁棒性维度场景检查】必须覆盖以下至少3种场景：\n- 异常输入（空输入、超长输入、特殊字符）\n- 并发请求（快速重复提交、多次同时请求）\n- 稳定性（断网恢复、超时处理、服务降级）",
            "用户体验": "\n\n【用户体验维度场景检查】必须覆盖以下至少3种场景：\n- 响应反馈（加载状态、等待提示、进度展示）\n- 错误提示（错误信息是否友好、易懂、有建设性）\n- 交互易用性（操作流程直观性、新用户上手难度）",
            "安全": "\n\n【安全维度场景检查】必须覆盖以下至少3种场景：\n- 提示词注入（Prompt Injection、越狱攻击）\n- 数据安全（用户隐私保护、敏感信息脱敏）\n- 内容安全（违规内容生成、有害信息过滤）",
        }
        dim_rule = dimension_quality_rules.get(dimension, "")
        if dim_rule:
            prompt += dim_rule

        debug_log(f"{dimension}维度提示词长度: {len(prompt)}")

        # 定义降级函数
        def fallback_cases():
            main_logger.warning(f"{dimension}维度 AI 响应解析失败，使用降级用例")
            return [self._create_fallback_case(dimension, max_num)]

        # 使用基类的异步安全 JSON 调用
        cases = await self.async_safe_llm_json_call(prompt, fallback_cases)

        if not cases:
            return []

        # 后处理（与同步版本一致）
        for case in cases:
            if not case.get("测试类型"):
                case["测试类型"] = dimension
            if dimension == "安全":
                case["优先级"] = "P0"
            if "正向" in case.get("测试标题", "") or "正常" in case.get("测试标题", ""):
                if not case.get("优先级") or case.get("优先级") == "P2":
                    case["优先级"] = "P0"
            if not case.get("关联需求"):
                case["关联需求"] = "无"
            if not case.get("前置条件"):
                case["前置条件"] = "无"
            if not case.get("实际结果"):
                case["实际结果"] = ""
            if not case.get("执行人"):
                case["执行人"] = ""

        return cases

    def _create_fallback_case(self, dimension: str, max_num: int) -> Dict:
        """创建降级用例（当 AI 解析失败时使用）"""
        return {
            "测试ID": f"AI_FALLBACK_{dimension[:2]}",
            "测试标题": f"{dimension}维度-基础验证用例",
            "测试类型": dimension,
            "优先级": "P2",
            "关联需求": "无",
            "前置条件": "系统正常运行",
            "测试数据": "标准测试数据",
            "测试步骤": "1. 执行核心业务操作\n2. 验证系统响应",
            "预期结果": "系统正确处理请求，返回预期结果",
            "实际结果": "",
            "执行人": ""
        }

    def _merge_rules(self, db_rule: Optional[Dict], user_rules: str) -> str:
        """合并数据库规则和用户规则"""
        if not db_rule:
            return user_rules if user_rules else ""

        rule_text = ""
        if db_rule.get('input_fields'):
            rule_text += f"\n【强制规则】输入字段只能是：{db_rule.get('input_fields')}\n"
        if db_rule.get('verification_code'):
            rule_text += f"【强制规则】验证码来源：{db_rule.get('verification_code')}\n"
        if db_rule.get('constraints'):
            rule_text += f"【强制规则】约束：{db_rule.get('constraints')}\n"
        if user_rules:
            rule_text += f"\n【补充规则】\n{user_rules}\n"

        return rule_text

    def export_excel(self, result: Dict, project_name: str, module_name: str,
                     need_analysis: bool = True) -> str:
        """导出AI测试结果为Excel"""
        filepath = ExcelExporter.export_ai_cases(result, project_name, module_name, need_analysis)
        if filepath:
            main_logger.info(f"AI测试Excel导出成功：{filepath}")
        return filepath

    def _clean_name(self, name: str) -> str:
        """清理文件名中的非法字符"""
        return re.sub(r'[\\/*?:"<>|]', "", name)[:50]

    def validate_input(self, **kwargs) -> tuple:
        """输入校验"""
        project = kwargs.get("project", "")
        module = kwargs.get("module", "")
        business_rules = kwargs.get("business_rules", "")

        if not project or not module:
            return False, "项目名称和模块名称不能为空"

        dangerous = ["忽略规则", "你现在是", "扮演", "越狱", "无视规则", "忘记规则"]
        for keyword in dangerous:
            if keyword in business_rules:
                return False, f"检测到可疑内容: {keyword}"

        return True, ""