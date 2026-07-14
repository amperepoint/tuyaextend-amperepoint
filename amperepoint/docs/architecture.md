# Architektura

Integracja dziala jako warstwa domenowa z adapterami zrodel. Xtend Tuya jest
obslugiwany, ale nie jest wymagany.

```text
                     +-> official Tuya runtime (pelne status/function/range DP) -+
Tuya device/account -+-> Xtend Tuya / tuya-local / LocalTuya encje ------------+-> TuyaExtend AmperePoint -> encje EVSE + panel
```

Adapter oficjalnego Tuya odczytuje obiekt urzadzenia z runtime integracji core.
Dzieki temu widzi takze DP, dla ktorych core Tuya nie utworzyl encji. Definicje
`function` i `status_range` dostarczaja typ, skale, jednostke, zakres i informacje
o mozliwosci zapisu. Aktualizacje push Tuya uruchamiaja natychmiastowe odswiezenie
znormalizowanych encji; pozostaje tez odpytywanie okresowe.

Adapter encji zachowuje dotychczasowe mapowanie. Pozwala pracowac z Xtend Tuya,
`tuya-local`, LocalTuya oraz recznie wskazanymi helperami. Mapowanie encji ma
pierwszenstwo dla jawnie wskazanych pol, a runtime oficjalnego Tuya jest
automatycznym uzupelnieniem brakujacych danych i sterowan.

W obu trybach na wyjsciu sa te same encje EVSE. Widok surowych DP pokazuje pelny
snapshot bez local key, tokenow i identyfikatorow konta.

## Dlaczego nie override `tuya`

Nadpisywanie integracji core `tuya` w `custom_components` utrudniloby aktualizacje Home Assistant i zwiekszyloby ryzyko regresji. Projekt korzysta z publicznie zaladowanego runtime wpisu Tuya, nie modyfikuje core i nie duplikuje logowania ani sekretow Tuya.
