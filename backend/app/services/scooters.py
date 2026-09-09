from app.models import ScooterStatus


def status_after_telemetry(current: ScooterStatus, battery: int, threshold: int) -> ScooterStatus:
    """Business rule for the battery level reported by telemetry.

    A battery strictly below the threshold always makes the scooter unavailable. A scooter that
    was unavailable and now reports a healthy battery becomes available again (there is no
    separate "reason" for unavailability yet). Reserved and riding scooters keep their status.
    """
    if battery < threshold:
        return ScooterStatus.UNAVAILABLE
    if current is ScooterStatus.UNAVAILABLE:
        return ScooterStatus.AVAILABLE
    return current
