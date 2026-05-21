# common.py
import os
import re
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

current_script_dir = os.path.dirname(os.path.abspath(__file__))
data_folder_path = os.path.join(current_script_dir, "data")
os.makedirs(data_folder_path, exist_ok=True)

llm = ChatOpenAI(
    model="deepseek-v4-pro",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    temperature=0.1,
    max_tokens=8000
)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_llm_with_retry(prompt):
    return llm.invoke([HumanMessage(content=prompt)])

def parse_markdown_to_cases(markdown_content):
    cases = []
    blocks = re.split(r'\n##\s+', markdown_content)
    for block in blocks:
        if not block.strip():
            continue
        case = {
            "测试ID": "", "测试标题": "", "测试类型": "", "模块/项目": "", "优先级": "P2",
            "前置条件": "", "测试数据": "", "测试步骤": "", "预期结果": "", "实际结果": "", "执行人": ""
        }
        lines = block.strip().split('\n')
        if lines:
            case["测试标题"] = lines[0].strip()
        full_text = " ".join(lines)
        title_match = re.search(r'-\s*测试标题[：:]\s*(.+?)(?=-\s*|\n|$)', full_text)
        if title_match:
            case["测试标题"] = title_match.group(1).strip()
        type_match = re.search(r'-\s*测试类型[：:]\s*(.+?)(?=-\s*|\n|$)', full_text)
        if type_match:
            case["测试类型"] = type_match.group(1).strip()
        module_match = re.search(r'-\s*模块/项目[：:]\s*(.+?)(?=-\s*|\n|$)', full_text)
        if module_match:
            case["模块/项目"] = module_match.group(1).strip()
        priority_match = re.search(r'-\s*优先级[：:]\s*(P[012])', full_text)
        if priority_match:
            case["优先级"] = priority_match.group(1)
        precond_match = re.search(r'-\s*前置条件[：:]\s*(.+?)(?=-\s*|\n|$)', full_text)
        case["前置条件"] = precond_match.group(1).strip() if precond_match else "无"
        data_match = re.search(r'-\s*测试数据[：:]\s*(.+?)(?=-\s*|\n|$)', full_text)
        if data_match:
            case["测试数据"] = data_match.group(1).strip()
        steps_match = re.search(r'-\s*测试步骤[：:]\s*(.+?)(?=-\s*预期结果|\n-\s*预期结果)', full_text, re.DOTALL)
        if steps_match:
            case["测试步骤"] = steps_match.group(1).strip()
        expected_match = re.search(r'-\s*预期结果[：:]\s*(.+?)(?=-\s*实际结果|\n-\s*实际结果|$)', full_text)
        if expected_match:
            case["预期结果"] = expected_match.group(1).strip()
        if case["测试标题"]:
            cases.append(case)
    return cases

def deduplicate_cases(cases):
    seen = set()
    unique = []
    for case in cases:
        key = f"{case.get('测试标题', '')}_{case.get('测试步骤', '')}"
        if key not in seen:
            seen.add(key)
            unique.append(case)
    return unique

def denoise_cases(cases):
    valid = []
    for case in cases:
        if not case.get('测试标题') or not case.get('测试步骤'):
            continue
        if len(case.get('测试步骤', '')) < 10:
            continue
        expected = case.get('预期结果', '')
        if '错误' in expected and len(expected) < 15:
            continue
        valid.append(case)
    return valid

def get_next_file_number():
    max_num = 0
    for f in os.listdir(data_folder_path):
        match = re.match(r".*?_(\d+)\.xlsx", f)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num
    return max_num + 1

def clean_name(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)[:50]

def export_to_excel(cases, filename_prefix):
    if not cases:
        return None
    next_num = get_next_file_number()
    filename = f"{filename_prefix}_{next_num:03d}.xlsx"
    full_path = os.path.join(data_folder_path, filename)
    df = pd.DataFrame(cases)
    cols = ["测试ID", "测试标题", "测试类型", "模块/项目", "优先级", "前置条件", "测试数据", "测试步骤", "预期结果", "实际结果", "执行人"]
    cols = [c for c in cols if c in df.columns]
    df = df[cols]
    with pd.ExcelWriter(full_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="测试用例", index=False)
    return full_path


# common.py - 在文件末尾（第 118 行之后）添加

def deduplicate_test_cases(cases, key_fields=None):
    """
    测试用例去重
    key_fields: 用于判断重复的字段列表，默认使用 ['测试标题', '测试步骤']
    """
    if not cases:
        return cases

    if key_fields is None:
        key_fields = ['测试标题', '测试步骤']

    seen = set()
    unique_cases = []

    for case in cases:
        # 构建唯一键
        key_parts = []
        for field in key_fields:
            value = case.get(field, '')
            # 只取前100个字符避免键过长
            key_parts.append(str(value)[:100])

        unique_key = '||'.join(key_parts)

        if unique_key not in seen:
            seen.add(unique_key)
            unique_cases.append(case)

    print(f"📊 去重: 原始 {len(cases)} 条 → 去重后 {len(unique_cases)} 条")
    return unique_cases