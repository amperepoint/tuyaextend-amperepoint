param(
    [int]$Samples = 6,
    [int]$IntervalSeconds = 15,
    [string]$Prefix = "amperepoint_q22",
    [string]$Container = "homeassistant",
    [string]$OutputCsv = ""
)

$ErrorActionPreference = "Stop"

if ($Samples -lt 1) {
    throw "Samples must be at least 1."
}

if ($IntervalSeconds -lt 1) {
    throw "IntervalSeconds must be at least 1."
}

$python = @'
import os
import sqlite3
import time
import datetime
import zoneinfo

SAMPLES = int(os.environ.get("SAMPLES", "6"))
INTERVAL_SECONDS = int(os.environ.get("INTERVAL_SECONDS", "15"))
PREFIX = os.environ.get("ENTITY_PREFIX", "amperepoint_q22")
TZ = zoneinfo.ZoneInfo(os.environ.get("TZ_NAME", "Europe/Warsaw"))

ENTITIES = {
    "status": f"sensor.{PREFIX}_status",
    "connected": f"binary_sensor.{PREFIX}_auto_podlaczone",
    "power_kw": f"sensor.{PREFIX}_moc",
    "session_energy_kwh": f"sensor.{PREFIX}_energia_sesji",
    "total_energy_kwh": f"sensor.{PREFIX}_energia_calkowita",
    "session_cost": f"sensor.{PREFIX}_koszt_sesji",
    "phase_count": f"sensor.{PREFIX}_liczba_faz",
    "current_limit_a": f"number.{PREFIX}_limit_pradu",
    "voltage_l1_v": f"sensor.{PREFIX}_napiecie_l1",
    "voltage_l2_v": f"sensor.{PREFIX}_napiecie_l2",
    "voltage_l3_v": f"sensor.{PREFIX}_napiecie_l3",
    "current_l1_a": f"sensor.{PREFIX}_prad_l1",
    "current_l2_a": f"sensor.{PREFIX}_prad_l2",
    "current_l3_a": f"sensor.{PREFIX}_prad_l3",
    "error": f"sensor.{PREFIX}_blad",
}

def latest_values():
    con = sqlite3.connect("/config/home-assistant_v2.db", timeout=5)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    values = {}
    for key, entity_id in ENTITIES.items():
        row = cur.execute(
            """
            select s.state, s.last_updated_ts
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

fields = ["sample", "observed_at"] + list(ENTITIES)
print(",".join(fields), flush=True)

for sample in range(1, SAMPLES + 1):
    values = latest_values()
    observed_at = datetime.datetime.now(TZ).isoformat(timespec="seconds")
    row = [str(sample), observed_at] + [str(values.get(field, "")) for field in ENTITIES]
    print(",".join(row), flush=True)
    if sample < SAMPLES:
        time.sleep(INTERVAL_SECONDS)
'@

$dockerArgs = @(
    "-e", "SAMPLES=$Samples",
    "-e", "INTERVAL_SECONDS=$IntervalSeconds",
    "-e", "ENTITY_PREFIX=$Prefix",
    "-e", "TZ_NAME=Europe/Warsaw"
)

$output = $python | docker exec -i @dockerArgs $Container python3 -

if ($OutputCsv) {
    $parent = Split-Path -Parent $OutputCsv
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent | Out-Null
    }
    $output | Set-Content -Encoding utf8 -Path $OutputCsv
    Write-Host "Saved observation CSV to $OutputCsv"
} else {
    $output
}
