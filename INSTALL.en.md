# Installation

TuyaExtend AmperePoint is a Home Assistant integration for AmperePoint EV
chargers. It can use the official Tuya integration directly or consume entities
from Xtend Tuya, `tuya-local` and LocalTuya. Xtend Tuya is optional.

It does not replace Tuya pairing. Initialize Tuya first, then add this HACS
integration.

## 1. Initialize Tuya In Home Assistant

1. Add the charger to the Tuya Smart / Smart Life mobile app.
2. In Home Assistant, go to:

```text
Settings -> Devices & services -> Add integration -> Tuya
```

3. Complete the official Tuya login / QR authorization flow.
4. Confirm that the charger appears in Home Assistant.
5. It is enough for the charger and at least one of its entities to appear in
   Tuya. TuyaExtend reads the remaining supported DPS from the official
   integration runtime even when Home Assistant did not create entities for
   them.

```text
switch
charging current / current limit
power
energy
work state / connection state
temperature
```

The exact DP list depends on the Tuya product generation and firmware.

If the charger is not visible through the official Tuya integration, install and
configure Tuya first. TuyaExtend AmperePoint cannot discover a cloud charger that
Home Assistant cannot see yet.

## 2. Install With HACS

1. Open HACS in Home Assistant.
2. Go to `Integrations`.
3. Open the three-dot menu and choose `Custom repositories`.
4. Add this repository:

```text
https://github.com/amperepoint/tuyaextend-amperepoint
```

5. Select category:

```text
Integration
```

6. Install `TuyaExtend AmperePoint`.
7. Restart Home Assistant.

## 3. Add The Integration

1. Go to:

```text
Settings -> Devices & services -> Add integration
```

2. Search for:

```text
TuyaExtend AmperePoint
```

3. On the welcome screen, choose automatic setup or manual entity mapping.
4. Select the detected AmperePoint charger and configure the tariff.
5. Leave `Create an AmperePoint dashboard` enabled for a ready-to-use sidebar
   panel with the charger entities mapped automatically.
6. Save the entry.

The integration detects Q Series models from the Tuya device name, model and
product metadata. If the charger is not detected, rename the Tuya/Home Assistant
device so that the model is visible in the name, for example:

```text
AmperePoint Q22 OTA
AmperePoint Q37
AmperePoint Q Series
```

Then reload the Tuya integration or restart Home Assistant and try again.

## 4. Open The AmperePoint Dashboard

With the dashboard option enabled, the integration creates a separate
AmperePoint panel in the Home Assistant sidebar. It does not overwrite or edit
existing dashboards. Later changes made to that panel are preserved across
Home Assistant restarts.

The bundled card resource is registered automatically in standard Home
Assistant storage-mode dashboards. If automatic dashboard creation was disabled,
add a manual card with:

```yaml
type: custom:amperepoint-q22-card
```

For multiple chargers, pass an entity prefix:

```yaml
type: custom:amperepoint-q22-card
entityPrefix: amperepoint_q22_ota
```

You can also provide explicit entity IDs:

```yaml
type: custom:amperepoint-q22-card
entities:
  switch: switch.amperepoint_q22_ota_charging
  currentLimit: number.amperepoint_q22_ota_current_limit
  status: sensor.amperepoint_q22_ota_status
  power: sensor.amperepoint_q22_ota_power
  sessionEnergy: sensor.amperepoint_q22_ota_session_energy
  totalEnergy: sensor.amperepoint_q22_ota_total_energy
```

If Lovelace is configured in YAML mode, add the card resource manually:

```yaml
resources:
  - url: /tuyaextend_amperepoint/frontend/amperepoint-q22-card.js
    type: module
```

## 5. What The Integration Adds

TuyaExtend AmperePoint creates normalized Home Assistant entities such as:

```text
readable charging status
vehicle / control-pilot state
charging power
current session energy
total energy
last session energy
current limit slider
charging mode selector
target energy
temperature
fault diagnostics
system version and a complete raw-DP list
phase voltage/current/power when DPS are available
```

With the official Tuya source, DP18 `switch`, DP4 `charge_cur_set`, DP14
`work_mode` and DP17 `energy_charge` can be controlled without Xtend Tuya when
the product marks them writable.

Current session energy can be calculated from:

```text
total energy delta
native session counter
power integration fallback
```

The default for newer Q22 OTA style devices is total-energy delta when a stable
total counter is available.

## 6. Optional Xtend And Local Sources

If Xtend Tuya is already installed, select its device during automatic setup or
map its entities manually. This remains compatible with earlier configurations,
but it is not required.

The repository also contains `tuya-local` profile candidates under:

```text
amperepoint/profiles/tuya_local/
```

Local mode is optional and more advanced. It can expose local DPS on some
chargers, but it usually requires the device local key and a working local Tuya
setup. The first public HACS path is intentionally based on the official Tuya
integration because it is easier for normal Home Assistant users.

## Troubleshooting

### No charger is detected

- Confirm that the charger appears in the official Tuya integration first.
- Reload the Tuya integration.
- Rename the HA device to include `AmperePoint`, `Q22`, `Q37`, or `Q Series`.
- Restart Home Assistant after installing the HACS integration.

### Phase data is missing

Some Tuya product generations define DP6/DP7/DP8 phase payloads but do not expose
them through the official Tuya API. The dashboard hides phase sections when those
values are not available.

### The card does not load

- Hard-refresh the browser.
- Check that `/tuyaextend_amperepoint/frontend/amperepoint-q22-card.js` is present
  as a Lovelace resource.
- In YAML-mode Lovelace, add the resource manually.

### Start/stop or current limit does not work

The official Tuya mode does not require a separate source entity. TuyaExtend
uses the device's writable DP definition. Confirm that the charger is online and
that the raw-DP view marks the item with `↔`. Xtend/local sources require a
correctly mapped writable source entity.

## Security

Do not publish:

```text
Tuya local keys
Tuya access tokens
Home Assistant .storage files
account identifiers
unsanitized raw API dumps
```
