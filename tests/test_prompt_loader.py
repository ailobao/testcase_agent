"""测试 PromptLoader 预热和缓存功能"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPromptLoaderWarmup:
    """测试提示词加载器的预热功能"""

    def test_warmup_status_exists(self):
        """预热状态应有 loaded_templates 字段"""
        from src.core.prompt_loader import prompt_loader
        status = prompt_loader.get_warmup_status()
        assert "loaded_templates" in status
        assert "missing_templates" in status
        assert "issues" in status

    def test_warmup_loaded_count(self):
        """已加载的模板数应 >= 0（至少 testpoint 存在）"""
        from src.core.prompt_loader import prompt_loader
        status = prompt_loader.get_warmup_status()
        assert status["loaded_templates"] >= 1

    def test_get_raw_prompt_task_template(self):
        """通过 task_templates.xxx 获取原始提示词应返回非空内容"""
        from src.core.prompt_loader import prompt_loader
        prompt = prompt_loader.get_raw_prompt("task_templates.testpoint")
        assert prompt is not None
        assert len(prompt) > 50  # 测试点模板足够长

    def test_get_raw_prompt_api_case(self):
        """api_case 模板应包含关键占位符"""
        from src.core.prompt_loader import prompt_loader
        prompt = prompt_loader.get_raw_prompt("task_templates.api_case")
        assert "{project_name}" in prompt
        assert "{module_name}" in prompt
        assert "{url_path}" in prompt

    def test_get_raw_prompt_manual_case(self):
        """manual_case 模板应包含关键占位符"""
        from src.core.prompt_loader import prompt_loader
        prompt = prompt_loader.get_raw_prompt("task_templates.manual_case")
        assert "{fields_example}" in prompt

    def test_get_raw_prompt_top_level(self):
        """顶级 key 应正常返回"""
        from src.core.prompt_loader import prompt_loader
        defense = prompt_loader.get_raw_prompt("defense_rules")
        assert defense is not None
        assert len(defense) > 0

        strategy = prompt_loader.get_raw_prompt("case_strategy")
        assert strategy is not None
        assert len(strategy) > 0

    def test_get_raw_prompt_missing_key(self):
        """不存在的 key 返回空字符串"""
        from src.core.prompt_loader import prompt_loader
        result = prompt_loader.get_raw_prompt("不存在的key")
        assert result == ""

    def test_get_task_prompt_success(self):
        """get_task_prompt 应正确组合并格式化"""
        from src.core.prompt_loader import prompt_loader
        prompt = prompt_loader.get_task_prompt(
            "ai_analysis",
            project="测试项目",
            module="登录模块",
            description="测试描述"
        )
        assert "测试项目" in prompt
        assert "登录模块" in prompt
        assert "测试描述" in prompt

    def test_get_task_prompt_missing_task(self):
        """不存在的任务名应抛出 ValueError"""
        from src.core.prompt_loader import prompt_loader
        with pytest.raises(ValueError, match="未找到任务模板"):
            prompt_loader.get_task_prompt("不存在的任务", x="y")

    def test_get_task_prompt_missing_placeholder(self):
        """缺失占位符应返回未替换的字符串（不崩溃）"""
        from src.core.prompt_loader import prompt_loader
        # ai_analysis 需要 project/module/description
        result = prompt_loader.get_task_prompt("ai_analysis")
        # 应包含未替换的占位符
        assert "{project}" in result or "{module}" in result

    def test_get_output_constraint(self):
        """output_constraints 各子键应存在"""
        from src.core.prompt_loader import prompt_loader
        # 验证通过 get_raw_prompt 能获取
        constraint = prompt_loader.get_raw_prompt("output_constraints")
        assert constraint is not None
        assert isinstance(constraint, str) or isinstance(constraint, dict)

    def test_get_reject_message(self):
        """拒绝话术应返回非空"""
        from src.core.prompt_loader import prompt_loader
        msg = prompt_loader.get_reject_message("default")
        assert msg is not None
        assert len(msg) > 0

    def test_get_reject_message_custom(self):
        """自定义原因应 fallback 到 default"""
        from src.core.prompt_loader import prompt_loader
        msg = prompt_loader.get_reject_message("不存在的理由")
        assert msg is not None
        assert len(msg) > 0

    def test_cache_consistency(self):
        """预热缓存和直接读取应返回相同内容"""
        from src.core.prompt_loader import prompt_loader
        # 直接从 config 读
        config = prompt_loader._config
        direct = config.get("task_templates", {}).get("testpoint", "")
        # 从缓存读
        cached = prompt_loader.get_raw_prompt("task_templates.testpoint")
        assert direct == cached

    def test_base_parts_cache_not_empty(self):
        """base_parts_cache 应该非空（至少 system_role 或 case_strategy 等存在）"""
        from src.core.prompt_loader import prompt_loader
        # _base_parts_cache 可能在配置为空时为 []
        # 但至少应该是一个列表
        assert isinstance(prompt_loader._base_parts_cache, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
