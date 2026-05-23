# testcase_agent.py
import re
import os
import json
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any
from common import llm, call_llm_with_retry, data_folder_path, clean_name, get_next_file_number
from database import get_rule

# ======================
# 模块参数配置（动态列）- 作为参考，不强制
# ======================
DEFAULT_FIELDS = ["param1", "param2", "param3"]


def build_system_prompt(fields, num):
    """动态构建提示词 - 手工用例用"""
    fields_example = "\n".join([f"- {f}：示例值" for f in fields])

    return f"""你是软件测试用例生成专家。

【核心目标】
生成数据驱动测试用例，测试步骤必须每步换行，预期结果为断言关键词。

【输出格式 - 每条用例用## 分隔，严格遵守】
## 正常登录
- 用例ID：TC_001
- 标题：正常登录
{fields_example}
- 前置条件：用户已注册，账号状态正常
- 测试步骤：
  1. 打开登录页面
  2. 输入用户名
  3. 输入密码
  4. 输入验证码
  5. 点击登录按钮
- 预期结果：登录成功
- 实际结果：（留空）
- 优先级：P0

【⚠️ 测试步骤格式要求 - 必须遵守】
测试步骤必须按以下格式，每步独占一行，以数字序号开头。

【预期结果格式要求】
预期结果必须是简洁的断言关键词。

【数量要求】生成 {num} 条用例，覆盖正常流程和异常流程
"""


def parse_column_cases(markdown_content, fields):
    """解析列式格式用例 - 手工用例用"""
    cases = []
    blocks = re.split(r'\n##\s+', markdown_content)

    for block in blocks:
        if not block.strip():
            continue

        case = {
            "用例ID": "",
            "标题": "",
            "前置条件": "",
            "测试步骤": "",
            "预期结果": "",
            "实际结果": "",
            "优先级": "P2"
        }
        for f in fields:
            case[f] = ""

        lines = block.split('\n')
        current_key = None
        current_value_lines = []

        for line in lines:
            line_stripped = line.strip()

            if line_stripped.startswith('-') and ('：' in line_stripped or ':' in line_stripped):
                if current_key and current_value_lines:
                    case[current_key] = '\n'.join(current_value_lines).strip()
                    current_value_lines = []

                if '：' in line_stripped:
                    key, value = line_stripped[2:].split('：', 1)
                else:
                    key, value = line_stripped[2:].split(':', 1)

                key = key.strip()
                value = value.strip()

                if key in ["测试步骤", "预期结果"] and not value:
                    current_key = key
                    current_value_lines = []
                else:
                    current_key = None
                    if key in case:
                        case[key] = value

            elif current_key and line_stripped:
                if re.match(r'^\d+[\.、]', line_stripped):
                    current_value_lines.append(line_stripped)
                elif current_value_lines:
                    current_value_lines[-1] += " " + line_stripped

        if current_key and current_value_lines:
            case[current_key] = '\n'.join(current_value_lines).strip()

        if case["标题"] or case["用例ID"]:
            if not case["前置条件"]:
                case["前置条件"] = "无"
            if not case["测试步骤"]:
                case["测试步骤"] = "1. 执行测试操作"
            if not case["预期结果"]:
                case["预期结果"] = "操作成功"
            cases.append(case)

    return cases


def generate_test_cases(project_name, module_name, test_type="", num=10, business_rules=""):
    """生成手工测试用例"""
    db_rule = get_rule(project_name, module_name)

    rules_list = []
    if db_rule:
        if db_rule.get('constraints'):
            rules_list.append(db_rule.get('constraints'))
    if business_rules:
        rules_list.append(business_rules)

    merged_rules = "\n".join(rules_list) if rules_list else "无特殊规则"

    if test_type and test_type.strip():
        requirement = f"项目：{project_name}，模块：{module_name}，测试类型：{test_type}"
    else:
        requirement = f"项目：{project_name}，模块：{module_name}"

    system_prompt = build_system_prompt(DEFAULT_FIELDS, num)

    prompt = system_prompt + f"""

【业务规则】
{merged_rules}

【需求】
{requirement}

请直接输出Markdown格式的用例："""

    response = call_llm_with_retry(prompt)
    markdown_content = response.content
    markdown_content = markdown_content.replace("```markdown", "").replace("```", "").strip()

    cases = parse_column_cases(markdown_content, DEFAULT_FIELDS)
    return cases


