# testcase_agent.py
import re
import os
import json
import pandas as pd
from common import llm, call_llm_with_retry, data_folder_path, clean_name, get_next_file_number
from database import get_rule

# ======================
# 模块参数配置（动态列）
# ======================
MODULE_FIELDS = {
    "登录": ["用户名", "密码", "验证码"],
    "购物车": ["商品ID", "数量", "是否勾选"],
    "下单": ["商品ID", "收货地址", "支付方式", "优惠券"],
    "搜索": ["关键词", "筛选条件", "排序方式"],
}

DEFAULT_FIELDS = ["参数1", "参数2", "参数3"]


def get_fields_by_module(module_name):
    """根据模块名获取参数列"""
    for key, fields in MODULE_FIELDS.items():
        if key in module_name:
            return fields
    return DEFAULT_FIELDS


def build_system_prompt(fields, num):
    """动态构建提示词 - 测试步骤强制换行，预期结果为断言关键词"""
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
测试步骤必须按以下格式，每步独占一行，以数字序号开头：

测试步骤：
  1. 第一步操作
  2. 第二步操作
  3. 第三步操作

❌ 错误写法（禁止）：
- 测试步骤：1.打开页面 2.输入账号 3.点击登录

✅ 正确写法：
- 测试步骤：
  1. 打开登录页面
  2. 输入用户名
  3. 点击登录按钮

【预期结果格式要求】
预期结果必须是简洁的断言关键词：

【登录模块关键词】
- 正常：登录成功
- 异常：密码错误、验证码错误、账号格式不匹配、账号不存在、账号已锁定

【注册模块关键词】
- 正常：注册成功
- 异常：用户名已存在、手机号格式不正确、密码强度不足、两次密码不一致

【搜索模块关键词】
- 正常：有搜索结果
- 异常：暂无相关商品、请输入搜索关键词

【购物车模块关键词】
- 正常：添加成功、修改成功、删除成功
- 异常：库存不足、请先登录

【下单/支付模块关键词】
- 正常：下单成功、支付成功
- 异常：库存不足、余额不足、支付失败、订单已超时

【数量要求】生成 {num} 条用例，覆盖正常流程和异常流程
"""


def parse_column_cases(markdown_content, fields):
    """解析列式格式用例 - 支持测试步骤换行"""
    cases = []
    blocks = re.split(r'\n##\s+', markdown_content)

    for block in blocks:
        if not block.strip():
            continue

        # 初始化所有字段
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

            # 解析新字段的键值对
            if line_stripped.startswith('-') and ('：' in line_stripped or ':' in line_stripped):
                # 保存上一个多行字段
                if current_key and current_value_lines:
                    case[current_key] = '\n'.join(current_value_lines).strip()
                    current_value_lines = []

                # 解析新字段
                if '：' in line_stripped:
                    key, value = line_stripped[2:].split('：', 1)
                else:
                    key, value = line_stripped[2:].split(':', 1)

                key = key.strip()
                value = value.strip()

                # 测试步骤和预期结果可能是多行字段
                if key in ["测试步骤", "预期结果"] and not value:
                    current_key = key
                    current_value_lines = []
                else:
                    current_key = None
                    if key in case:
                        case[key] = value

            # 处理多行内容（数字序号开头的行）
            elif current_key and line_stripped:
                # 匹配 1. xxx 或 1、xxx 格式
                if re.match(r'^\d+[\.、]', line_stripped):
                    current_value_lines.append(line_stripped)
                elif current_value_lines:
                    # 续行（同一段描述换行）
                    current_value_lines[-1] += " " + line_stripped

        # 保存最后一个多行字段
        if current_key and current_value_lines:
            case[current_key] = '\n'.join(current_value_lines).strip()

        # 只添加有效用例
        if case["标题"] or case["用例ID"]:
            # 设置默认值
            if not case["前置条件"]:
                case["前置条件"] = "无"
            if not case["测试步骤"]:
                case["测试步骤"] = "1. 执行测试操作"
            if not case["预期结果"]:
                case["预期结果"] = "操作成功"

            cases.append(case)

    return cases


def generate_test_cases(project_name, module_name, test_type="", num=10, business_rules=""):
    """生成测试用例"""
    # 获取动态字段
    fields = get_fields_by_module(module_name)

    db_rule = get_rule(project_name, module_name)

    # 构建规则
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

    # 动态构建提示词
    system_prompt = build_system_prompt(fields, num)

    prompt = system_prompt + f"""

【业务规则】
{merged_rules}

【需求】
{requirement}

请直接输出Markdown格式的用例："""

    response = call_llm_with_retry(prompt)
    markdown_content = response.content
    markdown_content = markdown_content.replace("```markdown", "").replace("```", "").strip()

    cases = parse_column_cases(markdown_content, fields)

    return cases


def export_excel(cases, project_name, module_name, test_type=""):
    """导出Excel"""
    if not cases:
        return None

    next_num = get_next_file_number()

    if test_type and test_type.strip():
        prefix = f"{clean_name(project_name)}_{clean_name(module_name)}_{clean_name(test_type)}"
    else:
        prefix = f"{clean_name(project_name)}_{clean_name(module_name)}"

    filename = f"{prefix}_{next_num:03d}.xlsx"
    full_path = os.path.join(data_folder_path, filename)

    # 列顺序：用例ID、标题、动态参数、前置条件、测试步骤、预期结果、实际结果、优先级
    fields = get_fields_by_module(module_name)
    cols = ["用例ID", "标题"] + fields + ["前置条件", "测试步骤", "预期结果", "实际结果", "优先级"]
    # 只保留存在的列
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

    cases = generate_test_cases(project, module, test_type, num, rules)
    if cases:
        filepath = export_excel(cases, project, module, test_type)
        print(f"✅ 生成 {len(cases)} 条用例 → {filepath}")