from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class HealthDbResponse(BaseModel):
    status: Literal["ok", "error"]
    database: Literal["ok", "unavailable"]
