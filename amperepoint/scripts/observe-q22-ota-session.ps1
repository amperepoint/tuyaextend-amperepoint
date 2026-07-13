param(
    [int]$Samples = 720,
    [int]$IntervalSeconds = 5,
    [string]$Container = "homeassistant",
    [string]$OutputCsv = "observations/q22-ota-session.csv"
)

$ErrorActionPreference = "Stop"

if ($Samples -lt 1) {
    throw "Samples must be at least 1."
}

if ($IntervalSeconds -lt 1) {
    throw "IntervalSeconds must be at least 1."
}

$python = @'
import csv
import datetime
import os
import sqlite3
import sys
import time
import zoneinfo

SAMPLES = int(os.environ.get("SAMPLES", "720"))
INTERVAL_SECONDS = int(os.environ.get("INTERVAL_SECONDS", "5"))
TZ = zoneinfo.ZoneInfo(os.environ.get("TZ_NAME", "Europe/Warsaw"))

ENTITIES = {
    "local_status": "sensor.q22_ota_status",
    "local_connection": "sensor.q22_ota_connection",
    "local_power_kw": "sensor.q22_ota_moc",
    "local_total_energy_kwh": "sensor.q22_ota_energia",
    "local_last_session_kwh": "sensor.q22_ota_last_session_energy",
    "local_problem": "binary_sensor.q22_ota_problem",
    "local_temperature_c": "sensor.q22_ota_temperatura_2",
    "local_current_limit_a": "number.q22_ota_charging_current_2",
    "local_switch": "switch.q22_ota",
    "local_voltage_a_v": "sensor.q22_ota_napiecie_a",
    "local_current_a_a": "sensor.q22_ota_prad_a",
    "local_phase_power_a_kw": "sensor.q22_ota_moc_a",
    "cloud_work_state": "sensor.q22_ota_work_state",
    "cloud_connection_state": "sensor.q22_ota_connection_state",
    "cloud_power_kw": "sensor.q22_ota_total_power",
    "cloud_total_energy_kwh": "sensor.q22_ota_total_energy",
    "cloud_once_energy_kwh": "sensor.q22_ota_charge_energy_single",
    "cloud_daily_energy_kwh": "sensor.q22_ota_daily_total_energy",
    "cloud_monthly_energy_kwh": "sensor.q22_ota_monthly_total_energy",
    "cloud_yearly_energy_kwh": "sensor.q22_ota_yearly_total_energy",
    "cloud_current_limit_a": "number.q22_ota_charging_current",
    "cloud_switch_xtend": "switch.q22_ota_switch",
    "cloud_switch_tuya": "switch.q22_ota_switch",
    "cloud_temperature_c": "sensor.q22_ota_temperatura",
    "hacs_status": "sensor.amperepoint_q22_ota_status",
    "hacs_connected": "binary_sensor.amperepoint_q22_ota_auto_podlaczone",
    "hacs_complete": "binary_sensor.amperepoint_q22_ota_ladowanie_zakonczone",
    "hacs_power_kw": "sensor.amperepoint_q22_ota_moc",
    "hacs_total_energy_kwh": "sensor.amperepoint_q22_ota_energia_calkowita",
    "hacs_session_energy_kwh": "sensor.amperepoint_q22_ota_energia_sesji",
    "hacs_cost": "sensor.amperepoint_q22_ota_koszt_sesji",
    "hacs_tariff": "sensor.amperepoint_q22_ota_taryfa",
    "hacs_phase_count": "sensor.amperepoint_q22_ota_liczba_faz",
    "hacs_current_limit_a": "number.amperepoint_q22_ota_limit_pradu",
    "hacs_switch": "switch.amperepoint_q22_ota_ladowanie",
    "hacs_voltage_l1_v": "sensor.amperepoint_q22_ota_napiecie_l1",
    "hacs_current_l1_a": "sensor.amperepoint_q22_ota_prad_l1",
}

FIELDS = ["sample", "observed_at"] + list(ENTITIES)


def latest_values():
    con = sqlite3.connect("/config/home-assistant_v2.db", timeout=5)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    values = {}
    for key, entity_id in ENTITIES.items():
        row = cur.execute(
            """
            select s.state
            from states s
            join states_meta sm on sm.metadata_id = s.metadata_id
            where sm.entity_id = ?
            order by s.state_id desc
            limit 1
            """,
            (entity_id,),
        ).fetchone()
        values[key] = row["state"] if row else ""
    con.close()
    return values


writer = csv.writer(sys.stdout, lineterminator="\n")
writer.writerow(FIELDS)
sys.stdout.flush()

for sample in range(1, SAMPLES + 1):
    values = latest_values()
    observed_at = datetime.datetime.now(TZ).isoformat(timespec="seconds")
    writer.writerow([sample, observed_at] + [values.get(field, "") for field in ENTITIES])
    sys.stdout.flush()
    if sample < SAMPLES:
        time.sleep(INTERVAL_SECONDS)
'@

$dockerArgs = @(
    "-e", "SAMPLES=$Samples",
    "-e", "INTERVAL_SECONDS=$IntervalSeconds",
    "-e", "TZ_NAME=Europe/Warsaw"
)

if ($OutputCsv) {
    $parent = Split-Path -Parent $OutputCsv
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent | Out-Null
    }
    $python | docker exec -i @dockerArgs $Container python3 - | Tee-Object -FilePath $OutputCsv
    Write-Host "Saved Q22 OTA session observation CSV to $OutputCsv"
} else {
    $python | docker exec -i @dockerArgs $Container python3 -
}
