import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Booking, BookingStatus, Scooter, ScooterStatus
from app.realtime.hub import ScooterHub
from app.services.booking_sweeper import run_booking_sweeper, sweep_bookings
from tests.test_bookings import make_scooter, make_user

WARN_BEFORE = timedelta(seconds=180)


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send_json(self, message: dict[str, Any]) -> None:
        self.sent.append(message)

    def of_type(self, event_type: str) -> list[dict[str, Any]]:
        return [m for m in self.sent if m["type"] == event_type]


def make_hub(user_id: int) -> tuple[ScooterHub, FakeSocket, FakeSocket]:
    hub = ScooterHub()
    owner, bystander = FakeSocket(), FakeSocket()
    hub.register(owner)  # type: ignore[arg-type]
    hub.register(bystander)  # type: ignore[arg-type]
    hub.identify(owner, user_id)  # type: ignore[arg-type]
    return hub, owner, bystander


async def make_booking(
    session: AsyncSession,
    user_id: int,
    scooter: Scooter,
    expires_at: datetime,
    scooter_status: ScooterStatus = ScooterStatus.RESERVED,
    created_at: datetime | None = None,
) -> Booking:
    scooter.status = scooter_status
    booking = Booking(user_id=user_id, scooter_id=scooter.id, expires_at=expires_at)
    if created_at is not None:
        booking.created_at = created_at
    session.add(booking)
    await session.commit()
    return booking


