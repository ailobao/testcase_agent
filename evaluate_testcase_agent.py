"""
使用百炼 DeepSeek 评估测试用例生成智能体（适配新版格式）
支持前置条件、测试步骤、断言式预期结果的评估
"""

import os
import json
import re
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

from testcase_agent import generate_test_cases
from testcase_ai_agent import generate_ai_test_cases

load_dotenv()

# ======================
# 配置
# ======================

BAILIAN_CONFIG = {
    "api_key": os.getenv("DASHSCOPE_API_KEY"),
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "deepseek-v3",
}

JUDGE_LLM = ChatOpenAI(
    model=BAILIAN_CONFIG["model"],
    api_key=BAILIAN_CONFIG["api_key"],
    base_url=BAILIAN_CONFIG["base_url"],
    temperature=0,
    max_tokens=1500
)


# ======================
# 根据模块类型获取评估标准
# ======================
def get_evaluation_criteria(module_name, test_type):
    """根据模块名称和测试类型返回评估标准"""

    # 登录模块：不需要边界值，重点在功能+异常+安全
    if "登录" in module_name or "login" in module_name.lower():
        return {
            "required_scenarios": ["正常登录", "密码错误", "账号不存在", "验证码错误", "空值校验", "连续失败锁定"],
            "not_required": ["边界值测试", "用户名长度测试", "密码复杂度测试"],
            "expected_keywords": ["登录成功", "密码错误", "验证码错误", "账号格式不匹配", "账号不存在", "账号已锁定"],
            "weight": {
                "format_score": 0.10,
                "rule_compliance": 0.15,
                "completeness": 0.15,
                "data_reasonableness": 0.10,
                "scenario_coverage": 0.20,
                "executability": 0.10,
                "assertion_quality": 0.10,
                "step_clarity": 0.10
            }
        }

    # 注册模块：需要边界值
    elif "注册" in module_name or "register" in module_name.lower():
        return {
            "required_scenarios": ["正常注册", "边界值测试", "异常输入", "重复注册", "空值校验"],
            "not_required": [],
            "expected_keywords": ["注册成功", "用户名已存在", "手机号格式不正确", "密码强度不足", "两次密码不一致"],
            "weight": {
                "format_score": 0.10,
                "rule_compliance": 0.15,
                "completeness": 0.15,
                "data_reasonableness": 0.10,
                "scenario_coverage": 0.20,
                "executability": 0.10,
                "assertion_quality": 0.10,
                "step_clarity": 0.10
            }
        }

    # 搜索模块：需要边界值
    elif "搜索" in module_name or "search" in module_name.lower():
        return {
            "required_scenarios": ["正常搜索", "边界值（长度）", "空搜索", "无结果", "特殊字符"],
            "not_required": [],
            "expected_keywords": ["有搜索结果", "暂无相关商品", "请输入搜索关键词"],
            "weight": {
                "format_score": 0.10,
                "rule_compliance": 0.15,
                "completeness": 0.15,
                "data_reasonableness": 0.10,
                "scenario_coverage": 0.20,
                "executability": 0.10,
                "assertion_quality": 0.10,
                "step_clarity": 0.10
            }
        }

    # 购物车模块
    elif "购物车" in module_name or "cart" in module_name.lower():
        return {
            "required_scenarios": ["添加商品", "修改数量", "删除商品", "库存不足", "未登录添加"],
            "not_required": [],
            "expected_keywords": ["添加成功", "修改成功", "删除成功", "库存不足", "请先登录"],
            "weight": {
                "format_score": 0.10,
                "rule_compliance": 0.15,
                "completeness": 0.15,
                "data_reasonableness": 0.10,
                "scenario_coverage": 0.20,
                "executability": 0.10,
                "assertion_quality": 0.10,
                "step_clarity": 0.10
            }
        }

    # 默认：通用标准
    else:
        return {
            "required_scenarios": ["正常流程", "异常流程", "边界值"],
            "not_required": [],
            "expected_keywords": ["操作成功", "操作失败", "参数错误"],
            "weight": {
                "format_score": 0.10,
                "rule_compliance": 0.15,
                "completeness": 0.15,
                "data_reasonableness": 0.10,
                "scenario_coverage": 0.20,
                "executability": 0.10,
                "assertion_quality": 0.10,
                "step_clarity": 0.10
            }
        }


