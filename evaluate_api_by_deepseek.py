"""
使用 DeepSeek 评估接口自动化测试用例质量
评估维度：字段完整性、断言规范性、场景覆盖度、提取变量、参数正确性、可执行性、URL合理性
"""

import os
import json
import re
import time
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

from testcase_agent import generate_api_test_full

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
    max_tokens=2000
)


# ======================
# 评估函数
# ======================
def evaluate_api_with_deepseek(project, module, rules, cases, expected_num):
    """使用 DeepSeek 评估接口测试用例质量"""

    if not cases:
        return {
            "total_score": 0,
            "max_score": 100,
            "grade": "失败",
            "error": "没有生成任何用例"
        }

    # 准备预览数据（最多展示10条）
    cases_preview = []
    for case in cases[:10]:
        preview_case = {
            "case_id": case.get("case_id"),
            "title": case.get("title"),
            "method": case.get("method"),
            "url": case.get("url"),
            "body": case.get("body", {}),
            "params": case.get("params", {}),
            "assert": case.get("assert", {}),
            "extract": case.get("extract", {})
        }
        cases_preview.append(preview_case)

    cases_json = json.dumps(cases_preview, ensure_ascii=False, indent=2)
    total = len(cases)

    eval_prompt = f"""你是接口测试用例质量评估专家。请对以下生成的接口测试用例进行客观评分。

【测试需求】
项目名称：{project}
模块名称：{module}
业务规则：{rules if rules else "无特殊规则"}
要求生成数量：{expected_num}条
实际生成数量：{total}条

【生成的接口用例（前{len(cases_preview)}条预览）】
{cases_json}

请从以下7个维度评分（每项0-10分）：

1. **数量达标率**：实际生成数量是否接近要求数量
2. **字段完整性**：每条用例是否包含 case_id, title, method, url, (body/params), assert
3. **断言规范性**：断言是否包含 status_code 和 body.code
4. **场景覆盖度**：是否覆盖正向、异常、边界场景
5. **提取变量**：正向用例是否正确提取了 token/session_id
6. **参数正确性**：字段名是否使用英文（不能有中文）
7. **可执行性**：用例能否直接用于 Pytest 脚本执行
8. **URL合理性**：URL 格式是否合理（以/开头，包含模块关键词）

请输出以下JSON格式，不要有其他文字：

{{
    "quantity_score": 10,
    "field_score": 10,
    "assert_score": 10,
    "scenario_score": 10,
    "extract_score": 10,
    "param_score": 10,
    "executable_score": 10,
    "url_score": 10,
    "total_score": 80,
    "max_score": 80,
    "grade": "优秀",
    "strengths": ["数量达标", "字段完整", "断言规范", "场景覆盖全面", "正向用例有extract", "参数英文化", "可执行性好", "URL合理"],
    "weaknesses": [],
    "suggestions": "无",
    "statistics": {{
        "total_cases": {total},
        "positive_count": 0,
        "negative_count": 0,
        "boundary_count": 0
    }}
}}"""

    try:
        response = JUDGE_LLM.invoke([HumanMessage(content=eval_prompt)])
        content = response.content.strip()

        # 清理 markdown 标记
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*$', '', content)
        content = content.strip()

        # 尝试解析 JSON
        result = json.loads(content)

        # 计算百分比得分
        total_score = result.get("total_score", 0)
        max_score = result.get("max_score", 80)
        result["percent_score"] = round((total_score / max_score) * 100, 1)

        return result

    except json.JSONDecodeError as e:
        print(f"   ⚠️ JSON解析失败，使用默认评分")
        print(f"   错误: {e}")
        print(f"   原始内容前500字符: {content[:500]}")

        # 降级评分
        return {
            "quantity_score": round(min(10, total / expected_num * 10), 1),
            "field_score": 5,
            "assert_score": 5,
            "scenario_score": 5,
            "extract_score": 5,
            "param_score": 5,
            "executable_score": 5,
            "url_score": 5,
            "total_score": 40,
            "max_score": 80,
            "percent_score": 50,
            "grade": "解析失败",
            "strengths": [],
            "weaknesses": ["DeepSeek评分解析失败，使用降级评分"],
            "suggestions": "检查用例格式",
            "statistics": {"total_cases": total}
        }
    except Exception as e:
        print(f"   ❌ 评估失败: {e}")
        return {
            "quantity_score": 0,
            "field_score": 0,
            "assert_score": 0,
            "scenario_score": 0,
            "extract_score": 0,
            "param_score": 0,
            "executable_score": 0,
            "url_score": 0,
            "total_score": 0,
            "max_score": 80,
            "percent_score": 0,
            "grade": "错误",
            "strengths": [],
            "weaknesses": [str(e)],
            "suggestions": "检查API配置",
            "statistics": {"total_cases": total}
        }