async def test_sweep_expires_overdue_bookings_and_frees_scooters(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    scooter = await make_scooter(db_session)
    now = datetime.now(UTC)
    booking = await make_booking(
        db_session, user.id, scooter, expires_at=now - timedelta(seconds=1)
    )
    hub, owner, bystander = make_hub(user.id)

    booking_id, scooter_id = booking.id, scooter.id  # expire_all() below drops loaded state

    result = await sweep_bookings(
        db_session, hub, now=now, warn_before=WARN_BEFORE, low_battery_threshold=15
    )

    assert [b.id for b in result.expired] == [booking_id]
    db_session.expire_all()
    stored = await db_session.get(Booking, booking_id)
    assert stored is not None and stored.status is BookingStatus.EXPIRED
    assert stored.ended_at == now
    freed = await db_session.scalar(select(Scooter).where(Scooter.id == scooter_id))
    assert freed is not None and freed.status is ScooterStatus.AVAILABLE
    assert owner.of_type("booking.expired")[0]["booking"]["id"] == booking_id
    assert bystander.of_type("scooter.updated")[0]["scooter"]["status"] == "available"
    assert bystander.of_type("booking.expired") == []


async def test_sweep_keeps_an_unavailable_scooter_unavailable(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    scooter = await make_scooter(db_session)
    now = datetime.now(UTC)
    await make_booking(
        db_session,
        user.id,
        scooter,
        expires_at=now - timedelta(seconds=1),
        scooter_status=ScooterStatus.UNAVAILABLE,
    )
    hub, _, _ = make_hub(user.id)
    scooter_id = scooter.id

    await sweep_bookings(
        db_session, hub, now=now, warn_before=WARN_BEFORE, low_battery_threshold=15
    )

    db_session.expire_all()
    stored = await db_session.scalar(select(Scooter).where(Scooter.id == scooter_id))
    assert stored is not None and stored.status is ScooterStatus.UNAVAILABLE


async def test_sweep_warns_exactly_once_before_expiry(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    scooter = await make_scooter(db_session)
    now = datetime.now(UTC)
    booking = await make_booking(
        db_session,
        user.id,
        scooter,
        expires_at=now + timedelta(seconds=100),
        created_at=now - timedelta(seconds=800),
    )
    hub, owner, bystander = make_hub(user.id)
    booking_id = booking.id

    first = await sweep_bookings(
        db_session, hub, now=now, warn_before=WARN_BEFORE, low_battery_threshold=15
    )
    second = await sweep_bookings(
        db_session,
        hub,
        now=now + timedelta(seconds=10),
        warn_before=WARN_BEFORE,
        low_battery_threshold=15,
    )

    assert [b.id for b in first.warned] == [booking_id]
    assert second.warned == [] and second.expired == []
    warnings = owner.of_type("booking.expiring")
    assert len(warnings) == 1
    assert warnings[0]["booking"]["id"] == booking_id
    assert warnings[0]["seconds_left"] == 100
    assert bystander.of_type("booking.expiring") == []
    db_session.expire_all()
    stored = await db_session.get(Booking, booking_id)
    assert stored is not None and stored.warned_at == now and stored.status is BookingStatus.ACTIVE


async def test_short_booking_is_warned_at_half_its_length_not_immediately(
    db_session: AsyncSession,
) -> None:
    """A 60 s booking must not trigger the "3 minutes left" warning the moment it is created."""
    user = await make_user(db_session)
    scooter = await make_scooter(db_session)
    now = datetime.now(UTC)
    booking = await make_booking(
        db_session, user.id, scooter, expires_at=now + timedelta(seconds=60), created_at=now
    )
    hub, owner, _ = make_hub(user.id)
    booking_id = booking.id

    at_creation = await sweep_bookings(
        db_session, hub, now=now, warn_before=WARN_BEFORE, low_battery_threshold=15
    )
    just_before_half = await sweep_bookings(
        db_session,
        hub,
        now=now + timedelta(seconds=29),
        warn_before=WARN_BEFORE,
        low_battery_threshold=15,
    )
    past_half = await sweep_bookings(
        db_session,
        hub,
        now=now + timedelta(seconds=31),
        warn_before=WARN_BEFORE,
        low_battery_threshold=15,
    )

    assert at_creation.warned == [] and just_before_half.warned == []
    assert [b.id for b in past_half.warned] == [booking_id]
    assert owner.of_type("booking.expiring")[0]["seconds_left"] == 29


async def test_sweep_does_not_warn_too_early(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    scooter = await make_scooter(db_session)
    now = datetime.now(UTC)
    await make_booking(db_session, user.id, scooter, expires_at=now + timedelta(seconds=400))
    hub, owner, _ = make_hub(user.id)

    result = await sweep_bookings(
        db_session, hub, now=now, warn_before=WARN_BEFORE, low_battery_threshold=15
    )

    assert result.warned == [] and result.expired == []
    assert owner.sent == []


async def test_sweep_catches_up_after_a_restart(db_session: AsyncSession) -> None:
    """Nothing lives in memory: one pass handles everything missed while the backend was down."""
    user_a = await make_user(db_session, "A")
    user_b = await make_user(db_session, "B")
    overdue_scooter = await make_scooter(db_session, code="KG-OVERDUE")
    soon_scooter = await make_scooter(db_session, code="KG-SOON")
    now = datetime.now(UTC)
    overdue = await make_booking(
        db_session, user_a.id, overdue_scooter, expires_at=now - timedelta(minutes=5)
    )
    soon = await make_booking(
        db_session,
        user_b.id,
        soon_scooter,
        expires_at=now + timedelta(seconds=60),
        created_at=now - timedelta(seconds=840),
    )
    hub = ScooterHub()

    result = await sweep_bookings(
        db_session, hub, now=now, warn_before=WARN_BEFORE, low_battery_threshold=15
    )

    assert [b.id for b in result.expired] == [overdue.id]
    assert [b.id for b in result.warned] == [soon.id]


async def test_sweeper_loop_runs_until_stopped(
    committed_db: async_sessionmaker[AsyncSession],
) -> None:
    async with committed_db() as session:
        user = await make_user(session)
        scooter = await make_scooter(session)
        booking = await make_booking(
            session, user.id, scooter, expires_at=datetime.now(UTC) - timedelta(seconds=1)
        )
    stop = asyncio.Event()
    task = asyncio.create_task(
        run_booking_sweeper(
            committed_db,
            ScooterHub(),
            interval=0.05,
            warn_before=WARN_BEFORE,
            low_battery_threshold=15,
            stop=stop,
        )
    )

    try:
        for _ in range(40):
            await asyncio.sleep(0.05)
            async with committed_db() as session:
                stored = await session.get(Booking, booking.id)
            if stored is not None and stored.status is BookingStatus.EXPIRED:
                break
        else:
            raise AssertionError("the sweeper loop did not expire the booking in time")
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=2)
