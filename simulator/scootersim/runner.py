import logging
import random
import time
from collections.abc import Callable
from typing import Any, Protocol

import httpx

from scootersim.config import Config
from scootersim.fleet import Fleet

MAX_BACKOFF_SECONDS = 30.0


class TelemetryClient(Protocol):
    def fetch_scooters(self) -> list[dict[str, Any]]: ...

    def send_telemetry(self, code: str, lat: float, lon: float, battery: int) -> dict[str, Any]: ...


def run(
    config: Config,
    client: TelemetryClient,
    *,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    rng: random.Random | None = None,
    max_ticks: int | None = None,
    log: logging.Logger | None = None,
) -> None:
    """Main loop: load the fleet, then tick and report forever.

    Any backend failure is logged and retried with exponential backoff; the process never
    exits because of the backend being down. `max_ticks` exists for tests only.
    """
    log = log or logging.getLogger(__name__)
    rng = rng or random.Random()
    fleet: Fleet | None = None
    backoff = 1.0
    ticks = 0

    while max_ticks is None or ticks < max_ticks:
        ticks += 1
        try:
            now = clock()
            if fleet is None:
                payload = client.fetch_scooters()
                if not payload:
                    log.warning("Backend has no scooters yet, waiting")
                    sleep(config.interval_seconds)
                    continue
                fleet = Fleet.from_server(payload, config, rng, now)
                log.info(
                    "Fleet loaded: %d scooters, %d riding at a time",
                    len(payload),
                    config.active_scooters,
                )
            elif config.refresh_every_ticks > 0 and ticks % config.refresh_every_ticks == 0:
                # bookings and recharges happen outside the simulator: re-read the statuses
                fleet.refresh_statuses(client.fetch_scooters(), now)

            for scooter in fleet.tick(config.interval_seconds, now):
                state = client.send_telemetry(
                    scooter.code, scooter.lat, scooter.lon, scooter.battery_percent
                )
                fleet.apply_server_status(
                    scooter.code,
                    str(state.get("status", "")),
                    now,
                    paused=bool(state.get("paused", False)),
                )

            backoff = 1.0
            sleep(config.interval_seconds)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                log.warning("Backend does not know one of our scooters, reloading the fleet")
                fleet = None
            else:
                log.warning(
                    "Backend answered %s, retrying in %.0fs", exc.response.status_code, backoff
                )
            sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
        except (httpx.HTTPError, OSError) as exc:
            log.warning("Backend unavailable (%s), retrying in %.0fs", exc, backoff)
            sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
