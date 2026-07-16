from __future__ import annotations

import asyncio
import json
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import HomeAssistantError, load_integration_module  # noqa: E402

source = load_integration_module("source")


def _definition(type_: str, **values) -> types.SimpleNamespace:
    return types.SimpleNamespace(type=type_, values=json.dumps(values))


class _Manager:
    def __init__(self) -> None:
        self.commands: list[tuple[str, list[dict]]] = []

    def send_commands(self, device_id: str, commands: list[dict]) -> None:
        self.commands.append((device_id, commands))


class _Hass:
    async def async_add_executor_job(self, func, *args):
        return func(*args)


def _make_source(functions: dict, status: dict | None = None):
    manager = _Manager()
    device = types.SimpleNamespace(
        id="device-1",
        online=True,
        status=status or {},
        function=functions,
        status_range={},
    )
    return (
        source.NativeTuyaSource(hass=_Hass(), manager=manager, device=device),
        manager,
    )


def _send(native, code, value):
    asyncio.run(native.async_send(code, value))


class NativeTuyaSendTests(unittest.TestCase):
    def _sent_value(self, manager: _Manager):
        self.assertEqual(len(manager.commands), 1)
        device_id, commands = manager.commands[0]
        self.assertEqual(device_id, "device-1")
        self.assertEqual(len(commands), 1)
        return commands[0]

    def test_scale_zero_float_is_sent_as_integer(self) -> None:
        native, manager = _make_source(
            {"charge_cur_set": _definition("Integer", min=6, max=32, scale=0, step=1)}
        )
        _send(native, "charge_cur_set", 11.0)
        command = self._sent_value(manager)
        self.assertEqual(command, {"code": "charge_cur_set", "value": 11})
        self.assertIsInstance(command["value"], int)

    def test_scale_one_multiplies_before_sending(self) -> None:
        native, manager = _make_source(
            {"charge_cur_set": _definition("Integer", min=60, max=320, scale=1)}
        )
        _send(native, "charge_cur_set", 11.0)
        self.assertEqual(self._sent_value(manager)["value"], 110)

    def test_value_below_raw_minimum_is_clamped(self) -> None:
        native, manager = _make_source(
            {"charge_cur_set": _definition("Integer", min=6, max=32, scale=0)}
        )
        _send(native, "charge_cur_set", 3)
        self.assertEqual(self._sent_value(manager)["value"], 6)

    def test_value_above_raw_maximum_is_clamped(self) -> None:
        native, manager = _make_source(
            {"charge_cur_set": _definition("Integer", min=6, max=32, scale=0)}
        )
        _send(native, "charge_cur_set", 40.0)
        self.assertEqual(self._sent_value(manager)["value"], 32)

    def test_in_range_integer_is_unchanged(self) -> None:
        native, manager = _make_source(
            {"charge_cur_set": _definition("Integer", min=6, max=32, scale=0)}
        )
        _send(native, "charge_cur_set", 16)
        self.assertEqual(self._sent_value(manager)["value"], 16)

    def test_boolean_passes_through(self) -> None:
        native, manager = _make_source({"switch": _definition("Boolean")})
        _send(native, "switch", True)
        self.assertIs(self._sent_value(manager)["value"], True)

    def test_enum_string_passes_through(self) -> None:
        native, manager = _make_source(
            {"work_mode": _definition("Enum", range=["charge_now", "charge_pct"])}
        )
        _send(native, "work_mode", "charge_now")
        self.assertEqual(self._sent_value(manager)["value"], "charge_now")

    def test_read_only_code_raises(self) -> None:
        native, manager = _make_source({}, status={"power_total": 1200})
        with self.assertRaises(HomeAssistantError):
            _send(native, "power_total", 5)
        self.assertEqual(manager.commands, [])


if __name__ == "__main__":
    unittest.main()
