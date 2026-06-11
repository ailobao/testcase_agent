"""
DeepEval 评估 - Pytest 脚本质量（带详细反馈）
"""
import os
import concurrent.futures
from deepeval import evaluate
from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.metrics import GEval

# 路径修复
import sys
_eval_dir = os.path.dirname(os.path.abspath(__file__))
if _eval_dir not in sys.path:
    sys.path.insert(0, _eval_dir)

from common import BaseEvaluator, JudgeLLM
from src.agents.api_agent import APITestAgent
from src.tools.rule_manager import get_all_projects, get_module_names


def get_pytest_feedback(script_content, module_name, cases_count):
    """获取 Pytest 脚本的详细改进建议"""
    from openai import OpenAI

    client = OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    prompt = f"""
你是 Pytest 脚本质量分析专家。请分析以下 {module_name} 模块的 Pytest 脚本（共 {cases_count} 条用例），指出具体问题和改进建议。

【脚本内容（前3000字符）】
{script_content[:3000]}

请按以下格式输出：

【总体评价】
（一句话总结）

【各维度评分】（每项0-10分）
语法正确性: X/10 - 问题说明
导入完整性: X/10 - 问题说明
参数化使用: X/10 - 问题说明
断言完整性: X/10 - 问题说明
代码可读性: X/10 - 问题说明

【主要问题】
1. 具体问题1
2. 具体问题2

【改进建议】
1. 具体建议1
2. 具体建议2
"""
    try:
        response = client.chat.completions.create(
            model=os.getenv("JUDGE_MODEL", "qwen3.7-plus"),
            messages=[
                {"role": "system", "content": "你是一个 Pytest 脚本质量分析专家。请严格按照用户要求的格式输出分析结果。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"获取详细反馈失败: {e}"


def get_test_modules(max_modules: int = None):
    """获取所有项目的所有模块"""
    projects = get_all_projects()
    modules = []
    for project in projects:
        for module in get_module_names(project):
            modules.append({"project": project, "module": module})
    if max_modules and len(modules) > max_modules:
        modules = modules[:max_modules]
    return modules


class PytestEvaluator(BaseEvaluator):
    eval_name = "Pytest 脚本质量评估"
    eval_description = "使用 DeepEval + Qwen-Max 评估 Pytest 脚本质量"
    eval_dimensions = ["语法正确性", "导入完整性", "参数化使用", "断言完整性", "代码可读性"]

    @property
    def TEST_SUITE(self):
        return get_test_modules()  # 全部模块

    def run(self):
        self.print_header()

        agent = APITestAgent()
        test_cases = []
        test_info = []

        all_modules = self.TEST_SUITE
        self.logger.info(f"📊 共 {len(all_modules)} 个模块，开始逐个生成...")

        for idx, test in enumerate(all_modules, 1):
            project = test["project"]
            module = test["module"]
            self.logger.info(f"\n📝 [{idx}/{len(all_modules)}] 生成: {project}/{module}")

            try:
                cases = agent.generate(project, module, "")
            except Exception as e:
                self.logger.info(f"   ❌ 生成失败: {e}")
                continue

            if not cases:
                self.logger.info(f"   ❌ 无用例")
                continue

            filepath = agent.export_pytest_script(cases, project, module)

            if not filepath or not os.path.exists(filepath):
                self.logger.info(f"   ❌ Pytest 脚本导出失败")
                continue

            with open(filepath, 'r', encoding='utf-8') as f:
                script_content = f.read()

            test_case = LLMTestCase(
                input=f"为{project}/{module}模块生成 Pytest 脚本",
                actual_output=script_content[:3000]
            )
            test_cases.append(test_case)
            test_info.append({
                "project": project,
                "module": module,
                "cases": len(cases),
                "script_content": script_content[:3000]
            })
            self.logger.info(f"   ✅ 用例数: {len(cases)}")

        if not test_cases:
            self.logger.info("❌ 没有可评估的测试用例")
            return

        pytest_metric = GEval(
            name="Pytest质量",
            criteria="评估 Pytest 脚本的质量",
            evaluation_steps=[
                "检查代码是否符合 Python 语法",
                "检查是否包含 import pytest、import requests",
                "检查是否使用 @pytest.mark.parametrize",
                "检查是否包含 assert 断言",
                "检查变量命名、注释、缩进是否规范"
            ],
            evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
            model=JudgeLLM.get_instance(),
            threshold=0.7
        )

        self.logger.info("\n⏳ DeepEval 评分中...")
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(evaluate, test_cases, [pytest_metric])
                eval_results = future.result(timeout=300)
        except concurrent.futures.TimeoutError:
            self.logger.info("❌ DeepEval 评分超时（超过5分钟）")
            return
        except Exception as e:
            self.logger.info(f"❌ DeepEval 评分失败: {e}")
            return

        # ========== DeepEval 评分结果 ==========
        self.logger.info("\n" + "=" * 80)
        self.logger.info("📈 DeepEval 评分结果")
        self.logger.info("=" * 80)

        scores = []
        if eval_results and eval_results.test_results:
            for i, metric_result in enumerate(eval_results.test_results):
                info = test_info[i] if i < len(test_info) else {"project": "?", "module": "?"}
                self.logger.info(f"\n📊 {info['project']}/{info['module']}")
                self.logger.info(f"   用例数: {info['cases']}")
                for metric in metric_result.metrics_data:
                    score = metric.score
                    scores.append(score)
                    self.logger.info(f"   DeepEval 得分: {score:.2f}")

        # ========== 汇总统计 ==========
        self.logger.info("\n" + "=" * 80)
        self.logger.info("📊 汇总统计")
        self.logger.info("=" * 80)
        self.logger.info(f"\n📋 总模块数: {len(all_modules)}")
        self.logger.info(f"✅ 评估成功: {len(test_cases)}")
        self.logger.info(f"❌ 跳过/失败: {len(all_modules) - len(test_cases)}")

        if scores:
            avg_score = sum(scores) / len(scores)
            self.logger.info(f"\n🏆 综合评分:")
            self.logger.info(f"   平均得分: {avg_score:.2f}")
            self.logger.info(f"   最低得分: {min(scores):.2f}")
            self.logger.info(f"   最高得分: {max(scores):.2f}")
            self.logger.info(f"   ≥ 0.7 通过率: {sum(1 for s in scores if s >= 0.7)}/{len(scores)} ({sum(1 for s in scores if s >= 0.7) / len(scores) * 100:.1f}%)")

        # ========== 详细反馈 ==========
        self.logger.info("\n" + "=" * 80)
        self.logger.info("🔍 详细分析与改进建议")
        self.logger.info("=" * 80)

        for info in test_info:
            self.logger.info(f"\n{'=' * 60}")
            self.logger.info(f"📋 {info['project']}/{info['module']}")
            self.logger.info(f"{'=' * 60}")

            feedback = get_pytest_feedback(info['script_content'], info['module'], info['cases'])
            self.logger.info(feedback)


def main():
    evaluator = PytestEvaluator()
    evaluator.run()


if __name__ == "__main__":
    main()
