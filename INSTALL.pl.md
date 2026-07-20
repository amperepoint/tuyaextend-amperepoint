# Instalacja

TuyaExtend AmperePoint to integracja Home Assistant dla ładowarek AmperePoint EV.
Może korzystać bezpośrednio z oficjalnej integracji Tuya albo z encji Xtend Tuya,
`tuya-local` i LocalTuya. Xtend Tuya jest opcjonalny.

Ta integracja nie zastępuje parowania Tuya. Najpierw zainicjalizuj Tuya, potem
dodaj integrację przez HACS.

## 1. Zainicjalizuj Tuya w Home Assistant

1. Dodaj ładowarkę do aplikacji Tuya Smart / Smart Life.
2. W Home Assistant przejdź do:

```text
Ustawienia -> Urządzenia i usługi -> Dodaj integrację -> Tuya
```

3. Przejdź oficjalny proces logowania Tuya / autoryzacji QR.
4. Upewnij się, że ładowarka jest widoczna w Home Assistant.
5. Wystarczy, że ładowarka i przynajmniej jedna jej encja są widoczne w Tuya.
   TuyaExtend odczyta pozostałe obsługiwane DP z runtime oficjalnej integracji,
   nawet jeżeli Home Assistant nie utworzył dla nich osobnych encji.

```text
switch
charging current / current limit
power
energy
work state / connection state
temperature
```

Dokładna lista DP zależy od generacji produktu i firmware ładowarki.

Jeśli ładowarka nie jest widoczna w oficjalnej integracji Tuya, najpierw
skonfiguruj Tuya. TuyaExtend AmperePoint nie wykryje ładowarki chmurowej, której
Home Assistant jeszcze nie widzi.

## 2. Zainstaluj przez HACS

1. Otwórz HACS w Home Assistant.
2. Przejdź do `Integrations`.
3. Otwórz menu z trzema kropkami i wybierz `Custom repositories`.
4. Dodaj repozytorium:

```text
https://github.com/amperepoint/tuyaextend-amperepoint
```

5. Wybierz kategorię:

```text
Integration
```

6. Zainstaluj `TuyaExtend AmperePoint`.
7. Zrestartuj Home Assistant.

## 3. Dodaj integrację

1. Przejdź do:

```text
Ustawienia -> Urządzenia i usługi -> Dodaj integrację
```

2. Wyszukaj:

```text
TuyaExtend AmperePoint
```

3. Na ekranie powitalnym wybierz konfigurację automatyczną albo ręczne
   przypisanie encji.
4. Wybierz wykrytą ładowarkę AmperePoint i ustaw taryfę.
5. Zapisz wpis integracji.

Integracja automatycznie tworzy jeden wspólny panel `AmperePoint` na pasku
bocznym i sama przejmuje pozostałe wykryte ładowarki Tuya jako kolejne wpisy.
Każda ładowarka pojawia się na liście rozwijanej na panelu. Kolejne
urządzenia można też dodawać ręcznie z poziomu integracji — nie tworzy to
nowych paneli, tylko dopisuje urządzenie do listy.

Integracja wykrywa modele Q Series na podstawie nazwy urządzenia Tuya, modelu i
metadanych produktu. Jeśli ładowarka nie zostanie wykryta, zmień nazwę
urządzenia w Tuya/Home Assistant tak, aby model był widoczny w nazwie, na
przykład:

```text
AmperePoint Q22 OTA
AmperePoint Q37
AmperePoint Q Series
```

Następnie przeładuj integrację Tuya albo zrestartuj Home Assistant i spróbuj
ponownie.

## 4. Otwórz panel AmperePoint

Integracja tworzy jeden panel `AmperePoint` na pasku bocznym Home Assistanta.
Nie nadpisuje ani nie zmienia istniejących dashboardów, a późniejsze zmiany w
tym panelu są zachowywane po restartach. Przy więcej niż jednej ładowarce w
nagłówku karty pojawia się lista rozwijana z wyborem urządzenia.

Zasób karty jest rejestrowany automatycznie w standardowych dashboardach
Home Assistant działających w trybie storage. Kartę można też dodać ręcznie na
dowolny własny dashboard:

