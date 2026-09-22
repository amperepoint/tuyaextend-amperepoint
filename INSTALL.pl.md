# Instalacja — Ampere Point Q Series i Wallbox PRIME

## Wybierz połączenie

| Seria | Zalecana ścieżka | Wymagania |
| --- | --- | --- |
| Q Series | Tuya Cloud + AmperePoint | Oficjalna integracja Tuya w HA, internet |
| Wallbox PRIME | Wbudowany AmperePoint Local (LAN) | Device ID, local key, sieć LAN i zgodny firmware |

Dla **Q Series zalecamy Tuya Cloud**: w obecnej integracji zapewnia szerszy
obsługiwany zakres DP i funkcji niż nasze profile lokalne. AmperePoint odczytuje
również DP z runtime Tuya, dla których oficjalna integracja nie utworzyła encji.
Zakres zależy od generacji i firmware — nie gwarantujemy wszystkich DP ani
pomiarów faz każdego modelu. Xtend Tuya nie jest wymagany.

Dla **PRIME lokalny protokół Tuya jest obsługiwany bezpośrednio przez nasze repo**.
Nie trzeba instalować osobnego Tuya Local ani LocalTuya. Oficjalna integracja
Tuya może posłużyć do importu danych połączenia, ale nie jest wymagana do pracy LAN.

## 1. Instalacja przez HACS

1. HACS → menu → **Repozytoria niestandardowe**.
2. Dodaj `https://github.com/amperepoint/tuyaextend-amperepoint`, kategoria **Integracja**.
3. Pobierz **TuyaExtend AmperePoint** i zrestartuj Home Assistant.
4. Otwórz **Ustawienia → Urządzenia i usługi → Dodaj integrację → AmperePoint**.
5. Wybierz ścieżkę właściwą dla swojej serii.

Samo pobranie plików w HACS nie uruchamia konfiguracji urządzenia.

## 2A. Q Series — Tuya Cloud

