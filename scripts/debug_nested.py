# debug_nested.py
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.json_parser import universal_json_parse

# 嵌套数组响应
NESTED_ARRAY_RESPONSE = (
    '[\n'
    '    [\n'
    '        {\n'
    '            "case_id": "TC_001",\n'
    '            "title": "用例1"\n'
    '        }\n'
    '    ],\n'
    '    [\n'
    '        {\n'
    '            "case_id": "TC_002",\n'
    '            "title": "用例2"\n'
    '        }\n'
    '    ]\n'
    ']'
)

print("=" * 50)
print("测试1: 直接使用 json.loads")
print("=" * 50)
data = json.loads(NESTED_ARRAY_RESPONSE)
print(f"类型: {type(data)}")
print(f"长度: {len(data)}")
print(f"内容: {data}")

print("\n" + "=" * 50)
print("测试2: 使用 universal_json_parse")
print("=" * 50)
result = universal_json_parse(NESTED_ARRAY_RESPONSE)
print(f"类型: {type(result)}")
print(f"长度: {len(result)}")
print(f"内容: {result}")