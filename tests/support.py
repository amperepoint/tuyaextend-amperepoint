"""Helpers for testing integration modules without a Home Assistant install.

Modules such as ``source`` and ``coordinator`` use relative imports and import
Home Assistant packages at module level. ``load_integration_module`` loads
them under a synthetic package after registering minimal Home Assistant stubs,
so their pure logic can be exercised with the standard library only.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

INTEGRATION_DIR = (
    Path(__file__).resolve().parents[1] / "custom_components" / "tuyaextend_amperepoint"
)
_PACKAGE = "tuyaextend_amperepoint_under_test"


class HomeAssistantError(Exception):
    """Stub of homeassistant.exceptions.HomeAssistantError."""


class _Store:
    """In-memory stand-in that keeps what was saved, like the real Store."""

    def __init__(self, *args, **kwargs) -> None:
        self._data = None

    def __class_getitem__(cls, _item):
        return cls

    async def async_load(self):
        return self._data

    async def async_save(self, data) -> None:
        self._data = data

    def async_delay_save(self, *_args, **_kwargs) -> None:
        return None


@dataclass(frozen=True, kw_only=True)
class _EntityDescription:
    """Stub of homeassistant.helpers.entity.EntityDescription."""

    key: str
    translation_key: str | None = None
    icon: str | None = None
    device_class: str | None = None
    entity_category: str | None = None
    native_unit_of_measurement: str | None = None


class _CoordinatorEntity:
    def __init__(self, coordinator) -> None:
        self.coordinator = coordinator

    def __class_getitem__(cls, _item):
        return cls


class _DataUpdateCoordinator:
    def __init__(self, hass, *, logger=None, name=None, update_interval=None) -> None:
        self.hass = hass

    def __class_getitem__(cls, _item):
        return cls

    def async_add_listener(self, _listener):
        return lambda: None


def _module(name: str, **attrs) -> types.ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        sys.modules[name] = module
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def install_homeassistant_stubs() -> None:
    if getattr(sys.modules.get("homeassistant"), "_ap_test_stub", False):
        return

    ha = _module("homeassistant", _ap_test_stub=True)
    _module(
        "homeassistant.config_entries",
        ConfigEntry=object,
        SOURCE_INTEGRATION_DISCOVERY="integration_discovery",
    )
    _module("homeassistant.core", HomeAssistant=object, callback=lambda func: func)
    _module("homeassistant.exceptions", HomeAssistantError=HomeAssistantError)
    _module(
        "homeassistant.const",
        CONF_ICON="icon",
        CONF_NAME="name",
        EVENT_HOMEASSISTANT_STARTED="homeassistant_started",
        ATTR_UNIT_OF_MEASUREMENT="unit_of_measurement",
        PERCENTAGE="%",
        UnitOfElectricCurrent=types.SimpleNamespace(MILLIAMPERE="mA", AMPERE="A"),
        UnitOfElectricPotential=types.SimpleNamespace(MILLIVOLT="mV", VOLT="V"),
        UnitOfEnergy=types.SimpleNamespace(WATT_HOUR="Wh", KILO_WATT_HOUR="kWh"),
        UnitOfPower=types.SimpleNamespace(WATT="W", KILO_WATT="kW"),
        Platform=types.SimpleNamespace(
            SENSOR="sensor",
            BINARY_SENSOR="binary_sensor",
            NUMBER="number",
            SELECT="select",
            SWITCH="switch",
            TIME="time",
        ),
    )
    helpers = _module("homeassistant.helpers")
    helpers.device_registry = _module(
        "homeassistant.helpers.device_registry",
        async_get=lambda _hass: None,
        DeviceInfo=dict,
    )
    helpers.entity = _module(
        "homeassistant.helpers.entity", EntityDescription=_EntityDescription
    )
    helpers.entity_platform = _module(
        "homeassistant.helpers.entity_platform", AddEntitiesCallback=object
    )
    helpers.entity_registry = _module(
        "homeassistant.helpers.entity_registry", async_get=lambda _hass: None
    )
    helpers.storage = _module("homeassistant.helpers.storage", Store=_Store)
    helpers.dispatcher = _module(
        "homeassistant.helpers.dispatcher",
        async_dispatcher_connect=lambda *_args, **_kwargs: lambda: None,
    )
    helpers.event = _module(
        "homeassistant.helpers.event",
        async_track_time_change=lambda *_args, **_kwargs: lambda: None,
    )
    helpers.update_coordinator = _module(
        "homeassistant.helpers.update_coordinator",
        DataUpdateCoordinator=_DataUpdateCoordinator,
        CoordinatorEntity=_CoordinatorEntity,
    )
    ha.helpers = helpers

    util = _module("homeassistant.util")
    util.dt = _module(
        "homeassistant.util.dt",
        utcnow=lambda: datetime.now(timezone.utc),
        now=lambda: datetime.now(timezone.utc),
        DEFAULT_TIME_ZONE=timezone.utc,
    )
    ha.util = util

    components = _module("homeassistant.components")
    components.number = _module(
        "homeassistant.components.number",
        NumberEntity=object,
        NumberMode=types.SimpleNamespace(SLIDER="slider", BOX="box"),
    )
    components.frontend = _module(
        "homeassistant.components.frontend",
        async_register_built_in_panel=lambda *_args, **_kwargs: None,
        async_remove_panel=lambda *_args, **_kwargs: None,
    )
    lovelace = _module("homeassistant.components.lovelace")

    class _ConfigNotFound(Exception):
        pass

    class _LovelaceStorage:
        pass

    lovelace.dashboard = _module(
        "homeassistant.components.lovelace.dashboard",
        LovelaceStorage=_LovelaceStorage,
    )
    lovelace.const = _module(
        "homeassistant.components.lovelace.const",
        ConfigNotFound=_ConfigNotFound,
        CONF_TITLE="title",
        LOVELACE_DATA="lovelace",
        MODE_STORAGE="storage",
    )
    components.lovelace = lovelace
    tuya = _module("homeassistant.components.tuya")
    tuya.const = _module(
        "homeassistant.components.tuya.const",
        TUYA_HA_SIGNAL_UPDATE_ENTITY="tuya_entry_update",
    )
    components.tuya = tuya
    ha.components = components


def load_integration_module(name: str) -> types.ModuleType:
    install_homeassistant_stubs()
    package = sys.modules.get(_PACKAGE)
    if package is None:
        package = types.ModuleType(_PACKAGE)
        package.__path__ = [str(INTEGRATION_DIR)]
        sys.modules[_PACKAGE] = package

    full_name = f"{_PACKAGE}.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]

    spec = importlib.util.spec_from_file_location(
        full_name, INTEGRATION_DIR / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module
