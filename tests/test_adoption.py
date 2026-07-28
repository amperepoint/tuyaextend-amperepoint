from __future__ import annotations

import asyncio
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import load_integration_module  # noqa: E402

adoption = load_integration_module("adoption")
const = load_integration_module("const")


class _Candidate:
    def __init__(
        self,
        device_id: str,
        mapping: dict[str, str] | None = None,
        title: str = "",
    ) -> None:
        self.device_id = device_id
        self.mapping = mapping or {}
        self.title = title

    def as_config_data(self) -> dict[str, str]:
        return {const.CONF_SOURCE_DEVICE_ID: self.device_id, **self.mapping}


class _DeviceRegistry:
    def __init__(self, identifiers: dict[str, set[tuple[str, str]]]) -> None:
        self._identifiers = identifiers

    def async_get(self, device_id: str):
        identifiers = self._identifiers.get(device_id)
        if identifiers is None:
            return None
        return types.SimpleNamespace(identifiers=identifiers)


class _Flow:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict, dict]] = []
        self.result: dict = {"type": "create_entry"}
        self.error: Exception | None = None

    async def async_init(self, domain: str, *, context: dict, data: dict) -> dict:
        self.calls.append((domain, context, data))
        if self.error is not None:
            raise self.error
        return dict(self.result)


class _ConfigEntries:
    def __init__(
        self,
        configured_ids: tuple[str, ...],
        entry_data: tuple[dict, ...] = (),
    ) -> None:
        self.flow = _Flow()
        self._entries = [
            types.SimpleNamespace(
                data={const.CONF_SOURCE_DEVICE_ID: device_id}, options={}
            )
            for device_id in configured_ids
        ] + [
            types.SimpleNamespace(data=dict(data), options={})
            for data in entry_data
        ]

    def async_entries(self, domain: str):
        return list(self._entries) if domain == const.DOMAIN else []

    def async_update_entry(self, entry, *, options=None, data=None) -> None:
        if options is not None:
            entry.options = options
        if data is not None:
            entry.data = data


class _Bus:
    def __init__(self) -> None:
        self.listeners: list[tuple[str, object]] = []

    def async_listen_once(self, event: str, listener) -> None:
        self.listeners.append((event, listener))


class _Hass:
    def __init__(
        self,
        configured_ids: tuple[str, ...] = (),
        entry_data: tuple[dict, ...] = (),
        is_running: bool = True,
    ) -> None:
        self.data: dict = {}
        self.config_entries = _ConfigEntries(configured_ids, entry_data)
        self.tasks = []
        self.is_running = is_running
        self.bus = _Bus()

    def async_create_task(self, coroutine) -> None:
        self.tasks.append(coroutine)

    def close_tasks(self) -> None:
        for task in self.tasks:
            task.close()


