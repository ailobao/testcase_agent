"""
Streamlit Cloud 入口 — 委托执行 src/ui/app.py
"""
import sys
import os

root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, root)
os.chdir(root)

import runpy
runpy.run_path(os.path.join(root, "src", "ui", "app.py"), run_name="__main__")
