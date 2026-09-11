# Instalacja

## Wallbox Prime: instalator profilu w aplikacji

Komunikaty kreatora dotyczą całej rodziny **Wallbox PRIME**, bez ograniczenia
do mocy lub PID. Integracja rozpoznaje też nazwę PRIME 11 kW i stosuje dla niej
limit modelu 16 A, zamiast przypisywać ją do wariantu 22 kW. Ogólna lub
niejednoznaczna nazwa PRIME nie daje domyślnie limitu 32 A.
Odczyt wersji 11 kW korzysta z tego samego dekodera, jeśli urządzenie udostępnia
zgodną telemetrię DP102. Nie jest to potwierdzenie zgodności wszystkich firmware
ani włączenie sterowania. Poniżej opisano dotychczas zweryfikowany profil.

Dla **Wallbox Prime 22 kW, PID `gbmxngploofmhbjc`, protokół LAN 3.5**
obsługiwany jest obecnie **odczyt lokalny, nie pełne sterowanie jak w Q Series**.
Inne PID i wersje firmware wymagają osobnego potwierdzenia zgodności.

Zainstaluj przez HACS zarówno AmperePoint (krok 2 poniżej), jak i
[Tuya Local](https://github.com/make-all/tuya-local), a następnie zrestartuj HA.
Tuya Local i LocalTuya to różne integracje; ten instalator wymaga **Tuya Local**.
Wybierz **Dodaj integrację → AmperePoint → Dodaj profil
Wallbox Prime (Tuya Local)**. Instalator jest także w menu **Konfiguruj**
istniejącej integracji AmperePoint. Zatwierdź instalację i uruchom ponownie HA.

Dodaj ładowarkę w Tuya Local, używając jej ID, IP, local key i protokołu 3.5.
Wybierz profil **Ampere Point Wallbox Prime 22kW (local)**, a potem automatyczną
konfigurację wykrytej ładowarki w AmperePoint. Przy błędnym dotychczasowym profilu
zachowaj dane połączenia przed ponownym dodaniem wpisu ładowarki w Tuya Local.

Dashboard odczytuje moc, energię sesji, temperaturę, pomiary faz, podłączenie
auta i czas sesji, jeśli firmware raportuje odpowiednie dane. Profil udostępnia
też diagnostykę, m.in. raportowany limit prądu i konfigurację harmonogramu;
są to odczyty, nie pola sterowania. Brak danych nie oznacza pomiaru zerowego.

**Niedostępne dla PRIME w 0.5.37:** start/stop, zmiana limitu prądu, zapis
harmonogramu i trybu ładowania, cel kWh oraz wykonywanie planu HA. Nie wymagamy
i nie zakładamy pełnej zgodności funkcji PRIME z Q Series.
Telemetria DP102 tego profilu wymaga źródła lokalnego; samo skonfigurowanie
oficjalnej integracji Tuya w HA nie wystarczy. Nie trzeba jednak dodawać
integracji chmurowej HA, aby korzystać z tej ścieżki lokalnej.

Zapewnij łączność LAN między HA i ładowarką; warto zarezerwować jej IP w DHCP.
Local key uzyskaj zgodnie z instrukcją Tuya Local. Instalator profilu nie pobiera
kluczy i nie realizuje autoryzacji konta Tuya. Nie publikuj local key ani danych konta.
Instalator nie nadpisuje innych wersji profilu.
Jeśli aktualizacja Tuya Local usunie plik, uruchom instalator ponownie.

TuyaExtend AmperePoint to integracja Home Assistant dla ładowarek AmperePoint EV.
Może korzystać bezpośrednio z oficjalnej integracji Tuya albo z encji Xtend Tuya,
`tuya-local` i LocalTuya. Xtend Tuya jest opcjonalny.

Ta integracja nie zastępuje parowania urządzenia. Poniższy krok 1 dotyczy
ścieżki chmurowej Q Series; dla PRIME użyj procedury lokalnej powyżej.

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
AmperePoint
```

3. Na ekranie powitalnym wybierz konfigurację automatyczną albo ręczne
   przypisanie encji.
4. Wybierz wykrytą ładowarkę AmperePoint i ustaw taryfę.
5. Zapisz wpis integracji.

Integracja automatycznie tworzy jeden wspólny panel `Ampere Point - Tuya dashboard` na pasku
bocznym i sama przejmuje pozostałe wykryte ładowarki Tuya jako kolejne wpisy.
Każda ładowarka pojawia się na liście rozwijanej na panelu. Kolejne
urządzenia można też dodawać ręcznie z poziomu integracji — nie tworzy to
nowych paneli, tylko dopisuje urządzenie do listy.

Przy aktualizacji integracja usuwa tylko niezmieniony panel, który starsza
wersja wygenerowała dla ładowarki. Jeśli panel był ręcznie edytowany, zostaje
zachowany, aby nie utracić zmian Lovelace.

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

Integracja tworzy jeden panel `Ampere Point - Tuya dashboard` na pasku bocznym Home Assistanta.
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

Dla PRIME zalecany jest instalator opisany na początku tej instrukcji.
Alternatywnie profil można zainstalować ręcznie:

1. Skopiuj profil z `amperepoint/profiles/tuya_local/` do
   `config/custom_components/tuya_local/devices/`.
2. Zrestartuj Home Assistant, żeby tuya-local wczytał nowy profil.
3. **Tylko gdy istniejący wpis ma błędny profil:** zachowaj dane połączenia
   i sprawdź używane encje oraz automatyzacje przed usunięciem wpisu. tuya-local pozwala
   wybrać profil urządzenia wyłącznie podczas *dodawania*; okno `Konfiguruj`
   istniejącego wpisu udostępnia tylko local key, adres IP, wersję protokołu i
   tryb odpytywania — nigdy typu urządzenia. Wpisu utworzonego z błędnym
   profilem nie da się przestawić na właściwy.
4. `Dodaj integrację` → `Tuya Local` → podaj device id, IP, local key i wersję
   protokołu (dla Prime: `3.5`). Połączenie musi się udać — przy błędzie
   formularz danych logowania wyświetla się ponownie i kreator nigdy nie
   dochodzi do wyboru profilu.
5. W kroku wyboru typu urządzenia wskaż profil ładowarki, np.
   `Ampere Point Wallbox Prime 22kW (amperepoint_prime_22kw_evcharger)`.

Aktualizacja tuya-local przez HACS może usunąć pliki z jego katalogu
`devices/`. Jeśli plik zniknie, uruchom ponownie instalator i zrestartuj HA.
Nie usuwaj poprawnie sparowanego wpisu tylko z powodu aktualizacji.

Po poprawnym dodaniu źródła lokalnego integracja AmperePoint sama rozpozna, że
to ta sama ładowarka, i dopisze mapowanie telemetrii do istniejącego wpisu —
nie powstaje drugi wpis ani drugi panel.

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
