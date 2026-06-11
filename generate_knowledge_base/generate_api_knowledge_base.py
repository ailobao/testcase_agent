import os
import sys
import json
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.config.settings import KNOWLEDGE_BASE_DIR

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../project_rules.db")


def get_all_rules():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT project_name, module_name, input_fields, required_fields, url_path, default_body, constraints, priority FROM project_rules ORDER BY project_name, module_name")
    rows = cursor.fetchall()
    conn.close()
    rules = []
    for row in rows:
        rule = {
            "project_name": row[0],
            "module_name": row[1],
            "input_fields": json.loads(row[2]) if row[2] else [],
            "required_fields": json.loads(row[3]) if row[3] else [],
            "url_path": row[4] or "",
            "default_body": json.loads(row[5]) if row[5] else {},
            "constraints": row[6] or "",
            "priority": row[7] or 1
        }
        rules.append(rule)
    return rules


def generate_markdown(rule):
    project = rule["project_name"]
    module = rule["module_name"]
    url_path = rule["url_path"]
    default_body = rule["default_body"]
    required_fields = rule["required_fields"]
    input_fields = rule["input_fields"]
    constraints = rule["constraints"]

    method = "POST"
    if "list" in url_path.lower() or "query" in url_path.lower() or "search" in url_path.lower():
        method = "GET"
    elif "delete" in module.lower() or "remove" in module.lower():
        method = "DELETE"
    elif "update" in module.lower() or "modify" in module.lower():
        method = "PUT"

    need_login = "是"
    if "login" in module.lower() or "captcha" in module.lower() or "验证码" in module:
        need_login = "否"

    param_rows = []
    all_fields = list(set(input_fields + required_fields))
    for field in all_fields:
        is_req = "是" if field in required_fields else "否"
        example = default_body.get(field, "")
        if isinstance(example, list):
            example = json.dumps(example, ensure_ascii=False)
        param_rows.append(f"| {field} | string | {is_req} | 说明 | {example} |")
    param_table = "\n".join(param_rows) if param_rows else "| 无参数 | - | - | - | - |"

    default_body_str = json.dumps(default_body, ensure_ascii=False, indent=2) if default_body else "{}"

    backtick = chr(96)
    if "login" in module.lower():
        success_resp = backtick * 3 + 'json\n{\n    "code": 200,\n    "msg": "操作成功",\n    "data": {"token": "xxx"}\n}\n' + backtick * 3
    elif "list" in module.lower() or "查询" in module:
        success_resp = backtick * 3 + 'json\n{\n    "code": 200,\n    "msg": "操作成功",\n    "data": {"total": 100, "list": []}\n}\n' + backtick * 3
    else:
        success_resp = backtick * 3 + 'json\n{\n    "code": 200,\n    "msg": "操作成功",\n    "data": {}\n}\n' + backtick * 3

    failure_resp = backtick * 3 + 'json\n{\n    "code": 400,\n    "msg": "参数错误"\n}\n' + backtick * 3

    rules_list = []
    if constraints:
        for line in constraints.split('\n'):
            if line.strip():
                rules_list.append("- " + line.strip())
    else:
        rules_list.append("- 无特殊规则")

    required_list = "\n".join(["- " + f for f in required_fields]) if required_fields else "- 无"
    optional_fields = [f for f in input_fields if f not in required_fields]
    optional_list = "\n".join(["- " + f for f in optional_fields]) if optional_fields else "- 无"

    content = f"""# {project} - {module} 模块

## 接口信息
| 属性 | 值 |
|------|-----|
| URL | {url_path} |
| 方法 | {method} |
| 需要登录 | {need_login} |

## 参数说明
| 参数名 | 类型 | 必填 | 说明 | 示例值 |
|--------|------|------|------|--------|
{param_table}

## 默认请求体示例
{backtick * 3}json
{default_body_str}
{backtick * 3}

## 返回格式
### 成功响应
{success_resp}

### 失败响应
{failure_resp}

## 业务规则
{chr(10).join(rules_list)}

## 必填参数
{required_list}

## 可选参数
{optional_list}

## 测试要点
### 正向用例
- 所有必填参数使用有效值，预期返回成功

### 反向用例
- 缺失必填参数，预期返回参数错误
- 必填参数为空字符串，预期返回参数错误
- Token 过期/错误/缺失，预期返回认证失败
- 参数值超出有效范围，预期返回参数错误

### 边界值
- 字符串参数：最小长度、最大长度、空字符串
- 数字参数：最小值、最大值、负数、0
"""
    return content


def main():
    print("=" * 60)
    print("从数据库生成 API 知识库文件")
    print("=" * 60)
    rules = get_all_rules()
    print(f"从数据库读取到 {len(rules)} 个模块")
    if not rules:
        print("没有找到任何规则")
        return
    api_dir = os.path.join(KNOWLEDGE_BASE_DIR, "api")
    os.makedirs(api_dir, exist_ok=True)
    print(f"目标目录: {api_dir}")
    generated = 0
    for rule in rules:
        project = rule["project_name"]
        module = rule["module_name"]
        filename = f"{project}_{module}.md"
        filename = filename.replace("\\", "_").replace("/", "_").replace(":", "_")
        filepath = os.path.join(api_dir, filename)
        content = generate_markdown(rule)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"生成: {filename}")
        generated += 1
    print("=" * 60)
    print(f"共生成 {generated} 个 API 知识库文件")
    print(f"保存位置: {api_dir}")


if __name__ == "__main__":
    main()