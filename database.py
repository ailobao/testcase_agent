# database.py - 完整版
"""
【数据库规则优先级】
- priority 字段：数字越大优先级越高
- 读取规则时按 priority DESC 排序
- 业务规则合并优先级：数据库规则 > 用户输入 > 默认
"""
import sqlite3
import os
import json
import re

DB_PATH = os.path.join(os.path.dirname(__file__), "project_rules.db")


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
    print("✅ 数据库初始化完成")


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
        print("✅ 添加列: required_fields")

    if "url_path" not in columns:
        cursor.execute("ALTER TABLE project_rules ADD COLUMN url_path TEXT")
        print("✅ 添加列: url_path")

    if "default_body" not in columns:
        cursor.execute("ALTER TABLE project_rules ADD COLUMN default_body TEXT")
        print("✅ 添加列: default_body")

    conn.commit()
    conn.close()
    print("✅ 数据库迁移完成")


def get_rule(project_name, module_name):
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
            "input_fields": row[0],
            "verification_code": row[1],
            "extra_features": row[2],
            "constraints": row[3],
            "priority": row[4],
            "required_fields": row[5] if len(row) > 5 else None,
            "url_path": row[6] if len(row) > 6 else None,
            "default_body": row[7] if len(row) > 7 else None,
        }
        return result
    return None


def save_rule(project_name, module_name, input_fields="", required_fields="", url_path="", default_body="",
              verification_code="", extra_features="", constraints="", priority=1):
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


def list_all_rules():
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


def delete_rule(project_name, module_name):
    """删除规则"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM project_rules WHERE project_name = ? AND module_name = ?", (project_name, module_name))
    conn.commit()
    conn.close()


def get_module_names(project_name):
    """获取指定项目下的所有模块名称"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT module_name FROM project_rules WHERE project_name = ?", (project_name,))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


def get_all_projects():
    """获取所有项目名称"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT project_name FROM project_rules")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


if __name__ == "__main__":
    migrate_db()
    print("=" * 60)
    print("数据库初始化完成")
    print("=" * 60)