# app.py - 统一入口（双模式：口语化版 + 专业化版）
import os
import re
import json
from datetime import datetime
import streamlit as st
import pandas as pd
import time

# 测试用例生成模块
from common import clean_name, check_debug_mode
from testcase_agent import generate_test_cases, export_excel, generate_api_test_full, generate_api_test_full_human
from testcase_ai_agent import generate_ai_test_cases, export_ai_test_result
from database import save_rule, list_all_rules, delete_rule, init_db
from fix_excel import fix_excel_format

# 测试点分析模块
from testpoint_agent import generate_test_points, check_info_completeness, generate_followup_prompt

# ======================
# 页面配置
# ======================
st.set_page_config(page_title="AI测试智能体", page_icon="🧪", layout="wide")

# 初始化数据库
try:
    init_db()
except Exception as e:
    st.error(f"数据库初始化失败: {e}")

st.title("🧪 AI测试智能体")
st.caption("支持：测试点分析 | 手工测试用例 | 接口自动化用例（口语化版/专业化版） | AI系统测试")

# ======================
# 调试模式显示（新增）
# ======================
if check_debug_mode():
    st.sidebar.info("🔧 **调试模式已开启**\n\n日志将输出到控制台")
else:
    if st.sidebar.checkbox("🔧 开启调试模式", value=False, help="开启后将在控制台输出详细日志"):
        os.environ["TEST_AGENT_DEBUG"] = "true"
        st.rerun()

# ======================
# 侧边栏
# ======================
with st.sidebar:
    st.header("📖 使用说明")
    st.markdown("""
    ### 1️⃣ 测试点分析
    - 生成思维导图结构的测试点
    - 输出Markdown格式，可直接粘贴到XMind
    - AI会自动追问补充信息

    ### 2️⃣ 手工测试用例
    - 生成Excel格式，包含测试步骤、断言关键词
    - 适用于手工执行或UI自动化
    - **正向用例**：按业务场景设计（少）
    - **反向用例**：按参数错误值累加（多）

    ### 3️⃣ 接口自动化用例
    - 支持两种输出模式：
      - **Apifox版**：给Apifox用的，适合交给Apifox测试数据
      - **专业化版**：结构化数据，适合自动化测试
    - **正向用例优先级P0**，其他P2

    ### 4️⃣ AI/大模型测试
    - 五大维度：功能、准确性、鲁棒性、用户体验、安全
    - 生成四维分析报告 + 测试用例
    - 安全用例优先级P0
    """)
    st.divider()

    st.markdown("### 🗄️ 规则管理（仅用例生成）")
    with st.expander("添加/更新规则"):
        rule_project = st.text_input("项目名称", key="rule_project")
        rule_module = st.text_input("模块名称", key="rule_module")
        rule_fields = st.text_input("输入字段（JSON数组）", placeholder='["用户名","密码","验证码"]')
        rule_code = st.text_input("验证码来源", placeholder="手动输入固定值8888")
        rule_extra = st.text_input("额外功能", placeholder='["忘记密码"]')
        rule_constraints = st.text_area("约束描述", placeholder="不要生成手机号登录、邮箱登录")
        if st.button("保存规则"):
            save_rule(rule_project, rule_module, rule_fields, rule_code, rule_extra, rule_constraints)
            st.success("规则已保存")

    with st.expander("查看/删除规则"):
        rules = list_all_rules()
        if rules:
            for r in rules:
                st.text(f"[P{str(r[4])}] {r[0]} - {r[1]}")
                if st.button(f"删除 {r[0]}-{r[1]}", key=f"del_{r[0]}_{r[1]}"):
                    delete_rule(r[0], r[1])
                    st.rerun()
        else:
            st.info("暂无规则")

# ======================
# 主界面 - 模式选择
# ======================
st.markdown("### 📌 请选择功能模式")

mode = st.radio(
    "",
    [
        "📋 测试点分析（输出Markdown，可转XMind）",
        "📝 手工测试用例（输出Excel）",
        "🚀 接口自动化用例（输出Excel + Pytest脚本）",
        "🤖 AI/大模型测试（五大维度分析）"
    ],
    horizontal=True,
    label_visibility="collapsed"
)

# ======================
# 公共输入
# ======================
col1, col2 = st.columns(2)
with col1:
    project = st.text_input("📁 项目名称", placeholder="例如：携程旅行 / 客达天下 / Python学习助手")
with col2:
    module = st.text_input("📂 模块名称", placeholder="例如：酒店搜索 / 新增课程 / 登录")

