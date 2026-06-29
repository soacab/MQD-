import json
import sqlite3
from pathlib import Path
from typing import Any

from app.core.config import settings


_connection: sqlite3.Connection | None = None


def _database_path() -> str:
    prefix = "sqlite:///"
    if not settings.database_url.startswith(prefix):
        raise RuntimeError("Only sqlite database URLs are supported by the MVP runtime.")
    return settings.database_url.removeprefix(prefix)


def connect() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        path = _database_path()
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        _connection = sqlite3.connect(path, check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA foreign_keys = ON")
    return _connection


def reset_database() -> None:
    global _connection
    if _connection is not None:
        _connection.close()
    _connection = None
    create_schema()


def close_database() -> None:
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


def create_schema() -> None:
    conn = connect()
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def execute(sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
    cur = connect().execute(sql, params)
    connect().commit()
    return cur


def query_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    row = connect().execute(sql, params).fetchone()
    return dict(row) if row else None


def query_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in connect().execute(sql, params).fetchall()]


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def from_json(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    return json.loads(value)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    email TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    permission_code TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, permission_code)
);

CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    saved_by INTEGER REFERENCES users(id),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    detail_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_code TEXT,
    project_name TEXT NOT NULL,
    customer TEXT NOT NULL,
    project_category TEXT,
    bu TEXT,
    project_level TEXT,
    mq_user_id INTEGER REFERENCES users(id),
    mq_user_name_snapshot TEXT,
    mp_owner TEXT,
    group_name TEXT,
    planned_mp_date TEXT,
    production_line TEXT,
    vdrive_url TEXT,
    vdrive_folder_guid TEXT,
    vdrive_folder_id INTEGER,
    vdrive_folder_name TEXT,
    vdrive_folder_path TEXT,
    status TEXT NOT NULL DEFAULT 'normal',
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_by INTEGER REFERENCES users(id),
    deleted_at TEXT,
    delete_reason TEXT
);

CREATE TABLE IF NOT EXISTS project_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    receive_date TEXT NOT NULL,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS project_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    project_order_id INTEGER NOT NULL REFERENCES project_orders(id),
    model_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS qg_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_code TEXT NOT NULL UNIQUE,
    node_name TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS business_rule_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qg_node_id INTEGER NOT NULL REFERENCES qg_nodes(id),
    version_no TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    change_summary TEXT,
    published_by INTEGER REFERENCES users(id),
    published_at TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(qg_node_id, version_no)
);

CREATE TABLE IF NOT EXISTS business_check_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_rule_version_id INTEGER NOT NULL REFERENCES business_rule_versions(id),
    qg_node_id INTEGER NOT NULL REFERENCES qg_nodes(id),
    rule_code TEXT NOT NULL,
    item_name TEXT NOT NULL,
    item_type TEXT NOT NULL,
    check_type TEXT NOT NULL,
    checklist_requirement TEXT,
    owner_dept TEXT,
    is_apqp INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(business_rule_version_id, rule_code)
);

CREATE TABLE IF NOT EXISTS auto_check_execution_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_check_rule_id INTEGER NOT NULL REFERENCES business_check_rules(id),
    execution_code TEXT NOT NULL,
    execution_mode TEXT NOT NULL,
    adapter_type TEXT NOT NULL,
    config_json TEXT NOT NULL,
    config_version TEXT NOT NULL,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(business_check_rule_id, execution_code)
);

CREATE TABLE IF NOT EXISTS inspection_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    qg_node_id INTEGER NOT NULL REFERENCES qg_nodes(id),
    task_no TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    current_round_no INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    archived_at TEXT,
    last_operated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    voided_by INTEGER REFERENCES users(id),
    voided_at TEXT,
    void_reason TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_active_task
ON inspection_tasks(project_id, qg_node_id)
WHERE status IN ('running', 'rectifying');

CREATE TABLE IF NOT EXISTS rule_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_task_id INTEGER NOT NULL UNIQUE REFERENCES inspection_tasks(id),
    business_rule_version_id INTEGER NOT NULL REFERENCES business_rule_versions(id),
    business_rule_snapshot_json TEXT NOT NULL,
    auto_check_execution_rule_snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inspection_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_task_id INTEGER NOT NULL REFERENCES inspection_tasks(id),
    round_no INTEGER NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(inspection_task_id, round_no)
);

