# Instalacja

TuyaExtend AmperePoint to pomocnicza integracja Home Assistant dla ładowarek
AmperePoint EV, które są już widoczne w Home Assistant przez Tuya.

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
5. Upewnij się, że dostępne są przynajmniej podstawowe encje Tuya, na przykład:

```text
switch
charging current / current limit
power
energy
work state / connection state
temperature
```

Dokładna lista encji zależy od generacji produktu Tuya oraz od tego, które DPS
Tuya udostępnia przez oficjalne API.

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

3. Wybierz wykrytą ładowarkę AmperePoint.
4. Zapisz wpis integracji.

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

## 4. Dodaj kartę Lovelace

W standardowych dashboardach Home Assistant działających w trybie storage
integracja rejestruje kartę automatycznie.

Dodaj kartę ręcznie:

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
temperatura
diagnostyka błędów
napięcie/prąd/moc faz, gdy odpowiednie DPS są dostępne
```

Energia bieżącej sesji może być liczona na podstawie:

```text
delty energii całkowitej
natywnego licznika sesji
awaryjnej integracji mocy w czasie
```

Dla nowszych urządzeń w stylu Q22 OTA domyślnym kierunkiem jest delta energii
całkowitej, jeśli dostępny jest stabilny licznik całkowity.

## 6. Opcjonalny tryb lokalny

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

Tuya musi udostępniać zapisywalne encje dla DP18 `switch` oraz DP4
`charge_cur_set`. Jeśli oficjalna integracja Tuya wystawia je tylko do odczytu
albo nie wystawia ich wcale, TuyaExtend może pokazać wartości, ale nie będzie
mógł nimi sterować.

## Bezpieczeństwo

Nie publikuj:

```text
Tuya local keys
Tuya access tokens
plików Home Assistant .storage
identyfikatorów kont
niezanonimizowanych surowych dumpów API
```
