"""测试点分析页面"""
import sys
import os
import re
import streamlit as st
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from src.agents.testpoint_agent import TestPointAgent
from src.tools.knowledge_loader import get_examples_by_keywords


def render():
    st.subheader("📋 测试点分析")

    st.info("💡 **测试点分析**：生成树形结构测试点，可直接粘贴到XMind生成思维导图")

    col1, col2 = st.columns(2)
    with col1:
        project = st.text_input("📁 项目名称", key="tp_project", placeholder="例如：客达天下")
    with col2:
        module = st.text_input("📂 模块名称", key="tp_module", placeholder="例如：登录、订单")

    business_rules = st.text_area(
        "📝 业务规则（可选，输入越详细生成越准）",
        height=200,
        placeholder="示例：\n- 外卖未支付订单15分钟后自动取消\n- 骑手送达即完成，用户无需手动收货\n- 评价不少于15个汉字",
        key="tp_rules"
    )

    if st.button("🚀 生成测试点", type="primary", use_container_width=True):
        if not project or not module:
            st.error("❌ 请填写项目名称和模块名称")
        else:
            agent = TestPointAgent()

            # 检查信息完整性
            with st.spinner("🔍 正在分析信息完整性..."):
                need_followup, questions = agent.check_info_completeness(project, module, business_rules)

            if need_followup and not business_rules:
                st.warning("⚠️ 信息不够完整，请补充以下信息：")
                answers = {}
                for q in questions:
                    answers[q] = st.text_area(f"**{q}**", key=f"tp_followup_{q[:20]}")

                col1, col2 = st.columns([1, 5])
                with col1:
                    if st.button("↩️ 返回修改"):
                        st.rerun()
                with col2:
                    if st.button("✅ 补充完成，生成测试点", type="primary"):
                        full_rules = agent.generate_followup_prompt(
                            {"project": project, "module": module, "rules": business_rules},
                            answers
                        )
                        with st.spinner("🤖 AI正在生成测试点，请稍候..."):
                            content, error = agent.generate(project, module, full_rules)
                            # 显示追踪 ID
                            trace_id = agent.get_trace_id()
                            if trace_id:
                                st.info(f"🔍 追踪 ID: `{trace_id}`")
                            if error:
                                st.error(f"❌ {error}")
                            else:
                                st.success(f"✅ 生成成功！共 {len(content)} 字符")
                                st.markdown("### 📄 预览")
                                st.markdown(content[:2000])
                                if len(content) > 2000:
                                    st.caption(f"... 还有 {len(content) - 2000} 字符，请下载完整文件查看")

                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                filename = f"{project}_{module}_测试点_{timestamp}.md"
                                filename = re.sub(r'[\\/*?:"<>|]', '', filename)

                                st.download_button(
                                    label="📥 下载MD文件",
                                    data=content,
                                    file_name=filename,
                                    mime="text/markdown",
                                    use_container_width=True
                                )
                                st.caption("💡 下载后可直接复制到XMind粘贴")
            else:
                # 获取知识库示例
                examples = get_examples_by_keywords(project, module)

                with st.spinner("🤖 AI正在生成测试点，请稍候..."):
                    content, error = agent.generate(project, module, business_rules, examples)
                    # 显示追踪 ID
                    trace_id = agent.get_trace_id()
                    if trace_id:
                        st.info(f"🔍 追踪 ID: `{trace_id}`")
                    if error:
                        st.error(f"❌ {error}")
                    else:
                        st.success(f"✅ 生成成功！共 {len(content)} 字符")
                        st.markdown("### 📄 预览")
                        st.markdown(content[:2000])
                        if len(content) > 2000:
                            st.caption(f"... 还有 {len(content) - 2000} 字符，请下载完整文件查看")

                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        filename = f"{project}_{module}_测试点_{timestamp}.md"
                        filename = re.sub(r'[\\/*?:"<>|]', '', filename)

                        st.download_button(
                            label="📥 下载MD文件",
                            data=content,
                            file_name=filename,
                            mime="text/markdown",
                            use_container_width=True
                        )
                        st.caption("💡 下载后可直接复制到XMind粘贴")