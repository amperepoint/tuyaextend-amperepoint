param(
    [Parameter(Mandatory = $true)]
    [string] $DeviceId,

    [int] $ScanSeconds = 8
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$target = Join-Path $root ".tmp_tinytuya_host"

if (-not (Test-Path -LiteralPath $target)) {
    python -m pip install --target $target "tinytuya==1.18.0" | Out-Host
}

$env:PYTHONPATH = $target

@"
import json
import tinytuya

device_id = "$DeviceId"
scan_seconds = $ScanSeconds

devices = tinytuya.deviceScan(
    verbose=False,
    maxretry=scan_seconds,
    color=False,
    poll=False,
    forcescan=False,
    byID=True,
)

device = devices.get(device_id)
if not device:
    print(f"Device not found: {device_id}")
    print("Found devices:")
    for found_id, info in devices.items():
        print(f"- {found_id}: {info.get('ip')} product={info.get('productKey')} version={info.get('version')}")
    raise SystemExit(1)

print(json.dumps({
    "device_id": device_id,
    "ip": device.get("ip"),
    "product_id": device.get("productKey"),
    "version": device.get("version"),
    "origin": device.get("origin"),
}, indent=2))
"@ | python -
