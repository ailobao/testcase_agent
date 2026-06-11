import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.config.settings import KNOWLEDGE_BASE_DIR


def get_manual_test_data():
    manual_data = {
        "微信登录测试用例": {
            "module": "微信登录",
            "description": "微信App登录功能测试",
            "scenarios": [
                {"name": "手机号为空时登录", "type": "反向", "precondition": "微信App已安装并正常运行",
                 "steps": "1. 打开微信登录页面\n2. 手机号输入框不输入任何内容\n3. 输入正确的密码\n4. 点击登录按钮",
                 "test_data": "手机号：空\n密码：已注册账号的正确密码", "expected": "登录失败，系统提示手机号不能为空"},
                {"name": "手机号未注册时登录", "type": "反向", "precondition": "微信App已安装并正常运行",
                 "steps": "1. 打开微信登录页面\n2. 输入未注册的手机号\n3. 输入任意密码\n4. 点击登录按钮",
                 "test_data": "手机号：13800138000（未注册）\n密码：任意",
                 "expected": "登录失败，系统提示该手机号未注册或引导注册流程"},
                {"name": "输入非手机号格式登录", "type": "反向", "precondition": "微信App已安装并正常运行",
                 "steps": "1. 打开微信登录页面\n2. 输入非手机号格式内容（如字母、特殊字符、不足/超过11位数字）\n3. 输入任意密码\n4. 点击登录按钮",
                 "test_data": "手机号：abc123 / 123 / 138001380001（12位）\n密码：任意",
                 "expected": "登录失败，系统提示请输入正确的手机号格式"},
                {"name": "密码为空时登录", "type": "反向", "precondition": "微信App已安装并正常运行，账号已注册",
                 "steps": "1. 打开微信登录页面\n2. 输入已注册的正确手机号\n3. 密码输入框不输入任何内容\n4. 点击登录按钮",
                 "test_data": "手机号：已注册账号的手机号\n密码：空", "expected": "登录失败，系统提示密码不能为空"},
                {"name": "密码错误时登录", "type": "反向", "precondition": "微信App已安装并正常运行，账号已注册",
                 "steps": "1. 打开微信登录页面\n2. 输入已注册的正确手机号\n3. 输入错误的密码\n4. 点击登录按钮",
                 "test_data": "手机号：已注册账号的手机号\n密码：错误密码（如123456，非正确密码）",
                 "expected": "登录失败，系统提示手机号或密码错误"}
            ]
        },
        "QQ登录测试用例": {
            "module": "QQ登录",
            "description": "QQ登录功能测试，支持手机号、用户名、邮箱三种账号类型",
            "scenarios": [
                {"name": "登录成功_手机号登录", "type": "正向", "precondition": "手机号已注册",
                 "steps": "1. 打开登录页面\n2. 输入手机号\n3. 输入密码\n4. 输入图片验证码\n5. 点击登录",
                 "test_data": "手机号：已注册手机号\n密码：正确密码\n验证码：正确未过期", "expected": "登录成功，跳转页面"},
                {"name": "登录成功_用户名登录", "type": "正向", "precondition": "用户名已注册",
                 "steps": "1. 打开登录页面\n2. 输入用户名\n3. 输入密码\n4. 输入图片验证码\n5. 点击登录",
                 "test_data": "用户名：已注册用户名\n密码：正确密码\n验证码：正确未过期", "expected": "登录成功，跳转页面"},
                {"name": "登录成功_邮箱登录", "type": "正向", "precondition": "邮箱已注册",
                 "steps": "1. 打开登录页面\n2. 输入邮箱\n3. 输入密码\n4. 输入图片验证码\n5. 点击登录",
                 "test_data": "邮箱：已注册邮箱\n密码：正确密码\n验证码：正确未过期", "expected": "登录成功，跳转页面"},
                {"name": "登录失败_账号为空", "type": "反向", "precondition": "账号已注册",
                 "steps": "1. 打开登录页面\n2. 账号为空\n3. 输入密码\n4. 输入图片验证码\n5. 点击登录",
                 "test_data": "账号：空\n密码：正确密码\n验证码：正确未过期", "expected": "登录失败，提示账号不能为空"},
                {"name": "登录失败_账号未注册", "type": "反向", "precondition": "无",
                 "steps": "1. 打开登录页面\n2. 输入未注册账号\n3. 输入密码\n4. 输入图片验证码\n5. 点击登录",
                 "test_data": "账号：未注册账号\n密码：任意\n验证码：正确未过期", "expected": "登录失败，提示账号未注册"},
                {"name": "登录失败_密码为空", "type": "反向", "precondition": "账号已注册",
                 "steps": "1. 打开登录页面\n2. 输入已注册账号\n3. 密码为空\n4. 输入图片验证码\n5. 点击登录",
                 "test_data": "账号：已注册账号\n密码：空\n验证码：正确未过期", "expected": "登录失败，提示密码不能为空"},
                {"name": "登录失败_密码错误", "type": "反向", "precondition": "账号已注册",
                 "steps": "1. 打开登录页面\n2. 输入已注册账号\n3. 输入错误密码\n4. 输入图片验证码\n5. 点击登录",
                 "test_data": "账号：已注册账号\n密码：错误密码\n验证码：正确未过期",
                 "expected": "登录失败，提示账号或密码错误"},
                {"name": "登录失败_验证码为空", "type": "反向", "precondition": "账号已注册",
                 "steps": "1. 打开登录页面\n2. 输入已注册账号\n3. 输入正确密码\n4. 验证码为空\n5. 点击登录",
                 "test_data": "账号：已注册账号\n密码：正确密码\n验证码：空", "expected": "登录失败，提示验证码错误"},
                {"name": "登录失败_已过期验证码", "type": "反向", "precondition": "账号已注册",
                 "steps": "1. 打开登录页面\n2. 输入已注册账号\n3. 输入正确密码\n4. 输入已过期的验证码\n5. 点击登录",
                 "test_data": "账号：已注册账号\n密码：正确密码\n验证码：已过期", "expected": "登录失败，提示验证码错误"},
                {"name": "登录失败_未过期验证码错误", "type": "反向", "precondition": "账号已注册",
                 "steps": "1. 打开登录页面\n2. 输入已注册账号\n3. 输入正确密码\n4. 输入错误的验证码\n5. 点击登录",
                 "test_data": "账号：已注册账号\n密码：正确密码\n验证码：错误验证码",
                 "expected": "登录失败，提示验证码错误"}
            ]
        },
        "购物车测试用例": {
            "module": "购物车",
            "description": "购物车功能测试",
            "scenarios": [
                {"name": "添加购物车成功，修改数量成功，结算成功", "type": "正向", "precondition": "打开页面",
                 "steps": "1. 登录\n2. 搜索商品\n3. 添加购物车\n4. 修改购物车数量\n5. 去结算",
                 "test_data": "账号：已注册账号\n商品：任意有库存商品",
                 "expected": "1. 添加购物车成功\n2. 修改购物车商品数量正常显示\n3. 点击结算正常跳转到订单页面"},
                {"name": "添加购物车失败_商品库存不足", "type": "反向", "precondition": "打开页面",
                 "steps": "1. 登录\n2. 搜索商品\n3. 添加购物车", "test_data": "账号：已注册账号\n商品：任意无库存商品",
                 "expected": "添加购物车失败，提示库存不足"},
                {"name": "添加购物车失败_商品ID不存在", "type": "反向", "precondition": "打开页面",
                 "steps": "1. 登录\n2. 搜索商品\n3. 添加购物车", "test_data": "账号：已注册账号\n商品ID：9999（不存在）",
                 "expected": "添加购物车失败，提示购买商品不存在"},
                {"name": "添加购物车失败_商品ID为空", "type": "反向", "precondition": "打开页面",
                 "steps": "1. 登录\n2. 搜索商品\n3. 添加购物车", "test_data": "账号：已注册账号\n商品ID：空",
                 "expected": "添加购物车失败，提示请选择要购买的商品"}
            ]
        },
        "订单测试用例": {
            "module": "订单",
            "description": "订单流程测试（TPSHOP项目）",
            "scenarios": [
                {"name": "下单成功", "type": "正向", "precondition": "1. 打开项目首页页面\n2. 支付账户余额充足",
                 "steps": "1. 搜索商品\n2. 加入购物车\n3. 登录\n4. 下订单\n5. 支付",
                 "test_data": "商品：任意有库存的商品1件\n账号：已注册账号及对应密码",
                 "expected": "下单成功，提示：订单提交成功，我们将在第一时间给你发货"},
                {"name": "下单失败_支付失败_余额不足", "type": "反向", "precondition": "打开项目首页页面",
                 "steps": "1. 搜索商品\n2. 加入购物车\n3. 登录\n4. 下订单\n5. 支付",
                 "test_data": "商品：任意有库存的商品1件\n账号：已注册账号\n支付余额：1元",
                 "expected": "下单失败，提示：余额不足"},
                {"name": "下单失败_登录失败", "type": "反向", "precondition": "打开项目首页页面",
                 "steps": "1. 搜索商品\n2. 加入购物车\n3. 登录\n4. 下订单\n5. 支付",
                 "test_data": "商品：任意有库存的商品1件\n账号：未注册账号", "expected": "下单失败，提示：密码错误"},
                {"name": "下单失败_添加购物车失败_库存不足", "type": "反向", "precondition": "打开项目首页页面",
                 "steps": "1. 搜索商品\n2. 加入购物车\n3. 登录\n4. 下订单\n5. 支付",
                 "test_data": "商品：任意无库存的商品\n账号：已注册账号", "expected": "下单失败，提示：库存不足"},
                {"name": "下单失败_商品不存在", "type": "反向", "precondition": "打开项目首页页面",
                 "steps": "1. 搜索商品\n2. 加入购物车\n3. 登录\n4. 下订单\n5. 支付",
                 "test_data": "商品：任意不存在商品\n账号：已注册账号", "expected": "下单失败，提示：购买商品不存在"},
                {"name": "登录成功+添加购物车成功+未填写收货地址", "type": "反向",
                 "precondition": "账号已注册，商品存在且库存充足",
                 "steps": "1. 打开登录页面\n2. 输入账号、密码、验证码\n3. 点击登录\n4. 添加商品到购物车\n5. 点击去结算\n6. 收货地址为空",
                 "test_data": "账号：已注册手机号\n密码：空\n验证码：正确未过期\n商品：任意库存充足",
                 "expected": "登录成功+添加购物车成功+去结算失败，提示请填写收货人信息"}
            ]
        },
        "售后流程测试用例_退货退款": {
            "module": "售后",
            "description": "退货退款流程测试",
            "scenarios": [
                {"name": "退货退款成功", "type": "正向",
                 "precondition": "1. 已登录账号\n2. 打开订单页面找到要退货退款订单",
                 "steps": "1. 登录已注册账号\n2. 找到需要退货退款订单\n3. 提交退货退款申请\n4. 商家审核\n5. 审核通过\n6. 客户确认商家收货信息并发货\n7. 商家收货\n8. 商家退款",
                 "test_data": "商品：任意已收货订单\n账号：已注册账号及对应密码", "expected": "退款成功"},
                {"name": "退货退款失败_商家审核不通过", "type": "反向",
                 "precondition": "1. 已登录账号\n2. 打开订单页面找到要退货退款订单",
                 "steps": "1. 登录已注册账号\n2. 找到需要退货退款订单\n3. 提交退货退款申请\n4. 商家审核\n5. 审核不通过",
                 "test_data": "商品：任意已收货订单\n账号：已注册账号及对应密码",
                 "expected": "退货退款失败，提示：商家拒绝了你的退款"},
                {"name": "退货退款失败_用户取消服务单", "type": "反向",
                 "precondition": "1. 已登录账号\n2. 打开订单页面找到要退货退款订单",
                 "steps": "1. 登录已注册账号\n2. 找到需要退货退款订单\n3. 提交退货退款申请\n4. 商家审核\n5. 审核通过\n6. 用户取消服务单",
                 "test_data": "商品：任意已收货订单\n账号：已注册账号及对应密码",
                 "expected": "退货退款失败，提示：用户取消了服务单"}
            ]
        }
    }
    return manual_data


