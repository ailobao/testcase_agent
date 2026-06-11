# tests/conftest.py
"""pytest 配置文件"""
import sys
import os
import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def sample_api_cases():
    """示例 API 用例 fixture"""
    from tests.fixtures.sample_cases import SAMPLE_API_CASES
    return SAMPLE_API_CASES


@pytest.fixture
def sample_ai_cases():
    """示例 AI 用例 fixture"""
    from tests.fixtures.sample_cases import SAMPLE_AI_CASES
    return SAMPLE_AI_CASES


@pytest.fixture
def sample_manual_cases():
    """示例手工用例 fixture"""
    from tests.fixtures.sample_cases import SAMPLE_MANUAL_CASES
    return SAMPLE_MANUAL_CASES


@pytest.fixture
def mock_llm_response():
    """Mock LLM 响应 fixture"""
    def _mock_response(response_text):
        with patch('src.core.llm_client.call_llm_with_prompt') as mock:
            mock.return_value = response_text
            yield mock
    return _mock_response