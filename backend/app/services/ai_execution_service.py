from typing import Any

from app.core.database import execute, to_json
from app.core.enums import AdapterType, AutoCheckResult, AutoCheckStatus, InspectionItemStatus


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