def generate_manual_markdown(module_name, data):
    backtick = chr(96)
    content = "# " + module_name + "\n\n"
    content += "## 模块描述\n"
    content += data['description'] + "\n\n"
    content += "## 测试用例\n"

    for scenario in data['scenarios']:
        content += "\n### " + scenario['name'] + "\n\n"
        content += "| 属性 | 值 |\n"
        content += "|------|-----|\n"
        content += "| 测试类型 | " + scenario['type'] + " |\n"
        content += "| 前置条件 | " + scenario['precondition'] + " |\n\n"
        content += "**测试步骤**\n"
        content += scenario['steps'] + "\n\n"
        content += "**测试数据**\n"
        content += backtick * 3 + "\n" + scenario['test_data'] + "\n" + backtick * 3 + "\n\n"
        content += "**预期结果**\n"
        content += scenario['expected'] + "\n\n"
        content += "---\n"

    return content


def main():
    print("=" * 60)
    print("生成手工测试知识库文件")
    print("=" * 60)

    manual_data = get_manual_test_data()
    print(f"读取到 {len(manual_data)} 个模块")

    for name in manual_data.keys():
        print(f"  - {name}")

    manual_dir = os.path.join(KNOWLEDGE_BASE_DIR, "manual")
    os.makedirs(manual_dir, exist_ok=True)
    print(f"\n目标目录: {manual_dir}")

    generated = 0
    for filename, data in manual_data.items():
        content = generate_manual_markdown(data['module'], data)
        filepath = os.path.join(manual_dir, filename + ".md")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"生成: {filename}.md")
        generated += 1

    print("=" * 60)
    print(f"共生成 {generated} 个手工测试知识库文件")
    print(f"保存位置: {manual_dir}")


if __name__ == "__main__":
    main()