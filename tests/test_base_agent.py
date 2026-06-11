# tests/test_base_agent.py
"""测试基类"""
import sys
import os
import pytest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.base_agent import BaseAgent
from src.utils.common_tools import safe_call


class ConcreteAgent(BaseAgent):
    """具体 Agent 实现（用于测试）"""

    def generate(self, **kwargs):
        return {"status": "success", "data": kwargs}


class TestBaseAgent:
    """测试基类"""

    def setup_method(self):
        """测试前准备"""
        self.agent = ConcreteAgent()

    def test_generate_method(self):
        """测试 generate 方法"""
        result = self.agent.generate(project="test", module="login")
        assert result["status"] == "success"
        assert result["data"]["project"] == "test"

    def test_validate_input_default(self):
        """测试默认输入校验"""
        valid, msg = self.agent.validate_input()
        assert valid is True
        assert msg == ""

    def test_post_process_default(self):
        """测试默认后处理"""
        result = self.agent.post_process({"data": "test"})
        assert result == {"data": "test"}

    def test_log_methods(self):
        """测试日志方法（不抛异常即可）"""
        try:
            self.agent.log_error("test_step", Exception("测试错误"), "test_context")
            self.agent.log_warning("test_step", "测试警告")
            self.agent.log_info("test_step", "测试信息")
        except Exception as e:
            pytest.fail(f"日志方法抛异常: {e}")

    @patch('src.agents.base_agent.safe_call')
    def test_safe_llm_call(self, mock_safe_call):
        """测试安全 LLM 调用"""
        mock_safe_call.return_value = "LLM响应内容"

        result = self.agent.safe_llm_call("测试提示词", default_return="")
        assert result == "LLM响应内容"

    @patch('src.utils.json_parser.universal_json_parse')
    @patch('src.agents.base_agent.BaseAgent.safe_llm_call')
    def test_safe_llm_json_call_success(self, mock_safe_llm_call, mock_universal_json_parse):
        """测试成功解析 JSON"""
        mock_safe_llm_call.return_value = '[{"case_id": "TC_001"}]'
        mock_universal_json_parse.return_value = [{"case_id": "TC_001"}]

        result = self.agent.safe_llm_json_call("测试提示词")
        assert len(result) == 1
        assert result[0]["case_id"] == "TC_001"

    @patch('src.agents.base_agent.BaseAgent.safe_llm_call')
    def test_safe_llm_json_call_empty_response(self, mock_safe_llm_call):
        """测试空响应"""
        mock_safe_llm_call.return_value = ""

        def fallback():
            return [{"fallback": True}]

        result = self.agent.safe_llm_json_call("测试提示词", fallback)
        assert result == [{"fallback": True}]

    @patch('src.utils.json_parser.universal_json_parse')
    @patch('src.agents.base_agent.BaseAgent.safe_llm_call')
    def test_safe_llm_json_call_parse_failure(self, mock_safe_llm_call, mock_universal_json_parse):
        """测试解析失败"""
        mock_safe_llm_call.return_value = "invalid json"
        mock_universal_json_parse.return_value = []

        def fallback():
            return [{"fallback": True}]

        result = self.agent.safe_llm_json_call("测试提示词", fallback)
        assert result == [{"fallback": True}]

    def test_merge_rules(self):
        """测试规则合并"""
        db_rule = {
            "input_fields": ["username", "password"],
            "constraints": "密码长度6-20"
        }
        user_rules = "验证码固定8888"

        result = self.agent._merge_rules(db_rule, user_rules)
        assert "输入字段只能是" in result
        assert "密码长度6-20" in result
        assert "验证码固定8888" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])