def export_excel(cases, project_name, module_name, test_type=""):
    """导出手工测试用例Excel"""
    if not cases:
        return None

    next_num = get_next_file_number()

    if test_type and test_type.strip():
        prefix = f"{clean_name(project_name)}_{clean_name(module_name)}_{clean_name(test_type)}"
    else:
        prefix = f"{clean_name(project_name)}_{clean_name(module_name)}"

    filename = f"{prefix}_{next_num:03d}.xlsx"
    full_path = os.path.join(data_folder_path, filename)

    cols = ["用例ID", "标题", "前置条件", "测试步骤", "预期结果", "实际结果", "优先级"]
    # 动态添加其他字段
    for key in cases[0].keys():
        if key not in cols:
            cols.append(key)
    cols = [c for c in cols if c in cases[0].keys()] if cases else cols

    df = pd.DataFrame(cases)
    df = df[cols]

    with pd.ExcelWriter(full_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="测试用例", index=False)

    print(f"✅ 导出成功：{full_path}")
    return full_path


# ======================
# JSON 容错解析函数
# ======================
def safe_json_parse(content):
    """容错解析 JSON，支持多种格式"""
    # 1. 去除 markdown 代码块标记
    content = re.sub(r'```json\s*', '', content)
    content = re.sub(r'```\s*$', '', content)
    content = content.strip()

    # 2. 尝试直接解析
    try:
        return json.loads(content)
    except:
        pass

    # 3. 尝试修复单引号
    try:
        fixed = re.sub(r"(?<!\\)'", '"', content)
        return json.loads(fixed)
    except:
        pass

    # 4. 尝试提取第一个完整的 JSON 数组
    try:
        match = re.search(r'\[\s*\{.*?\}\s*\]', content, re.DOTALL)
        if match:
            return json.loads(match.group())
    except:
        pass

    # 5. 尝试提取第一个完整的 JSON 对象
    try:
        brace_count = 0
        start = -1
        for i, char in enumerate(content):
            if char == '{':
                if brace_count == 0:
                    start = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start != -1:
                    json_str = content[start:i + 1]
                    return json.loads(json_str)
    except:
        pass

    # 6. 最后尝试：修复未加引号的键名
    try:
        fixed = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', content)
        return json.loads(fixed)
    except:
        raise ValueError(f"无法解析JSON: {content[:200]}")


def ensure_dict_field(value, field_name="body"):
    """确保字段是字典类型，如果是字符串则尝试解析"""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value) if value else {}
            return parsed if isinstance(parsed, dict) else {}
        except:
            return {}
    return {}


# ======================
# 接口自动化用例生成（通用版 - 支持 GET/POST 参数）
# ======================
def generate_api_test_cases(project_name: str, module_name: str, test_type: str = "", num: int = 10,
                            business_rules: str = "") -> List[Dict]:
    """
    生成接口自动化测试用例（JSON格式）
    完全动态：让 LLM 从业务规则中自动提取字段
    支持 GET 请求的 params 和 POST 请求的 body
    """
    # 规则获取和合并
    db_rule = get_rule(project_name, module_name)

    rules_list = []
    if db_rule:
        if db_rule.get('constraints'):
            rules_list.append(db_rule.get('constraints'))
        if db_rule.get('input_fields'):
            rules_list.append(f"输入字段：{db_rule.get('input_fields')}")
        if db_rule.get('verification_code'):
            rules_list.append(f"验证码：{db_rule.get('verification_code')}")
    if business_rules:
        rules_list.append(business_rules)

    # 如果没有规则，给一个通用提示
    if not rules_list:
        rules_list.append(f"请根据'{module_name}'模块的常见业务逻辑生成测试用例")

    merged_rules = "\n".join(rules_list)

    if test_type and test_type.strip():
        test_desc = f"测试类型：{test_type}"
    else:
        test_desc = "覆盖正向、异常、边界场景"

    # 构建 URL
    url_path = f"/api/{module_name.lower().replace(' ', '_').replace('搜索', 'search').replace('登录', 'login').replace('购物车', 'cart').replace('下单', 'order')}"

    prompt = f"""你是接口自动化测试用例生成专家。请生成JSON格式的接口测试用例。

【项目】{project_name}
【模块】{module_name}

【业务规则】
{merged_rules}

【期望数量】约 {num} 条（请根据业务复杂度自行决定，不要凑数，质量优先）

【重要规则 - 必须遵守】
1. **请从【业务规则】中提取请求参数字段名和数据类型**
2. 字段名必须使用英文（如 username, password, city, goods_id, checkin, checkout）
3. 不要使用中文字段名
4. 根据请求方法决定参数位置：
   - GET 请求：参数放在 "params" 字段
   - POST/PUT/DELETE 请求：参数放在 "body" 字段
5. 登录、新增类接口用 POST，查询类接口用 GET
6. 正向用例（预期成功）必须提取 token 或 session_id 到 "extract" 字段
7. 异常用例的 "extract" 字段为空对象 {{}}
8. "body" 和 "params" 的值必须是 JSON 对象 {{}}，不能是字符串

【输出格式 - 严格JSON数组】
[
    {{
        "case_id": "TC_001",
        "title": "正常{module_name}",
        "method": "POST",
        "url": "{url_path}",
        "headers": {{"Content-Type": "application/json"}},
        "body": {{
            // POST 请求的参数放这里
        }},
        "params": {{
            // GET 请求的参数放这里
        }},
        "assert": {{
            "status_code": 200,
            "body.code": 0,
            "body.msg": "操作成功"
        }},
        "extract": {{"token": "body.data.token"}}
    }}
]

请只输出JSON数组，不要有任何解释文字："""

    try:
        response = call_llm_with_retry(prompt)
        content = response.content.strip()

        cases = safe_json_parse(content)

        if isinstance(cases, dict):
            cases = [cases]
        # 不限制数量，让 LLM 自己决定
        # if len(cases) > num:
        #     cases = cases[:num]

        # 补充默认字段并修复类型
        for i, case in enumerate(cases, 1):
            if not case.get("case_id"):
                case["case_id"] = f"API_TC_{i:03d}"
            if not case.get("headers"):
                case["headers"] = {"Content-Type": "application/json"}

            # 确保 body 是字典
            case["body"] = ensure_dict_field(case.get("body"), "body")

            # 确保 params 是字典
            case["params"] = ensure_dict_field(case.get("params"), "params")

            # 确保 extract 是字典
            if "extract" not in case or case["extract"] is None:
                assert_body = case.get("assert", {})
                if assert_body.get("body.code") == 0:
                    case["extract"] = {"token": "body.data.token"}
                else:
                    case["extract"] = {}
            elif isinstance(case["extract"], str):
                try:
                    case["extract"] = json.loads(case["extract"]) if case["extract"] else {}
                except:
                    case["extract"] = {}

        print(f"✅ 接口用例生成成功：{len(cases)}条")
        return cases

    except Exception as e:
        print(f"❌ 生成失败: {e}")
        print(f"原始返回内容: {content[:500] if 'content' in dir() else 'N/A'}")
        return []


