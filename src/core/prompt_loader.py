"""统一提示词加载器 — 支持启动时预热和模板验证"""
import os
import yaml
import logging
from typing import Dict, Any, List, Tuple

# 获取项目根目录
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
PROMPTS_FILE = os.path.join(project_root, "prompts.yaml")

logger = logging.getLogger("main")

# 预期的任务模板清单（启动时校验完整性）
EXPECTED_TASK_TEMPLATES = [
    "testpoint",
    "api_case",
    "manual_case",
    "ai_analysis",
    "ai_test_case",
]

# 预期必须存在的顶级配置键
EXPECTED_REQUIRED_TOP_KEYS = [
    "defense_rules",
    "case_strategy",
    "output_constraints",
    "reject_messages",
    "task_templates",
]

# 可选配置键（有则加载，无则跳过）
EXPECTED_OPTIONAL_TOP_KEYS = [
    "system_role",
    "priority_rules",
]


class PromptLoader:
    """统一提示词加载器 - 单例模式，支持启动时预热"""

    _instance = None
    _config = None

    # 预热缓存
    _template_cache: Dict[str, str] = {}         # task_name -> template
    _base_parts_cache: List[str] = []             # 预组合的 system_role + priority_rules + case_strategy
    _warmup_status: Dict[str, Any] = {}           # 预热状态报告

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """加载配置文件"""
        if not os.path.exists(PROMPTS_FILE):
            raise FileNotFoundError(f"配置文件不存在: {PROMPTS_FILE}")

        with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)

        if self._config is None:
            raise ValueError(f"配置文件为空: {PROMPTS_FILE}")

        # 启动时预热
        self._warmup()

    # ====================== 预热 ======================

    def _warmup(self):
        """启动时预热：验证模板完整性，预组合高频片段"""
        issues: List[str] = []
        stats = {"loaded_templates": 0, "missing_templates": [], "issues": issues}

        # 1. 验证必须存在的顶级键
        for key in EXPECTED_REQUIRED_TOP_KEYS:
            if key not in self._config:
                issues.append(f"缺少顶级配置: {key}")

        # 可选键仅 debug 日志
        for key in EXPECTED_OPTIONAL_TOP_KEYS:
            if key not in self._config:
                logger.debug(f"可选配置不存在（正常）: {key}")

        # 2. 验证并缓存任务模板
        task_templates = self._config.get("task_templates", {})
        for name in EXPECTED_TASK_TEMPLATES:
            template = task_templates.get(name, "")
            if not template:
                stats["missing_templates"].append(name)
                issues.append(f"缺少任务模板: task_templates.{name}")
            else:
                self._template_cache[name] = template
                stats["loaded_templates"] += 1

        # 3. 预组合 get_task_prompt 的公共片段
        base_parts = []
        for key in ["system_role", "priority_rules", "case_strategy"]:
            val = self._config.get(key, "")
            if val:
                base_parts.append(val)
        self._base_parts_cache = base_parts

        # 4. 验证 output_constraints 子键
        output_cons = self._config.get("output_constraints", {})
        expected_cons = ["testpoint", "manual_case", "api_case", "ai_test_case", "ai_analysis"]
        for con in expected_cons:
            if con not in output_cons:
                issues.append(f"缺少输出约束: output_constraints.{con}")

        self._warmup_status = stats

        if issues:
            for msg in issues:
                logger.warning(f"提示词配置问题: {msg}")
        else:
            logger.info(
                f"提示词预热完成: {stats['loaded_templates']}/{len(EXPECTED_TASK_TEMPLATES)} 模板已缓存"
            )

    def get_warmup_status(self) -> Dict[str, Any]:
        """获取预热状态报告"""
        return dict(self._warmup_status)

    # ====================== 原始提示词获取 ======================

    def get_raw_prompt(self, key: str) -> str:
        """
        获取原始提示词（不做任何加工，不添加 system_role/priority_rules 等）

        支持两种格式：
        - "task_templates.testpoint" -> 获取 task_templates 下的 testpoint
        - "defense_rules" -> 直接获取顶级 key
        """
        if key.startswith("task_templates."):
            actual_key = key.replace("task_templates.", "")
            # 优先从预热缓存读取
            cached = self._template_cache.get(actual_key)
            if cached is not None:
                return cached
            return self._config.get("task_templates", {}).get(actual_key, "")

        return self._config.get(key, "")

    # ====================== 各配置段获取 ======================

    def get_system_role(self) -> str:
        return self._config.get("system_role", "")

    def get_priority_rules(self) -> str:
        return self._config.get("priority_rules", "")

    def get_case_strategy(self) -> str:
        return self._config.get("case_strategy", "")

    def get_defense_rules(self) -> str:
        return self._config.get("defense_rules", "")

    # ====================== 任务提示词组合 ======================

    def get_task_prompt(self, task_name: str, **kwargs) -> str:
        """
        获取任务提示词（使用预热缓存组合，避免重复拼接）
        """
        # 从预热缓存获取模板
        template = self._template_cache.get(task_name)
        if template is None:
            template = self._config.get("task_templates", {}).get(task_name, "")
        if not template:
            raise ValueError(f"未找到任务模板: {task_name}")

        # 使用预热缓存的 base_parts
        parts = list(self._base_parts_cache)
        parts.append(template)

        output_constraint = self._get_output_constraint(task_name)
        if output_constraint:
            parts.append(output_constraint)

        full_prompt = "\n\n".join(parts)

        try:
            return full_prompt.format(**kwargs)
        except KeyError as e:
            logger.warning(f"提示词格式化参数缺失: {e}, task={task_name}")
            # 剥离残留的 {placeholder}，避免损坏模板传给 LLM
            import re
            return re.sub(r'\{[^}]*\}', '', full_prompt)

    def _get_output_constraint(self, task_name: str) -> str:
        mapping = {
            "testpoint": "testpoint",
            "manual_case": "manual_case",
            "api_case": "api_case",
            "ai_test_case": "ai_test_case",
            "ai_analysis": "ai_analysis",
        }
        key = mapping.get(task_name, "testpoint")
        return self._config.get("output_constraints", {}).get(key, "")

    # ====================== 拒绝话术 ======================

    def get_reject_message(self, reason: str = "default") -> str:
        messages = self._config.get("reject_messages", {})
        return messages.get(reason, messages.get("default", "请稍后重试😊"))

    # ====================== 兼容旧接口 ======================

    def get_task_prompt_sync(self, task_name: str, **kwargs) -> str:
        """同步兼容方法"""
        return self.get_task_prompt(task_name, **kwargs)


prompt_loader = PromptLoader()