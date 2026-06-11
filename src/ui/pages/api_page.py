"""接口自动化用例页面 - 支持多格式独立下载"""
import sys
import os
import json
import streamlit as st

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from src.agents.api_agent import APITestAgent


def render():
    st.subheader("🚀 接口自动化用例")

    st.info("💡 **AI 自主判断用例数量**：系统会根据业务复杂度自动生成合适的用例数量，不会强制凑数，也不会遗漏重要场景。")

    col1, col2 = st.columns(2)
    with col1:
        project = st.text_input("📁 项目名称", key="api_project", placeholder="例如：客达天下")
    with col2:
        module = st.text_input("📂 模块名称", key="api_module", placeholder="例如：登录、新增课程")

    business_rules = st.text_area(
        "📝 业务规则（可选，越详细越准确）",
        height=150,
        placeholder="示例：\n用户名: hmadmin\n密码: qqqqqq\n验证码: 3333\nuuid: 2222"
    )

    # 生成按钮
    if st.button("🚀 生成接口用例", type="primary", use_container_width=True):
        if not project or not module:
            st.error("❌ 请填写项目名称和模块名称")
        else:
            with st.spinner("正在生成用例（AI自主判断数量 + 代码补充）..."):
                agent = APITestAgent()
                cases = agent.generate(project, module, business_rules)

                # 显示追踪 ID（可从 agent 获取，即使 end_trace 后也可读取）
                trace_id = agent.get_trace_id()
                if trace_id:
                    st.info(f"🔍 追踪 ID: `{trace_id}`\n\n💡 保存此 ID 以便在日志中定位本次请求")

                if cases:
                    # 保存到 session_state，避免刷新丢失
                    st.session_state['generated_cases'] = cases
                    st.session_state['generated_project'] = project
                    st.session_state['generated_module'] = module

                    # 统计
                    p0_count = sum(1 for c in cases if c.get("priority") == "P0")
                    p2_count = len(cases) - p0_count

                    st.success(f"✅ 生成 {len(cases)} 条用例（AI 根据业务复杂度自主判断）")
                    st.caption(f"📊 P0优先级: {p0_count} 条 | P2优先级: {p2_count} 条")

                    # 预览
                    st.subheader("📋 用例预览（前10条）")
                    preview_data = []
                    for case in cases[:10]:
                        preview_data.append({
                            "用例编号": case.get("case_id", ""),
                            "标题": case.get("title", "")[:60],
                            "方法": case.get("method", ""),
                            "优先级": case.get("priority", ""),
                        })
                    st.dataframe(preview_data, use_container_width=True)

                    if len(cases) > 10:
                        st.caption(f"... 还有 {len(cases) - 10} 条用例，请下载完整文件查看")
                else:
                    st.warning("⚠️ 未能生成用例，请检查项目/模块名称是否正确，或重试")

    # ======================
    # 下载区域（独立于生成按钮，不会刷新）
    # ======================
    if 'generated_cases' in st.session_state and st.session_state['generated_cases']:
        st.divider()
        st.markdown("### 📥 下载文件")

        cases = st.session_state['generated_cases']
        project = st.session_state['generated_project']
        module = st.session_state['generated_module']

        agent = APITestAgent()

        col1, col2, col3 = st.columns(3)

        with col1:
            # Excel 下载按钮
            excel_path = agent.export_excel(cases, project, module)
            if excel_path and os.path.exists(excel_path):
                with open(excel_path, "rb") as f:
                    st.download_button(
                        label="📊 下载 Excel 文件",
                        data=f.read(),
                        file_name=os.path.basename(excel_path),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="download_excel"
                    )

        with col2:
            # JSON 下载按钮
            json_path = agent.export_data_driver(cases, project, module)
            if json_path and os.path.exists(json_path):
                with open(json_path, "rb") as f:
                    st.download_button(
                        label="📋 下载 JSON 文件",
                        data=f.read(),
                        file_name=os.path.basename(json_path),
                        mime="application/json",
                        use_container_width=True,
                        key="download_json"
                    )

        with col3:
            # Pytest 下载按钮
            pytest_path = agent.export_pytest_script(cases, project, module)
            if pytest_path and os.path.exists(pytest_path):
                with open(pytest_path, "rb") as f:
                    st.download_button(
                        label="🐍 下载 Pytest 脚本",
                        data=f.read(),
                        file_name=os.path.basename(pytest_path),
                        mime="text/x-python",
                        use_container_width=True,
                        key="download_pytest"
                    )

