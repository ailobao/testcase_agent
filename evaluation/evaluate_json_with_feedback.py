"""
DeepEval 评估 - JSON 用例质量（带详细反馈）
逐模块评估，完整异常处理，时间统计
"""
import json
import time
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

from common import BaseEvaluator, JudgeLLM, parse_judge_json_response
from src.agents.api_agent import APITestAgent
from src.tools.rule_manager import get_all_projects, get_module_names


def build_cases_summary(cases: list, max_chars: int = 5000) -> str:
    """将用例列表压缩为评估友好的摘要"""
    if not cases:
        return "[]"

    detailed = cases[:8]
    rest = cases[8:]
    parts = [json.dumps(detailed, ensure_ascii=False, indent=2)]

    if rest:
        summaries = []
        for c in rest:
            summaries.append({
                "case_id": c.get("case_id", "?"),
                "title": c.get("title", ""),
                "assert": c.get("assert", {}),
                "body_keys": list(c.get("body", {}).keys()) if isinstance(c.get("body"), dict) else str(c.get("body"))
            })
        parts.append("\n--- 以下为摘要 ---\n")
        parts.append(json.dumps(summaries, ensure_ascii=False, indent=2))

    full = "\n".join(parts)
    if len(full) > max_chars:
        full = full[:max_chars] + "\n... [截断]"
    return full


