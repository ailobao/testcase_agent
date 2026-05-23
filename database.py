# database.py
import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(__file__), "project_rules.db")


def get_connection():
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


def get_rule(project_name, module_name):
    """获取指定项目和模块的规则"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT input_fields, verification_code, extra_features, constraints, priority FROM project_rules WHERE project_name = ? AND module_name = ?",
        (project_name, module_name)
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "input_fields": row[0],
            "verification_code": row[1],
            "extra_features": row[2],
            "constraints": row[3],
            "priority": row[4]
        }
    return None


def save_rule(project_name, module_name, input_fields="", verification_code="", extra_features="", constraints="",
              priority=1):
    """保存或更新规则"""
    conn = get_connection()
    cursor = conn.cursor()

    # 处理 input_fields：如果是列表字符串，尝试解析
    if input_fields and input_fields.startswith('['):
        try:
            # 验证是否为有效JSON
            json.loads(input_fields)
        except:
            pass

    cursor.execute('''
        INSERT INTO project_rules (project_name, module_name, input_fields, verification_code, extra_features, constraints, priority)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(project_name, module_name) 
        DO UPDATE SET 
            input_fields = excluded.input_fields,
            verification_code = excluded.verification_code,
            extra_features = excluded.extra_features,
            constraints = excluded.constraints,
            priority = excluded.priority,
            updated_at = CURRENT_TIMESTAMP
    ''', (project_name, module_name, input_fields, verification_code, extra_features, constraints, priority))
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


if __name__ == "__main__":
    init_db()