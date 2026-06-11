"""评估基类 — 公共基础设施"""
import os
import sys
import json
import time
import logging
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from abc import ABC, abstractmethod

# ====================== 运行环境检查 ======================
# 解决 Windows GBK 编码问题
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 重要：请用项目 venv 的 Python 运行，而非系统 Python
#   正确：.venv/Scripts/python evaluation/evaluate_xxx.py
#   错误：py -u evaluation/evaluate_xxx.py（缺少 deepeval 等依赖）
_expected_venv = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.venv')
if sys.prefix == sys.base_prefix and os.path.exists(_expected_venv):
    print(f"[Warning] 检测到不在 venv 中运行，请使用: {_expected_venv}/Scripts/python")

from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

# ====================== 路径修复 ======================
# 所有 evaluation/ 下的脚本都依赖项目根目录的 import
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

load_dotenv()


# ====================== DeepEval 模式专用 ======================

class JudgeLLM:
    """
    DeepEval 模式使用的 Judge LLM 包装。
    默认使用 deepseek-v3（DashScope 兼容接口），供 GEval 作为评估模型使用。
    可通过 JUDGE_MODEL 环境变量覆盖。
    """
    _model = None

    @classmethod
    def get_instance(cls):
        if cls._model is not None:
            return cls._model

        from deepeval.models.base_model import DeepEvalBaseLLM

        api_key = os.getenv("DASHSCOPE_API_KEY")
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"  # 固定 DashScope
        model_name = os.getenv("JUDGE_MODEL", "qwen3.7-plus")

        class _JudgeLLM(DeepEvalBaseLLM):
            def __init__(self):
                self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=120)
                self.model = model_name

            def load_model(self):
                return self.client

            def generate(self, prompt: str) -> str:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    max_tokens=2000
                )
                return response.choices[0].message.content

            async def a_generate(self, prompt: str) -> str:
                return self.generate(prompt)

            def get_model_name(self):
                return self.model

        cls._model = _JudgeLLM()
        return cls._model


# ====================== 直调 Judge 模式专用 ======================

def create_deepseek_judge(model: str = None) -> ChatOpenAI:
    """创建 DashScope Judge LLM（固定 DashScope）"""
    return ChatOpenAI(
        model=model or os.getenv("JUDGE_MODEL", "qwen3.7-plus"),
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",  # 固定 DashScope
        temperature=0,
        max_tokens=2000
    )


