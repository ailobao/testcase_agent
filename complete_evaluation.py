"""
完整评估脚本 - 支持 GET 请求的 params 和 POST 请求的 body
评估维度：数量达标率、字段完整性、断言规范性、场景覆盖度、提取变量、参数正确性、可执行性、URL合理性
"""

import os
import json
import time
from datetime import datetime
from typing import List, Dict, Any
from testcase_agent import generate_api_test_full

# ======================
# 评估函数
# ======================

def check_field_completeness(case: Dict) -> bool:
    """
    检查字段完整性
    根据请求方法决定检查 body 还是 params
    """
    method = case.get("method", "").upper()

    # 基础必需字段
    base_fields = ["case_id", "title", "method", "url", "assert"]

    # 根据方法决定参数字段
    if method == "GET":
        param_field = "params"
    else:
        param_field = "body"

    required_fields = base_fields + [param_field]

    for field in required_fields:
        if field not in case:
            return False
        # 对于 body/params，空对象也算有效（测试缺失参数的用例）
        if field in ["body", "params"]:
            continue
        if not case.get(field):
            return False
    return True


def check_assert_standard(case: Dict) -> bool:
    """检查断言规范性：是否包含 status_code 和 body.code"""
    assert_body = case.get("assert", {})
    return "status_code" in assert_body and "body.code" in assert_body


def check_param_correctness(case: Dict) -> bool:
    """检查参数正确性：body 或 params 中的字段名不能有中文"""
    import re

    # 检查 body
    body = case.get("body", {})
    for key in body.keys():
        if re.search(r'[\u4e00-\u9fff]', key):
            return False

    # 检查 params
    params = case.get("params", {})
    for key in params.keys():
        if re.search(r'[\u4e00-\u9fff]', key):
            return False

    return True


def check_executability(case: Dict) -> bool:
    """检查可执行性：字段完整且断言规范"""
    return check_field_completeness(case) and check_assert_standard(case)


def check_url_reasonableness(case: Dict, module_name: str) -> tuple:
    """检查 URL 合理性，返回 (是否合理, 问题描述)"""
    url = case.get("url", "")
    if not url:
        return False, "URL为空"

    if not url.startswith("/"):
        return False, f"URL应以/开头: {url}"

    # 检查是否包含常见的关键词
    module_keywords = module_name.lower().replace(" ", "")
    url_lower = url.lower()

    # 根据不同模块检查合理的关键词
    reasonable = True
    issues = []

    if "search" in module_keywords or "搜索" in module_name:
        if "search" not in url_lower and "query" not in url_lower:
            issues.append(f"搜索模块URL应包含search或query: {url}")
    elif "login" in module_keywords or "登录" in module_name:
        if "login" not in url_lower and "auth" not in url_lower:
            issues.append(f"登录模块URL应包含login或auth: {url}")
    elif "cart" in module_keywords or "购物车" in module_name:
        if "cart" not in url_lower:
            issues.append(f"购物车模块URL应包含cart: {url}")

    return len(issues) == 0, "; ".join(issues) if issues else ""


def evaluate_case(case: Dict, module_name: str) -> Dict:
    """评估单个用例"""
    method = case.get("method", "").upper()

    # 判断是否正向用例（body.code == 0）
    assert_body = case.get("assert", {})
    is_positive = assert_body.get("body.code") == 0

    return {
        "field_complete": check_field_completeness(case),
        "assert_standard": check_assert_standard(case),
        "param_correct": check_param_correctness(case),
        "executable": check_executability(case),
        "url_reasonable": check_url_reasonableness(case, module_name)[0],
        "is_positive": is_positive,
        "has_extract": bool(case.get("extract") and len(case.get("extract", {})) > 0)
    }


