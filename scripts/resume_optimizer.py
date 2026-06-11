# scripts/resume_optimizer.py
"""简历优化助手 - 支持多模型调用"""
import sys
import os

# 将项目根目录添加到路径
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage


DEFAULT_PROMPT_TEMPLATE = """你是一个资深的AI软件测试工程师简历优化专家。请帮我优化以下简历内容。

【优化要求】
1. 保持真实性 - 不要编造我没有做过的技术或项目
2. 突出 AI 相关能力 - 强调 LLM、AI测试、自动化等关键词
3. 量化成果 - 把模糊的描述改为有数据的表述
4. 面试官视角 - 写出来的内容要让面试官觉得"这个人有深度"
5. 简洁有力 - 每句话都有信息量，不要空话套话
6. 中文表达 - 使用地道的中文技术表述

【岗位方向】
- 职位：AI软件测试工程师
- 地点：北京
- 薪资区间：15-18k
- 不要金融方向的项目描述

【我的简历内容】
{resume_text}

【输出格式】
请按以下结构输出优化后的简历：

## 个人信息
（优化后的个人简介/求职意向）

## 技能亮点
（3-5个核心技术亮点，每个一句话）

## 项目经历
（优化后的项目描述，用 STAR 法则）

## 工作经历
（优化后的经历描述）

请直接输出优化后的内容，不要加多余的说明。"""


def call_llm_direct(prompt: str, llm: ChatOpenAI) -> str:
    """直接用传入的 LLM 实例调用"""
    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content


def optimize_resume(resume_text: str, extra_instructions: str = "",
                    use_bailian: bool = False, model_name: str = None) -> str:
    """
    调用 LLM 优化简历内容

    参数:
        resume_text: 原始简历文本
        extra_instructions: 额外要求
        use_bailian: 是否使用阿里百炼 DashScope 通道
        model_name: 模型名（None 则用默认）
    """
    prompt = DEFAULT_PROMPT_TEMPLATE.format(resume_text=resume_text)
    if extra_instructions:
        prompt += f"\n\n【额外要求】\n{extra_instructions}"

    if use_bailian:
        # ========== 阿里百炼通道 ==========
        model = model_name or os.getenv("BAILIAN_MODEL", "deepseek-v4-pro")
        api_key = os.getenv("DASHSCOPE_API_KEY")
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

        print("=" * 60)
        print(f"  🤖 调用阿里百炼 DeepSeek V4 Pro...")
        print(f"  📋 模型: {model}")
        print("=" * 60)

        llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.3,
            max_tokens=8000,
            timeout=120,
        )
    else:
        # ========== 默认通道（.env 中 LLM_MODEL 配置） ==========
        from src.core.llm_client import call_llm_with_prompt

        print("=" * 60)
        print(f"  🤖 调用默认 LLM（{os.getenv('LLM_MODEL', '未知')}）...")
        print("=" * 60)

        return call_llm_with_prompt(prompt, use_cache=False)

    return call_llm_direct(prompt, llm)


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python scripts/resume_optimizer.py 简历.txt [选项]")
        print()
        print("选项:")
        print("  --bailian     使用阿里百炼 DeepSeek V4 Pro（消耗百炼额度）")
        print("  --model NAME  指定百炼上的模型名（默认 deepseek-v4-pro）")
        print("  -- \"指令\"     额外要求，如 -- \"目标公司: 字节\"")
        print()
        print("示例:")
        print("  python scripts/resume_optimizer.py 简历.txt --bailian")
        print('  python scripts/resume_optimizer.py 简历.txt --bailian -- "突出AI量化能力"')
        print("  python scripts/resume_optimizer.py 简历.txt")
        sys.exit(1)

    resume_file = sys.argv[1]
    use_bailian = "--bailian" in sys.argv
    model_name = None
    extra = ""

    # 解析 --model
    if "--model" in sys.argv:
        idx = sys.argv.index("--model")
        if idx + 1 < len(sys.argv):
            model_name = sys.argv[idx + 1]

    # 解析额外指令（最后一个 -- 后面的内容，排除 --bailian 和 --model）
    try:
        last_ddash = max(i for i, a in enumerate(sys.argv) if a == "--")
        # 检查 -- 后面是不是 --bailian 或 --model 的参数，如果是就不当指令
        if last_ddash >= 2 and not (sys.argv[last_ddash - 1] in ("--bailian", "--model")):
            extra = " ".join(sys.argv[last_ddash + 1:])
    except ValueError:
        pass

    # 读取简历
    if not os.path.exists(resume_file):
        print(f"[Error] 文件不存在: {resume_file}")
        sys.exit(1)

    with open(resume_file, "r", encoding="utf-8") as f:
        resume_text = f.read()

    if not resume_text.strip():
        print("❌ 简历文件为空")
        sys.exit(1)

    print(f"📄 已读取简历: {resume_file} ({len(resume_text)} 字符)")

    # 调用模型
    result = optimize_resume(resume_text, extra, use_bailian, model_name)

    # 输出结果
    print("\n" + "=" * 60)
    print("  ✅ 优化完成")
    print("=" * 60)
    print(result)

    # 保存到文件
    output_file = resume_file.rsplit(".", 1)[0] + "_优化版.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(result)
    print(f"\n💾 已保存: {output_file}")


if __name__ == "__main__":
    main()
