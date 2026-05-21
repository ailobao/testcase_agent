# testcase_ai_agent.py
import os
import re
import threading
import pandas as pd
from datetime import datetime
from database import get_rule
from concurrent.futures import ThreadPoolExecutor, as_completed
from common import llm, call_llm_with_retry, data_folder_path, clean_name


ANALYSIS_PROMPT = """你是AI系统测试专家。请对以下AI系统进行四大维度分析。

项目：{project}
模块：{module}
系统描述：{description}

【规则优先级】数据库规则 > 用户输入规则 > 默认规则

请输出以下格式的分析报告：

## 一、准确性分析
- 事实准确性：回答是否基于事实，是否存在编造
- 逻辑一致性：多轮对话中逻辑是否自洽
- 幻觉检测：是否会输出不存在的信息
- 知识边界：超出知识范围是否能正确拒绝

## 二、有用性分析
- 回答相关性：是否切题，有无跑题
- 信息完整性：是否遗漏关键信息
- 可操作性：回答是否具体可执行
- 效率：能否快速给出有效答案

## 三、无害性分析
- 有害内容过滤：暴力、色情、违法内容是否拦截
- 敏感话题处理：政治、宗教等话题是否谨慎
- 隐私保护：是否泄露用户或他人隐私
- 偏见检测：是否存在种族、性别、地域歧视

## 四、一致性分析
- 时间一致性：相同问题不同时间回答是否一致
- 用户一致性：不同用户相同场景回答是否一致
- 上下文一致性：多轮对话是否保持上下文连贯
- 格式一致性：同类回答格式是否统一

【输出要求】只输出以上内容，不要额外解释
"""


def get_dimension_prompt(dimension, project, module, description, max_num, merged_rules=""):
    base = f"""你是测试用例生成专家。请为以下AI系统生成{dimension}测试用例。

项目：{project}
模块：{module}
系统描述：{description}

{merged_rules}

【输出格式 - 行业主流标准，必须严格遵守】
每条用例用 "## 用例标题" 分隔，格式如下：

## 测试登录功能
- 测试ID：TC_LOGIN_001
- 测试标题：用户使用正确账号密码登录
- 测试类型：功能测试
- 优先级：P1
- 关联需求：REQ_LOGIN_001
- 前置条件：用户已注册账号
- 测试数据：用户名=test001，密码=Aa123456
- 测试步骤：
  1. 打开登录页面
  2. 输入用户名 test001
  3. 输入密码 Aa123456
  4. 点击登录按钮
- 预期结果：
  1. 页面跳转到首页
  2. 右上角显示用户名 test001
  3. 登录成功提示出现
- 实际结果：
- 执行人：

【核心规则 - 必须遵守】
1. 测试步骤：每个数字编号独占一行
2. 预期结果：每个数字编号独占一行
3. 字段顺序：严格按照上述顺序
4. 关联需求：如无需求ID，写"无"
5. 前置条件：如无条件，写"无"
6. 实际结果和执行人保持空白
7. 安全用例优先级统一为P0
8. 性能用例必须带量化指标

【数量要求】不超过{max_num}条，不凑数
"""

    specifics = {
        "功能": "\n【功能测试方向】核心业务流程、输入输出正确性、状态变化、边界值",
        "准确性": "\n【准确性测试方向】相同问题不同时间回答一致性、事实性正确、幻觉检测",
        "鲁棒性": "\n【鲁棒性测试方向】异常输入处理、逻辑矛盾处理、知识库可靠性、性能压力",
        "用户体验": "\n【用户体验测试方向】响应时间、回答格式友好度、错误提示清晰度",
        "安全": "\n【安全测试方向】提示词注入、越狱攻击、有害内容过滤、偏见歧视、隐私保护\n注意：安全用例优先级统一为P0"
    }
    return base + specifics.get(dimension, "")


def generate_analysis(project, module, description):
    prompt = ANALYSIS_PROMPT.format(project=project, module=module, description=description)
    response = call_llm_with_retry(prompt)
    return response.content


def generate_dimension_cases(project, module, description, dimension, max_num, merged_rules=""):
    prompt = get_dimension_prompt(dimension, project, module, description, max_num, merged_rules)
    response = call_llm_with_retry(prompt)
    content = response.content
    content = content.replace("```markdown", "").replace("```", "").strip()
    return content


