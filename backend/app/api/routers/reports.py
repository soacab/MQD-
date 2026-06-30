from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import current_user
from app.api.responses import ok
from app.services import report_service

router = APIRouter()


@router.get("/api/v1/reports")
def list_reports(
    project_id: int | None = None,
    qg_node_id: int | None = None,
    overall_result: str | None = None,
    generated_by: int | None = None,
    generated_from: str | None = None,
    generated_to: str | None = None,
    user: dict = Depends(current_user),
) -> dict[str, Any]:
    return ok(report_service.list_reports(project_id, qg_node_id, overall_result, generated_by, generated_from, generated_to, user))


@router.get("/api/v1/reports/{report_id}")
def get_report(report_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(report_service.get_report(report_id, user))
