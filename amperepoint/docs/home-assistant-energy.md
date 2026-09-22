# Charging energy / Energia ładowania

Energy foundation for issue #36, part 1. This adds a consumption stream for
Home Assistant Energy and Recorder. It does **not** implement a session archive,
historical price calculation, CSV export or PV allocation.

## Power cross-check (0.5.39b3)

**Charging energy** now checks counter increases against a parallel integral
of reported power. **Energy estimated from power** is a separate diagnostic
sensor; do not add both sensors for the same charger to the Energy dashboard.
The original device counter remains unchanged and visible.

Correction is deliberately conservative: the counter's accumulated increase
must exceed the power estimate by **10%**, **plus** the larger of 0.1 kWh or two
counter ticks, **plus** one minute at the conservative maximum power allowed by the integration. These absolute margins avoid correcting rounding and short reporting
delays. Only excess consumption is corrected; a lower counter is not topped up.
Comparison windows normally re-anchor on a counter advance after an hour;
an unchanged counter retains its window so delayed reports can catch up.

For a covered interval, an excessive counter increase is replaced with the
remaining energy estimated from power. The raw-counter baseline is advanced
at the same checkpoint, so the excluded amount cannot be added on a later poll
or restart. The published total never decreases. Corrections are estimates,
not calibrated measurements or modifications to charger firmware / Tuya.

Freshness is required throughout the comparison window (maximum 60 seconds
between observations and maximum 60-second power-report age):

- Direct PRIME LAN: successful validated snapshots.
- Native Tuya cloud: passive observation of actual `power_total` MQTT reports,
  including repeated zeros. Reading the SDK cache or a device-wide update does
  not renew freshness. Reconnection clears the previous report. Unsupported
  MQTT adapters / encoded `dpId` reports cannot authorize correction.
- Mapped power entities / packed PRIME telemetry: provider reports timestamped
  by HA `last_reported`. This relies on the provider reporting actual samples;
  a provider that republishes cached data cannot be detected here. Generic Q
  raw-DP aggregate attributes lack per-power timestamps and cannot authorize
  correction.

Missing/stale power, source changes, offline periods and restarts invalidate
the comparison window. The next usable counter advance starts a new window;
unknown intervals retain counter handling and are not automatically corrected.
The power estimate skips uncovered intervals and records incomplete history.
If the charger reports zero only once for a long pause, automatic correction
is intentionally unavailable for that pause. A 15-second coordinator poll is
not proof of a fresh device measurement. Small fluctuations/errors inside the
tolerance remain possible; a false but fresh power report can also mislead
the cross-check. This is not a substitute for a separate calibrated meter.

Charging-energy attributes expose `power_validation`, `correction_count`,
`excluded_energy_kwh` and `power_tolerance_percent`. A correction publishes
`data_quality: power_corrected` and marks `incomplete_history: true`; the
persistent correction count remains visible after subsequent normal readings.
The diagnostic power sensor identifies itself as `power_estimate` and exposes
its own `incomplete_history` flag. Both totals use the existing acknowledged
checkpoint before publication. No old Recorder statistics are rewritten.

## Kontrola mocy — po polsku

Od wersji rozwojowej **0.5.39b3** licznik **Energia ładowania** porównuje przyrosty
z równoległym obliczeniem mocy × czasu. Osobny sensor diagnostyczny **Energia
obliczona z mocy** pozwala sprawdzić wynik. W panelu Energia wybieramy tylko
**Energia ładowania**, żeby nie liczyć tego samego zużycia dwa razy.

Korekta nadmiernego przyrostu wymaga przekroczenia **10%** oraz dodatkowego
marginesu: minimum **0,1 kWh / dwa kroki licznika** i energii jednej minuty przy
konserwatywnej maksymalnej mocy przyjętej przez integrację. Nie podnosimy automatycznie zaniżonych wskazań.
Odrzucony przyrost jest zapisywany razem z nowym punktem odniesienia, więc nie
wróci po kolejnym odczycie lub restarcie. Surowy licznik urządzenia pozostaje
bez zmian. Wynik skorygowany jest szacunkiem.

