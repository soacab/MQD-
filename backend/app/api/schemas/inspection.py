from typing import Literal

from app.api.schemas.common import StrictRequest


class PrepareInspectionTaskRequest(StrictRequest):
    vdrive_url: str | None = None


class CreateInspectionTaskRequest(StrictRequest):
    project_id: int | None = None
    qg_node_id: int | None = None
    vdrive_url: str | None = None
    project_name: str | None = None
    customer: str | None = None
    project_category: str | None = None
    bu: str | None = None
    project_level: str | None = None
    mq_user_id: int | None = None
    mp_owner: str | None = None
    group_name: str | None = None
    planned_mp_date: str | None = None
    production_line: str | None = None
    receive_date: str | None = None
    models: list[str] | str | None = None


class ConvertToManualRequest(StrictRequest):
    reason: str | None = None


class ConfirmItemRequest(StrictRequest):
    decision_result: Literal["pass", "fail", "conditional", "na"] | None = None
    decision_text: str | None = None
    responsible_owner: str | None = None
    countermeasure: str | None = None
    planned_finish_date: str | None = None
    override_auto_result: bool | None = None
    override_reason: str | None = None


class VoidTaskRequest(StrictRequest):
    void_reason: str | None = None
