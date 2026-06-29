from app.core.database import execute, query_one, to_json


def seed_database() -> None:
    if not query_one("SELECT id FROM users WHERE uid = ?", ("admin",)):
        execute(
            "INSERT INTO users(uid, name, email, status) VALUES (?, ?, ?, ?)",
            ("admin", "系统管理员", "admin@example.com", "active"),
        )
        admin = query_one("SELECT id FROM users WHERE uid = ?", ("admin",))
        for permission in ("super_admin", "inspection_engineer", "rules_admin", "project_admin"):
            execute(
                "INSERT INTO user_permissions(user_id, permission_code) VALUES (?, ?)",
                (admin["id"], permission),
            )

    for sort_order, code in enumerate(("QG2", "QG3.1", "QG3.2", "QG3.3", "QG3", "QG4"), start=1):
        if not query_one("SELECT id FROM qg_nodes WHERE node_code = ?", (code,)):
            execute(
                "INSERT INTO qg_nodes(node_code, node_name, sort_order, is_active) VALUES (?, ?, ?, 1)",
                (code, code, sort_order),
            )

    if not query_one("SELECT key FROM system_settings WHERE key = ?", ("auto_check_enabled",)):
        execute(
            "INSERT INTO system_settings(key, value_json, saved_by) VALUES (?, ?, ?)",
            ("auto_check_enabled", to_json(True), 1),
        )
