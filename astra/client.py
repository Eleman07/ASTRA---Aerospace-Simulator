"""ASTRA Python HTTP Client.

Standard-library implementation: no extra dependencies.
"""

import json

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AstraClient:
    def __init__(
        self,
        base_url="http://127.0.0.1:8765",
        timeout_s=30,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

        if "github.io" in self.base_url.lower():
            raise ValueError(
                "GitHub Pages does not expose a Python HTTP API. "
                "Start the local server with python server.py."
            )

    def _request(self, endpoint, payload=None):
        method = "GET" if payload is None else "POST"

        body = (
            None
            if payload is None
            else json.dumps(
                payload,
                allow_nan=False
            ).encode("utf-8")
        )

        request = Request(
            self.base_url + endpoint,
            data=body,
            method=method,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        try:
            with urlopen(
                request, timeout=self.timeout_s
            ) as response:
                return json.load(response)

        except HTTPError as error:
            detail = error.read().decode(
                "utf-8", errors="replace"
            )
            raise RuntimeError(
                f"ASTRA API HTTP {error.code}: {detail}"
            ) from error

        except URLError as error:
            raise ConnectionError(
                f"Cannot connect to ASTRA at {self.base_url}. "
                "Start python server.py first."
            ) from error

    def status(self):
        return self._request("/api/v1/status")

    def models(self):
        return self._request("/api/v1/models")

    def state(self):
        return self._request("/api/v1/state")

    def reset(
        self,
        vehicle="space",
        scenario="mission",
        **kwargs
    ):
        payload = {
            "vehicle": vehicle,
            "scenario": scenario,
            **kwargs,
        }
        return self._request("/api/v1/reset", payload)

    def launch(self):
        return self._request("/api/v1/launch", {})

    def step(self, dt_s=0.1):
        return self._request(
            "/api/v1/step",
            {"dt_s": dt_s}
        )

    def command(self, **kwargs):
        return self._request(
            "/api/v1/command",
            kwargs
        )

    def stage(self):
        return self._request("/api/v1/stage", {})

    def engineering(self, analysis, **kwargs):
        return self._request(
            "/api/v1/engineering",
            {"analysis": analysis, **kwargs}
        )

    def engineering_solvers(self):
        return self._request("/api/v1/engineering")

    def vehicle_parts(self):
        return self._request("/api/v1/vehicle-parts")

    def inject_fault(self, **kwargs):
        return self._request("/api/v1/fault", kwargs)

    def clear_faults(self):
        return self._request("/api/v1/fault/clear", {})

    def close(self):
        pass
