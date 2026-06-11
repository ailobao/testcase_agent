# src/strategies/fixed_pattern_strategy.py
"""固定模式用例生成策略 - Token异常、参数缺失、参数为空等"""
from typing import List, Dict, Optional, Any
import json


class FixedPatternStrategy:
    """固定模式用例生成器

    负责生成：
    - Token 异常用例（过期、错误、为空、缺失）
    - 参数缺失用例
    - 参数为空用例
    """

    # 默认请求头模板
    DEFAULT_HEADERS = {
        "Content-Type": "application/json",
        "Authorization": "Bearer {{token}}"
    }

    # 常见业务字段 → 合理性保底值
    BUSINESS_DEFAULTS = {
        "username": "admin", "password": "123456", "code": "8888",
        "name": "测试名称001", "title": "测试标题001",
        "phone": "13800138000", "mobile": "13800138000", "tel": "010-88886666",
        "email": "test@example.com", "mail": "test@example.com",
        "price": 99, "amount": 100, "count": 1, "num": 1, "quantity": 1,
        "age": 18, "page": 1, "size": 10, "limit": 10, "offset": 0,
        "id": 1, "status": 1, "type": 1, "sort": 0,
        "address": "北京市朝阳区", "remark": "测试备注", "desc": "测试描述",
        "info": "测试信息", "content": "测试内容",
    }

    def __init__(self):
        self.code_count = 0

    def generate_token_error_cases(self, url_path: str, body_data: dict, method: str,
                                   start_case_id: int, is_login_module: bool = False) -> List[Dict]:
        """
        生成 Token 异常用例

        参数:
            url_path: 接口路径
            body_data: 请求体模板
            method: 请求方法
            start_case_id: 起始用例编号
            is_login_module: 是否为登录模块（登录模块不需要 Token）

        返回:
            Token 异常用例列表
        """
        if is_login_module:
            return []

        token_templates = [
            ("Token过期", "Bearer expired_token_xxx"),
            ("Token错误", "Bearer wrong_token_12345"),
            ("Token为空", ""),
            ("缺失Token", None),
        ]

        cases = []
        case_id = start_case_id

        for title, token_value in token_templates:
            cases.append(self._create_token_error_case(
                title, token_value, url_path, body_data, method, case_id
            ))
            case_id += 1
            self.code_count += 1

        return cases

    def generate_missing_param_cases(self, required_fields: List[str], url_path: str,
                                     body_data: dict, method: str, start_case_id: int) -> List[Dict]:
        """
        生成参数缺失用例

        参数:
            required_fields: 必填参数列表
            url_path: 接口路径
            body_data: 请求体模板
            method: 请求方法
            start_case_id: 起始用例编号

        返回:
            参数缺失用例列表
        """
        cases = []
        case_id = start_case_id

        for field in required_fields:
            test_body = body_data.copy()
            test_body.pop(field, None)
            test_body = self._enrich_body_values(test_body)

            cases.append(self._create_missing_param_case(
                field, url_path, test_body, method, case_id
            ))
            case_id += 1
            self.code_count += 1

        return cases

    def generate_empty_param_cases(self, required_fields: List[str], url_path: str,
                                   body_data: dict, method: str, start_case_id: int) -> List[Dict]:
        """
        生成参数为空用例

        参数:
            required_fields: 必填参数列表
            url_path: 接口路径
            body_data: 请求体模板
            method: 请求方法
            start_case_id: 起始用例编号

        返回:
            参数为空用例列表
        """
        cases = []
        case_id = start_case_id

        for field in required_fields:
            test_body = body_data.copy()
            original_value = test_body.get(field)

            if isinstance(original_value, str):
                test_body[field] = ""
            elif isinstance(original_value, int):
                test_body[field] = 0
            else:
                test_body[field] = ""

            test_body = self._enrich_body_values(test_body, skip_field=field)

            cases.append(self._create_empty_param_case(
                field, url_path, test_body, method, case_id
            ))
            case_id += 1
            self.code_count += 1

        return cases

    def generate_all_fixed_cases(self, required_fields: List[str], url_path: str,
                                 body_data: dict, method: str, start_case_id: int,
                                 is_login_module: bool = False) -> List[Dict]:
        """
        生成所有固定模式用例

        参数:
            required_fields: 必填参数列表
            url_path: 接口路径
            body_data: 请求体模板
            method: 请求方法
            start_case_id: 起始用例编号
            is_login_module: 是否为登录模块

        返回:
            所有固定模式用例列表
        """
        all_cases = []
        current_id = start_case_id

        # 1. Token 异常用例
        token_cases = self.generate_token_error_cases(
            url_path, body_data, method, current_id, is_login_module
        )
        all_cases.extend(token_cases)
        current_id += len(token_cases)

        # 2. 参数缺失用例
        missing_cases = self.generate_missing_param_cases(
            required_fields, url_path, body_data, method, current_id
        )
        all_cases.extend(missing_cases)
        current_id += len(missing_cases)

        # 3. 参数为空用例
        empty_cases = self.generate_empty_param_cases(
            required_fields, url_path, body_data, method, current_id
        )
        all_cases.extend(empty_cases)

        return all_cases

    def reset_count(self):
        """重置计数"""
        self.code_count = 0

    def get_count(self) -> int:
        """获取生成的用例数量"""
        return self.code_count

    # ============== 私有方法 ==============

    def _create_token_error_case(self, title: str, token_value: Optional[str],
                                 url_path: str, body_data: dict, method: str, case_id: int) -> Dict:
        """创建 Token 异常用例"""
        headers = self.DEFAULT_HEADERS.copy()

        if token_value is None:
            headers.pop("Authorization", None)
        elif token_value == "":
            headers["Authorization"] = ""
        else:
            headers["Authorization"] = token_value

        body = self._enrich_body_values(body_data.copy() if body_data else {})

        return {
            "case_id": f"TC_{case_id:03d}",
            "title": title,
            "method": method,
            "url": url_path,
            "headers": headers,
            "body": body,
            "assert": self._normalize_assert({"status_code": 401, "body.msg": "认证失败"}, method),
            "extract": {},
            "priority": "P2"
        }

    def _create_missing_param_case(self, field: str, url_path: str,
                                   body_data: dict, method: str, case_id: int) -> Dict:
        """创建参数缺失用例"""
        return {
            "case_id": f"TC_{case_id:03d}",
            "title": f"缺失参数 {field}",
            "method": method,
            "url": url_path,
            "headers": self.DEFAULT_HEADERS.copy(),
            "body": body_data,
            "assert": self._normalize_assert({"status_code": 400, "body.msg": f"{field}不能为空"}, method),
            "extract": {},
            "priority": "P2"
        }

    def _create_empty_param_case(self, field: str, url_path: str,
                                 body_data: dict, method: str, case_id: int) -> Dict:
        """创建参数为空用例"""
        return {
            "case_id": f"TC_{case_id:03d}",
            "title": f"参数 {field} 为空",
            "method": method,
            "url": url_path,
            "headers": self.DEFAULT_HEADERS.copy(),
            "body": body_data,
            "assert": self._normalize_assert({"status_code": 400, "body.msg": f"{field}不能为空"}, method),
            "extract": {},
            "priority": "P2"
        }

    def _normalize_assert(self, assert_dict: dict, method: str) -> dict:
        """规范化断言"""
        result = assert_dict.copy()

        if "status_code" not in result:
            result["status_code"] = 200 if method == "GET" else 200

        if method in ["POST", "PUT", "DELETE"]:
            if "body.code" not in result:
                status_code = result.get("status_code", 200)
                result["body.code"] = status_code
            if "body.msg" not in result:
                status_code = result.get("status_code", 200)
                msg_map = {200: "操作成功", 401: "认证失败", 400: "参数错误", 404: "资源不存在"}
                result["body.msg"] = msg_map.get(status_code, "操作失败")

        return result

    def _enrich_body_values(self, body: dict, skip_field: str = None) -> dict:
        """
        确保 body 中的参数值有业务含义（非空、非占位符）。
        只补充空/None/占位符的字段，不覆盖已有的有效值。
        """
        enriched = body.copy() if body else {}
        PLACEHOLDER_PATTERNS = ("test", "xxx", "placeholder", "示例")

        for key, value in list(enriched.items()):
            if skip_field and key == skip_field:
                continue  # 跳过错检测的目标字段（如空值/缺失字段）
            # 如果值为空/None/占位符，用业务默认值替换
            if value is None or (isinstance(value, str) and (not value.strip() or value.lower() in PLACEHOLDER_PATTERNS)):
                enriched[key] = self.BUSINESS_DEFAULTS.get(key, f"测试{key}001")
            elif isinstance(value, str) and len(value) < 2:
                enriched[key] = self.BUSINESS_DEFAULTS.get(key, f"测试{key}001")

        return enriched