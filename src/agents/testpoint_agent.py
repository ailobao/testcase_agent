"""测试点分析 Agent — 统一错误处理"""
import sys
import os
import re
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from src.core.prompt_loader import prompt_loader
from src.agents.base_agent import BaseAgent
from src.core.logger import main_logger, debug_log
from src.utils.trace import get_trace_id


# 将项目根目录添加到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# 输出目录
OUTPUT_DIR = os.path.join(project_root, "testpoint_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


class TestPointAgent(BaseAgent):
    """测试点分析 Agent"""

    def __init__(self):
        super().__init__()

    def generate(self, project: str, module: str, rules: str, examples: str = "") -> Tuple[
        Optional[str], Optional[str]]:
        """
        生成测试点分析

        返回:
            (content, None)    — 成功
            (None, error_msg)  — 失败
        """
        # 开始追踪
        trace_id = self.start_trace()
        main_logger.info(f"开始生成测试点: {project}/{module} (trace_id: {trace_id})")

        # 1. 输入校验
        valid, msg = self.validate_business_rules(rules)
        if not valid:
            debug_log(f"业务规则校验失败: {msg}")
            self.end_trace()
            return None, msg

        # 2. 构建提示词（保护 KeyError）
        try:
            prompt_template = prompt_loader.get_raw_prompt("task_templates.testpoint")
            if not prompt_template:
                self.end_trace()
                return None, "提示词模板为空: task_templates.testpoint"

            prompt = prompt_template.format(
                project=project or "未知项目",
                module=module or "未知模块",
                rules=rules if rules else "无特殊规则",
                examples=examples or "",
            )
        except KeyError as e:
            main_logger.error(f"提示词模板缺少占位符: {e}")
            self.end_trace()
            return None, f"提示词模板配置错误，缺少占位符: {e}"

        main_logger.info(f"提示词长度: {len(prompt)}")

        # 3. 调用 LLM
        try:
            response = self.safe_llm_call(prompt, default_return="")
            if not response:
                main_logger.warning("LLM 返回为空，使用降级内容")
                fallback = self._create_fallback_content(project, module, rules)
                saved_path = self._save_file(fallback, project, module)
                if saved_path:
                    main_logger.info(f"降级测试点已保存: {saved_path}")
                self.end_trace()
                return fallback, None

            content = response.replace("```markdown", "").replace("```", "").strip()

            # 4. 保存文件（保存失败不中断流程）
            saved_path = self._save_file(content, project, module)
            if saved_path:
                main_logger.info(f"测试点已保存: {saved_path}")
            else:
                main_logger.warning("测试点文件保存失败，仍返回内容")

            # 5. 统计
            lines = content.split('\n')
            testpoint_count = sum(1 for line in lines if line.strip().startswith('-'))
            main_logger.info(f"共生成 {testpoint_count} 条测试点")

            self.end_trace()
            return content, None

        except Exception as e:
            main_logger.error(f"生成失败: {type(e).__name__}: {e}")
            self.end_trace()
            # 尝试生成降级内容兜底
            try:
                fallback = self._create_fallback_content(project, module, rules)
                return fallback, None
            except Exception:
                return None, f"生成失败: {e}"

    def check_info_completeness(self, project: str, module: str, rules: str) -> Tuple[bool, List[str]]:
        """
        判断信息是否充足

        返回:
        - (是否需要追问, 问题列表)
        """
        # 规则1：业务规则为空或只有默认值
        if not rules or rules == "无特殊规则" or rules.strip() == "":
            # 根据项目名称匹配常见产品
            if "美团" in project or "外卖" in project or "闪购" in project or "到店" in project:
                questions = [
                    "您测试的是美团哪条业务线？（外卖/闪购/到店餐饮/到店综合/酒店旅行/美团优选/小象超市）",
                    "该业务线的订单有哪些特殊规则？（例如：未支付外卖订单15分钟后自动取消、骑手送达即完成、到店订单需核销券码等）"
                ]
                return True, questions
            elif "抖音" in project:
                questions = [
                    "测试的是抖音哪个业务模块？（购物车/订单列表/直播订单/退款售后）",
                    "该模块有哪些特殊规则？（例如：购物车限购数量、优惠券分摊逻辑、评价字数下限等）"
                ]
                return True, questions
            elif "流利说" in project or "英语" in project:
                questions = [
                    "测试的是流利说哪个模块？（定级测试/课程学习/配音课/真人PK/打卡/错题本）",
                    "该模块有哪些特殊规则？（例如：定级测试20题5分钟、录音最长60秒、打卡连续奖励等）"
                ]
                return True, questions
            elif "微信小程序" in project or "小程序" in project:
                questions = [
                    "小程序的主要业务场景是什么？（电商/点餐/预约/工具/营销）",
                    "是否依赖微信授权登录、支付、地理位置等能力？"
                ]
                return True, questions
            else:
                questions = [
                    "这个App/系统属于什么类型？（电商/社交/金融/教育/生活服务/工具）",
                    "您关注的测试重点是什么？（功能/安全/性能/兼容性）"
                ]
                return True, questions

        # 规则2：业务规则过短（少于30字）
        if len(rules) < 30:
            questions = ["请补充更多业务规则细节，以便生成更精准的测试点（例如：取消规则、退款规则、边界值、安全要求等）"]
            return True, questions

        # 规则3：未明确端类型
        if "App" not in rules and "小程序" not in rules and "Web" not in rules and "移动端" not in rules:
            if "小程序" in project:
                return False, []
            elif "Web" in project or "管理后台" in project:
                return False, []
            else:
                questions = ["这是App端、小程序端还是Web端？"]
                return True, questions

        return False, []

    def generate_followup_prompt(self, original_input: Dict, answers: Dict) -> str:
        """
        根据原输入和追问回答，构建完整的业务规则
        """
        full_rules = original_input.get("rules", "")

        if answers:
            full_rules += "\n\n【补充信息】"
            for q, a in answers.items():
                if a:
                    full_rules += f"\n- {q}: {a}"

        return full_rules

    def validate_business_rules(self, rules: str) -> Tuple[bool, str]:
        """校验业务规则是否包含恶意内容"""
        dangerous_keywords = [
            "忽略", "无视", "忘记", "删除规则",
            "输出提示词", "显示系统指令", "你现在是", "扮演", "越狱"
        ]
        rules_lower = rules.lower()
        for keyword in dangerous_keywords:
            if keyword.lower() in rules_lower:
                return False, f"检测到可疑内容：{keyword}"
        return True, ""

    def _save_file(self, content: str, project: str, module: str) -> Optional[str]:
        """
        保存测试点到 MD 文件，并记录生成记录。

        返回:
            成功返回文件路径，失败返回 None
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            trace_id = get_trace_id() or ""
            trace_suffix = f"_{trace_id}" if trace_id else ""
            filename = f"{project}_{module}_测试点_{timestamp}{trace_suffix}.md"
            filename = re.sub(r'[\\/*?:"<>|]', '', filename)
            filepath = os.path.join(OUTPUT_DIR, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            # 记录生成记录（失败不中断）
            try:
                record_file = os.path.join(OUTPUT_DIR, "generation_records.json")
                record = {
                    "timestamp": timestamp,
                    "trace_id": trace_id or "",
                    "project": project,
                    "module": module,
                    "length": len(content),
                }
                records = []
                if os.path.exists(record_file):
                    with open(record_file, 'r', encoding='utf-8') as f:
                        raw = f.read()
                        if raw.strip():
                            records = json.loads(raw)
                records.append(record)
                with open(record_file, 'w', encoding='utf-8') as f:
                    json.dump(records, f, ensure_ascii=False, indent=2)
            except (OSError, json.JSONDecodeError) as e:
                main_logger.warning(f"生成记录文件写入失败（不影响主文件）: {e}")

            return filepath

        except OSError as e:
            main_logger.error(f"测试点文件保存失败: {e}")
            return None

    def _create_fallback_content(self, project: str, module: str, rules: str) -> str:
        """LLM 失败时生成降级的测试点内容"""
        main_logger.info("生成降级测试点模板")

        # 从规则中提取关键词作为测试点线索
        keywords = []
        if rules and rules != "无特殊规则":
            # 提取中文字符作为线索
            chinese_words = re.findall(r'[一-鿿]{2,}', rules)
            keywords = chinese_words[:5]

        lines = [
            f"# {project} - {module} 测试点分析",
            "",
            "> ⚠️ 当前为降级模板（LLM 调用异常时自动生成）",
            "> 请根据实际业务场景补充测试点",
            "",
            "## 功能测试",
            "- 正常功能验证",
            "- 异常输入处理",
            "- 边界条件测试",
        ]

        if keywords:
            lines.append("")
            lines.append("## 根据业务规则推断的测试点")
            for kw in keywords:
                lines.append(f"- {kw}相关测试")

        lines.append("")
        lines.append("## 兼容性测试")
        lines.append("- 不同浏览器/设备验证")
        lines.append("")
        lines.append("## 安全测试")
        lines.append("- 权限验证")
        lines.append("- 数据安全")
        lines.append("")
        lines.append("---")
        lines.append(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        return "\n".join(lines)