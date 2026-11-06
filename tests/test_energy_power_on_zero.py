"""A lifetime counter that reads 0 after every power-on (Q11, 2026-11).

The charger reports its lifetime counter as 0 right after a power-on and the
stored value only with the next charge, once at an older level. Before the fix
the meter added the whole counter in one step after each power-on: +57.5 and
+108.2 kWh in a week in which the car took about 113 kWh.
"""
from __future__ import annotations

import bisect
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import load_integration_module

energy = load_integration_module("energy")

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "q11_power_on_zero_log.json"


class PowerOnZeroLogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.log = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def replay(self):
        """Poll the held readings every 15 s, as the coordinator does."""
        counter, power = self.log["counter_kwh"], self.log["power_kw"]
        counter_times = [t for t, _ in counter]
        power_times = [t for t, _ in power]
        meter = energy.ChargingEnergy()
        steps = []
        at_reference = None
        t = counter[0][0]
        while t <= self.log["end_s"]:
            value = counter[bisect.bisect_right(counter_times, t) - 1][1]
            j = bisect.bisect_right(power_times, t) - 1
            sample_power = (energy.PowerSample("q:power", power[j][1], float(power[j][0]))
                            if j >= 0 else None)
            before = meter.total
            meter.update(energy.EnergySample("q:dp1", "device_counter", value, 0.01),
                         float(t), self.log["max_power_kw"], power=sample_power)
            steps.append(meter.total - before)
            if at_reference is None and t >= self.log["reference_s"]:
                at_reference = meter.total
            t += self.log["poll_s"]
        return meter, steps, at_reference

    def test_power_on_zeros_do_not_add_the_lifetime_counter(self):
        meter, steps, at_reference = self.replay()
        # 25.5 -> 49.1, 49.2 -> 131.5 and 108.2 -> 115.7 kWh: what was charged.
        self.assertAlmostEqual(meter.total, 113.4, delta=0.2)
        # The customer's three days: the charger's session reports add up to
        # 49.07 kWh; the counter lost one 0.1 kWh tick at the second power-on.
        self.assertAlmostEqual(meter.total - at_reference, 48.3, delta=0.2)
        self.assertLess(max(steps), 1.0)
        self.assertTrue(meter.incomplete)


if __name__ == "__main__":
    unittest.main()
