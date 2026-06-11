# test_extract.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.json_parser import _extract_dicts

# 测试数据
test_data = [[{'case_id': 'TC_001', 'title': '用例1'}], [{'case_id': 'TC_002', 'title': '用例2'}]]
result = _extract_dicts(test_data)
print(f"测试数据: {test_data}")
print(f"提取结果: {result}")
print(f"结果长度: {len(result)}")