# ======================
# 模式1：测试点分析
# ======================
if mode == "📋 测试点分析（输出Markdown，可转XMind）":
    st.divider()
    st.subheader("📋 测试点分析")

    if "tp_step" not in st.session_state:
        st.session_state.tp_step = "input"
    if "tp_original_input" not in st.session_state:
        st.session_state.tp_original_input = {}
    if "tp_followup_questions" not in st.session_state:
        st.session_state.tp_followup_questions = []
    if "tp_followup_answers" not in st.session_state:
        st.session_state.tp_followup_answers = {}

    if st.session_state.tp_step == "input":
        rules = st.text_area(
            "📝 业务规则（可选，输入越详细生成越准）",
            height=200,
            placeholder="示例：\n- 外卖未支付订单15分钟后自动取消\n- 骑手送达即完成，用户无需手动收货\n- 评价不少于15个汉字",
            help="可以直接粘贴你之前整理的业务规则"
        )

        if st.button("🚀 生成测试点", type="primary", use_container_width=True):
            if not project or not module:
                st.error("❌ 请填写项目名称和模块名称")
            else:
                with st.spinner("🔍 正在分析信息完整性..."):
                    need_followup, questions = check_info_completeness(project, module, rules)

                if need_followup and not rules:
                    st.session_state.tp_step = "followup"
                    st.session_state.tp_original_input = {
                        "project": project,
                        "module": module,
                        "rules": rules
                    }
                    st.session_state.tp_followup_questions = questions
                    st.session_state.tp_followup_answers = {}
                    st.rerun()
                else:
                    with st.spinner("🤖 AI正在生成测试点，请稍候..."):
                        try:
                            content, error = generate_test_points(project, module, rules)
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
                                    use_container_width=True,
                                    key=f"download_tp_{timestamp}"
                                )
                                st.caption("💡 下载后可直接复制到XMind粘贴")
                        except Exception as e:
                            st.error(f"❌ 生成失败：{e}")

    elif st.session_state.tp_step == "followup":
        st.subheader("📋 请补充以下信息")
        st.caption("系统检测到信息不够完整，请回答以下问题，补充后会自动生成测试点")
        answers = {}
        for i, q in enumerate(st.session_state.tp_followup_questions):
            answers[q] = st.text_area(f"**问题 {i + 1}:** {q}", key=f"tp_followup_q_{i}", height=80)
        col_btn1, col_btn2 = st.columns([1, 5])
        with col_btn1:
            if st.button("↩️ 返回修改", use_container_width=True):
                st.session_state.tp_step = "input"
                st.rerun()
        with col_btn2:
            if st.button("✅ 补充完成，生成测试点", type="primary", use_container_width=True):
                full_rules = generate_followup_prompt(st.session_state.tp_original_input, answers)
                with st.spinner("🤖 AI正在生成测试点，请稍候..."):
                    try:
                        content, error = generate_test_points(
                            st.session_state.tp_original_input["project"],
                            st.session_state.tp_original_input["module"],
                            full_rules
                        )
                        if error:
                            st.error(f"❌ {error}")
                            st.session_state.tp_step = "input"
                        else:
                            st.success(f"✅ 生成成功！共 {len(content)} 字符")
                            st.markdown("### 📄 预览")
                            st.markdown(content[:2000])
                            if len(content) > 2000:
                                st.caption(f"... 还有 {len(content) - 2000} 字符，请下载完整文件查看")
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            filename = f"{st.session_state.tp_original_input['project']}_{st.session_state.tp_original_input['module']}_测试点_{timestamp}.md"
                            filename = re.sub(r'[\\/*?:"<>|]', '', filename)
                            st.download_button(
                                label="📥 下载MD文件",
                                data=content,
                                file_name=filename,
                                mime="text/markdown",
                                use_container_width=True,
                                key=f"download_tp_followup_{timestamp}"
                            )
                            st.caption("💡 下载后可直接复制到XMind粘贴")
                            st.session_state.tp_step = "input"
                    except Exception as e:
                        st.error(f"❌ 生成失败：{e}")
                        st.session_state.tp_step = "input"

