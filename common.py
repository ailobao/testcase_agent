# common.py
import os
import re
import json
import yaml
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Tuple, Any, Optional, Dict, List
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

current_script_dir = os.path.dirname(os.path.abspath(__file__))
data_folder_path = os.path.join(current_script_dir, "data")
os.makedirs(data_folder_path, exist_ok=True)

# ======================
# LLM 配置
# ======================
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-v3")
LLM_API_KEY = os.getenv("DASHSCOPE_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "8000"))

# 调试模式
DEBUG_MODE = os.getenv("TEST_AGENT_DEBUG", "false").lower() == "true"

llm = ChatOpenAI(
    model=LLM_MODEL,
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
    temperature=LLM_TEMPERATURE,
    max_tokens=LLM_MAX_TOKENS
)


def debug_log(msg: str, data: Any = None):
    """调试日志，仅 DEBUG_MODE=True 时输出"""
    if DEBUG_MODE:
        print(f"[DEBUG] {msg}")
        if data is not None:
            print(f"       {data}")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_llm_with_retry(prompt):
    return llm.invoke([HumanMessage(content=prompt)])


# ======================
# Prompt 加载器
# ======================
class PromptLoader:
    """统一提示词加载器"""

    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._load_config()
        return cls._instance

    @classmethod
    def _load_config(cls):
        config_path = Path(__file__).parent / "prompts.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        with open(config_path, 'r', encoding='utf-8') as f:
            cls._config = yaml.safe_load(f)
        debug_log("prompts.yaml 加载成功")

    def get_system_role(self) -> str:
        return self._config.get("system_role", "")

    def get_priority_rules(self) -> str:
        return self._config.get("priority_rules", "")

    def get_case_strategy(self) -> str:
        return self._config.get("case_strategy", "")

    def get_task_prompt(self, task_name: str, **kwargs) -> str:
        """获取任务提示词"""
        template = self._config.get("task_templates", {}).get(task_name, "")
        if not template:
            raise ValueError(f"未找到任务模板: {task_name}")

        # 构建完整提示词
        parts = []
        parts.append(self.get_system_role())
        parts.append(self.get_priority_rules())
        parts.append(self.get_case_strategy())
        parts.append(template)
        parts.append(self.get_output_constraint(task_name))

        full_prompt = "\n\n".join([p for p in parts if p])

        # 格式化
        try:
            return full_prompt.format(**kwargs)
        except KeyError as e:
            debug_log(f"格式化参数缺失: {e}")
            return full_prompt

    def get_output_constraint(self, task_name: str) -> str:
        """获取输出格式约束"""
        mapping = {
            "testpoint": "testpoint",
            "manual_case": "manual_case",
            "api_case": "api_case",
            "ai_test_case": "ai_test_case"
        }
        key = mapping.get(task_name, "testpoint")
        return self._config.get("output_constraints", {}).get(key, "")

    def get_reject_message(self, reason: str = "default") -> str:
        """获取拒绝话术"""
        messages = self._config.get("reject_messages", {})
        return messages.get(reason, messages.get("default", "请稍后重试😊"))

    def get_defense_rules(self) -> str:
        """获取防御规则"""
        return self._config.get("defense_rules", "")


# ======================
# 输出校验器
# ======================
class OutputValidator:
    """输出格式校验器"""

    @staticmethod
    def validate_json(content: str) -> Tuple[bool, str, Optional[List]]:
        """
        校验是否为合法JSON
        返回: (是否成功, 错误信息, 解析后的对象)
        """
        # 去除可能的markdown标记
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*$', '', content)
        content = content.strip()

        if not content:
            return False, "输出为空", None

        if content[0] not in ['[', '{']:
            return False, "输出不是JSON格式（应以[或{开头）", None

        if '```' in content:
            return False, "输出包含markdown代码块标记", None

        try:
            data = json.loads(content)
            return True, "", data
        except json.JSONDecodeError as e:
            return False, f"JSON解析失败: {str(e)[:50]}", None

    @staticmethod
    def validate_markdown(content: str) -> Tuple[bool, str]:
        """校验是否为合法Markdown格式"""
        if not content:
            return False, "输出为空"

        # 检查是否有标题
        if not re.search(r'^##\s+', content, re.MULTILINE):
            return False, "输出不是Markdown格式（缺少##标题）"

        return True, ""

    @staticmethod
    def validate_manual_case_format(content: str) -> Tuple[bool, str, List]:
        """
        校验手工用例格式，并解析出用例列表
        返回: (是否成功, 错误信息, 用例列表)
        """
        # 复用原有的 parse_column_cases 逻辑
        from testcase_agent import parse_column_cases
        from testcase_agent import DEFAULT_FIELDS

        cases = parse_column_cases(content, DEFAULT_FIELDS)
        if not cases:
            return False, "未能解析出有效用例", []
        return True, "", cases

    @staticmethod
    def validate_case_count(cases: List, expected_min: int, is_positive: bool) -> Tuple[bool, str]:
        """校验用例数量是否符合策略"""
        actual = len(cases)

        if is_positive:
            # 正向用例应该少（场景数通常不超过10）
            if actual > max(expected_min * 2, 20):
                return False, f"正向用例({actual})数量异常，可能按参数展开而非按场景"
        else:
            # 反向用例应该多（参数错误值累加）
            if expected_min > 0 and actual < expected_min * 0.5:
                return False, f"反向用例({actual})少于预期({expected_min})，可能错误合并了"

        return True, ""


# ======================
# 通用工具函数
# ======================
def parse_markdown_to_cases(markdown_content):
    cases = []
    blocks = re.split(r'\n##\s+', markdown_content)
    for block in blocks:
        if not block.strip():
            continue
        case = {
            "测试ID": "", "测试标题": "", "测试类型": "", "模块/项目": "", "优先级": "P2",
            "前置条件": "", "测试数据": "", "测试步骤": "", "预期结果": "", "实际结果": "", "执行人": ""
        }
        lines = block.strip().split('\n')
        if lines:
            case["测试标题"] = lines[0].strip()
        full_text = " ".join(lines)
        title_match = re.search(r'-\s*测试标题[：:]\s*(.+?)(?=-\s*|\n|$)', full_text)
        if title_match:
            case["测试标题"] = title_match.group(1).strip()
        type_match = re.search(r'-\s*测试类型[：:]\s*(.+?)(?=-\s*|\n|$)', full_text)
        if type_match:
            case["测试类型"] = type_match.group(1).strip()
        module_match = re.search(r'-\s*模块/项目[：:]\s*(.+?)(?=-\s*|\n|$)', full_text)
        if module_match:
            case["模块/项目"] = module_match.group(1).strip()
        priority_match = re.search(r'-\s*优先级[：:]\s*(P[012])', full_text)
        if priority_match:
            case["优先级"] = priority_match.group(1)
        precond_match = re.search(r'-\s*前置条件[：:]\s*(.+?)(?=-\s*|\n|$)', full_text)
        case["前置条件"] = precond_match.group(1).strip() if precond_match else "无"
        data_match = re.search(r'-\s*测试数据[：:]\s*(.+?)(?=-\s*|\n|$)', full_text)
        if data_match:
            case["测试数据"] = data_match.group(1).strip()
        steps_match = re.search(r'-\s*测试步骤[：:]\s*(.+?)(?=-\s*预期结果|\n-\s*预期结果)', full_text, re.DOTALL)
        if steps_match:
            case["测试步骤"] = steps_match.group(1).strip()
        expected_match = re.search(r'-\s*预期结果[：:]\s*(.+?)(?=-\s*实际结果|\n-\s*实际结果|$)', full_text)
        if expected_match:
            case["预期结果"] = expected_match.group(1).strip()
        if case["测试标题"]:
            cases.append(case)
    return cases


def deduplicate_cases(cases):
    seen = set()
    unique = []
    for case in cases:
        key = f"{case.get('测试标题', '')}_{case.get('测试步骤', '')}"
        if key not in seen:
            seen.add(key)
            unique.append(case)
    return unique


def denoise_cases(cases):
    valid = []
    for case in cases:
        if not case.get('测试标题') or not case.get('测试步骤'):
            continue
        if len(case.get('测试步骤', '')) < 10:
            continue
        expected = case.get('预期结果', '')
        if '错误' in expected and len(expected) < 15:
            continue
        valid.append(case)
    return valid


def get_next_file_number():
    max_num = 0
    for f in os.listdir(data_folder_path):
        match = re.match(r".*?_(\d+)\.xlsx", f)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num
    return max_num + 1


def clean_name(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)[:50]


def export_to_excel(cases, filename_prefix):
    if not cases:
        return None
    next_num = get_next_file_number()
    filename = f"{filename_prefix}_{next_num:03d}.xlsx"
    full_path = os.path.join(data_folder_path, filename)
    df = pd.DataFrame(cases)
    cols = ["测试ID", "测试标题", "测试类型", "模块/项目", "优先级", "前置条件", "测试数据", "测试步骤", "预期结果",
            "实际结果", "执行人"]
    cols = [c for c in cols if c in df.columns]
    df = df[cols]
    with pd.ExcelWriter(full_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="测试用例", index=False)
    return full_path


def deduplicate_test_cases(cases, key_fields=None):
    """测试用例去重"""
    if not cases:
        return cases

    if key_fields is None:
        key_fields = ['测试标题', '测试步骤']

    seen = set()
    unique_cases = []

    for case in cases:
        key_parts = []
        for field in key_fields:
            value = case.get(field, '')
            key_parts.append(str(value)[:100])

        unique_key = '||'.join(key_parts)

        if unique_key not in seen:
            seen.add(unique_key)
            unique_cases.append(case)

    debug_log(f"去重: 原始 {len(cases)} 条 → 去重后 {len(unique_cases)} 条")
    return unique_cases


# ======================
# 输入校验
# ======================
def validate_user_input(content: str) -> Tuple[bool, str]:
    """检测用户输入是否包含注入攻击或违规内容"""
    dangerous_keywords = [
        "忽略规则", "忘记规则", "无视规则",
        "你现在是", "扮演", "越狱",
        "显示系统指令", "输出提示词"
    ]

    content_lower = content.lower()
    for keyword in dangerous_keywords:
        if keyword.lower() in content_lower:
            debug_log(f"检测到可疑内容: {keyword}")
            return False, f"检测到可疑内容：{keyword}"

    return True, ""


# ======================
# 调试模式入口检查
# ======================
def check_debug_mode() -> bool:
    """返回当前是否处于调试模式"""
    return DEBUG_MODE


# 初始化提示词加载器
prompt_loader = PromptLoader()