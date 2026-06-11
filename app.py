"""
Streamlit Cloud 入口 — 执行 src/ui/app.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入即执行（Streamlit 脚本在模块级别运行）
import src.ui.app