class AutoAdoptionTests(unittest.TestCase):
    def test_schedules_only_unconfigured_devices_once(self) -> None:
        hass = _Hass(("configured",))
        candidates = [_Candidate("configured"), _Candidate("new")]
        with patch.object(adoption, "discover_sources", return_value=candidates):
            self.assertEqual(asyncio.run(adoption.async_start_auto_adoption(hass)), 1)
            self.assertEqual(asyncio.run(adoption.async_start_auto_adoption(hass)), 0)

        self.assertEqual(len(hass.config_entries.flow.calls), 1)
        self.assertTrue(hass.data[const.DOMAIN][adoption._AUTO_ADOPTION_STARTED])

    def test_empty_discovery_can_be_retried_later(self) -> None:
        hass = _Hass()
        with patch.object(adoption, "discover_sources", return_value=[]):
            self.assertEqual(asyncio.run(adoption.async_start_auto_adoption(hass)), 0)

        self.assertNotIn(
            adoption._AUTO_ADOPTION_STARTED, hass.data.get(const.DOMAIN, {})
        )
        with patch.object(
            adoption, "discover_sources", return_value=[_Candidate("new")]
        ):
            self.assertEqual(asyncio.run(adoption.async_start_auto_adoption(hass)), 1)


    def test_adoption_is_deferred_until_home_assistant_started(self) -> None:
        hass = _Hass(is_running=False)
        with patch.object(
            adoption, "discover_sources", return_value=[_Candidate("new")]
        ) as discover:
            self.assertEqual(asyncio.run(adoption.async_start_auto_adoption(hass)), 0)
            discover.assert_not_called()

        self.assertEqual(len(hass.tasks), 0)
        self.assertEqual(len(hass.bus.listeners), 1)
        self.assertTrue(hass.data[const.DOMAIN][adoption._AUTO_ADOPTION_STARTED])

        # The startup listener re-runs the scan once states are live.
        hass.is_running = True
        with patch.object(
            adoption, "discover_sources", return_value=[_Candidate("new")]
        ):
            hass.data[const.DOMAIN][adoption._AUTO_ADOPTION_STARTED] = False
            self.assertEqual(asyncio.run(adoption.async_start_auto_adoption(hass)), 1)

    def test_mapping_to_a_deleted_entity_is_replaced(self) -> None:
        """Re-pairing a charger must overwrite mappings left pointing at ghosts."""
        entry = types.SimpleNamespace(
            data={
                const.CONF_SOURCE_DEVICE_ID: "dev-1",
                "source_status": "sensor.gone_status",
                "source_power": "sensor.live_power",
            },
            options={},
        )
        hass = _Hass()
        hass.config_entries._entries = [entry]
        candidate = _Candidate(
            "dev-1",
            {
                "source_status": "sensor.new_status",
                "source_power": "sensor.new_power",
            },
        )

        class _EntityRegistry:
            def async_get(self, entity_id):
                # Only the power source survived the re-pairing.
                return object() if entity_id == "sensor.live_power" else None

        with patch.object(adoption.er, "async_get", return_value=_EntityRegistry()):
            adoption._async_backfill_mapping(
                hass, {"entry": entry}, candidate
            )

        # The dead mapping is replaced, the live one is left alone.
        self.assertEqual(entry.options["source_status"], "sensor.new_status")
        self.assertNotIn("source_power", entry.options)

    def test_deleted_charger_is_not_adopted_again(self) -> None:
        """A charger the user removed must stay removed across restarts."""
        hass = _Hass()
        candidate = _Candidate("dev-1", {"source_status": "sensor.a"}, "Charger")
        with patch.object(adoption, "discover_sources", return_value=[candidate]):
            self.assertEqual(
                asyncio.run(adoption.async_start_auto_adoption(hass)), 1
            )

        # The user deletes the entry, so no config entry references it; the
        # next restart re-runs discovery with the same candidate.
        hass.config_entries._entries.clear()
        hass.data[const.DOMAIN][adoption._AUTO_ADOPTION_STARTED] = False
        with patch.object(adoption, "discover_sources", return_value=[candidate]):
            self.assertEqual(
                asyncio.run(adoption.async_start_auto_adoption(hass)), 0
            )
        self.assertEqual(len(hass.config_entries.flow.calls), 1)

    def test_failed_flow_is_retried_after_restart(self) -> None:
        """A failed config flow must not permanently suppress the charger."""
        hass = _Hass()
        candidate = _Candidate("dev-1", {"source_status": "sensor.a"}, "Charger")
        hass.config_entries.flow.result = {
            "type": "abort",
            "reason": "simulated_failure",
        }
        with (
            patch.object(adoption, "discover_sources", return_value=[candidate]),
            patch.object(adoption._LOGGER, "warning"),
        ):
            self.assertEqual(
                asyncio.run(adoption.async_start_auto_adoption(hass)), 0
            )

        hass.data[const.DOMAIN][adoption._AUTO_ADOPTION_STARTED] = False
        hass.config_entries.flow.result = {"type": "create_entry"}
        with patch.object(adoption, "discover_sources", return_value=[candidate]):
            self.assertEqual(
                asyncio.run(adoption.async_start_auto_adoption(hass)), 1
            )
        self.assertEqual(len(hass.config_entries.flow.calls), 2)

    def test_flow_exception_does_not_break_setup_or_suppress_retry(self) -> None:
        hass = _Hass()
        candidate = _Candidate("dev-1", {"source_status": "sensor.a"}, "Charger")
        hass.config_entries.flow.error = RuntimeError("simulated failure")
        with (
            patch.object(adoption, "discover_sources", return_value=[candidate]),
            patch.object(adoption._LOGGER, "exception"),
        ):
            self.assertEqual(
                asyncio.run(adoption.async_start_auto_adoption(hass)), 0
            )

        hass.data[const.DOMAIN][adoption._AUTO_ADOPTION_STARTED] = False
        hass.config_entries.flow.error = None
        with patch.object(adoption, "discover_sources", return_value=[candidate]):
            self.assertEqual(
                asyncio.run(adoption.async_start_auto_adoption(hass)), 1
            )

    def test_physical_twin_backfills_the_existing_entry(self) -> None:
        # Cloud Tuya entry exists; the tuya-local twin of the same charger
        # shares the vendor id in its registry identifiers. Instead of a
        # duplicate entry, the existing one gains the missing telemetry
        # mapping.
        hass = _Hass(("cloud-dev",))
        registry = _DeviceRegistry(
            {
                "cloud-dev": {("tuya", "phys-1")},
                "local-dev": {("tuya_local", "phys-1")},
            }
        )
        candidates = [
            _Candidate(
                "local-dev",
                {
                    "source_status": "sensor.local_status",
                    "source_raw_dp": "sensor.local_status",
                },
            )
        ]
        with (
            patch.object(adoption, "discover_sources", return_value=candidates),
            patch.object(adoption.dr, "async_get", return_value=registry),
        ):
            self.assertEqual(asyncio.run(adoption.async_start_auto_adoption(hass)), 0)
        entry = hass.config_entries.async_entries(const.DOMAIN)[0]
        self.assertEqual(
            entry.options["source_raw_dp"], "sensor.local_status"
        )

    def test_duplicate_titles_do_not_merge_distinct_chargers(self) -> None:
        # User-visible names are not stable physical identifiers. Two chargers
        # called "wallbox_stock_1" must remain two separate entries.
        hass = _Hass()
        candidates = [
            _Candidate("cloud-dev", {"source_status": "sensor.a"}, "wallbox_stock_1"),
            _Candidate(
                "local-dev",
                {"source_status": "sensor.b", "source_raw_dp": "sensor.b"},
                "wallbox_stock_1",
            ),
        ]
        with patch.object(adoption, "discover_sources", return_value=candidates):
            self.assertEqual(asyncio.run(adoption.async_start_auto_adoption(hass)), 2)
        adopted_ids = {
            data[const.CONF_SOURCE_DEVICE_ID]
            for _, _, data in hass.config_entries.flow.calls
        }
        self.assertEqual(adopted_ids, {"cloud-dev", "local-dev"})

    def test_cloud_and_local_twins_produce_one_merged_entry(self) -> None:
        # The real registry shape: one physical charger, two registry devices
        # (cloud "tuya" and "tuya_local"), both carrying the vendor id.
        hass = _Hass()
        registry = _DeviceRegistry(
            {
                "cloud-dev": {("tuya", "bf929f09d0e09aa9c3dr2z")},
                "local-dev": {("tuya_local", "bf929f09d0e09aa9c3dr2z")},
            }
        )
        candidates = [
            _Candidate(
                "cloud-dev",
                {
                    "source_status": "sensor.cloud_status",
                    "source_charge_switch": "switch.cloud_charging",
                },
                "wallbox_stock_1",
            ),
            _Candidate(
                "local-dev",
                {
                    "source_status": "sensor.local_status",
                    "source_raw_dp": "sensor.local_status",
                    "source_current_limit": "sensor.local_current_limit",
                },
                "Ampere Point Wallbox Prime 22kW",
            ),
        ]
        with (
            patch.object(adoption, "discover_sources", return_value=candidates),
            patch.object(adoption.dr, "async_get", return_value=registry),
        ):
            self.assertEqual(asyncio.run(adoption.async_start_auto_adoption(hass)), 1)
        _, _, data = hass.config_entries.flow.calls[0]
        # The local source wins because it carries the most mappings...
        self.assertEqual(data[const.CONF_SOURCE_DEVICE_ID], "local-dev")
        self.assertEqual(data["source_raw_dp"], "sensor.local_status")
        # ...and inherits what only the cloud twin provides.
        self.assertEqual(data["source_charge_switch"], "switch.cloud_charging")

    def test_manually_configured_charger_is_not_adopted_again(self) -> None:
        # A manual entry stores no source_device_id, only mapped entity ids.
        hass = _Hass(
            entry_data=(
                {
                    "source_status": "sensor.prime_charging_status",
                    "name": "Wallbox Prime",
                },
            )
        )
        candidates = [
            _Candidate(
                "prime-device",
                {"source_status": "sensor.prime_charging_status"},
            ),
            _Candidate("other-device", {"source_status": "sensor.other_status"}),
        ]
        with patch.object(adoption, "discover_sources", return_value=candidates):
            self.assertEqual(asyncio.run(adoption.async_start_auto_adoption(hass)), 1)
        self.assertEqual(len(hass.config_entries.flow.calls), 1)


