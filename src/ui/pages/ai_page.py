"""AI系统测试页面"""
import sys
import os
import streamlit as st

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from src.agents.ai_agent import AITestAgent


def render():
    st.subheader("🤖 AI/大模型测试")

    st.info("💡 **五大维度测试**：功能、准确性、鲁棒性、用户体验、安全")

    col1, col2 = st.columns(2)
    with col1:
        project = st.text_input("📁 项目名称", key="ai_project", placeholder="例如：智能客服系统")
    with col2:
        module = st.text_input("📂 模块名称", key="ai_module", placeholder="例如：问答模块")

    description = st.text_area(
        "📝 系统描述",
        height=100,
        placeholder="描述待测试的AI系统功能...",
        key="ai_description"
    )

    business_rules = st.text_area(
        "📝 业务规则（可选）",
        height=100,
        placeholder="输入项目的特定规则...",
        key="ai_rules"
    )

    need_analysis = st.radio(
        "是否需要生成四大维度分析报告？",
        ["需要（生成分析报告 + 测试用例）", "不需要（只生成测试用例）"],
        horizontal=True
    )

    st.markdown("### 📊 各维度用例数量配置")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        func_limit = st.number_input("功能用例上限", min_value=0, max_value=20, value=10)
    with col2:
        acc_limit = st.number_input("准确性上限", min_value=0, max_value=20, value=8)
    with col3:
        robust_limit = st.number_input("鲁棒性上限", min_value=0, max_value=20, value=8)
    with col4:
        ux_limit = st.number_input("用户体验上限", min_value=0, max_value=20, value=6)
    with col5:
        sec_limit = st.number_input("安全用例上限", min_value=0, max_value=20, value=10)

    limits = {
        "功能": func_limit,
        "准确性": acc_limit,
        "鲁棒性": robust_limit,
        "用户体验": ux_limit,
        "安全": sec_limit
    }

    if st.button("🚀 生成测试文档", type="primary", use_container_width=True):
        if not project or not module:
            st.error("❌ 请填写项目名称和模块名称")
        elif not description:
            st.error("❌ 请填写系统描述")
        elif sum(limits.values()) == 0:
            st.error("❌ 请至少设置一种用例的上限")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()

            def update_progress(progress, message):
                progress_bar.progress(int(progress * 100))
                status_text.text(message)

            with st.spinner("正在生成测试文档..."):
                agent = AITestAgent()
                result = agent.generate(
                    project, module, description, limits,
                    ("需要" in need_analysis), business_rules,
                    progress_callback=update_progress
                )

                # 显示追踪 ID
                trace_id = agent.get_trace_id()
                if trace_id:
                    st.info(f"🔍 追踪 ID: `{trace_id}`\n\n💡 保存此 ID 以便在日志中定位本次请求")

                progress_bar.progress(100)
                status_text.text("✅ 生成完成！")

                if "需要" in need_analysis and result.get("analysis"):
                    st.subheader("📋 四大维度分析")
                    st.markdown(result["analysis"])

                st.subheader("📊 测试用例")
                if result.get("cases"):
                    st.dataframe(result["cases"], use_container_width=True)

                    filepath = agent.export_excel(result, project, module, ("需要" in need_analysis))
                    if filepath and os.path.exists(filepath):
                        with open(filepath, "rb") as f:
                            st.download_button(
                                label="📥 下载Excel文件",
                                data=f.read(),
                                file_name=os.path.basename(filepath),
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )
                    st.success(f"✅ 生成 {len(result['cases'])} 条用例")
                else:
                    st.warning("⚠️ 未能生成有效的测试用例")