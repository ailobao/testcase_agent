# tests/test_fixed_pattern_strategy.py
"""测试固定模式策略"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.strategies.fixed_pattern_strategy import FixedPatternStrategy


class TestFixedPatternStrategy:
    """测试固定模式用例生成器"""

    def setup_method(self):
        self.strategy = FixedPatternStrategy()
        self.url_path = "/api/test"
        self.body_data = {"username": "admin", "password": "123456"}
        self.method = "POST"
        self.required_fields = ["username", "password"]

    def test_generate_all_fixed_cases_for_login(self):
        """测试登录模块（不生成 Token 用例）"""
        cases = self.strategy.generate_all_fixed_cases(
            self.required_fields, self.url_path, self.body_data,
            self.method, 1, is_login_module=True
        )

        # 登录模块：4 Token + 2 缺失 + 2 为空 = 8 条？
        # 不对！is_login_module=True 时 Token 用例为 0
        # 所以应该是 0 + 2 + 2 = 4 条
        assert len(cases) == 4
        assert self.strategy.get_count() == 4

        # 验证没有 Token 用例
        titles = [c["title"] for c in cases]
        assert "Token过期" not in titles
        assert "缺失参数" in titles[0]
    def test_token_error_cases(self):
        """测试生成 Token 异常用例"""
        cases = self.strategy.generate_token_error_cases(
            self.url_path, self.body_data, self.method, 1, is_login_module=False
        )

        assert len(cases) == 4
        assert cases[0]["title"] == "Token过期"
        assert cases[1]["title"] == "Token错误"
        assert cases[2]["title"] == "Token为空"
        assert cases[3]["title"] == "缺失Token"
        assert cases[0]["case_id"] == "TC_001"
        assert cases[3]["case_id"] == "TC_004"

    def test_token_error_cases_for_login(self):
        """测试登录模块不生成 Token 用例"""
        cases = self.strategy.generate_token_error_cases(
            self.url_path, self.body_data, self.method, 1, is_login_module=True
        )
        assert cases == []

    def test_missing_param_cases(self):
        """测试生成参数缺失用例"""
        cases = self.strategy.generate_missing_param_cases(
            self.required_fields, self.url_path, self.body_data, self.method, 1
        )

        assert len(cases) == 2
        assert cases[0]["title"] == "缺失参数 username"
        assert cases[1]["title"] == "缺失参数 password"
        assert "username" not in cases[0]["body"]
        assert "password" not in cases[1]["body"]

    def test_empty_param_cases(self):
        """测试生成参数为空用例"""
        cases = self.strategy.generate_empty_param_cases(
            self.required_fields, self.url_path, self.body_data, self.method, 1
        )

        assert len(cases) == 2
        assert cases[0]["title"] == "参数 username 为空"
        assert cases[1]["title"] == "参数 password 为空"
        assert cases[0]["body"]["username"] == ""
        assert cases[1]["body"]["password"] == ""

    def test_generate_all_fixed_cases(self):
        """测试生成所有固定模式用例"""
        cases = self.strategy.generate_all_fixed_cases(
            self.required_fields, self.url_path, self.body_data,
            self.method, 1, is_login_module=False
        )

        # 4 Token + 2 缺失 + 2 为空 = 8 条
        assert len(cases) == 8
        assert self.strategy.get_count() == 8

    def test_reset_count(self):
        """测试重置计数"""
        self.strategy.generate_all_fixed_cases(
            self.required_fields, self.url_path, self.body_data,
            self.method, 1, is_login_module=False
        )
        assert self.strategy.get_count() == 8

        self.strategy.reset_count()
        assert self.strategy.get_count() == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])