Wymagamy ciągłości danych i raportów mocy nie starszych niż 60 sekund.
Ponowne czytanie pamięci Tuya co 15 sekund nie odświeża pomiaru. Przy utracie
danych, restarcie lub nieobsługiwanym źródle świeżości nie korygujemy nieznanego
okresu. Dotyczy to również ładowarki, która przez wielogodzinną przerwę wysyła
zero tylko raz. Encje mapowane muszą dostarczać rzeczywiste raporty, a nie
odświeżać stare wartości. Liczba korekt i pominięte kWh są widoczne w atrybutach
sensora. Wcześniejsze statystyki HA nie są zmieniane.

## English — setup

1. Back up Home Assistant, install the integration update and restart HA.
2. Open the AmperePoint dashboard and select the charger. Expand **Energy in
   Home Assistant** above the footer. It shows the exact entity ID for that charger.
3. In **Settings → Dashboards → Energy**, add that entity under **Individual
   devices**. Choose **Charging energy**, not Session energy, Last session energy
   or Source energy counter. Add each physical charger once.
4. Keep the home's grid-import meter as the grid source. A charger is an
   individual load; its consumption is already part of the home's grid meter.
5. Recorder must record the new sensor. If you use Recorder include/exclude
   filters, check them. Wait for Home Assistant to collect and process statistics;
   an empty Energy chart immediately after setup is normal.

Each charger gets an entity with unique ID `<config_entry_id>_charging_energy`,
unit `kWh`, `device_class: energy`, `state_class: total_increasing`. Its entity ID
is generated by HA and may be renamed, so use the exact one shown in the panel.
The existing power sensor remains `kW`, `device_class: power`,
`state_class: measurement`.

### Upgrade from older energy entities

Old entity IDs and current values are preserved. Session energy, Last session
energy, Source energy counter (previously Total energy) and Session cost no
longer declare a statistics state class: they are source/session snapshots,
not the canonical continuous consumption series. Existing custom entity names
are not overwritten by the new translated default name.

If an old sensor was selected in Energy, replace that selection with **Charging
energy**. Do not add both. Existing Recorder rows/statistics are **not deleted,
rewritten or merged**; the new sensor starts a separate history. The old series
does not continue producing long-term statistics. A historical Energy chart may
therefore change when its selected source is replaced. Back up HA before changing
an existing setup. This version does not automatically migrate historical sums
or alter the home's Energy configuration.

## Polski — konfiguracja

1. Zrób kopię zapasową Home Assistant, zainstaluj aktualizację i zrestartuj HA.
2. Otwórz panel AmperePoint i wybierz ładowarkę. Nad stopką rozwiń **Energia w
   Home Assistant** — znajdziesz tam dokładny identyfikator jej encji.
3. W **Ustawienia → Panele → Energia** dodaj ją w sekcji poszczególnych urządzeń.
   Wybierz **Energia ładowania**, nie energię sesji, ostatniej sesji ani źródłowy
   licznik energii. Każdą fizyczną ładowarkę dodaj tylko raz.
4. Nie zastępuj ładowarką licznika poboru z sieci dla całego domu. Ładowarka jest
   odbiornikiem, którego zużycie jest już uwzględnione w liczniku domu.
5. Recorder musi zapisywać nową encję. Sprawdź własne filtry include/exclude.
   Poczekaj na zebranie i przetworzenie statystyk przez HA — pusty wykres zaraz
   po konfiguracji nie oznacza błędu.

Każda ładowarka ma własną encję z unique ID `<config_entry_id>_charging_energy`,
jednostką `kWh`, `device_class: energy` i `state_class: total_increasing`.
Identyfikator encji nadaje HA, a użytkownik może go zmienić — użyj tego z panelu.
Dotychczasowa moc zachowuje `kW`, `device_class: power`,
`state_class: measurement`.

### Przejście ze starszych encji

