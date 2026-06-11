"""将原 knowledge_base.py 的内容迁移到 .md 文件"""
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入原知识库
from knowledge_base import KNOWLEDGE_BASE

# 知识库目录
KNOWLEDGE_BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base")
os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)

for key, content in KNOWLEDGE_BASE.items():
    filepath = os.path.join(KNOWLEDGE_BASE_DIR, f"{key}.md")
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content.strip())
    print(f"✅ 迁移: {key}.md")

print(f"共迁移 {len(KNOWLEDGE_BASE)} 个知识库文件")