"""
评估 AI 系统测试用例生成质量
维度: 功能、准确性、鲁棒性、用户体验、安全、分析报告
"""
import json
import time
from datetime import datetime

# 路径修复：确保 evaluation/ 目录在 sys.path 中
import sys, os
_eval_dir = os.path.dirname(os.path.abspath(__file__))
if _eval_dir not in sys.path:
    sys.path.insert(0, _eval_dir)

from common import BaseEvaluator
from src.agents.ai_agent import AITestAgent


def evaluate_ai_cases(project, module, description, cases, analysis, judge_func):
    """使用 DeepSeek 评估 AI 测试用例质量"""
    if not cases:
        return {
            "total_score": 0, "max_score": 100, "grade": "失败",
            "error": "没有生成任何用例"
        }

    # 统计各维度
    dim_counts = {}
    for case in cases:
        dim = case.get("测试类型", "未知")
        dim_counts[dim] = dim_counts.get(dim, 0) + 1

    cases_preview = []
    for case in cases[:5]:
        preview = {
            "测试ID": case.get("测试ID"),
            "测试标题": case.get("测试标题"),
            "测试类型": case.get("测试类型"),
            "优先级": case.get("优先级"),
            "前置条件": str(case.get("前置条件", ""))[:100],
            "测试步骤": str(case.get("测试步骤", ""))[:100],
            "预期结果": str(case.get("预期结果", ""))[:100],
        }
        cases_preview.append(preview)

    cases_json = json.dumps(cases_preview, ensure_ascii=False, indent=2)

    prompt = f"""你是AI系统测试专家。请对以下生成的AI系统测试用例进行客观评分。

【测试需求】
项目名称：{project}
模块名称：{module}
系统描述：{description}

【生成结果】
分析报告长度：{len(analysis)}字符
测试用例总数：{len(cases)}条
各维度分布：{json.dumps(dim_counts, ensure_ascii=False)}

【测试用例预览（前5条）】
{cases_json}

请从以下6个维度评分（每项0-20分）：

1. **功能测试质量**：是否覆盖了核心功能、输入输出、边界条件
2. **准确性测试质量**：是否测试了输出准确性、一致性、幻觉检测
3. **鲁棒性测试质量**：是否测试了异常输入、并发、稳定性
4. **用户体验测试质量**：是否测试了响应速度、友好提示、易用性
5. **安全性测试质量**：是否测试了提示词注入、越狱、数据安全
6. **分析报告质量**：分析报告是否全面、有深度、可操作

请输出以下JSON格式：

{{
    "function_score": 16,
    "accuracy_score": 16,
    "robustness_score": 16,
    "ux_score": 16,
    "security_score": 16,
    "analysis_score": 16,
    "total_score": 96,
    "max_score": 120,
    "percent_score": 80.0,
    "grade": "良好",
    "strengths": ["功能覆盖全面", "安全性测试到位"],
    "weaknesses": ["鲁棒性测试不足"],
    "suggestions": "增加并发测试和高负载场景",
    "dimension_distribution": {json.dumps(dim_counts, ensure_ascii=False)}
}}"""

    result = judge_func(prompt)
    if result:
        return result
    return {
        "total_score": 0, "max_score": 120, "percent_score": 0,
        "grade": "评估失败", "error": "Judge 调用失败"
    }


AI_TEST_SUITE = [
    {"name": "智能客服-问答模块", "project": "智能客服系统", "module": "问答模块",
     "description": "用户输入问题，AI返回答案。支持多轮对话、上下文理解、知识库检索。",
     "limits": {"功能": 8, "准确性": 8, "鲁棒性": 6, "用户体验": 6, "安全": 8}},
    {"name": "智能客服-意图识别", "project": "智能客服系统", "module": "意图识别",
     "description": "识别用户意图，分类到预定义意图类别（咨询、投诉、建议等）。",
     "limits": {"功能": 8, "准确性": 10, "鲁棒性": 6, "用户体验": 4, "安全": 6}},
    {"name": "代码助手-Python代码生成", "project": "AI代码助手", "module": "Python代码生成",
     "description": "根据自然语言描述生成Python代码，需要生成注释和示例。",
     "limits": {"功能": 10, "准确性": 10, "鲁棒性": 6, "用户体验": 6, "安全": 8}},
    {"name": "代码助手-代码解释", "project": "AI代码助手", "module": "代码解释",
     "description": "解释代码的功能、逻辑和潜在问题。",
     "limits": {"功能": 8, "准确性": 10, "鲁棒性": 6, "用户体验": 6, "安全": 6}},
    {"name": "内容审核-文本审核", "project": "内容审核系统", "module": "文本审核",
     "description": "检测文本中的违规内容（色情、暴力、政治敏感）。",
     "limits": {"功能": 8, "准确性": 10, "鲁棒性": 8, "用户体验": 4, "安全": 10}},
    {"name": "内容审核-图片审核", "project": "内容审核系统", "module": "图片审核",
     "description": "检测图片中的违规内容。",
     "limits": {"功能": 8, "准确性": 10, "鲁棒性": 8, "用户体验": 4, "安全": 10}},
    {"name": "翻译系统-中译英", "project": "AI翻译系统", "module": "中译英",
     "description": "将中文翻译成英文，保持语义准确。",
     "limits": {"功能": 8, "准确性": 10, "鲁棒性": 6, "用户体验": 6, "安全": 6}},
    {"name": "文本摘要-新闻摘要", "project": "AI文本摘要系统", "module": "新闻摘要",
     "description": "对新闻文章生成简短摘要，保留关键信息。",
     "limits": {"功能": 8, "准确性": 8, "鲁棒性": 6, "用户体验": 6, "安全": 6}},
]


