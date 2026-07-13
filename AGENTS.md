# AGENTS.md

## Project Brief

This repository supports AmperePoint EV charger integration work for Home
Assistant and Tuya.

The HACS integration lives under:

```text
custom_components/tuyaextend_amperepoint/
```

AmperePoint-specific profiles, dashboards, notes and observations live under:

```text
amperepoint/
```

## AmperePoint Facts To Preserve

- Q22 OTA PID: `cu111poj2mtikvls`.
- Current Q22 test pairing: `<device_id_q22_ota_current>`.
- Current Q22 LAN discovery: `<local_ip_q22_ota_current>`, protocol `3.5`.
- Standard HA Tuya/Tuya Sharing exposes only DP `1,3,4,9,13,14,17,18,24,25`
  for the current Q22 pairing.
- DP `6,7,8,10,19,23,33` are product-defined but not currently returned by the
  standard HA Tuya/Tuya Sharing path.
- Q22 OTA DP4 current limit is `6..32 A` in the latest HA/Tuya Sharing dump.
- Q37/VE DP1 behaved as a resetting session counter in testing.
- Q37/VE DP25 latched completed/last-session energy.
- Q37/VE DP6/DP7/DP8 phase readings were invalid on the tested unit and must not
  be treated as production-ready.

## Editing Rules

- Do not commit Tuya local keys, access tokens, Home Assistant `.storage` files,
  account identifiers, or raw unsanitized dumps.
- Keep raw API dumps sanitized.
- Do not present DP6/DP7/DP8 phase values as confirmed for Q22 OTA until a valid
  local payload is captured.
- Keep `tuya-local` profiles generation-specific when behavior differs.
- Keep dashboards explicit about whether values come from cloud/Xtend, local LAN,
  or the AmperePoint normalization layer.

## Useful Locations

```text
amperepoint/profiles/tuya_local/
amperepoint/dashboards/
custom_components/tuyaextend_amperepoint/
amperepoint/docs/q22-ota-dp-map.md
amperepoint/docs/q-series-generations.md
amperepoint/observations/q22-ota-standard-ha-tuya-api-raw-20260611.json
```
