"""Best-effort, once-per-version activation counts; never part of setup readiness."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import logging
import time
from typing import Any
from uuid import UUID, uuid4

from .const import DOMAIN, VERSION

CONF_USAGE_REPORTING = "usage_reporting"
ENDPOINT = "https://tools.emaxima.pl/amperepoint/api/ha-usage/activation"
DATA_KEY = f"{DOMAIN}.usage_reporting"
ENABLED_KEY = f"{DATA_KEY}.enabled"
REQUEST_TIMEOUT = 3
START_DELAY = 60
RETRY_DELAYS = (3600, 21600)
_LOGGER = logging.getLogger(__name__)


class UsageReporter:
    """Persist an installation ID and acknowledge each version only after delivery."""

    def __init__(
        self,
        store: Any,
        send: Callable[[str, str], Awaitable[bool]],
        *,
        version: str = VERSION,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.store = store
        self.send = send
        self.version = version
        self.sleep = sleep

    async def run(self) -> None:
        """Contain storage/network failures, but allow HA to cancel on shutdown."""
        try:
            await self.sleep(START_DELAY)
            state = await self.store.async_load()
            if state is None:
                state = {"installation_id": uuid4().hex, "reported_versions": [], "retry_after": 0}
                # Do not send an identity that cannot survive a restart.
                await self.store.async_save(state)
            if not isinstance(state, dict):
                raise ValueError("Invalid usage state")
            installation_id = UUID(state["installation_id"]).hex
            versions = state["reported_versions"]
            if not isinstance(versions, list) or not all(isinstance(v, str) for v in versions):
                raise ValueError("Invalid usage versions")
            if self.version in versions:
                return
            cooldown = max(0, min(float(state.get("retry_after", 0)) - time.time(), 86400))
            if cooldown:
                await self.sleep(cooldown)

            for attempt in range(len(RETRY_DELAYS) + 1):
                try:
                    async with asyncio.timeout(REQUEST_TIMEOUT):
                        accepted = await self.send(installation_id, self.version)
                except Exception:
                    # Do not log the URL, installation ID, IP, or a traceback.
                    accepted = False
                if accepted:
                    state = {**state, "reported_versions": [*versions, self.version], "retry_after": 0}
                    await self.store.async_save(state)
                    return
                delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 86400
                state = {**state, "retry_after": time.time() + delay}
                await self.store.async_save(state)
                if attempt < len(RETRY_DELAYS):
                    await self.sleep(delay)
            _LOGGER.debug("Optional usage report deferred; integration operation is unaffected")
        except Exception:
            _LOGGER.debug("Optional usage reporting unavailable; integration operation is unaffected")


async def _send(installation_id: str, version: str) -> bool:
    # HA already provides aiohttp. No additional dependency/download is needed.
    import aiohttp

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        cookie_jar=aiohttp.DummyCookieJar(),
    ) as session:
        async with session.get(
            ENDPOINT,
            params={"installation": installation_id, "version": version},
            headers={"Cache-Control": "no-store", "User-Agent": "AmperePoint-Usage/1"},
            allow_redirects=False,
        ) as response:
            # A login page, proxy response or redirect must not acknowledge delivery.
            return response.status == 204 and response.headers.get("X-AmperePoint-Usage") == "accepted"


def register_entry(hass: Any, entry: Any) -> None:
    """Schedule after successful entry setup, without awaiting disk or network I/O."""
    try:
        if not hass.data.get(ENABLED_KEY, True):
            return
        manager = hass.data.get(DATA_KEY)
        if manager is None:
            manager = _Manager(hass)
            hass.data[DATA_KEY] = manager
        manager.entries.add(entry.entry_id)
        entry.async_on_unload(lambda: manager.remove(entry.entry_id))
        manager.start()
    except Exception:
        _LOGGER.debug("Optional usage reporting could not be scheduled")


class _Manager:
    def __init__(self, hass: Any) -> None:
        self.hass = hass
        self.entries: set[str] = set()
        self.task: asyncio.Task | None = None
        self.unsubscribe: Callable | None = None

    def start(self) -> None:
        if self.task is not None or self.unsubscribe is not None:
            return
        from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
        from homeassistant.core import CoreState, callback

        @callback
        def started(_event: Any = None) -> None:
            self.unsubscribe = None
            # Background tasks are excluded from HA startup readiness and cancelled
            # by HA at shutdown. Store initialization also stays in this task.
            self.task = self.hass.async_create_background_task(self.run(), "AmperePoint usage report")

        # HA's is_running also includes the starting state.
        if self.hass.state is CoreState.running:
            started()
        else:
            self.unsubscribe = self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, started)

    async def run(self) -> None:
        try:
            from homeassistant.helpers.storage import Store

            await UsageReporter(Store(self.hass, 1, DATA_KEY), _send).run()
        except Exception:
            _LOGGER.debug("Optional usage reporting unavailable")

    def remove(self, entry_id: str) -> None:
        self.entries.discard(entry_id)
        if self.entries:
            return
        if self.unsubscribe is not None:
            self.unsubscribe()
        if self.task is not None:
            self.task.cancel()
        self.hass.data.pop(DATA_KEY, None)
