"""初始化数据库规则 - 客达天下项目"""
import sys
import os

# 将项目根目录添加到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.rule_manager import save_rule


def init_all_modules():
    """初始化所有项目的模块配置"""

    print("=" * 60)
    print("开始初始化数据库规则...")
    print("=" * 60)

    # ========== 客达天下项目 ==========

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
    print("✅ 客达天下/登录")

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
    print("✅ 客达天下/生成验证码")

    # 3. 注册
    save_rule(
        project_name="客达天下",
        module_name="注册",
        input_fields='["username", "password", "phone", "code", "uuid"]',
        required_fields='["username", "password", "phone", "code", "uuid"]',
        url_path="/api/register",
        default_body='{"username": "newuser", "password": "123456", "phone": "13800138000", "code": "8888", "uuid": "test-uuid-123"}',
        constraints="用户名3-20字符，密码6-20字符，手机号11位，验证码固定8888"
    )
    print("✅ 客达天下/注册")

    # 4. 新增课程
    save_rule(
        project_name="客达天下",
        module_name="新增课程",
        input_fields='["name", "subject", "price", "applicablePerson", "info"]',
        required_fields='["name", "subject", "price", "applicablePerson"]',
        url_path="/api/clues/course",
        default_body='{"name": "测试课程", "subject": "6", "price": 899, "applicablePerson": "2", "info": "测试课程介绍"}',
        constraints="课程名称1-64字符，价格0-99999，学科有效值0-9，适用人群1-2"
    )
    print("✅ 客达天下/新增课程")

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
    print("✅ 客达天下/查询课程列表")

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
    print("✅ 客达天下/查询课程")

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
    print("✅ 客达天下/修改课程")

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
    print("✅ 客达天下/删除课程")

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
    print("✅ 客达天下/合同上传")

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
    print("✅ 客达天下/新增合同")

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
    print("✅ 客达天下/查询合同列表")

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
    print("✅ 客达天下/删除合同")

    # ========== 电商平台 ==========

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
    print("✅ 电商平台/登录")

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
    print("✅ 电商平台/购物车")

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
    print("✅ 电商平台/下单")

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
    print("✅ 电商平台/搜索")

    # ========== 旅游平台 ==========

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
    print("✅ 旅游平台/酒店搜索")

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
    print("✅ 旅游平台/机票搜索")

    # ========== 社交平台 ==========

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
    print("✅ 社交平台/发布动态")

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
    print("✅ 社交平台/评论")

    # ========== 银行系统 ==========

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
    print("✅ 银行系统/余额查询")

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
    print("✅ 银行系统/转账")

    print("=" * 60)
    print("✅ 所有模块配置初始化完成！共 21 个模块")
    print("=" * 60)


if __name__ == "__main__":
    init_all_modules()