def evaluate_testcases_with_deepseek(project, module, rules, generated_cases, test_type="传统"):
    """使用 DeepSeek 评估生成的测试用例质量（新版格式）"""

    # 获取该模块的评估标准
    criteria = get_evaluation_criteria(module, test_type)

    # 格式化生成的用例（展示更多细节）
    if isinstance(generated_cases, list):
        # 展示前5条用例的完整信息
        cases_to_show = []
        for case in generated_cases[:5]:
            case_copy = case.copy()
            # 截断过长的字段
            for key in ["测试步骤", "前置条件"]:
                if key in case_copy and len(case_copy.get(key, "")) > 200:
                    case_copy[key] = case_copy[key][:200] + "..."
            cases_to_show.append(case_copy)
        cases_preview = json.dumps(cases_to_show, ensure_ascii=False, indent=2)
    else:
        cases_preview = str(generated_cases)

    # 构建评估提示
    eval_prompt = f"""你是测试用例质量评估专家。请对以下生成的测试用例进行客观评分。

【测试需求】
项目名称：{project}
模块名称：{module}
业务规则：{rules if rules else "无特殊规则"}

【生成的测试用例（前5条预览）】
{cases_preview}

【重要说明】对于【{module}】模块：
- 应该覆盖的场景：{', '.join(criteria['required_scenarios'])}
- 不需要覆盖的场景：{', '.join(criteria['not_required']) if criteria['not_required'] else "无"}
- 预期结果应该使用的关键词：{', '.join(criteria['expected_keywords'])}

请从以下8个维度评分（每项0-10分）：

1. **格式正确性**：是否包含用例ID、标题、动态参数列、前置条件、测试步骤、预期结果、优先级
2. **规则遵循度**：是否正确遵守了业务规则（如验证码固定8888）
3. **用例完整性**：每条用例是否有完整的前置条件、测试步骤、预期结果
4. **数据合理性**：测试数据是否符合业务逻辑
5. **场景覆盖度**：【{module}模块】是否正确覆盖了应该测试的场景
6. **可执行性**：生成的用例能否直接用于数据驱动测试
7. **断言质量**：预期结果是否是简洁的断言关键词（如"登录成功"、"密码错误"），而非长句子描述
8. **步骤清晰度**：测试步骤是否使用数字序号换行（1. 2. 3.），步骤是否清晰可执行

请只输出以下JSON格式，不要有其他任何文字：
{{
    "format_score": 8,
    "rule_compliance": 9,
    "completeness": 8,
    "data_reasonableness": 8,
    "scenario_coverage": 8,
    "executability": 9,
    "assertion_quality": 9,
    "step_clarity": 9,
    "total_score": 68,
    "max_score": 80,
    "grade": "优秀",
    "strengths": ["格式规范", "规则遵循度高", "断言关键词简洁准确", "测试步骤换行清晰"],
    "weaknesses": [],
    "suggestions": "可以增加连续失败锁定测试"
}}"""

    try:
        response = JUDGE_LLM.invoke([HumanMessage(content=eval_prompt)])
        content = response.content.strip()

        # 解析JSON
        try:
            result = json.loads(content)
            if "format_score" in result:
                return result
        except json.JSONDecodeError:
            pass

        # 提取JSON代码块
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except:
                pass

        # 提取第一个完整JSON
        bracket_count = 0
        start = -1
        for i, char in enumerate(content):
            if char == '{':
                if bracket_count == 0:
                    start = i
                bracket_count += 1
            elif char == '}':
                bracket_count -= 1
                if bracket_count == 0 and start != -1:
                    try:
                        return json.loads(content[start:i+1])
                    except:
                        break

        # 默认返回
        return {
            "format_score": 5,
            "rule_compliance": 5,
            "completeness": 5,
            "data_reasonableness": 5,
            "scenario_coverage": 5,
            "executability": 5,
            "assertion_quality": 5,
            "step_clarity": 5,
            "total_score": 40,
            "max_score": 80,
            "grade": "待改进",
            "strengths": [],
            "weaknesses": ["评估解析失败"],
            "suggestions": "请检查模型输出"
        }

    except Exception as e:
        return {
            "format_score": 0,
            "rule_compliance": 0,
            "completeness": 0,
            "data_reasonableness": 0,
            "scenario_coverage": 0,
            "executability": 0,
            "assertion_quality": 0,
            "step_clarity": 0,
            "total_score": 0,
            "max_score": 80,
            "grade": "错误",
            "strengths": [],
            "weaknesses": [str(e)],
            "suggestions": "检查API配置"
        }


