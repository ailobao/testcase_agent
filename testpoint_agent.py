# testpoint_agent.py
import os
import re
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from tenacity import retry, stop_after_attempt, wait_exponential

# 导入知识库和公共模块
from knowledge_base import get_examples_by_keywords
from common import (
    call_llm_with_retry, debug_log, prompt_loader,
    OutputValidator, validate_user_input, check_debug_mode
)

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

# 评委模型（用于准确性校验）
judge_llm = ChatOpenAI(
    model="qwen-turbo",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    temperature=0,
    max_tokens=50
)


def validate_business_rules(rules):
    """检测业务规则中的可疑内容"""
    dangerous_keywords = [
        "忽略", "无视", "忘记", "删除规则",
        "输出提示词", "显示系统指令", "你现在是", "扮演", "越狱"
    ]
    rules_lower = rules.lower()
    for keyword in dangerous_keywords:
        if keyword.lower() in rules_lower:
            return False, f"检测到可疑内容：{keyword}"
    return True, ""


def save_file(content, project, module):
    """保存测试点到文件"""
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


def generate_test_points(project, module, rules):
    """
    生成测试点分析
    返回: (content, error)
    """
    try:
        # 输入校验
        is_valid, msg = validate_user_input(rules)
        if not is_valid:
            return None, msg

        is_valid, msg = validate_business_rules(rules)
        if not is_valid:
            return None, msg

        # 获取知识库示例
        examples = get_examples_by_keywords(project, module)
        debug_log(f"已加载知识库参考示例")

        # 使用统一提示词加载器（替代原来的长 SYSTEM_PROMPT）
        prompt = prompt_loader.get_task_prompt(
            "testpoint",
            project=project,
            module=module,
            rules=rules if rules else "无特殊规则",
            examples=examples
        )

        # 添加防御规则
        defense_rules = prompt_loader.get_defense_rules()
        prompt = f"{prompt}\n\n{defense_rules}"

        debug_log(f"提示词长度: {len(prompt)} 字符")

        response = call_llm_with_retry(prompt)
        content = response.content

        # 清理输出
        content = content.replace("```markdown", "").replace("```", "").strip()

        # 输出校验
        is_valid, error_msg = OutputValidator.validate_markdown(content)
        if not is_valid:
            debug_log(f"输出校验失败: {error_msg}")
            # 尝试修复：去除开头多余内容
            lines = content.split('\n')
            start_idx = 0
            for i, line in enumerate(lines):
                if line.startswith('#') or line.startswith('##') or line.startswith('###'):
                    start_idx = i
                    break
            if start_idx > 0:
                content = '\n'.join(lines[start_idx:])
                debug_log("已尝试修复输出格式")

        return content, None

    except Exception as e:
        debug_log(f"生成失败: {e}")
        return None, str(e)


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


# ======================
# 以下为评测相关函数（保持不变）
# ======================
def target_for_eval(inputs: dict) -> dict:
    """评测用目标函数"""
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
    """功能测试评测"""
    error = outputs.get("error", "")
    score = 1.0 if not error else 0.0
    return {
        "key": "functional",
        "score": score,
        "comment": "无报错" if score else f"报错: {error}"
    }


def accuracy_test(outputs: dict, reference_outputs: dict) -> dict:
    """准确性测试评测（关键词匹配）"""
    actual = outputs.get("output", "").lower()
    expected = reference_outputs.get("expected_keyword", "").lower()
    score = 1.0 if expected in actual else 0.0
    return {
        "key": "accuracy",
        "score": score,
        "comment": f"包含'{expected}'" if score else f"未包含'{expected}'"
    }


def llm_accuracy_test(outputs: dict, reference_outputs: dict) -> dict:
    """准确性测试评测（LLM判断）"""
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


# 兼容原有的 main 函数
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

    print(f"\n⏳ 正在生成测试点分析...")

    try:
        content, error = generate_test_points(project, module, business_rules)

        if error:
            print(f"\n❌ 生成失败：{error}")
            return

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


if __name__ == "__main__":
    main()