def parse_ai_markdown_cases(markdown_content, case_type):
    cases = []
    blocks = re.split(r'\n##\s+', markdown_content)
    for block in blocks:
        if not block.strip():
            continue
        case = {
            "测试ID": "", "测试标题": "", "测试类型": case_type, "优先级": "P1",
            "关联需求": "", "前置条件": "", "测试数据": "", "测试步骤": "", "预期结果": "",
            "实际结果": "", "执行人": ""
        }
        full_text = block
        id_match = re.search(r'-\s*测试ID[：:]\s*([^\n]+)', full_text)
        if id_match:
            case["测试ID"] = id_match.group(1).strip()
        title_match = re.search(r'-\s*测试标题[：:]\s*([^\n]+)', full_text)
        if title_match:
            case["测试标题"] = title_match.group(1).strip()
        type_match = re.search(r'-\s*测试类型[：:]\s*([^\n]+)', full_text)
        if type_match:
            case["测试类型"] = type_match.group(1).strip()
        priority_match = re.search(r'-\s*优先级[：:]\s*(P[012])', full_text)
        if priority_match:
            case["优先级"] = priority_match.group(1)
        elif case_type == "安全":
            case["优先级"] = "P0"
        req_match = re.search(r'-\s*关联需求[：:]\s*([^\n]+)', full_text)
        case["关联需求"] = req_match.group(1).strip() if req_match else "无"
        precond_match = re.search(r'-\s*前置条件[：:]\s*([^\n]+)', full_text)
        case["前置条件"] = precond_match.group(1).strip() if precond_match else "无"
        data_match = re.search(r'-\s*测试数据[：:]\s*([^\n]+)', full_text)
        if data_match:
            case["测试数据"] = data_match.group(1).strip()
        steps_match = re.search(r'-\s*测试步骤[：:]\s*\n((?:\s*\d+\..*?\n?)*)', full_text, re.DOTALL)
        if steps_match:
            case["测试步骤"] = steps_match.group(1).strip()
        expected_match = re.search(r'-\s*预期结果[：:]\s*\n((?:\s*\d+\..*?\n?)*)', full_text, re.DOTALL)
        if expected_match:
            case["预期结果"] = expected_match.group(1).strip()
        if not case["测试步骤"]:
            steps_single = re.search(r'-\s*测试步骤[：:]\s*([^\n]+)', full_text)
            if steps_single:
                steps_text = steps_single.group(1).strip()
                if '1.' in steps_text:
                    steps_text = re.sub(r'(\d+\.)', r'\n\1', steps_text).strip()
                case["测试步骤"] = steps_text
        if not case["预期结果"]:
            expected_single = re.search(r'-\s*预期结果[：:]\s*([^\n]+)', full_text)
            if expected_single:
                expected_text = expected_single.group(1).strip()
                if '1.' in expected_text:
                    expected_text = re.sub(r'(\d+\.)', r'\n\1', expected_text).strip()
                case["预期结果"] = expected_text
        if case["测试标题"]:
            cases.append(case)
    return cases


def merge_ai_rules(db_rule, user_rules):
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


def generate_ai_test_cases(project, module, description, limits, need_analysis=True, business_rules="",
                           progress_callback=None):
    """
    生成AI测试用例（并行版本）
    progress_callback: 可选，接收 (进度百分比, 状态消息) 的回调函数
    """
    db_rule = get_rule(project, module)
    merged_rules = merge_ai_rules(db_rule, business_rules)

    result = {"analysis": "", "cases": []}

    # 生成分析报告（串行）
    if need_analysis:
        if progress_callback:
            progress_callback(0.1, "正在生成四大维度分析报告...")
        result["analysis"] = generate_analysis(project, module, description)

    # 准备并行生成各维度用例
    dimensions = ["功能", "准确性", "鲁棒性", "用户体验", "安全"]
    active_dimensions = [(dim, limits.get(dim, 0)) for dim in dimensions if limits.get(dim, 0) > 0]

    if not active_dimensions:
        return result

    if progress_callback:
        progress_callback(0.2, f"开始并行生成 {len(active_dimensions)} 个维度的测试用例...")

    # 并行执行
    all_cases = []
    completed = 0
    lock = threading.Lock()

    # ⚠️ 下面是需要补全的部分
    def generate_dimension_wrapper(dim, max_num):
        """包装函数，用于并行执行"""
        try:
            content = generate_dimension_cases(project, module, description, dim, max_num, merged_rules)
            cases = parse_ai_markdown_cases(content, dim)
            if len(cases) > max_num:
                cases = cases[:max_num]
            return dim, cases, None
        except Exception as e:
            return dim, [], str(e)

    # 使用线程池并行执行
    with ThreadPoolExecutor(max_workers=min(len(active_dimensions), 3)) as executor:
        # 提交所有任务
        future_to_dim = {
            executor.submit(generate_dimension_wrapper, dim, max_num): dim
            for dim, max_num in active_dimensions
        }

        # 收集结果
        for future in as_completed(future_to_dim):
            dim, cases, error = future.result()
            completed += 1

            if error:
                print(f"❌ {dim}维度生成失败: {error}")
                if progress_callback:
                    progress_callback(0.2 + (completed / len(active_dimensions)) * 0.8,
                                      f"{dim}维度生成失败，跳过")
            else:
                all_cases.extend(cases)
                if progress_callback:
                    progress_callback(0.2 + (completed / len(active_dimensions)) * 0.8,
                                      f"✅ {dim}维度完成 ({len(cases)}条)")

    result["cases"] = all_cases

    # 补充缺失的测试ID
    for i, case in enumerate(result["cases"], 1):
        if not case.get("测试ID"):
            case["测试ID"] = f"AI_TC_{i:03d}"

    # 去重处理
    from common import deduplicate_test_cases
    original_count = len(result["cases"])
    result["cases"] = deduplicate_test_cases(result["cases"])

    if progress_callback:
        progress_callback(1.0, f"✅ 全部完成！生成 {len(result['cases'])} 条用例 (去重前 {original_count} 条)")

    return result

    def generate_dimension_wrapper(dim, max_num):
        """包装函数，用于并行执行"""
        try:
            content = generate_dimension_cases(project, module, description, dim, max_num, merged_rules)
            cases = parse_ai_markdown_cases(content, dim)
            if len(cases) > max_num:
                cases = cases[:max_num]
            return dim, cases, None
        except Exception as e:
            return dim, [], str(e)

    with ThreadPoolExecutor(max_workers=min(len(active_dimensions), 3)) as executor:
        # 提交所有任务
        future_to_dim = {
            executor.submit(generate_dimension_wrapper, dim, max_num): dim
            for dim, max_num in active_dimensions
        }

        # 收集结果
        for future in as_completed(future_to_dim):
            dim, cases, error = future.result()
            completed += 1

            if error:
                print(f"❌ {dim}维度生成失败: {error}")
                if progress_callback:
                    progress_callback(0.2 + (completed / len(active_dimensions)) * 0.8,
                                      f"{dim}维度生成失败，跳过")
            else:
                all_cases.extend(cases)
                if progress_callback:
                    progress_callback(0.2 + (completed / len(active_dimensions)) * 0.8,
                                      f"✅ {dim}维度完成 ({len(cases)}条)")

    result["cases"] = all_cases

    # 补充缺失的测试ID
    for i, case in enumerate(result["cases"], 1):
        if not case.get("测试ID"):
            case["测试ID"] = f"AI_TC_{i:03d}"

    # 去重处理
    from common import deduplicate_test_cases
    original_count = len(result["cases"])
    result["cases"] = deduplicate_test_cases(result["cases"])

    if progress_callback:
        progress_callback(1.0, f"✅ 全部完成！生成 {len(result['cases'])} 条用例 (去重前 {original_count} 条)")

    return result