# ======================
# 测试用例集（更新规则以匹配新格式）
# ======================
TEST_SUITE = [
    {
        "name": "登录-功能异常测试",
        "type": "traditional",
        "project": "tpshop商城",
        "module": "登录",
        "test_type": "功能测试",
        "case_num": 8,
        "rules": """登录只需要用户名、密码、验证码，验证码固定为8888。
测试账号：13513531480/123456。
没有手机号登录、短信验证码。
用户名不存在提示'用户名不存在'，密码错误提示'密码错误'，验证码错误提示'验证码错误'。
连续5次密码错误锁定30分钟。
预期结果使用断言关键词：登录成功、密码错误、验证码错误、账号格式不匹配、账号不存在、账号已锁定""",
    },
    {
        "name": "注册-边界值测试",
        "type": "traditional",
        "project": "tpshop商城",
        "module": "注册",
        "test_type": "功能测试",
        "case_num": 10,
        "rules": """注册需要：用户名(6-20位字母数字)、密码(8-16位含字母+数字+特殊字符)、手机号(11位1开头)、验证码(6位固定888888)。
需要覆盖边界值：用户名5/6/20/21位，密码7/8/16/17位，手机号10/11/12位。
预期结果使用断言关键词：注册成功、用户名已存在、手机号格式不正确、密码强度不足、两次密码不一致""",
    },
    {
        "name": "搜索-功能测试",
        "type": "traditional",
        "project": "电商平台",
        "module": "搜索",
        "test_type": "功能测试",
        "case_num": 8,
        "rules": """搜索功能：支持关键词搜索，支持筛选条件（价格、品牌）。
预期结果使用断言关键词：有搜索结果、暂无相关商品、请输入搜索关键词""",
    },
    {
        "name": "购物车-功能测试",
        "type": "traditional",
        "project": "电商平台",
        "module": "购物车",
        "test_type": "功能测试",
        "case_num": 8,
        "rules": """购物车功能：添加商品、修改数量、删除商品。
预期结果使用断言关键词：添加成功、修改成功、删除成功、库存不足、请先登录""",
    },
]


