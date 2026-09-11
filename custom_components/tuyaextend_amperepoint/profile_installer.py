"""Install the bundled, read-only Prime profile through the HA setup flow."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import tempfile
from typing import Any

import voluptuous as vol

_LOGGER = logging.getLogger(__name__)
PROFILE_NAME = "amperepoint_prime_22kw_evcharger.yaml"
BUNDLED_PROFILE = Path(__file__).parent / "profiles" / PROFILE_NAME
SPLIT_PROFILE_NAME = "amperepoint_prime_split_evcharger.yaml"


def install_prime_profile(config_dir: str, profile_name: str = PROFILE_NAME) -> str:
    """Publish a complete profile without replacing user or upstream files.

    Runs in an executor. A hard link makes publication atomic and exclusive:
    concurrent installers cannot overwrite each other or expose a partial YAML.
    """
    if profile_name not in (PROFILE_NAME, SPLIT_PROFILE_NAME):
        raise ValueError("Unknown bundled PRIME profile")
    root = Path(config_dir).resolve()
    integration = root / "custom_components" / "tuya_local"
    devices = integration / "devices"
    if not (integration / "manifest.json").is_file() or not devices.is_dir():
        return "prime_tuya_local_missing"
    if devices.resolve() != devices:
        return "prime_profile_path_error"
    target = devices / profile_name
    content = (BUNDLED_PROFILE.parent / profile_name).read_bytes()

    def existing_result() -> str:
        if target.is_symlink() or not target.is_file():
            return "prime_profile_conflict"
        existing = target.read_bytes().replace(b"\r\n", b"\n")
        if existing == content.replace(b"\r\n", b"\n"):
            return "prime_profile_installed"
        return "prime_profile_conflict"

    if target.exists() or target.is_symlink():
        return existing_result()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=devices, suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            return existing_result()
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return "prime_profile_installed"


def install_prime_profiles(config_dir: str) -> str:
    """Install each generation independently, preserving all conflicting files.

    A conflict in one generation must not prevent the other from being installed.
    Report the conflict so the user can review the preserved file; retry is safe.
    """
    results = [install_prime_profile(config_dir, name)
               for name in (PROFILE_NAME, SPLIT_PROFILE_NAME)]
    return next((result for result in results if result != "prime_profile_installed"),
                "prime_profile_installed")


class PrimeProfileFlowMixin:
    """Shared opt-in installer for the add-integration and options menus."""

    async def async_step_prime_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        errors = {}
        if user_input is not None:
            try:
                result = await self.hass.async_add_executor_job(
                    install_prime_profiles, self.hass.config.path()
                )
            except OSError:
                _LOGGER.exception("Unable to install the bundled Wallbox Prime profile")
                result = "prime_profile_write_error"
            if result == "prime_profile_installed":
                # No AmperePoint entry exists until an actual charger is selected.
                return self.async_abort(reason=result)
            errors["base"] = result
        return self.async_show_form(
            step_id="prime_profile", data_schema=vol.Schema({}), errors=errors
        )
