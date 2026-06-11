# evaluation/evaluate_kdtx.py - 客达天下项目专用评估脚本
import os
import sys
import json
import re
import time
import logging
from datetime import datetime
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

# 修复 Windows GBK 编码问题（emoji 等字符）
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.agents.api_agent import APITestAgent
from src.tools.rule_manager import get_rule

load_dotenv()

# ======================
# 配置日志
# ======================
LOG_DIR = os.path.join(_project_root, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

log_filename = os.path.join(LOG_DIR, f"kdtx_evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ======================
# Judge 配置
# ======================
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "qwen3.7-plus")
JUDGE_API_KEY = os.getenv("JUDGE_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
JUDGE_BASE_URL = os.getenv("JUDGE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

judge_llm = ChatOpenAI(
    model=JUDGE_MODEL,
    api_key=JUDGE_API_KEY,
    base_url=JUDGE_BASE_URL,
    temperature=0,
    max_tokens=800
)


# ======================
# 客达天下项目模块列表（动态计算建议数量）
# ======================
def calculate_expected_count(module_name: str) -> int:
    """根据模块参数动态计算建议用例数量（上限30条）"""

    # 不同模块的正向测试点最多的参数有效值数量
    positive_map = {
        "新增课程": 4,  # 价格有4个有效值
        "新增合同": 3,  # 合同编号有3个有效值
        "登录": 1,  # 正向1条
        "生成验证码": 1,
        "查询课程列表": 1,
        "查询课程": 1,
        "修改课程": 1,
        "删除课程": 1,
        "合同上传": 1,
        "查询合同列表": 1,
        "删除合同": 1,
    }

    # 必填参数数量
    rule = get_rule("客达天下", module_name)
    if rule and rule.get("required_fields"):
        fields = rule["required_fields"]
        required_fields = fields if isinstance(fields, list) else json.loads(fields)
        required_count = len(required_fields)
    else:
        required_count = 0

    # Token异常固定4条
    token_count = 4

    # 参数缺失 = 必填参数数量
    missing_count = required_count

    # 参数为空 = 必填参数中的string类型数量
    empty_count = required_count

    # 格式错误（根据模块估算）
    format_map = {
        "新增课程": 3,  # 价格格式/名称超长/学科范围
        "新增合同": 4,  # 手机号/姓名/课程ID/合同编号
        "登录": 2,  # 用户名/密码
        "删除合同": 2,  # ID格式/ID不存在
    }
    format_count = format_map.get(module_name, 2)

    # 业务异常（根据模块估算）
    business_map = {
        "新增课程": 1,  # 课程已存在
        "新增合同": 2,  # 合同编号重复/课程不存在
        "登录": 1,  # 验证码错误
        "删除合同": 1,  # 合同不存在
    }
    business_count = business_map.get(module_name, 1)

    # 正向用例数量
    positive_count = positive_map.get(module_name, 1)

    # 总数量
    total = token_count + missing_count + empty_count + format_count + business_count + positive_count

    # 上限30条
    return min(total, 30)


# 模块列表（不预置数量，动态计算）
KDTX_MODULES = [
    {"name": "登录", "description": "用户登录功能"},
    {"name": "注册", "description": "用户注册功能"},
    {"name": "生成验证码", "description": "生成验证码图片"},
    {"name": "新增课程", "description": "新增课程管理"},
    {"name": "查询课程列表", "description": "查询课程列表"},
    {"name": "查询课程", "description": "查询单个课程详情"},
    {"name": "修改课程", "description": "修改课程信息"},
    {"name": "删除课程", "description": "删除课程"},
    {"name": "合同上传", "description": "上传合同文件"},
    {"name": "新增合同", "description": "新增合同"},
    {"name": "查询合同列表", "description": "查询合同列表"},
    {"name": "删除合同", "description": "删除合同"},
]

# ======================
# 评估维度配置
# ======================
DIMENSIONS = {
    "quantity": {"name": "数量达标率", "weight": 10, "desc": "实际生成数/要求数"},
    "fields": {"name": "字段完整性", "weight": 10, "desc": "case_id/title/method/url/body/assert"},
    "assert": {"name": "断言规范性", "weight": 10, "desc": "status_code + body.code + body.msg"},
    "scenario": {"name": "场景覆盖度", "weight": 10, "desc": "正向/反向/边界"},
    "extract": {"name": "提取变量", "weight": 10, "desc": "正向用例是否有extract"},
    "params": {"name": "参数正确性", "weight": 10, "desc": "字段名不能有中文"},
    "executable": {"name": "可执行性", "weight": 10, "desc": "字段完整+断言规范"},
    "url": {"name": "URL合理性", "weight": 10, "desc": "URL格式是否合理"}
}


def evaluate_by_judge(cases: List[Dict], module_name: str, required_num: int) -> Dict:
    """使用 Judge LLM 评估用例质量（默认 qwen3.7-plus，通过 JUDGE_MODEL 环境变量可切换）"""

    if not cases:
        return {
            "total_score": 0,
            "max_score": 80,
            "percent_score": 0,
            "grade": "待改进",
            "dimensions": {},
            "strengths": [],
            "weaknesses": [],
            "suggestions": "未生成任何用例，请检查模块配置"
        }

    case_sample = json.dumps(cases[:3], ensure_ascii=False, indent=2)
    total_count = len(cases)

    # 统计用例类型
    positive_count = sum(1 for c in cases if "正向" in c.get("title", "") or "成功" in c.get("title", ""))
    negative_count = sum(
        1 for c in cases if any(k in c.get("title", "") for k in ["缺失", "为空", "错误", "过期", "超长", "格式"]))
    token_count = sum(1 for c in cases if "Token" in c.get("title", ""))

    prompt = f"""你是测试用例质量评估专家。请评估以下接口测试用例的质量。

【模块】{module_name}
【要求数量】{required_num}条
【实际数量】{total_count}条
【正向用例数】{positive_count}
【反向用例数】{negative_count}
【Token用例数】{token_count}

【用例样例（前3条）】
{case_sample}

【评估维度】（每项0-10分）
1. 数量达标率：{total_count}/{required_num}，实际/要求比例
2. 字段完整性：检查每条用例是否有 case_id, title, method, url, body, assert
3. 断言规范性：检查 assert 是否包含 status_code, body.code, body.msg
4. 场景覆盖度：是否覆盖正向、反向、边界、Token异常
5. 提取变量：正向用例是否有 extract 字段
6. 参数正确性：字段名是否英文化，无中文
7. 可执行性：字段完整 + 断言规范
8. URL合理性：URL格式是否正确

【输出格式】只输出JSON，不要其他内容：
{{
    "dimensions": {{
        "quantity": {{"score": 0-10, "comment": "说明"}},
        "fields": {{"score": 0-10, "comment": "说明"}},
        "assert": {{"score": 0-10, "comment": "说明"}},
        "scenario": {{"score": 0-10, "comment": "说明"}},
        "extract": {{"score": 0-10, "comment": "说明"}},
        "params": {{"score": 0-10, "comment": "说明"}},
        "executable": {{"score": 0-10, "comment": "说明"}},
        "url": {{"score": 0-10, "comment": "说明"}}
    }},
    "strengths": ["优点1", "优点2"],
    "weaknesses": ["缺点1", "缺点2"],
    "suggestions": "改进建议"
}}"""

    try:
        response = judge_llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*$', '', content)

        result = json.loads(content)

        total_score = 0
        for key in DIMENSIONS.keys():
            if key in result.get("dimensions", {}):
                total_score += result["dimensions"][key].get("score", 0)

        result["total_score"] = total_score
        result["max_score"] = 80
        result["percent_score"] = round(total_score / 80 * 100, 1)

        if result["percent_score"] >= 90:
            result["grade"] = "优秀 ⭐⭐⭐"
        elif result["percent_score"] >= 75:
            result["grade"] = "良好 ⭐⭐"
        elif result["percent_score"] >= 60:
            result["grade"] = "及格 ⭐"
        else:
            result["grade"] = "待改进"

        return result

    except Exception as e:
        logger.error(f"Judge 评估失败: {e}")
        return {
            "total_score": 0,
            "max_score": 80,
            "percent_score": 0,
            "grade": "评估失败",
            "dimensions": {},
            "strengths": [],
            "weaknesses": [f"评估失败: {str(e)}"],
            "suggestions": f"请检查 {JUDGE_MODEL} API 配置"
        }


def evaluate_module(project_name: str, module_name: str, description: str) -> Dict:
    """评估单个模块"""
    logger.info(f"开始评估模块: {module_name}")

    # 动态计算建议数量
    required_num = calculate_expected_count(module_name)
    logger.info(f"模块 {module_name} 建议用例数: {required_num}")

    start_time = time.time()

    # 生成用例
    agent = APITestAgent()
    cases = agent.generate(project_name, module_name, "")
    cases = cases or []

    elapsed = time.time() - start_time

    # Judge 评估
    evaluation = evaluate_by_judge(cases, module_name, required_num)

    # 添加统计信息
    evaluation["cases_count"] = len(cases)
    evaluation["required_num"] = required_num
    evaluation["elapsed"] = round(elapsed, 2)
    evaluation["module_name"] = module_name
    evaluation["description"] = description

    # 统计用例类型
    evaluation["positive_count"] = sum(1 for c in cases if "正向" in c.get("title", "") or "成功" in c.get("title", ""))
    evaluation["negative_count"] = sum(
        1 for c in cases if any(k in c.get("title", "") for k in ["缺失", "为空", "错误", "过期", "超长"]))
    evaluation["token_count"] = sum(1 for c in cases if "Token" in c.get("title", ""))

    # 示例用例
    if cases:
        sample = cases[0].copy()
        if "body" in sample:
            sample["body"] = str(sample["body"])[:100]
        if "assert" in sample:
            sample["assert"] = str(sample["assert"])[:100]
        evaluation["sample_case"] = sample
    else:
        evaluation["sample_case"] = None

    return evaluation


def run_evaluation(project_name: str = "客达天下"):
    """运行完整评估"""
    print("=" * 80)
    print(f"🎯 {project_name} 接口测试用例智能体评估")
    print("=" * 80)
    print(f"📅 评估时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 测试模块数: {len(KDTX_MODULES)}")
    print(f"📋 评估维度: 数量达标率、字段完整性、断言规范性、场景覆盖度、提取变量、参数正确性、可执行性、URL合理性")
    print("=" * 80)
    print()

    results = []

    for i, module in enumerate(KDTX_MODULES, 1):
        print(f"{'=' * 70}")
        print(f"📝 [{i}/{len(KDTX_MODULES)}] {module['name']}")
        print(f"   描述: {module['description']}")
        print(f"=" * 70)

        evaluation = evaluate_module(project_name, module["name"], module["description"])
        results.append(evaluation)

        # 打印结果
        print(f"   ⏱️ 耗时: {evaluation['elapsed']}秒")
        print(f"   📊 生成: {evaluation['cases_count']}条用例")
        print(f"   📋 要求: {evaluation['required_num']}条")
        print(
            f"   📈 正向: {evaluation.get('positive_count', 0)}条, 反向: {evaluation.get('negative_count', 0)}条, Token: {evaluation.get('token_count', 0)}条")
        print(f"   🏆 得分: {evaluation['percent_score']}% ({evaluation['grade']})")

        if evaluation.get('strengths'):
            print(f"   ✅ 优点: {', '.join(evaluation['strengths'][:2])}")
        if evaluation.get('weaknesses'):
            print(f"   ⚠️ 缺点: {', '.join(evaluation['weaknesses'][:2])}")

        if evaluation.get('sample_case'):
            sample = evaluation['sample_case']
            print(f"   📋 示例: {sample.get('case_id', '')} - {sample.get('title', '')}")

        print()

    # 汇总报告
    avg_score = sum(r['percent_score'] for r in results) / len(results) if results else 0

    print("=" * 80)
    print("📈 汇总报告")
    print("=" * 80)
    print()
    print(f"📊 执行统计:")
    print(f"   成功: {len(results)}/{len(KDTX_MODULES)}")
    print(f"   平均综合得分: {avg_score:.1f}%")
    print()

    print("📊 各模块得分:")
    print("-" * 60)
    for r in results:
        print(f"   {r['module_name']:12}: {r['percent_score']:5.1f}% ({r['grade']})")
    print()

    # 评级
    if avg_score >= 90:
        grade = "🏆 优秀 - 接口用例质量高，可直接使用"
    elif avg_score >= 75:
        grade = "✅ 良好 - 基本可用，建议优化"
    elif avg_score >= 60:
        grade = "⚠️ 及格 - 需要改进"
    else:
        grade = "❌ 待改进 - 存在较多问题"

    print(f"🎯 综合评级: {grade}")
    print()

    # 保存报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "project": project_name,
        "total_modules": len(KDTX_MODULES),
        "successful_count": len(results),
        "avg_score": avg_score,
        "results": results
    }

    report_file = f"kdtx_evaluation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"✅ 详细报告已保存: {report_file}")
    print(f"✅ 日志已保存: {log_filename}")
    print("=" * 80)

    return report


def evaluate_single_module(project_name: str, module_name: str):
    """评估单个模块"""
    print("=" * 80)
    print(f"🎯 评估模块: {module_name}")
    print("=" * 80)

    evaluation = evaluate_module(project_name, module_name, "")

    print(f"📊 生成: {evaluation['cases_count']}条用例")
    print(f"📋 要求: {evaluation['required_num']}条")
    print(f"🏆 得分: {evaluation['percent_score']}% ({evaluation['grade']})")
    print(f"✅ 优点: {', '.join(evaluation.get('strengths', []))}")
    print(f"⚠️ 缺点: {', '.join(evaluation.get('weaknesses', []))}")
    print(f"💡 建议: {evaluation.get('suggestions', '')}")

    return evaluation


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='客达天下项目评估脚本')
    parser.add_argument('--module', '-m', type=str, help='指定模块名称')

    args = parser.parse_args()

    if args.module:
        evaluate_single_module("客达天下", args.module)
    else:
        run_evaluation("客达天下")