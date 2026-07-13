# Tuya Developer products

Source file:

```text
<source_file_path>
```

Export date on disk: 2026-05-27.

## Product list

| Product name | Product ID | Category | Communication | Created | Modified | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `Q21_11kW_with_OTA` | `kvldga0omutrnify` | EV charger | Wi-Fi, Bluetooth LE, LTE Cat1 | 2026-02-26 | 2026-02-26 | Newer OTA generation candidate. |
| `Q20_7KW_with_OTA` | `1qu8ca6etdubbigj` | EV charger | Wi-Fi, Bluetooth LE | 2025-11-01 | 2026-02-07 | Seen earlier in HA registry as `Q20_7-vdevo`. |
| `Q20_3.5KW_with_OTA` | `c2sgesr3zo1met7q` | EV charger | Wi-Fi, Bluetooth LE | 2025-11-01 | 2026-02-07 | Candidate generation. |
| `Q11_11KW_with_OTA` | `3axf0fkgiop0ukhb` | EV charger | Wi-Fi, Bluetooth LE | 2025-11-01 | 2026-02-26 | Seen earlier in HA registry as `Q11 OTA`. |
| `Q22 OTA` | `cu111poj2mtikvls` | EV charger | Wi-Fi, Bluetooth LE | 2025-10-31 | 2026-03-05 | Screenshot function definition captured. |
| `EV Charger_NO_OTA_3.5KW_7KW_11KW_22KW` | `jhlyzpk5nfk28nrh` | EV charger | Wi-Fi, Bluetooth LE | 2025-09-13 | 2026-02-07 | Candidate non-OTA generation. |
| `EV Charger_VE` | `fdfjiphjxtc9qyhd` | EV charger | Wi-Fi, Bluetooth LE | 2025-04-17 | 2026-02-12 | Tested as `Q37 VG`. |

The export does not include the oldest charger tested first:

```text
bktb3jskdic1ar2t
```

## Panel and firmware hints

Most products use:

```text
Panel: Maxima-Ev-Chargering-Panel
Panel UIID: 000002pnmm
Wi-Fi/Bluetooth module: WBR3
Module firmware key: keyjkajwawthq4f5
```

Exceptions:

```text
Q21_11kW_with_OTA -> DIY Style Panel on Studio, UIID 0000000999, Wi-Fi/BLE/LTE Cat1
```

## Local profile strategy

Keep HACS generic at the Q Series family level. Keep `tuya-local` profiles product/generation-specific enough to capture DP differences.

Current profile coverage:

| Product ID | Profile |
| --- | --- |
| `bktb3jskdic1ar2t` | `profiles/tuya_local/amperepoint_q_series_evcharger.yaml` |
| `fdfjiphjxtc9qyhd` | `profiles/tuya_local/amperepoint_ve_evcharger.yaml` |
| `cu111poj2mtikvls` | `profiles/tuya_local/amperepoint_q22_ota_evcharger.yaml`, candidate until physical test |

Other product IDs should be added to a profile only after a function-definition screenshot/export or physical local DP dump confirms the layout.

## Product function maps

Captured detailed function maps:

```text
docs/product-fdfjiphjxtc9qyhd-ev-charger-ve.md
docs/product-cu111poj2mtikvls-q22-ota.md
```

The visible DP layout for `EV Charger_VE` and `Q22 OTA` is very similar. Physical HA testing still matters because the Q37/VE test unit did not provide trustworthy DP6/DP7/DP8 phase values even though the product definition lists them.
