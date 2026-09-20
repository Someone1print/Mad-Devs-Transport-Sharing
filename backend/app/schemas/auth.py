from pydantic import BaseModel, Field, field_validator

from app.schemas.user import UserOut


def _stripped_name(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("name must not be blank")
    return stripped


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    # format, domain and password rules are checked in the endpoint, which names the failed rule
    email: str = Field(max_length=1000)
    password: str = Field(max_length=1000)

    @field_validator("name")
    @classmethod
    def strip_and_require_text(cls, value: str) -> str:
        return _stripped_name(value)


class LoginIn(BaseModel):
    email: str = Field(max_length=1000)
    password: str = Field(max_length=1000)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(max_length=1000)
    new_password: str = Field(max_length=1000)


class AuthOut(BaseModel):
    """The signed-in user and their session token (also set as the HttpOnly cookie)."""

    user: UserOut
    token: str
