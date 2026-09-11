"""Onboarding for the integration-owned LAN source (no Tuya Local required)."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.helpers import selector, device_registry as dr

from .const import DOMAIN, CONF_SOURCE_PHYSICAL_IDS
from .local_source import LOCAL_SOURCE, LOCAL_FIELDS, LocalConnectionError, read_local


def local_schema(current=None, *, options=False):
    current = current or {}
    fields = {}
    if not options:
        fields[vol.Required("name", default=current.get("name", "Wallbox PRIME - Local"))] = str
        fields[vol.Required("local_device_id", default=current.get("local_device_id", ""))] = str
    key_marker = vol.Optional("local_key") if options else vol.Required("local_key")
    fields[key_marker] = selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))
    fields[vol.Optional("local_host", default=current.get("local_host", ""))] = str
    fields[vol.Required("local_protocol", default=current.get("local_protocol", "3.5"))] = vol.In(["3.5", "3.4", "3.3"])
    return vol.Schema(fields)


def cloud_candidates(hass):
    """Read keys from an already authorized HA runtime; never call the cloud here."""
    result = {}
    for entry in hass.config_entries.async_entries("tuya"):
        manager = getattr(getattr(entry, "runtime_data", None), "manager", None)
        for device in getattr(manager, "device_map", {}).values():
            if not getattr(device, "local_key", None):
                continue
            name = str(getattr(device, "name", ""))
            if getattr(device, "category", "") != "qccdz" and not any(
                text in name.lower() for text in ("wallbox", "prime", "ev charger", "ampere")
            ):
                continue
            result[device.id] = {"name": name, "local_device_id": device.id,
                                 "local_key": device.local_key, "local_protocol": "3.5"}
    return result


def existing_physical_entry(hass, device_id):
    registry = dr.async_get(hass)
    for entry in hass.config_entries.async_entries(DOMAIN):
        config = {**entry.data, **entry.options}
        if config.get("local_device_id") == device_id or device_id in config.get(CONF_SOURCE_PHYSICAL_IDS, []):
            return entry
        source_id = config.get("source_device_id")
        source = registry.async_get(source_id) if registry and source_id else None
        if source and any(str(identifier[-1]) == device_id for identifier in source.identifiers):
            return entry
    return None


def local_entry_data(previous, credentials):
    # Do not leave cloud/entity command routes behind when migrating an entry.
    data = {k: v for k, v in previous.items()
            if not k.startswith("source_") and k not in LOCAL_FIELDS}
    connection = {key: credentials[key] for key in (*LOCAL_FIELDS, "local_family", "name")
                  if key in credentials}
    return {**data, **connection, "model": "prime", "source_integration": LOCAL_SOURCE,
            CONF_SOURCE_PHYSICAL_IDS: [credentials["local_device_id"]]}


class NativeLocalFlowMixin:
    async def async_step_local(self, user_input=None):
        self._local_candidates = cloud_candidates(self.hass)
        menu = ["local_manual"]
        if self._local_candidates:
            menu.insert(0, "local_import")
        return self.async_show_menu(step_id="local", menu_options=menu)

    async def async_step_local_import(self, user_input=None):
        candidates = cloud_candidates(self.hass)
        errors = {}
        if user_input is not None:
            selected = candidates.get(user_input["local_device_id"])
            if selected:
                credentials = {**selected, "local_host": user_input.get("local_host", "")}
                try:
                    self._local_pending = await self._async_probe_local(credentials)
                    return await self.async_step_local_confirm()
                except LocalConnectionError as err:
                    errors["base"] = str(err)
            else:
                errors["base"] = "device_not_found"
        if not candidates:
            return await self.async_step_local_manual()
        return self.async_show_form(step_id="local_import", errors=errors, data_schema=vol.Schema({
            vol.Required("local_device_id"): vol.In({k:v["name"] for k,v in candidates.items()}),
            vol.Optional("local_host", default=(user_input or {}).get("local_host", "")): str,
        }))

    async def _async_probe_local(self, credentials):
        result = await self.hass.async_add_executor_job(read_local, credentials)
        return {**credentials, "local_host": result["host"], "local_family": result["family"]}

    async def async_step_local_manual(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                self._local_pending = await self._async_probe_local(dict(user_input))
                return await self.async_step_local_confirm()
            except LocalConnectionError as err:
                errors["base"] = str(err)
        return self.async_show_form(step_id="local_manual", errors=errors,
                                    data_schema=local_schema(user_input))

    async def async_step_local_confirm(self, user_input=None):
        pending = self._local_pending
        existing = existing_physical_entry(self.hass, pending["local_device_id"])
        if user_input is not None:
            if existing:
                data = local_entry_data({**existing.data, **existing.options}, pending)
                self.hass.config_entries.async_update_entry(existing, data=data, options={})
                await self.hass.config_entries.async_reload(existing.entry_id)
                return self.async_abort(reason="local_migrated")
            await self.async_set_unique_id(f"{DOMAIN}_local_{pending['local_device_id']}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=pending["name"], data=local_entry_data({}, pending))
        return self.async_show_form(step_id="local_confirm", data_schema=vol.Schema({}),
                                   description_placeholders={"name": pending["name"],
                                    "host": pending["local_host"],
                                    "action": "migration" if existing else "new"})


class NativeLocalOptionsMixin:
    async def async_step_local_connection(self, user_input=None):
        current = {**self._config_entry.data, **self._config_entry.options}
        errors = {}
        if user_input is not None:
            credentials = {**current, **user_input}
            if not user_input.get("local_key"):
                credentials["local_key"] = current.get("local_key", "")
            try:
                result = await self.hass.async_add_executor_job(read_local, credentials)
                credentials["local_host"] = result["host"]
                credentials["local_family"] = result["family"]
                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=local_entry_data(current, credentials), options={})
                await self.hass.config_entries.async_reload(self._config_entry.entry_id)
                return self.async_abort(reason="local_updated")
            except LocalConnectionError as err:
                errors["base"] = str(err)
        return self.async_show_form(step_id="local_connection", errors=errors,
                                    data_schema=local_schema(current, options=True))
