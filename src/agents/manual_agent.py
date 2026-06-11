"""手工测试用例生成 Agent - 支持动态列数据驱动"""
import sys
import os
import re
import json
import logging
from typing import List, Dict, Optional, Tuple
from src.utils.common_tools import deduplicate_cases
from datetime import datetime
from src.utils.excel_exporter import ExcelExporter

# 将项目根目录添加到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.agents.base_agent import BaseAgent
from src.tools.rule_manager import get_rule
from src.config.settings import DATA_DIR, DEBUG_MODE
from src.core.logger import main_logger, debug_log
from src.core.prompt_loader import prompt_loader



class ManualTestAgent(BaseAgent):
    """手工测试用例生成 Agent - 支持动态列数据驱动"""

    def __init__(self):
        super().__init__()

    def generate(self, project_name: str, module_name: str,
                 test_type: str = "", expected_num: int = 0,
                 business_rules: str = "") -> Tuple[List[Dict], List[str]]:
        """
        生成手工测试用例

        参数:
        - project_name: 项目名称
        - module_name: 模块名称
        - test_type: 测试类型（功能/安全/性能等）
        - expected_num: 期望数量（0=不限，仅作为展示上限，不强求凑数）
        - business_rules: 业务规则

        返回:
        - (cases, fields): 用例列表和动态字段列表
        """
        # 开始追踪
        trace_id = self.start_trace()
        main_logger.info(f"开始生成手工用例: {project_name}/{module_name} (trace_id: {trace_id})")
        main_logger.info(f"测试类型: {test_type}, 期望数量: {expected_num if expected_num > 0 else '不限'}")

        # 1. 输入校验
        valid, msg = self.validate_input(
            project=project_name,
            module=module_name,
            business_rules=business_rules
        )
        if not valid:
            debug_log(f"输入校验失败: {msg}")
            self.end_trace()
            return [], []

        # 2. 获取数据库规则（动态字段从这里来）
        db_rule = get_rule(project_name, module_name)

        # 3. 动态获取字段列表
        fields = self._get_dynamic_fields(db_rule, business_rules, module_name)
        main_logger.info(f"动态字段列表: {fields}")

        # 4. 合并规则
        merged_rules = self._merge_rules(db_rule, business_rules)

        # 5. 构建提示词
        requirement = f"项目：{project_name}，模块：{module_name}"
        if test_type and test_type.strip():
            requirement += f"，测试类型：{test_type}"

        prompt = self._build_prompt(project_name, module_name, fields, expected_num)
        prompt += f"""

【业务规则】
{merged_rules}

【需求】
{requirement}

【参数说明】
请根据以下参数生成测试数据，每个参数作为独立列：
{self._format_fields_for_prompt(fields)}

--- 重要质量要求 ---

【测试数据要求】
1. 测试数据必须使用具体、真实的示例值（如用户名用 admin，密码用 123456），不能使用"test_xxx_001"或"测试值"等占位符
2. 每个字段的取值要符合业务含义（如手机号用 13800138000，价格用 99.9或100）
3. 正向用例的数据必须合法有效，反向用例的数据必须确实非法

【边界场景要求】
1. 有明确范围/长度的参数必须覆盖边界值（最小值、最大值、超出边界）
2. 尽可能覆盖：空值、超长、特殊字符、非法格式等异常输入
3. 每个模块至少包含 3-5 个边界场景

请直接输出Markdown格式的用例："""

        main_logger.info(f"提示词长度: {len(prompt)}")

        # 6. 调用 LLM
        try:
            response = self.safe_llm_call(prompt, default_return="")
            if not response:
                main_logger.warning("LLM 返回为空，使用降级用例")
                fallback = self._create_fallback_cases(project_name, module_name, fields, test_type)
                self.end_trace()
                return fallback, fields

            markdown_content = response.replace("```markdown", "").replace("```", "").strip()

            cases = self._parse_cases(markdown_content, fields)

            # 7. 部分恢复：如果解析结果为空但有原始内容，生成降级用例
            if not cases and markdown_content:
                main_logger.warning("LLM 响应无法解析为有效用例，使用降级用例")
                fallback = self._create_fallback_cases(project_name, module_name, fields, test_type)
                self.end_trace()
                return fallback, fields

            # 8. 后处理（去重、去噪）
            original_count = len(cases)
            cases = deduplicate_cases(cases, key_fields=[])  # 只用标题去重
            main_logger.info(f"标题去重: {original_count} → {len(cases)}")
            cases = self._denoise_cases(cases)

            # 9. 去噪后如果全被过滤了，也用降级用例
            if not cases:
                main_logger.warning("所有用例被去噪过滤，使用降级用例")
                fallback = self._create_fallback_cases(project_name, module_name, fields, test_type)
                self.end_trace()
                return fallback, fields

            # 10. 数量控制（只做上限截断，不强制凑数）
            original_count = len(cases)
            if 0 < expected_num < len(cases):
                cases = cases[:expected_num]
                main_logger.info(f"用例数 {original_count} 超过期望 {expected_num}，仅展示前 {expected_num} 条")
            else:
                main_logger.info(
                    f"生成 {original_count} 条用例（期望{expected_num if expected_num > 0 else "不限"}条，未强制凑数）")
            self.end_trace()
            return cases, fields

        except (KeyError, ValueError) as e:
            main_logger.error(f"参数或格式错误: {e}")
            fallback = self._create_fallback_cases(project_name, module_name, fields, test_type)
            self.end_trace()
            return fallback, fields
        except Exception as e:
            main_logger.error(f"生成失败(未知错误): {type(e).__name__}: {e}")
            fallback = self._create_fallback_cases(project_name, module_name, fields, test_type)
            self.end_trace()
            return fallback, fields

    def _get_dynamic_fields(self, db_rule: Optional[Dict], business_rules: str, module_name: str) -> List[str]:
        """
        动态获取字段列表
        优先级：数据库规则中的 input_fields > 从业务规则解析 > 根据模块名推断 > 默认字段
        """
        # 1. 优先从数据库规则获取
        if db_rule and db_rule.get("input_fields"):
            fields = db_rule["input_fields"]
            if isinstance(fields, list) and fields:
                main_logger.info(f"从数据库获取字段: {fields}")
                return fields

        # 2. 从业务规则解析（匹配如：用户名、密码、验证码等）
        if business_rules:
            import re
            fields = set()
            # 匹配 key: value 或 key=value 格式
            for line in business_rules.split('\n'):
                match = re.match(r'(\w+)\s*[:=]\s*\S+', line.strip())
                if match:
                    fields.add(match.group(1))
            if fields:
                main_logger.info(f"从业务规则解析字段: {list(fields)}")
                return list(fields)

        # 3. 根据模块名推断常见字段
        module_fields_map = {
            "登录": ["用户名", "密码", "验证码"],
            "注册": ["用户名", "密码", "确认密码", "手机号", "验证码"],
            "新增": ["名称", "类型", "价格", "描述"],
            "添加": ["名称", "类型", "价格", "描述"],
            "修改": ["ID", "名称", "类型", "价格"],
            "更新": ["ID", "名称", "类型", "价格"],
            "删除": ["ID"],
            "查询": ["关键词", "页码", "每页条数"],
            "搜索": ["关键词", "页码", "每页条数"],
            "列表": ["页码", "每页条数"],
        }

        for key, field_list in module_fields_map.items():
            if key in module_name:
                main_logger.info(f"根据模块名推断字段: {field_list}")
                return field_list

        # 4. 默认字段
        default_fields = ["参数1", "参数2", "参数3"]
        main_logger.info(f"使用默认字段: {default_fields}")
        return default_fields

    def _format_fields_for_prompt(self, fields: List[str]) -> str:
        """格式化字段用于提示词 — 使用有业务含义的示例值"""
        if not fields:
            return "- 无特殊参数"

        # 常见字段名到合理示例值的映射
        field_examples = {
            "用户名": "admin", "password": "123456", "密码": "123456",
            "验证码": "8888", "code": "8888", "uuid": "a1b2c3d4-e5f6-7890",
            "手机号": "13800138000", "phone": "13800138000",
            "邮箱": "test@example.com", "email": "test@example.com",
            "名称": "测试课程", "name": "测试课程",
            "价格": "99.9", "price": "99.9", "金额": "100",
            "数量": "1", "num": "1", "count": "1",
            "ID": "1", "id": "1", "商品ID": "1001",
            "类型": "1", "type": "1", "subject": "1",
            "描述": "这是一个测试数据", "info": "测试数据", "remark": "测试备注",
            "状态": "1", "status": "1",
            "token": "eyJhbGciOiJIUzI1NiJ9.xxx",
            "file": "/path/to/test.pdf",
            "page": "1", "关键词": "测试", "keyword": "测试",
        }

        lines = []
        for field in fields:
            # 兼容数据库返回 dict 类型字段（{name, type, description}）
            field_name = field["name"] if isinstance(field, dict) else field
            example = field_examples.get(field_name, f"示例{field_name}")
            if isinstance(field, dict):
                desc = field.get("description", "")
                req = "必填" if field.get("required") else "选填"
                lines.append(f"- {field_name}：{example}（{req}，{desc}）")
            else:
                lines.append(f"- {field}：{example}")
        return "\n".join(lines)

    def _build_prompt(self, project: str, module: str, fields: List[str], num: int) -> str:
        """构建系统提示词"""
        field_names = [f["name"] if isinstance(f, dict) else f for f in fields]
        fields_example = "\n".join([f"- {fn}：test_{fn}_001" for fn in field_names])

        # 从 yaml 加载提示词模板
        prompt_template = prompt_loader.get_raw_prompt("task_templates.manual_case")

        # 格式化提示词
        prompt = prompt_template.format(
            project=project,
            module=module,
            fields_example=fields_example,
            num=num
        )

        return prompt

    def _parse_cases(self, markdown_content: str, fields: List[str]) -> List[Dict]:
        """解析Markdown格式的用例，支持动态字段，测试步骤保持换行"""
        cases = []
        blocks = re.split(r'\n##\s+', markdown_content)

        for block in blocks:
            if not block.strip():
                continue

            # 基础字段
            case = {
                "用例ID": "",
                "标题": "",
                "前置条件": "",
                "测试步骤": "",
                "预期结果": "",
                "实际结果": "",
                "优先级": "P2"
            }
            # 动态添加参数字段
            for f in fields:
                case[f] = ""

            lines = block.split('\n')
            current_key = None
            current_value_lines = []

            for line in lines:
                line_stripped = line.strip()

                if line_stripped.startswith('-') and ('：' in line_stripped or ':' in line_stripped):
                    # 保存上一个字段的值
                    if current_key and current_value_lines:
                        if current_key in ["测试步骤", "预期结果"]:
                            # 保持换行格式，用 \n 连接
                            case[current_key] = '\n'.join(current_value_lines).strip()
                        else:
                            case[current_key] = '\n'.join(current_value_lines).strip()
                        current_value_lines = []

                    if '：' in line_stripped:
                        key, value = line_stripped[2:].split('：', 1)
                    else:
                        key, value = line_stripped[2:].split(':', 1)

                    key = key.strip()
                    value = value.strip()

                    if key in ["测试步骤", "预期结果"] and not value:
                        # 多行字段开始
                        current_key = key
                        current_value_lines = []
                    else:
                        current_key = None
                        if key in case:
                            case[key] = value
                        elif key in fields:
                            case[key] = value

                elif current_key and line_stripped:
                    # 收集多行内容
                    current_value_lines.append(line_stripped)

            # 保存最后一个字段
            if current_key and current_value_lines:
                if current_key in ["测试步骤", "预期结果"]:
                    case[current_key] = '\n'.join(current_value_lines).strip()
                else:
                    case[current_key] = '\n'.join(current_value_lines).strip()

            # 补充默认值
            if case["标题"] or case["用例ID"]:
                if not case.get("前置条件"):
                    case["前置条件"] = "无"
                if not case.get("测试步骤"):
                    case["测试步骤"] = "1. 执行测试操作"
                if not case.get("预期结果"):
                    case["预期结果"] = "操作成功"
                cases.append(case)

        return cases

    def _denoise_cases(self, cases: List[Dict]) -> List[Dict]:
        """过滤无效用例"""
        valid = []
        for case in cases:
            if not case.get('标题') or not case.get('测试步骤'):
                continue
            if len(case.get('测试步骤', '')) < 10:
                continue
            # 不再过滤"错误"相关短消息——反向用例的预期结果可能很短但合法
            valid.append(case)

        if len(valid) != len(cases):
            main_logger.info(f"去噪: {len(cases)} → {len(valid)}")
        return valid

    def _merge_rules(self, db_rule: Optional[Dict], user_rules: str) -> str:
        """合并数据库规则和用户规则"""
        rules_list = []
        if db_rule and db_rule.get('constraints'):
            rules_list.append(f"【数据库规则】{db_rule.get('constraints')}")
        if user_rules:
            rules_list.append(f"【用户规则】{user_rules}")
        return "\n".join(rules_list) if rules_list else "无特殊规则"

    def _create_fallback_cases(self, project_name: str, module_name: str,
                                fields: List[str], test_type: str = "") -> List[Dict]:
        """创建降级用例（LLM 失败时的保底方案）"""
        main_logger.info(f"生成降级用例: {project_name}/{module_name}")

        fallback_type = test_type if test_type else "功能"
        cases = [
            self._create_basic_case("TC_001", f"{fallback_type}验证-基础功能",
                                    "P0", "系统正常运行",
                                    f"1. 进入{module_name}页面\n2. 输入标准测试数据\n3. 执行{module_name}操作",
                                    "操作成功，返回预期结果", fields),
            self._create_basic_case("TC_002", f"{fallback_type}验证-异常输入",
                                    "P1", "系统正常运行",
                                    f"1. 进入{module_name}页面\n2. 输入异常测试数据\n3. 执行{module_name}操作",
                                    "系统提示错误信息，操作失败", fields),
            self._create_basic_case("TC_003", f"{fallback_type}验证-边界条件",
                                    "P2", "系统正常运行",
                                    f"1. 进入{module_name}页面\n2. 输入边界测试数据\n3. 执行{module_name}操作",
                                    "系统正确处理边界情况", fields),
        ]
        main_logger.info(f"降级用例: 生成 {len(cases)} 条基础用例")
        return cases

    def _create_basic_case(self, case_id: str, title: str, priority: str,
                           precondition: str, steps: str, expected: str,
                           fields: List[str]) -> Dict:
        """创建单条基础用例（使用有业务含义的示例值）"""
        _field_examples = {
            "用户名": "admin", "password": "123456", "密码": "123456",
            "验证码": "8888", "code": "8888", "uuid": "a1b2c3d4-e5f6-7890",
            "手机号": "13800138000", "phone": "13800138000",
            "邮箱": "test@example.com",
            "名称": "测试课程", "name": "测试课程",
            "价格": "99.9", "price": "99.9", "金额": "100",
            "数量": "1", "num": "1",
            "ID": "1", "id": "1", "商品ID": "1001",
            "类型": "1", "subject": "1",
            "描述": "测试数据", "info": "测试数据",
            "状态": "1", "status": "1",
            "file": "/path/to/test.pdf",
            "page": "1", "关键词": "测试", "keyword": "测试",
        }
        case = {
            "用例ID": case_id,
            "标题": title,
            "前置条件": precondition,
            "测试步骤": steps,
            "预期结果": expected,
            "实际结果": "",
            "优先级": priority,
        }
        for f in fields:
            field_name = f["name"] if isinstance(f, dict) else f
            case[field_name] = _field_examples.get(field_name, f"示例{field_name}")
        return case

    def export_excel(self, cases: List[Dict], project_name: str, module_name: str,
                     test_type: str = "", fields: List[str] = None) -> str:
        """导出手工测试用例Excel"""
        filepath = ExcelExporter.export_manual_cases(cases, project_name, module_name, test_type, fields)
        if filepath:
            main_logger.info(f"Excel导出成功：{filepath}")
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