# app.py
import os
import streamlit as st
from common import clean_name
from testcase_agent import generate_test_cases, export_excel
from testcase_ai_agent import generate_ai_test_cases, export_ai_test_result
from database import save_rule, list_all_rules, delete_rule, init_db
from fix_excel import fix_excel_format
import pandas as pd
import time

# 页面配置
st.set_page_config(page_title="AI测试用例生成器", page_icon="🧪", layout="wide")

# 初始化数据库
try:
    init_db()
except Exception as e:
    st.error(f"数据库初始化失败: {e}")

st.title("🧪 AI测试用例生成器")
st.caption("支持传统项目测试和AI系统测试 | 规则优先级：数据库规则 > 用户输入规则 > 默认规则")

# 侧边栏
with st.sidebar:
    st.header("📖 使用说明")
    st.markdown("""
    ### 传统项目测试
    1. 填写项目名称和模块名称
    2. 输入业务规则（可选，越详细越准）
    3. 选择测试类型，配置数量
    4. 点击「生成用例」

    ### AI/大模型测试
    1. 填写项目名称和模块名称
    2. 输入系统描述和业务规则
    3. 点击确认，选择是否需要四大维度分析
    4. 配置各维度上限，点击生成

    ### 输出格式
    - 完整数据驱动格式（用例ID、标题、参数列、前置条件、测试步骤、预期结果、实际结果、优先级）
    - 预期结果为简洁断言关键词，如：登录成功、密码错误
    - 测试步骤自动换行显示（1. 2. 3.）
    - 实际结果列留空，由你自己的脚本执行后写入
    - Excel 自动美化（表头蓝底白字、列宽自适应、边框）
    """)
    st.divider()

    st.markdown("### 🗄️ 规则管理")
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

# 主界面
col1, col2 = st.columns(2)
with col1:
    project = st.text_input("📁 项目名称", placeholder="例如：携程旅行 / tpshop商城")
with col2:
    module = st.text_input("📂 模块名称", placeholder="例如：酒店搜索 / 登录")

test_category = st.radio("请选择测试类型", ["传统项目测试", "AI/大模型测试"], horizontal=True)

# ======================
# 传统项目测试
# ======================
if test_category == "传统项目测试":
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
        placeholder="示例：\n- 登录只需要用户名、密码、验证码，验证码固定为8888\n- 没有手机号登录、没有短信验证码\n- 没有密码显隐切换（眼睛图标）"
    )

    if st.button("📝 生成用例", type="primary", use_container_width=True):
        if not project or not module:
            st.error("❌ 请填写项目名称和模块名称")
        else:
            # 创建进度条
            progress_bar = st.progress(0)
            status_text = st.empty()

            with st.spinner(f"正在生成 {case_num} 条测试用例..."):
                status_text.text("📝 正在分析业务规则...")
                progress_bar.progress(10)

                type_map = {"功能测试": "功能", "安全测试": "安全", "性能测试": "性能",
                            "兼容性测试": "兼容性", "稳定性测试": "稳定性", "异常测试": "异常", "全类型": ""}
                test_type_value = type_map.get(test_type, "")

                status_text.text(f"🎯 正在生成 {case_num} 条用例...")
                progress_bar.progress(30)

                cases = generate_test_cases(project, module, test_type_value, case_num, business_rules)

                progress_bar.progress(80)
                status_text.text("📊 正在导出Excel...")

            if cases:
                filepath = export_excel(cases, project, module, test_type_value)
                # 美化Excel格式
                fix_excel_format(filepath)

                progress_bar.progress(100)
                status_text.text("✅ 生成完成！")
                time.sleep(0.5)
                progress_bar.empty()
                status_text.empty()

                st.success(f"✅ 用例已生成并美化，共 {len(cases)} 条")
                st.info(f"📁 文件位置：{filepath}")

                if os.path.exists(filepath):
                    with open(filepath, "rb") as f:
                        st.download_button(
                            label="📥 下载Excel文件",
                            data=f,
                            file_name=os.path.basename(filepath),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )

                    # 显示前几条预览
                    df = pd.read_excel(filepath, sheet_name="测试用例")
                    st.subheader("📋 用例预览（前5条）")
                    st.dataframe(df.head(5), use_container_width=True)
            else:
                st.warning("⚠️ 未能生成有效的测试用例，请调整业务规则重试")

# ======================
# AI/大模型测试
# ======================
else:
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
                # 创建进度条
                progress_bar = st.progress(0)
                status_text = st.empty()

                with st.spinner("正在生成测试文档..."):
                    def update_progress(progress, message):
                        progress_bar.progress(int(progress * 100))
                        status_text.text(message)

                    status_text.text("🔍 正在分析系统描述...")
                    progress_bar.progress(10)

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
                            st.download_button(
                                label="📥 下载Excel文件",
                                data=f,
                                file_name=os.path.basename(filepath),
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )
                    st.success(f"✅ 生成 {len(result['cases'])} 条用例")
                else:
                    st.warning("⚠️ 未能生成有效的测试用例")

st.divider()
st.caption("🧪 AI测试用例生成器 | 数据驱动标准格式 | 预期结果为断言关键词 | 测试步骤自动换行 | Excel自动美化")