def export_api_excel(cases: List[Dict], project_name: str, module_name: str, test_type: str = "") -> str:
    """
    导出接口用例为Excel
    同时从 body 和 params 中提取动态参数列
    """
    if not cases:
        return None

    next_num = get_next_file_number()
    prefix = f"{clean_name(project_name)}_{clean_name(module_name)}_API"
    if test_type and test_type.strip():
        prefix = f"{clean_name(project_name)}_{clean_name(module_name)}_{clean_name(test_type)}_API"

    filename = f"{prefix}_{next_num:03d}.xlsx"
    full_path = os.path.join(data_folder_path, filename)

    # 动态提取所有 body 和 params 中的字段名
    all_body_keys = set()
    all_params_keys = set()

    for case in cases:
        # 确保 body 是字典
        body = ensure_dict_field(case.get("body"), "body")
        # 确保 params 是字典
        params = ensure_dict_field(case.get("params"), "params")

        all_body_keys.update(body.keys())
        all_params_keys.update(params.keys())

    body_keys = sorted(list(all_body_keys))
    params_keys = sorted(list(all_params_keys))

    # 构建数据行
    rows = []
    for case in cases:
        # 确保 body 和 params 是字典
        body = ensure_dict_field(case.get("body"), "body")
        params = ensure_dict_field(case.get("params"), "params")

        row = {
            "用例ID": case.get("case_id", ""),
            "标题": case.get("title", ""),
            "方法": case.get("method", "GET"),
            "URL": case.get("url", ""),
        }

        # 添加 params 参数字段（GET请求）
        for key in params_keys:
            row[f"params_{key}"] = params.get(key, "")

        # 添加 body 参数字段（POST请求）
        for key in body_keys:
            row[f"body_{key}"] = body.get(key, "")

        row["断言"] = json.dumps(case.get("assert", {}), ensure_ascii=False)
        row["提取变量"] = json.dumps(case.get("extract", {}), ensure_ascii=False)

        rows.append(row)

    df = pd.DataFrame(rows)

    # 列顺序
    fixed_cols = ["用例ID", "标题", "方法", "URL"]
    param_cols = [f"params_{k}" for k in params_keys]
    body_cols = [f"body_{k}" for k in body_keys]
    other_cols = ["断言", "提取变量"]

    cols = fixed_cols + param_cols + body_cols + other_cols
    cols = [c for c in cols if c in df.columns]
    df = df[cols]

    with pd.ExcelWriter(full_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="接口用例", index=False)

    try:
        from fix_excel import fix_excel_format
        fix_excel_format(full_path)
    except:
        pass

    print(f"✅ 接口用例Excel导出成功：{full_path}")
    return full_path


