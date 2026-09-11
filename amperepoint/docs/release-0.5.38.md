# 0.5.38 — Q Series Cloud + built-in PRIME LAN

## Polski

Wallbox PRIME ma teraz lokalną obsługę protokołu Tuya **wbudowaną w AmperePoint**.
Nie wymaga osobnego Tuya Local ani LocalTuya. Q Series nadal zalecamy łączyć
przez oficjalną integrację Tuya / Tuya Cloud — ta ścieżka zapewnia obecnie
szerszy obsługiwany zakres DP w naszym dodatku. Dostępność zależy od firmware.

### Co nowego

- Kreator AmperePoint Local: import danych z autoryzowanej integracji Tuya lub
  ręczne Device ID/local key, wykrywanie IP i możliwość ręcznego adresu.
- Zweryfikowane sterowanie PRIME: start/stop i limit prądu przez LAN.
- Tryby „Ładuj teraz”, „Do zadanej energii” i „Według harmonogramu” realizowane
  przez planer HA: dni tygodnia, wiele przedziałów, prąd na przedział, override,
  następna akcja i zachowanie ustawień po restarcie.
- Niezależne potwierdzanie komend odczytem urządzenia. Packed PRIME nie musi
  raportować DP140 — potwierdzenie wykorzystuje sprawdzoną parę statusów DP101/109.
- Czytelne tabele wszystkich odczytanych wartości LAN, z redakcją danych autoryzacji.
- PID i wersja w stopce oraz skrót do ustawień. Poprawiony onboarding i wskazanie
  nieznanego podłączenia auta, gdy urządzenie nie raportuje CP.
- Nowe instrukcje PL/EN dla obu serii i dwa podglądy panelu PRIME.

### Zakres i ważne ograniczenia

Sterowanie jest włączane dla zweryfikowanych kontraktów firmware split
`(V7.0.0)F2.0.0` oraz packed `(V8.0.7)F1.3.6`, nie tylko na podstawie mocy lub PID.
Obecne profile ograniczają prąd do 16 A i nie przekraczają DP152. Packed
przetestowano z DP152 = 16 A; inna konfiguracja może pozostać tylko do odczytu.
Nie deklarujemy pełnego zakresu każdej odmiany PRIME 11/22 kW.

**HA musi działać i mieć połączenie LAN, aby wykonać plan i odcięcie kWh.**
Ładowarka pozostaje w natywnym trybie natychmiastowym, z wyłączonym własnym
harmonogramem. Nie zapisujemy jej natywnego harmonogramu ani limitów instalacji
i zabezpieczeń. Unikaj konkurencyjnego sterowania z innych integracji/aplikacji.

Testy fizyczne: EVSE tester bez poboru mocy, start/stop, kilka limitów prądu,
uruchomienie celu energii, automatyczny start/stop przedziału i powrót po restarcie HA.
**Pomiar pod obciążeniem i rzeczywiste odcięcie po zadanych kWh wymagają dalszej
weryfikacji z autem.** Grafiki mają oznaczone dane demonstracyjne.

### Aktualizacja

Zrób kopię HA → pobierz **v0.5.38** w HACS → zrestartuj HA → odśwież przeglądarkę.
Dla istniejącego PRIME tylko do odczytu otwórz opcje połączenia LAN i włącz
zweryfikowane sterowanie. Nie trzeba usuwać wpisu. Przechodząc z osobnego Tuya Local,
zachowaj dane i zależne automatyzacje oraz wyłącz konkurencyjne połączenie LAN.
Aktualizacja sama nie paruje nowej ładowarki.

[Instrukcja PL](https://github.com/amperepoint/tuyaextend-amperepoint/blob/v0.5.38/INSTALL.pl.md)
· [Panel PRIME](https://github.com/amperepoint/tuyaextend-amperepoint/blob/v0.5.38/amperepoint/screenshots/amperepoint-prime-lan.png)
· [Diagnostyka PRIME](https://github.com/amperepoint/tuyaextend-amperepoint/blob/v0.5.38/amperepoint/screenshots/amperepoint-prime-diagnostics.png)

## English

PRIME now has **built-in local Tuya protocol support**, without a separate
Tuya Local/LocalTuya dependency. Q Series is still best served by the official
Tuya Cloud path for broader currently supported DP coverage in AmperePoint;
the exact range depends on generation and firmware.

- Native LAN onboarding, credential import/manual entry and IP discovery.
- Verified PRIME start/stop/current controls, with independent device readback.
- HA-owned charge-now, energy-target and weekly-planner modes, per-window
  current, overrides, next action and persisted settings.
- Readable LAN tables, redacted authentication data, PID/version footer and
  integration-settings shortcut. Unknown CP is not treated as disconnected.
- Reworked English/Polish installation manuals and labelled PRIME UI previews.

Validated control contracts: split `(V7.0.0)F2.0.0` and packed `(V8.0.7)F1.3.6`.
Current is conservatively capped at 16 A and never above DP152; packed was tested
with a 16 A installation limit. Unknown firmware or a different packed limit may
remain read-only. This is not full-range validation of every PRIME variant.

**HA must remain running and connected for scheduling and energy cutoffs.**
Keep the device in native immediate mode, disable its own schedule and avoid
competing controllers. Native schedule/protection/installation-limit writes
are not enabled. Hardware tests used zero-load EVSE testers; metering under
load and an actual energy-target cutoff still require real-vehicle validation.

Back up HA, update through HACS, restart HA and refresh the browser. Existing
read-only LAN entries can enable verified controls through connection options.
Preserve credentials/automation dependencies when migrating from separate
Tuya Local and disable its competing LAN connection first.

Validation: **189 Python tests + 12 frontend tests**, syntax/encoding checks,
HA 2026.7.2 local runtime tests and cloud-free import checks.
[English instructions](https://github.com/amperepoint/tuyaextend-amperepoint/blob/v0.5.38/INSTALL.en.md).
