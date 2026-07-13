# TODO

This list tracks the near-term product work for `amperepoint/tuya-ap`.

## Dashboard

- [x] Bundle the AmperePoint Q Series Lovelace card with the integration.
- [x] Hide dashboard sections when required datapoints are not available.
- [x] Add card translations for PL/EN/DE/CS/ES/FR/HU.
- [ ] Build a polished default dashboard view for AmperePoint EV chargers.
- [ ] Make the dashboard visually clear and useful on desktop and mobile.
- [ ] Add simple charging controls: start, stop, current limit and mode/status.
- [ ] Add schedule controls for charging windows and planned charging sessions.
- [ ] Show reliable consumed energy values for the current session and historical use.
- [ ] Add default charts:
  - charging power,
  - session energy,
  - daily energy,
  - monthly charging cost.

## Presets

- [ ] Define reusable charging presets for common use cases.
- [ ] Support current-limit presets adjusted to the detected charger model.
- [ ] Prepare schedule/tariff presets for future tariff-aware charging.

## HACS Package

- [x] Keep the project installable as a HACS custom repository.
- [x] Package the integration as a `tuya-extend` style helper layer, not as a
      replacement for Home Assistant's built-in Tuya integration.
- [x] Register the bundled Lovelace card as a frontend resource in storage mode.
- [x] Add automatic AmperePoint source discovery from existing Tuya/Tuya Local
      devices.
- [x] Detect the AmperePoint Q Series model automatically from device/product
      metadata.
- [x] Ensure installation creates the `tuyaextend_amperepoint` integration from:

```text
custom_components/tuyaextend_amperepoint/
```

- [x] Document first-run setup for selecting existing Tuya/Xtend/Tuya Local
      entities and turning them into AmperePoint EVSE entities.
- [ ] Add a first-run generated dashboard/view helper.
- [ ] Add tests for entity discovery and raw phase payload decoding.

## Tuya Local

- [ ] Maintain a generic `Ampere Point Q Series` profile for `tuya-local`.
- [ ] Keep generation-specific profiles when DP behavior differs between Q22,
      Q37/VE and older Q Series chargers.
- [ ] Validate DP6/DP7/DP8 phase data before exposing phase sensors as stable
      production entities.
- [ ] Document which DPS are cloud-visible, local-only, product-defined or still
      unconfirmed.