def export_pytest_file(cases: List[Dict], project_name: str, module_name: str) -> str:
    """
    生成可直接运行的Pytest脚本
    支持：params（GET）和 body（POST）两种参数方式
    """
    if not cases:
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"test_{clean_name(module_name)}_{timestamp}.py"
    filepath = os.path.join(data_folder_path, filename)

    # 预处理 cases，确保 body 和 params 是字典
    clean_cases = []
    for case in cases:
        clean_case = case.copy()
        clean_case["body"] = ensure_dict_field(case.get("body"), "body")
        clean_case["params"] = ensure_dict_field(case.get("params"), "params")
        clean_cases.append(clean_case)

    cases_json = json.dumps(clean_cases, ensure_ascii=False, indent=2)

    pytest_code = f'''"""
自动生成的接口自动化测试脚本
项目：{project_name}
模块：{module_name}
生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

import pytest
import requests
import json
from typing import Dict, Any

BASE_URL = "http://localhost:8080"  # TODO: 修改为实际接口地址
session = requests.Session()


def get_nested_value(data: Dict, path: str) -> Any:
    """根据路径获取嵌套值"""
    keys = path.split(".")
    value = data
    for key in keys:
        if value is None:
            return None
        if isinstance(value, dict):
            value = value.get(key)
        elif isinstance(value, list):
            try:
                idx = int(key)
                value = value[idx] if idx < len(value) else None
            except ValueError:
                return None
        else:
            return None
    return value


TEST_CASES = {cases_json}


class Test{clean_name(module_name)}:

    @pytest.mark.parametrize("case", TEST_CASES)
    def test_api(self, case):
        url = BASE_URL + case["url"]
        method = case["method"].upper()
        headers = case.get("headers", {{"Content-Type": "application/json"}})
        body = case.get("body", {{}})
        params = case.get("params", {{}})

        if method == "GET":
            resp = session.get(url, headers=headers, params=params)
        elif method == "POST":
            resp = session.post(url, headers=headers, json=body, params=params)
        elif method == "PUT":
            resp = session.put(url, headers=headers, json=body, params=params)
        elif method == "DELETE":
            resp = session.delete(url, headers=headers, params=params)
        else:
            raise ValueError(f"不支持的方法: {{method}}")

        # 执行断言
        for assert_path, expected in case.get("assert", {{}}).items():
            if assert_path == "status_code":
                assert resp.status_code == expected, f"状态码错误: {{resp.status_code}} != {{expected}}"
            else:
                actual = get_nested_value(resp.json(), assert_path)
                assert actual == expected, f"{{assert_path}}: {{actual}} != {{expected}}"

        # 提取变量（供后续接口使用）
        for var_name, path in case.get("extract", {{}}).items():
            value = get_nested_value(resp.json(), path)
            setattr(self, var_name, value)
            print(f"✅ 提取变量: {{var_name}} = {{value}}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(pytest_code)

    print(f"✅ Pytest脚本生成成功：{filepath}")
    return filepath


def generate_api_test_full(project_name: str, module_name: str, test_type: str = "",
                           num: int = 10, business_rules: str = "") -> Dict:
    """
    一站式生成接口测试用例
    返回：{"cases": 用例列表, "excel_path": Excel文件路径, "pytest_path": Pytest脚本路径}
    """
    result = {
        "cases": [],
        "excel_path": None,
        "pytest_path": None
    }

    cases = generate_api_test_cases(project_name, module_name, test_type, num, business_rules)
    result["cases"] = cases

    if not cases:
        return result

    result["excel_path"] = export_api_excel(cases, project_name, module_name, test_type)
    result["pytest_path"] = export_pytest_file(cases, project_name, module_name)

    return result


if __name__ == "__main__":
    project = input("项目名称：")
    module = input("模块名称：")
    test_type = input("测试类型（回车=全类型）：")
    num = int(input("数量（1-40）："))
    rules = input("业务规则（可选）：")

    mode = input("模式（1=手工用例，2=接口用例）：")
    if mode == "2":
        result = generate_api_test_full(project, module, test_type, num, rules)
        print(f"✅ 生成 {len(result['cases'])} 条接口用例")
        print(f"   Excel: {result['excel_path']}")
        print(f"   Pytest: {result['pytest_path']}")
    else:
        cases = generate_test_cases(project, module, test_type, num, rules)
        if cases:
            filepath = export_excel(cases, project, module, test_type)
            print(f"✅ 生成 {len(cases)} 条用例 → {filepath}")