Zachowujemy identyfikatory i bieżące wartości starych encji. Energia sesji,
energia ostatniej sesji, źródłowy licznik energii (wcześniej energia całkowita)
oraz koszt sesji nie deklarują już klasy statystycznej. To odczyty źródłowe lub
wartości pojedynczej sesji, a nie ciągły licznik zużycia. Własne nazwy encji
ustawione przez użytkownika pozostają bez zmian.

Jeżeli wcześniej wybrano jedną z tych encji w Energii, zastąp ją **Energią
ładowania**. Nie dodawaj obu równocześnie. Nie usuwamy, nie przepisujemy i nie
scalamy istniejących danych Recorder. Nowa encja tworzy osobną historię,
a stara nie dopisuje kolejnych statystyk długoterminowych. Zmiana wybranego
źródła może zmienić widoczną historię panelu Energia. Przed zmianą istniejącej
konfiguracji wykonaj kopię HA. Ta wersja nie przenosi starych sum automatycznie
i nie zmienia ustawień energetycznych domu.

## Measurement contract / Zasady pomiaru

| Source / Źródło | Input / Odczyt | Method attribute |
| --- | --- | --- |
| Q Series Cloud | Available DP1 `forward_energy_total`, scaled from Tuya metadata; it is **not** assumed to be a lifetime meter | `device_counter` |
| PRIME native LAN, split or packed telemetry | DP102 JSON field `e` divided by 10, in kWh | `session_counter` |
| Explicit mapped energy entity | Configured total counter, otherwise configured current-session counter | `device_counter` / `session_counter` |
| Power-only mapping, or Q source without a counter | Integration of available kW samples | `power_estimate` |

DP25 (last completed session) is never used as live consumption. Native PRIME
LAN uses its telemetry directly; mapped PRIME telemetry is supported for older
external-source setups. Only **one** input contributes at a time. A configured
counter becoming unavailable does not trigger a fallback to power. Mapped
`Wh`/`kWh`/`MWh` and `W`/`kW`/`MW` are normalized; explicitly incompatible units
are rejected. Unitless manual mappings retain the existing kWh/kW convention.

DP25, czyli zakończona sesja, nie jest źródłem bieżącego zużycia. Jednocześnie
liczymy tylko jedno źródło. Brak odczytu wybranego licznika nie przełącza pomiaru
na moc. Przy mapowaniu encji poprawnie przeliczamy Wh/kWh/MWh i W/kW/MW;
niezgodne jednostki są odrzucane. Ręczne mapowanie bez jednostki oznacza kWh/kW.

### Baseline, resets and gaps

- The first valid reading establishes a baseline and outputs zero. Historical
  consumption from before installation is not imported.
- Positive counter differences increase the persisted sum. Equal readings do
  not add energy. Small nonzero downward jitter keeps the high-water mark.
- A counter dropping to zero starts a new baseline without resetting the sum.
  A larger drop to a nonzero reading also rebases, but does not add that ambiguous
  reading; history is flagged incomplete. A rapid implausible increase is rejected.
- After restart/outage, a counter increase can recover an observed difference.
  If a session reset occurred unseen and the new reading exceeds the old one,
  a counter alone cannot detect it; multiple sessions during an outage cannot
  be reconstructed reliably. This can undercount energy.
- Recovery is recorded when the next sample arrives. HA may show the recovered
  delta in that later statistics interval; this version cannot attribute it to
  exact missing hours, days or prices. Do not use it for retrospective dynamic
  tariff billing.
- Power estimation uses a left sum only between uninterrupted samples no more
  than 60 seconds apart. It does not integrate across explicit outages or an HA
  restart. Missing intervals are not filled with invented energy.
- Zero power from a tester adds zero estimated energy. CP, the charge switch
  and planner state do not themselves increase this meter.
