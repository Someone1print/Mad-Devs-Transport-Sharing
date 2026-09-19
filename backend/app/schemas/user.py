from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field

from app.services.mail import address_for


class UserEmailUpdate(BaseModel):
    """The new login and receipt address; format, domain and uniqueness are checked in the
    endpoint (an empty value is refused: the address is how the user signs in)."""

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
