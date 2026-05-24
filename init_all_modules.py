# init_all_modules.py - 初始化所有模块配置（客达天下 + 电商/旅游/社交/银行）
from database import save_rule


def init_all_modules():
    """初始化所有项目的模块配置"""

    # =========================================================
    # 一、客达天下项目（根据API文档）
    # =========================================================

    # 1. 登录
    save_rule(
        project_name="客达天下",
        module_name="登录",
        input_fields='["username", "password", "code", "uuid"]',
        required_fields='["username", "password", "code", "uuid"]',
        url_path="/api/login",
        default_body='{"username": "manager", "password": "123456", "code": "8888", "uuid": "test-uuid-123"}',
        constraints="验证码固定为8888，用户名manager，密码123456"
    )

    # 2. 生成验证码
    save_rule(
        project_name="客达天下",
        module_name="生成验证码",
        input_fields='[]',
        required_fields='[]',
        url_path="/api/captchaImage",
        default_body='{}',
        constraints="GET请求，返回验证码图片和uuid"
    )

    # 3. 新增课程
    save_rule(
        project_name="客达天下",
        module_name="新增课程",
        input_fields='["name", "subject", "price", "applicablePerson", "info"]',
        required_fields='["name", "subject", "price", "applicablePerson"]',
        url_path="/api/clues/course",
        default_body='{"name": "测试课程", "subject": "6", "price": 899, "applicablePerson": "2", "info": "测试课程介绍"}',
        constraints="课程名称1-64字符，价格0-99999，学科有效值0-9，适用人群1-2"
    )

    # 4. 查询课程列表
    save_rule(
        project_name="客达天下",
        module_name="查询课程列表",
        input_fields='["name", "subject", "price", "applicablePerson", "info"]',
        required_fields='[]',
        url_path="/api/clues/course/list",
        default_body='{}',
        constraints="GET请求，所有参数可选"
    )

    # 5. 查询课程
    save_rule(
        project_name="客达天下",
        module_name="查询课程",
        input_fields='["id"]',
        required_fields='["id"]',
        url_path="/api/clues/course/:id",
        default_body='{"id": 1000127924}',
        constraints="id为课程ID，必填"
    )

    # 6. 修改课程
    save_rule(
        project_name="客达天下",
        module_name="修改课程",
        input_fields='["id", "name", "subject", "price", "applicablePerson", "info"]',
        required_fields='["id"]',
        url_path="/api/clues/course",
        default_body='{"id": 93, "name": "接口测试001", "subject": "6", "price": 998, "applicablePerson": "2", "info": "课程介绍001"}',
        constraints="PUT请求，id必填，其他可选"
    )

    # 7. 删除课程
    save_rule(
        project_name="客达天下",
        module_name="删除课程",
        input_fields='["id"]',
        required_fields='["id"]',
        url_path="/api/clues/course/:id",
        default_body='{"id": 93}',
        constraints="DELETE请求，id必填"
    )

    # 8. 合同上传
    save_rule(
        project_name="客达天下",
        module_name="合同上传",
        input_fields='["file"]',
        required_fields='["file"]',
        url_path="/api/common/upload",
        default_body='{"file": "/path/to/file.pdf"}',
        constraints="POST请求，multipart/form-data格式，需要token"
    )

    # 9. 新增合同
    save_rule(
        project_name="客达天下",
        module_name="新增合同",
        input_fields='["contractNo", "phone", "name", "subject", "courseId", "channel", "activityId", "fileName"]',
        required_fields='["contractNo", "phone", "name", "subject", "courseId", "fileName"]',
        url_path="/api/contract",
        default_body='{"contractNo": "HT20240001", "phone": "13812345678", "name": "测试客户", "subject": "6", "courseId": 100, "fileName": "/profile/upload/test.pdf"}',
        constraints="合同编号需唯一，手机号11位数字，客户姓名1-50字符"
    )

    # 10. 查询合同列表
    save_rule(
        project_name="客达天下",
        module_name="查询合同列表",
        input_fields='["phone"]',
        required_fields='[]',
        url_path="/api/contract/list",
        default_body='{}',
        constraints="GET请求，phone可选"
    )

    # 11. 删除合同
    save_rule(
        project_name="客达天下",
        module_name="删除合同",
        input_fields='["id"]',
        required_fields='["id"]',
        url_path="/api/contract/remove",
        default_body='{"id": 10950251898105098}',
        constraints="POST请求，application/x-www-form-urlencoded格式，id必填"
    )

    # =========================================================
    # 二、电商平台
    # =========================================================

    # 12. 电商-登录
    save_rule(
        project_name="电商平台",
        module_name="登录",
        input_fields='["username", "password", "verify_code", "uuid"]',
        required_fields='["username", "password"]',
        url_path="/api/login",
        default_body='{"username": "test001", "password": "123456", "verify_code": "8888", "uuid": "test-uuid-123"}',
        constraints="用户名6-20字符，密码6-20字符，验证码固定8888"
    )

    # 13. 电商-购物车
    save_rule(
        project_name="电商平台",
        module_name="购物车",
        input_fields='["goods_id", "num", "selected", "sku_id"]',
        required_fields='["goods_id", "num"]',
        url_path="/api/cart",
        default_body='{"goods_id": 1001, "num": 1, "selected": true, "sku_id": "SKU001"}',
        constraints="商品ID存在，数量1-99，sku_id可选"
    )

    # 14. 电商-下单
    save_rule(
        project_name="电商平台",
        module_name="下单",
        input_fields='["goods_id", "num", "address_id", "payment_id", "coupon_id"]',
        required_fields='["goods_id", "num", "address_id"]',
        url_path="/api/order",
        default_body='{"goods_id": 1001, "num": 1, "address_id": 100, "payment_id": 1, "coupon_id": 0}',
        constraints="商品库存充足，地址存在，支付方式有效"
    )

    # 15. 电商-搜索
    save_rule(
        project_name="电商平台",
        module_name="搜索",
        input_fields='["keyword", "category_id", "sort", "page", "size"]',
        required_fields='["keyword"]',
        url_path="/api/search",
        default_body='{"keyword": "手机", "category_id": 1, "sort": "price_asc", "page": 1, "size": 20}',
        constraints="关键词1-50字符，分页参数可选"
    )

    # =========================================================
    # 三、旅游平台
    # =========================================================

    # 16. 旅游-酒店搜索
    save_rule(
        project_name="旅游平台",
        module_name="酒店搜索",
        input_fields='["city", "checkin", "checkout", "rooms", "adults", "children", "keyword"]',
        required_fields='["city", "checkin", "checkout"]',
        url_path="/api/hotel/search",
        default_body='{"city": "北京", "checkin": "2026-06-01", "checkout": "2026-06-02", "rooms": 1, "adults": 2, "children": 0, "keyword": ""}',
        constraints="入住日期不能早于今天，离店日期晚于入住日期，房间数1-5"
    )

    # 17. 旅游-机票搜索
    save_rule(
        project_name="旅游平台",
        module_name="机票搜索",
        input_fields='["from_city", "to_city", "date", "passenger_num", "cabin_type"]',
        required_fields='["from_city", "to_city", "date"]',
        url_path="/api/flight/search",
        default_body='{"from_city": "北京", "to_city": "上海", "date": "2026-06-01", "passenger_num": 1, "cabin_type": "economy"}',
        constraints="出发城市和到达城市不同，日期不能早于今天"
    )

    # =========================================================
    # 四、社交平台
    # =========================================================

    # 18. 社交-发布动态
    save_rule(
        project_name="社交平台",
        module_name="发布动态",
        input_fields='["content", "images", "location", "topic_id"]',
        required_fields='["content"]',
        url_path="/api/feed/publish",
        default_body='{"content": "今天天气真好！", "images": ["img1.jpg", "img2.jpg"], "location": "北京", "topic_id": 0}',
        constraints="内容1-500字符，图片最多9张"
    )

    # 19. 社交-评论
    save_rule(
        project_name="社交平台",
        module_name="评论",
        input_fields='["feed_id", "content", "reply_to"]',
        required_fields='["feed_id", "content"]',
        url_path="/api/comment/add",
        default_body='{"feed_id": 1001, "content": "写得真好！", "reply_to": 0}',
        constraints="内容1-200字符，reply_to为被评论的评论ID"
    )

    # =========================================================
    # 五、银行系统
    # =========================================================

    # 20. 银行-余额查询
    save_rule(
        project_name="银行系统",
        module_name="余额查询",
        input_fields='["account_id", "account_type"]',
        required_fields='["account_id"]',
        url_path="/api/balance",
        default_body='{"account_id": "6217000012345678", "account_type": "savings"}',
        constraints="账号存在，账户类型有效"
    )

    # 21. 银行-转账
    save_rule(
        project_name="银行系统",
        module_name="转账",
        input_fields='["from_account", "to_account", "amount", "password", "remark"]',
        required_fields='["from_account", "to_account", "amount", "password"]',
        url_path="/api/transfer",
        default_body='{"from_account": "6217000012345678", "to_account": "6217000087654321", "amount": 100, "password": "123456", "remark": "测试转账"}',
        constraints="金额大于0，不超过余额，账户存在"
    )

    print("=" * 70)
    print("✅ 所有模块配置初始化完成！")
    print("=" * 70)
    print("\n📋 已初始化的模块（共21个）：")
    print("-" * 70)
    print("\n【客达天下】（11个）")
    print("  1. 登录")
    print("  2. 生成验证码")
    print("  3. 新增课程")
    print("  4. 查询课程列表")
    print("  5. 查询课程")
    print("  6. 修改课程")
    print("  7. 删除课程")
    print("  8. 合同上传")
    print("  9. 新增合同")
    print("  10. 查询合同列表")
    print("  11. 删除合同")
    print("\n【电商平台】（4个）")
    print("  12. 登录")
    print("  13. 购物车")
    print("  14. 下单")
    print("  15. 搜索")
    print("\n【旅游平台】（2个）")
    print("  16. 酒店搜索")
    print("  17. 机票搜索")
    print("\n【社交平台】（2个）")
    print("  18. 发布动态")
    print("  19. 评论")
    print("\n【银行系统】（2个）")
    print("  20. 余额查询")
    print("  21. 转账")
    print("=" * 70)


if __name__ == "__main__":
    init_all_modules()