def evaluate_test_suite(cases: List[Dict], module_name: str, expected_num: int) -> Dict:
    """评估整个测试套件"""
    if not cases:
        return {
            "quantity_compliance": 0,
            "field_completeness": 0,
            "assert_standard": 0,
            "scenario_coverage": 0,
            "extract_variable": 0,
            "param_correctness": 0,
            "executability": 0,
            "url_reasonableness": 0,
            "total_score": 0,
            "max_score": 80,
            "details": {}
        }

    total = len(cases)

    # 1. 数量达标率
    quantity_compliance = min(100.0, (total / expected_num) * 100) if expected_num > 0 else 100.0

    # 2. 字段完整性
    field_complete_count = 0
    # 3. 断言规范性
    assert_standard_count = 0
    # 4. 参数正确性
    param_correct_count = 0
    # 5. 可执行性
    executable_count = 0
    # 6. URL合理性
    url_reasonable_count = 0

    # 场景统计
    positive_count = 0
    negative_count = 0
    boundary_count = 0
    positive_has_extract = 0

    # 字段详细统计
    field_status = {
        "case_id": {"present": 0, "non_empty": 0},
        "title": {"present": 0, "non_empty": 0},
        "method": {"present": 0, "non_empty": 0},
        "url": {"present": 0, "non_empty": 0},
        "body": {"present": 0, "non_empty": 0},
        "params": {"present": 0, "non_empty": 0},
        "assert": {"present": 0, "non_empty": 0},
    }

    for case in cases:
        # 字段完整性
        if check_field_completeness(case):
            field_complete_count += 1

        # 断言规范性
        if check_assert_standard(case):
            assert_standard_count += 1

        # 参数正确性
        if check_param_correctness(case):
            param_correct_count += 1

        # 可执行性
        if check_executability(case):
            executable_count += 1

        # URL合理性
        url_ok, _ = check_url_reasonableness(case, module_name)
        if url_ok:
            url_reasonable_count += 1

        # 场景统计
        assert_body = case.get("assert", {})
        title = case.get("title", "").lower()

        if assert_body.get("body.code") == 0:
            positive_count += 1
            if case.get("extract") and len(case.get("extract", {})) > 0:
                positive_has_extract += 1
        else:
            negative_count += 1

        if any(kw in title for kw in ["边界", "长度", "最大", "最小", "超长", "边界值", "limit", "max", "min"]):
            boundary_count += 1

        # 字段详细统计
        for field in field_status:
            if field in case:
                field_status[field]["present"] += 1
                if case.get(field):
                    field_status[field]["non_empty"] += 1

    # 计算得分（每项满分10分）
    field_completeness_score = (field_complete_count / total) * 10 if total > 0 else 0
    assert_standard_score = (assert_standard_count / total) * 10 if total > 0 else 0
    param_correctness_score = (param_correct_count / total) * 10 if total > 0 else 0
    executability_score = (executable_count / total) * 10 if total > 0 else 0
    url_reasonableness_score = (url_reasonable_count / total) * 10 if total > 0 else 0

    # 场景覆盖度评分（满分10分）
    scenario_score = 0
    if positive_count > 0:
        scenario_score += 4
    if negative_count > 0:
        scenario_score += 4
    if boundary_count > 0:
        scenario_score += 2

    # 提取变量评分（满分10分）
    extract_score = (positive_has_extract / positive_count) * 10 if positive_count > 0 else 10.0

    # 数量达标率转换为10分制
    quantity_score = quantity_compliance / 10

    # 总分（8个维度，各10分）
    total_score = (quantity_score + field_completeness_score + assert_standard_score +
                   scenario_score + extract_score + param_correctness_score +
                   executability_score + url_reasonableness_score)
    max_score = 80

    return {
        "quantity_compliance": round(quantity_score, 1),
        "field_completeness": round(field_completeness_score, 1),
        "assert_standard": round(assert_standard_score, 1),
        "scenario_coverage": scenario_score,
        "extract_variable": round(extract_score, 1),
        "param_correctness": round(param_correctness_score, 1),
        "executability": round(executability_score, 1),
        "url_reasonableness": round(url_reasonableness_score, 1),
        "total_score": round(total_score, 1),
        "max_score": max_score,
        "percent_score": round((total_score / max_score) * 100, 1),
        "details": {
            "quantity": {
                "expected": expected_num,
                "actual": total,
                "compliance_rate": quantity_compliance
            },
            "field": {
                "complete_count": field_complete_count,
                "total": total,
                "field_status": field_status
            },
            "assert": {
                "standard_count": assert_standard_count,
                "total": total
            },
            "scenario": {
                "positive_count": positive_count,
                "negative_count": negative_count,
                "boundary_count": boundary_count,
                "total": total
            },
            "extract": {
                "positive_count": positive_count,
                "has_extract_count": positive_has_extract
            },
            "param": {
                "correct_count": param_correct_count,
                "total": total
            },
            "executable": {
                "executable_count": executable_count,
                "total": total
            },
            "url_issues": []
        }
    }


