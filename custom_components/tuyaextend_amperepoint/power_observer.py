"""Passive, per-DP freshness evidence from the existing Tuya MQTT connection.

Device-wide online/update events cannot certify that DP9 was measured again.
No credentials, extra network requests, SDK patches or charger commands.
"""
from __future__ import annotations

import time
from typing import Any

from .energy import non_negative


class PowerReportObserver:
    def __init__(self, device_id: str) -> None:
        self.device_id = device_id
        self._mq = None
        self._report: tuple[Any, float] | None = None

    def attach(self, mq: Any) -> None:
        if mq is self._mq:
            return
        self.close()
        if (callable(getattr(mq, "add_message_listener", None))
                and callable(getattr(mq, "remove_message_listener", None))):
            mq.add_message_listener(self._on_message)
            self._mq = mq

    def close(self) -> None:
        if self._mq is not None:
            self._mq.remove_message_listener(self._on_message)
        self._mq = None
        self._report = None

    def _on_message(self, message: Any) -> None:
        # SDK callback runs on its MQTT thread. Publish a single immutable
        # tuple; don't touch HA state, schedule I/O, or retain full payloads.
        if not isinstance(message, dict) or message.get("protocol") != 4:
            return
        data = message.get("data")
        if not isinstance(data, dict) or data.get("devId") != self.device_id:
            return
        status = data.get("status")
        if not isinstance(status, list):
            return
        for item in status:
            # Only decoded Tuya codes: local-strategy dpId payloads can have
            # different encodings and cannot safely certify the cached value.
            if not isinstance(item, dict) or item.get("code") != "power_total":
                continue
            if non_negative(item.get("value")) is None:
                self._report = None
                continue
            received = time.time()
            stamp = non_negative(item.get("t", message.get("t")))
            if stamp is not None:
                if stamp > 1e11:  # Tuya commonly uses milliseconds
                    stamp /= 1000
                if stamp > received + 5:
                    self._report = None
                    continue
                received = min(received, stamp)
            old = self._report
            if old is None or received > old[1]:
                self._report = (item["value"], received)

    def reported_at(self, raw_value: Any) -> float | None:
        report = self._report
        return report[1] if report is not None and report[0] == raw_value else None
