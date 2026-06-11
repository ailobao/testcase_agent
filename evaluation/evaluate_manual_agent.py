"""
评估手工测试用例生成质量
维度: 格式规范、规则遵循、场景覆盖、可执行性、数据合理性
"""
import json
import time

# 路径修复：确保 evaluation/ 目录在 sys.path 中
import sys, os
_eval_dir = os.path.dirname(os.path.abspath(__file__))
if _eval_dir not in sys.path:
    sys.path.insert(0, _eval_dir)

from common import BaseEvaluator
from src.agents.manual_agent import ManualTestAgent


def evaluate_manual_cases(project, module, rules, cases, fields, judge_func):
    """使用 DeepSeek 评估手工测试用例质量"""
    if not cases:
        return {
            "total_score": 0, "max_score": 100, "grade": "失败",
            "error": "没有生成任何用例"
        }

    # 兼容数据库返回 dict 类型字段（{name, type, description}）
    flat_fields = [f["name"] if isinstance(f, dict) else f for f in (fields or [])]

    cases_preview = []
    for case in cases[:5]:
        preview = {
            "用例ID": case.get("用例ID"),
            "标题": str(case.get("标题", ""))[:50],
            "优先级": case.get("优先级"),
            "前置条件": str(case.get("前置条件", ""))[:80],
            "测试步骤": str(case.get("测试步骤", ""))[:150],
            "预期结果": str(case.get("预期结果", ""))[:80],
        }
        for field in flat_fields[:3]:
            if field in case:
                preview[field] = str(case.get(field, ""))[:30]
        cases_preview.append(preview)

    cases_json = json.dumps(cases_preview, ensure_ascii=False, indent=2)

    prompt = f"""你是手工测试用例质量评估专家。请对以下生成的手工测试用例进行客观评分。

【测试需求】
项目名称：{project}
模块名称：{module}
业务规则：{rules if rules else "无特殊规则"}
动态字段：{fields}

【生成的测试用例（前5条预览）】
{cases_json}

实际生成数量：{len(cases)}条

请从以下5个维度评分（每项0-20分）：

1. **格式规范性**：是否包含用例ID、标题、前置条件、测试步骤、预期结果、优先级
2. **规则遵循度**：是否正确遵守了业务规则和动态字段要求
3. **场景覆盖度**：是否覆盖了正向、异常、边界场景
4. **可执行性**：测试步骤是否清晰、可操作，前置条件是否明确
5. **数据合理性**：测试数据是否符合业务逻辑，是否真实有效

请输出以下JSON格式：

{{
    "format_score": 16,
    "rule_score": 16,
    "scenario_score": 16,
    "executable_score": 16,
    "data_score": 16,
    "total_score": 80,
    "max_score": 100,
    "percent_score": 80.0,
    "grade": "良好",
    "strengths": ["格式规范", "步骤清晰"],
    "weaknesses": ["边界场景不足"],
    "suggestions": "增加更多边界值测试"
}}"""

    result = judge_func(prompt)
    if result:
        return result
    return {
        "total_score": 0, "max_score": 100, "percent_score": 0,
        "grade": "评估失败", "error": "Judge 调用失败"
    }


MANUAL_TEST_SUITE = [
    {"name": "登录", "project": "客达天下", "module": "登录", "test_type": "功能测试", "case_num": 10,
     "rules": "用户名：manager/admin，密码：123456，验证码：8888"},
    {"name": "新增课程", "project": "客达天下", "module": "新增课程", "test_type": "功能测试", "case_num": 12,
     "rules": "课程名称1-64字符，价格0-99999，学科有效值0-9"},
    {"name": "查询课程列表", "project": "客达天下", "module": "查询课程列表", "test_type": "功能测试", "case_num": 10,
     "rules": "支持按名称、学科筛选"},
    {"name": "删除课程", "project": "客达天下", "module": "删除课程", "test_type": "功能测试", "case_num": 8,
     "rules": "根据ID删除课程"},
    {"name": "合同上传", "project": "客达天下", "module": "合同上传", "test_type": "功能测试", "case_num": 8,
     "rules": "支持PDF、Word格式，大小不超过10MB"},
    {"name": "新增合同", "project": "客达天下", "module": "新增合同", "test_type": "功能测试", "case_num": 12,
     "rules": "合同编号唯一，手机号11位"},
    {"name": "电商-登录", "project": "电商平台", "module": "登录", "test_type": "功能测试", "case_num": 10,
     "rules": "用户名：手机号/邮箱，密码6-20位，验证码固定8888"},
    {"name": "电商-购物车", "project": "电商平台", "module": "购物车", "test_type": "功能测试", "case_num": 10,
     "rules": "数量1-99，库存不足提示"},
    {"name": "电商-下单", "project": "电商平台", "module": "下单", "test_type": "功能测试", "case_num": 10,
     "rules": "需要地址、支付方式"},
    {"name": "银行-转账", "project": "银行系统", "module": "转账", "test_type": "功能测试", "case_num": 10,
     "rules": "金额>0，不能超过余额"},
]