# ======================
# 测试用例集
# ======================
TEST_SUITE = [
    # 电商平台
    {"name": "【电商】登录模块", "project": "电商平台", "module": "登录", "case_num": 15,
     "rules": """登录接口：POST /api/login
参数：username(手机号/邮箱), password(6-20位), verify_code(4位数字，固定8888)
成功返回：{"code":0, "msg":"登录成功", "data":{"token":"xxx"}}
失败返回：{"code":1, "msg":"错误信息"}
- 账号：13513531480 / 123456
- 验证码固定8888
- 密码错误返回：密码错误
- 账号不存在返回：账号不存在"""},

    {"name": "【电商】购物车模块", "project": "电商平台", "module": "购物车", "case_num": 12,
     "rules": """购物车接口：
- 添加：POST /api/cart/add，参数：goods_id, num
- 查询：GET /api/cart/list
- 修改：PUT /api/cart/update，参数：cart_id, num
- 删除：DELETE /api/cart/delete，参数：cart_id
规则：数量范围1-999，需要登录，库存不足返回错误"""},

    {"name": "【电商】搜索模块", "project": "电商平台", "module": "搜索", "case_num": 10,
     "rules": """搜索接口：GET /api/search
参数：keyword(关键词), filter(筛选条件), sort(排序方式)
规则：支持模糊搜索，无结果返回空列表"""},

    {"name": "【电商】下单模块", "project": "电商平台", "module": "下单", "case_num": 12,
     "rules": """下单接口：POST /api/order
参数：goods_id, address_id, payment_id, coupon_id
规则：需要登录，库存不足返回错误"""},

    # 旅游平台
    {"name": "【旅游】酒店搜索", "project": "旅游平台", "module": "酒店搜索", "case_num": 12,
     "rules": """酒店搜索接口：GET /api/hotel/search
参数：city(城市), checkin(入住日期), checkout(离店日期), rooms(房间数), adults(成人数)
规则：日期格式YYYY-MM-DD，房间数1-5，每房成人1-3"""},

    {"name": "【旅游】机票搜索", "project": "旅游平台", "module": "机票搜索", "case_num": 10,
     "rules": """机票搜索接口：GET /api/flight/search
参数：from_city(出发城市), to_city(到达城市), date(出发日期), passenger_num(乘客数)
规则：日期不能是过去，乘客数1-9"""},

    # 社交平台
    {"name": "【社交】发布动态", "project": "社交平台", "module": "发布动态", "case_num": 10,
     "rules": """发布动态接口：POST /api/feed/publish
参数：content(内容), images(图片列表), location(位置)
规则：内容长度1-500字，需要登录"""},

    {"name": "【社交】评论功能", "project": "社交平台", "module": "评论", "case_num": 10,
     "rules": """评论接口：POST /api/comment/add
参数：feed_id, content, reply_to(可选)
规则：内容长度1-200字，需要登录"""},

    # 金融系统
    {"name": "【金融】转账功能", "project": "银行系统", "module": "转账", "case_num": 12,
     "rules": """转账接口：POST /api/transfer
参数：from_account, to_account, amount, password
规则：金额>0，不能超过余额，需要登录"""},

    {"name": "【金融】查询余额", "project": "银行系统", "module": "余额查询", "case_num": 8,
     "rules": """余额查询接口：GET /api/balance
参数：account_id
规则：需要登录"""},
]


