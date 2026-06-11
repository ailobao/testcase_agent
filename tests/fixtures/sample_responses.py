# tests/fixtures/sample_responses.py
"""示例 LLM 响应数据"""

# 标准 JSON 数组响应（2个元素）
STANDARD_ARRAY_RESPONSE = (
    '[\n'
    '    {\n'
    '        "case_id": "TC_001",\n'
    '        "title": "正向用例-正常登录",\n'
    '        "method": "POST",\n'
    '        "url": "/api/login",\n'
    '        "headers": {"Content-Type": "application/json"},\n'
    '        "body": {"username": "admin", "password": "123456"},\n'
    '        "assert": {"status_code": 200, "body.code": 200},\n'
    '        "extract": {"token": "body.data.token"},\n'
    '        "priority": "P0"\n'
    '    },\n'
    '    {\n'
    '        "case_id": "TC_002",\n'
    '        "title": "反向用例-密码错误",\n'
    '        "method": "POST",\n'
    '        "url": "/api/login",\n'
    '        "headers": {"Content-Type": "application/json"},\n'
    '        "body": {"username": "admin", "password": "wrong"},\n'
    '        "assert": {"status_code": 401, "body.code": 401, "body.msg": "认证失败"},\n'
    '        "extract": {},\n'
    '        "priority": "P1"\n'
    '    }\n'
    ']'
)

# Markdown 包裹的响应
MARKDOWN_WRAPPED_RESPONSE = (
    '```json\n'
    '[\n'
    '    {\n'
    '        "case_id": "TC_001",\n'
    '        "title": "正向用例-搜索商品",\n'
    '        "method": "GET",\n'
    '        "url": "/api/search",\n'
    '        "headers": {"Content-Type": "application/json"},\n'
    '        "body": {"keyword": "手机"},\n'
    '        "assert": {"status_code": 200},\n'
    '        "extract": {},\n'
    '        "priority": "P0"\n'
    '    }\n'
    ']\n'
    '```'
)

# Python 字面量格式（单引号）
PYTHON_LITERAL_RESPONSE = (
    '[\n'
    "    {\n"
    "        'case_id': 'TC_001',\n"
    "        'title': '正向用例-创建订单',\n"
    "        'method': 'POST',\n"
    "        'url': '/api/order',\n"
    "        'headers': {'Content-Type': 'application/json'},\n"
    "        'body': {'goods_id': 1001, 'num': 1, 'address_id': 100},\n"
    "        'assert': {'status_code': 200, 'body.code': 200, 'body.msg': '操作成功'},\n"
    "        'extract': {'order_id': 'body.data.id'},\n"
    "        'priority': 'P0'\n"
    "    }\n"
    ']'
)

# 尾随逗号的响应（2个元素）
TRAILING_COMMA_RESPONSE = (
    '[\n'
    '    {\n'
    '        "case_id": "TC_001",\n'
    '        "title": "正向用例-添加购物车",\n'
    '        "method": "POST",\n'
    '        "url": "/api/cart",\n'
    '        "body": {"goods_id": 1001, "num": 1},\n'
    '        "priority": "P0",\n'
    '    },\n'
    '    {\n'
    '        "case_id": "TC_002",\n'
    '        "title": "反向用例-数量超限",\n'
    '        "method": "POST",\n'
    '        "url": "/api/cart",\n'
    '        "body": {"goods_id": 1001, "num": 100},\n'
    '        "priority": "P1",\n'
    '    },\n'
    ']'
)

# 缺少逗号的响应（3个元素）
MISSING_COMMA_RESPONSE = (
    '[\n'
    '    {"case_id": "TC_001", "title": "正向用例"}\n'
    '    {"case_id": "TC_002", "title": "反向用例"}\n'
    '    {"case_id": "TC_003", "title": "边界值用例"}\n'
    ']'
)

# 带注释的响应
COMMENTED_RESPONSE = (
    '[\n'
    '    // 正向用例\n'
    '    {\n'
    '        "case_id": "TC_001",\n'
    '        "title": "正向用例-正常流程",\n'
    '        "method": "POST",\n'
    '        "url": "/api/transfer",\n'
    '        "body": {"from_account": "123", "to_account": "456", "amount": 100},\n'
    '        "assert": {"status_code": 200}\n'
    '    },\n'
    '    /* 反向用例 */\n'
    '    {\n'
    '        "case_id": "TC_002",\n'
    '        "title": "反向用例-余额不足",\n'
    '        "method": "POST",\n'
    '        "url": "/api/transfer",\n'
    '        "body": {"from_account": "123", "to_account": "456", "amount": 10000},\n'
    '        "assert": {"status_code": 400, "body.msg": "余额不足"}\n'
    '    }\n'
    ']'
)

# 不完整的响应
INCOMPLETE_RESPONSE = (
    '[\n'
    '    {\n'
    '        "case_id": "TC_001",\n'
    '        "title": "正向用例",\n'
    '        "method": "POST",\n'
    '        "url": "/api/login",\n'
    '        "body": {"username": "admin", "password":'
)

# 空响应
EMPTY_RESPONSE = ''

# 完全无效的响应
INVALID_RESPONSE = '这不是 JSON 格式的内容'

# 单个对象
SINGLE_OBJECT_RESPONSE = (
    '{\n'
    '    "case_id": "TC_001",\n'
    '    "title": "正向用例",\n'
    '    "method": "GET",\n'
    '    "url": "/api/example",\n'
    '    "body": {},\n'
    '    "assert": {"status_code": 200},\n'
    '    "priority": "P0"\n'
    '}'
)

# AI 维度用例响应（2个元素）
AI_DIMENSION_RESPONSE = (
    '[\n'
    '    {\n'
    '        "测试ID": "TC_001",\n'
    '        "测试标题": "正向用例-正常提问",\n'
    '        "测试类型": "功能",\n'
    '        "优先级": "P0",\n'
    '        "关联需求": "无",\n'
    '        "前置条件": "用户已登录",\n'
    '        "测试数据": "今天天气怎么样？",\n'
    '        "测试步骤": "1. 输入问题\\n2. 点击发送",\n'
    '        "预期结果": "返回正确答案"\n'
    '    },\n'
    '    {\n'
    '        "测试ID": "TC_002",\n'
    '        "测试标题": "反向用例-空输入",\n'
    '        "测试类型": "鲁棒性",\n'
    '        "优先级": "P1",\n'
    '        "关联需求": "无",\n'
    '        "前置条件": "用户已登录",\n'
    '        "测试数据": "",\n'
    '        "测试步骤": "1. 输入为空\\n2. 点击发送",\n'
    '        "预期结果": "提示请输入内容"\n'
    '    }\n'
    ']'
)

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

# 带 null/true/false 的响应
NULL_BOOLEAN_RESPONSE = (
    '[\n'
    '    {\n'
    '        "case_id": "TC_001",\n'
    '        "title": "测试用例",\n'
    '        "active": true,\n'
    '        "deleted": false,\n'
    '        "data": null,\n'
    '        "count": 0\n'
    '    }\n'
    ']'
)