# ======================
# 主程序
# ======================
def main():
    print("=" * 80)
    print("🎯 使用百炼 DeepSeek 评估测试用例智能体（新版格式）")
    print("=" * 80)
    print(f"📅 评估时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📋 评估维度：格式、规则遵循、完整性、数据合理性、场景覆盖、可执行性、断言质量、步骤清晰度")
    print("💡 特别说明：预期结果应为简洁断言关键词，测试步骤需换行显示")
    print("=" * 80)

    all_results = []

    for i, test in enumerate(TEST_SUITE, 1):
        print(f"\n{'=' * 70}")
        print(f"📝 测试 {i}: {test['name']}")
        print(f"   模块: {test['module']}")
        print(f"   用例数量: {test['case_num']}")
        print('=' * 70)

        print("⏳ 调用智能体生成测试用例...")

        try:
            cases = generate_test_cases(
                project_name=test['project'],
                module_name=test['module'],
                test_type=test.get('test_type', '功能测试'),
                num=test.get('case_num', 5),
                business_rules=test.get('rules', '')
            )
            print(f"✅ 生成了 {len(cases)} 条测试用例")

            if len(cases) == 0:
                print("⚠️ 未生成任何用例，跳过评估")
                continue

            # 展示用例结构
            if cases:
                print("\n📋 用例结构示例（第一条）:")
                first_case = cases[0]
                for key in ["用例ID", "标题", "预期结果", "前置条件"]:
                    if key in first_case:
                        val = first_case[key]
                        if len(str(val)) > 50:
                            val = str(val)[:50] + "..."
                        print(f"   {key}: {val}")
                if "测试步骤" in first_case:
                    steps = first_case["测试步骤"]
                    steps_preview = steps[:100] + "..." if len(steps) > 100 else steps
                    print(f"   测试步骤: {steps_preview}")

        except Exception as e:
            print(f"❌ 生成失败: {e}")
            continue

        print("\n⏳ DeepSeek 评估中...")
        eval_result = evaluate_testcases_with_deepseek(
            project=test['project'],
            module=test['module'],
            rules=test.get('rules', ''),
            generated_cases=cases,
            test_type="传统"
        )

        max_score = eval_result.get('max_score', 80)
        total_score = eval_result.get('total_score', 0)

        print(f"\n📊 评估结果（满分 {max_score}）:")
        print(f"   ├─ 格式正确性: {eval_result.get('format_score', 0)}/10")
        print(f"   ├─ 规则遵循度: {eval_result.get('rule_compliance', 0)}/10")
        print(f"   ├─ 用例完整性: {eval_result.get('completeness', 0)}/10")
        print(f"   ├─ 数据合理性: {eval_result.get('data_reasonableness', 0)}/10")
        print(f"   ├─ 场景覆盖度: {eval_result.get('scenario_coverage', 0)}/10")
        print(f"   ├─ 可执行性: {eval_result.get('executability', 0)}/10")
        print(f"   ├─ 断言质量: {eval_result.get('assertion_quality', 0)}/10")
        print(f"   ├─ 步骤清晰度: {eval_result.get('step_clarity', 0)}/10")
        print(f"   └─ 总分: {total_score}/{max_score}")

        # 计算百分比得分
        percent_score = (total_score / max_score) * 100
        print(f"\n🏆 得分率: {percent_score:.1f}% - {eval_result.get('grade', 'N/A')}")

        if eval_result.get('strengths'):
            print(f"\n✅ 优点: {', '.join(eval_result['strengths'])}")
        if eval_result.get('weaknesses'):
            print(f"⚠️ 缺点: {', '.join(eval_result['weaknesses'])}")
        if eval_result.get('suggestions'):
            print(f"💡 建议: {eval_result['suggestions']}")

        all_results.append({
            "test_name": test['name'],
            "module": test['module'],
            "cases_count": len(cases),
            "evaluation": eval_result,
            "percent_score": percent_score
        })

    # 输出汇总
    print("\n" + "=" * 80)
    print("📈 评估汇总报告")
    print("=" * 80)

    for result in all_results:
        eval_data = result['evaluation']
        max_score = eval_data.get('max_score', 80)
        print(f"\n📊 {result['test_name']}: {eval_data.get('total_score', 0)}/{max_score} ({result['percent_score']:.1f}%)")
        print(f"   ├─ 场景覆盖度: {eval_data.get('scenario_coverage', 0)}/10")
        print(f"   ├─ 断言质量: {eval_data.get('assertion_quality', 0)}/10")
        print(f"   └─ 步骤清晰度: {eval_data.get('step_clarity', 0)}/10")

    # 计算平均分
    if all_results:
        avg_score = sum(r['percent_score'] for r in all_results) / len(all_results)
        print(f"\n📈 平均得分率: {avg_score:.1f}%")

    # 保存报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "judge_model": BAILIAN_CONFIG["model"],
        "format_version": "2.0",
        "dimensions": ["格式正确性", "规则遵循度", "用例完整性", "数据合理性", "场景覆盖度", "可执行性", "断言质量", "步骤清晰度"],
        "results": all_results
    }

    with open("testcase_agent_evaluation_v3.json", "w", encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 详细评估报告已保存: testcase_agent_evaluation_v3.json")


if __name__ == "__main__":
    main()