CREATE TABLE IF NOT EXISTS inspection_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_task_id INTEGER NOT NULL REFERENCES inspection_tasks(id),
    inspection_round_id INTEGER NOT NULL REFERENCES inspection_rounds(id),
    source_rule_code TEXT NOT NULL,
    source_business_rule_id INTEGER,
    item_name_snapshot TEXT NOT NULL,
    item_type_snapshot TEXT NOT NULL,
    check_type_snapshot TEXT NOT NULL,
    checklist_requirement_snapshot TEXT,
    owner_dept_snapshot TEXT,
    is_apqp_snapshot INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    final_result TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS engineer_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_item_id INTEGER NOT NULL REFERENCES inspection_items(id),
    decision_result TEXT NOT NULL,
    decision_text TEXT NOT NULL,
    responsible_owner TEXT,
    countermeasure TEXT,
    planned_finish_date TEXT,
    override_auto_result INTEGER NOT NULL DEFAULT 0,
    override_reason TEXT,
    decided_by INTEGER REFERENCES users(id),
    decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rectification_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_task_id INTEGER NOT NULL REFERENCES inspection_tasks(id),
    source_round_id INTEGER NOT NULL REFERENCES inspection_rounds(id),
    source_item_id INTEGER NOT NULL UNIQUE REFERENCES inspection_items(id),
    project_id INTEGER NOT NULL REFERENCES projects(id),
    item_name_snapshot TEXT NOT NULL,
    problem_desc TEXT NOT NULL,
    responsible_owner TEXT NOT NULL,
    planned_finish_date TEXT NOT NULL,
    marked_done_by INTEGER REFERENCES users(id),
    marked_done_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS followup_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_task_id INTEGER NOT NULL REFERENCES inspection_tasks(id),
    source_round_id INTEGER NOT NULL REFERENCES inspection_rounds(id),
    source_item_id INTEGER NOT NULL UNIQUE REFERENCES inspection_items(id),
    project_id INTEGER NOT NULL REFERENCES projects(id),
    item_name_snapshot TEXT NOT NULL,
    countermeasure TEXT NOT NULL,
    responsible_owner TEXT NOT NULL,
    planned_finish_date TEXT NOT NULL,
    closed_by INTEGER REFERENCES users(id),
    closed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auto_check_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_item_id INTEGER NOT NULL REFERENCES inspection_items(id),
    attempt_no INTEGER NOT NULL,
    is_latest INTEGER NOT NULL DEFAULT 1,
    auto_status TEXT NOT NULL,
    auto_result TEXT,
    confidence REAL,
    evidence_text TEXT,
    source_system TEXT,
    execution_rule_snapshot TEXT,
    raw_result_json TEXT,
    error_code TEXT,
    error_message TEXT,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auto_check_candidate_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    auto_check_result_id INTEGER NOT NULL REFERENCES auto_check_results(id),
    vdrive_file_id INTEGER,
    file_guid TEXT,
    file_name TEXT NOT NULL,
    file_ext TEXT,
    file_path TEXT,
    file_size INTEGER,
    file_version TEXT,
    created_time TEXT,
    modified_time TEXT,
    recommend_score REAL,
    recommend_reason TEXT,
    is_recommended INTEGER NOT NULL DEFAULT 0,
    is_selected INTEGER NOT NULL DEFAULT 0,
    source_type TEXT NOT NULL DEFAULT 'system_scanned',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS file_parse_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_item_id INTEGER NOT NULL REFERENCES inspection_items(id),
    auto_check_result_id INTEGER REFERENCES auto_check_results(id),
    candidate_file_id INTEGER REFERENCES auto_check_candidate_files(id),
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    parser_type TEXT,
    parser_rule_code TEXT,
    object_key TEXT,
    parsed_result_json TEXT,
    error_code TEXT,
    error_message TEXT,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inspection_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_task_id INTEGER NOT NULL UNIQUE REFERENCES inspection_tasks(id),
    project_id INTEGER NOT NULL REFERENCES projects(id),
    qg_node_id INTEGER NOT NULL REFERENCES qg_nodes(id),
    report_no TEXT NOT NULL UNIQUE,
    overall_result TEXT,
    latest_round_no INTEGER NOT NULL DEFAULT 1,
    business_rule_version_no TEXT NOT NULL,
    generated_by INTEGER REFERENCES users(id),
    generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_modified_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    summary_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS report_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES inspection_reports(id),
    source_rule_code TEXT NOT NULL,
    item_name_snapshot TEXT NOT NULL,
    item_type_snapshot TEXT NOT NULL,
    check_type_snapshot TEXT NOT NULL,
    checklist_requirement_snapshot TEXT,
    latest_inspection_item_id INTEGER NOT NULL REFERENCES inspection_items(id),
    auto_result_snapshot TEXT,
    engineer_decision_snapshot TEXT,
    final_result TEXT,
    process_records_json TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(report_id, source_rule_code)
);

CREATE TABLE IF NOT EXISTS report_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_item_id INTEGER NOT NULL REFERENCES report_items(id),
    correction_text TEXT NOT NULL,
    corrected_by INTEGER REFERENCES users(id),
    corrected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vdrive_scan_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    inspection_task_id INTEGER REFERENCES inspection_tasks(id),
    inspection_round_id INTEGER REFERENCES inspection_rounds(id),
    scan_status TEXT NOT NULL,
    folders_count INTEGER NOT NULL DEFAULT 0,
    files_count INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS vdrive_folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_batch_id INTEGER NOT NULL REFERENCES vdrive_scan_batches(id),
    folder_guid TEXT NOT NULL,
    folder_id INTEGER,
    folder_name TEXT,
    folder_path TEXT,
    parent_folder_guid TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vdrive_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_batch_id INTEGER NOT NULL REFERENCES vdrive_scan_batches(id),
    folder_guid TEXT,
    vdrive_file_id INTEGER,
    file_guid TEXT,
    file_name TEXT,
    file_ext TEXT,
    file_path TEXT,
    file_size INTEGER,
    file_version TEXT,
    created_time TEXT,
    modified_time TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""
