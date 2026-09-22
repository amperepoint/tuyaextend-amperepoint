# Installation — Ampere Point Q Series and Wallbox PRIME

## Choose a connection

| Series | Recommended path | Requirements |
| --- | --- | --- |
| Q Series | Tuya Cloud + AmperePoint | Official Tuya integration in HA, internet |
| Wallbox PRIME | Built-in AmperePoint Local (LAN) | Device ID, local key, LAN and compatible firmware |

For **Q Series we recommend Tuya Cloud**: our integration currently supports
a broader DP/feature range through this path than through our local profiles.
AmperePoint also reads DPS present in the Tuya runtime without dedicated
official HA entities. Coverage depends on generation and firmware; not every
DP or phase measurement is guaranteed. Xtend Tuya is not required.

For **PRIME, local Tuya protocol support is built into this repository**.
Separate Tuya Local or LocalTuya is not needed. The official Tuya integration
can help import credentials, but is not required for LAN operation.

## 1. Install through HACS

1. Open HACS → menu → **Custom repositories**.
2. Add `https://github.com/amperepoint/tuyaextend-amperepoint`, category **Integration**.
3. Download **TuyaExtend AmperePoint** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → AmperePoint**.
5. Follow the path for your series below.

Downloading files in HACS alone does not configure the charger.

## 2A. Q Series — Tuya Cloud

1. Pair the charger in Tuya Smart or Smart Life.
2. Add the official **Tuya** integration in HA, enter the app account's User Code
   and complete QR authorization following the [HA instructions](https://www.home-assistant.io/integrations/tuya/).
3. Confirm that the charger appears among Tuya devices in HA.
4. Choose the detected-charger setup option in AmperePoint.
5. Select the charger, configure the tariff and submit.

This path does not require a local key or a separate Tuya Developer account
for official HA authorization. If discovery fails, reload Tuya and check the
name/model, for example `Ampere Point Q Series`.

Available product features include start/stop, current, modes, energy target,
planner, measurements and diagnostics. Commands require writable DPS.
A DP in a product schema is not necessarily returned by the cloud.

## 2B. Wallbox PRIME — AmperePoint Local (LAN)

1. Ensure HA can reach the charger; a router DHCP reservation is recommended.
2. Choose **AmperePoint Local (LAN)** in the AmperePoint wizard.
3. Import details from an already authorized Tuya integration, or select manual setup.
4. Enter the name, **device ID**, **local key**, IP and protocol (tested PRIME: **3.5**).
5. Empty IP requests discovery. Docker/VLAN may require an explicit IP and LAN routing.
6. The wizard checks the device and indicates controls or read-only support.
7. Confirm and open **Ampere Point - Tuya dashboard**.

**Device ID is not PID.** Device ID identifies the individual charger and is
needed for connection. PID identifies the product and appears in the diagnostic footer.

The local key is a device secret. If import cannot provide it, obtain it
through authorized Tuya account tools. Manual retrieval may require a Tuya
Developer account, Cloud project and linked app account. Our wizard does not
create that project or authenticate to Tuya Developer. Re-pairing can change the key.

### PRIME scope in 0.5.38

Profiles use the DP contract and firmware, not just name, power rating or PID.

| Feature | Scope |
| --- | --- |
| LAN readings | Power, session energy, temperature, status, firmware and available technical values |
| Start/stop | Verified split `(V7.0.0)F2.0.0` and packed `(V8.0.7)F1.3.6` profiles |
| Current | Integer 1 A steps, maximum 16 A and never above installation limit DP152 |
| Modes | Charge now, energy target and scheduled charging — executed by HA |
| Planner | Multiple weekdays/windows, minute precision, per-window current, overrides and next action |
| Commands | Independent readback; an ACK alone is insufficient |
| Restart | Saved plan/settings and automatic LAN reconnection |

Packed was verified with a 16 A installation limit; other limits or unknown
firmware may remain read-only. Split is also capped at 16 A. This is not a
claim of full-range controls for every PRIME 11/22 kW variant.

**The planner runs in HA, not in the charger's memory.** HA must remain running
and connected for scheduled stops and energy cutoffs. Keep the device in native
immediate mode with its own schedules disabled. Avoid competing Tuya or other
integration controls. We do not write DP151, DP152 or protection settings.

Start/stop, current and a scheduled window were confirmed on zero-load EVSE
testers. Meter accuracy and energy-target cutoff still need real-vehicle tests.
Missing CP does not mean the car is disconnected.
[Packed test report](amperepoint/docs/prime-packed-local-controls-20260911.md).

## 3. Dashboard and settings

One shared **Ampere Point - Tuya dashboard** supports Q Cloud and PRIME LAN.
Select a charger in the header when several are configured. Each entry has
its own configuration and planner.

**Integration settings** in the footer opens the matching HA entry. LAN options
allow changing the IP, key and protocol and rechecking verified controls.
An existing read-only entry need not be deleted. The footer shows source, PID
and dashboard version.

Add the card to your own dashboard:

```yaml
type: custom:amperepoint-q22-card
entityPrefix: amperepoint_q_series
```

The technical card name is retained for compatibility; it also supports PRIME.
For YAML Lovelace add this resource as a `module`:
`/tuyaextend_amperepoint/frontend/amperepoint-q22-card.js`.

## 4. Updates and migration

HACS offers a published release after checking for updates. A GitHub commit
alone does not install anything on users' systems. Back up HA, update through
HACS, restart HA and refresh the browser. Check the backend/card version in the footer.

When migrating from separate Tuya Local, preserve connection details and check
dependent automations. Disable competing LAN connections before enabling ours.
The wizard can migrate a matching AmperePoint entry to LAN, retaining entities
and pausing its previous planner. Check dependencies before deleting entries.

Xtend Tuya, Tuya Local and LocalTuya remain optional entity sources for existing
setups, but are not dependencies of built-in PRIME LAN.

## 5. Energy dashboard

For the energy-foundation update (`0.5.39b3` development), expand **Energy in
Home Assistant** above the AmperePoint footer, then add the indicated **Charging
energy** entity under individual devices in HA's Energy settings. Recorder must
record it. Add one consumption sensor per physical charger.

When upgrading, replace old session/source-energy selections with the new sensor;
do not add both. Historical statistics are not merged or deleted. The new sensor
starts at zero and is separate from the current-session display.
[Full guide: sources, gaps, resets, restart and migration](amperepoint/docs/home-assistant-energy.md).

## Troubleshooting and security

- **PRIME missing in Cloud:** use LAN; do not expect full PRIME telemetry from cloud.
- **LAN error:** check IP, key, protocol, routing and competing LAN clients.
- **Read-only:** inspect firmware and DPS; do not force another device's profile.
- **Missing phases:** coverage depends on source; missing measurements are not fabricated.
- **Old card:** hard-refresh the browser.
- **Unconfirmed command:** check connectivity, device status and competing automations.

Never publish local keys, tokens, HA `.storage`, account details or unsanitized
raw dumps. Card/authentication data is redacted in diagnostics. The integration
does not replace electrical protections or correct installation settings.
