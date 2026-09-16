from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.services.mail import address_for


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def strip_and_require_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped


class UserEmailUpdate(BaseModel):
    """`""` or `null` clears the address; the format itself is checked in the endpoint."""

    email: str | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str | None = None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def mail_address(self) -> str:
        """Where receipts go right now: the entered e-mail, or the stub derived from the name."""
        return self.email or address_for(self.name)
