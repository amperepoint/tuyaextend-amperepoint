param(
    [Parameter(Mandatory = $true)]
    [string] $Payload
)

$ErrorActionPreference = "Stop"

$bytes = [Convert]::FromBase64String($Payload)

if ($bytes.Length -ne 7) {
    throw "Expected a 7-byte phase payload, got $($bytes.Length) byte(s)."
}

function Read-BigEndianUInt {
    param(
        [byte[]] $Bytes,
        [int] $Offset,
        [int] $Length
    )

    $value = 0
    for ($index = 0; $index -lt $Length; $index++) {
        $value = ($value -shl 8) -bor $Bytes[$Offset + $index]
    }
    return $value
}

$voltageRaw = Read-BigEndianUInt -Bytes $bytes -Offset 0 -Length 2
$currentRaw = Read-BigEndianUInt -Bytes $bytes -Offset 2 -Length 3
$powerRaw = Read-BigEndianUInt -Bytes $bytes -Offset 5 -Length 2

[ordered]@{
    payload = $Payload
    length = $bytes.Length
    hex = (($bytes | ForEach-Object { $_.ToString("x2") }) -join " ")
    voltage_raw = $voltageRaw
    voltage_v = $voltageRaw / 10.0
    current_raw = $currentRaw
    current_a = $currentRaw / 1000.0
    power_raw = $powerRaw
    power_kw = $powerRaw / 1000.0
} | ConvertTo-Json
