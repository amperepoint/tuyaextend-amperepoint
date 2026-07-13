# AmperePoint Q22 Home Assistant reference map

## Status dokumentu

To jest aktualna referencyjna mapa integracji dla 3-fazowej ladowarki
AmperePoint AC EV Mode 3 Type 2 / Q22 pracujacej w ekosystemie Tuya.

Dokument rozdziela dwie rzeczy:

- stan sprzetu i definicje DP w Tuya,
- stan faktycznie potwierdzony w Home Assistant / Tuya Local.

Ladowarka jest urzadzeniem 3-fazowym. Datapointy fazowe DP6, DP7 i DP8 sa
zdefiniowane w produkcie Tuya jako fazy L1/L2/L3. W aktualnych testach Q22 OTA
potwierdzono dekodowanie napiecia L1 z surowego DP6, ale standardowy
Home Assistant / Xtend nie tworzy jeszcze z tego gotowej encji fazowej.

## Model

| Parametr | Wartosc |
| --- | --- |
| Producent | AmperePoint |
| Typ urzadzenia | AC EV Mode 3 Type 2 |
| Seria | Q |
| Model referencyjny | Q22 |
| Fazy sprzetowe | 3 |
| Platforma IoT | Tuya |
| Local protocol | Tuya LAN 3.5 |
| Local port | TCP 6668 |
| Home Assistant | Tuya Local / LocalTuya / AmperePoint HACS |

Do lokalnej konfiguracji wymagane sa:

- adres IP ladowarki w sieci lokalnej,
- Device ID,
- Local Key,
- protokol Tuya LAN `3.5`.

Oficjalna integracja Tuya w Home Assistant pokazuje tylko podstawowe sterowanie
i nie jest pelna integracja dla tego modelu ladowarki.

## Potwierdzony stan integracji

W testach Q22 OTA potwierdzono odczyt i/lub sterowanie nastepujacych DP:

```text
1, 3, 4, 9, 10, 13, 14, 18, 24, 25
```

Wymuszone odczyty lokalne tych DP nie zwrocily uzytecznego payloadu w stanie
oczekiwania/pauzy:

```text
6, 7, 8, 19, 23, 33
```

Oznacza to, ze DP6/DP7/DP8 sa czescia definicji produktu. Surowy payload fazowy
zostal potwierdzony w Tuya API dla wszystkich trzech faz, ale standardowy HA /
Xtend nadal nie tworzy z niego gotowych encji fazowych.

## Datapoint map

| DP | Identifier | Typ | Kierunek | Jednostka | Status HA | Znaczenie |
| --- | --- | --- | --- | --- | --- | --- |
| `1` | `forward_energy_total` | value | report | `kWh`, scale `2` | potwierdzone | Calkowity licznik energii |
| `3` | `work_state` | enum | report | n/a | potwierdzone | Status pracy ladowarki |
| `4` | `charge_cur_set` | value | send/report | `A`, scale `0` | potwierdzone | Limit pradu ladowania |
| `6` | `phase_a` | raw | report | 7 bajtow | potwierdzone w raw API, brak encji HA | Dane fazy L1 |
| `7` | `phase_b` | raw | report | 7 bajtow | potwierdzone w raw API, brak encji HA | Dane fazy L2 |
| `8` | `phase_c` | raw | report | 7 bajtow | potwierdzone w raw API, brak encji HA | Dane fazy L3 |
| `9` | `power_total` | value | report | `kW`, scale `3` | potwierdzone | Moc calkowita |
| `10` | `fault` | fault | report | bitfield | potwierdzone | Bledy i alarmy |
| `13` | `connection_state` | enum | report | n/a | potwierdzone | Stan podlaczenia auta / CP |
| `14` | `work_mode` | enum | send/report | n/a | potwierdzone | Tryb pracy |
| `17` | `energy_charge` | value | send/report | `kWh`, scale `0` | zdefiniowane, widoczne w cloud dump | Docelowa energia ladowania |
| `18` | `switch` | bool | send/report | n/a | potwierdzone | Start / stop ladowania |
| `19` | `local_timer` | raw | send/report | raw | zdefiniowane, niepotwierdzone w HA | Harmonogram ladowania |
| `23` | `system_version` | string | report | n/a | zdefiniowane, niepotwierdzone w HA | Wersja systemu / firmware |
| `24` | `temp_current` | value | report | `C`, scale `0` | potwierdzone | Temperatura ladowarki |
| `25` | `charge_energy_once` | value | report | `kWh`, scale `2` | potwierdzone | Energia ostatniej zakonczonej sesji ladowania |
| `33` | `mode_set` | raw | send/report | raw | zdefiniowane, niepotwierdzone w HA | Dodatkowe ustawienia trybu |

