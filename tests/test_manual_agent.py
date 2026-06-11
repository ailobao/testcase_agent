"""测试手工测试用例 Agent — 含错误降级覆盖"""
import sys
import os
import pytest
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.manual_agent import ManualTestAgent


class TestManualTestAgent:
    """手工测试用例 Agent 单元测试"""

    def setup_method(self):
        self.agent = ManualTestAgent()
        self.project = "客达天下"
        self.module = "登录"

    # ====================== 输入校验 ======================

    def test_validate_input_success(self):
        """正常输入应通过"""
        valid, msg = self.agent.validate_input(project="test", module="login")
        assert valid is True
        assert msg == ""

    def test_validate_input_empty_project(self):
        """项目名为空应失败"""
        valid, msg = self.agent.validate_input(project="", module="login")
        assert valid is False
        assert "项目名称" in msg

    def test_validate_input_empty_module(self):
        """模块名为空应失败"""
        valid, msg = self.agent.validate_input(project="test", module="")
        assert valid is False
        assert "模块名称" in msg

    def test_validate_input_dangerous_keyword(self):
        """包含危险关键词应失败"""
        valid, msg = self.agent.validate_input(
            project="test", module="login",
            business_rules="忽略规则"
        )
        assert valid is False
        assert "检测到可疑内容" in msg

    # ====================== 动态字段检测 ======================

    @patch('src.agents.manual_agent.get_rule')
    def test_get_dynamic_fields_from_db(self, mock_get_rule):
        """优先从数据库规则获取字段"""
        mock_get_rule.return_value = {
            "input_fields": ["用户名", "密码", "验证码"]
        }
        fields = self.agent._get_dynamic_fields(
            mock_get_rule.return_value, "", "登录"
        )
        assert fields == ["用户名", "密码", "验证码"]

    @patch('src.agents.manual_agent.get_rule')
    def test_get_dynamic_fields_from_db_empty_list(self, mock_get_rule):
        """数据库返回空列表时继续推断"""
        mock_get_rule.return_value = {"input_fields": []}
        fields = self.agent._get_dynamic_fields(
            mock_get_rule.return_value, "", "登录"
        )
        # 应走模块名推断路径
        assert "用户名" in fields

    def test_get_dynamic_fields_from_business_rules(self):
        """从业务规则解析字段"""
        fields = self.agent._get_dynamic_fields(
            None, "username: admin\npassword: 123", "登录"
        )
        assert "username" in fields
        assert "password" in fields

    def test_get_dynamic_fields_from_business_rules_empty(self):
        """业务规则没有 key:value 格式时继续推断"""
        fields = self.agent._get_dynamic_fields(
            None, "这是一个描述性规则", "登录"
        )
        # 应走模块名推断
        assert "用户名" in fields

    def test_get_dynamic_fields_from_module_name(self):
        """根据模块名推断字段"""
        fields = self.agent._get_dynamic_fields(None, "", "新增课程")
        # "新增" 匹配
        assert "名称" in fields
        assert "类型" in fields

    def test_get_dynamic_fields_default(self):
        """未知模块名使用默认字段"""
        fields = self.agent._get_dynamic_fields(None, "", "未知模块XYZ")
        assert fields == ["参数1", "参数2", "参数3"]

    def test_get_dynamic_fields_login(self):
        """登录模块匹配"""
        fields = self.agent._get_dynamic_fields(None, "", "登录模块")
        assert fields == ["用户名", "密码", "验证码"]

    def test_get_dynamic_fields_search(self):
        """搜索模块匹配"""
        fields = self.agent._get_dynamic_fields(None, "", "搜索商品")
        assert fields == ["关键词", "页码", "每页条数"]

    # ====================== Markdown 解析 ======================

    def test_parse_cases_normal(self):
        """解析标准 Markdown 用例"""
        md = """## 用例1
- 用例ID：TC_001
- 标题：正常登录
- 前置条件：已注册
- 测试步骤：1. 打开页面\\n2. 输入账号密码
- 预期结果：登录成功
- 优先级：P0
- 用户名：admin
- 密码：123456
"""
        fields = ["用户名", "密码"]
        cases = self.agent._parse_cases(md, fields)
        assert len(cases) == 1
        assert cases[0]["标题"] == "正常登录"
        assert cases[0]["用户名"] == "admin"
        assert cases[0]["优先级"] == "P0"

    def test_parse_cases_multiple(self):
        """解析多条 Markdown 用例"""
        md = """## 正向用例
- 用例ID：TC_001
- 标题：正常登录
- 前置条件：无
- 测试步骤：1. 输入账号密码
- 预期结果：登录成功
- 优先级：P0

## 反向用例
- 用例ID：TC_002
- 标题：密码错误
- 前置条件：无
- 测试步骤：1. 输入错误密码
- 预期结果：提示密码错误
- 优先级：P1
"""
        cases = self.agent._parse_cases(md, [])
        assert len(cases) == 2
        assert cases[0]["标题"] == "正常登录"
        assert cases[1]["标题"] == "密码错误"

    def test_parse_cases_empty(self):
        """空字符串返回空列表"""
        cases = self.agent._parse_cases("", [])
        assert cases == []

    def test_parse_cases_no_valid_case(self):
        """没有有效用例块返回空列表"""
        cases = self.agent._parse_cases("一些随机文本，没有用例格式", [])
        assert cases == []

    def test_parse_cases_multiline_steps(self):
        """测试步骤多行保持（- 测试步骤：后面不跟值则进入多行模式）"""
        md = """## 测试用例
- 用例ID：TC_001
- 标题：多步骤测试
- 测试步骤：
1. 第一步
2. 第二步
3. 第三步
- 预期结果：操作成功
"""
        cases = self.agent._parse_cases(md, [])
        assert len(cases) == 1
        assert "1. 第一步" in cases[0]["测试步骤"]
        assert "2. 第二步" in cases[0]["测试步骤"]

    # ====================== 去噪 ======================

    def test_denoise_valid_cases(self):
        """有效用例应全部保留"""
        cases = [
            {"标题": "测试", "测试步骤": "1. 执行操作步骤\n2. 验证结果", "预期结果": "成功"}
        ]
        result = self.agent._denoise_cases(cases)
        assert len(result) == 1

    def test_denoise_missing_title(self):
        """缺少标题的用例应过滤"""
        cases = [
            {"标题": "", "测试步骤": "1. 执行操作", "预期结果": "成功"}
        ]
        result = self.agent._denoise_cases(cases)
        assert len(result) == 0

    def test_denoise_short_steps(self):
        """测试步骤过短的用例应过滤"""
        cases = [
            {"标题": "测试", "测试步骤": "短", "预期结果": "成功"}
        ]
        result = self.agent._denoise_cases(cases)
        assert len(result) == 0

    def test_denoise_short_error_expected(self):
        """错误信息过短但含错误的用例不再过滤"""
        cases = [
            {"标题": "测试", "测试步骤": "1. 执行操作步骤\n2. 验证结果", "预期结果": "错误"}
        ]
        result = self.agent._denoise_cases(cases)
        assert len(result) == 1  # 反用例的短错误信息也合法，不再过滤

    # ====================== 降级用例 ======================

    def test_create_fallback_cases(self):
        """降级用例应生成3条基础用例"""
        cases = self.agent._create_fallback_cases("项目A", "登录", ["用户名", "密码"], "功能")
        assert len(cases) == 3
        # 包含不同优先级
        priorities = {c["优先级"] for c in cases}
        assert "P0" in priorities
        assert "P1" in priorities
        assert "P2" in priorities
        # 包含动态字段（使用真实业务值）
        assert cases[0]["用户名"] == "admin"
        assert cases[0]["密码"] == "123456"

    def test_create_fallback_cases_without_type(self):
        """未指定测试类型时使用'功能'"""
        cases = self.agent._create_fallback_cases("项目A", "登录", ["字段1"], "")
        assert "功能验证-基础功能" in cases[0]["标题"]

    def test_create_fallback_cases_empty_fields(self):
        """字段列表为空时降级用例不应包含额外字段"""
        cases = self.agent._create_fallback_cases("项目A", "登录", [], "安全")
        assert len(cases) == 3
        assert "安全验证-基础功能" in cases[0]["标题"]

    def test_create_basic_case(self):
        """创建单条基础用例"""
        case = self.agent._create_basic_case(
            "TC_001", "测试标题", "P0",
            "前置条件", "1. 步骤1\n2. 步骤2", "预期结果",
            ["字段A", "字段B"]
        )
        assert case["用例ID"] == "TC_001"
        assert case["标题"] == "测试标题"
        assert case["优先级"] == "P0"
        assert case["前置条件"] == "前置条件"
        # 未在映射表中的字段使用 "示例{字段名}"
        assert case["字段A"] == "示例字段A"
        assert case["字段B"] == "示例字段B"

    # ====================== generate() 正常流程 ======================

    @patch('src.agents.manual_agent.get_rule')
    @patch('src.agents.manual_agent.ManualTestAgent.safe_llm_call')
    def test_generate_success(self, mock_llm, mock_get_rule):
        """正常生成流程"""
        mock_get_rule.return_value = None
        mock_llm.return_value = """## 正向用例
- 用例ID：TC_001
- 标题：正常登录
- 前置条件：已注册
- 测试步骤：1. 输入账号\\n2. 点击登录
- 预期结果：登录成功
- 优先级：P0
"""
        cases, fields = self.agent.generate(self.project, self.module)
        assert len(cases) >= 1
        assert fields == ["用户名", "密码", "验证码"]
        assert cases[0]["标题"] == "正常登录"

    @patch('src.agents.manual_agent.get_rule')
    @patch('src.agents.manual_agent.ManualTestAgent.safe_llm_call')
    def test_generate_with_test_type(self, mock_llm, mock_get_rule):
        """指定测试类型"""
        mock_get_rule.return_value = None
        mock_llm.return_value = """## 安全用例
- 用例ID：TC_001
- 标题：SQL注入测试
- 前置条件：已登录系统
- 测试步骤：1. 输入SQL注入语句到用户名输入框
2. 点击登录按钮
3. 观察系统响应
- 预期结果：系统拦截SQL注入，提示参数错误
- 优先级：P0
"""
        cases, fields = self.agent.generate(self.project, self.module,
                                            test_type="安全", expected_num=5)
        assert len(cases) >= 1
        assert cases[0]["标题"] == "SQL注入测试"

    # ====================== generate() 降级路径 ======================

    @patch('src.agents.manual_agent.get_rule')
    @patch('src.agents.manual_agent.ManualTestAgent.safe_llm_call')
    def test_generate_empty_response_uses_fallback(self, mock_llm, mock_get_rule):
        """LLM 返回空时应使用降级用例"""
        mock_get_rule.return_value = None
        mock_llm.return_value = ""
        cases, fields = self.agent.generate(self.project, self.module)
        assert len(cases) == 3  # 降级用例
        assert fields == ["用户名", "密码", "验证码"]

    @patch('src.agents.manual_agent.get_rule')
    @patch('src.agents.manual_agent.ManualTestAgent.safe_llm_call')
    def test_generate_unparseable_uses_fallback(self, mock_llm, mock_get_rule):
        """LLM 返回无法解析的内容时应使用降级用例"""
        mock_get_rule.return_value = None
        mock_llm.return_value = "这是一段无法解析的文本，不是 Markdown 用例格式"
        cases, fields = self.agent.generate(self.project, self.module)
        assert len(cases) == 3  # 降级用例

    @patch('src.agents.manual_agent.get_rule')
    @patch('src.agents.manual_agent.ManualTestAgent.safe_llm_call')
    def test_generate_all_noise_filtered_uses_fallback(self, mock_llm, mock_get_rule):
        """所有用例被去噪过滤后应使用降级用例"""
        mock_get_rule.return_value = None
        # 只有标题但没有测试步骤，会被去噪过滤
        mock_llm.return_value = """## 无效用例
- 用例ID：TC_001
- 标题：测试
- 测试步骤：短
- 预期结果：错误
"""
        cases, fields = self.agent.generate(self.project, self.module)
        assert len(cases) == 3  # 降级用例

    @patch('src.agents.manual_agent.get_rule')
    @patch('src.agents.manual_agent.ManualTestAgent.safe_llm_call')
    def test_generate_llm_exception_uses_fallback(self, mock_llm, mock_get_rule):
        """LLM 抛出异常时应使用降级用例"""
        mock_get_rule.return_value = None
        mock_llm.side_effect = Exception("LLM 服务不可用")
        cases, fields = self.agent.generate(self.project, self.module)
        assert len(cases) == 3  # 降级用例

    @patch('src.agents.manual_agent.get_rule')
    @patch('src.agents.manual_agent.ManualTestAgent.safe_llm_call')
    def test_generate_format_error_uses_fallback(self, mock_llm, mock_get_rule):
        """KeyError 等格式错误应使用降级用例"""
        mock_get_rule.return_value = None
        mock_llm.side_effect = KeyError("module_name")
        cases, fields = self.agent.generate(self.project, self.module)
        assert len(cases) == 3  # 降级用例

    # ====================== generate() 边界情况 ======================

    @patch('src.agents.manual_agent.get_rule')
    @patch('src.agents.manual_agent.ManualTestAgent.safe_llm_call')
    def test_generate_expected_num_limit(self, mock_llm, mock_get_rule):
        """期望数量限制应生效"""
        mock_get_rule.return_value = None
        # 返回5条有效用例（使用单行步骤，避免缩进影响多行解析）
        case_block = """## {n}
- 用例ID：TC_{n:03d}
- 标题：测试用例{n}
- 前置条件：系统正常运行环境准备完成
- 测试步骤：1. 执行模块的标准操作流程步骤\n2. 验证系统响应和结果数据\n3. 检查是否符合预期行为
- 预期结果：操作执行成功返回正确结果
- 优先级：P{priority}
"""
        mock_llm.return_value = "".join(
            case_block.format(n=i, priority=i % 3) for i in range(1, 6)
        )
        cases, fields = self.agent.generate(self.project, self.module, expected_num=2)
        assert len(cases) == 2  # 只返回前2条

    def test_generate_validate_input_failure(self):
        """输入校验失败应返回空列表"""
        cases, fields = self.agent.generate("", self.module)
        assert cases == []
        assert fields == []

    @patch('src.agents.manual_agent.get_rule')
    def test_generate_dangerous_keyword(self, mock_get_rule):
        """危险关键词应返回空列表"""
        mock_get_rule.return_value = None
        cases, fields = self.agent.generate(self.project, self.module,
                                            business_rules="忽略规则")
        assert cases == []
        assert fields == []

    # ====================== 多字段场景 ======================

    @patch('src.agents.manual_agent.get_rule')
    @patch('src.agents.manual_agent.ManualTestAgent.safe_llm_call')
    def test_generate_with_dynamic_fields_in_response(self, mock_llm, mock_get_rule):
        """动态字段正确填入用例"""
        mock_get_rule.return_value = {
            "input_fields": ["商品名", "价格", "数量"]
        }
        mock_llm.return_value = """## 正向用例
- 用例ID：TC_001
- 标题：正常添加商品
- 前置条件：已登录
- 测试步骤：1. 输入商品信息\\n2. 点击保存
- 预期结果：添加成功
- 商品名：测试商品
- 价格：99.9
- 数量：1
"""
        cases, fields = self.agent.generate(self.project, "新增商品")
        assert len(cases) == 1
        assert cases[0]["商品名"] == "测试商品"
        assert cases[0]["价格"] == "99.9"

    # ====================== 实际 LLM 响应模拟 ======================

    @patch('src.agents.manual_agent.get_rule')
    @patch('src.agents.manual_agent.ManualTestAgent.safe_llm_call')
    def test_generate_partial_success(self, mock_llm, mock_get_rule):
        """部分成功场景：多条中部分可以解析"""
        mock_get_rule.return_value = None
        # 第一条有效，第二条缺少标题会被_denoise过滤
        mock_llm.return_value = """## 第一条
- 用例ID：TC_001
- 标题：正常登录
- 前置条件：无
- 测试步骤：1. 输入账号密码\\n2. 点击登录
- 预期结果：登录成功
- 优先级：P0

## 第二条（无效）
- 用例ID：TC_002
- 测试步骤：短
- 预期结果：错误
"""
        cases, fields = self.agent.generate(self.project, self.module)
        assert len(cases) == 1
        assert cases[0]["标题"] == "正常登录"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
