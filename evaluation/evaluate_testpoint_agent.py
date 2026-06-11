"""
评估测试点分析生成质量
维度: 结构完整性、测试点覆盖率、口语化程度、场景实用性、规则遵循度
"""
import json
import time

# 路径修复：确保 evaluation/ 目录在 sys.path 中
import sys, os
_eval_dir = os.path.dirname(os.path.abspath(__file__))
if _eval_dir not in sys.path:
    sys.path.insert(0, _eval_dir)

from common import BaseEvaluator
from src.agents.testpoint_agent import TestPointAgent
from src.tools.knowledge_loader import get_examples_by_keywords


def evaluate_testpoint_content(project, module, rules, content, judge_func):
    """使用 DeepSeek 评估测试点分析质量"""
    if not content or len(content) < 100:
        return {
            "total_score": 0, "max_score": 100, "grade": "失败",
            "error": "内容过短或为空"
        }

    content_preview = content[:3000]
    if len(content) > 3000:
        content_preview += f"\n... (共{len(content)}字符，已截断)"

    prompt = f"""你是测试点分析质量评估专家。请对以下生成的测试点分析进行客观评分。

【测试需求】
项目名称：{project}
模块名称：{module}
业务规则：{rules if rules else "无特殊规则"}

【生成的测试点分析（前3000字符）】
{content_preview}

请从以下5个维度评分（每项0-20分）：

1. **结构完整性**：是否包含功能测试、非功能测试、测试方法总结，格式是否规范
2. **测试点覆盖率**：是否覆盖了核心功能的正向、反向、边界场景
3. **口语化程度**：描述是否像人话，是否使用"能不能"、"点了会不会"等口语表达
4. **场景实用性**：测试点是否实用，能否直接用于指导测试执行
5. **规则遵循度**：是否正确遵守了业务规则，反向测试点是否只写操作不写预期

请输出以下JSON格式：

{{
    "structure_score": 16,
    "coverage_score": 16,
    "colloquial_score": 16,
    "practicality_score": 16,
    "rule_score": 16,
    "total_score": 80,
    "max_score": 100,
    "percent_score": 80.0,
    "grade": "良好",
    "strengths": ["结构完整", "覆盖全面"],
    "weaknesses": ["口语化不足"],
    "suggestions": "使用更多口语化表达"
}}"""

    result = judge_func(prompt)
    if result:
        return result
    return {
        "total_score": 0, "max_score": 100, "percent_score": 0,
        "grade": "评估失败", "error": "Judge 调用失败"
    }


TESTPOINT_TEST_SUITE = [
    {"name": "登录", "project": "客达天下", "module": "登录",
     "rules": "用户名：manager/admin，密码：123456，验证码：8888"},
    {"name": "新增课程", "project": "客达天下", "module": "新增课程",
     "rules": "课程名称1-64字符，价格0-99999"},
    {"name": "查询课程列表", "project": "客达天下", "module": "查询课程列表",
     "rules": "支持按名称、学科筛选"},
    {"name": "删除课程", "project": "客达天下", "module": "删除课程",
     "rules": "根据ID删除课程"},
    {"name": "合同上传", "project": "客达天下", "module": "合同上传",
     "rules": "支持PDF、Word格式"},
    {"name": "新增合同", "project": "客达天下", "module": "新增合同",
     "rules": "合同编号唯一，手机号11位"},
    {"name": "电商-购物车", "project": "电商平台", "module": "购物车",
     "rules": "数量1-99，库存不足提示"},
    {"name": "电商-下单", "project": "电商平台", "module": "下单",
     "rules": "需要地址、支付方式"},
    {"name": "银行-转账", "project": "银行系统", "module": "转账",
     "rules": "金额>0，不能超过余额"},
]


class TestPointEvaluator(BaseEvaluator):
    eval_name = "测试点分析评估"
    eval_description = "使用 DeepSeek 评估测试点分析生成质量"
    eval_dimensions = ["结构完整性", "测试点覆盖率", "口语化程度", "场景实用性", "规则遵循度"]

    @property
    def TEST_SUITE(self):
        return TESTPOINT_TEST_SUITE

    def run(self):
        self.print_header()
        agent = TestPointAgent()

        for i, test in enumerate(self.TEST_SUITE, 1):
            self.print_module_start(i, len(self.TEST_SUITE),
                                    test['name'], test['project'], test['module'])

            try:
                t0 = time.time()
                self.logger.info("⏳ 调用智能体生成测试点分析...")

                examples = get_examples_by_keywords(test['project'], test['module'])
                content, error = agent.generate(
                    project=test['project'],
                    module=test['module'],
                    rules=test.get('rules', ''),
                    examples=examples
                )
                elapsed = time.time() - t0

                if error:
                    self.logger.info(f"   ❌ 生成失败: {error}")
                    continue

                # 统计
                lines = content.split('\n')
                testpoint_count = sum(1 for line in lines if line.strip().startswith('-'))

                self.logger.info(f"   ⏱️ 耗时: {elapsed:.2f}秒")
                self.logger.info(f"   📊 内容长度: {len(content)}字符")
                self.logger.info(f"   📊 测试点数量: {testpoint_count}条")

                # DeepSeek 评估
                self.logger.info("⏳ DeepSeek 评估中...")
                eval_result = evaluate_testpoint_content(
                    test['project'], test['module'],
                    test.get('rules', ''), content, self._judge
                )

                pct = eval_result.get('percent_score', 0)
                self.logger.info(f"\n   📊 评分详情:")
                self.logger.info(f"      结构完整性: {eval_result.get('structure_score', 0)}/20")
                self.logger.info(f"      测试点覆盖率: {eval_result.get('coverage_score', 0)}/20")
                self.logger.info(f"      口语化程度: {eval_result.get('colloquial_score', 0)}/20")
                self.logger.info(f"      场景实用性: {eval_result.get('practicality_score', 0)}/20")
                self.logger.info(f"      规则遵循度: {eval_result.get('rule_score', 0)}/20")
                self.logger.info(f"   🏆 总分: {eval_result.get('total_score', 0)}/{eval_result.get('max_score', 100)} ({pct}%) {eval_result.get('grade', '')}")

                self.results.append({
                    "test_name": test['name'],
                    "project": test['project'],
                    "module": test['module'],
                    "module_name": test['name'],
                    "content_length": len(content),
                    "testpoint_count": testpoint_count,
                    "percent_score": pct,
                    "grade": eval_result.get('grade', ''),
                    "strengths": eval_result.get('strengths', []),
                    "weaknesses": eval_result.get('weaknesses', []),
                    "evaluation": eval_result,
                    "elapsed": elapsed,
                })

            except Exception as e:
                self.logger.info(f"   ❌ 生成失败: {e}")
                import traceback
                traceback.print_exc()

        self.print_summary()
        self.save_report()


def main():
    evaluator = TestPointEvaluator()
    evaluator.run()


if __name__ == "__main__":
    main()
