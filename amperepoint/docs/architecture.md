# Architektura

Integracja dziala jako warstwa domenowa nad natywna integracja Tuya.

```text
Tuya device -> native Tuya integration -> HA entities -> TuyaExtend AmperePoint -> readable HA entities
```

Na starcie konfiguracja jest jawna: uzytkownik wybiera model AmperePoint i wskazuje encje zrodlowe. To pozwala dzialac zanim zostanie zebrane pelne, stabilne mapowanie DP dla wszystkich wariantow sprzetu.

## Dlaczego nie override `tuya`

Nadpisywanie integracji core `tuya` w `custom_components` utrudniloby aktualizacje Home Assistant i zwiekszyloby ryzyko regresji. Ten projekt jest helperem: korzysta z danych juz obecnych w HA i dodaje czytelna warstwe encji.
