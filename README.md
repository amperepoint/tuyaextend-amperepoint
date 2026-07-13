# TuyaExtend AmperePoint

Home Assistant / HACS workspace for AmperePoint EV chargers using Tuya.

<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=amperepoint&repository=tuyaextend-amperepoint&category=integration">
    <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open Repository on HACS">
  </a>
</p>

## Manuals

- [English installation manual](INSTALL.en.md)
- [Polska instrukcja instalacji](INSTALL.pl.md)

## Quick Start

1. Add the charger to the Tuya Smart / Smart Life app.
2. Configure the official Home Assistant Tuya integration first.
3. Install this repository through HACS as a custom integration.
4. Add `TuyaExtend AmperePoint` from Home Assistant integrations.
5. Add the Lovelace card:

```yaml
type: custom:amperepoint-q22-card
```

Full installation manuals: [`INSTALL.en.md`](INSTALL.en.md) / [`INSTALL.pl.md`](INSTALL.pl.md).

This repository contains:

- the HACS integration in [`custom_components/tuyaextend_amperepoint`](custom_components/tuyaextend_amperepoint),
- the bundled Lovelace card in [`custom_components/tuyaextend_amperepoint/frontend`](custom_components/tuyaextend_amperepoint/frontend),
- the AmperePoint EVSE knowledge pack in [`amperepoint/`](amperepoint/).

The AmperePoint pack includes `tuya-local` profiles, Lovelace dashboards,
diagnostic scripts, sanitized API dumps and DP maps collected from real Q Series
chargers.

## AmperePoint Pack

Start here:

```text
amperepoint/README.md
```

Important files:

```text
TODO.md
amperepoint/profiles/tuya_local/
amperepoint/dashboards/
amperepoint/docs/
amperepoint/observations/
amperepoint/scripts/
custom_components/tuyaextend_amperepoint/
```

## HACS Integration Direction

`TuyaExtend AmperePoint` is designed as a helper layer for Home Assistant. It
does not replace the official Tuya integration. The expected flow is:

1. Install and configure the official Home Assistant Tuya integration.
2. Install this repository as a HACS custom integration.
3. Add `TuyaExtend AmperePoint` from Home Assistant integrations.
4. Select a detected AmperePoint charger.
5. Add the bundled Lovelace card:

```yaml
type: custom:amperepoint-q22-card
```

The integration detects AmperePoint Q Series models from the Tuya device name,
model and product identifiers. The model key is encoded in the product/device
metadata, so current-limit ranges and phase assumptions are selected
automatically.

The integration creates normalized HA entities for readable status, charging
state, power, session energy, total energy, last session energy, current limit,
temperature, diagnostics and phase measurements when the source DPS are
available. Missing datapoints do not break the dashboard; the frontend card hides
unavailable sections.

The bundled card is exposed from the integration directory and registered as a
Lovelace module resource automatically in storage-mode dashboards. If Lovelace is
configured in YAML mode, add the resource manually:

```yaml
url: /tuyaextend_amperepoint/frontend/amperepoint-q22-card.js
type: module
```

For multiple chargers, pass `entityPrefix` or explicit `entities` to the card.
For example:

```yaml
type: custom:amperepoint-q22-card
entityPrefix: amperepoint_q22_ota
```

## Current Findings

### Q22 OTA / `cu111poj2mtikvls`

Current test pairing:

```text
Device ID: <device_id_q22_ota_current>
Local IP: <local_ip_q22_ota_current>
Local protocol: 3.5
Product ID: cu111poj2mtikvls
```

The standard Home Assistant Tuya integration / Tuya Sharing API currently exposes:

```text
DP1  forward_energy_total
DP3  work_state
DP4  charge_cur_set
DP9  power_total
DP13 connection_state
DP14 work_mode
DP17 energy_charge
DP18 switch
DP24 temp_current
DP25 charge_energy_once
```

The following DPS are defined in the Tuya product but were not returned by the
standard HA/Tuya Sharing API path in the latest test:

```text
DP6  phase_a
DP7  phase_b
DP8  phase_c
DP10 fault
DP19 local_timer
DP23 system_version
DP33 mode_set
```

Switching the Tuya Developer project from Standard Instruction to DP Instruction
did not make those missing report-only DPS appear in the HA/Tuya Sharing API
response.

### Q37 / EV Charger VE / `fdfjiphjxtc9qyhd`

For the tested Q37 generation:

- DP1 behaves as a resetting session counter, not a lifetime meter.
- DP25 latches the completed/last session value.
- DP6/DP7/DP8 produced invalid local phase values on the tested unit and are not
  mapped as production sensors.

### Older Q Series / `bktb3jskdic1ar2t`

The older test charger exposed local DP6/DP7/DP8 phase payloads. This confirms
that phase DPS exist in at least some Q Series generations, but behavior differs
by firmware/product generation.

## Security

This repository must not contain:

- Tuya local keys,
- Tuya access tokens,
- Home Assistant `.storage` files,
- account credentials.

API dumps under `amperepoint/observations/` are sanitized.

## Installation Notes

This repository is not a replacement for Home Assistant's built-in Tuya
integration. It adds an AmperePoint normalization layer on top of entities that
already exist in Home Assistant.

Recommended direction:

1. Keep the official Tuya integration or Xtend Tuya for cloud entities.
2. Use `tuya-local` with profiles from `amperepoint/profiles/tuya_local/` for LAN
   testing.
3. Use the AmperePoint extension integration from:

```text
custom_components/tuyaextend_amperepoint/
```

That extension normalizes existing HA entities into EVSE-oriented entities such
as readable status, charging power, session energy, session cost, current limit
and diagnostics.
