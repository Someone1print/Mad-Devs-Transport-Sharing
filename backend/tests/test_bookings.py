import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models import Booking, BookingStatus, Scooter, ScooterStatus, User
from app.realtime.hub import hub


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)


async def make_user(session: AsyncSession, name: str = "Rider") -> User:
    user = User(name=name)
    session.add(user)
    await session.commit()
    return user


async def make_scooter(
    session: AsyncSession, code: str = "KG-B1", status: ScooterStatus = ScooterStatus.AVAILABLE
) -> Scooter:
    scooter = Scooter(code=code, lat=42.87, lon=74.59, battery=80, status=status)
    session.add(scooter)
    await session.commit()
    return scooter


def headers(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


async def test_booking_reserves_scooter_for_the_user(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await make_user(db_session)
    await make_scooter(db_session)
    listener = FakeSocket()
    hub.register(listener)  # type: ignore[arg-type]
    before = datetime.now(UTC)
    try:
        response = await client.post(
            "/api/bookings", json={"scooter_code": "KG-B1"}, headers=headers(user)
        )
    finally:
        hub.unregister(listener)  # type: ignore[arg-type]

    assert response.status_code == 201
    body = response.json()
    assert body["scooter_code"] == "KG-B1"
    assert body["user_id"] == user.id
    assert body["status"] == "active"
    expires_at = datetime.fromisoformat(body["expires_at"])
    ttl = timedelta(seconds=settings.booking_ttl_seconds)
    assert before + ttl - timedelta(seconds=5) <= expires_at <= before + ttl + timedelta(seconds=5)

    db_session.expire_all()
    scooter = await db_session.scalar(select(Scooter).where(Scooter.code == "KG-B1"))
    assert scooter is not None and scooter.status is ScooterStatus.RESERVED
    public = [m for m in listener.sent if m["type"] == "scooter.updated"]
    assert public and public[0]["scooter"]["status"] == "reserved"


@pytest.mark.parametrize("status", [ScooterStatus.RESERVED, ScooterStatus.UNAVAILABLE])
async def test_booking_rejects_scooter_that_is_not_available(
    client: AsyncClient, db_session: AsyncSession, status: ScooterStatus
) -> None:
    user = await make_user(db_session)
    await make_scooter(db_session, status=status)

    response = await client.post(
        "/api/bookings", json={"scooter_code": "KG-B1"}, headers=headers(user)
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "scooter_not_available"


async def test_user_cannot_hold_two_active_bookings(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await make_user(db_session)
    await make_scooter(db_session, code="KG-B1")
    await make_scooter(db_session, code="KG-B2")
    first = await client.post(
        "/api/bookings", json={"scooter_code": "KG-B1"}, headers=headers(user)
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/bookings", json={"scooter_code": "KG-B2"}, headers=headers(user)
    )

    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "user_has_active_booking"
    db_session.expire_all()
    other = await db_session.scalar(select(Scooter).where(Scooter.code == "KG-B2"))
    assert other is not None and other.status is ScooterStatus.AVAILABLE


async def test_booking_unknown_scooter_is_404_and_missing_user_is_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await make_user(db_session)
    await make_scooter(db_session)

    unknown = await client.post(
        "/api/bookings", json={"scooter_code": "KG-NOPE"}, headers=headers(user)
    )
    anonymous = await client.post("/api/bookings", json={"scooter_code": "KG-B1"})

    assert unknown.status_code == 404
    assert anonymous.status_code == 401


async def test_partial_unique_index_is_the_safety_net(db_session: AsyncSession) -> None:
    user_a = await make_user(db_session, "A")
    user_b = await make_user(db_session, "B")
    scooter = await make_scooter(db_session)
    user_a_id, user_b_id, scooter_id = user_a.id, user_b.id, scooter.id  # rollback expires objects
    expires_at = datetime.now(UTC) + timedelta(minutes=15)
    db_session.add(Booking(user_id=user_a_id, scooter_id=scooter_id, expires_at=expires_at))
    await db_session.commit()

    db_session.add(Booking(user_id=user_b_id, scooter_id=scooter_id, expires_at=expires_at))
    with pytest.raises(IntegrityError, match="uq_bookings_active_scooter"):
        await db_session.commit()
    await db_session.rollback()

    # a finished booking does not block a new one for the same scooter
    finished = await db_session.scalar(select(Booking).where(Booking.user_id == user_a_id))
    assert finished is not None
    finished.status = BookingStatus.CANCELLED
    db_session.add(Booking(user_id=user_b_id, scooter_id=scooter_id, expires_at=expires_at))
    await db_session.commit()


async def test_concurrent_bookings_only_one_wins(
    client: AsyncClient, committed_db: async_sessionmaker[AsyncSession]
) -> None:
    async with committed_db() as session:
        users = [await make_user(session, f"Rider {i}") for i in range(3)]
        await make_scooter(session)

    responses = await asyncio.gather(
        *(
            client.post("/api/bookings", json={"scooter_code": "KG-B1"}, headers=headers(user))
            for user in users
        )
    )

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [201, 409, 409]
    for response in responses:
        if response.status_code == 409:
            assert response.json()["detail"]["code"] == "scooter_not_available"
    async with committed_db() as session:
        active = await session.scalar(
            select(func.count()).select_from(Booking).where(Booking.status == BookingStatus.ACTIVE)
        )
        scooter = await session.scalar(select(Scooter).where(Scooter.code == "KG-B1"))
    assert active == 1
    assert scooter is not None and scooter.status is ScooterStatus.RESERVED


async def test_booking_waits_for_the_scooter_row_lock(
    client: AsyncClient, committed_db: async_sessionmaker[AsyncSession]
) -> None:
    async with committed_db() as session:
        user = await make_user(session)
        scooter = await make_scooter(session)

    async with committed_db() as locker:
        await locker.execute(
            text("SELECT id FROM scooters WHERE id = :id FOR UPDATE"), {"id": scooter.id}
        )
        request = asyncio.create_task(
            client.post("/api/bookings", json={"scooter_code": "KG-B1"}, headers=headers(user))
        )
        await asyncio.sleep(0.3)
        assert not request.done(), "the request must wait while another transaction holds the row"
        await locker.commit()  # releases the lock without changing the scooter

        response = await asyncio.wait_for(request, timeout=5)

    assert response.status_code == 201
