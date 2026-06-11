"""跑一半模块的 JSON 评估"""
import sys, os, time, json
_eval_dir = os.path.dirname(os.path.abspath(__file__))
if _eval_dir not in sys.path:
    sys.path.insert(0, _eval_dir)

from evaluation.common import BaseEvaluator
from evaluation.evaluate_json_with_feedback import JSONEvaluator, get_test_modules, build_cases_summary, get_json_feedback
from src.agents.api_agent import APITestAgent
from deepeval import evaluate
from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.metrics import GEval
from evaluation.common import JudgeLLM
import concurrent.futures

# 取前一半模块（11个）
MODULE_COUNT = 11

class HalfEvaluator(BaseEvaluator):
    eval_name = "JSON 用例质量评估（半量）"
    eval_dimensions = ["格式正确性", "断言规范性", "边界值覆盖", "场景覆盖", "参数有效性"]

    @property
    def TEST_SUITE(self):
        modules = get_test_modules(max_modules=MODULE_COUNT)
        self.logger.info(f"📊 共 {len(modules)} 个模块（前一半）")
        return modules

    def run(self):
        self.print_header()
        modules = self.TEST_SUITE
        total_start = time.time()

        for i, test in enumerate(modules, 1):
            project = test["project"]
            module = test["module"]
            self.logger.info(f"\n📝 [{i}/{len(modules)}] {project}/{module}")

            t0 = time.time()
            agent = APITestAgent()
            try:
                cases = agent.generate(project, module, "")
                cases = cases or []
            except Exception as e:
                self.results.append({"project": project, "module": module, "error": str(e), "elapsed": time.time()-t0})
                self.logger.info(f"   ❌ 生成失败: {e}")
                continue

            if not cases:
                self.results.append({"project": project, "module": module, "error": "无用例", "elapsed": time.time()-t0})
                self.logger.info(f"   ❌ 无用例")
                continue

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
                    "检查6字段完整性", "检查断言规范性",
                    "检查边界值覆盖深度", "检查场景覆盖广度", "检查参数值有效性"
                ],
                evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
                model=JudgeLLM.get_instance(),
                threshold=0.65,
                async_mode=False
            )

            try:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(evaluate, [test_case], [json_metric])
                    eval_results = future.result(timeout=300)
                score = None
                if eval_results.test_results:
                    metrics = eval_results.test_results[0].metrics_data
                    if metrics:
                        score = round(metrics[0].score, 2)
            except Exception as e:
                self.results.append({"project": project, "module": module, "error": f"评分失败: {e}", "elapsed": time.time()-t0})
                self.logger.info(f"   ❌ 评分失败: {e}")
                continue

            # 详细反馈
            feedback = get_json_feedback(cases, module, len(cases))
            elapsed = round(time.time() - t0, 2)

            result = {
                "project": project, "module": module,
                "cases": cases, "deepval_score": score,
                "feedback": feedback, "elapsed": elapsed
            }
            self.results.append(result)
            self.logger.info(f"   ✅ 用例: {len(cases)}条 | DeepEval: {score} | 耗时: {elapsed}s")

        # 汇总
        total_elapsed = round(time.time() - total_start, 2)
        successful = [r for r in self.results if r.get("deepval_score") is not None]
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"📊 汇总: {len(successful)}/{len(modules)} 成功")
        self.logger.info(f"⏱️ 总耗时: {total_elapsed}s")
        scores = [r["deepval_score"] for r in successful]
        if scores:
            avg = sum(scores) / len(scores)
            self.logger.info(f"🏆 平均 DeepEval 得分: {avg:.2f}")
            self.logger.info(f"   最高: {max(scores):.2f}  最低: {min(scores):.2f}")
            for r in successful:
                self.logger.info(f"   {r['project']}/{r['module']:10}: {r['deepval_score']:.2f}")
        self.save_report()


if __name__ == "__main__":
    e = HalfEvaluator()
    e.run()
