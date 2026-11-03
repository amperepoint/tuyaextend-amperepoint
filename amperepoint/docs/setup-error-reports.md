# Downloadable LAN setup diagnostics

After a failed manual LAN setup, Tuya credential import, or LAN options check,
the same form offers **Download error report / Pobierz raport błędu**. It works
before a config entry exists. The user can download the JSON and attach it to
a support ticket, correct the fields, and retry without leaving the wizard.
Downloading does not contact AmperePoint or query the charger again.

The report contains the integration/HA versions, UTC time, attempted setup
method, protocol, failure stage, public product ID when available, and the
sanitized response from that attempt. Validation checks distinguish missing
DP102/109 from an unexpected telemetry layout. Protocol errors retain only a
numeric error code; socket/authentication failures may have no DP snapshot.

Known telemetry/settings DPs preserve types and allowed values, including
DP102 measurements, DP106 firmware, DP107 presets, DP109 state, DP117 phases,
DP140 start/stop, DP150 current, DP151 mode and DP152 installation limit.
Unknown DP values are redacted while their IDs/types remain visible. Unknown
nested fields are counted but omitted. Card/authentication DPs 112/113 are
always redacted. This report is not a complete raw packet dump: adding a new
layout can still require a separately reviewed read-only capture.

Device IDs, IP addresses, names, local keys, account data, raw exceptions and
protocol error bodies are not included. Credentials remain in the existing
HA setup flow, not in the report cache. No control/profile validation is relaxed
and the diagnostic path sends no charger commands.

Downloads use the HA authenticated HTTP view and a signed, path-specific URL
valid for 15 minutes. Only sanitized JSON is held in memory, with a maximum of
16 reports and timed eviction; no report is written to HA storage or `www`.
Downloads use `Content-Disposition: attachment` and `Cache-Control: no-store`.
Restarting HA invalidates reports. Retrying creates a fresh link; an expired or
evicted link returns 404. Download the file rather than forwarding its URL.

Validation:

```sh
python -m unittest discover -s tests
node --test tests/test_frontend_device_selector.mjs
```

`tests/ha_setup_diagnostics_smoke.py` additionally runs the real HA flow and
HTTP authentication/download path using a simulated charger. Run it in an
isolated HA container with this repository mounted at `/work` read-only.
