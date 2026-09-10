# DOC: deployment#tailscale-cutover
param([switch]$Activate)
$ErrorActionPreference='Stop'
$runtimeRoot='C:\ProgramData\DenHub'
$marker="$runtimeRoot\den-runtime.json"
$state=Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
if ($state.root -ne $runtimeRoot -or ($state.mode -ne 'staging' -and -not ($Activate -and $state.mode -eq 'production'))) {
    throw 'HTTPS staging requires a staging runtime or a production activation retry.'
}
$status=& 'C:\Program Files\Tailscale\tailscale.exe' status --json | ConvertFrom-Json
if ($status.BackendState -ne 'Running') { throw 'Tailscale is not connected.' }
$hostname=$status.Self.DNSName.TrimEnd('.')
if ($hostname -notmatch '^[a-z0-9-]+\.[a-z0-9-]+\.ts\.net$') { throw 'Unexpected Tailscale hostname.' }
$origin='https://'+$hostname
if ($env:DEN_PUBLIC_ORIGIN -and $env:DEN_PUBLIC_ORIGIN -ne $origin) { throw 'DEN_PUBLIC_ORIGIN does not match this Tailscale node.' }
if ($state.mode -eq 'production' -and $state.productionOrigin -ne $origin) { throw 'Activation cannot change the installed production origin.' }
$env:DEN_ENV='production'; $env:DEN_PUBLIC_ORIGIN=$origin
$env:DEN_SECRET_FILE="$runtimeRoot\secrets.json"; $env:DEN_DATA_DIR="$runtimeRoot\data"
& $state.python -B "$($state.release)\manage.py" check --deploy --fail-level WARNING
if ($LASTEXITCODE -ne 0) { throw 'Production deployment checks failed.' }
$config="$runtimeRoot\DenHub.xml"
[xml]$xml=Get-Content -LiteralPath $config -Raw
($xml.service.env | Where-Object name -eq 'DEN_ENV').value='production'
($xml.service.env | Where-Object name -eq 'DEN_PUBLIC_ORIGIN').value=$origin
Stop-Service DenHub
$xml.Save($config)
$state.mode='production'; $state.productionOrigin=$origin
$state | Add-Member -NotePropertyName stagingCopy -NotePropertyValue (-not $Activate) -Force
$state | ConvertTo-Json | Set-Content -LiteralPath $marker -Encoding UTF8
Start-Service DenHub
if ($Activate) {
    $verified=$false
    for ($attempt=0; $attempt -lt 10; $attempt++) {
        try {
            $response=Invoke-WebRequest ($origin+'/') -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) { $verified=$true; break }
        } catch { }
        Start-Sleep -Seconds 1
    }
    if (-not $verified) { throw 'HTTPS verification failed.' }
    $origin | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'live-url.txt') -Encoding ASCII
    Write-Output "Production HTTPS activated: $origin"
} else { Write-Output "Production HTTPS settings enabled against the staging database copy: $origin" }