# ======================
# 测试用例集
# ======================
TEST_SUITE = [
    {"name": "【电商】登录模块", "project": "电商平台", "module": "登录", "case_num": 15,
     "rules": """登录接口：POST /api/login
参数：username(手机号/邮箱), password(6-20位), verify_code(4位数字，固定8888)
成功返回：{"code":0, "msg":"登录成功", "data":{"token":"xxx"}}
失败返回：{"code":1, "msg":"错误信息"}"""},

    {"name": "【电商】购物车模块", "project": "电商平台", "module": "购物车", "case_num": 12,
     "rules": """购物车接口：
- 添加：POST /api/cart/add，参数：goods_id, num
- 查询：GET /api/cart/list
- 修改：PUT /api/cart/update，参数：cart_id, num
- 删除：DELETE /api/cart/delete，参数：cart_id"""},

    {"name": "【旅游】酒店搜索", "project": "旅游平台", "module": "酒店搜索", "case_num": 12,
     "rules": """酒店搜索接口：GET /api/hotel/search
参数：city(城市), checkin(入住日期), checkout(离店日期), rooms(房间数), adults(成人数)"""},

    {"name": "【社交】发布动态", "project": "社交平台", "module": "发布动态", "case_num": 10,
     "rules": """发布动态接口：POST /api/feed/publish
参数：content(内容), images(图片列表), location(位置)"""},

    {"name": "【金融】查询余额", "project": "银行系统", "module": "余额查询", "case_num": 8,
     "rules": """余额查询接口：GET /api/balance
参数：account_id"""},
]