# ======================
# 模式2：手工测试用例
# ======================
elif mode == "📝 手工测试用例（输出Excel）":
    st.divider()
    st.subheader("📊 用例数量配置")

    col1, col2 = st.columns(2)
    with col1:
        test_type = st.selectbox("测试类型",
                                 ["功能测试", "安全测试", "性能测试", "兼容性测试", "稳定性测试", "异常测试", "全类型"])
    with col2:
        case_num = st.number_input("生成数量", 1, 40, 10)

    st.markdown("### 📝 业务规则（可选）")
    st.caption("规则越详细，用例越精准。优先级：数据库规则 > 这里输入的规则 > 默认规则")
    business_rules = st.text_area(
        "业务规则",
        height=150,
        placeholder="示例：\n- 登录只需要用户名、密码、验证码，验证码固定为8888"
    )

    if st.button("📝 生成用例", type="primary", use_container_width=True):
        if not project or not module:
            st.error("❌ 请填写项目名称和模块名称")
        else:
            type_map = {"功能测试": "功能", "安全测试": "安全", "性能测试": "性能",
                        "兼容性测试": "兼容性", "稳定性测试": "稳定性", "异常测试": "异常", "全类型": ""}
            test_type_value = type_map.get(test_type, "")

            progress_bar = st.progress(0)
            status_text = st.empty()

            with st.spinner(f"正在生成 {case_num} 条手工测试用例..."):
                status_text.text("📝 正在分析业务规则...")
                progress_bar.progress(10)

                cases = generate_test_cases(project, module, test_type_value, case_num, business_rules)

                progress_bar.progress(80)
                status_text.text("📊 正在导出Excel...")

            if cases:
                filepath = export_excel(cases, project, module, test_type_value)
                try:
                    fix_excel_format(filepath)
                except:
                    pass

                progress_bar.progress(100)
                status_text.text("✅ 生成完成！")
                time.sleep(0.5)
                progress_bar.empty()
                status_text.empty()

                st.success(f"✅ 手工用例已生成，共 {len(cases)} 条")

                if os.path.exists(filepath):
                    with open(filepath, "rb") as f:
                        excel_data = f.read()
                    st.download_button(
                        label="📥 下载Excel文件",
                        data=excel_data,
                        file_name=os.path.basename(filepath),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key=f"download_manual_{time.time()}"
                    )

                    df = pd.read_excel(filepath, sheet_name="测试用例")
                    st.subheader("📋 用例预览（前5条）")
                    st.dataframe(df.head(5), use_container_width=True)
            else:
                st.warning("⚠️ 未能生成有效的测试用例，请调整业务规则重试")

# ======================
# 模式3：接口自动化用例（双模式）
# ======================
elif mode == "🚀 接口自动化用例（输出Excel + Pytest脚本）":
    st.divider()

    # 输出模式选择
    output_style = st.radio(
        "📌 输出模式",
        ["📝 口语化版（适合老师/评审，像人写的）", "🚀 专业化版（适合数据驱动，生成Pytest脚本）"],
        horizontal=True,
        help="口语化版：描述口语化，适合交给老师评审；专业化版：结构化数据，可直接用于自动化测试"
    )

    st.subheader("📊 用例数量配置")
    col1, col2 = st.columns(2)
    with col1:
        test_type = st.selectbox("测试类型",
                                 ["功能测试", "安全测试", "性能测试", "兼容性测试", "稳定性测试", "异常测试", "全类型"])
    with col2:
        case_num = st.number_input("期望数量", 1, 40, 10, help="AI会根据业务复杂度自行判断，不强制凑数")

    st.markdown("### 📝 业务规则（可选）")
    st.caption("规则越详细，用例越精准。优先级：数据库规则 > 这里输入的规则 > 默认规则")
    business_rules = st.text_area(
        "业务规则",
        height=150,
        placeholder="示例：\n- 登录只需要用户名、密码、验证码，验证码固定为8888\n- 课程名称1-64个字符\n- 价格必须是正整数"
    )

    if st.button("🚀 生成接口用例", type="primary", use_container_width=True):
        if not project or not module:
            st.error("❌ 请填写项目名称和模块名称")
        else:
            type_map = {"功能测试": "功能", "安全测试": "安全", "性能测试": "性能",
                        "兼容性测试": "兼容性", "稳定性测试": "稳定性", "异常测试": "异常", "全类型": ""}
            test_type_value = type_map.get(test_type, "")

            progress_bar = st.progress(0)
            status_text = st.empty()

            with st.spinner("正在生成接口用例..."):
                status_text.text("📝 正在分析业务规则...")
                progress_bar.progress(10)

                if "口语化版" in output_style:
                    result = generate_api_test_full_human(project, module, test_type_value, case_num, business_rules)
                else:
                    result = generate_api_test_full(project, module, test_type_value, case_num, business_rules)

                progress_bar.progress(80)
                status_text.text("📊 正在导出...")
                time.sleep(0.3)

                progress_bar.progress(100)
                status_text.text("✅ 生成完成！")
                time.sleep(0.5)
                progress_bar.empty()
                status_text.empty()

            if result["cases"]:
                st.success(f"✅ 用例已生成，共 {len(result['cases'])} 条")

                # 下载区域
                download_container = st.container()
                with download_container:
                    st.markdown("### 📥 下载文件")
                    col1, col2 = st.columns(2)

                    with col1:
                        if result["excel_path"] and os.path.exists(result["excel_path"]):
                            with open(result["excel_path"], "rb") as f:
                                excel_data = f.read()
                            st.download_button(
                                label="📥 下载Excel用例",
                                data=excel_data,
                                file_name=os.path.basename(result["excel_path"]),
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True,
                                key=f"download_api_excel_{int(time.time())}"
                            )

                    with col2:
                        if result["pytest_path"] and os.path.exists(result["pytest_path"]):
                            with open(result["pytest_path"], "r", encoding="utf-8") as f:
                                pytest_data = f.read()
                            st.download_button(
                                label="🐍 下载Pytest脚本",
                                data=pytest_data,
                                file_name=os.path.basename(result["pytest_path"]),
                                mime="text/x-python",
                                use_container_width=True,
                                key=f"download_api_pytest_{int(time.time())}"
                            )

                # 预览用例
                st.subheader("📋 用例预览（前5条）")
                if "口语化版" in output_style:
                    preview_df = pd.DataFrame(result["cases"])[["case_id", "test_point", "steps", "expected"]].head(5)
                else:
                    preview_df = pd.DataFrame(result["cases"])[["case_id", "title", "method", "url"]].head(5)
                st.dataframe(preview_df, use_container_width=True)

                if result["pytest_path"]:
                    st.info(f"💡 运行测试：`pytest {os.path.basename(result['pytest_path'])} -v`")
            else:
                st.warning("⚠️ 未能生成有效的用例，请调整业务规则重试")

