$ErrorActionPreference = "Stop"

docker logs --tail 200 homeassistant

$logPath = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..\..")) ".local\home-assistant\config\home-assistant.log"
if (Test-Path $logPath) {
    Write-Host ""
    Write-Host "Filtered integration log:"
    Get-Content -Tail 300 $logPath | Select-String "tuyaextend_amperepoint|AmperePoint|ERROR|WARNING"
}
