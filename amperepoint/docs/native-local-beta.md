# AmperePoint Local — test builds

**0.5.38b2:** readable tables for every reported datapoint and opt-in, verified
PRIME start/stop/current controls. See the [hardware test report](native-local-controls-test-20260911.md).
The read-only baseline below describes 0.5.38b1 and the default for unverified entries.

This build adds an integration-owned LAN transport using TinyTuya. It does not
require the Tuya Local custom integration. It is a read-only PRIME pilot, not
full Tuya Local feature parity and not a stable release.

## Setup

In Settings → Devices & services → AmperePoint → Add entry, choose local LAN.
Either import the selected charger's key once from an already configured Tuya
integration, or enter its device ID, local key, private IPv4 address and protocol.
The key is stored in Home Assistant's config entry, never in the dashboard or
diagnostic download. Protect HA backups as they contain credentials.

Leaving the address empty requests broadcast discovery. Some Docker/VM network
configurations do not forward LAN broadcasts; enter the address manually in
that case. After a failed connection, discovery is retried at a bounded interval.
The recovered address is saved. A DHCP reservation is still recommended.

The connection must pass a real status read and match a supported PRIME layout
before it is saved. An existing dashboard entry for the same physical device
is migrated only after confirmation; stale entity control routes are removed.
Connection settings can be edited later without displaying the saved key.

## Test scope

- Separate PRIME packed (DP102) and split (DP102 + DP117) telemetry layouts.
- Power, session energy, temperature, status, CP connection and raw diagnostics.
- Start/stop, current settings and the planner are deliberately disabled on LAN.
- A closed socket after each bounded status poll; unavailable on read failure.
- Saved credentials and address survive HA restart; reads do not use Tuya cloud.
- One-time credential import is optional. A standalone QR login is not included.

Do not add the same charger to another persistent LAN client at the same time.
No claim of validated nonzero power/current/energy scaling follows from a
zero-load EVSE tester. Test those against a real session before enabling writes
or expanding the supported capability list. Existing Q cloud behavior remains
unchanged.

## Acceptance checks

1. Select the test wallbox in the shared Ampere Point - Tuya dashboard.
2. Check `AmperePoint Local`, `LAN OK`, the IP and read-only notice in the footer.
3. With a tester connected and no load, expect a connected vehicle and zero power;
   do not interpret raw `STATE_C` alone as proof of active charging.
4. Inspect the DP table and compare temperature/CP with the device.
5. Restart HA and verify automatic reconnection and the same selected device.
6. Test disconnect/reconnect and DHCP discovery separately on a suitable LAN.

The manifest pins TinyTuya 1.20.0, matching the installed Tuya Local version to
avoid competing pinned dependency versions when both integrations coexist.