# ======================
# 模式4：AI/大模型测试
# ======================
else:  # mode == "🤖 AI/大模型测试（五大维度分析）"
    st.divider()
    st.subheader("🤖 AI/大模型测试配置")

    st.markdown("### 📝 系统描述与业务规则")
    if "ai_description" not in st.session_state:
        st.session_state.ai_description = ""
    if "ai_business_rules" not in st.session_state:
        st.session_state.ai_business_rules = ""

    description_input = st.text_area("系统描述", value=st.session_state.ai_description, height=100,
                                     placeholder="描述待测试的AI系统功能...", key="ai_desc_input")
    business_rules_input = st.text_area("业务规则（可选）", value=st.session_state.ai_business_rules, height=100,
                                        placeholder="输入项目的特定规则，会覆盖默认规则...", key="ai_rules_input")

    col_confirm, _ = st.columns([1, 5])
    with col_confirm:
        if st.button("✅ 确认输入", type="primary"):
            st.session_state.ai_description = description_input
            st.session_state.ai_business_rules = business_rules_input
            st.success("已确认")

    if st.session_state.ai_description:
        need_analysis = st.radio("是否需要生成「四大维度分析」？",
                                 ["需要（生成分析报告 + 测试用例）", "不需要（只生成测试用例）"], horizontal=True)
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            func_limit = st.number_input("功能用例上限", 0, 20, 10)
        with col2:
            acc_limit = st.number_input("准确性上限", 0, 20, 8)
        with col3:
            robust_limit = st.number_input("鲁棒性上限", 0, 20, 8)
        with col4:
            ux_limit = st.number_input("用户体验上限", 0, 20, 6)
        with col5:
            sec_limit = st.number_input("安全用例上限", 0, 20, 10)
        limits = {"功能": func_limit, "准确性": acc_limit, "鲁棒性": robust_limit,
                  "用户体验": ux_limit, "安全": sec_limit}

        if st.button("🚀 生成测试文档", type="primary", use_container_width=True):
            if not project or not module:
                st.error("❌ 请填写项目名称和模块名称")
            elif sum(limits.values()) == 0:
                st.error("❌ 请至少设置一种用例的上限")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()

                with st.spinner("正在生成测试文档..."):
                    def update_progress(progress, message):
                        progress_bar.progress(int(progress * 100))
                        status_text.text(message)

                    result = generate_ai_test_cases(
                        project, module, st.session_state.ai_description, limits,
                        ("需要" in need_analysis), st.session_state.ai_business_rules,
                        progress_callback=update_progress
                    )

                    progress_bar.progress(100)
                    status_text.text("✅ 生成完成！")
                    time.sleep(0.5)
                    progress_bar.empty()
                    status_text.empty()

                if "需要" in need_analysis and result.get("analysis"):
                    st.subheader("📋 四大维度分析")
                    st.markdown(result["analysis"])

                st.subheader("📊 测试用例")
                if result.get("cases"):
                    st.dataframe(result["cases"], use_container_width=True)
                    filepath = export_ai_test_result(result, project, module, ("需要" in need_analysis))
                    if filepath and os.path.exists(filepath):
                        with open(filepath, "rb") as f:
                            ai_excel_data = f.read()
                        st.download_button(
                            label="📥 下载Excel文件",
                            data=ai_excel_data,
                            file_name=os.path.basename(filepath),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                            key=f"download_ai_{int(time.time())}"
                        )
                    st.success(f"✅ 生成 {len(result['cases'])} 条用例")
                else:
                    st.warning("⚠️ 未能生成有效的测试用例")

st.divider()
st.caption("🧪 AI测试智能体 | 支持测试点分析 / 手工用例 / 接口用例（口语化版+专业化版）/ AI测试")