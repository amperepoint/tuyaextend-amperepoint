"""Short-lived downloads for setup failures before a config entry exists."""
from __future__ import annotations

from datetime import timedelta
import json
import secrets
import time

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.auth import async_sign_path
from homeassistant.const import __version__ as HA_VERSION

from .const import DOMAIN
from .setup_diagnostics import build_report

DATA_KEY = f"{DOMAIN}_setup_reports"
TTL = 15 * 60
MAX_REPORTS = 16
URL = "/api/amperepoint/setup_diagnostics"


class ReportStore:
    """Memory only; bounded even when a setup flow is abandoned."""

    def __init__(self):
        self.reports: dict[str, tuple[float, str]] = {}

    def prune(self):
        now = time.monotonic()
        for key, (expires, _) in list(self.reports.items()):
            if expires <= now:
                self.reports.pop(key, None)

    def put(self, report):
        self.prune()
        while len(self.reports) >= MAX_REPORTS:
            self.reports.pop(next(iter(self.reports)))
        token = secrets.token_urlsafe(24)
        self.reports[token] = (time.monotonic() + TTL, json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return token

    def get(self, token):
        self.prune()
        item = self.reports.get(token)
        return item[1] if item else None


class SetupDiagnosticView(HomeAssistantView):
    url = URL + "/{report_id}"
    name = "api:amperepoint:setup_diagnostics"
    requires_auth = True

    def __init__(self, store):
        self.store = store

    async def get(self, request, report_id):
        body = self.store.get(report_id)
        if body is None:
            raise web.HTTPNotFound()
        return web.Response(
            text=body, content_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="amperepoint-setup-diagnostics.json"',
                     "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                     "Referrer-Policy": "no-referrer"},
        )


def create_download(hass, error, config, source):
    store = hass.data.get(DATA_KEY)
    if store is None:
        store = hass.data[DATA_KEY] = ReportStore()
        hass.http.register_view(SetupDiagnosticView(store))
    token = store.put(build_report(error, config, source, HA_VERSION))
    # Evict without waiting for another request, including abandoned flows.
    hass.loop.call_later(TTL, store.reports.pop, token, None)
    return async_sign_path(hass, f"{URL}/{token}", timedelta(seconds=TTL))