# ======================
# 主程序
# ======================
def main():
    print("=" * 80)
    print("🎯 接口测试用例智能体评估（DeepSeek 评分版）")
    print("=" * 80)
    print(f"📅 评估时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 测试模块数: {len(TEST_SUITE)}")
    print("📋 评估维度: 数量达标率、字段完整性、断言规范性、场景覆盖度、提取变量、参数正确性、可执行性、URL合理性")
    print("💡 使用模型: DeepSeek-V3")
    print("=" * 80)

    all_results = []

    for i, test in enumerate(TEST_SUITE, 1):
        print(f"\n{'=' * 70}")
        print(f"📝 [{i}/{len(TEST_SUITE)}] {test['name']}")
        print(f"   项目: {test['project']}")
        print(f"   模块: {test['module']}")
        print(f"   要求数量: {test['case_num']}")
        print('=' * 70)

        try:
            start_time = time.time()
            print("⏳ 调用智能体生成接口用例...")

            result = generate_api_test_full(
                project_name=test['project'],
                module_name=test['module'],
                test_type='功能测试',
                num=test['case_num'],
                business_rules=test.get('rules', '')
            )
            elapsed = time.time() - start_time

            cases = result.get("cases", [])
            print(f"   ⏱️ 耗时: {elapsed:.2f}秒")
            print(f"   📊 生成: {len(cases)}条用例")

            if len(cases) == 0:
                print(f"   ❌ 未生成任何用例，跳过评估")
                continue

            # 展示示例用例
            if cases:
                print(f"\n   📋 示例用例（第一条）:")
                sample = cases[0]
                print(f"      case_id: {sample.get('case_id')}")
                print(f"      title: {sample.get('title')}")
                print(f"      method: {sample.get('method')}")
                print(f"      url: {sample.get('url')}")
                if sample.get('params'):
                    print(f"      params: {json.dumps(sample.get('params'), ensure_ascii=False)[:80]}")
                if sample.get('body'):
                    print(f"      body: {json.dumps(sample.get('body'), ensure_ascii=False)[:80]}")

            # DeepSeek 评估
            print(f"\n⏳ DeepSeek 评估中...")
            eval_result = evaluate_api_with_deepseek(
                project=test['project'],
                module=test['module'],
                rules=test.get('rules', ''),
                cases=cases,
                expected_num=test['case_num']
            )

            # 输出评分
            print(f"\n   📊 评分详情:")
            print(f"      数量达标: {eval_result.get('quantity_score', 0)}/10")
            print(f"      字段完整: {eval_result.get('field_score', 0)}/10")
            print(f"      断言规范: {eval_result.get('assert_score', 0)}/10")
            print(f"      场景覆盖: {eval_result.get('scenario_score', 0)}/10")
            print(f"      提取变量: {eval_result.get('extract_score', 0)}/10")
            print(f"      参数正确: {eval_result.get('param_score', 0)}/10")
            print(f"      可执行性: {eval_result.get('executable_score', 0)}/10")
            print(f"      URL合理: {eval_result.get('url_score', 0)}/10")
            print(
                f"   🏆 总分: {eval_result.get('total_score', 0)}/{eval_result.get('max_score', 80)} ({eval_result.get('percent_score', 0)}%)")
            print(f"   {eval_result.get('grade', 'N/A')}")

            if eval_result.get('strengths'):
                print(f"   ✅ 优点: {', '.join(eval_result['strengths'][:3])}")
            if eval_result.get('weaknesses'):
                print(f"   ⚠️ 缺点: {', '.join(eval_result['weaknesses'][:3])}")

            all_results.append({
                "test_name": test['name'],
                "project": test['project'],
                "module": test['module'],
                "cases_count": len(cases),
                "evaluation": eval_result,
                "elapsed": elapsed
            })

        except Exception as e:
            print(f"   ❌ 生成失败: {e}")
            all_results.append({
                "test_name": test['name'],
                "project": test['project'],
                "module": test['module'],
                "cases_count": 0,
                "success": False,
                "error": str(e)
            })

    # ======================
    # 汇总报告
    # ======================
    print("\n" + "=" * 80)
    print("📈 汇总报告")
    print("=" * 80)

    successful = [r for r in all_results if r.get('cases_count', 0) > 0]

    if successful:
        avg_score = sum(r['evaluation'].get('percent_score', 0) for r in successful) / len(successful)

        print(f"\n📊 执行统计:")
        print(f"   成功: {len(successful)}/{len(all_results)}")
        print(f"   平均综合得分: {avg_score:.1f}%")

        print(f"\n📊 各模块得分:")
        print("-" * 60)
        for r in successful:
            score = r['evaluation'].get('percent_score', 0)
            grade = r['evaluation'].get('grade', 'N/A')
            print(f"   {r['test_name']}: {score:.1f}% ({grade})")

        # 综合评级
        if avg_score >= 90:
            print(f"\n🎯 综合评级: 🏆 优秀 - 接口用例质量高")
        elif avg_score >= 75:
            print(f"\n🎯 综合评级: ✅ 良好 - 基本可用")
        else:
            print(f"\n🎯 综合评级: ⚠️ 待改进")

    # 保存报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "model": BAILIAN_CONFIG["model"],
        "total_modules": len(all_results),
        "successful_count": len(successful),
        "avg_score": sum(r['evaluation'].get('percent_score', 0) for r in successful) / len(
            successful) if successful else 0,
        "results": all_results
    }

    with open("api_deepseek_evaluation.json", "w", encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 详细报告已保存: api_deepseek_evaluation.json")


if __name__ == "__main__":
    main()