# ======================
# 主程序
# ======================
def main():
    print("=" * 80)
    print("🎯 接口测试用例智能体 - 完整评估报告")
    print("=" * 80)
    print(f"📅 评估时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 测试模块数: {len(TEST_SUITE)}")
    print("📋 评估维度:")
    print("   1. 数量达标率 (10分) - 实际生成数/要求数")
    print("   2. 字段完整性 (10分) - case_id/title/method/url/(body/params)/assert")
    print("   3. 断言规范性 (10分) - status_code + body.code")
    print("   4. 场景覆盖度 (10分) - 正向/反向/边界")
    print("   5. 提取变量 (10分) - 正向用例是否有extract")
    print("   6. 参数正确性 (10分) - 字段名不能有中文")
    print("   7. 可执行性 (10分) - 字段完整+断言规范")
    print("   8. URL合理性 (10分) - URL格式是否合理")
    print("=" * 80)

    all_results = []
    project_stats = {}

    for i, test in enumerate(TEST_SUITE, 1):
        print(f"\n{'=' * 70}")
        print(f"📝 [{i}/{len(TEST_SUITE)}] {test['name']}")
        print(f"   项目: {test['project']}")
        print(f"   模块: {test['module']}")
        print(f"   要求数量: {test['case_num']}")
        print('=' * 70)

        try:
            start_time = time.time()
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
                print(f"   ❌ 未生成任何用例")
                continue

            # 评估
            eval_result = evaluate_test_suite(cases, test['module'], test['case_num'])

            # 展示评分
            print(f"\n   📊 评分详情:")
            print(f"      数量达标: {eval_result['quantity_compliance']:.1f}/10")
            print(f"      字段完整: {eval_result['field_completeness']:.1f}/10")
            print(f"      断言规范: {eval_result['assert_standard']:.1f}/10")
            print(f"      场景覆盖: {eval_result['scenario_coverage']}/10")
            print(f"      提取变量: {eval_result['extract_variable']:.1f}/10")
            print(f"      参数正确: {eval_result['param_correctness']:.1f}/10")
            print(f"      可执行性: {eval_result['executability']:.1f}/10")
            print(f"      URL合理: {eval_result['url_reasonableness']:.1f}/10")
            print(f"   🏆 总分: {eval_result['total_score']:.1f}/{eval_result['max_score']} ({eval_result['percent_score']:.1f}%)")

            # 判断等级
            if eval_result['percent_score'] >= 90:
                grade = "优秀 ⭐⭐⭐"
            elif eval_result['percent_score'] >= 75:
                grade = "良好 ⭐⭐"
            elif eval_result['percent_score'] >= 60:
                grade = "及格 ⭐"
            else:
                grade = "待改进"
            print(f"   {grade}")

            # 优点
            strengths = []
            if eval_result['quantity_compliance'] >= 9.5:
                strengths.append(f"数量达标({test['case_num']}/{len(cases)})")
            if eval_result['field_completeness'] >= 9:
                strengths.append("字段完整")
            if eval_result['assert_standard'] >= 9:
                strengths.append("断言规范")
            if eval_result['scenario_coverage'] >= 8:
                details = eval_result['details']
                strengths.append(f"场景覆盖好(正{details['scenario']['positive_count']}/反{details['scenario']['negative_count']})")
            if eval_result['extract_variable'] >= 9:
                strengths.append("正向用例有extract")
            if eval_result['param_correctness'] >= 9:
                strengths.append("参数字段英文化")
            if eval_result['executability'] >= 9:
                strengths.append("可执行性好")

            if strengths:
                print(f"   ✅ 优点: {', '.join(strengths)}")

            # 缺点
            weaknesses = []
            if eval_result['field_completeness'] < 7:
                weaknesses.append("字段不完整")
            if eval_result['assert_standard'] < 7:
                weaknesses.append("断言不规范")
            if eval_result['scenario_coverage'] < 6:
                weaknesses.append("场景覆盖不足")
            if eval_result['extract_variable'] < 7:
                weaknesses.append("正向用例缺少extract")
            if eval_result['param_correctness'] < 7:
                weaknesses.append("参数字段含中文")
            if eval_result['executability'] < 7:
                weaknesses.append("可执行性差")

            if weaknesses:
                print(f"   ⚠️ 缺点: {', '.join(weaknesses)}")

            # 展示示例用例
            if cases:
                print(f"\n   📋 示例用例:")
                sample = cases[0]
                print(f"      case_id: {sample.get('case_id')}")
                print(f"      title: {sample.get('title')}")
                print(f"      method: {sample.get('method')}")
                print(f"      url: {sample.get('url')}")
                if sample.get('params'):
                    print(f"      params: {json.dumps(sample.get('params'), ensure_ascii=False)[:100]}")
                if sample.get('body'):
                    print(f"      body: {json.dumps(sample.get('body'), ensure_ascii=False)[:100]}")
                print(f"      assert: {json.dumps(sample.get('assert'), ensure_ascii=False)}")

            # 统计项目
            project = test['project']
            if project not in project_stats:
                project_stats[project] = {"scores": [], "count": 0}
            project_stats[project]["scores"].append(eval_result['percent_score'])
            project_stats[project]["count"] += 1

            all_results.append({
                "test_name": test['name'],
                "project": test['project'],
                "module": test['module'],
                "expected_num": test['case_num'],
                "actual_num": len(cases),
                "success": True,
                "elapsed": elapsed,
                "scores": eval_result,
                "grade": grade,
                "strengths": strengths,
                "weaknesses": weaknesses,
                "sample_cases": cases[:2] if cases else []
            })

        except Exception as e:
            print(f"   ❌ 生成失败: {e}")
            all_results.append({
                "test_name": test['name'],
                "project": test['project'],
                "module": test['module'],
                "expected_num": test['case_num'],
                "actual_num": 0,
                "success": False,
                "error": str(e)
            })

    # ======================
    # 汇总报告
    # ======================
    print("\n" + "=" * 80)
    print("📈 汇总报告")
    print("=" * 80)

    successful = [r for r in all_results if r.get('success')]
    failed = [r for r in all_results if not r.get('success')]

    print(f"\n📊 执行统计:")
    print(f"   成功: {len(successful)}/{len(all_results)}")
    print(f"   失败: {len(failed)}/{len(all_results)}")

    if successful:
        avg_score = sum(r['scores']['percent_score'] for r in successful) / len(successful)
        avg_quantity = sum(r['scores']['quantity_compliance'] for r in successful) / len(successful) * 10

        print(f"\n📈 总体得分:")
        print(f"   平均综合得分: {avg_score:.1f}%")
        print(f"   平均数量达标率: {avg_quantity:.1f}%")

        # 各维度平均分
        dim_avg = {
            "数量达标率": 0,
            "字段完整性": 0,
            "断言规范性": 0,
            "场景覆盖度": 0,
            "提取变量": 0,
            "参数正确性": 0,
            "可执行性": 0,
            "URL合理性": 0
        }
        for r in successful:
            s = r['scores']
            dim_avg["数量达标率"] += s['quantity_compliance']
            dim_avg["字段完整性"] += s['field_completeness']
            dim_avg["断言规范性"] += s['assert_standard']
            dim_avg["场景覆盖度"] += s['scenario_coverage']
            dim_avg["提取变量"] += s['extract_variable']
            dim_avg["参数正确性"] += s['param_correctness']
            dim_avg["可执行性"] += s['executability']
            dim_avg["URL合理性"] += s['url_reasonableness']

        n = len(successful)
        print(f"\n📊 各维度平均得分:")
        for k, v in dim_avg.items():
            bar = "█" * int(v) + "░" * (10 - int(v))
            print(f"   {k}: {v/n:.1f}/10 {bar}")

        # 按项目分组
        print(f"\n📊 按项目分组:")
        for project, stats in project_stats.items():
            avg = sum(stats['scores']) / len(stats['scores'])
            print(f"   {project}: 平均分 {avg:.1f}% (测试{stats['count']}个模块)")

        # 泛化能力分析
        domain_scores = {}
        for r in successful:
            name = r['test_name']
            if "电商" in name:
                domain_scores["电商"] = domain_scores.get("电商", []) + [r['scores']['percent_score']]
            elif "旅游" in name:
                domain_scores["旅游"] = domain_scores.get("旅游", []) + [r['scores']['percent_score']]
            elif "社交" in name:
                domain_scores["社交"] = domain_scores.get("社交", []) + [r['scores']['percent_score']]
            elif "金融" in name:
                domain_scores["金融"] = domain_scores.get("金融", []) + [r['scores']['percent_score']]

        if domain_scores:
            print(f"\n🧠 泛化能力分析:")
            for domain, scores in domain_scores.items():
                avg = sum(scores) / len(scores)
                print(f"   {domain}领域: {avg:.1f}%")

        # 综合评级
        if avg_score >= 90:
            print("\n🎯 综合评级: 🏆 优秀 - 可以直接用于生产环境")
        elif avg_score >= 75:
            print("\n🎯 综合评级: ✅ 良好 - 基本可用，建议优化")
        elif avg_score >= 60:
            print("\n🎯 综合评级: ⚠️ 及格 - 需要改进")
        else:
            print("\n🎯 综合评级: ❌ 待改进 - 存在明显问题")

    # 保存报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_modules": len(all_results),
        "successful_count": len(successful),
        "failed_count": len(failed),
        "avg_score": avg_score if successful else 0,
        "avg_quantity_rate": avg_quantity if successful else 0,
        "dimension_avg": {k: v/n for k, v in dim_avg.items()} if successful else {},
        "project_stats": {p: {"count": s["count"], "avg_score": sum(s["scores"])/len(s["scores"])} for p, s in project_stats.items()},
        "generalization": {
            "domain_scores": {d: sum(s)/len(s) for d, s in domain_scores.items()} if domain_scores else {},
            "interpretation": "泛化能力良好" if avg_score >= 75 else "泛化能力一般"
        } if successful else {},
        "results": all_results
    }

    with open("complete_evaluation_report.json", "w", encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 详细报告已保存: complete_evaluation_report.json")


if __name__ == "__main__":
    main()