if __name__ == "__main__":
    unittest.main()


class RepairedAfterRepairingTests(unittest.TestCase):
    """Pairing a charger again must not orphan the entry that adopted it."""

    def test_entry_follows_the_charger_to_its_new_pairing(self) -> None:
        # Deleting a tuya-local pairing takes its device and entities with
        # it, so the entry loses every way of being recognised except the
        # vendor id remembered while the device was still there.
        entry_data = {
            const.CONF_SOURCE_DEVICE_ID: "old-dev",
            "source_status": "sensor.old_status",
        }
        hass = _Hass(entry_data=(entry_data,))
        entry = hass.config_entries._entries[0]

        first_registry = _DeviceRegistry({"old-dev": {("tuya_local", "vendor-1")}})
        with patch.object(adoption.dr, "async_get", return_value=first_registry):
            with patch.object(
                adoption,
                "discover_sources",
                return_value=[
                    _Candidate("old-dev", {"source_status": "sensor.old_status"})
                ],
            ):
                asyncio.run(adoption.async_start_auto_adoption(hass))

        self.assertEqual(
            entry.data[const.CONF_SOURCE_PHYSICAL_IDS],
            ["vendor-1"],
            "the vendor id has to be recorded while the device still exists",
        )

        # The charger is paired again: new device, new entities, old ones gone.
        second_registry = _DeviceRegistry({"new-dev": {("tuya_local", "vendor-1")}})

        class _EntityRegistry:
            def async_get(self, entity_id):
                return object() if entity_id == "sensor.new_status" else None

        hass.data[const.DOMAIN][adoption._AUTO_ADOPTION_STARTED] = False
        with patch.object(adoption.dr, "async_get", return_value=second_registry):
            with patch.object(
                adoption.er, "async_get", return_value=_EntityRegistry()
            ):
                with patch.object(
                    adoption,
                    "discover_sources",
                    return_value=[
                        _Candidate("new-dev", {"source_status": "sensor.new_status"})
                    ],
                ):
                    scheduled = asyncio.run(
                        adoption.async_start_auto_adoption(hass)
                    )

        self.assertEqual(scheduled, 0, "no duplicate entry may be created")
        self.assertEqual(entry.options["source_status"], "sensor.new_status")
        self.assertEqual(entry.data[const.CONF_SOURCE_DEVICE_ID], "new-dev")


