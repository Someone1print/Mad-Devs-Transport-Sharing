"""The mailbox stub: e-mails are rows, and one dedup key never yields two of them."""

import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Email, User
from app.services.mail import address_for, send_email
from tests.test_bookings import make_user


async def test_send_email_stores_the_message_for_the_user(db_session: AsyncSession) -> None:
    user = await make_user(db_session, "Айбек Жумалиев")
    user_id = user.id

    email = await send_email(
        db_session, user, subject="Чек", body="Итого 5.00 KGS", dedup_key="ride:1:receipt"
    )

    assert email is not None
    assert email.user_id == user_id
    assert email.to_address == "aybek-zhumaliev@example.invalid"
    assert email.subject == "Чек" and email.body == "Итого 5.00 KGS"
    assert email.dedup_key == "ride:1:receipt"
    assert email.created_at is not None


def test_address_local_part_is_bounded_for_any_64_char_name() -> None:
    # «щ» is the widest expansion (4 letters): 64 of them would be 256 characters unbounded
    address = address_for("щ" * 64)

    local_part, domain = address.split("@")
    assert domain == "example.invalid"
    assert len(local_part) == 64
    assert len(address) <= 255  # the column
    assert address_for("a-" * 40).endswith("@example.invalid")  # a cut never ends in a dash
    assert not address_for("a-" * 40).split("@")[0].endswith("-")


async def test_second_send_with_the_same_key_creates_nothing(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    first = await send_email(db_session, user, "A", "first", dedup_key="k")

    second = await send_email(db_session, user, "A", "second text", dedup_key="k")

    assert first is not None and second is None
    stored = (await db_session.scalars(select(Email))).all()
    assert [e.body for e in stored] == ["first"]


async def test_different_keys_are_different_emails(db_session: AsyncSession) -> None:
    user = await make_user(db_session)

    await send_email(db_session, user, "A", "one", dedup_key="ride:1:receipt")
    await send_email(db_session, user, "A", "two", dedup_key="ride:2:receipt")

    assert await db_session.scalar(select(func.count()).select_from(Email)) == 2


async def test_concurrent_sends_with_one_key_store_exactly_one(
    committed_db: async_sessionmaker[AsyncSession],
) -> None:
    async with committed_db() as session:
        user_id = (await make_user(session)).id

    async def attempt(n: int) -> bool:
        # each attempt is its own transaction and commits, like a real request would
        async with committed_db() as session:
            user = await session.get(User, user_id)
            assert user is not None
            email = await send_email(session, user, "A", f"copy {n}", dedup_key="race")
            await session.commit()
            return email is not None

    results = await asyncio.gather(*(attempt(n) for n in range(5)))

    assert sum(results) == 1
    async with committed_db() as session:
        assert await session.scalar(select(func.count()).select_from(Email)) == 1


def test_address_for_transliterates_and_slugs_the_name() -> None:
    assert address_for("Дана") == "dana@example.invalid"
    assert address_for("  John  Smith ") == "john-smith@example.invalid"
    assert address_for("Ырыс-Бек Ж.") == "yrys-bek-zh@example.invalid"
    assert address_for("!!!") == "user@example.invalid"