def parse_judge_json_response(response: str) -> Optional[Dict]:
    """
    解析 Judge LLM 的 JSON 响应。
    支持：
    - 纯 JSON
    - markdown 包裹的 JSON
    - 文本中嵌入的 JSON 对象（qwen-max 等模型输出）
    返回 dict 或 None。
    """
    import re
    content = response.strip()
    if not content:
        return None

    # 1. 清理 markdown 包裹后直接解析
    cleaned = re.sub(r'^```json\s*', '', content)
    cleaned = re.sub(r'```\s*$', '', cleaned)
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 2. 查找文本中的第一个完整 JSON 对象 {}（qwen-max 常输出叙述+JSON）
    #    从第一个 { 开始，找到括号平衡的 } 结束
    brace_start = cleaned.find('{')
    if brace_start >= 0:
        depth = 0
        for i in range(brace_start, len(cleaned)):
            ch = cleaned[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    try:
                        candidate = cleaned[brace_start:i + 1]
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        # 可能是嵌套 JSON，继续尝试更大范围
                        continue
        # 最后一个括号尝试
        try:
            candidate = cleaned[brace_start:]
            # 补上缺失的括号
            if depth > 0:
                candidate += '}' * depth
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    return None


# ====================== 基类 ======================

class BaseEvaluator(ABC):
    """
    评估基类 — 所有评估脚本共用此基类。

    子类只需定义：
    - eval_name / eval_description 类变量
    - TEST_SUITE 模块列表
    - _build_eval_prompt()     — 直调模式：构建评估 prompt
    - _parse_eval_result()     — 直调模式：解析 LLM 返回的评分
    - _run_single_eval()       — 完整跑一个模块的评估流程
    - run()                    — 主入口
    """

    # 评估元信息（子类覆盖）
    eval_name: str = "未命名评估"
    eval_description: str = ""
    eval_dimensions: List[str] = []

    def __init__(self):
        self.results: List[Dict] = []
        self.logger = self._setup_logger()

    # ====================== 日志 ======================

    def _setup_logger(self) -> logging.Logger:
        """配置日志器"""
        log_dir = os.path.join(_project_root, "logs")
        os.makedirs(log_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = os.path.join(log_dir, f"{self.eval_name}_{timestamp}.log")

        logger = logging.getLogger(f"eval_{self.eval_name}_{timestamp}")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()

        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(fh)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(ch)

        return logger

    # ====================== 打印 ======================

    def print_header(self):
        """打印评估标题"""
        self.logger.info("=" * 80)
        self.logger.info(f"🎯 {self.eval_name}")
        self.logger.info("=" * 80)
        self.logger.info(f"📅 评估时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"📊 测试模块数: {len(self.TEST_SUITE)}")
        if self.eval_dimensions:
            self.logger.info(f"📋 评估维度: {'、'.join(self.eval_dimensions)}")
        self.logger.info("=" * 80)

    def print_module_start(self, index: int, total: int, name: str, project: str, module: str):
        """打印模块评估开始"""
        self.logger.info(f"\n{'=' * 70}")
        self.logger.info(f"📝 [{index}/{total}] {name}")
        self.logger.info(f"   项目: {project}")
        self.logger.info(f"   模块: {module}")
        self.logger.info('=' * 70)

    def print_module_result(self, result: Dict):
        """打印单个模块的评估结果（子类可覆盖）"""
        cases_count = result.get('cases_count', result.get('content_length', 0))
        score = result.get('percent_score')
        grade = result.get('grade', '')
        elapsed = result.get('elapsed', 0)

        score_str = f"得分: {score}%" if score is not None else "评分: N/A"
        grade_str = f" ({grade})" if grade else ""
        self.logger.info(f"   ⏱️ 耗时: {elapsed:.2f}秒" if elapsed else "")
        self.logger.info(f"   📊 生成: {cases_count}")
        self.logger.info(f"   🏆 {score_str}{grade_str}")

        if result.get('strengths'):
            self.logger.info(f"   ✅ 优点: {'、'.join(result['strengths'][:3])}")
        if result.get('weaknesses'):
            self.logger.info(f"   ⚠️ 缺点: {'、'.join(result['weaknesses'][:3])}")

    def print_summary(self):
        """打印汇总报告"""
        successful = [r for r in self.results if r.get('percent_score') is not None]

        self.logger.info("\n" + "=" * 80)
        self.logger.info("📈 汇总报告")
        self.logger.info("=" * 80)

        if successful:
            avg_score = sum(r['percent_score'] for r in successful) / len(successful)
            self.logger.info(f"\n📊 有效评估: {len(successful)}/{len(self.results)} 个模块")
            self.logger.info(f"📊 平均综合得分: {avg_score:.1f}%")

            self.logger.info(f"\n📊 各模块得分:")
            for r in successful:
                score = r.get('percent_score', 0)
                grade = r.get('grade', '')
                name = r.get('module_name', r.get('name', ''))
                self.logger.info(f"   {name:12}: {score:5.1f}%  ({grade})")

        else:
            self.logger.info("   无有效评分结果")

    # ====================== 报告保存 ======================

    def save_report(self, extra: Dict = None):
        """保存 JSON 报告到 evaluation/data/"""
        report_dir = os.path.join(_project_root, "evaluation", "data")
        os.makedirs(report_dir, exist_ok=True)

        report = {
            "timestamp": datetime.now().isoformat(),
            "eval_name": self.eval_name,
            "total_modules": len(self.TEST_SUITE),
            "successful_count": len([r for r in self.results if r.get('percent_score') is not None]),
            "results": self.results,
        }
        if extra:
            report.update(extra)

        winner = [r for r in self.results if r.get('percent_score') is not None]
        if winner:
            report["avg_score"] = sum(r['percent_score'] for r in winner) / len(winner)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.eval_name}_{timestamp}.json"
        filepath = os.path.join(report_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        self.logger.info(f"\n✅ 详细报告已保存: {filepath}")

    # ====================== 直调 Judge 辅助 ======================

    def _create_judge(self) -> ChatOpenAI:
        """创建 DeepSeek Judge"""
        return create_deepseek_judge()

    def _judge(self, prompt: str) -> Optional[Dict]:
        """
        调用 LLM Judge 并解析 JSON 响应。
        支持 qwen-max / deepseek 等模型。
        返回 dict 或 None。
        """
        from langchain_core.messages import SystemMessage

        try:
            llm = self._create_judge()
            # 使用 SystemMessage 强约束输出格式（qwen-max 需要更明确的指示）
            system_msg = SystemMessage(
                content="你是一个评分助手。你的回答必须是一个合法的JSON对象，只输出JSON，不要包含任何markdown标记、解释文字或格式说明。"
            )
            response = llm.invoke([system_msg, HumanMessage(content=prompt)])
            result = parse_judge_json_response(response.content)
            if result is not None:
                return result

            # 兜底：第二次尝试，更简短的指令
            self.logger.warning("Judge 初次解析失败，尝试二次调用...")
            retry_prompt = (
                "请仅输出JSON格式的评分结果，不要输出任何其他内容：\n\n"
                + prompt
            )
            response2 = llm.invoke([HumanMessage(content=retry_prompt)])
            return parse_judge_json_response(response2.content)

        except Exception as e:
            self.logger.error(f"Judge 评估调用失败: {e}")
            return None

    # ====================== 子类必须实现 ======================

    @property
    @abstractmethod
    def TEST_SUITE(self) -> List[Dict]:
        """测试模块列表"""
        ...

    @abstractmethod
    def run(self):
        """运行评估"""
        ...
