"""规则管理器 - 数据库操作封装"""
import sys
import os
import json
import sqlite3
import logging
from typing import Dict, List, Optional

logger = logging.getLogger("main.rule_manager")

# 将项目根目录添加到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

DB_PATH = os.path.join(project_root, "project_rules.db")


def get_connection():
    """获取数据库连接"""
    return sqlite3.connect(DB_PATH)


def init_db():
    """初始化数据库：创建规则表（如果不存在）"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS project_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            module_name TEXT NOT NULL,
            input_fields TEXT,
            required_fields TEXT,
            url_path TEXT,
            default_body TEXT,
            verification_code TEXT,
            extra_features TEXT,
            constraints TEXT,
            priority INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_name, module_name)
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("✅ 数据库初始化完成")


def migrate_db():
    """数据库迁移：添加缺失的列"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='project_rules'")
    if not cursor.fetchone():
        conn.close()
        init_db()
        return

    cursor.execute("PRAGMA table_info(project_rules)")
    columns = [col[1] for col in cursor.fetchall()]

    if "required_fields" not in columns:
        cursor.execute("ALTER TABLE project_rules ADD COLUMN required_fields TEXT")
        logger.info("✅ 添加列: required_fields")

    if "url_path" not in columns:
        cursor.execute("ALTER TABLE project_rules ADD COLUMN url_path TEXT")
        logger.info("✅ 添加列: url_path")

    if "default_body" not in columns:
        cursor.execute("ALTER TABLE project_rules ADD COLUMN default_body TEXT")
        logger.info("✅ 添加列: default_body")

    conn.commit()
    conn.close()
    logger.info("✅ 数据库迁移完成")


def get_rule(project_name: str, module_name: str) -> Optional[Dict]:
    """获取指定项目和模块的规则"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(project_rules)")
    columns = [col[1] for col in cursor.fetchall()]

    select_cols = ["input_fields", "verification_code", "extra_features", "constraints", "priority"]
    if "required_fields" in columns:
        select_cols.append("required_fields")
    else:
        select_cols.append("'' as required_fields")

    if "url_path" in columns:
        select_cols.append("url_path")
    else:
        select_cols.append("'' as url_path")

    if "default_body" in columns:
        select_cols.append("default_body")
    else:
        select_cols.append("'' as default_body")

    sql = f"SELECT {', '.join(select_cols)} FROM project_rules WHERE project_name = ? AND module_name = ?"

    cursor.execute(sql, (project_name, module_name))
    row = cursor.fetchone()
    conn.close()

    if row:
        result = {
            "input_fields": json.loads(row[0]) if row[0] else [],
            "verification_code": row[1] or "",
            "extra_features": json.loads(row[2]) if row[2] else [],
            "constraints": row[3] or "",
            "priority": row[4] or 1,
            "required_fields": json.loads(row[5]) if row[5] else [],
            "url_path": row[6] or "",
            "default_body": json.loads(row[7]) if row[7] else {},
        }
        return result
    return None


def save_rule(project_name: str, module_name: str,
              input_fields: str = "",
              required_fields: str = "",
              url_path: str = "",
              default_body: str = "",
              verification_code: str = "",
              extra_features: str = "",
              constraints: str = "",
              priority: int = 1):
    """保存或更新规则"""
    conn = get_connection()
    cursor = conn.cursor()

    migrate_db()

    cursor.execute('''
        INSERT INTO project_rules (project_name, module_name, input_fields, required_fields, url_path, default_body, verification_code, extra_features, constraints, priority)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(project_name, module_name) 
        DO UPDATE SET 
            input_fields = excluded.input_fields,
            required_fields = excluded.required_fields,
            url_path = excluded.url_path,
            default_body = excluded.default_body,
            verification_code = excluded.verification_code,
            extra_features = excluded.extra_features,
            constraints = excluded.constraints,
            priority = excluded.priority,
            updated_at = CURRENT_TIMESTAMP
    ''', (project_name, module_name, input_fields, required_fields, url_path, default_body,
          verification_code, extra_features, constraints, priority))
    conn.commit()
    conn.close()


def list_all_rules() -> List:
    """列出所有规则"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT project_name, module_name, input_fields, constraints, priority FROM project_rules ORDER BY priority DESC")
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    return rows


def delete_rule(project_name: str, module_name: str):
    """删除规则"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM project_rules WHERE project_name = ? AND module_name = ?", (project_name, module_name))
    conn.commit()
    conn.close()


def get_module_names(project_name: str) -> List[str]:
    """获取指定项目下的所有模块名称"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT module_name FROM project_rules WHERE project_name = ?", (project_name,))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


def get_all_projects() -> List[str]:
    """获取所有项目名称"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT project_name FROM project_rules")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]