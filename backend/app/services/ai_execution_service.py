from typing import Any

from app.core.database import execute, from_json, query_all, query_one, to_json, transaction
from app.core.enums import AdapterType, AutoCheckResult, AutoCheckStatus, InspectionItemStatus
from app.core.exceptions import BusinessError
from app.vdrive import list_vdrive_files


def run_mock_auto_check(item_id: int, execution_rule_snapshot: dict[str, Any]) -> None:
    execute(
        """
        INSERT INTO auto_check_results(
            inspection_item_id, attempt_no, is_latest, auto_status, auto_result,
            confidence, evidence_text, source_system, execution_rule_snapshot,
            raw_result_json, started_at, finished_at
        ) VALUES (?, 1, 1, ?, ?, 0.9, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            item_id,
            AutoCheckStatus.SUCCESS,
            AutoCheckResult.PASS,
            "Mock adapter found matching evidence; engineer confirmation is still required.",
            execution_rule_snapshot.get("adapter_type", AdapterType.MOCK),
            to_json(execution_rule_snapshot),
            to_json({"mock": True}),
        ),
    )
    execute("UPDATE inspection_items SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (InspectionItemStatus.AUTO_COMPLETED, item_id))


def execution_rule_snapshot_for_item(item: dict[str, Any]) -> dict[str, Any]:
    snapshot = query_one("SELECT * FROM rule_snapshots WHERE inspection_task_id = ?", (item["inspection_task_id"],))
    execution_snapshot = from_json(snapshot["auto_check_execution_rule_snapshot_json"], []) if snapshot else []
    for execution in execution_snapshot:
        if execution.get("business_check_rule_id") == item["source_business_rule_id"]:
            return execution
    raise BusinessError("AUTO_EXECUTION_RULE_REQUIRED", "检查项缺少自动执行规则快照")


def list_vdrive_files_for_item(item: dict[str, Any]) -> list[dict[str, Any]]:
    project = query_one(
        """
        SELECT p.*
        FROM projects p
        JOIN inspection_tasks t ON t.project_id = p.id
        WHERE t.id = ?
        """,
        (item["inspection_task_id"],),
    )
    if not project or not project["vdrive_folder_id"]:
        raise BusinessError("PROJECT_VDRIVE_REQUIRED", "项目缺少 VDrive 文件夹标识")
    return list_vdrive_files(int(project["vdrive_folder_id"]), project.get("vdrive_folder_path"))


def candidate_keywords(item: dict[str, Any], execution_rule_snapshot: dict[str, Any]) -> list[str]:
    config = execution_rule_snapshot.get("config_json") or {}
    raw_keywords = config.get("candidate_keywords") or config.get("file_name_keywords") or config.get("keywords")
    if raw_keywords is None:
        raw_keywords = [item.get("source_rule_code"), item.get("item_name_snapshot")]
    if isinstance(raw_keywords, str):
        raw_keywords = [raw_keywords]
    keywords: list[str] = []
    for keyword in raw_keywords or []:
        if isinstance(keyword, dict):
            keyword = keyword.get("keyword") or keyword.get("value") or keyword.get("text")
        if keyword:
            keywords.append(str(keyword).lower())
    return keywords


def match_candidate_files(
    item: dict[str, Any], execution_rule_snapshot: dict[str, Any], files: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    keywords = candidate_keywords(item, execution_rule_snapshot)
    if not keywords:
        return []
    matches: list[dict[str, Any]] = []
    for file in files:
        haystack = " ".join(str(file.get(field) or "") for field in ("file_name", "file_path", "file_version")).lower()
        score = sum(1 for keyword in keywords if keyword in haystack)
        if score:
            candidate = dict(file)
            candidate["recommend_score"] = min(1.0, score / max(len(keywords), 1))
            candidate["recommend_reason"] = "文件名、路径或版本匹配自动执行规则关键词"
            matches.append(candidate)
    matches.sort(key=lambda file: (-float(file.get("recommend_score") or 0), str(file.get("file_name") or "")))
    return matches


def next_attempt_no(item_id: int) -> int:
    row = query_one("SELECT MAX(attempt_no) AS max_attempt FROM auto_check_results WHERE inspection_item_id = ?", (item_id,))
    return int(row["max_attempt"] or 0) + 1


def latest_auto_check_result(item_id: int) -> dict[str, Any] | None:
    return query_one(
        "SELECT * FROM auto_check_results WHERE inspection_item_id = ? AND is_latest = 1 ORDER BY attempt_no DESC, id DESC LIMIT 1",
        (item_id,),
    )


def candidate_rows_for_result(result_id: int) -> list[dict[str, Any]]:
    rows = query_all("SELECT * FROM auto_check_candidate_files WHERE auto_check_result_id = ? ORDER BY is_recommended DESC, recommend_score DESC, id", (result_id,))
    for row in rows:
        row["is_recommended"] = bool(row["is_recommended"])
        row["is_selected"] = bool(row["is_selected"])
    return rows


def serialize_auto_check_result(row: dict[str, Any]) -> dict[str, Any]:
    row["is_latest"] = bool(row["is_latest"])
    row["execution_rule_snapshot"] = from_json(row["execution_rule_snapshot"], {})
    row["raw_result_json"] = from_json(row["raw_result_json"], {})
    row["candidate_files"] = candidate_rows_for_result(row["id"])
    return row


def insert_auto_check_result(
    item_id: int,
    auto_status: str,
    auto_result: str,
    evidence_text: str,
    execution_rule_snapshot: dict[str, Any],
    raw_result: dict[str, Any],
    error_code: str | None = None,
    error_message: str | None = None,
) -> int:
    attempt_no = next_attempt_no(item_id)
    execute("UPDATE auto_check_results SET is_latest = 0 WHERE inspection_item_id = ?", (item_id,))
    cur = execute(
        """
        INSERT INTO auto_check_results(
            inspection_item_id, attempt_no, is_latest, auto_status, auto_result,
            confidence, evidence_text, source_system, execution_rule_snapshot,
            raw_result_json, error_code, error_message, started_at, finished_at
        ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            item_id,
            attempt_no,
            auto_status,
            auto_result,
            0.9 if auto_status == AutoCheckStatus.SUCCESS else None,
            evidence_text,
            execution_rule_snapshot.get("adapter_type", AdapterType.VDRIVE),
            to_json(execution_rule_snapshot),
            to_json(raw_result),
            error_code,
            error_message,
        ),
    )
    return int(cur.lastrowid)


