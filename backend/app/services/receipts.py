"""The receipt e-mail: text built from the stored receipt columns, sent once per ride."""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import CURRENCY
from app.core.config import settings
from app.models import Email, Ride, User
from app.services.mail import send_email


def receipt_dedup_key(ride: Ride) -> str:
    return f"ride:{ride.id}:receipt"


def format_duration(seconds: int) -> str:
    minutes, rest = divmod(seconds, 60)
    return f"{minutes} мин {rest:02d} с"


def local_time(moment: datetime) -> datetime:
    """The stored UTC instant in the service's time zone, as the rider saw it on the map."""
    return moment.astimezone(ZoneInfo(settings.local_timezone))


def utc_offset_label(moment: datetime) -> str:
    """`UTC+6` for Bishkek: names the zone without assuming the reader knows its abbreviation."""
    offset = moment.utcoffset()
    assert offset is not None, "only aware datetimes reach the receipt"
    minutes = int(offset.total_seconds()) // 60
    sign = "+" if minutes >= 0 else "-"
    hours, rest = divmod(abs(minutes), 60)
    return f"UTC{sign}{hours}" + (f":{rest:02d}" if rest else "")


def receipt_subject(ride: Ride) -> str:
    return f"Чек за поездку на {ride.scooter.code}"


def receipt_body(ride: Ride) -> str:
    """Plain text; the amounts are the stored receipt, never recomputed."""
    assert ride.total_cost is not None, "only a finished ride has a receipt"
    assert ride.finished_at is not None, "only a finished ride has a receipt"
    started_local = local_time(ride.started_at)
    finished_local = local_time(ride.finished_at)
    started = started_local.strftime("%d.%m.%Y %H:%M")
    finished = finished_local.strftime("%H:%M")
    if finished_local.date() != started_local.date():
        finished = finished_local.strftime("%d.%m.%Y %H:%M")
    window = f"{started} — {finished} ({utc_offset_label(started_local)})"
    lines = [
        f"Здравствуйте, {ride.user.name}!",
        "",
        f"Поездка на самокате {ride.scooter.code} завершена ({window}).",
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
