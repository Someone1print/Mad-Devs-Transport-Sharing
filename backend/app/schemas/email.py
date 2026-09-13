from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EmailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    to_address: str
    subject: str
    body: str
    dedup_key: str
    created_at: datetime