def insert_candidate_files(result_id: int, candidates: list[dict[str, Any]], selected_id: int | None = None) -> None:
    recommended_index = 0
    for index, candidate in enumerate(candidates):
        is_selected = bool(selected_id and candidate.get("id") == selected_id)
        execute(
            """
            INSERT INTO auto_check_candidate_files(
                auto_check_result_id, vdrive_file_id, file_guid, file_name, file_ext,
                file_path, file_size, file_version, created_time, modified_time,
                recommend_score, recommend_reason, is_recommended, is_selected, source_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'system_scanned')
            """,
            (
                result_id,
                candidate.get("vdrive_file_id"),
                candidate.get("file_guid"),
                candidate.get("file_name"),
                candidate.get("file_ext"),
                candidate.get("file_path"),
                candidate.get("file_size"),
                candidate.get("file_version"),
                candidate.get("created_time"),
                candidate.get("modified_time"),
                candidate.get("recommend_score"),
                candidate.get("recommend_reason"),
                1 if index == recommended_index else 0,
                1 if is_selected or (selected_id is None and len(candidates) == 1) else 0,
            ),
        )


def scan_candidate_files(item: dict[str, Any]) -> dict[str, Any]:
    execution_rule = execution_rule_snapshot_for_item(item)
    try:
        files = list_vdrive_files_for_item(item)
        candidates = match_candidate_files(item, execution_rule, files)
    except Exception as exc:
        with transaction():
            result_id = insert_auto_check_result(
                item["id"],
                AutoCheckStatus.ERROR,
                AutoCheckResult.ERROR,
                "VDrive 文件元数据读取失败，已降级为人工判断。",
                execution_rule,
                {"error": str(exc)},
                "VDRIVE_READ_FAILED",
                str(exc),
            )
            execute("UPDATE inspection_items SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (InspectionItemStatus.MANUAL_REQUIRED, item["id"]))
        return serialize_auto_check_result(query_one("SELECT * FROM auto_check_results WHERE id = ?", (result_id,)))

    with transaction():
        if not candidates:
            result_id = insert_auto_check_result(
                item["id"],
                AutoCheckStatus.MANUAL_REQUIRED,
                AutoCheckResult.NOT_FOUND,
                "未找到匹配的 VDrive 候选文件，需人工判断。",
                execution_rule,
                {"candidate_count": 0},
            )
            execute("UPDATE inspection_items SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (InspectionItemStatus.MANUAL_REQUIRED, item["id"]))
        elif len(candidates) == 1:
            result_id = insert_auto_check_result(
                item["id"],
                AutoCheckStatus.SUCCESS,
                AutoCheckResult.PASS,
                "找到唯一匹配的 VDrive 候选文件，等待工程师确认。",
                execution_rule,
                {"candidate_count": 1},
            )
            insert_candidate_files(result_id, candidates)
            execute("UPDATE inspection_items SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (InspectionItemStatus.AUTO_COMPLETED, item["id"]))
        else:
            result_id = insert_auto_check_result(
                item["id"],
                AutoCheckStatus.CANDIDATE_WAITING,
                AutoCheckResult.MANUAL_REQUIRED,
                "发现多个 VDrive 候选文件，需要工程师选择。",
                execution_rule,
                {"candidate_count": len(candidates)},
            )
            insert_candidate_files(result_id, candidates)
            execute("UPDATE inspection_items SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (InspectionItemStatus.CANDIDATE_WAITING, item["id"]))
    return serialize_auto_check_result(query_one("SELECT * FROM auto_check_results WHERE id = ?", (result_id,)))


def list_latest_candidate_files(item_id: int) -> list[dict[str, Any]]:
    latest = latest_auto_check_result(item_id)
    if not latest:
        return []
    return candidate_rows_for_result(latest["id"])


def select_candidate_file(item: dict[str, Any], candidate_file_id: int) -> dict[str, Any]:
    if item["status"] != InspectionItemStatus.CANDIDATE_WAITING:
        raise BusinessError("ITEM_NOT_WAITING_FOR_CANDIDATE", "当前检查项不在候选文件待选状态")
    latest = latest_auto_check_result(item["id"])
    if not latest:
        raise BusinessError("AUTO_CHECK_RESULT_NOT_FOUND", "未找到最新自动检查结果")
    candidate = query_one(
        "SELECT * FROM auto_check_candidate_files WHERE id = ? AND auto_check_result_id = ?",
        (candidate_file_id, latest["id"]),
    )
    if not candidate:
        raise BusinessError("CANDIDATE_FILE_NOT_FOUND", "候选文件不存在或不属于当前最新自动检查结果")
    with transaction():
        execute("UPDATE auto_check_candidate_files SET is_selected = 0 WHERE auto_check_result_id = ?", (latest["id"],))
        execute("UPDATE auto_check_candidate_files SET is_selected = 1 WHERE id = ?", (candidate_file_id,))
        execute(
            """
            UPDATE auto_check_results
            SET auto_status = ?, auto_result = ?, evidence_text = ?, raw_result_json = ?, finished_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                AutoCheckStatus.SUCCESS,
                AutoCheckResult.PASS,
                "工程师已选择 VDrive 候选文件，自动检查进入待确认。",
                to_json({"selected_candidate_file_id": candidate_file_id}),
                latest["id"],
            ),
        )
        execute("UPDATE inspection_items SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (InspectionItemStatus.AUTO_COMPLETED, item["id"]))
    return serialize_auto_check_result(query_one("SELECT * FROM auto_check_results WHERE id = ?", (latest["id"],)))