## Status ladowarki

DP3 `work_state`:

| Wartosc Tuya | Znaczenie w HA |
| --- | --- |
| `charger_free` | Gotowy |
| `charger_insert` | Auto podlaczone |
| `charger_free_fault` | Blad |
| `charger_wait` | Gotowy / oczekiwanie |
| `charger_charging` | Ladowanie |
| `charger_pause` | Wstrzymane |
| `charger_end` | Zakonczone |
| `charger_fault` | Blad |

DP13 `connection_state`:

| Wartosc Tuya | Znaczenie w HA |
| --- | --- |
| `controlpi_12v` | Gotowy |
| `controlpi_12v_pwm` | Gotowy |
| `controlpi_9v` | Auto wykryte |
| `controlpi_9v_pwm` | Auto podlaczone |
| `controlpi_6v` | Gotowy do ladowania |
| `controlpi_6v_pwm` | Ladowanie |
| `controlpi_error` | Blad CP |

DP14 `work_mode`:

| Wartosc Tuya | Znaczenie |
| --- | --- |
| `charge_now` | Ladowanie natychmiastowe |
| `charge_energy` | Ladowanie do zadanej energii |
| `charge_schedule` | Ladowanie wedlug harmonogramu |

## Fazy

Stan faktyczny dla faz:

| Element | Status |
| --- | --- |
| Sprzet Q22 | 3-fazowy |
| DP6 `phase_a` | zdefiniowany w produkcie Tuya |
| DP7 `phase_b` | zdefiniowany w produkcie Tuya |
| DP8 `phase_c` | zdefiniowany w produkcie Tuya |
| Odczyt DP6/DP7/DP8 w surowym Tuya API | potwierdzone napiecie, prad i moc dla L1/L2/L3 |
| Odczyt DP6/DP7/DP8 jako gotowe encje HA / Xtend | niepotwierdzone w aktualnych testach |
| Gotowe encje fazowe w HACS | nieaktywne produkcyjnie; mozna pokazac w diagnostyce |

Docelowo DP6, DP7 i DP8 powinny reprezentowac:

| DP | Faza | Dane docelowe |
| --- | --- | --- |
| `6` | L1 | napiecie, prad, moc |
| `7` | L2 | napiecie, prad, moc |
| `8` | L3 | napiecie, prad, moc |

Te encje powinny pozostac opcjonalne do momentu przechwycenia poprawnego payloadu
w trakcie aktywnego ladowania:

| DP | Docelowe encje HA |
| --- | --- |
| `6` | `sensor.<device>_napiecie_l1`, `sensor.<device>_prad_l1`, `sensor.<device>_moc_l1` |
| `7` | `sensor.<device>_napiecie_l2`, `sensor.<device>_prad_l2`, `sensor.<device>_moc_l2` |
| `8` | `sensor.<device>_napiecie_l3`, `sensor.<device>_prad_l3`, `sensor.<device>_moc_l3` |

Potwierdzony parser 7-bajtowego payloadu fazowego:

