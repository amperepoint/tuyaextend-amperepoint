$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$source = Join-Path $repoRoot "custom_components\tuyaextend_amperepoint"
$target = Resolve-Path (Join-Path $repoRoot "..\.local\home-assistant\config")
$customComponents = Join-Path $target "custom_components"
$destination = Join-Path $customComponents "tuyaextend_amperepoint"

New-Item -ItemType Directory -Force -Path $customComponents | Out-Null
New-Item -ItemType Directory -Force -Path $destination | Out-Null

robocopy $source $destination /MIR /XD __pycache__ .pytest_cache /XF *.pyc | Out-Null
$code = $LASTEXITCODE
if ($code -ge 8) {
    throw "robocopy failed with exit code $code"
}

Write-Host "Synced TuyaExtend AmperePoint to $destination"