```yaml
type: custom:amperepoint-q22-card
```

Dla wielu ładowarek podaj prefiks encji:

```yaml
type: custom:amperepoint-q22-card
entityPrefix: amperepoint_q22_ota
```

Możesz też podać encje jawnie:

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

Jeśli Lovelace działa w trybie YAML, dodaj zasób karty ręcznie:

```yaml
resources:
  - url: /tuyaextend_amperepoint/frontend/amperepoint-q22-card.js
    type: module
```

## 5. Co dodaje integracja

TuyaExtend AmperePoint tworzy znormalizowane encje Home Assistant, takie jak:

```text
czytelny status ładowania
stan auta / control pilot
moc ładowania
energia bieżącej sesji
energia całkowita
energia ostatniej sesji
suwak limitu prądu
wybór trybu ładowania
energia docelowa
temperatura
diagnostyka błędów
wersja systemu i pełna lista surowych DP
napięcie/prąd/moc faz, gdy odpowiednie DPS są dostępne
```

W trybie oficjalnego Tuya sterowanie DP18 `switch`, DP4 `charge_cur_set`, DP14
`work_mode` i DP17 `energy_charge` działa bez instalowania Xtend Tuya, o ile
produkt oznacza te DP jako zapisywalne.

Energia bieżącej sesji może być liczona na podstawie:

```text
delty energii całkowitej
natywnego licznika sesji
awaryjnej integracji mocy w czasie
```

Dla nowszych urządzeń w stylu Q22 OTA domyślnym kierunkiem jest delta energii
całkowitej, jeśli dostępny jest stabilny licznik całkowity.

## 6. Opcjonalne źródła Xtend i lokalne

Jeżeli Xtend Tuya jest już zainstalowany, można wybrać jego urządzenie podczas
automatycznej konfiguracji albo przypisać encje ręcznie. Ten tryb pozostaje
zgodny z wcześniejszymi konfiguracjami, ale nie jest wymagany.

Repozytorium zawiera też kandydackie profile `tuya-local`:

```text
amperepoint/profiles/tuya_local/
```

Tryb lokalny jest opcjonalny i bardziej zaawansowany. Na części ładowarek może
udostępnić lokalne DPS, ale zwykle wymaga local key urządzenia i działającej
konfiguracji lokalnej Tuya. Pierwsza publiczna ścieżka HACS jest celowo oparta
na oficjalnej integracji Tuya, bo jest prostsza dla typowych użytkowników Home
Assistant.

## Rozwiązywanie problemów

### Ładowarka nie została wykryta

- Upewnij się, że ładowarka jest widoczna w oficjalnej integracji Tuya.
- Przeładuj integrację Tuya.
- Zmień nazwę urządzenia HA tak, aby zawierała `AmperePoint`, `Q22`, `Q37` albo
  `Q Series`.
- Zrestartuj Home Assistant po instalacji integracji przez HACS.

### Brakuje danych faz

Niektóre generacje produktów Tuya definiują payloady faz w DP6/DP7/DP8, ale nie
udostępniają ich przez oficjalne API Tuya. Dashboard ukrywa sekcje faz, gdy te
wartości nie są dostępne.

### Karta się nie ładuje

- Odśwież przeglądarkę z pominięciem cache.
- Sprawdź, czy `/tuyaextend_amperepoint/frontend/amperepoint-q22-card.js` jest
  dodany jako zasób Lovelace.
- W trybie YAML Lovelace dodaj zasób ręcznie.

### Start/stop albo limit prądu nie działa

W trybie oficjalnego Tuya nie jest wymagana osobna encja źródłowa. TuyaExtend
korzysta z definicji zapisu urządzenia. Sprawdź, czy ładowarka jest online i czy
w widoku surowych DP dana pozycja ma oznaczenie `↔`. Dla źródeł Xtend/lokalnych
sterowanie wymaga poprawnego przypisania encji źródłowej.

## Bezpieczeństwo

Nie publikuj:

```text
Tuya local keys
Tuya access tokens
plików Home Assistant .storage
identyfikatorów kont
niezanonimizowanych surowych dumpów API
```