| Bajty | Pole | Skala |
| --- | --- | --- |
| `0..1` | napiecie, unsigned big-endian | `/10 V` |
| `2..4` | prad, unsigned big-endian | `/1000 A` |
| `5..6` | moc fazy, unsigned big-endian | `/1000 kW` |

Przyklady z Q22_13072026:

```text
phase_a = CNQAAAAAAA==
hex     = 08 d4 00 00 00 00 00
L1 V    = 0x08d4 / 10 = 226.0 V

phase_a = CJgAKvgJdA==
hex     = 08 98 00 2a f8 09 74
L1      = 220.0 V, 11.000 A, 2.420 kW

phase_b = CKwAKvgJig==
hex     = 08 ac 00 2a f8 09 8a
L2      = 222.0 V, 11.000 A, 2.442 kW

phase_c = CJgAKvgJdA==
hex     = 08 98 00 2a f8 09 74
L3      = 220.0 V, 11.000 A, 2.420 kW

suma faz = 7.282 kW = DP9 power_total 7282 / 1000
```

W aktualnym dashboardzie produkcyjnym nie nalezy prezentowac faz jako pewnych
danych pomiarowych. Mozna je pokazac w widoku diagnostycznym jako encje do
walidacji.

## Home Assistant mapping

| Funkcja w HA | DP | Identifier | Status |
| --- | --- | --- | --- |
| Status ladowania | `3` | `work_state` | potwierdzone |
| Auto podlaczone | `13` | `connection_state` | potwierdzone |
| Start / stop | `18` | `switch` | potwierdzone |
| Limit pradu | `4` | `charge_cur_set` | potwierdzone |
| Tryb ladowania | `14` | `work_mode` | potwierdzone |
| Moc calkowita | `9` | `power_total` | potwierdzone |
| Energia calkowita | `1` | `forward_energy_total` | potwierdzone |
| Energia biezacej sesji | delta z `1` | `forward_energy_total` | liczona jako roznica od startu sesji |
| Energia ostatniej sesji | `25` | `charge_energy_once` | potwierdzone |
| Temperatura | `24` | `temp_current` | potwierdzone |
| Bledy | `10` | `fault` | potwierdzone |
| Napiecie/prad/moc L1 | `6` | `phase_a` | parser potwierdzony w raw API, brak gotowej encji HA |
| Napiecie/prad/moc L2 | `7` | `phase_b` | parser potwierdzony w raw API, brak gotowej encji HA |
| Napiecie/prad/moc L3 | `8` | `phase_c` | parser potwierdzony w raw API, brak gotowej encji HA |
| Harmonogram | `19` | `local_timer` | docelowe, niepotwierdzone w HA |
| Wersja firmware | `23` | `system_version` | docelowe, niepotwierdzone w HA |
| Ustawienia trybu | `33` | `mode_set` | docelowe, niepotwierdzone w HA |

## Zalecane encje AmperePoint HACS

Dedykowana integracja AmperePoint HACS powinna wystawiac uzytkownikowi
ustandaryzowany model EVSE, niezaleznie od surowych nazw DP Tuya.

Encje potwierdzone / produkcyjne:

| Encja HACS | Zrodlo |
| --- | --- |
| `sensor.amperepoint_<device>_status` | DP3 |
| `binary_sensor.amperepoint_<device>_auto_podlaczone` | DP13 |
| `sensor.amperepoint_<device>_moc` | DP9 |
| `sensor.amperepoint_<device>_energia_calkowita` | DP1 |
| `sensor.amperepoint_<device>_energia_sesji` | delta z DP1 |
| `sensor.amperepoint_<device>_energia_ostatniej_sesji` | DP25 |
| `sensor.amperepoint_<device>_koszt_sesji` | energia sesji * taryfa |
| `sensor.amperepoint_<device>_taryfa` | stawka lokalna lub encja taryfy |
| `sensor.amperepoint_<device>_blad` | DP10 |
| `number.amperepoint_<device>_limit_pradu` | DP4 |
| `switch.amperepoint_<device>_ladowanie` | DP18 |

