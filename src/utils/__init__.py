# src/utils/__init__.py
"""工具函数模块"""

from .common_tools import (
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

# 从 json_parser 导入 JSON 相关函数
from .json_parser import universal_json_parse

# 为了兼容旧代码，如果其他地方还在使用 safe_json_parse，可以添加别名
# safe_json_parse = universal_json_parse

__all__ = [
    'deduplicate_cases',
    'clean_name',
    'ensure_dict_field',
    'get_max_case_id',
    'fix_case_id',
    'renumber_cases',
    'normalize_assert',
    'get_business_scenarios',
    'extract_user_params',
    'safe_call',
    'universal_json_parse'
]