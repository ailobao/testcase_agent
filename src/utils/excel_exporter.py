"""统一的 Excel 导出服务"""
import os
import re
import json
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional

from src.config.settings import DATA_DIR


class ExcelExporter:
    """统一的 Excel 导出器"""

    @staticmethod
    def export_manual_cases(cases: List[Dict], project_name: str, module_name: str,
                            test_type: str = "", fields: List[str] = None) -> Optional[str]:
        """
        导出手工测试用例 Excel

        参数:
        - cases: 用例列表
        - project_name: 项目名称
        - module_name: 模块名称
        - test_type: 测试类型
        - fields: 动态字段列表
        """
        if not cases:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if test_type and test_type.strip():
            prefix = f"{ExcelExporter._clean_name(project_name)}_{ExcelExporter._clean_name(module_name)}_{ExcelExporter._clean_name(test_type)}"
        else:
            prefix = f"{ExcelExporter._clean_name(project_name)}_{ExcelExporter._clean_name(module_name)}"

        filename = f"{prefix}_{timestamp}.xlsx"
        filepath = os.path.join(DATA_DIR, filename)

        # 动态列构建
        base_cols = ["用例ID", "标题", "前置条件", "测试步骤", "预期结果", "实际结果", "优先级"]

        dynamic_cols = []
        if fields:
            dynamic_cols = fields
        else:
            all_keys = list(cases[0].keys()) if cases else []
            dynamic_cols = [k for k in all_keys if k not in base_cols]

        cols = base_cols + dynamic_cols
        cols = [c for c in cols if c in cases[0].keys()] if cases else cols

        df = pd.DataFrame(cases)
        for col in cols:
            if col not in df.columns:
                df[col] = ""

        df = df[cols]
        df.to_excel(filepath, sheet_name="测试用例", index=False)

        ExcelExporter._beautify_excel(filepath)
        return filepath

    @staticmethod
    def export_api_cases(cases: List[Dict], project_name: str, module_name: str) -> Optional[str]:
        """导出接口测试用例 Excel"""
        if not cases:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{project_name}_{module_name}_API_{timestamp}.xlsx"
        filename = re.sub(r'[\\/*?:"<>|]', '', filename)
        filepath = os.path.join(DATA_DIR, filename)

        is_login_module = "login" in module_name.lower() or "登录" in module_name

        rows = []
        for case in cases:
            body = ExcelExporter._ensure_dict(case.get("body", {}))
            title = case.get("title", "")

            if "Token" in title and ("过期" in title or "错误" in title or "空" in title or "缺失" in title):
                pre_condition = "无（Token异常场景）"
            elif is_login_module:
                pre_condition = "无（登录前状态）"
            else:
                pre_condition = "用户已登录，token有效"

            row = {
                "用例编号": case.get("case_id", ""),
                "用例标题": title,
                "模块/项目": f"{project_name}/{module_name}",
                "优先级": case.get("priority", "P2"),
                "前置条件": pre_condition,
                "请求方法": case.get("method", "POST"),
                "URL": case.get("url", ""),
                "请求头": json.dumps(case.get("headers", {}), ensure_ascii=False),
                "请求体": json.dumps(body, ensure_ascii=False),
                "预期结果": json.dumps(case.get("assert", {}), ensure_ascii=False)
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        df.to_excel(filepath, sheet_name="接口用例", index=False)

        ExcelExporter._beautify_excel(filepath)
        return filepath

    @staticmethod
    def export_ai_cases(result: Dict, project_name: str, module_name: str,
                        need_analysis: bool = True) -> Optional[str]:
        """导出 AI 测试用例 Excel"""
        if not result.get("cases"):
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{ExcelExporter._clean_name(project_name)}_{ExcelExporter._clean_name(module_name)}_AITest_{timestamp}.xlsx"
        filepath = os.path.join(DATA_DIR, filename)

        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            if need_analysis and result.get("analysis"):
                analysis_lines = result["analysis"].strip().split('\n')
                analysis_df = pd.DataFrame({"内容": analysis_lines})
                analysis_df.to_excel(writer, sheet_name="四维分析", index=False)

            cases_df = pd.DataFrame(result["cases"])
            cols = ["测试ID", "测试标题", "测试类型", "优先级", "关联需求", "前置条件",
                    "测试数据", "测试步骤", "预期结果", "实际结果", "执行人"]
            cols = [c for c in cols if c in cases_df.columns]
            if cols:
                cases_df[cols].to_excel(writer, sheet_name="测试用例", index=False)

        ExcelExporter._beautify_excel(filepath)
        return filepath

    @staticmethod
    def _beautify_excel(filepath: str) -> None:
        """美化 Excel 格式"""
        try:
            from scripts.fix_excel import fix_excel_format
            fix_excel_format(filepath)
        except ImportError:
            pass
        except Exception:
            pass

    @staticmethod
    def _clean_name(name: str) -> str:
        """清理文件名中的非法字符"""
        if not name:
            return "unknown"
        return re.sub(r'[\\/*?:"<>|]', "", name)[:50]

    @staticmethod
    def _ensure_dict(value: Any, default: dict = None) -> dict:
        """确保值是字典"""
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