"""知识库加载器 - 从文件系统加载知识库，支持按模式分类"""
import os
import re
import logging
from typing import Dict, List, Tuple, Optional

from src.config.settings import KNOWLEDGE_BASE_DIR

logger = logging.getLogger("main.knowledge_loader")


class KnowledgeLoader:
    """知识库加载器 - 支持 testpoint/api/manual/ai 四种模式"""

    _instance = None
    _cache: Dict[str, Dict[str, str]] = {}  # {mode: {key: content}}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_all()
        return cls._instance

    def _load_all(self):
        """加载所有知识库文件到缓存"""
        if not os.path.exists(KNOWLEDGE_BASE_DIR):
            os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)
            self._create_default_directories()
            return

        # 遍历所有子目录
        for mode in os.listdir(KNOWLEDGE_BASE_DIR):
            mode_dir = os.path.join(KNOWLEDGE_BASE_DIR, mode)
            if not os.path.isdir(mode_dir):
                continue

            self._cache[mode] = {}
            file_count = 0

            for filename in os.listdir(mode_dir):
                if filename.endswith('.md') and filename != 'README.md':
                    filepath = os.path.join(mode_dir, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        key = filename[:-3]  # 去掉 .md 后缀
                        self._cache[mode][key] = content
                        file_count += 1

            if file_count > 0:
                logger.info(f"[OK] 知识库加载成功 [{mode}]: {file_count} 个文件")

    def _create_default_directories(self):
        """创建默认的目录结构"""
        modes = ["testpoint", "api", "manual", "ai"]
        for mode in modes:
            mode_dir = os.path.join(KNOWLEDGE_BASE_DIR, mode)
            os.makedirs(mode_dir, exist_ok=True)

            # 创建 README.md 说明文件
            readme_path = os.path.join(mode_dir, "README.md")
            if not os.path.exists(readme_path):
                with open(readme_path, 'w', encoding='utf-8') as f:
                    f.write(f"# {mode.upper()} 知识库\n\n")
                    f.write(f"将 {mode} 相关的知识库文件放在此目录下。\n\n")
                    f.write("## 文件命名规则\n")
                    f.write("- 格式：`{项目名}_{模块名}.md`\n")
                    f.write("- 示例：`客达天下_登录.md`\n\n")
                    f.write("## 文件内容格式\n")
                    f.write("```markdown\n")
                    f.write("# 模块名称\n\n")
                    f.write("## 接口信息\n")
                    f.write("- URL: ...\n")
                    f.write("- 方法: ...\n\n")
                    f.write("## 参数说明\n")
                    f.write("| 参数名 | 类型 | 必填 | 说明 |\n")
                    f.write("|--------|------|------|------|\n\n")
                    f.write("## 业务规则\n")
                    f.write("1. ...\n")
                    f.write("```\n")

        logger.info(f"[OK] 已创建知识库目录结构: {KNOWLEDGE_BASE_DIR}")

    def get_example(self, mode: str, key: str) -> str:
        """
        根据模式和 key 获取知识库内容

        参数:
        - mode: 模式 (testpoint/api/manual/ai)
        - key: 知识库文件 key（不含 .md 后缀）

        返回:
        - 知识库内容，不存在则返回空字符串
        """
        return self._cache.get(mode, {}).get(key, "")

    def match_by_keywords(self, mode: str, project_name: str, module_name: str) -> str:
        """
        根据模式、项目名称和模块名称匹配知识库

        参数:
        - mode: 模式 (testpoint/api/manual/ai)
        - project_name: 项目名称
        - module_name: 模块名称

        返回:
        - 匹配到的知识库内容
        """
        all_text = f"{project_name} {module_name}".lower()

        # 根据模式选择匹配规则
        if mode == "testpoint":
            rules = self._get_testpoint_rules()
        elif mode == "api":
            rules = self._get_api_rules()
        elif mode == "manual":
            rules = self._get_manual_rules()
        elif mode == "ai":
            rules = self._get_ai_rules()
        else:
            rules = []

        for keywords, key in rules:
            for kw in keywords:
                if kw in all_text:
                    example = self.get_example(mode, key)
                    if example:
                        return example

        return "暂无完全匹配的示例，请基于通用测试设计原则生成。"

    def _get_testpoint_rules(self) -> List[Tuple[List[str], str]]:
        """测试点分析的关键词匹配规则"""
        return [
            # 具体业务示例
            (["酒店", "搜索", "旅游", "携程", "住宿"], "携程_酒店搜索"),
            (["购物车", "电商", "抖音", "商品", "价格"], "抖音_购物车"),
            (["智能体", "AI", "学习助手", "Python", "考试", "阶段"], "Python学习助手"),

            # 通用规则
            (["订单", "取消", "退款", "售后", "收货", "评价", "发票", "外卖", "到店", "优选", "电商", "交易"], "电商_订单通用规则"),
            (["金融", "支付", "银行", "转账", "交易", "结算", "退款"], "金融_支付通用规则"),
            (["社交", "聊天", "IM", "消息", "好友", "群", "朋友圈"], "社交_IM通用规则"),
            (["直播", "音视频", "推流", "拉流", "弹幕", "礼物", "主播"], "音视频_直播通用规则"),
            (["企业服务", "CRM", "审批", "导入导出", "权限", "角色", "员工"], "企业服务_CRM通用规则"),
            (["医疗", "健康", "问诊", "挂号", "病历", "药店", "体检"], "医疗健康通用规则"),
            (["物流", "配送", "快递", "运单", "司机", "仓储"], "物流配送通用规则"),

            # 产品/端类型匹配
            (["美团", "外卖", "闪购", "到店", "优选", "小象", "酒店", "旅行"], "美团_业务框架"),
            (["抖音", "直播", "短视频", "电商购物"], "抖音_业务框架"),
            (["企业微信", "企微", "企业微信管理端"], "企业微信_业务框架"),
            (["微信小程序", "小程序", "微信小程式"], "微信小程序_通用框架"),
            (["支付宝小程序", "支付宝小程式"], "支付宝小程序_通用框架"),
            (["管理后台", "后台系统", "web管理", "admin", "后台管理"], "Web_管理后台通用框架"),
        ]

    def _get_api_rules(self) -> List[Tuple[List[str], str]]:
        """接口测试的关键词匹配规则"""
        return [
            # 客达天下项目
            (["客达天下", "登录"], "客达天下_登录"),
            (["客达天下", "验证码", "captcha"], "客达天下_生成验证码"),
            (["客达天下", "课程", "新增", "添加"], "客达天下_新增课程"),
            (["客达天下", "课程列表", "查询"], "客达天下_查询课程列表"),
            (["客达天下", "课程详情", "查询课程"], "客达天下_查询课程"),
            (["客达天下", "修改课程", "更新课程"], "客达天下_修改课程"),
            (["客达天下", "删除课程"], "客达天下_删除课程"),
            (["客达天下", "合同上传", "upload"], "客达天下_合同上传"),
            (["客达天下", "新增合同", "添加合同"], "客达天下_新增合同"),
            (["客达天下", "合同列表", "查询合同"], "客达天下_查询合同列表"),
            (["客达天下", "删除合同"], "客达天下_删除合同"),

            # 电商平台
            (["电商", "登录"], "电商_登录"),
            (["电商", "购物车"], "电商_购物车"),
            (["电商", "下单", "订单"], "电商_下单"),

            # 旅游平台
            (["旅游", "酒店", "搜索"], "旅游_酒店搜索"),
            (["旅游", "机票", "搜索"], "旅游_机票搜索"),

            # 社交平台
            (["社交", "发布", "动态"], "社交_发布动态"),
            (["社交", "评论"], "社交_评论"),

            # 金融系统
            (["金融", "转账", "银行"], "金融_转账"),
            (["金融", "余额", "查询"], "金融_余额查询"),
        ]

    def _get_manual_rules(self) -> List[Tuple[List[str], str]]:
        """手工测试的关键词匹配规则"""
        return [
            (["登录"], "登录功能测试用例"),
            (["购物车"], "购物车功能测试用例"),
            (["订单"], "订单流程测试用例"),
            (["注册"], "注册功能测试用例"),
            (["搜索"], "搜索功能测试用例"),
        ]

    def _get_ai_rules(self) -> List[Tuple[List[str], str]]:
        """AI系统测试的关键词匹配规则"""
        return [
            (["Python", "学习", "助手", "智能体"], "Python学习助手"),
            (["客服", "问答", "智能客服"], "智能客服_问答模块"),
            (["代码", "生成", "代码助手"], "代码助手_代码生成"),
            (["审核", "内容", "敏感词"], "内容审核_文本审核"),
        ]

    def get_all_examples(self, mode: str = None) -> str:
        """
        获取所有知识库内容

        参数:
        - mode: 指定模式，为 None 时返回所有模式的内容

        返回:
        - 所有知识库内容拼接的字符串
        """
        if mode:
            return "\n\n".join(self._cache.get(mode, {}).values())
        else:
            all_content = []
            for mode_content in self._cache.values():
                all_content.extend(mode_content.values())
            return "\n\n".join(all_content)

    def list_modes(self) -> List[str]:
        """列出所有已加载的模式"""
        return list(self._cache.keys())

    def list_keys(self, mode: str) -> List[str]:
        """列出指定模式下的所有知识库 key"""
        return list(self._cache.get(mode, {}).keys())

    def reload(self):
        """重新加载所有知识库"""
        self._cache.clear()
        self._load_all()


# 创建全局实例
knowledge_loader = KnowledgeLoader()


# ======================
# 兼容旧接口（保持原有调用方式）
# ======================

def get_examples_by_keywords(project_name: str, module_name: str, mode: str = "testpoint") -> str:
    """
    根据项目名称和模块名称，匹配最相关的知识库示例

    参数:
    - project_name: 项目名称
    - module_name: 模块名称
    - mode: 模式 (testpoint/api/manual/ai)，默认 testpoint

    返回:
    - 知识库内容
    """
    return knowledge_loader.match_by_keywords(mode, project_name, module_name)


def get_example_by_mode_and_key(mode: str, key: str) -> str:
    """
    直接根据模式和 key 获取知识库内容

    参数:
    - mode: 模式 (testpoint/api/manual/ai)
    - key: 知识库文件 key

    返回:
    - 知识库内容
    """
    return knowledge_loader.get_example(mode, key)


# ======================
# 测试代码
# ======================
if __name__ == "__main__":
    print("=" * 60)
    print("知识库加载器测试")
    print("=" * 60)

    print(f"\n📁 知识库目录: {KNOWLEDGE_BASE_DIR}")
    print(f"📊 已加载模式: {knowledge_loader.list_modes()}")

    for mode in knowledge_loader.list_modes():
        keys = knowledge_loader.list_keys(mode)
        print(f"\n📂 [{mode}] 共 {len(keys)} 个知识库:")
        for key in keys[:5]:  # 只显示前5个
            print(f"   - {key}")
        if len(keys) > 5:
            print(f"   ... 还有 {len(keys) - 5} 个")

    print("\n" + "=" * 60)
    print("关键词匹配测试（testpoint 模式）:")
    print("=" * 60)

    test_cases = [
        ("携程", "酒店搜索", "testpoint"),
        ("抖音", "购物车", "testpoint"),
        ("Python", "学习助手", "testpoint"),
        ("客达天下", "登录", "api"),
        ("电商", "购物车", "api"),
        ("电商", "登录", "manual"),
    ]

    for project, module, mode in test_cases:
        example = get_examples_by_keywords(project, module, mode)
        status = "✅ 匹配到" if len(example) > 100 and "暂无完全匹配" not in example else "❌ 未匹配"
        first_line = example.split('\n')[0] if example else ""
        print(f"  [{mode}] {project}-{module}: {status} - {first_line[:50]}")