class AIEvaluator(BaseEvaluator):
    eval_name = "AI 系统测试用例评估"
    eval_description = "使用 DeepSeek 评估 AI 系统测试用例生成质量"
    eval_dimensions = ["功能测试质量", "准确性测试质量", "鲁棒性测试质量", "用户体验测试质量", "安全性测试质量", "分析报告质量"]

    @property
    def TEST_SUITE(self):
        return AI_TEST_SUITE

    def evaluate_single(self, test: dict, cases: list, analysis: str, elapsed: float) -> dict:
        """
        纯评估：对已生成的 cases+analysis 执行评分，不依赖生成步骤。
        可用在 run() 内部，也可被外部传入预生成数据调用。
        """
        if not cases:
            return {"error": "没有用例", "skip": True}

        # 各维度统计
        dim_stats = {}
        for case in cases:
            d = case.get("测试类型", "未知")
            dim_stats[d] = dim_stats.get(d, 0) + 1
        self.logger.info(f"   📈 维度分布: {dim_stats}")

        self.logger.info("⏳ DeepSeek 评估中...")
        eval_result = evaluate_ai_cases(
            test['project'], test['module'], test['description'],
            cases, analysis, self._judge
        )

        pct = eval_result.get('percent_score', 0)
        self.logger.info(f"\n   📊 评分详情:")
        self.logger.info(f"      功能测试: {eval_result.get('function_score', 0)}/20")
        self.logger.info(f"      准确性测试: {eval_result.get('accuracy_score', 0)}/20")
        self.logger.info(f"      鲁棒性测试: {eval_result.get('robustness_score', 0)}/20")
        self.logger.info(f"      用户体验: {eval_result.get('ux_score', 0)}/20")
        self.logger.info(f"      安全性测试: {eval_result.get('security_score', 0)}/20")
        self.logger.info(f"      分析报告: {eval_result.get('analysis_score', 0)}/20")
        total = eval_result.get('total_score', 0)
        max_score = eval_result.get('max_score', 120)
        self.logger.info(f"   🏆 总分: {total}/{max_score} ({pct}%) {eval_result.get('grade', '')}")

        return {
            "test_name": test['name'],
            "project": test['project'],
            "module": test['module'],
            "module_name": test['name'],
            "cases_count": len(cases),
            "analysis_length": len(analysis),
            "dimension_distribution": dim_stats,
            "evaluation": eval_result,
            "percent_score": pct,
            "grade": eval_result.get('grade', ''),
            "strengths": eval_result.get('strengths', []),
            "weaknesses": eval_result.get('weaknesses', []),
            "elapsed": elapsed,
        }

    def run(self):
        self.print_header()
        agent = AITestAgent()

        for i, test in enumerate(self.TEST_SUITE, 1):
            self.print_module_start(i, len(self.TEST_SUITE),
                                    test['name'], test['project'], test['module'])

            try:
                t0 = time.time()
                self.logger.info("⏳ 调用智能体生成AI测试用例...")

                result = agent.generate(
                    project_name=test['project'],
                    module_name=test['module'],
                    description=test['description'],
                    limits=test['limits'],
                    need_analysis=True,
                    business_rules=""
                )
                elapsed = time.time() - t0

                cases = result.get("cases", [])
                analysis = result.get("analysis", "")

                self.logger.info(f"   ⏱️ 耗时: {elapsed:.2f}秒")
                self.logger.info(f"   📊 生成用例: {len(cases)}条")

                if not cases:
                    self.logger.info("   ❌ 未生成任何用例，跳过评估")
                    continue

                r = self.evaluate_single(test, cases, analysis, elapsed)
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
    evaluator = AIEvaluator()
    evaluator.run()


if __name__ == "__main__":
    main()
