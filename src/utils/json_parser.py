# src/utils/json_parser.py
"""统一的 JSON 解析器 - 合并所有修复策略"""
import re
import json
import ast
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("main.json_parser")


def universal_json_parse(content: str, default_return: Optional[List[Dict]] = None) -> List[Dict]:
    """万能 JSON 解析器"""
    if default_return is None:
        default_return = []

    if not content or not isinstance(content, str):
        return default_return

    original = content.strip()

    # 1. 去除 markdown 代码块标记
    cleaned = re.sub(r'```json\s*', '', original)
    cleaned = re.sub(r'```\s*$', '', cleaned)
    cleaned = cleaned.strip()

    # 2. 直接解析 JSON
    try:
        data = json.loads(cleaned)
        result = _extract_dicts(data)
        if result:  # 如果提取到了字典，直接返回
            return result
    except json.JSONDecodeError:
        logger.debug("strategy 2 failed (direct json.loads), trying next")

    # 3. 压缩为单行
    single_line = re.sub(r'\s+', ' ', cleaned)
    try:
        data = json.loads(single_line)
        result = _extract_dicts(data)
        if result:
            return result
    except Exception:
        logger.debug("strategy 3 failed (single-line json.loads), trying next")

    # 4. 移除注释和尾随逗号
    no_comments = re.sub(r'//.*?$', '', cleaned, flags=re.MULTILINE)
    no_comments = re.sub(r'/\*.*?\*/', '', no_comments, flags=re.DOTALL)
    no_trailing_comma = re.sub(r',\s*}', '}', no_comments)
    no_trailing_comma = re.sub(r',\s*]', ']', no_trailing_comma)

    try:
        data = json.loads(no_trailing_comma)
        result = _extract_dicts(data)
        if result:
            return result
    except Exception:
        logger.debug("strategy 4 failed (strip comments/trailing commas), trying next")

    # 5. Python 字面量
    try:
        py_literal = no_trailing_comma.replace("'", '"')
        py_literal = py_literal.replace('True', 'true').replace('False', 'false').replace('None', 'null')
        data = json.loads(py_literal)
        result = _extract_dicts(data)
        if result:
            return result
    except Exception:
        logger.debug("strategy 5 failed (Python literal conversion), trying next")

    # 6. ast.literal_eval
    try:
        ast_compatible = no_trailing_comma.replace('true', 'True').replace('false', 'False').replace('null', 'None')
        obj = ast.literal_eval(ast_compatible)
        result = _extract_dicts(obj)
        if result:
            return result
    except Exception:
        logger.debug("strategy 6 failed (ast.literal_eval), trying next")

    # 7. 提取平衡的 JSON
    balanced = _extract_balanced_json(cleaned)
    if balanced:
        try:
            data = json.loads(balanced)
            result = _extract_dicts(data)
            if result:
                return result
        except Exception:
            logger.debug("strategy 7 failed (balanced JSON extraction), trying next")

    # 8. 修复缺少逗号
    fixed_commas = re.sub(r'\}\s*\{', '},{', cleaned)
    try:
        data = json.loads(fixed_commas)
        result = _extract_dicts(data)
        if result:
            return result
    except Exception:
        logger.debug("strategy 8 failed (fixed missing commas), trying next")

    # 9. 逐个对象解析
    objects = re.findall(r'(\{[^{}]*\}|\[[^\[\]]*\])', cleaned)
    results = []
    for obj_str in objects:
        try:
            parsed = json.loads(obj_str)
            results.append(parsed)
        except Exception:
            continue
    if results:
        result = _extract_dicts(results)
        if result:
            return result

    # 10. 截断恢复：尝试关闭未闭合的 JSON，抢救已完整的对象
    salvaged = _salvage_truncated_json(cleaned)
    if salvaged:
        try:
            data = json.loads(salvaged)
            result = _extract_dicts(data)
            if result:
                return result
        except Exception:
            logger.debug("strategy 10 failed (truncated JSON salvage), trying next")

    # 11. 逐个提取独立对象（针对截断响应：跳过最后一个不完整对象）
    #     匹配从 { 到 } 的完整对象，即使其中有嵌套
    brace_objects = _extract_complete_brace_objects(cleaned)
    if brace_objects:
        results = []
        for obj_str in brace_objects:
            try:
                results.append(json.loads(obj_str))
            except Exception:
                continue
        if results:
            result = _extract_dicts(results)
            if result:
                return result

    logger.warning("所有 11 种 JSON 解析策略均失败，返回默认值")
    return default_return


def _salvage_truncated_json(text: str) -> Optional[str]:
    """
    尝试修复截断的 JSON 数组。
    处理场景：末尾字段不完整（如 `"预期结果"` 没有值和逗号）、括号未闭合。
    """
    text = text.strip()
    if not text:
        return None

    if not text.startswith('['):
        return None

    # 先尝试修复括号平衡
    depth = 0
    brace_depth = 0

    for ch in text:
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
        elif ch == '{':
            brace_depth += 1
        elif ch == '}':
            brace_depth -= 1

    fixed = text
    if brace_depth > 0:
        fixed += '}' * brace_depth
    if depth > 0:
        fixed += ']' * depth

    if fixed == text:
        return None

    # 括号闭和后尝试解析，如果仍然失败则尝试剥离最后一个不完整的键值对
    try:
        json.loads(fixed)
        return fixed
    except json.JSONDecodeError:
        pass

    # 剥离末尾不完整字段：找到最后一个完整的 "key": 或 "key": value 模式
    # 从末尾开始，找到最后一个能被完整闭合的位置
    for strip_pos in range(len(fixed) - 1, 0, -1):
        chunk = fixed[:strip_pos]
        # 补上括号
        bd = 0
        for ch in chunk:
            if ch == '{': bd += 1
            elif ch == '}': bd -= 1
        if bd > 0:
            chunk += '}' * bd
        try:
            json.loads(chunk)
            return chunk
        except json.JSONDecodeError:
            continue

    return None


def _extract_complete_brace_objects(text: str) -> List[str]:
    """
    提取文本中所有完整的 {} JSON 对象。
    跳过最后一个不完整的对象（截断场景）。
    """
    objects = []
    i = 0
    while i < len(text):
        if text[i] == '{':
            depth = 0
            start = i
            while i < len(text):
                if text[i] == '{':
                    depth += 1
                elif text[i] == '}':
                    depth -= 1
                    if depth == 0:
                        # 找到一个完整对象
                        objects.append(text[start:i + 1])
                        break
                i += 1
            if depth > 0:
                # 最后一个对象不完整，丢弃
                pass
        i += 1
    return objects


def _extract_dicts(data: Any) -> List[Dict]:
    """
    从任意嵌套的数据结构中提取所有字典

    例如：
    - {"a": 1} -> [{"a": 1}]
    - [{"a": 1}, {"b": 2}] -> [{"a": 1}, {"b": 2}]
    - [[{"a": 1}], [{"b": 2}]] -> [{"a": 1}, {"b": 2}]
    """
    result = []

    if isinstance(data, dict):
        result.append(data)
    elif isinstance(data, list):
        for item in data:
            result.extend(_extract_dicts(item))
    # 忽略其他类型（字符串、数字等）

    return result


def _extract_balanced_json(text: str) -> Optional[str]:
    """提取第一个括号平衡的 JSON 片段"""
    stack = []
    start = -1
    for i, ch in enumerate(text):
        if ch in '{[':
            if not stack:
                start = i
            stack.append(ch)
        elif ch in '}]':
            if stack:
                stack.pop()
                if not stack and start != -1:
                    return text[start:i + 1]
    return None