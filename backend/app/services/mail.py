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
LOCAL_PART_MAX = 64  # RFC 5321; also keeps a 64-char name of 4-letter expansions in String(255)
EMAIL_MAX_LENGTH = 254  # RFC 5321 path limit; also the users.email column

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya", "ң": "ng", "ө": "o", "ү": "u",
}  # fmt: skip


def email_problem(value: str) -> str | None:
    """Why `value` is not an acceptable address, as a key the client turns into a hint.

    None means the format is fine. Format only — no whitespace, exactly one `@`, a local part,
    a domain with a dot — because the stub cannot send a confirmation code, so existence is
    never checked. The same keys come out of the client-side copy (frontend/src/account/email.ts);
    shared/email-cases.json pins both.
    """
    if any(ch.isspace() for ch in value):
        return "whitespace"
    if len(value) > EMAIL_MAX_LENGTH:
        return "too_long"
    if value.count("@") != 1:
        return "at_sign"
    local_part, domain = value.split("@")
    if not local_part:
        return "local_part"
    if "." not in domain or domain.startswith(".") or domain.endswith(".") or ".." in domain:
        return "domain"
    return None


def recipient_address(user: User) -> str:
    """The address entered in the account, or the name-derived stub while it is empty."""
    return user.email or address_for(user.name)


def address_for(name: str) -> str:
    """A stable, obviously fake address derived from the display name (users have no e-mail)."""
    lowered = name.strip().lower()
    latin = "".join(_TRANSLIT.get(ch, ch) for ch in lowered)
    ascii_only = unicodedata.normalize("NFKD", latin).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")[:LOCAL_PART_MAX].rstrip("-")
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
            to_address=recipient_address(user),
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
