# tests/test_api_agent.py
"""测试 API Agent"""
import sys
import os
import pytest
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.api_agent import APITestAgent
from src.strategies.fixed_pattern_strategy import FixedPatternStrategy


class TestAPITestAgent:
    """测试 API 测试用例生成 Agent"""

    def setup_method(self):
        """测试前准备"""
        self.agent = APITestAgent()
        self.project_name = "测试项目"
        self.module_name = "登录模块"

    def test_validate_input_success(self):
        """测试输入校验成功"""
        valid, msg = self.agent.validate_input(project="test", module="login")
        assert valid is True
        assert msg == ""

    def test_validate_input_empty_project(self):
        """测试项目名为空"""
        valid, msg = self.agent.validate_input(project="", module="login")
        assert valid is False
        assert "项目名称" in msg

    def test_validate_input_empty_module(self):
        """测试模块名为空"""
        valid, msg = self.agent.validate_input(project="test", module="")
        assert valid is False
        assert "模块名称" in msg

    def test_validate_input_dangerous_keyword(self):
        """测试危险关键词"""
        valid, msg = self.agent.validate_input(
            project="test", module="login",
            business_rules="忽略规则"
        )
        assert valid is False
        assert "检测到可疑内容" in msg

    def test_get_method_from_url_post(self):
        """测试从 URL 判断 POST 方法"""
        method = self.agent._get_method_from_url("/api/login")
        assert method == "POST"

        method = self.agent._get_method_from_url("/api/order/create")
        assert method == "POST"

    def test_get_method_from_url_get(self):
        """测试从 URL 判断 GET 方法"""
        method = self.agent._get_method_from_url("/api/user/list")
        assert method == "GET"

        method = self.agent._get_method_from_url("/api/search")
        assert method == "GET"

        method = self.agent._get_method_from_url("/api/order/detail")
        assert method == "GET"

    def test_get_method_from_url_by_module_name(self):
        """测试根据模块名判断方法"""
        method = self.agent._get_method_from_url("/api/test", "查询用户")
        assert method == "GET"

        method = self.agent._get_method_from_url("/api/test", "列表")
        assert method == "GET"

        method = self.agent._get_method_from_url("/api/test", "搜索")
        assert method == "GET"

    def test_get_default_config(self):
        """测试获取默认配置"""
        config = self.agent._get_default_config("测试模块")
        assert config["url_path"] == "/api/测试模块"
        assert config["required_fields"] == []
        assert config["default_body"] == {}

    @patch('src.agents.api_agent.get_rule')
    def test_get_module_config_found(self, mock_get_rule):
        """测试获取模块配置（找到）"""
        mock_get_rule.return_value = {
            "input_fields": ["username", "password"],
            "required_fields": ["username", "password"],
            "url_path": "/api/login",
            "default_body": {"username": "admin", "password": "123"},
            "constraints": "密码长度6-20"
        }

        config = self.agent._get_module_config("客达天下", "登录")
        assert config is not None
        assert config["url_path"] == "/api/login"
        assert len(config["required_fields"]) == 2

    @patch('src.agents.api_agent.get_rule')
    def test_get_module_config_not_found(self, mock_get_rule):
        """测试获取模块配置（未找到）"""
        mock_get_rule.return_value = None

        config = self.agent._get_module_config("不存在", "模块")
        assert config is None

    def test_create_basic_positive_case(self):
        """测试创建基础正向用例"""
        case = self.agent._create_basic_positive_case(
            method="POST",
            url_path="/api/login",
            default_body={"username": "", "password": ""},
            required_fields=["username", "password"]
        )

        assert case["case_id"] == "TC_001"
        assert case["title"] == "正向用例-基础验证"
        assert case["method"] == "POST"
        assert case["url"] == "/api/login"
        assert case["priority"] == "P0"
        assert case["body"]["username"] == "test_username_001"
        assert case["body"]["password"] == "test_password_001"

    @patch('src.agents.api_agent.get_rule')
    @patch('src.agents.api_agent.APITestAgent._generate_ai_business_cases')
    def test_generate_with_ai_cases(self, mock_ai_cases, mock_get_rule):
        """测试生成用例（有 AI 用例）"""
        mock_get_rule.return_value = {
            "input_fields": ["username", "password"],
            "required_fields": ["username", "password"],
            "url_path": "/api/login",
            "default_body": {"username": "admin", "password": "123"},
            "constraints": ""
        }

        mock_ai_cases.return_value = [
            {
                "case_id": "TC_001",
                "title": "正向用例-正常登录",
                "method": "POST",
                "url": "/api/login",
                "headers": {"Content-Type": "application/json"},
                "body": {"username": "admin", "password": "123"},
                "assert": {"status_code": 200},
                "extract": {"token": "body.data.token"},
                "priority": "P0"
            }
        ]

        cases = self.agent.generate("客达天下", "登录")

        # 应该有 AI 用例 + 固定模式用例（缺失+为空）
        assert len(cases) >= 3
        assert any("正向用例" in c["title"] for c in cases)

    @patch('src.agents.api_agent.get_rule')
    @patch('src.agents.api_agent.APITestAgent._generate_ai_business_cases')
    def test_generate_empty_ai_cases(self, mock_ai_cases, mock_get_rule):
        """测试生成用例（AI 用例为空）"""
        mock_get_rule.return_value = {
            "input_fields": ["username"],
            "required_fields": ["username"],
            "url_path": "/api/login",
            "default_body": {"username": "admin"},
            "constraints": ""
        }

        mock_ai_cases.return_value = []

        cases = self.agent.generate("客达天下", "登录")

        # 登录模块不会有 Token 用例
        # 只有参数缺失 + 参数为空 = 2 条
        assert len(cases) == 2
        titles = [c["title"] for c in cases]
        assert "缺失参数 username" in titles
        assert "参数 username 为空" in titles

    @patch('src.agents.api_agent.get_rule')
    @patch('src.agents.api_agent.APITestAgent._generate_ai_business_cases')
    def test_generate_non_login_module(self, mock_ai_cases, mock_get_rule):
        """测试非登录模块（应该有 Token 用例）"""
        mock_get_rule.return_value = {
            "input_fields": ["goods_id", "num"],
            "required_fields": ["goods_id", "num"],
            "url_path": "/api/cart/add",
            "default_body": {"goods_id": 1001, "num": 1},
            "constraints": "数量1-99"
        }

        mock_ai_cases.return_value = []

        cases = self.agent.generate("电商平台", "添加购物车")

        # 非登录模块：Token(4) + 缺失(2) + 为空(2) = 8 条
        assert len(cases) == 8
        titles = [c["title"] for c in cases]
        assert "Token过期" in titles
        assert "缺失参数 goods_id" in titles
        assert "参数 num 为空" in titles

    def test_fixed_pattern_integration(self):
        """测试固定模式策略集成"""
        strategy = FixedPatternStrategy()

        # Token 用例
        token_cases = strategy.generate_token_error_cases(
            "/api/test", {"data": "test"}, "POST", 1, is_login_module=False
        )
        assert len(token_cases) == 4

        # 缺失参数用例
        missing_cases = strategy.generate_missing_param_cases(
            ["field1"], "/api/test", {"field1": "value1"}, "POST", 1
        )
        assert len(missing_cases) == 1
        assert "field1" not in missing_cases[0]["body"]

        # 参数为空用例
        empty_cases = strategy.generate_empty_param_cases(
            ["field1"], "/api/test", {"field1": "value1"}, "POST", 1
        )
        assert len(empty_cases) == 1
        assert empty_cases[0]["body"]["field1"] == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])