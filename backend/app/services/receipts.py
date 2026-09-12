"""The receipt e-mail: text built from the stored receipt columns, sent once per ride."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import CURRENCY
from app.models import Email, Ride, User
from app.services.mail import send_email


def receipt_dedup_key(ride: Ride) -> str:
    return f"ride:{ride.id}:receipt"


def format_duration(seconds: int) -> str:
    minutes, rest = divmod(seconds, 60)
    return f"{minutes} мин {rest:02d} с"


def receipt_subject(ride: Ride) -> str:
    return f"Чек за поездку на {ride.scooter.code}"


def receipt_body(ride: Ride) -> str:
    """Plain text; the amounts are the stored receipt, never recomputed."""
    assert ride.total_cost is not None, "only a finished ride has a receipt"
    started = ride.started_at.strftime("%d.%m.%Y %H:%M UTC")
    finished = ride.finished_at.strftime("%H:%M UTC") if ride.finished_at else "—"
    lines = [
        f"Здравствуйте, {ride.user.name}!",
        "",
        f"Поездка на самокате {ride.scooter.code} завершена ({started} — {finished}).",
        "",
        f"Ехали: {format_duration(ride.ride_seconds or 0)} — {ride.ride_cost} {CURRENCY}",
        f"Стояли: {format_duration(ride.pause_seconds or 0)} — {ride.pause_cost} {CURRENCY}",
        f"Итого: {ride.total_cost} {CURRENCY}",
        "",
        f"Тариф: {ride.ride_rate_per_minute} {CURRENCY}/мин езды, "
        f"{ride.pause_rate_per_minute} {CURRENCY}/мин паузы, оплата посекундная.",
        "",
        "Спасибо, что ездите с нами!",
    ]
    return "\n".join(lines)


async def send_receipt(session: AsyncSession, user: User, ride: Ride) -> Email | None:
    """Queue the receipt for a finished ride; None if it was already sent (dedup by ride)."""
    return await send_email(
        session, user, receipt_subject(ride), receipt_body(ride), receipt_dedup_key(ride)
    )
