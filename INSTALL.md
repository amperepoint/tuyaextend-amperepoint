# Installation / Instalacja

Choose a language:

- [English installation manual](INSTALL.en.md)
- [Polska instrukcja instalacji](INSTALL.pl.md)

## Important

Wallbox Prime 22 kW uses **Tuya Local** for read-only telemetry. AmperePoint
includes a profile installer in its setup and options menus; see the language
manuals above. The cloud setup below applies to chargers exposing their data
through the official Tuya integration.

AmperePoint does not replace device pairing. Q Series can use the official
Home Assistant Tuya integration; PRIME uses Tuya Local with the bundled profile.
The shared panel is named **Ampere Point - Tuya dashboard**.

AmperePoint nie zastępuje parowania urządzenia. Q Series może korzystać z
oficjalnej integracji Tuya, a PRIME wymaga Tuya Local z dołączonym profilem.
PRIME: odczyt telemetrii, bez start/stop, zmiany prądu i sterowania planerem.
Nazwa wspólnego panelu: **Ampere Point - Tuya dashboard**.

## HACS

```text
https://github.com/amperepoint/tuyaextend-amperepoint
```
