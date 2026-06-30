from typing import Any

from fastapi import APIRouter, Body, Depends

from app.api.deps import current_user
from app.api.responses import ok
from app.services import inspection_service

router = APIRouter()


@router.post("/api/v1/inspection-tasks/prepare")
def prepare_inspection_task(payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(inspection_service.prepare_inspection_task(payload, user))


@router.post("/api/v1/inspection-tasks")
def create_inspection_task(payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(inspection_service.create_inspection_task(payload, user))


@router.get("/api/v1/inspection-tasks")
def list_inspection_tasks(status: str | None = None, project_id: int | None = None, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(inspection_service.list_inspection_tasks(status, project_id, user))


@router.get("/api/v1/inspection-tasks/{task_id}")
def get_inspection_task(task_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(inspection_service.get_inspection_task(task_id, user))


@router.get("/api/v1/inspection-tasks/{task_id}/current-round/items")
def current_round_items(task_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(inspection_service.current_round_items(task_id, user))


@router.get("/api/v1/dashboard/overview")
def dashboard_overview(user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(inspection_service.dashboard_overview(user))


@router.get("/api/v1/dashboard/my-todos")
def dashboard_my_todos(user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(inspection_service.dashboard_my_todos(user))


@router.get("/api/v1/inspection-items/{item_id}")
def get_inspection_item(item_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(inspection_service.get_inspection_item(item_id, user))


@router.post("/api/v1/inspection-items/{item_id}/convert-to-manual")
def convert_to_manual(item_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(inspection_service.convert_to_manual(item_id, payload, user))


@router.post("/api/v1/inspection-items/{item_id}/confirm")
def confirm_item(item_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(inspection_service.confirm_item(item_id, payload, user))


@router.post("/api/v1/inspection-tasks/{task_id}/archive-current-round")
def archive_current_round(task_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(inspection_service.archive_current_round(task_id, user))


@router.post("/api/v1/inspection-tasks/{task_id}/void")
def void_task(task_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(inspection_service.void_task(task_id, payload, user))


@router.get("/api/v1/rectification-items")
def list_rectifications(task_id: int | None = None, project_id: int | None = None, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(inspection_service.list_rectifications(task_id, project_id, user))


@router.post("/api/v1/rectification-items/{rectification_id}/mark-done")
def mark_rectification_done(rectification_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(inspection_service.mark_rectification_done(rectification_id, user))


@router.post("/api/v1/rectification-items/{rectification_id}/undo-done")
def undo_rectification_done(rectification_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(inspection_service.undo_rectification_done(rectification_id, user))


@router.get("/api/v1/followup-items")
def list_followups(task_id: int | None = None, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(inspection_service.list_followups(task_id, user))


@router.post("/api/v1/followup-items/{followup_id}/close")
def close_followup(followup_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(inspection_service.close_followup(followup_id, user))


@router.post("/api/v1/inspection-tasks/{task_id}/trigger-recheck")
def trigger_recheck(task_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(inspection_service.trigger_recheck(task_id, user))


@router.get("/api/v1/inspection-items/{item_id}/auto-check-results")
def list_auto_check_results(item_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(inspection_service.list_auto_check_results(item_id, user))
