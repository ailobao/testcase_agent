# tests/test_json_parser.py
"""测试统一的 JSON 解析器"""
import sys
import os
import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.json_parser import universal_json_parse

# 直接从文件导入，不使用 fixtures 包
import importlib.util

# 手动加载 sample_responses
spec = importlib.util.spec_from_file_location(
    "sample_responses",
    os.path.join(os.path.dirname(__file__), "fixtures", "sample_responses.py")
)
sample_responses = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sample_responses)


class TestUniversalJsonParse:
    """测试万能 JSON 解析器"""

    def test_standard_array(self):
        """测试标准 JSON 数组（有2个元素）"""
        result = universal_json_parse(sample_responses.STANDARD_ARRAY_RESPONSE)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["case_id"] == "TC_001"
        assert result[1]["case_id"] == "TC_002"

    def test_markdown_wrapped(self):
        """测试 Markdown 包裹的 JSON"""
        result = universal_json_parse(sample_responses.MARKDOWN_WRAPPED_RESPONSE)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["method"] == "GET"
        assert result[0]["url"] == "/api/search"

    def test_python_literal(self):
        """测试 Python 字面量（单引号）"""
        result = universal_json_parse(sample_responses.PYTHON_LITERAL_RESPONSE)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["case_id"] == "TC_001"
        assert result[0]["body"]["goods_id"] == 1001

    def test_trailing_comma(self):
        """测试尾随逗号（有2个元素）"""
        result = universal_json_parse(sample_responses.TRAILING_COMMA_RESPONSE)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["case_id"] == "TC_001"
        assert result[1]["case_id"] == "TC_002"

    def test_missing_comma(self):
        """测试缺少逗号（}{ 模式，有3个元素）"""
        result = universal_json_parse(sample_responses.MISSING_COMMA_RESPONSE)
        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0]["case_id"] == "TC_001"
        assert result[1]["case_id"] == "TC_002"
        assert result[2]["case_id"] == "TC_003"

    def test_commented_response(self):
        """测试带注释的响应"""
        result = universal_json_parse(sample_responses.COMMENTED_RESPONSE)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["case_id"] == "TC_001"
        assert result[1]["case_id"] == "TC_002"

    def test_single_object(self):
        """测试单个对象（应转为数组）"""
        result = universal_json_parse(sample_responses.SINGLE_OBJECT_RESPONSE)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["case_id"] == "TC_001"

    def test_incomplete_response(self):
        """测试不完整的响应（应降级）"""
        result = universal_json_parse(sample_responses.INCOMPLETE_RESPONSE, default_return=[])
        assert result == []

    def test_empty_response(self):
        """测试空响应"""
        result = universal_json_parse(sample_responses.EMPTY_RESPONSE, default_return=[])
        assert result == []

    def test_invalid_response(self):
        """测试完全无效的响应"""
        result = universal_json_parse(sample_responses.INVALID_RESPONSE, default_return=[])
        assert result == []

    def test_custom_default_return(self):
        """测试自定义默认返回值"""
        custom_default = [{"fallback": True}]
        result = universal_json_parse(sample_responses.INVALID_RESPONSE, default_return=custom_default)
        assert result == custom_default

    def test_ai_dimension_response(self):
        """测试 AI 维度用例格式（有2个元素）"""
        result = universal_json_parse(sample_responses.AI_DIMENSION_RESPONSE)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["测试标题"] == "正向用例-正常提问"
        assert result[1]["测试标题"] == "反向用例-空输入"

    def test_nested_array_response(self):
        """测试嵌套数组响应"""
        result = universal_json_parse(sample_responses.NESTED_ARRAY_RESPONSE)
        assert isinstance(result, list)
        # 嵌套数组会被展平
        assert len(result) == 2
        assert result[0]["case_id"] == "TC_001"
        assert result[1]["case_id"] == "TC_002"

    def test_null_boolean_response(self):
        """测试带 null/true/false 的响应"""
        result = universal_json_parse(sample_responses.NULL_BOOLEAN_RESPONSE)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["active"] is True
        assert result[0]["deleted"] is False
        assert result[0]["data"] is None

    def test_none_input(self):
        """测试 None 输入"""
        result = universal_json_parse(None, default_return=[])
        assert result == []

    def test_non_string_input(self):
        """测试非字符串输入"""
        result = universal_json_parse(12345, default_return=[])
        assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])