from typing import Any

from pydantic import BaseModel, ConfigDict


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


def request_dict(payload: BaseModel) -> dict[str, Any]:
    return payload.model_dump(exclude_unset=True)
