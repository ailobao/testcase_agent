"""手工测试用例页面 - 支持动态列数据驱动，无强制数量限制"""
import sys
import os
import streamlit as st

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from src.agents.manual_agent import ManualTestAgent


def render():
    st.subheader("📝 手工测试用例")

    st.info("💡 **AI 自主判断用例数量**：系统会根据业务复杂度自动生成合适的用例数量，不会强制凑数，也不会遗漏重要场景。")

    col1, col2 = st.columns(2)
    with col1:
        project = st.text_input("📁 项目名称", key="manual_project", placeholder="例如：客达天下")
    with col2:
        module = st.text_input("📂 模块名称", key="manual_module", placeholder="例如：登录、新增课程")

    col1, col2 = st.columns(2)
    with col1:
        test_type = st.selectbox(
            "测试类型",
            ["功能测试", "安全测试", "性能测试", "兼容性测试", "稳定性测试", "异常测试", "全类型"],
            key="manual_type"
        )
    with col2:
        case_num = st.number_input(
            "期望展示数量（0=不限，AI不会强制凑数）",
            min_value=0,
            max_value=40,
            value=10,
            key="manual_num",
            help="AI会根据业务复杂度自主判断用例数量，此值仅作展示上限，不会强制生成凑数用例"
        )

    business_rules = st.text_area(
        "📝 业务规则（可选，越详细越准确）",
        height=150,
        placeholder="示例：\n用户名: admin\n密码: 123456\n验证码: 8888"
    )

    if st.button("📝 生成用例", type="primary", use_container_width=True):
        if not project or not module:
            st.error("❌ 请填写项目名称和模块名称")
        else:
            type_map = {
                "功能测试": "功能",
                "安全测试": "安全",
                "性能测试": "性能",
                "兼容性测试": "兼容性",
                "稳定性测试": "稳定性",
                "异常测试": "异常",
                "全类型": ""
            }
            test_type_value = type_map.get(test_type, "")

            with st.spinner(f"正在生成手工测试用例..."):
                agent = ManualTestAgent()
                cases, fields = agent.generate(project, module, test_type_value, case_num, business_rules)

                # 显示追踪 ID
                trace_id = agent.get_trace_id()
                if trace_id:
                    st.info(f"🔍 追踪 ID: `{trace_id}`\n\n💡 保存此 ID 以便在日志中定位本次请求")

                if cases:
                    st.success(f"✅ 生成 {len(cases)} 条用例（AI 根据业务复杂度自主判断）")

                    # 显示动态字段
                    if fields:
                        st.caption(f"📊 动态列: {', '.join(fields)}")

                    # 预览
                    st.subheader("📋 用例预览（前5条）")
                    preview_data = []
                    for case in cases[:5]:
                        preview_item = {
                            "用例ID": case.get("用例ID", ""),
                            "标题": case.get("标题", "")[:40],
                            "优先级": case.get("优先级", ""),
                        }
                        # 添加动态字段预览
                        for field in fields[:2]:
                            preview_item[field] = case.get(field, "")[:20]
                        preview_data.append(preview_item)

                    st.dataframe(preview_data, use_container_width=True)

                    if len(cases) > 10:
                        st.caption(f"... 还有 {len(cases) - 5} 条用例，请下载完整文件查看")

                    # 导出Excel
                    filepath = agent.export_excel(cases, project, module, test_type_value, fields)
                    if filepath and os.path.exists(filepath):
                        with open(filepath, "rb") as f:
                            st.download_button(
                                label="📥 下载 Excel 文件",
                                data=f.read(),
                                file_name=os.path.basename(filepath),
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )
                else:
                    st.warning("⚠️ 未能生成有效的测试用例，请调整业务规则重试")