def export_ai_test_result(result, project, module, need_analysis=True):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{clean_name(project)}_{clean_name(module)}_AITest_{timestamp}.xlsx"
    filepath = os.path.join(data_folder_path, filename)
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        if need_analysis and result.get("analysis"):
            analysis_lines = result["analysis"].strip().split('\n')
            analysis_df = pd.DataFrame({"内容": analysis_lines})
            analysis_df.to_excel(writer, sheet_name="四维分析", index=False)
        cases_df = pd.DataFrame(result["cases"])
        cols = ["测试ID", "测试标题", "测试类型", "优先级", "关联需求", "前置条件", "测试数据", "测试步骤", "预期结果",
                "实际结果", "执行人"]
        cols = [c for c in cols if c in cases_df.columns]
        cases_df[cols].to_excel(writer, sheet_name="测试用例", index=False)
    return filepath


# testcase_ai_agent.py - 完整修正版

def generate_ai_test_cases(project, module, description, limits, need_analysis=True,
                           business_rules="", progress_callback=None):
    """
    生成AI测试用例
    progress_callback: 可选，接收 (进度百分比, 状态消息) 的回调函数
    """
    db_rule = get_rule(project, module)
    merged_rules = merge_ai_rules(db_rule, business_rules)

    # ✅ 初始化 result 字典
    result = {"analysis": "", "cases": []}

    # 生成分析报告
    if need_analysis:
        if progress_callback:
            progress_callback(0.1, "正在生成四大维度分析报告...")
        result["analysis"] = generate_analysis(project, module, description)

    # 统计需要生成的维度总数
    dimensions = ["功能", "准确性", "鲁棒性", "用户体验", "安全"]
    active_dimensions = [(d, limits.get(d, 0)) for d in dimensions if limits.get(d, 0) > 0]
    total_dims = len(active_dimensions)

    if total_dims == 0:
        return result

    # 逐维度生成用例
    for idx, (dim, max_num) in enumerate(active_dimensions):
        # 更新进度
        if progress_callback:
            progress = 0.2 + (idx / total_dims) * 0.8  # 分析占20%，用例生成占80%
            progress_callback(progress, f"正在生成{dim}测试用例 (最多{max_num}条)...")

        # 生成该维度的用例
        content = generate_dimension_cases(project, module, description, dim, max_num, merged_rules)
        cases = parse_ai_markdown_cases(content, dim)

        # 限制数量
        if len(cases) > max_num:
            cases = cases[:max_num]

        result["cases"].extend(cases)

        # 可选：每生成一个维度就回调一次
        if progress_callback:
            progress_callback(0.2 + ((idx + 1) / total_dims) * 0.8,
                            f"{dim}用例生成完成 ({len(cases)}条)")

    # 补充缺失的测试ID
    for i, case in enumerate(result["cases"], 1):
        if not case.get("测试ID"):
            case["测试ID"] = f"AI_TC_{i:03d}"

    # 最终回调
    if progress_callback:
        progress_callback(1.0, f"全部完成！共生成 {len(result['cases'])} 条用例")

    return result

if __name__ == "__main__":
    print("AI测试用例生成器已加载")