class RememberAfterMatchTests(unittest.TestCase):
    """An entry matched through its entities must record the vendor ids too."""

    def test_entry_without_remembered_ids_records_them_on_match(self) -> None:
        # The state a charger is left in when it was re-paired before vendor
        # ids were ever stored: the entry works, because the new entities
        # happen to carry the old ids, but its source device is gone.
        entry_data = {
            const.CONF_SOURCE_DEVICE_ID: "deleted-dev",
            "source_status": "sensor.q22_status",
        }
        hass = _Hass(entry_data=(entry_data,))
        entry = hass.config_entries._entries[0]
        registry = _DeviceRegistry({"new-dev": {("tuya_local", "vendor-9")}})

        class _EntityRegistry:
            def async_get(self, entity_id):
                return object()

        with patch.object(adoption.dr, "async_get", return_value=registry):
            with patch.object(
                adoption.er, "async_get", return_value=_EntityRegistry()
            ):
                with patch.object(
                    adoption,
                    "discover_sources",
                    return_value=[
                        _Candidate("new-dev", {"source_status": "sensor.q22_status"})
                    ],
                ):
                    scheduled = asyncio.run(
                        adoption.async_start_auto_adoption(hass)
                    )

        self.assertEqual(scheduled, 0)
        self.assertEqual(entry.data[const.CONF_SOURCE_PHYSICAL_IDS], ["vendor-9"])
        self.assertEqual(entry.data[const.CONF_SOURCE_DEVICE_ID], "new-dev")
