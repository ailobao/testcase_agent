"""AI测试智能体 - 主入口"""
import sys
import os

# 将项目根目录添加到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import streamlit as st
import re
from datetime import datetime

# 页面配置
st.set_page_config(
    page_title="AI测试智能体",
    page_icon="🧪",
    layout="wide"
)

# 隐藏右下角工具栏(Manage app/Settings等)
st.markdown(
    "<style>"
    "div[data-testid='stToolbar'], "
    "div[data-testid='stStatusWidget'], "
    "div.stToolbar, "
    "button[kind='toolbar'], "
    "button[title='Manage app'], "
    "button[title='Settings'], "
    "#MainMenu { display: none !important; } "
    "footer { visibility: hidden !important; }"
    "</style>",
    unsafe_allow_html=True,
)

# 导入所有页面
from src.ui.pages import api_page, manual_page, ai_page, testpoint_page


def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.header("📖 使用说明")

        st.markdown("### 🚀 接口自动化用例")
        st.markdown("- 输入项目名称和模块名称")
        st.markdown("- 可选输入业务规则（参数值、约束条件）")
        st.markdown("- AI 自主判断用例数量，不强制凑数")
        st.markdown("- 支持三种导出格式：Excel、JSON、Pytest脚本")

        st.markdown("### 📝 手工测试用例")
        st.markdown("- 生成 Excel 格式的手工测试用例")
        st.markdown("- 支持动态列数据驱动")
        st.markdown("- 测试步骤自动换行显示")

        st.markdown("### 🤖 AI系统测试")
        st.markdown("- 五大维度：功能、准确性、鲁棒性、用户体验、安全")
        st.markdown("- 自动生成四维分析报告")
        st.markdown("- 支持并行生成各维度用例")

        st.markdown("### 📋 测试点分析")
        st.markdown("- 生成树形结构测试点")
        st.markdown("- 支持 Markdown 导出")
        st.markdown("- 可直接粘贴到 XMind")

        st.markdown("### 📝 业务规则示例")
        st.code("""
用户名: admin
密码: 123456
验证码: 8888
        """, language="text")

        st.divider()
        st.caption("🧪 AI测试智能体 v2.0")
        st.caption("支持接口自动化 | 手工测试 | AI系统测试 | 测试点分析")


def main():
    """主函数"""
    st.title("🧪 AI测试智能体")
    st.caption("AI驱动的自动化测试用例生成平台")

    # 渲染侧边栏
    render_sidebar()

    # 主界面 - 模式选择
    mode = st.radio(
        "请选择功能模式",
        ["🚀 接口自动化用例", "📝 手工测试用例", "🤖 AI系统测试", "📋 测试点分析"],
        horizontal=True,
        label_visibility="collapsed"
    )

    # 路由到对应页面
    if mode == "🚀 接口自动化用例":
        api_page.render()
    elif mode == "📝 手工测试用例":
        manual_page.render()
    elif mode == "🤖 AI系统测试":
        ai_page.render()
    elif mode == "📋 测试点分析":
        testpoint_page.render()


main()
