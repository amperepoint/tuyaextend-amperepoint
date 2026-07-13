# Plan prac i debugowanie HA Docker

## Stan lokalnego srodowiska

- Home Assistant dziala w kontenerze Docker `homeassistant`.
- URL lokalny: `http://localhost:8123`.
- Wersja HA: `2026.5.4`.
- `/config` w kontenerze jest zamontowany z:

```text
<home_assistant_config>
```

- Natywna integracja Tuya jest juz skonfigurowana.
- HACS nie jest jeszcze skonfigurowany.
- `xtend_tuya` jest zainstalowany recznie jako narzedzie diagnostyczne.
- `tuya-local` jest zainstalowany recznie jako opcjonalne narzedzie lokalnego DP discovery.
- Nasza integracja jest wgrana do `custom_components/tuyaextend_amperepoint`.

## Decyzja o HACS

Na etapie debugowania realnego urzadzenia nie instalujemy jeszcze HACS. Bezposrednia instalacja przez `custom_components` daje mniej zmiennych: testujemy tylko Home Assistant, natywna Tuya i nasza integracje.

HACS wraca do planu po pierwszym potwierdzonym mapowaniu AmperePoint Q22/Q11, najlepiej gdy repo bedzie juz na GitHub i bedziemy chcieli przetestowac realna sciezke instalacji uzytkownika.

## Aktualny wynik dla urzadzenia testowego

Szczegoly sa w:

```text
docs/device-<device_id_q_series_legacy>.md
```

Najwazniejsze encje zrodlowe:

```text
switch.we1ck46_ev_switch
number.we1ck46_ev_charging_current
sensor.we1ck46_ev_charge_energy_single
sensor.we1ck46_ev_work_state
sensor.we1ck46_ev_total_power
```

Nasze encje `tuyaextend_amperepoint` zostaly utworzone i pokazaly podczas testu:

```text
Status: Ladowanie
Moc: 4.936 kW
Energia sesji: 0.04 kWh
Koszt sesji: 0.05 PLN
Limit pradu: 14 A
Ladowanie: on
```

## Opcjonalny tryb lokalny

Szczegoly researchu i procedura testu sa w:

```text
docs/local-mode-research.md
```

W skrocie: dla EVSE wybieramy najpierw `tuya-local`, bo ma profile dla product ID `bktb3jskdic1ar2t` i moze odczytac lokalne DP `6`, `7`, `8` z fazami A/B/C.

## Cel debugowania

Najpierw udowodnic, jakie encje i wartosci daje natywna Tuya dla realnego urzadzenia AmperePoint. Dopiero potem utwardzac mapowanie DP/statusow i sterowanie.

## Etap 1 - przygotowanie lokalnej instalacji

1. Skopiowac integracje do lokalnego katalogu HA:

```powershell
.\scripts\sync-to-ha.ps1
```

2. Zrestartowac Home Assistant:

```powershell
docker restart homeassistant
```

3. Sprawdzic log po starcie:

```powershell
.\scripts\ha-logs.ps1
```

4. W UI HA wejsc w `Settings -> Devices & services -> Add integration` i dodac `TuyaExtend AmperePoint`.

## Etap 2 - jutro po dodaniu urzadzenia testowego

1. Dodac ladowarke AmperePoint do aplikacji Tuya / Smart Life i upewnic sie, ze natywna integracja Tuya widzi ja w HA.
2. Spisac wszystkie encje utworzone przez Tuya dla urzadzenia.
3. Dla kazdej encji zapisac:

```text
entity_id
friendly_name
device_class
unit_of_measurement
state w idle
state po podlaczeniu auta
state podczas ladowania
state po zakonczeniu
state przy bledzie, jesli da sie bezpiecznie wywolac
```

4. W konfiguracji `TuyaExtend AmperePoint` zmapowac najpierw minimum:

```text
model
source_status
source_connected
source_power
source_current_limit
source_charge_switch
source_error
source_voltage_l1/l2/l3
source_current_l1/l2/l3
```

5. Dopiero po potwierdzeniu stanow podlaczyc koszt i taryfe.

## Etap 3 - scenariusze testowe

Minimalny zestaw testow na realnym sprzecie:

| Scenariusz | Co sprawdzamy |
| --- | --- |
| Urzadzenie idle | status, brak auta, moc 0 kW, fazy 0 |
| Auto podlaczone bez ladowania | auto podlaczone, status czytelny, moc blisko 0 |
| Start ladowania | switch start/stop, status Ladowanie, moc kW, prady faz |
| Zmiana limitu pradu | slider HA -> encja Tuya -> realna zmiana pradu |
| Koniec ladowania | auto wykrycie `charging_complete` po progu czasu |
| Odpiecie auta | reset podlaczenia i brak falszywego konca sesji |
| Dynamiczna taryfa | koszt sesji liczony z encji ceny |
| Brak encji zrodlowej | integracja nie crashuje, pokazuje `unknown`/brak danych |

## Debugowanie w HA

Najwazniejsze logi:

```powershell
docker logs --tail 200 homeassistant
Get-Content -Tail 200 ".local\home-assistant\config\home-assistant.log"
```

Logi tylko naszej integracji:

```powershell
Get-Content -Tail 300 ".local\home-assistant\config\home-assistant.log" |
  Select-String "tuyaextend_amperepoint|AmperePoint"
```

Warto dodac do `configuration.yaml` na czas debugowania:

```yaml
logger:
  default: info
  logs:
    custom_components.tuyaextend_amperepoint: debug
    homeassistant.components.tuya: debug
```

Po zmianie `configuration.yaml`:

```powershell
docker restart homeassistant
```

## Debugowanie encji Tuya

Najbezpieczniejsza metoda: w HA wejsc w `Developer tools -> States` i filtrowac po nazwie urzadzenia albo po `tuya`.

Do szybkiego zrzutu entity registry bez sekretow:

```powershell
.\scripts\dump-tuya-entities.ps1
```

Do obserwacji stanow na zywo najlepiej uzyc UI HA, bo widac zmiany natychmiast i latwo wymusic refresh.

## Kolejnosc implementacji po testach

1. Dopisac realne modele i mapowanie stanow do `models.py`.
2. Poprawic przeliczanie jednostek, jesli Tuya podaje W/Wh/mA albo wartosci skalowane.
3. Ustabilizowac wykrywanie faz na podstawie realnych pradow L1/L2/L3.
4. Dopasowac slider limitu pradu do tego, czy Tuya przyjmuje A, dziesiate A, czy DP enum.
5. Dodac testy jednostkowe dla statusow, kosztow i konca ladowania.
6. Dopiero potem przygotowac instalacje przez HACS i release `v0.1.0`.

## Kryterium gotowosci pierwszej wersji

Pierwsza wersja jest gotowa, gdy dla AmperePoint Q22 mamy potwierdzone:

- status `Ladowanie/Gotowy/Zakonczone/Blad`,
- auto podlaczone,
- moc w kW,
- energia sesji w kWh,
- koszt sesji w PLN,
- start/stop,
- limit pradu 6-32 A,
- napiecia i prady L1/L2/L3,
- wykrywanie 1/2/3 faz,
- brak bledow w logu po restarcie HA.
