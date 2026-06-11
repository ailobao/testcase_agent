"""
使用 DeepSeek 官方 API 优化提示词
"""

import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

# 加载 .env
load_dotenv()

# ======================
# DeepSeek 官方配置
# ======================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    print("❌ 请设置 DEEPSEEK_API_KEY 环境变量")
    print("   在 .env 文件中添加: DEEPSEEK_API_KEY=sk-xxx")
    sys.exit(1)

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)


def call_deepseek(prompt, model="deepseek-v4-pro", temperature=0.5):
    """调用 DeepSeek 官方 API"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=temperature
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        return None


def load_prompt_template(template_name):
    """从 prompts.yaml 加载提示词模板"""
    import yaml

    with open("prompts.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config.get("task_templates", {}).get(template_name, "")


def save_optimized_prompt(template_name, optimized_content):
    """保存优化后的提示词"""
    import yaml

    with open("prompts.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 备份原内容
    backup_file = f"prompts_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
    with open(backup_file, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, indent=2)
    print(f"✅ 已备份原提示词到: {backup_file}")

    # 更新模板
    if "task_templates" not in config:
        config["task_templates"] = {}
    config["task_templates"][template_name] = optimized_content

    # 保存
    with open("prompts.yaml", "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, indent=2)

    print(f"✅ 已更新提示词: {template_name}")


def analyze_problems(template_name, bad_cases, good_examples=""):
    """分析当前提示词的问题"""

    current_prompt = load_prompt_template(template_name)
    if not current_prompt:
        print(f"❌ 未找到模板: {template_name}")
        return

    print("=" * 80)
    print(f"🔍 分析提示词: {template_name}")
    print("=" * 80)

    analysis_prompt = f"""
你是提示词优化专家，擅长分析测试用例生成提示词的问题。

【当前提示词】
{current_prompt}

【生成的劣质用例示例】
{json.dumps(bad_cases, ensure_ascii=False, indent=2)}

【期望的优质用例示例】
{good_examples if good_examples else "（请根据你的专业知识判断）"}

请分析：
1. 当前提示词存在哪些问题导致生成了劣质用例？
2. 缺失了哪些关键约束？
3. 哪些表述不够清晰或容易被误解？
4. 输出格式约束是否足够强？

请输出分析结果（不要输出优化后的提示词）。
"""

    print("⏳ 正在分析问题...")
    analysis = call_deepseek(analysis_prompt)
    if analysis:
        print("\n📊 分析结果:\n")
        print(analysis)

    return analysis


def optimize_prompt(template_name, analysis, additional_requirements=""):
    """基于分析结果优化提示词"""

    current_prompt = load_prompt_template(template_name)

    optimization_prompt = f"""
你是提示词优化专家。请根据以下分析结果优化提示词。

【当前提示词】
{current_prompt}

【问题分析】
{analysis}

【额外要求】
{additional_requirements if additional_requirements else "无"}

【优化要求】
1. 保持原有的输出格式约束（只输出JSON数组）
2. 强化边界值要求（必须包含 min、mid、max）
3. 强化参数组合要求
4. 强化正向用例 extract 要求
5. 增加具体的示例
6. 使用更强的约束语言（如"必须"、"禁止"）

请直接输出优化后的完整提示词，不要输出解释。
"""

    print("⏳ 正在生成优化后的提示词...")
    optimized = call_deepseek(optimization_prompt, temperature=0.5)

    if optimized:
        print("\n✅ 优化后的提示词:\n")
        print("=" * 80)
        print(optimized)
        print("=" * 80)

        # 询问是否保存
        save = input("\n是否保存优化后的提示词？(y/n): ")
        if save.lower() == 'y':
            save_optimized_prompt(template_name, optimized)
            print("✅ 已保存，下次运行将使用新提示词")
    else:
        print("❌ 优化失败")


def main():
    print("=" * 80)
    print("🎯 DeepSeek 提示词优化工具")
    print("=" * 80)
    print()

    # 选择要优化的模板
    templates = [
        "api_case",
        "testpoint",
        "ai_test_case",
        "manual_case",
        "ai_analysis"
    ]

    print("可优化的模板:")
    for i, t in enumerate(templates, 1):
        print(f"  {i}. {t}")
    print()

    choice = input("请选择要优化的模板 (1-5): ")
    try:
        idx = int(choice) - 1
        template_name = templates[idx]
    except:
        print("❌ 无效选择")
        return

    print("\n请提供生成的劣质用例示例（JSON格式，至少2-3条）")
    print("示例输入:")
    print('''
[
    {
        "case_id": "TC_001",
        "title": "正向用例-测试",
        "body": {"name": "test"},
        "assert": {"status_code": 200}
    }
]
''')

    bad_cases_input = input("\n请输入劣质用例 (直接回车使用默认示例): ")

    if bad_cases_input.strip():
        try:
            bad_cases = json.loads(bad_cases_input)
        except:
            print("❌ JSON 解析失败，使用默认示例")
            bad_cases = [
                {
                    "case_id": "TC_001",
                    "title": "正向用例",
                    "body": {},
                    "assert": {"status_code": 200}
                }
            ]
    else:
        # 默认劣质用例示例
        bad_cases = [
            {
                "case_id": "TC_001",
                "title": "测试登录",
                "method": "POST",
                "body": {"username": "test", "password": "123"},
                "assert": {"status_code": 200}
            }
        ]
        print(f"使用默认示例: {json.dumps(bad_cases, ensure_ascii=False)}")

    # 分析问题
    analysis = analyze_problems(template_name, bad_cases)

    if not analysis:
        print("❌ 分析失败")
        return

    print("\n" + "=" * 80)
    continue_opt = input("\n是否继续优化提示词？(y/n): ")

    if continue_opt.lower() == 'y':
        additional = input("请输入额外要求 (直接回车跳过): ")
        optimize_prompt(template_name, analysis, additional)


if __name__ == "__main__":
    main()