- A Cloud/LAN/entity change preserves the sum and establishes a fresh baseline,
  skipping ambiguous overlap. The meter is persisted with existing session state
  through HA Store, not in a second sample database. Each checkpoint is written
  atomically and read back from disk before a new value is published. A failed
  write makes the sensor unavailable; it cannot publish an uncommitted increase.
  Unloading waits for an in-flight write, so an old entry cannot overwrite its
  replacement. This is an application-level checkpoint, not a guarantee against
  physical disk failure. Restoring an older HA backup restores the older baseline.

Pierwszy odczyt ustala punkt początkowy: licznik zaczyna od zera, bez importu
energii sprzed instalacji. Przyrosty są sumowane, duplikaty pomijane, a reset
źródła nie zeruje sumy. Po spadku do niezerowej wartości nie doliczamy jej
automatycznie — dane mogą być niepełne. Po przerwie odtwarzamy tylko możliwą
do odczytania różnicę licznika. Niewidocznych resetów i sesji nie da się pewnie
odtworzyć. Odzyskany przyrost HA zapisuje przy kolejnym odczycie, niekoniecznie
w godzinie rzeczywistego zużycia. Moc jest całkowana wyłącznie pomiędzy
nieprzerwanymi próbkami oddalonymi o maksymalnie 60 sekund. Restart lub luka
nie powodują dopisywania domniemanej energii. Zmiana źródła zachowuje sumę,
ale wyznacza nowy punkt odniesienia. Nowa wartość jest publikowana dopiero po
atomowym zapisie i sprawdzeniu pliku. Błąd zapisu oznacza niedostępność sensora,
bez publikowania niezapisanego przyrostu. Przeładowanie integracji czeka na
zakończenie zapisu. Nie jest to ochrona przed fizyczną awarią dysku; odtworzenie
starszego backupu HA przywraca także starszy stan licznika.

Energy reported by the EVSE is not net energy stored in the battery. These are
software accounting rules, not calibration evidence: nonzero PRIME measurements
and energy-target cutoff still require a loaded vehicle test. Cloud online flags
do not guarantee that every cached DP is fresh; upstream delays and corrections
limit accuracy. The meter does not send commands or change charging control.

Energia raportowana przez EVSE nie jest energią netto w baterii. Testy oprogramowania
nie potwierdzają kalibracji pomiarów. PRIME nadal wymaga próby pod obciążeniem
w celu sprawdzenia niezerowych pomiarów i odcięcia po celu kWh. Dane z chmury mogą
przychodzić z opóźnieniem. Nowy licznik nie wysyła komend do ładowarki.

## Diagnostics and storage recovery

The sensor exposes four bounded attributes: `measurement_method`, `data_quality`,
`incomplete_history` and `recording_since` (UTC). No sample archive or device
credentials are included. `incomplete_history` remains true once a known gap,
rebase, source change or rejected spike occurs; it is a warning, not a quantified
error bound. `data_quality` describes the latest processing result, not a
certification of the whole history. Unknown/corrupt saved meter formats produce
`storage_error` and an unavailable sensor instead of silently starting over;
restore a compatible backup before continuing. Do not delete Recorder statistics
as a way to repair the integration's stored state.

Atrybuty określają metodę, wynik ostatniego przetworzenia, znaną niepełność
historii i czas rozpoczęcia zapisu (UTC). Znacznik niepełności pozostaje aktywny
po wykryciu problemu; nie określa wielkości błędu. `storage_error` oznacza brak
możliwości odczytania zapisanego licznika — przywróć zgodny backup integracji,
zamiast zerować statystyki HA.

## Architecture

Recorder owns time-series storage and long-term statistics. The integration
persists only an accumulator and its baseline per config entry. Energy dashboard
configuration is explicit, not automatically overwritten. Utility Meter is
optional if a user also wants daily/monthly helper entities; it is not required
for the Energy dashboard and is not a new integration dependency.

References: [individual devices](https://www.home-assistant.io/docs/energy/individual-devices/),
[sensor state classes](https://developers.home-assistant.io/docs/core/entity/sensor/),
[Recorder](https://www.home-assistant.io/integrations/recorder/),
[Utility Meter](https://www.home-assistant.io/integrations/utility_meter/).
