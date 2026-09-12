"""Mailbox stub: e-mails are rows in `emails`, never sent anywhere (no SMTP, per the assignment).

Idempotent by construction: `send_email` inserts with ON CONFLICT (dedup_key) DO NOTHING, so a
retry, a double click or two concurrent requests with the same key leave exactly one message.
"""

import re
import unicodedata

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Email, User

MAIL_DOMAIN = "example.invalid"  # RFC 2606: guaranteed never to resolve

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya", "ң": "ng", "ө": "o", "ү": "u",
}  # fmt: skip


def address_for(name: str) -> str:
    """A stable, obviously fake address derived from the display name (users have no e-mail)."""
    lowered = name.strip().lower()
    latin = "".join(_TRANSLIT.get(ch, ch) for ch in lowered)
    ascii_only = unicodedata.normalize("NFKD", latin).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")
    return f"{slug or 'user'}@{MAIL_DOMAIN}"


async def send_email(
    session: AsyncSession, user: User, subject: str, body: str, dedup_key: str
) -> Email | None:
    """Store the message for the user; returns None when `dedup_key` was already used.

    Does not commit: the caller decides the transaction (a receipt e-mail is written in the
    same transaction as the receipt itself).
    """
    statement = (
        insert(Email)
        .values(
            user_id=user.id,
            to_address=address_for(user.name),
            subject=subject,
            body=body,
            dedup_key=dedup_key,
        )
        .on_conflict_do_nothing(index_elements=["dedup_key"])
        .returning(Email.id)
    )
    email_id = await session.scalar(statement)
    if email_id is None:
        return None
    return await session.get(Email, email_id)