Encje docelowe / diagnostyczne, niepotwierdzone w aktualnym odczycie Q22:

| Encja HACS | Zrodlo |
| --- | --- |
| `sensor.amperepoint_<device>_liczba_faz` | wyliczane z L1/L2/L3 po potwierdzeniu faz |
| `sensor.amperepoint_<device>_napiecie_l1` | DP6 |
| `sensor.amperepoint_<device>_napiecie_l2` | DP7 |
| `sensor.amperepoint_<device>_napiecie_l3` | DP8 |
| `sensor.amperepoint_<device>_prad_l1` | DP6 |
| `sensor.amperepoint_<device>_prad_l2` | DP7 |
| `sensor.amperepoint_<device>_prad_l3` | DP8 |

## Energia i koszt sesji

Referencyjny model liczenia energii:

1. DP1 `forward_energy_total` jest glownym licznikiem energii.
2. Energia sesji jest liczona jako roznica miedzy aktualnym DP1 a zapisana
   wartoscia bazowa z poczatku sesji.
3. DP25 `charge_energy_once` jest wystawiany jako energia ostatniej zakonczonej
   sesji ladowania, a nie jako aktywny licznik biezacej sesji.
4. Koszt sesji jest liczony jako:

```text
koszt_sesji = energia_sesji_kwh * stawka_za_kwh
```

Integracja AmperePoint HACS obsluguje:

- stala stawke za kWh,
- walute,
- wskazanie zewnetrznej encji Home Assistant jako aktualnej stawki energii.

Taryfy godzinowe sa rozszerzeniem modelu i powinny korzystac z tej samej encji
energii sesji.

## DP102

DP102 `x_metrics` nie jest wymagany do aktualnej integracji Q22 opisanej w tym
dokumencie. Model Q22 jest mapowany na podstawie standardowych DP:

```text
1, 3, 4, 9, 10, 13, 14, 18, 24, 25
```

DP6, DP7 i DP8 sa potwierdzone jako surowe zrodla danych fazowych w Tuya API.
DP19, DP23 i DP33 pozostaja w definicji produktu jako datapointy docelowe, ale
nie sa potwierdzone jako gotowe zrodla danych w aktualnym odczycie Home
Assistant / Tuya Local.

## Minimalny dashboard HA

Dashboard produkcyjny powinien pokazywac dane potwierdzone:

```text
AmperePoint Q22
Status: Ladowanie
Auto: podlaczone
Moc: 10.8 kW
Energia sesji: 14.2 kWh
Koszt sesji: 17.04 PLN

[ Start / Stop ]

Limit pradu:
[ 6 A ----- 16 A ]

Wykres mocy z ostatnich 6 h
Wykres energii dziennej
Wykres kosztow miesiecznych
```

Parametry fazowe powinny byc pokazane dopiero po potwierdzeniu odczytu DP6/DP7/DP8:

```text
Napiecie L1: 231 V
Napiecie L2: 229 V
Napiecie L3: 232 V
Prad L1: 15.7 A
Prad L2: 15.8 A
Prad L3: 15.6 A
```

Do czasu walidacji faz taki blok moze byc dostepny tylko w widoku diagnostycznym.

## Pliki projektu

| Element | Plik |
| --- | --- |
| Profil Tuya Local | `profiles/tuya_local/amperepoint_q22_ota_evcharger.yaml` |
| Techniczna mapa DP | `docs/q22-ota-dp-map.md` |
| Mapa produktu | `docs/product-cu111poj2mtikvls-q22-ota.md` |
| Mapa urzadzenia testowego | `docs/device-<device_id_q22_ota_legacy>.md` |
| Dashboard testowy | `dashboards/q22-ota-ha-test.yaml` |
