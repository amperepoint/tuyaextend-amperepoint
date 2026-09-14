"""Acknowledged checkpoints for a meter consumed by HA statistics."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from homeassistant.core import CoreState
from homeassistant.helpers.storage import Store


class EnergySaveError(Exception):
    """The meter checkpoint could not be confirmed on disk."""


class EnergyStore(Store[dict[str, Any]]):
    """Use HA's atomic storage, but never mistake a logged error for success.

    Store.async_save can swallow write errors or defer writes during shutdown.
    Verify the actual file, not async_load (which can return pending/cache data).
    No delayed saves are used for this store.
    """

    async def async_save(self, data: dict[str, Any]) -> None:
        task = asyncio.create_task(self._async_save_and_verify(data))
        cancelled = False
        # A cancelled refresh must not leave an executor write running behind
        # a reloaded entry. Drain even repeated cancellation before releasing
        # the coordinator's refresh/unload lock.
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                cancelled = True
        task.result()
        if cancelled:
            raise asyncio.CancelledError

    async def _async_save_and_verify(self, data: dict[str, Any]) -> None:
        if self.hass.state is CoreState.stopping:
            raise EnergySaveError("HA is stopping; energy checkpoint not published")
        await super().async_save(data)
        try:
            saved = await self.hass.async_add_executor_job(self._read_checkpoint)
        except (OSError, ValueError) as err:
            raise EnergySaveError("Cannot read back energy checkpoint") from err
        if not isinstance(saved, dict) or saved.get("data") != data:
            raise EnergySaveError("Energy checkpoint was not written; keeping previous published value")

    def _read_checkpoint(self) -> Any:
        return json.loads(Path(self.path).read_text(encoding="utf-8"))
