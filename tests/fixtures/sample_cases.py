# tests/fixtures/sample_cases.py
"""示例用例数据"""

SAMPLE_API_CASES = [
    {
        "case_id": "TC_001",
        "title": "正向用例-正常登录",
        "method": "POST",
        "url": "/api/login",
        "headers": {"Content-Type": "application/json", "Authorization": "Bearer {{token}}"},
        "body": {"username": "admin", "password": "123456"},
        "assert": {"status_code": 200, "body.code": 200, "body.msg": "操作成功"},
        "extract": {"token": "body.data.token"},
        "priority": "P0"
    },
    {
        "case_id": "TC_002",
        "title": "缺失参数 username",
        "method": "POST",
        "url": "/api/login",
        "headers": {"Content-Type": "application/json", "Authorization": "Bearer {{token}}"},
        "body": {"password": "123456"},
        "assert": {"status_code": 400, "body.msg": "username不能为空"},
        "extract": {},
        "priority": "P2"
    },
    {
        "case_id": "TC_003",
        "title": "Token过期",
        "method": "POST",
        "url": "/api/login",
        "headers": {"Content-Type": "application/json", "Authorization": "Bearer expired_token"},
        "body": {"username": "admin", "password": "123456"},
        "assert": {"status_code": 401, "body.msg": "认证失败"},
        "extract": {},
        "priority": "P2"
    }
]

SAMPLE_AI_CASES = [
    {
        "测试ID": "TC_001",
        "测试标题": "正向用例-正常提问",
        "测试类型": "功能",
        "优先级": "P0",
        "关联需求": "无",
        "前置条件": "用户已登录",
        "测试数据": "今天天气怎么样？",
        "测试步骤": "1. 输入问题\n2. 点击发送",
        "预期结果": "返回正确答案",
        "实际结果": "",
        "执行人": ""
    },
    {
        "测试ID": "TC_002",
        "测试标题": "反向用例-空输入",
        "测试类型": "鲁棒性",
        "优先级": "P1",
        "关联需求": "无",
        "前置条件": "用户已登录",
        "测试数据": "",
        "测试步骤": "1. 输入为空\n2. 点击发送",
        "预期结果": "提示请输入内容",
        "实际结果": "",
        "执行人": ""
    },
    {
        "测试ID": "TC_003",
        "测试标题": "边界值-超长输入",
        "测试类型": "准确性",
        "优先级": "P2",
        "关联需求": "无",
        "前置条件": "用户已登录",
        "测试数据": "a" * 10000,
        "测试步骤": "1. 输入超长文本\n2. 点击发送",
        "预期结果": "提示内容过长或截断处理",
        "实际结果": "",
        "执行人": ""
    }
]

SAMPLE_MANUAL_CASES = [
    {
        "用例ID": "TC_001",
        "标题": "登录功能测试-正常流程",
        "前置条件": "已注册账号",
        "测试步骤": "1. 打开登录页面\n2. 输入正确的用户名和密码\n3. 点击登录按钮",
        "预期结果": "登录成功，跳转到首页",
        "实际结果": "",
        "优先级": "P0",
        "用户名": "test001",
        "密码": "123456",
        "验证码": "8888"
    },
    {
        "用例ID": "TC_002",
        "标题": "登录功能测试-密码错误",
        "前置条件": "已注册账号",
        "测试步骤": "1. 打开登录页面\n2. 输入正确的用户名和错误的密码\n3. 点击登录按钮",
        "预期结果": "提示密码错误，停留在登录页",
        "实际结果": "",
        "优先级": "P1",
        "用户名": "test001",
        "密码": "wrong_password",
        "验证码": "8888"
    },
    {
        "用例ID": "TC_003",
        "标题": "登录功能测试-用户名为空",
        "前置条件": "已注册账号",
        "测试步骤": "1. 打开登录页面\n2. 用户名留空，输入密码和验证码\n3. 点击登录按钮",
        "预期结果": "提示用户名不能为空",
        "实际结果": "",
        "优先级": "P2",
        "用户名": "",
        "密码": "123456",
        "验证码": "8888"
    }
]

# 用于去重测试的重复用例
DUPLICATE_API_CASES = [
    {
        "case_id": "TC_001",
        "title": "正向用例-正常登录",
        "body": {"username": "admin", "password": "123456"}
    },
    {
        "case_id": "TC_002",
        "title": "正向用例-正常登录",  # 标题相同
        "body": {"username": "admin", "password": "123456"}  # body 也相同
    },
    {
        "case_id": "TC_003",
        "title": "正向用例-正常登录",  # 标题相同
        "body": {"username": "admin", "password": "different"}  # body 不同
    }
]

# 用于编号测试的用例
UNNUMBERED_CASES = [
    {"case_id": "", "title": "用例1"},
    {"case_id": "", "title": "用例2"},
    {"case_id": "", "title": "用例3"}
]

# 用于断言测试的响应数据
SAMPLE_RESPONSES = {
    "success_200": {
        "status_code": 200,
        "body": {"code": 200, "msg": "操作成功", "data": {"id": 123}}
    },
    "auth_failed": {
        "status_code": 401,
        "body": {"code": 401, "msg": "认证失败"}
    },
    "not_found": {
        "status_code": 404,
        "body": {"code": 404, "msg": "资源不存在"}
    },
    "bad_request": {
        "status_code": 400,
        "body": {"code": 400, "msg": "参数错误"}
    }
}