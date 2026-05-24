# testcase_ai_agent.py
import os
import re
import threading
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from database import get_rule
from common import (
    llm, call_llm_with_retry, data_folder_path, clean_name, deduplicate_test_cases,
    prompt_loader, OutputValidator, debug_log, validate_user_input, check_debug_mode
)


# ======================
# 分析报告生成（使用统一提示词）
# ======================
def generate_analysis(project, module, description):
    """生成四大维度分析报告"""
    prompt = prompt_loader.get_task_prompt(
        "ai_analysis",
        project=project,
        module=module,
        description=description
    )
    debug_log(f"分析报告提示词长度: {len(prompt)}")
    response = call_llm_with_retry(prompt)
    return response.content


# ======================
# 单个维度用例生成（使用统一提示词）
# ======================
def generate_dimension_cases(project, module, description, dimension, max_num, merged_rules=""):
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

    # 添加防御规则和正向/反向策略
    defense_rules = prompt_loader.get_defense_rules()
    case_strategy = prompt_loader.get_case_strategy()
    prompt = f"{prompt}\n\n{defense_rules}\n\n{case_strategy}"

    debug_log(f"{dimension}维度提示词长度: {len(prompt)}")

    response = call_llm_with_retry(prompt)
    content = response.content
    content = content.replace("```json", "").replace("```", "").strip()

    return content


# ======================
# 解析AI测试用例JSON
# ======================
def parse_ai_json_cases(json_content: str, case_type: str) -> List[Dict]:
    """解析AI测试用例的JSON格式内容"""
    cases = []

    # 使用输出校验器解析JSON
    is_valid, error_msg, data = OutputValidator.validate_json(json_content)

    if not is_valid:
        debug_log(f"JSON解析失败: {error_msg}")
        # 尝试兜底解析
        try:
            import json
            # 尝试提取JSON数组
            match = re.search(r'\[\s*\{.*?\}\s*\]', json_content, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                return cases
        except:
            return cases

    if isinstance(data, dict):
        data = [data]

    for item in data:
        case = {
            "测试ID": item.get("测试ID", ""),
            "测试标题": item.get("测试标题", ""),
            "测试类型": case_type,
            "优先级": item.get("优先级", "P2"),
            "关联需求": item.get("关联需求", "无"),
            "前置条件": item.get("前置条件", "无"),
            "测试数据": item.get("测试数据", ""),
            "测试步骤": item.get("测试步骤", ""),
            "预期结果": item.get("预期结果", ""),
            "实际结果": "",
            "执行人": ""
        }

        # 安全用例强制P0
        if case_type == "安全":
            case["优先级"] = "P0"

        # 正向用例P0（根据标题判断）
        if "正向" in case["测试标题"] or "正常" in case["测试标题"]:
            case["优先级"] = "P0"

        if case["测试标题"]:
            cases.append(case)

    return cases


def merge_ai_rules(db_rule, user_rules):
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


def generate_ai_test_cases(project, module, description, limits, need_analysis=True,
                           business_rules="", progress_callback=None):
    """
    生成AI测试用例（并行版本）
    progress_callback: 可选，接收 (进度百分比, 状态消息) 的回调函数
    """
    # 输入校验
    is_valid, msg = validate_user_input(business_rules)
    if not is_valid:
        debug_log(f"输入校验失败: {msg}")
        if progress_callback:
            progress_callback(1.0, f"输入校验失败: {msg}")
        return {"analysis": "", "cases": []}

    db_rule = get_rule(project, module)
    merged_rules = merge_ai_rules(db_rule, business_rules)

    result = {"analysis": "", "cases": []}

    # 生成分析报告（串行）
    if need_analysis:
        if progress_callback:
            progress_callback(0.1, "正在生成四大维度分析报告...")
        try:
            result["analysis"] = generate_analysis(project, module, description)
            debug_log("分析报告生成成功")
        except Exception as e:
            debug_log(f"分析报告生成失败: {e}")
            result["analysis"] = f"## 分析报告生成失败\n\n错误信息：{str(e)}"

    # 准备并行生成各维度用例
    dimensions = ["功能", "准确性", "鲁棒性", "用户体验", "安全"]
    active_dimensions = [(dim, limits.get(dim, 0)) for dim in dimensions if limits.get(dim, 0) > 0]

    if not active_dimensions:
        if progress_callback:
            progress_callback(1.0, "没有需要生成的用例维度")
        return result

    if progress_callback:
        progress_callback(0.2, f"开始并行生成 {len(active_dimensions)} 个维度的测试用例...")

    # 并行执行
    all_cases = []
    completed = 0
    lock = threading.Lock()

    def generate_dimension_wrapper(dim, max_num):
        """包装函数，用于并行执行"""
        try:
            content = generate_dimension_cases(project, module, description, dim, max_num, merged_rules)
            cases = parse_ai_json_cases(content, dim)
            if len(cases) > max_num:
                cases = cases[:max_num]
            return dim, cases, None
        except Exception as e:
            debug_log(f"{dim}维度生成异常: {e}")
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

    result["cases"] = all_cases

    # 补充缺失的测试ID
    for i, case in enumerate(result["cases"], 1):
        if not case.get("测试ID"):
            case["测试ID"] = f"AI_TC_{i:03d}"

    # 去重处理
    original_count = len(result["cases"])
    result["cases"] = deduplicate_test_cases(result["cases"])

    debug_log(f"去重: 原始 {original_count} 条 → 去重后 {len(result['cases'])} 条")

    if progress_callback:
        progress_callback(1.0, f"✅ 全部完成！生成 {len(result['cases'])} 条用例 (去重前 {original_count} 条)")

    return result


def export_ai_test_result(result, project, module, need_analysis=True):
    """导出AI测试结果为Excel"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{clean_name(project)}_{clean_name(module)}_AITest_{timestamp}.xlsx"
    filepath = os.path.join(data_folder_path, filename)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        if need_analysis and result.get("analysis"):
            analysis_lines = result["analysis"].strip().split('\n')
            analysis_df = pd.DataFrame({"内容": analysis_lines})
            analysis_df.to_excel(writer, sheet_name="四维分析", index=False)

        cases_df = pd.DataFrame(result["cases"])
        cols = ["测试ID", "测试标题", "测试类型", "优先级", "关联需求", "前置条件",
                "测试数据", "测试步骤", "预期结果", "实际结果", "执行人"]
        cols = [c for c in cols if c in cases_df.columns]
        if len(cols) > 0:
            cases_df[cols].to_excel(writer, sheet_name="测试用例", index=False)

    # 美化Excel
    try:
        from fix_excel import fix_excel_format
        fix_excel_format(filepath)
    except:
        pass

    print(f"✅ AI测试Excel导出成功：{filepath}")
    return filepath


if __name__ == "__main__":
    print("AI测试用例生成器已加载")