1. Dodaj ładowarkę do Tuya Smart lub Smart Life.
2. W HA dodaj oficjalną integrację **Tuya**, podaj User Code z ustawień konta
   aplikacji i przejdź autoryzację QR zgodnie z [instrukcją HA](https://www.home-assistant.io/integrations/tuya/).
3. Sprawdź, czy ładowarka jest widoczna w urządzeniach Tuya w HA.
4. W AmperePoint wybierz **Skonfiguruj wykrytą ładowarkę**.
5. Wybierz urządzenie, ustaw taryfę i zatwierdź.

Ta ścieżka nie wymaga local key ani osobnego konta Tuya Developer do autoryzacji
oficjalnej integracji HA. Jeśli urządzenia nie widać, przeładuj Tuya i sprawdź
nazwę/model, np. `Ampere Point Q Series`.

Dostępne dla danego produktu funkcje obejmują start/stop, prąd, tryby, cel energii,
planer, pomiary i diagnostykę. Zapis działa tylko dla DP udostępnionych jako
zapisywalne. DP opisany w schemacie produktu nie zawsze jest przekazywany przez chmurę.

## 2B. Wallbox PRIME — AmperePoint Local (LAN)

1. Zapewnij łączność HA z ładowarką; zalecana jest rezerwacja DHCP w routerze.
2. W kreatorze AmperePoint wybierz **AmperePoint Local (LAN)**.
3. Wybierz import danych z już autoryzowanej integracji Tuya albo konfigurację ręczną.
4. Podaj nazwę, **Device ID**, **local key**, IP i protokół (na testowanych PRIME: **3.5**).
5. Puste IP uruchamia wykrywanie. Docker/VLAN może wymagać ręcznego IP i zapewnienia ruchu LAN.
6. Kreator sprawdzi urządzenie i pokaże zakres: sterowanie albo tylko odczyt.
7. Zatwierdź i otwórz **Ampere Point - Tuya dashboard**.

**Device ID nie jest PID-em.** Device ID identyfikuje konkretną ładowarkę i jest
potrzebny do połączenia. PID identyfikuje produkt i pojawia się w stopce diagnostycznej.

Local key jest tajnym kluczem urządzenia. Jeśli import go nie udostępnia,
uzyskaj go przez autoryzowane narzędzia konta Tuya. Ręczne pobranie może wymagać
konta Tuya Developer, projektu Cloud i powiązania konta aplikacji. Nasz kreator
nie tworzy takiego projektu ani nie loguje do Tuya Developer. Ponowne parowanie
może zmienić local key.

### Zakres PRIME w 0.5.38

Profile wybierane są według DP i firmware, nie samej nazwy, mocy czy PID.

| Funkcja | Zakres |
| --- | --- |
| Odczyty LAN | Moc, energia sesji, temperatura, status, firmware i dostępne wartości techniczne |
| Start/stop | Zweryfikowane profile split `(V7.0.0)F2.0.0` i packed `(V8.0.7)F1.3.6` |
| Prąd | Co 1 A, maksymalnie 16 A i nie powyżej limitu instalacji DP152 |
| Tryby | Ładuj teraz, do zadanej energii, według harmonogramu — wykonywane przez HA |
| Planer | Wiele dni/przedziałów, dokładność minutowa, prąd na przedział, override, następna akcja |
| Komendy | Potwierdzane niezależnym odczytem; sam ACK nie oznacza sukcesu |
| Restart | Zapis planu/ustawień i odtworzenie połączenia LAN |

Packed zweryfikowano z limitem instalacji 16 A; inny limit lub nieznany firmware
może pozostawić urządzenie tylko do odczytu. Split też jest ograniczony do 16 A.
Nie deklarujemy pełnego zakresu sterowania każdą wersją PRIME 11/22 kW.

**Planer działa w HA, nie w pamięci ładowarki.** HA musi działać i mieć połączenie
również przy zatrzymaniu lub osiągnięciu celu kWh. Pozostaw urządzenie w natywnym
trybie natychmiastowym, z wyłączonym własnym harmonogramem. Nie uruchamiaj
konkurencyjnego sterowania w Tuya lub innych integracjach. Nie zapisujemy DP151,
DP152 ani parametrów zabezpieczeń.

Start/stop, prąd i przedział harmonogramu potwierdzono na testerach EVSE bez poboru
mocy. Dokładność pomiarów i odcięcie po zadanych kWh wymagają testu z autem.
Brak odczytu CP nie oznacza odłączonego auta.
[Raport testów packed](amperepoint/docs/prime-packed-local-controls-20260911.md).

## 3. Panel i ustawienia

Jeden panel **Ampere Point - Tuya dashboard** obsługuje Q Cloud i PRIME LAN.
Przy kilku urządzeniach wybierasz ładowarkę w nagłówku. Każdy wpis ma osobną
konfigurację i planer.

**Ustawienia integracji** w stopce prowadzą do właściwego wpisu HA. W opcjach LAN
można zmienić IP, klucz i protokół oraz ponownie sprawdzić zweryfikowane sterowanie.
Nie trzeba usuwać istniejącego wpisu tylko do odczytu. Stopka pokazuje źródło, PID
i wersję dashboardu.

Kartę można dodać do własnego panelu:

```yaml
type: custom:amperepoint-q22-card
entityPrefix: amperepoint_q_series
```

Nazwa techniczna karty pozostaje dla zgodności — obsługuje także PRIME.
W YAML Lovelace dodaj zasób typu `module`:
`/tuyaextend_amperepoint/frontend/amperepoint-q22-card.js`.

## 4. Aktualizacje i migracja

HACS udostępnia nowe opublikowane wydanie po sprawdzeniu aktualizacji.
Sam commit na GitHub nie instaluje niczego u użytkowników. Zrób kopię HA,
zainstaluj aktualizację w HACS, zrestartuj HA i odśwież przeglądarkę.
Sprawdź zgodność wersji karty/backendu w stopce.

Przechodząc z osobnego Tuya Local, zachowaj dane połączenia i sprawdź zależne
automatyzacje. Wyłącz konkurencyjne połączenie LAN przed uruchomieniem naszego.
Kreator może przełączyć pasujący wpis AmperePoint na LAN, zachowując encje
i wstrzymując poprzedni planer. Nie usuwaj wpisów bez sprawdzenia zależności.

Xtend Tuya, Tuya Local i LocalTuya pozostają opcjonalnymi źródłami dla wcześniejszych
konfiguracji, ale nie są zależnościami wbudowanego PRIME LAN.

## 5. Panel Energia

W aktualizacji z nowym licznikiem (`0.5.39`) rozwiń **Energia
w Home Assistant** nad stopką panelu AmperePoint. Dodaj wskazaną encję **Energia
ładowania** jako poszczególne urządzenie w ustawieniach Energii HA. Recorder musi
ją zapisywać. Każdą fizyczną ładowarkę dodaj tylko raz.

Przy aktualizacji zastąp starsze encje energii sesji/źródłowej nową — nie dodawaj
obu. Nie scalamy ani nie usuwamy starszych statystyk. Nowa encja zaczyna od zera
i jest niezależna od wskazania aktualnej sesji.
[Pełna instrukcja: źródła, luki, resety, restart i migracja](amperepoint/docs/home-assistant-energy.md).

## Problemy i bezpieczeństwo

- **Brak PRIME w Cloud:** użyj ścieżki LAN; nie oczekuj pełnej telemetrii PRIME z chmury.
- **Błąd LAN:** sprawdź IP, klucz, protokół, sieć i inne aktywne klienty LAN.
- **Tylko odczyt:** sprawdź firmware i DP; nie wymuszaj profilu innego urządzenia.
- **Brak faz:** zakres zależy od źródła; brakujących pomiarów nie zastępujemy fikcyjnymi.
- **Stara karta:** odśwież przeglądarkę z pominięciem cache.
- **Niepotwierdzona komenda:** sprawdź łączność, stan urządzenia i konkurencyjne automatyzacje.

Nie publikuj local keys, tokenów, plików HA `.storage`, danych kont ani surowych
niezanonimizowanych dumpów. Dane kart/autoryzacji są redagowane w diagnostyce.
Integracja nie zastępuje zabezpieczeń elektrycznych ani prawidłowej konfiguracji instalacji.
