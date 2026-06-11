# src/agents/api_agent.py
"""接口测试用例生成 Agent - 优化版（基于测试点分析模式）"""
import sys
import os
import json
import re
from typing import List, Dict, Optional, Any
from datetime import datetime

# 将项目根目录添加到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.agents.base_agent import BaseAgent
from src.strategies import FixedPatternStrategy
from src.tools.rule_manager import get_rule
from src.config.settings import DATA_DIR, DATA_DRIVER_DIR, PYTEST_DIR
from src.core.logger import main_logger, debug_log, log_ai_prompt, log_ai_parsed, log_step, log_summary
from src.utils.common_tools import deduplicate_cases
from src.utils.excel_exporter import ExcelExporter
from src.core.prompt_loader import prompt_loader

# 默认请求头
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": "Bearer {{token}}"
}


class APITestAgent(BaseAgent):
    """接口测试用例生成 Agent - 优化版（基于测试点分析模式）"""

    def __init__(self):
        super().__init__()
        self.fixed_pattern = FixedPatternStrategy()

    def generate(self, project_name: str, module_name: str,
                 business_rules: str = "") -> List[Dict]:
        """智能混合策略生成接口测试用例"""
        # 开始追踪
        trace_id = self.start_trace()
        log_step("开始生成", f"{project_name}/{module_name} (trace_id: {trace_id})")

        # 1. 输入校验
        valid, msg = self.validate_input(project=project_name, module=module_name, business_rules=business_rules)
        if not valid:
            debug_log(f"输入校验失败: {msg}")
            self.end_trace()
            return []

        # 2. 获取数据库规则
        config = self._get_module_config(project_name, module_name)
        if not config:
            debug_log(f"未找到模块配置: {project_name}/{module_name}")
            config = self._get_default_config(module_name)

        url_path = config["url_path"]
        default_body = config["default_body"]
        required_fields = config["required_fields"]
        db_constraints = config["constraints"]

        # 3. 合并规则（使用基类的公共方法）
        merged_rules = self._merge_rules(
            {"constraints": db_constraints} if db_constraints else None,
            business_rules
        )

        # 4. 判断请求方法和模块类型
        method = self._get_method_from_url(url_path, module_name)
        is_login_module = "login" in url_path.lower() or "登录" in module_name or "注册" in module_name

        main_logger.info(f"URL: {url_path}, 方法: {method}")
        main_logger.info(f"必填参数: {required_fields}")
        main_logger.info(f"免Token模块: {is_login_module}")

        all_cases = []
        code_count = 0

        # ======================
        # 第一步：AI 生成业务深度用例
        # ======================
        log_step("步骤1", "AI 生成业务深度用例...")

        ai_cases = self._generate_ai_business_cases(
            project_name, module_name, url_path, default_body,
            required_fields, merged_rules, method, is_login_module
        )

        if ai_cases is None:
            ai_cases = []
        main_logger.info(f"AI 生成了 {len(ai_cases)} 条业务用例")
        all_cases.extend(ai_cases)

        # ======================
        # 提取用户指定的参数
        # ======================
        user_params = self.extract_user_params(ai_cases, business_rules, default_body)
        if user_params:
            main_logger.info(f"用户参数: {user_params}")

        # ======================
        # 第二步：固定模式用例补充
        # ======================
        log_step("步骤2", "固定模式用例补充...")

        existing_titles = [c.get("title", "") for c in all_cases]
        case_id = self.get_max_case_id(all_cases) + 1

        # 重置计数器
        self.fixed_pattern.reset_count()

        # 2.1 Token 异常用例（仅非登录模块需要）
        token_cases = self.fixed_pattern.generate_token_error_cases(
            url_path, user_params or default_body, method, case_id, is_login_module
        )
        for case in token_cases:
            # 使用子串匹配去重：AI 可能已生成"Token异常-Token过期验证"，
            # FixedPattern 生成"Token过期"——精确匹配会漏掉
            title = case["title"]
            is_dup = False
            for t in existing_titles:
                if title in t or t in title:
                    is_dup = True
                    break
            if not is_dup:
                all_cases.append(case)
                case_id += 1
        code_count += self.fixed_pattern.get_count()
        main_logger.info(f"固定模式补充: Token异常 {len(token_cases)} 条")

        # 2.2 参数缺失用例（只生成未被 AI 覆盖的）
        self.fixed_pattern.reset_count()
        missing_cases = self.fixed_pattern.generate_missing_param_cases(
            required_fields, url_path, user_params or default_body, method, case_id
        )
        added_missing = 0
        for case in missing_cases:
            exists = False
            for t in existing_titles:
                if case["title"] in t:
                    exists = True
                    break
            if not exists:
                all_cases.append(case)
                case_id += 1
                added_missing += 1
        code_count += added_missing
        main_logger.info(f"固定模式补充: 参数缺失 {added_missing} 条")

        # 2.3 参数为空用例（只生成未被 AI 覆盖的）
        self.fixed_pattern.reset_count()
        empty_cases = self.fixed_pattern.generate_empty_param_cases(
            required_fields, url_path, user_params or default_body, method, case_id
        )
        added_empty = 0
        for case in empty_cases:
            exists = False
            for t in existing_titles:
                if case["title"] in t:
                    exists = True
                    break
            if not exists:
                all_cases.append(case)
                case_id += 1
                added_empty += 1
        code_count += added_empty
        main_logger.info(f"固定模式补充: 参数为空 {added_empty} 条")

        main_logger.info(f"固定模式共补充了 {code_count} 条用例")

        # ======================
        # 第三步：全局去重 + 编号重整
        # ======================
        original_count = len(all_cases)
        all_cases = deduplicate_cases(all_cases)
        main_logger.info(f"全局去重: {original_count} → {len(all_cases)}")
        all_cases = self.renumber_cases(all_cases, prefix="TC_", start=1)

        # ======================
        # 最终统计
        # ======================
        log_summary(len(all_cases), len(ai_cases), code_count)

        self.end_trace()
        return all_cases

    def _generate_ai_business_cases(self, project_name: str, module_name: str, url_path: str,
                                    default_body: dict, required_fields: List[str],
                                    business_rules: str, method: str, is_login_module: bool) -> List[Dict]:
        """AI 生成需要业务理解的深度用例 - 基于测试点分析模式"""

        param_fields = "\n".join([f"- {p}: {default_body.get(p, '示例值')}" for p in default_body.keys()])
        business_scenarios = self.get_business_scenarios(module_name, is_login_module)

        # 处理 URL 中的动态参数占位符（如 :id → 替换为具体示例值）
        clean_url = url_path
        url_params_hint = ""
        if ':' in url_path:
            # 提取动态参数名并生成替换提示
            url_params = re.findall(r':(\w+)', url_path)
            url_params_hint = "\n【URL动态参数替换规则】\n"
            for p in url_params:
                # 根据参数名生成合理示例值
                sample_val = {"id": "93", "courseId": "1001", "userId": "10086",
                              "fileId": "F2024001", "contractId": "C2024001"}.get(p, "test_001")
                clean_url = clean_url.replace(f":{p}", sample_val)
                url_params_hint += f"- URL 中的 :{p} 必须替换为具体值（如 {sample_val}），不能保留占位符\n"

        # 构建提示词
        prompt_template = prompt_loader.get_raw_prompt("task_templates.api_case")
        prompt = prompt_template.format(
            project_name=project_name,
            module_name=module_name,
            url_path=clean_url,  # 使用替换了动态参数的 URL
            method=method,
            business_rules=business_rules,
            param_fields=param_fields,
            required_fields=json.dumps(required_fields, ensure_ascii=False),
            business_scenarios=business_scenarios
        )

        # 追加 URL 参数替换提示
        if url_params_hint:
            prompt += url_params_hint

        # 添加防御规则和策略
        defense_rules = prompt_loader.get_defense_rules()
        case_strategy = prompt_loader.get_case_strategy()
        prompt = f"{prompt}\n\n{defense_rules}\n\n{case_strategy}"

        log_ai_prompt(prompt)

        # 定义降级函数
        def fallback_cases():
            """生成降级用例，确保不为空且有基本的场景覆盖"""
            main_logger.warning(f"AI 响应解析失败，使用降级用例")
            cases = [self._create_basic_positive_case(
                method, url_path, default_body, required_fields
            )]
            # 追加边界值用例（如果有业务约束）
            constraints = business_rules if business_rules else ""
            if "0" in constraints or "1" in constraints or "500" in constraints:
                for field in default_body:
                    if "content" in field.lower() or "name" in field.lower() or "标题" in field:
                        cases.append(self._create_fallback_case(
                            "边界值-{}-长度0字符".format(field), method, url_path,
                            self._make_body_with_field(default_body, field, ""),
                            400, "参数错误", "P1"
                        ))
                        cases.append(self._create_fallback_case(
                            "边界值-{}-超长字符".format(field), method, url_path,
                            self._make_body_with_field(default_body, field, "a" * 501),
                            400, "参数错误", "P1"
                        ))
                        break
            # 追加格式异常用例
            cases.append(self._create_fallback_case(
                "反向用例-特殊字符注入", method, url_path,
                self._make_body_with_field(default_body,
                    list(default_body.keys())[0] if default_body else "param",
                    "<script>alert(1)</script>"),
                400, "参数错误", "P2"
            ))
            return cases

        # 使用基类的安全 JSON 调用
        cases = self.safe_llm_json_call(prompt, fallback_cases)

        if not cases:
            main_logger.warning(f"AI 生成失败，返回空列表")
            return []

        log_ai_parsed(cases)

        # ===== 质量检查：检测解析碎片 =====
        # 当 LLM 返回格式不规范的 JSON 时，策略 9 可能只提取到内层对象碎片
        # （如 body 子字段），导致大量用例缺少 title 和 body 内容。
        # 条件：超过 50% 的用例 body 为空 → 判定为解析碎片 → 使用降级
        valid_cases = [c for c in cases
                       if isinstance(c.get("body"), dict) and c["body"]]
        if len(valid_cases) < len(cases) * 0.3 and fallback_cases:
            main_logger.warning(
                f"解析质量低：仅 {len(valid_cases)}/{len(cases)} 条含有效 body，"
                f"判定为 JSON 解析碎片，使用降级用例"
            )
            cases = fallback_cases()
            if not cases:
                return []

        # ===== 登录/注册等免Token模块不需要 Token 异常用例 =====
        if is_login_module:
            before = len(cases)
            cases = [c for c in cases if "Token" not in c.get("title", "")]
            if len(cases) < before:
                main_logger.info(f"登录模块过滤掉 {before - len(cases)} 条 Token 异常用例")

        # 后处理：补充默认字段
        for case in cases:
            if not case.get("headers"):
                case["headers"] = DEFAULT_HEADERS.copy()
            if not case.get("method"):
                case["method"] = method
            if not case.get("url"):
                case["url"] = url_path
            case["body"] = self.ensure_dict_field(case.get("body"))

            # 清理：JSON 降级解析可能把请求头字段泄漏到顶层
            for header_field in ["Content-Type", "Authorization", "Accept", "User-Agent"]:
                if header_field in case and "headers" in case:
                    if header_field not in case["headers"]:
                        case["headers"][header_field] = case[header_field]
                    del case[header_field]

            # 确保必填字段存在（缺失会导致格式检查扣分）
            if not case.get("title"):
                # 尝试从其他字段推断标题，兜底用 case_id
                case["title"] = f"AI生成用例_{case.get('case_id', 'unknown')}"
            if "priority" not in case or not case.get("priority"):
                # 根据标题推断优先级
                title = case.get("title", "")
                if "正向" in title:
                    case["priority"] = "P0"
                elif "边界" in title:
                    case["priority"] = "P1"
                else:
                    case["priority"] = "P2"

            if "extract" not in case and "正向" in case.get("title", ""):
                if is_login_module:
                    case["extract"] = {"token": "body.data.token"}
                else:
                    case["extract"] = {"id": "body.data.id"}

            if "assert" in case:
                case["assert"] = self.normalize_assert(case["assert"], method)
            else:
                case["assert"] = self.normalize_assert({}, method)

        # 按 case_strategy 比例调整用例类型分布
        cases = self._enforce_case_strategy(cases)

        return cases if cases else []

    def _create_basic_positive_case(self, method: str, url_path: str,
                                    default_body: dict, required_fields: List[str]) -> Dict:
        """创建基础正向用例（降级用）"""
        # 构造有效的请求体
        body = default_body.copy()
        for field in required_fields:
            if field not in body or not body[field]:
                body[field] = f"test_{field}_001"

        return {
            "case_id": "TC_001",
            "title": "正向用例-基础验证",
            "method": method,
            "url": url_path,
            "headers": DEFAULT_HEADERS.copy(),
            "body": body,
            "assert": self.normalize_assert({}, method),
            "extract": {},
            "priority": "P0"
        }

    def _create_fallback_case(self, title: str, method: str, url_path: str,
                               body: dict, status_code: int, msg: str, priority: str) -> Dict:
        """创建降级用例（统一格式）"""
        return {
            "case_id": "TC_999",
            "title": title,
            "method": method,
            "url": url_path,
            "headers": DEFAULT_HEADERS.copy(),
            "body": body,
            "assert": self.normalize_assert({"status_code": status_code, "body.msg": msg}, method),
            "extract": {},
            "priority": priority,
        }

    def _make_body_with_field(self, base_body: dict, field: str, value: Any) -> dict:
        """在 base_body 基础上替换指定字段的值"""
        body = base_body.copy()
        body[field] = value
        return body

    def _get_module_config(self, project_name: str, module_name: str) -> Optional[Dict]:
        """从数据库读取模块配置"""
        rule = get_rule(project_name, module_name)
        if not rule:
            return None

        return {
            "input_fields": rule.get("input_fields", []),
            "required_fields": rule.get("required_fields", []),
            "url_path": rule.get("url_path", f"/api/{module_name}"),
            "default_body": rule.get("default_body", {}),
            "constraints": rule.get("constraints", ""),
        }

    def _get_default_config(self, module_name: str) -> Dict:
        """获取默认配置"""
        return {
            "input_fields": [],
            "required_fields": [],
            "url_path": f"/api/{module_name}",
            "default_body": {},
            "constraints": "",
        }

    def _get_method_from_url(self, url_path: str, module_name: str = "") -> str:
        """根据 URL 特征判断请求方法"""
        query_keywords = ["list", "search", "query", "get", "find", "page", "index", "show", "detail"]
        for keyword in query_keywords:
            if keyword in url_path.lower():
                return "GET"

        query_modules = ["查询", "列表", "搜索", "详情"]
        for keyword in query_modules:
            if keyword in module_name:
                return "GET"

        return "POST"

    def export_excel(self, cases: List[Dict], project_name: str, module_name: str) -> str:
        """导出Excel并美化格式"""
        filepath = ExcelExporter.export_api_cases(cases, project_name, module_name)
        if filepath:
            main_logger.info(f"Excel导出成功：{filepath}")
        return filepath

    def export_data_driver(self, cases: List[Dict], project_name: str, module_name: str) -> str:
        """导出数据驱动JSON"""
        if not cases:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{project_name}_{module_name}_data_driver_{timestamp}.json"
        filename = re.sub(r'[\\/*?:"<>|]', '', filename)
        filepath = os.path.join(DATA_DRIVER_DIR, filename)

        template = {"method": "POST", "url": "", "headers": {"Content-Type": "application/json"}}

        for case in cases:
            if case.get("priority") == "P0":
                template["method"] = case.get("method", "POST")
                template["url"] = case.get("url", "")
                template["headers"] = case.get("headers", {"Content-Type": "application/json"})
                break

        test_data = []
        for case in cases:
            data_item = {
                "case_id": case.get("case_id", ""),
                "title": case.get("title", ""),
                "priority": case.get("priority", "P2"),
                "body": case.get("body", {}),
                "expected": case.get("assert", {}),
                "extract": case.get("extract", {})
            }
            test_data.append(data_item)

        output = {
            "project": project_name,
            "module": module_name,
            "generated_at": datetime.now().isoformat(),
            "template": template,
            "test_data": test_data
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        main_logger.info(f"数据驱动JSON导出成功：{filepath}")
        return filepath

    def export_pytest_script(self, cases: List[Dict], project_name: str, module_name: str) -> str:
        """生成Pytest脚本"""
        if not cases:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_{module_name}_{timestamp}.py"
        filename = re.sub(r'[\\/*?:"<>|]', '', filename)
        filepath = os.path.join(PYTEST_DIR, filename)

        # 使用紧凑 JSON（不打缩进）以减少脚本体积，让 @parametrize 在脚本前部可见
        test_data_json = json.dumps(cases, ensure_ascii=False, indent=None)

        pytest_code = f'''"""
自动生成的接口自动化测试脚本
项目：{project_name}
模块：{module_name}
生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
import pytest
import requests
import json

BASE_URL = "http://localhost:8080"
session = requests.Session()


class Test{module_name}:

    @pytest.mark.parametrize("case", TEST_CASES, ids=lambda x: x.get("case_id", "unknown"))
    def test_api(self, case):
        url = BASE_URL + case["url"]
        method = case["method"].upper()
        headers = case.get("headers", {{"Content-Type": "application/json"}})
        body = case.get("body", {{}})

        if method == "GET":
            resp = session.get(url, headers=headers)
        elif method == "POST":
            resp = session.post(url, headers=headers, json=body)
        elif method == "PUT":
            resp = session.put(url, headers=headers, json=body)
        elif method == "DELETE":
            resp = session.delete(url, headers=headers)
        else:
            raise ValueError(f"不支持的方法: {{method}}")

        for key, value in case.get("assert", {{}}).items():
            if key == "status_code":
                assert resp.status_code == value
            else:
                assert resp.json().get(key) == value


TEST_CASES = {test_data_json}
'''

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(pytest_code)

        main_logger.info(f"Pytest脚本导出成功：{filepath}")
        return filepath

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