# src/utils/common_tools.py
"""公共工具函数 - 所有 Agent 共享"""
import re
import json
import logging
from typing import List, Dict, Any, Optional, Callable

logger = logging.getLogger("main.common_tools")


def deduplicate_cases(cases: List[Dict], key_fields: List[str] = None) -> List[Dict]:
    """
    通用去重 - 基于标题和 body 字段

    参数:
    - cases: 用例列表
    - key_fields: 用于去重的 body 字段。
                  None（默认）→ 使用 body 中所有字段（自动适配不同接口）
                  []          → 只用标题去重
                  ["field1"]  → 标题 + 指定字段
    """
    if not cases:
        return cases

    seen = set()
    unique = []

    for idx, case in enumerate(cases):
        # 支持多种标题字段名
        title = (case.get("title", "") or
                 case.get("测试标题", "") or
                 case.get("标题", "") or "")

        body = case.get("body", {})
        # 安全处理：AI 生成的 body 可能不是 dict（如字符串），兜底为空 dict
        if not isinstance(body, dict):
            body = {}

        key_parts = [title]

        # 默认使用 body 中所有字段作为区分（自动适配各接口的不同字段）
        if key_fields is None:
            # 取 body 中所有字段的值（按 key 排序保证顺序一致）
            for k in sorted(body.keys()):
                key_parts.append(f"{k}:{body[k]}")
        else:
            # 指定字段
            for field in key_fields:
                if field in body:
                    key_parts.append(str(body[field]))

        # ===== 兜底：body 和 title 都为空时，保留所有 case =====
        # 避免 AI 解析异常导致大量用例因 body={} 被误去重
        if not body and not title:
            unique.append(case)
            continue

        key = "|".join(key_parts)
        if key not in seen:
            seen.add(key)
            unique.append(case)

    return unique


def clean_name(name: str) -> str:
    """清理文件名中的非法字符"""
    if not name:
        return "unknown"
    return re.sub(r'[\\/*?:"<>|]', "", name)[:50]


def ensure_dict_field(value: Any, default: Optional[dict] = None) -> dict:
    """确保字段是字典类型"""
    if value is None:
        return default or {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value) if value else {}
            return parsed if isinstance(parsed, dict) else (default or {})
        except:
            return default or {}
    return default or {}


def get_max_case_id(cases: List[Dict], prefix: str = "TC_") -> int:
    """获取用例列表中的最大编号"""
    max_id = 0
    for case in cases:
        case_id = case.get("case_id", "")
        match = re.search(rf'{prefix}(\d+)', case_id)
        if match:
            num = int(match.group(1))
            if num > max_id:
                max_id = num
    return max_id


def fix_case_id(cases: List[Dict], start_id: int = 1, prefix: str = "TC_") -> List[Dict]:
    """修复用例编号，从指定编号开始连续递增"""
    fixed_cases = []
    for i, case in enumerate(cases):
        case["case_id"] = f"{prefix}{start_id + i:03d}"
        fixed_cases.append(case)
    return fixed_cases


def renumber_cases(cases: List[Dict], prefix: str = "TC_", start: int = 1) -> List[Dict]:
    """重新编号所有用例"""
    for i, case in enumerate(cases, start):
        case["case_id"] = f"{prefix}{i:03d}"
    return cases


def normalize_assert(assert_dict: dict, method: str) -> dict:
    """根据请求方法规范化断言"""
    if not assert_dict:
        if method == "GET":
            return {"status_code": 200}
        else:
            return {"status_code": 200, "body.code": 200, "body.msg": "操作成功"}

    result = assert_dict.copy()

    if "status_code" not in result:
        result["status_code"] = 200

    if method in ["POST", "PUT", "DELETE"]:
        if "body.code" not in result:
            status_code = result.get("status_code", 200)
            if status_code == 200:
                result["body.code"] = 200
            elif status_code == 401:
                result["body.code"] = 401
            elif status_code == 404:
                result["body.code"] = 404
            elif status_code == 400:
                result["body.code"] = 400
            else:
                result["body.code"] = 500
        if "body.msg" not in result:
            status_code = result.get("status_code", 200)
            if status_code == 200:
                result["body.msg"] = "操作成功"
            elif status_code == 401:
                result["body.msg"] = "认证失败"
            elif status_code == 404:
                result["body.msg"] = "资源不存在"
            elif status_code == 400:
                result["body.msg"] = "参数错误"
            else:
                result["body.msg"] = "操作失败"

    return result


def get_business_scenarios(module_name: str, is_login_module: bool) -> str:
    """根据模块类型获取业务异常场景"""
    if is_login_module:
        return "- 用户名不存在\n- 密码错误\n- 验证码错误\n- 账号被锁定"
    elif "新增" in module_name or "创建" in module_name or "add" in module_name.lower():
        return "- 重复创建（相同唯一标识）\n- 字段值超长\n- 权限不足（无创建权限）"
    elif "删除" in module_name or "delete" in module_name.lower():
        return "- 删除不存在的记录\n- 删除已被删除的记录\n- 权限不足（无删除权限）"
    elif "修改" in module_name or "更新" in module_name or "update" in module_name.lower():
        return "- 修改不存在的记录\n- 修改为重复的唯一标识\n- 权限不足（无修改权限）"
    else:
        return "- 查询不存在的资源\n- 权限不足（无访问权限）"


def extract_user_params(ai_cases: List[Dict], business_rules: str, default_body: dict) -> Optional[Dict]:
    """提取用户参数"""
    for case in ai_cases:
        if "正向" in case.get("title", "") and case.get("priority") == "P0":
            body = case.get("body", {})
            if isinstance(body, dict):
                return body.copy()
            # body 不是 dict（如字符串），跳过此用例继续找

    if business_rules:
        user_params = {}
        for line in business_rules.split('\n'):
            match = re.match(r'(\w+)\s*[:=]\s*(\S+)', line.strip())
            if match:
                user_params[match.group(1)] = match.group(2)
        if user_params:
            return user_params

    return None


def safe_call(func: Callable, error_msg: str = "", default_return: Any = None, 
              retry_count: int = 3, retry_delay: float = 1.0) -> Any:
    """
    安全执行函数，带重试机制

    参数:
    - func: 要执行的函数（无参数）
    - error_msg: 错误提示信息
    - default_return: 失败时的默认返回值
    - retry_count: 重试次数
    - retry_delay: 重试延迟（秒）

    返回:
    - 函数返回值，或失败时的 default_return
    """
    import time
    
    for attempt in range(retry_count):
        try:
            return func()
        except Exception as e:
            if attempt == retry_count - 1:
                print(f"{error_msg}，重试{retry_count}次后仍失败: {e}")
                logger.warning(f"{error_msg}，重试{retry_count}次后仍失败: {e}")
                return default_return
            time.sleep(retry_delay)
            continue
    return default_return