from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models import Email
from app.schemas.email import EmailOut

router = APIRouter()


@router.get("/emails", summary="The caller's mailbox (stub: stored, never sent), newest first")
async def list_emails(
    user: CurrentUser, session: Annotated[AsyncSession, Depends(get_db)]
) -> list[EmailOut]:
    emails = await session.scalars(
        select(Email)
        .where(Email.user_id == user.id)
        .order_by(Email.created_at.desc(), Email.id.desc())
    )
    return [EmailOut.model_validate(e) for e in emails]
