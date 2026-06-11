# tests/test_common_tools.py
"""测试公共工具函数"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.common_tools import (
    deduplicate_cases,
    clean_name,
    ensure_dict_field,
    get_max_case_id,
    fix_case_id,
    renumber_cases,
    normalize_assert,
    get_business_scenarios,
    extract_user_params,
    safe_call
)


class TestDeduplicateCases:
    """测试用例去重"""

    def test_deduplicate_by_title(self):
        """测试基于标题去重"""
        cases = [
            {"title": "测试1", "body": {}},
            {"title": "测试1", "body": {}},
            {"title": "测试2", "body": {}}
        ]
        result = deduplicate_cases(cases)
        assert len(result) == 2

    def test_deduplicate_by_body_field(self):
        """测试基于 body 字段去重"""
        cases = [
            {"title": "测试", "body": {"username": "admin"}},
            {"title": "测试", "body": {"username": "admin"}},
            {"title": "测试", "body": {"username": "user"}}
        ]
        result = deduplicate_cases(cases)
        assert len(result) == 2

    def test_deduplicate_with_empty_key_fields(self):
        """测试空 key_fields"""
        cases = [
            {"title": "测试1", "body": {"username": "admin"}},
            {"title": "测试1", "body": {"username": "user"}},
            {"title": "测试2", "body": {"username": "admin"}}
        ]
        result = deduplicate_cases(cases, key_fields=[])
        assert len(result) == 2

    def test_no_duplicates(self):
        """测试无重复用例"""
        cases = [
            {"title": "测试1", "body": {}},
            {"title": "测试2", "body": {}}
        ]
        result = deduplicate_cases(cases)
        assert len(result) == 2

    def test_empty_list(self):
        """测试空列表"""
        result = deduplicate_cases([])
        assert result == []


class TestCleanName:
    """测试文件名清理"""

    def test_remove_invalid_chars(self):
        """测试移除非法字符"""
        assert clean_name("test/file:name") == "testfilename"
        assert clean_name("a?b*c|d") == "abcd"
        assert clean_name('test"name') == "testname"
        assert clean_name("test<name>") == "testname"

    def test_empty_name(self):
        """测试空名称"""
        assert clean_name("") == "unknown"

    def test_max_length(self):
        """测试长度限制"""
        long_name = "a" * 100
        assert len(clean_name(long_name)) == 50

    def test_none_input(self):
        """测试 None 输入"""
        assert clean_name(None) == "unknown"


class TestEnsureDictField:
    """测试字典字段确保"""

    def test_none_value(self):
        """测试 None 值"""
        assert ensure_dict_field(None) == {}
        assert ensure_dict_field(None, {"default": True}) == {"default": True}

    def test_dict_value(self):
        """测试字典值"""
        assert ensure_dict_field({"a": 1}) == {"a": 1}

    def test_string_value(self):
        """测试字符串值"""
        assert ensure_dict_field('{"a": 1}') == {"a": 1}
        assert ensure_dict_field("invalid json") == {}

    def test_other_types(self):
        """测试其他类型"""
        assert ensure_dict_field(123) == {}
        assert ensure_dict_field([1, 2, 3]) == {}
        assert ensure_dict_field(True) == {}


class TestCaseId:
    """测试用例编号相关函数"""

    def test_get_max_case_id(self):
        """测试获取最大编号"""
        cases = [
            {"case_id": "TC_001"},
            {"case_id": "TC_005"},
            {"case_id": "TC_003"}
        ]
        assert get_max_case_id(cases) == 5

    def test_get_max_case_id_with_different_prefix(self):
        """测试不同前缀"""
        cases = [
            {"case_id": "API_001"},
            {"case_id": "API_010"},
            {"case_id": "API_005"}
        ]
        assert get_max_case_id(cases, prefix="API_") == 10

    def test_get_max_case_id_empty(self):
        """测试空列表"""
        assert get_max_case_id([]) == 0

    def test_get_max_case_id_no_match(self):
        """测试无匹配编号"""
        cases = [
            {"case_id": "ABC"},
            {"case_id": "DEF"}
        ]
        assert get_max_case_id(cases) == 0

    def test_fix_case_id(self):
        """测试修复编号"""
        cases = [{"case_id": ""}, {"case_id": ""}]
        result = fix_case_id(cases, start_id=1)
        assert result[0]["case_id"] == "TC_001"
        assert result[1]["case_id"] == "TC_002"

    def test_fix_case_id_with_custom_prefix(self):
        """测试自定义前缀"""
        cases = [{"case_id": ""}]
        result = fix_case_id(cases, start_id=5, prefix="API_")
        assert result[0]["case_id"] == "API_005"

    def test_renumber_cases(self):
        """测试重新编号"""
        cases = [{"case_id": "TC_999"}, {"case_id": "TC_888"}]
        result = renumber_cases(cases, start=1)
        assert result[0]["case_id"] == "TC_001"
        assert result[1]["case_id"] == "TC_002"

    def test_renumber_cases_custom_prefix(self):
        """测试自定义前缀重新编号"""
        cases = [{"case_id": "API_999"}, {"case_id": "API_888"}]
        result = renumber_cases(cases, prefix="API_", start=10)
        assert result[0]["case_id"] == "API_010"
        assert result[1]["case_id"] == "API_011"


class TestNormalizeAssert:
    """测试断言规范化"""

    def test_get_method_default(self):
        """测试 GET 方法默认断言"""
        result = normalize_assert({}, "GET")
        assert result == {"status_code": 200}

    def test_post_method_default(self):
        """测试 POST 方法默认断言"""
        result = normalize_assert({}, "POST")
        assert result == {"status_code": 200, "body.code": 200, "body.msg": "操作成功"}

    def test_preserve_existing(self):
        """测试保留已有断言"""
        result = normalize_assert({"status_code": 404}, "POST")
        assert result["status_code"] == 404
        assert result["body.code"] == 404
        assert result["body.msg"] == "资源不存在"

    def test_401_response(self):
        """测试 401 响应"""
        result = normalize_assert({"status_code": 401}, "POST")
        assert result["body.code"] == 401
        assert result["body.msg"] == "认证失败"

    def test_put_method(self):
        """测试 PUT 方法"""
        result = normalize_assert({}, "PUT")
        assert result["body.code"] == 200
        assert result["body.msg"] == "操作成功"

    def test_delete_method(self):
        """测试 DELETE 方法"""
        result = normalize_assert({}, "DELETE")
        assert result["body.code"] == 200
        assert result["body.msg"] == "操作成功"


class TestGetBusinessScenarios:
    """测试业务场景获取"""

    def test_login_module(self):
        """测试登录模块"""
        result = get_business_scenarios("登录", True)
        assert "用户名不存在" in result
        assert "密码错误" in result

    def test_add_module(self):
        """测试新增模块"""
        result = get_business_scenarios("新增课程", False)
        assert "重复创建" in result

    def test_delete_module(self):
        """测试删除模块"""
        result = get_business_scenarios("删除合同", False)
        assert "删除不存在的记录" in result

    def test_update_module(self):
        """测试修改模块"""
        result = get_business_scenarios("修改订单", False)
        assert "修改不存在的记录" in result

    def test_default(self):
        """测试默认场景"""
        result = get_business_scenarios("其他模块", False)
        assert "查询不存在的资源" in result


class TestExtractUserParams:
    """测试用户参数提取"""

    def test_from_ai_cases(self):
        """测试从 AI 用例提取"""
        ai_cases = [
            {"title": "正向用例", "priority": "P0", "body": {"username": "admin", "password": "123"}},
            {"title": "反向用例", "priority": "P2", "body": {"username": "test"}}
        ]
        result = extract_user_params(ai_cases, "", {})
        assert result == {"username": "admin", "password": "123"}

    def test_from_business_rules(self):
        """测试从业务规则提取"""
        business_rules = "username: admin\npassword=123456"
        result = extract_user_params([], business_rules, {})
        assert result == {"username": "admin", "password": "123456"}

    def test_no_params(self):
        """测试无参数"""
        result = extract_user_params([], "", {})
        assert result is None


class TestSafeCall:
    """测试安全调用函数"""

    def test_successful_call(self):
        """测试成功调用"""
        def success():
            return "success"
        result = safe_call(success, error_msg="测试")
        assert result == "success"

    def test_failed_call_with_retry(self):
        """测试失败调用（带重试）"""
        call_count = 0
        def fail_twice_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("模拟失败")
            return "success"

        result = safe_call(fail_twice_then_succeed, error_msg="测试", retry_count=3)
        assert result == "success"

    def test_failed_call_default_return(self):
        """测试失败调用返回默认值"""
        def always_fail():
            raise Exception("总是失败")

        result = safe_call(always_fail, error_msg="测试", default_return="fallback", retry_count=2)
        assert result == "fallback"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])