# testcase_agent.py - 纯业务逻辑版（从数据库读取配置）
"""
【规则优先级 - 从上到下执行】

0号铁律：AI 只输出 JSON 数组，不输出解释性文字、不开场白
规则1：代码生成优先（Token异常、参数缺失、参数为空）
规则2：AI 生成补充（正向用例、格式错误、业务异常）
规则3：用例编号连续（AI 从代码生成最大编号+1开始）
规则4：断言规范（POST类需 body.code + body.msg，GET类只需 status_code）
规则5：超长字符串用占位符，不实际生成
规则6：业务规则优先级（数据库规则 > 用户输入 > 默认）
规则7：口语化版输出 Apifox 兼容格式（用例标题/token/参数/msg/code）
"""
import re
import os
import json
import logging
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional
from common import (
    llm, call_llm_with_retry, data_folder_path, clean_name, get_next_file_number,
    prompt_loader, OutputValidator, validate_user_input
)
from database import get_rule

# ======================
# 配置日志
# ======================
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

log_filename = os.path.join(LOG_DIR, f"testcase_gen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# AI 思考日志
ai_logger = logging.getLogger("ai")
ai_logger.setLevel(logging.INFO)
ai_handler = logging.FileHandler(os.path.join(LOG_DIR, f"ai_thinking_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
                                 encoding='utf-8')
ai_handler.setFormatter(logging.Formatter('%(asctime)s\n%(message)s\n' + '=' * 80 + '\n'))
ai_logger.addHandler(ai_handler)
ai_logger.propagate = False

# ======================
# 默认请求头（全局通用）
# ======================
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": "Bearer {{token}}"
}

DEFAULT_FIELDS = ["param1", "param2", "param3"]


# ======================
# 辅助函数
# ======================
def get_max_case_id(cases: List[Dict]) -> int:
    """获取用例列表中的最大编号"""
    max_id = 0
    for case in cases:
        case_id = case.get("case_id", "")
        match = re.search(r'TC_(\d+)', case_id)
        if match:
            num = int(match.group(1))
            if num > max_id:
                max_id = num
    return max_id


def safe_json_parse(content: str) -> List[Dict]:
    """容错解析 JSON"""
    content = re.sub(r'```json\s*', '', content)
    content = re.sub(r'```\s*$', '', content)
    content = content.strip()

    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return [data]
        return data
    except:
        pass

    content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
    content = re.sub(r',\s*}', '}', content)
    content = re.sub(r',\s*]', ']', content)

    try:
        fixed = re.sub(r"(?<!\\)'", '"', content)
        data = json.loads(fixed)
        if isinstance(data, dict):
            return [data]
        return data
    except:
        pass

    try:
        match = re.search(r'\[\s*\{.*?\}\s*\]', content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            if isinstance(data, dict):
                return [data]
            return data
    except:
        pass

    try:
        fixed = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', content)
        data = json.loads(fixed)
        if isinstance(data, dict):
            return [data]
        return data
    except:
        raise ValueError(f"无法解析JSON: {content[:200]}")


def ensure_dict_field(value, field_name="body"):
    """确保字段是字典类型"""
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


def deduplicate_api_cases(cases):
    """接口用例去重"""
    if not cases:
        return cases

    seen = set()
    unique = []

    for case in cases:
        title = case.get("title", "")
        body = case.get("body", {})
        body_str = json.dumps(body, sort_keys=True) if body else ""
        key = f"{title}_{body_str[:100]}"

        if key not in seen:
            seen.add(key)
            unique.append(case)

    logger.info(f"去重: 原始 {len(cases)} 条 → 去重后 {len(unique)} 条")
    return unique


def filter_oversize_cases(cases: List[Dict], max_length: int = 100) -> List[Dict]:
    """过滤掉包含超长字符串的用例"""
    filtered = []
    for case in cases:
        body = case.get("body", {})
        is_oversize = False

        for key, value in body.items():
            if isinstance(value, str) and len(value) > max_length:
                logger.warning(f"跳过超长用例: {case.get('title')} - {key} 长度 {len(value)}")
                is_oversize = True
                break

        if not is_oversize:
            filtered.append(case)

    return filtered


def fix_case_id(cases: List[Dict], start_id: int) -> List[Dict]:
    """修复用例编号，从指定编号开始连续递增"""
    fixed_cases = []
    for i, case in enumerate(cases):
        case["case_id"] = f"TC_{start_id + i:03d}"
        fixed_cases.append(case)
    return fixed_cases


def get_method_from_url(url_path: str, module_name: str = "") -> str:
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


def normalize_assert(assert_dict: dict, method: str) -> dict:
    """根据请求方法规范化断言"""
    if not assert_dict:
        if method == "GET":
            return {"status_code": 200}
        else:
            return {"status_code": 200, "body.code": 200, "body.msg": "操作成功"}

    result = assert_dict.copy()

    if "status_code" not in result:
        result["status_code"] = 200

    if method in ["POST", "PUT", "DELETE"]:
        if "body.code" not in result:
            status_code = result.get("status_code", 200)
            if status_code == 200:
                result["body.code"] = 200
            elif status_code == 401:
                result["body.code"] = 401
            else:
                result["body.code"] = 500
        if "body.msg" not in result:
            if result.get("status_code") == 200:
                result["body.msg"] = "操作成功"
            elif result.get("status_code") == 401:
                result["body.msg"] = "认证失败，无法访问系统资源"
            else:
                result["body.msg"] = "操作失败"

    return result


# ======================
# 从数据库读取模块配置
# ======================
def get_module_config(project_name: str, module_name: str) -> Optional[Dict]:
    """从数据库读取模块配置"""
    rule = get_rule(project_name, module_name)
    if not rule:
        logger.warning(f"未找到模块配置: {project_name}/{module_name}")
        return None

    return {
        "input_fields": json.loads(rule.get("input_fields", "[]")) if rule.get("input_fields") else [],
        "required_fields": json.loads(rule.get("required_fields", "[]")) if rule.get("required_fields") else [],
        "url_path": rule.get("url_path", f"/api/{module_name}"),
        "default_body": json.loads(rule.get("default_body", "{}")) if rule.get("default_body") else {},
        "constraints": rule.get("constraints", ""),
    }


# ======================
# 代码生成：Token 异常用例（规则1：代码生成优先）
# ======================
def generate_token_error_cases(module_name: str, url_path: str, default_body: dict, start_id: int,
                               method: str = "POST") -> List[Dict]:
    """生成 Token 异常用例（代码生成）"""
    cases = []
    case_id = start_id

    error_scenarios = [
        ("Token过期", "Bearer expired_token_xxx", 401, "认证失败，无法访问系统资源"),
        ("Token错误", "Bearer wrong_token_12345", 401, "认证失败，无法访问系统资源"),
        ("Token为空", "", 401, "认证失败，无法访问系统资源"),
        ("缺失Token", None, 401, "认证失败，无法访问系统资源"),
    ]

    for title, token_value, status_code, msg in error_scenarios:
        headers = DEFAULT_HEADERS.copy()
        if token_value is None:
            headers.pop("Authorization", None)
        else:
            headers["Authorization"] = token_value

        assert_dict = normalize_assert({"status_code": status_code, "body.msg": msg}, method)

        cases.append({
            "case_id": f"TC_{case_id:03d}",
            "title": title,
            "method": method,
            "url": url_path,
            "headers": headers,
            "body": default_body.copy(),
            "assert": assert_dict,
            "extract": {},
            "priority": "P2"
        })
        case_id += 1

    logger.info(f"代码生成 Token 异常用例: {len(cases)} 条")
    return cases


def generate_missing_param_cases(url_path: str, default_body: dict, required_fields: List[str], start_id: int,
                                 method: str = "POST") -> List[Dict]:
    """生成参数缺失用例（代码生成）"""
    cases = []
    case_id = start_id

    for field in required_fields:
        body = default_body.copy()
        body.pop(field, None)

        assert_dict = normalize_assert({"status_code": 400, "body.msg": f"{field}不能为空"}, method)

        cases.append({
            "case_id": f"TC_{case_id:03d}",
            "title": f"缺失参数 {field}",
            "method": method,
            "url": url_path,
            "headers": DEFAULT_HEADERS.copy(),
            "body": body,
            "assert": assert_dict,
            "extract": {},
            "priority": "P2"
        })
        case_id += 1

    logger.info(f"代码生成参数缺失用例: {len(cases)} 条")
    return cases


def generate_empty_param_cases(url_path: str, default_body: dict, required_fields: List[str], start_id: int,
                               method: str = "POST") -> List[Dict]:
    """生成参数为空用例（代码生成）"""
    cases = []
    case_id = start_id

    for field in required_fields:
        body = default_body.copy()
        original_value = body.get(field)
        if isinstance(original_value, str):
            body[field] = ""
        elif isinstance(original_value, int):
            body[field] = 0
        else:
            body[field] = ""

        assert_dict = normalize_assert({"status_code": 400, "body.msg": f"{field}不能为空"}, method)

        cases.append({
            "case_id": f"TC_{case_id:03d}",
            "title": f"参数 {field} 为空",
            "method": method,
            "url": url_path,
            "headers": DEFAULT_HEADERS.copy(),
            "body": body,
            "assert": assert_dict,
            "extract": {},
            "priority": "P2"
        })
        case_id += 1

    logger.info(f"代码生成参数为空用例: {len(cases)} 条")
    return cases


# ======================
# AI 生成：正向用例 + 格式错误 + 业务异常（规则2：AI 生成补充）
# ======================
def generate_ai_cases(project_name: str, module_name: str, url_path: str,
                      default_body: dict, required_fields: List[str],
                      business_rules: str, start_id: int, max_num: int) -> List[Dict]:
    """AI 生成正向用例、格式错误、业务异常用例"""

    method = get_method_from_url(url_path, module_name)
    logger.info(f"开始调用 AI 生成用例，起始编号: TC_{start_id:03d}，请求方法: {method}")

    if method == "GET":
        assert_example = {"status_code": 200}
        assert_requirement = "GET请求只验证 status_code"
    else:
        assert_example = {"status_code": 200, "body.code": 200, "body.msg": "操作成功"}
        assert_requirement = "POST/PUT/DELETE 请求必须包含 status_code、body.code、body.msg"

    prompt = f"""你是接口自动化测试用例生成专家。

【规则优先级 - 必须严格遵守】
0号铁律：只输出 JSON 数组，不输出解释性文字、不开场白
规则1：正向用例只选1个参数遍历，不要为每个参数都生成
规则2：{assert_requirement}
规则3：正向用例必须包含 extract 字段提取 token 或 id
规则4：用例编号从 TC_{start_id:03d} 开始连续
规则5：超长字符串用占位符，不要实际生成

【项目】{project_name}
【模块】{module_name}
【接口地址】{url_path}
【请求方法】{method}

【业务规则】
{business_rules}

【默认请求体】
{json.dumps(default_body, ensure_ascii=False, indent=2)}

【必填参数】
{json.dumps(required_fields, ensure_ascii=False)}

【已经生成的用例】
以下用例已由代码生成，你不需要再生成：
- Token 异常用例
- 参数缺失用例
- 参数为空用例

【你需要生成的用例类型】
1. 正向用例（只选1个参数遍历，3-5条，P0，必须有extract）
2. 格式错误用例（每个类型1条，P2）
3. 业务规则异常用例（每个约束1条，P2）

【用例格式】
{{
    "case_id": "TC_XXX",
    "title": "用例标题",
    "method": "{method}",
    "url": "{url_path}",
    "headers": {{"Content-Type": "application/json", "Authorization": "Bearer {{token}}"}},
    "body": {{}},
    "assert": {json.dumps(assert_example, ensure_ascii=False)},
    "extract": {{"token": "body.data.token"}},
    "priority": "P0"
}}

请直接输出 JSON 数组："""

    ai_logger.info(f"【AI 提示词】\n{prompt}")
    logger.info(f"AI 提示词长度: {len(prompt)} 字符")

    try:
        response = call_llm_with_retry(prompt)
        content = response.content.strip()

        ai_logger.info(f"【AI 原始响应】\n{content}")
        logger.info(f"AI 原始响应长度: {len(content)} 字符")

        cases = safe_json_parse(content)

        for i, case in enumerate(cases):
            if not case.get("headers"):
                case["headers"] = DEFAULT_HEADERS.copy()
            if not case.get("method"):
                case["method"] = method
            if not case.get("url"):
                case["url"] = url_path
            case["body"] = ensure_dict_field(case.get("body"), "body")
            if "extract" not in case:
                if case.get("priority") == "P0" or "正向" in case.get("title", ""):
                    if "login" in url_path or "登录" in project_name:
                        case["extract"] = {"token": "body.data.token"}
                    elif "新增" in case.get("title", "") or "add" in url_path:
                        case["extract"] = {"id": "body.data.id"}
                    else:
                        case["extract"] = {}
                else:
                    case["extract"] = {}
            if "priority" not in case:
                case["priority"] = "P2"
            if "assert" in case:
                case["assert"] = normalize_assert(case["assert"], method)
            else:
                case["assert"] = normalize_assert({}, method)

        cases = fix_case_id(cases, start_id)
        cases = filter_oversize_cases(cases)

        ai_logger.info(f"【AI 解析结果】共 {len(cases)} 条用例")
        logger.info(f"AI 成功生成 {len(cases)} 条用例")
        return cases

    except Exception as e:
        logger.error(f"AI 生成失败: {e}")
        return []


# ======================
# 主函数：混合策略生成（专业化版）
# ======================
def generate_api_test_cases(project_name: str, module_name: str, test_type: str = "",
                            num: int = 10, business_rules: str = "") -> List[Dict]:
    """混合策略生成接口测试用例（专业化版）"""
    is_valid, msg = validate_user_input(business_rules)
    if not is_valid:
        logger.error(f"输入校验失败: {msg}")
        return []

    config = get_module_config(project_name, module_name)
    if not config:
        logger.error(f"未找到模块配置: {project_name}/{module_name}")
        return []

    url_path = config["url_path"]
    default_body = config["default_body"]
    required_fields = config["required_fields"]
    db_constraints = config["constraints"]

    method = get_method_from_url(url_path, module_name)

    rules_list = []
    if db_constraints:
        rules_list.append(f"【数据库规则】{db_constraints}")
    if business_rules:
        rules_list.append(f"【用户规则】{business_rules}")
    merged_rules = "\n".join(rules_list) if rules_list else "无特殊规则"

    logger.info(f"开始生成 {module_name} 模块接口测试用例，目标数量: {num}")
    logger.info(f"项目: {project_name}, 模块: {module_name}")
    logger.info(f"URL: {url_path}, 方法: {method}")
    logger.info(f"必填参数: {required_fields}")

    all_cases = []
    case_id = 1
    code_count = 0
    ai_count = 0

    logger.info("步骤1: 代码生成 Token 异常用例...")
    token_cases = generate_token_error_cases(module_name, url_path, default_body, case_id, method)
    all_cases.extend(token_cases)
    code_count += len(token_cases)
    case_id = get_max_case_id(all_cases) + 1

    logger.info("步骤2: 代码生成参数缺失用例...")
    missing_cases = generate_missing_param_cases(url_path, default_body, required_fields, case_id, method)
    all_cases.extend(missing_cases)
    code_count += len(missing_cases)
    case_id = get_max_case_id(all_cases) + 1

    logger.info("步骤3: 代码生成参数为空用例...")
    empty_cases = generate_empty_param_cases(url_path, default_body, required_fields, case_id, method)
    all_cases.extend(empty_cases)
    code_count += len(empty_cases)
    case_id = get_max_case_id(all_cases) + 1

    logger.info("步骤4: AI 生成正向用例、格式错误、业务异常...")
    ai_max_num = max(1, num - len(all_cases))
    ai_cases = generate_ai_cases(project_name, module_name, url_path, default_body,
                                 required_fields, merged_rules, case_id, ai_max_num)
    ai_count = len(ai_cases)
    all_cases.extend(ai_cases)

    logger.info("步骤5: 去重处理...")
    all_cases = deduplicate_api_cases(all_cases)

    if len(all_cases) > num:
        all_cases = all_cases[:num]

    logger.info(f"生成完成！总计 {len(all_cases)} 条用例")
    logger.info(f"  - 代码生成: {code_count} 条")
    logger.info(f"  - AI 生成: {ai_count} 条")

    return all_cases


# ======================
# 专业化版导出
# ======================
def export_api_excel(cases: List[Dict], project_name: str, module_name: str, test_type: str = "") -> str:
    """导出专业化版Excel - 10列格式"""
    if not cases:
        return None

    next_num = get_next_file_number()
    prefix = f"{clean_name(project_name)}_{clean_name(module_name)}_API"
    if test_type and test_type.strip():
        prefix = f"{clean_name(project_name)}_{clean_name(module_name)}_{clean_name(test_type)}_API"

    filename = f"{prefix}_{next_num:03d}.xlsx"
    full_path = os.path.join(data_folder_path, filename)

    rows = []
    for case in cases:
        body = ensure_dict_field(case.get("body"), "body")
        priority = case.get("priority", "P2")

        title = case.get("title", "")
        if "Token" in title and ("过期" in title or "错误" in title or "空" in title or "缺失" in title):
            pre_condition = "无（Token异常场景）"
        else:
            pre_condition = "用户已登录，token有效"

        row = {
            "用例编号": case.get("case_id", ""),
            "用例标题": case.get("title", ""),
            "模块项目": project_name,
            "优先级": priority,
            "前置条件": pre_condition,
            "请求方法": case.get("method", "POST"),
            "URL": case.get("url", ""),
            "请求头": json.dumps(case.get("headers", {"Content-Type": "application/json"}), ensure_ascii=False),
            "请求体": json.dumps(body, ensure_ascii=False),
            "预期结果": json.dumps(case.get("assert", {}), ensure_ascii=False)
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    cols = ["用例编号", "用例标题", "模块项目", "优先级", "前置条件", "请求方法", "URL", "请求头", "请求体", "预期结果"]
    cols = [c for c in cols if c in df.columns]
    df = df[cols]

    with pd.ExcelWriter(full_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="接口用例", index=False)

    try:
        from fix_excel import fix_excel_format
        fix_excel_format(full_path)
    except:
        pass

    print(f"✅ 专业化版Excel导出成功：{full_path}")
    return full_path


def export_pytest_file(cases: List[Dict], project_name: str, module_name: str) -> str:
    """生成Pytest脚本"""
    if not cases:
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"test_{clean_name(module_name)}_{timestamp}.py"
    filepath = os.path.join(data_folder_path, filename)

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

BASE_URL = "http://localhost:8080"
session = requests.Session()


def get_nested_value(data: Dict, path: str) -> Any:
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

        for assert_path, expected in case.get("assert", {{}}).items():
            if assert_path == "status_code":
                assert resp.status_code == expected
            else:
                actual = get_nested_value(resp.json(), assert_path)
                assert actual == expected

        for var_name, path in case.get("extract", {{}}).items():
            value = get_nested_value(resp.json(), path)
            setattr(self, var_name, value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(pytest_code)

    print(f"✅ Pytest脚本生成成功：{filepath}")
    return filepath


def generate_api_test_full(project_name: str, module_name: str, test_type: str = "",
                           num: int = 10, business_rules: str = "") -> Dict:
    """一站式生成专业化版接口测试用例"""
    result = {"cases": [], "excel_path": None, "pytest_path": None}
    cases = generate_api_test_cases(project_name, module_name, test_type, num, business_rules)
    result["cases"] = cases
    if not cases:
        return result
    result["excel_path"] = export_api_excel(cases, project_name, module_name, test_type)
    result["pytest_path"] = export_pytest_file(cases, project_name, module_name)
    return result


# ======================
# 口语化版：Apifox 格式（规则7）
# ======================
def generate_api_test_full_human(project_name: str, module_name: str, test_type: str = "",
                                 num: int = 10, business_rules: str = "") -> Dict:
    """
    口语化版 - 生成 Apifox 兼容的数据驱动表格格式
    """
    is_valid, msg = validate_user_input(business_rules)
    if not is_valid:
        print(f"❌ 输入校验失败: {msg}")
        return {"cases": [], "excel_path": None, "pytest_path": None}

    db_rule = get_rule(project_name, module_name)
    config = get_module_config(project_name, module_name)

    rules_list = []
    if db_rule and db_rule.get('constraints'):
        rules_list.append(db_rule.get('constraints'))
    if business_rules:
        rules_list.append(business_rules)
    merged_rules = "\n".join(rules_list) if rules_list else business_rules

    url_path = config["url_path"] if config else f"/api/{module_name.lower().replace(' ', '_')}"
    method = get_method_from_url(url_path, module_name)

    default_body = config["default_body"] if config else {}

    # 获取参数列表
    param_names = list(default_body.keys()) if default_body else ["param1", "param2", "param3"]
    param_fields = "\n".join([f"- {p}: 参数值" for p in param_names])

    prompt = f"""你是接口测试用例生成专家。

【规则优先级 - 必须严格遵守】
0号铁律：只输出 JSON 数组，不输出解释性文字
规则7：输出 Apifox 兼容的数据驱动表格格式

【项目】{project_name}
【模块】{module_name}
【接口地址】{url_path}
【请求方法】{method}

【业务规则】
{merged_rules}

【参数说明】
- 用例标题: 简短描述（如：token过期、课程空字符、价格边界值）
- token: 登录依赖（正确token/Bearer过期token/Bearer错误token/空/缺失）
{param_fields}
- msg: 响应消息（断言校验）
- code: 业务状态码（断言校验，200=成功，401=认证失败）

【默认值】
{json.dumps(default_body, ensure_ascii=False, indent=2)}

【需要生成的测试数据】
1. Token 异常用例（4条）：
   - 用例标题: token过期，token=Bearer过期token，其他参数正确 → code=401, msg="认证失败，无法访问系统资源"
   - 用例标题: token错误，token=Bearer错误token，其他参数正确 → code=401, msg="认证失败，无法访问系统资源"
   - 用例标题: token为空，token=Bearer，其他参数正确 → code=401, msg="认证失败，无法访问系统资源"
   - 用例标题: token缺失，token不传，其他参数正确 → code=401, msg="认证失败，无法访问系统资源"

2. 正向用例（必须按参数边界值生成，起码1条）：
   - 分析哪个参数的正向测试点最多（通常是价格、金额、数量、ID等）
   - 找出该参数的有效边界值（如价格：0, 1, 999, 99999；课程ID：100, 101, 102）
   - 固定其他参数的正确值，只变化这个参数
   - **每个边界值生成一条独立的用例**
   - 数量 = 该参数的有效边界值数量（通常 3-5 条，必须多于 1 条）
   - 示例：
     - 用例标题: 价格边界值0，price=0 → code=200, msg="操作成功"
     - 用例标题: 价格边界值1，price=1 → code=200, msg="操作成功"
     - 用例标题: 价格边界值999，price=999 → code=200, msg="操作成功"
     - 用例标题: 价格边界值99999，price=99999 → code=200, msg="操作成功"
    
3. 参数异常用例：
   - 用例标题: 课程空字符，name为空 → code=400, msg="课程名称不能为空"
   - 用例标题: 课程超长，name=51字符 → code=400, msg="课程名称超出长度"
   - 用例标题: 价格为负数，price=-1 → code=400, msg="价格不能为负数"

【输出格式】JSON数组，每行是一个测试数据：

[
  {{
    "case_id": "TC_001",
    "用例标题": "token过期",
    "token": "Bearer过期token",
    {', '.join([f'"{p}": "示例值"' for p in param_names])},
    "msg": "认证失败，无法访问系统资源",
    "code": 401
  }}
]

【字段说明】
- case_id: 字符串
- 用例标题: 字符串
- token: 字符串
- {', '.join(param_names)}: 根据参数类型（字符串/数字）
- msg: 字符串
- code: 数字

请生成 {num} 条测试数据，直接输出 JSON 数组："""

    try:
        response = call_llm_with_retry(prompt)
        content = response.content.strip()

        cases = safe_json_parse(content)

        for i, case in enumerate(cases, 1):
            if not case.get("case_id"):
                case["case_id"] = f"TC_{i:03d}"

        excel_path = export_apifox_excel(cases, project_name, module_name, test_type, param_names)
        return {"cases": cases, "excel_path": excel_path, "pytest_path": None}

    except Exception as e:
        print(f"❌ 口语化版生成失败: {e}")
        return {"cases": [], "excel_path": None, "pytest_path": None}


def export_apifox_excel(cases: List[Dict], project_name: str, module_name: str,
                        test_type: str = "", param_names: List[str] = None) -> str:
    """导出 Apifox 兼容的 Excel 格式（含用例标题）"""
    if not cases:
        return None

    next_num = get_next_file_number()
    prefix = f"{clean_name(project_name)}_{clean_name(module_name)}_APIFOX"
    if test_type and test_type.strip():
        prefix = f"{clean_name(project_name)}_{clean_name(module_name)}_{clean_name(test_type)}_APIFOX"

    filename = f"{prefix}_{next_num:03d}.xlsx"
    full_path = os.path.join(data_folder_path, filename)

    if param_names is None:
        param_names = ["param1", "param2", "param3"]

    # Apifox 需要的列顺序：case_id, 用例标题, token, 参数..., msg, code
    cols = ["case_id", "用例标题", "token"] + param_names + ["msg", "code"]

    rows = []
    for case in cases:
        row = {}
        for col in cols:
            value = case.get(col, "")
            # 处理数字类型
            if col == "code" and isinstance(value, str):
                try:
                    value = int(value)
                except:
                    value = 500
            row[col] = value
        rows.append(row)

    df = pd.DataFrame(rows)
    # 只保留存在的列
    existing_cols = [c for c in cols if c in df.columns]
    df = df[existing_cols]

    with pd.ExcelWriter(full_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="测试数据", index=False)

    try:
        from fix_excel import fix_excel_format
        fix_excel_format(full_path)
    except:
        pass

    print(f"✅ Apifox 格式导出成功：{full_path}")
    return full_path


# ======================
# 手工用例和其他函数
# ======================
def build_system_prompt(fields, num):
    """动态构建提示词 - 手工用例用"""
    fields_example = "\n".join([f"- {f}：test_{f}_001" for f in fields])

    base_prompt = prompt_loader.get_task_prompt(
        "manual_case",
        project="{project}",
        module="{module}"
    )

    num_requirement = f"\n【数量要求】生成 {num} 条用例，覆盖正常流程和异常流程"

    return base_prompt + num_requirement


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
    is_valid, msg = validate_user_input(business_rules)
    if not is_valid:
        print(f"❌ 输入校验失败: {msg}")
        return []

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

【防御规则】
{prompt_loader.get_defense_rules()}

请直接输出Markdown格式的用例："""

    response = call_llm_with_retry(prompt)
    markdown_content = response.content
    markdown_content = markdown_content.replace("```markdown", "").replace("```", "").strip()

    is_valid, error_msg, cases = OutputValidator.validate_manual_case_format(markdown_content)
    if not is_valid:
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


if __name__ == "__main__":
    project = input("项目名称：")
    module = input("模块名称：")
    test_type = input("测试类型（回车=全类型）：")
    num = int(input("数量（1-40）："))
    rules = input("业务规则（可选）：")

    mode = input("模式（1=手工用例，2=专业化版，3=口语化版）：")
    if mode == "2":
        result = generate_api_test_full(project, module, test_type, num, rules)
        print(f"✅ 生成 {len(result['cases'])} 条专业化版用例")
    elif mode == "3":
        result = generate_api_test_full_human(project, module, test_type, num, rules)
        print(f"✅ 生成 {len(result['cases'])} 条口语化版用例")
    else:
        cases = generate_test_cases(project, module, test_type, num, rules)
        if cases:
            filepath = export_excel(cases, project, module, test_type)
            print(f"✅ 生成 {len(cases)} 条手工用例 → {filepath}")