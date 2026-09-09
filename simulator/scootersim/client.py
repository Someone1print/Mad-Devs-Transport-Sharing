from typing import Any

import httpx


class BackendClient:
    """Thin HTTP client for the scooter API; raises httpx errors for the runner to handle."""

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self._http = httpx.Client(base_url=base_url, timeout=timeout)

    def fetch_scooters(self) -> list[dict[str, Any]]:
        response = self._http.get("/api/scooters")
        response.raise_for_status()
        return response.json()

    def send_telemetry(self, code: str, lat: float, lon: float, battery: int) -> dict[str, Any]:
        response = self._http.post(
            "/api/telemetry", json={"code": code, "lat": lat, "lon": lon, "battery": battery}
        )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._http.close()