def get_json_feedback(cases: list, module_name: str, cases_count: int) -> str:
    """获取 JSON 用例的详细改进建议"""
    from openai import OpenAI
    import os

    summary = build_cases_summary(cases)
    client = OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    judge_model = os.getenv("JUDGE_MODEL", "qwen3.7-plus")
    prompt = f"""你是测试用例质量分析专家。请分析以下 {module_name} 模块的测试用例（共 {cases_count} 条），指出具体问题和改进建议。

【用例内容】
{summary}

请按以下格式输出：

【总体评价】
（一句话总结）

【各维度评分】（每项0-10分）
格式正确性: X/10 - 问题说明
断言规范性: X/10 - 问题说明
边界值覆盖: X/10 - 问题说明
场景覆盖: X/10 - 问题说明
参数有效性: X/10 - 问题说明

【主要问题】
1. 具体问题1
2. 具体问题2

【改进建议】
1. 具体建议1
2. 具体建议2"""

    try:
        response = client.chat.completions.create(
            model=judge_model,
            messages=[
                {"role": "system", "content": "你是一个测试用例质量分析专家。请严格按照用户要求的格式输出分析结果。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=3000
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


class JSONEvaluator(BaseEvaluator):
    eval_name = "JSON 用例质量评估"
    eval_description = "使用 DeepEval + Qwen-Max 评估接口测试用例 JSON 质量"
    eval_dimensions = ["格式正确性", "断言规范性", "边界值覆盖", "场景覆盖", "参数有效性"]

    @property
    def TEST_SUITE(self):
        return get_test_modules()  # 全部模块

    def run_single_evaluation(self, project: str, module: str, cases: list = None):
        """对单个模块生成用例、评分并返回结果。

        参数:
            cases: 可选，预生成的用例列表。不传则调用 agent.generate() 生成。
        """
        result = {
            "project": project,
            "module": module,
            "module_name": f"{project}/{module}",
            "cases": [],
            "deepval_score": None,
            "feedback": "",
            "error": None,
            "elapsed": 0,
        }

        t0 = time.time()

        if cases is not None:
            # 使用外部传入的预生成用例，跳过 agent.generate()
            self.logger.info(f"   使用预生成用例: {len(cases)} 条")
        else:
            agent = APITestAgent()
            try:
                cases = agent.generate(project, module, "")
                cases = cases or []
            except Exception as e:
                result["error"] = f"生成失败: {e}"
                result["elapsed"] = time.time() - t0
                return result

        if not cases:
            result["error"] = "未生成任何用例"
            result["elapsed"] = time.time() - t0
            return result

        result["cases"] = cases

        # DeepEval 评分
        cases_str = json.dumps(cases, ensure_ascii=False, indent=2)
        test_case = LLMTestCase(
            input=f"为{project}/{module}模块生成接口测试用例",
            actual_output=cases_str
        )

        json_metric = GEval(
            name="JSON质量",
            criteria="""评估接口测试用例的JSON质量，逐项打分（每项0-10分）：

1. 格式正确性（10分）：6个字段齐不齐、body是否合法JSON、url占位符是否替换
2. 断言规范性（10分）：正向有status_code+body.code+body.msg、反向状态码合理、无硬编码易变消息
3. 边界值覆盖（10分）：有范围的参数覆盖min/mid/max/min-1/max+1、ID类有异常值
4. 场景覆盖（10分）：正向含extract、必填缺失/参数为空/Token异常、越权/注入/并发等
5. 参数有效性（10分）：值有实际业务含义、无占位符、枚举使用合法取值
""",
            evaluation_steps=[
                "检查6字段完整性",
                "检查断言规范性",
                "检查边界值覆盖深度",
                "检查场景覆盖广度",
                "检查参数值有效性"
            ],
            evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
            model=JudgeLLM.get_instance(),
            threshold=0.65,
            async_mode=False
        )

        try:
            # DeepEval 长时间运行可能挂起，加超时保护（5分钟）
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(evaluate, [test_case], [json_metric])
                eval_results = future.result(timeout=300)
            if eval_results.test_results:
                metrics = eval_results.test_results[0].metrics_data
                if metrics:
                    result["deepval_score"] = round(metrics[0].score, 2)
        except concurrent.futures.TimeoutError:
            result["error"] = "DeepEval 评分超时（超过5分钟）"
            result["elapsed"] = time.time() - t0
            return result
        except Exception as e:
            result["error"] = f"DeepEval 评分失败: {e}"
            result["elapsed"] = time.time() - t0
            return result

        # 详细反馈
        result["feedback"] = get_json_feedback(cases, module, len(cases))
        result["elapsed"] = round(time.time() - t0, 2)
        return result

    def run(self):
        self.print_header()
        agent = APITestAgent()
        modules = self.TEST_SUITE
        total_start = time.time()
        self.logger.info(f"📊 共 {len(modules)} 个模块，开始逐个生成...")

        for i, test in enumerate(modules, 1):
            project = test["project"]
            module = test["module"]
            self.logger.info(f"\n📝 [{i}/{len(modules)}] 评估: {project}/{module}")

            t_start = time.time()
            r = self.run_single_evaluation(project, module)
            t_cost = time.time() - t_start

            if r["error"]:
                self.logger.info(f"   ❌ {r['error']}")
                if "超时" in str(r.get("error", "")):
                    self.logger.warning(f"   ⏰ {project}/{module} DeepEval 评分超时，可在 common.py 中调高 timeout 参数")
            else:
                score_str = f"{r['deepval_score']:.2f}" if r["deepval_score"] is not None else "N/A"
                self.logger.info(f"   ✅ 用例数: {len(r['cases'])} | 得分: {score_str} | 耗时: {r['elapsed']}s")

            self.results.append(r)

        total_elapsed = round(time.time() - total_start, 2)

        # ========== 汇总统计 ==========
        self.logger.info("\n" + "=" * 80)
        self.logger.info("📊 汇总统计")
        self.logger.info("=" * 80)

        successful = [r for r in self.results if r["deepval_score"] is not None and not r["error"]]
        failed = [r for r in self.results if r["error"]]
        self.logger.info(f"\n📋 总模块数: {len(modules)}")
        self.logger.info(f"✅ 评估成功: {len(successful)}")
        self.logger.info(f"❌ 跳过/失败: {len(failed)}")
        self.logger.info(f"📊 总用例数: {sum(len(r['cases']) for r in successful)}")
        self.logger.info(f"⏱️ 总耗时: {total_elapsed}s")

        scores = [r["deepval_score"] for r in successful]
        if scores:
            avg_score = sum(scores) / len(scores)
            self.logger.info(f"\n🏆 综合评分:")
            self.logger.info(f"   平均得分: {avg_score:.2f}")
            self.logger.info(f"   最低得分: {min(scores):.2f}")
            self.logger.info(f"   最高得分: {max(scores):.2f}")
            self.logger.info(f"   ≥ 0.65 通过率: {sum(1 for s in scores if s >= 0.65)}/{len(scores)} ({sum(1 for s in scores if s >= 0.65) / len(scores) * 100:.1f}%)")

        # ========== 详细反馈 ==========
        self.logger.info("\n" + "=" * 80)
        self.logger.info("🔍 详细分析与改进建议")
        self.logger.info("=" * 80)

        for r in self.results:
            self.logger.info(f"\n{'=' * 60}")
            self.logger.info(f"📋 {r['project']}/{r['module']}")
            self.logger.info(f"{'=' * 60}")
            if r["error"]:
                self.logger.info(f"⚠️ 错误: {r['error']}")
            else:
                self.logger.info(r["feedback"])

        self.save_report()


def main():
    evaluator = JSONEvaluator()
    evaluator.run()


if __name__ == "__main__":
    main()