class ManualEvaluator(BaseEvaluator):
    eval_name = "手工测试用例评估"
    eval_description = "使用 DeepSeek 评估手工测试用例生成质量"
    eval_dimensions = ["格式规范性", "规则遵循度", "场景覆盖度", "可执行性", "数据合理性"]

    @property
    def TEST_SUITE(self):
        return MANUAL_TEST_SUITE

    def evaluate_single(self, test: dict, cases: list, fields: list, elapsed: float) -> dict:
        """
        纯评估：对已生成的 cases 执行评分，不依赖生成步骤。
        """
        if not cases:
            return {"error": "没有用例", "skip": True}

        self.logger.info("⏳ DeepSeek 评估中...")
        eval_result = evaluate_manual_cases(
            test['project'], test['module'],
            test.get('rules', ''), cases, fields, self._judge
        )

        pct = eval_result.get('percent_score', 0)
        self.logger.info(f"\n   📊 评分详情:")
        self.logger.info(f"      格式规范: {eval_result.get('format_score', 0)}/20")
        self.logger.info(f"      规则遵循: {eval_result.get('rule_score', 0)}/20")
        self.logger.info(f"      场景覆盖: {eval_result.get('scenario_score', 0)}/20")
        self.logger.info(f"      可执行性: {eval_result.get('executable_score', 0)}/20")
        self.logger.info(f"      数据合理: {eval_result.get('data_score', 0)}/20")
        self.logger.info(f"   🏆 总分: {eval_result.get('total_score', 0)}/{eval_result.get('max_score', 100)} ({pct}%) {eval_result.get('grade', '')}")

        return {
            "test_name": test['name'],
            "project": test['project'],
            "module": test['module'],
            "module_name": test['name'],
            "cases_count": len(cases),
            "dynamic_fields": fields,
            "percent_score": pct,
            "grade": eval_result.get('grade', ''),
            "strengths": eval_result.get('strengths', []),
            "weaknesses": eval_result.get('weaknesses', []),
            "evaluation": eval_result,
            "elapsed": elapsed,
        }

    def run(self):
        self.print_header()
        agent = ManualTestAgent()

        for i, test in enumerate(self.TEST_SUITE, 1):
            self.print_module_start(i, len(self.TEST_SUITE),
                                    test['name'], test['project'], test['module'])

            try:
                t0 = time.time()
                self.logger.info("⏳ 调用智能体生成手工测试用例...")

                cases, fields = agent.generate(
                    project_name=test['project'],
                    module_name=test['module'],
                    test_type=test['test_type'],
                    expected_num=test['case_num'],
                    business_rules=test.get('rules', '')
                )
                elapsed = time.time() - t0

                self.logger.info(f"   ⏱️ 耗时: {elapsed:.2f}秒")
                self.logger.info(f"   📊 生成用例: {len(cases)}条")

                if not cases:
                    self.logger.info("   ❌ 未生成任何用例，跳过评估")
                    continue

                r = self.evaluate_single(test, cases, fields, elapsed)
                if r.get("skip"):
                    continue
                self.results.append(r)

            except Exception as e:
                self.logger.info(f"   ❌ 生成失败: {e}")
                import traceback
                traceback.print_exc()

            except Exception as e:
                self.logger.info(f"   ❌ 生成失败: {e}")
                import traceback
                traceback.print_exc()

        self.print_summary()
        self.save_report()


def main():
    evaluator = ManualEvaluator()
    evaluator.run()


if __name__ == "__main__":
    main()
