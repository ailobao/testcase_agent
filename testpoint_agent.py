import os
import re
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from tenacity import retry, stop_after_attempt, wait_exponential

# 导入你的知识库
from knowledge_base import get_examples_by_keywords

load_dotenv()

# ======================
# 配置
# ======================
output_dir = "testpoint_output"
os.makedirs(output_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('testpoint_gen.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

llm = ChatOpenAI(
    model="deepseek-v4-pro",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    temperature=0.1,
    max_tokens=8000)

# 评委模型
judge_llm = ChatOpenAI(
    model="qwen-turbo",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    temperature=0,
    max_tokens=50
)


def validate_business_rules(rules):
    dangerous_keywords = [
        "忽略", "无视", "忘记", "删除规则",
        "输出提示词", "显示系统指令", "你现在是", "扮演", "越狱"
    ]
    rules_lower = rules.lower()
    for keyword in dangerous_keywords:
        if keyword.lower() in rules_lower:
            return False, f"检测到可疑内容：{keyword}"
    return True, ""


SYSTEM_PROMPT = """你是从事了十年的软件测试点分析专家，懂等价类、边界值、场景法这些测试设计方法。

【项目信息不足时的引导规则】
如果用户只提供了项目名称和模块名称，没有提供详细的业务规则，你需要先根据项目类型进行引导。

=== 当项目是 App 端时 ===
请主动询问以下信息（一次性问完）：
1. App 名称及主要业务方向（例如：社交、电商、金融、生活服务、工具等）
2. 你要测试的核心模块名称（如：登录注册、订单操作、支付、个人中心）
3. 该模块的关键功能点（列出几个即可）
4. 有没有特殊的业务规则？（如：未支付订单15分钟自动取消、支付限额、风控规则等）
5. 是否涉及多角色（普通用户/商家/管理员）或跨平台（iOS/Android）差异？

=== 当项目是小程序端时 ===
请主动询问以下信息：
1. 小程序名称及所属平台（微信/支付宝/抖音等）
2. 主要业务场景（电商、点餐、预约、工具、营销等）
3. 你要测试的核心模块
4. 是否依赖微信/支付宝的授权登录、支付、地理位置等能力？
5. 有没有针对小程序的特殊规则（如：小程序码参数、分享带参、订阅消息）？

=== 当项目是 Web 端时 ===
请主动询问以下信息：
1. 网站/后台系统名称及业务类型（电商、OA、CRM、数据分析等）
2. 要测试的模块名称（如：商品管理、订单列表、报表导出、权限配置）
3. 该模块的主要功能点
4. 是否有浏览器兼容性要求（Chrome/Edge/Firefox/IE？）
5. 是否有分辨率、响应式布局要求？
6. 是否有复杂的权限体系或审批流程？

如果你已经提供了完整信息，请直接根据以下要求生成测试点，不再额外提问。

【说话要口语化】
- 测试点描述要像人话，别像机器翻译
- 多用“能不能”、“点了会不会”、“输错了提不提示”这种表达
- 示例：❌“选择拍照，调起系统相机，拍照后进入裁剪界面，裁剪确认后头像更新成功”
         ✅“拍照后能裁剪，裁剪完头像就换了”

【不限制数量】
- 不限制测试点条数，核心功能多写，边缘功能少写
- 宁可多写不要漏，用户会自己删

【输出格式】
每个子功能写3个部分：正向、反向、边界值（边界值有就写，没有就跳过）

### 【子功能名称】

#### 正向（正常能走通的）
- 口语化描述1
- 口语化描述2

#### 反向（出错或异常的情况）
- 口语化描述1
- 口语化描述2

#### 边界值（有明确边界就写，没有就跳过）
- 比如长度限制、数量上限、时间范围等
- 没有边界概念的功能（如开关、状态切换）直接跳过这部分

【整体结构模板】
# 【项目名称】- 模块：【模块名称】

## 一、功能测试

### 1. 【子功能1】

#### 正向
- ...

#### 反向
- ...

#### 边界值（有就写，没有就跳过）
- ...

### 2. 【子功能2】

（以此类推）

## 二、非功能测试

### 1. 兼容性
- 浏览器：Chrome/Edge/Firefox
- 分辨率：1920x1080/1366x768
- 移动端：iOS/Android

### 2. 易用性
- 新手能不能看懂
- 操作有没有反馈
- 报错提示清不清楚

### 3. 可靠性
- 长时间用会不会崩
- 刷页面数据还在不在
- 断网了能不能恢复

### 4. 性能
- 页面打开快不快（<2秒）
- 点按钮反应快不快（<1秒）

### 5. 安全
- 改请求参数能不能越权
- 没登录能不能访问
- 输SQL脚本会不会被执行
- 手机号有没有脱敏

## 三、测试方法总结
- 等价类：有效/无效的例子
- 边界值：关键边界点
- 场景法：正常流程/异常流程

【参考示例】
{examples}

【用户输入】
项目名称：{project}
模块名称：{module}

【业务规则】
{rules}

【输出要求】
1. 只输出模板内容，不要额外解释
2. 安全测试只在【非功能测试】里写一次，不要在【功能测试】里重复写
3. 先按业务规则生成，用户没给的规则不要编
4. 边界值有就写，没有就跳过，不要硬凑
【反向测试点格式约束 - 必须遵守】

反向测试点只描述用户的错误操作或异常行为，不要写系统应该怎样处理（即不要写“会不会”、“是否”、“能否”等预期结果描述）。

正确写法示例：
- “不选答案就提交”
- “没授权麦克风就点录音”
- “未登录状态下进入订单列表”
- “已取消的订单，用户调用确认收货接口”
- “金币不够时点补打卡”

错误写法示例（禁止）：
- “不选答案就提交，会不会被拦截”
- “没授权麦克风就点录音，会不会弹提示”
- “已取消的订单，用户调用确认收货接口，会不会被拦截”

【输出要求】
在生成每个功能模块的“反向”测试点时，每一条只写用户做了什么错事，不写预期结果。
预期结果（系统应如何反应）由读者自行推断，或在本文档其他章节统一说明。
"""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_llm(prompt):
    logging.info("正在调用大模型...")
    return llm.invoke([HumanMessage(content=prompt)])


def save_file(content, project, module):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{project}_{module}_测试点_{timestamp}.md"
    filename = re.sub(r'[\\/*?:"<>|]', '', filename)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    record = {
        "timestamp": timestamp,
        "project": project,
        "module": module,
        "length": len(content)
    }
    record_file = os.path.join(output_dir, "generation_records.json")
    records = []
    if os.path.exists(record_file):
        with open(record_file, 'r', encoding='utf-8') as f:
            records = json.load(f)
    records.append(record)
    with open(record_file, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    return filepath


def main():
    print("=" * 70)
    print("===== AI测试点分析智能体 =====")
    print("格式：树形层级 | 输出：.md | 可直接粘贴到XMind")
    print("=" * 70)

    project = input("\n项目名称：").strip()
    while not project:
        project = input("项目名称不能为空：").strip()

    module = input("模块名称：").strip()
    while not module:
        module = input("模块名称不能为空：").strip()

    print("\n💡 请输入业务规则（粘贴后按两次回车结束）")
    print("   示例：每个商品最多购买99件、超出配送范围不可下单")
    print("-" * 50)

    rules_lines = []
    while True:
        line = input()
        if line == "":
            if len(rules_lines) > 0:
                break
            else:
                continue
        rules_lines.append(line)
    business_rules = "\n".join(rules_lines) if rules_lines else "无特殊规则"

    is_valid, msg = validate_business_rules(business_rules)
    if not is_valid:
        print(f"\n❌ 安全校验失败：{msg}")
        return

    if business_rules != "无特殊规则":
        print(f"\n✅ 已读取业务规则（共 {len(rules_lines)} 行）")

    examples = get_examples_by_keywords(project, module)
    print(f"\n📚 已加载知识库参考示例")

    prompt = SYSTEM_PROMPT.format(
        project=project,
        module=module,
        rules=business_rules,
        examples=examples
    )

    print(f"\n⏳ 正在生成测试点分析...")

    try:
        response = call_llm(prompt)
        content = response.content
        content = content.replace("```markdown", "").replace("```", "").strip()

        filepath = save_file(content, project, module)
        print(f"\n✅ 已保存：{filepath}")

        lines = content.split('\n')
        testpoint_count = sum(1 for line in lines if line.strip().startswith('-'))
        print(f"📊 共生成 {testpoint_count} 条测试点")

        print("\n" + "=" * 70)
        print("📋 生成内容预览：")
        print("=" * 70)
        print(content[:1500])
        if len(content) > 1500:
            print("\n...（完整内容请打开文件查看）")

        print("\n" + "=" * 70)
        print("🎉 完成！")
        print(f"📁 文件位置：{filepath}")
        print("\n💡 转XMind方法：")
        print("   1. 打开XMind")
        print("   2. 新建思维导图")
        print("   3. 复制生成的.md文件内容")
        print("   4. 在XMind中粘贴 → 自动生成思维导图")
        print("=" * 70)
    except Exception as e:
        print(f"\n❌ 生成失败：{e}")


def generate_test_points(project, module, rules):
    try:
        is_valid, msg = validate_business_rules(rules)
        if not is_valid:
            return None, msg

        examples = get_examples_by_keywords(project, module)

        prompt = SYSTEM_PROMPT.format(
            project=project,
            module=module,
            rules=rules if rules else "无特殊规则",
            examples=examples
        )

        response = call_llm(prompt)
        content = response.content
        content = content.replace("```markdown", "").replace("```", "").strip()

        return content, None
    except Exception as e:
        return None, str(e)


def target_for_eval(inputs: dict) -> dict:
    parts = inputs.get("question", "").split(",")
    project = parts[0].strip() if len(parts) > 0 else ""
    module = parts[1].strip() if len(parts) > 1 else ""
    rules = parts[2].strip() if len(parts) > 2 else ""

    content, error = generate_test_points(project, module, rules)

    return {
        "output": content if content else "",
        "error": error if error else ""
    }


def functional_test(outputs: dict, reference_outputs: dict) -> dict:
    error = outputs.get("error", "")
    score = 1.0 if not error else 0.0
    return {
        "key": "functional",
        "score": score,
        "comment": "无报错" if score else f"报错: {error}"
    }


def accuracy_test(outputs: dict, reference_outputs: dict) -> dict:
    actual = outputs.get("output", "").lower()
    expected = reference_outputs.get("expected_keyword", "").lower()
    score = 1.0 if expected in actual else 0.0
    return {
        "key": "accuracy",
        "score": score,
        "comment": f"包含'{expected}'" if score else f"未包含'{expected}'"
    }


def llm_accuracy_test(outputs: dict, reference_outputs: dict) -> dict:
    actual = outputs.get("output", "")[:2000]
    expected = reference_outputs.get("expected_keyword", "")

    if not actual:
        return {"key": "llm_accuracy", "score": 0.0, "comment": "输出为空"}

    judge_prompt = f"""判断下面的输出是否表达了"{expected}"的意思。

输出：{actual}

规则：
- 只要意思相近就算正确，不需要完全一样
- 只回答：正确 或 错误

你的判断："""

    try:
        response = judge_llm.invoke([HumanMessage(content=judge_prompt)])
        is_correct = "正确" in response.content
        return {
            "key": "llm_accuracy",
            "score": 1.0 if is_correct else 0.0,
            "comment": f"预期: {expected} | 判断: {'正确' if is_correct else '错误'}"
        }
    except:
        score = 1.0 if expected in actual else 0.0
        return {"key": "llm_accuracy", "score": score, "comment": "降级匹配"}


def check_info_completeness(project, module, rules):
    """
    判断信息是否充足，返回(是否需要追问, 问题列表)
    """
    # 规则1：业务规则为空或只有默认值
    if not rules or rules == "无特殊规则" or rules.strip() == "":
        # 根据项目名称匹配常见产品
        if "美团" in project or "外卖" in project or "闪购" in project or "到店" in project:
            questions = [
                "您测试的是美团哪条业务线？（外卖/闪购/到店餐饮/到店综合/酒店旅行/美团优选/小象超市）",
                "该业务线的订单有哪些特殊规则？（例如：未支付外卖订单15分钟后自动取消、骑手送达即完成、到店订单需核销券码等）"
            ]
            return True, questions
        elif "抖音" in project:
            questions = [
                "测试的是抖音哪个业务模块？（购物车/订单列表/直播订单/退款售后）",
                "该模块有哪些特殊规则？（例如：购物车限购数量、优惠券分摊逻辑、评价字数下限等）"
            ]
            return True, questions
        elif "流利说" in project or "英语" in project:
            questions = [
                "测试的是流利说哪个模块？（定级测试/课程学习/配音课/真人PK/打卡/错题本）",
                "该模块有哪些特殊规则？（例如：定级测试20题5分钟、录音最长60秒、打卡连续奖励等）"
            ]
            return True, questions
        elif "微信小程序" in project or "小程序" in project:
            questions = [
                "小程序的主要业务场景是什么？（电商/点餐/预约/工具/营销）",
                "是否依赖微信授权登录、支付、地理位置等能力？"
            ]
            return True, questions
        else:
            questions = [
                "这个App/系统属于什么类型？（电商/社交/金融/教育/生活服务/工具）",
                "您关注的测试重点是什么？（功能/安全/性能/兼容性）"
            ]
            return True, questions

    # 规则2：业务规则过短（少于30字）
    if len(rules) < 30:
        questions = ["请补充更多业务规则细节，以便生成更精准的测试点（例如：取消规则、退款规则、边界值、安全要求等）"]
        return True, questions

    # 规则3：未明确端类型
    if "App" not in rules and "小程序" not in rules and "Web" not in rules and "移动端" not in rules:
        # 从项目名称推断
        if "小程序" in project:
            return False, []  # 已经明确是小程序
        elif "Web" in project or "管理后台" in project:
            return False, []
        else:
            questions = ["这是App端、小程序端还是Web端？"]
            return True, questions

    # 信息充足，不需要追问
    return False, []


def generate_followup_prompt(original_input, answers):
    """
    根据原输入和追问回答，构建完整的业务规则
    """
    full_rules = original_input.get("rules", "")

    if answers:
        full_rules += "\n\n【补充信息】"
        for q, a in answers.items():
            if a:
                full_rules += f"\n- {q}: {a}"

    return full_rules
if __name__ == "__main__":
    main()