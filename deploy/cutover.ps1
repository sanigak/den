# DOC: deployment#tailscale-cutover
$ErrorActionPreference='Stop'
$sourceRoot=Split-Path $PSScriptRoot -Parent
$runtimeRoot='C:\ProgramData\DenHub'
$marker="$runtimeRoot\den-runtime.json"
$state=Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
if ($state.root -ne $runtimeRoot -or $state.mode -ne 'production' -or -not $state.stagingCopy) {
    throw 'Cutover requires a verified production-configured staging copy.'
}
$origin=$state.productionOrigin
if ((Invoke-WebRequest $origin -UseBasicParsing -TimeoutSec 15).StatusCode -ne 200) { throw 'Private HTTPS preflight failed.' }
$legacyPid=[int](Get-Content "$sourceRoot\.hardening\legacy.pid")
$legacy=Get-CimInstance Win32_Process -Filter "ProcessId=$legacyPid"
$expectedExe="$sourceRoot\infonetenv\Scripts\python.exe"
$expectedCommand='"'+$expectedExe+'" -B manage.py runserver 0.0.0.0:8080 --noreload'
$recorded=(Get-Item "$sourceRoot\.hardening\legacy.pid").LastWriteTimeUtc
if (-not $legacy -or $legacy.ExecutablePath -ne $expectedExe -or $legacy.CommandLine -ne $expectedCommand -or
    [Math]::Abs(($legacy.CreationDate.ToUniversalTime()-$recorded).TotalSeconds) -gt 5) {
    throw 'The recorded legacy writer no longer matches; identify it before cutover.'
}
$listeners=Get-NetTCPConnection -LocalPort 8080 -State Listen
if (@($listeners).Count -ne 1) { throw 'Unrecognized legacy listener.' }
$ancestor=$listeners.OwningProcess
for ($attempt=0;$attempt -lt 8 -and $ancestor -ne $legacyPid;$attempt++) {
    $ancestor=(Get-CimInstance Win32_Process -Filter "ProcessId=$ancestor").ParentProcessId
}
if ($ancestor -ne $legacyPid) { throw 'Legacy listener is not in the recorded process tree.' }
& taskkill.exe /PID $legacyPid /T /F
if ($LASTEXITCODE -ne 0) { throw 'Could not stop the legacy writer.' }
Stop-Service DenHub
$python=$state.python
$maintenance="$runtimeRoot\tools\maintenance.py"
$legacyBackup="$runtimeRoot\backups\den-cutover-$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfff')).sqlite3"
$before=& $python -B $maintenance copy --source "$sourceRoot\infonet\db.sqlite3" --destination $legacyBackup
if ($LASTEXITCODE -ne 0) { throw 'Fresh legacy backup failed; writers remain stopped.' }
$before | Set-Content ([IO.Path]::ChangeExtension($legacyBackup,'.json')) -Encoding UTF8
$transfer=& $python -B $maintenance copy --source $legacyBackup --destination "$runtimeRoot\data\db.sqlite3"
if ($LASTEXITCODE -ne 0 -or $before -ne $transfer) { throw 'Data transfer did not match the backup.' }
$env:DEN_ENV='production'; $env:DEN_PUBLIC_ORIGIN=$origin
$env:DEN_SECRET_FILE="$runtimeRoot\secrets.json"; $env:DEN_DATA_DIR="$runtimeRoot\data"
& $python -B "$($state.release)\manage.py" migrate --noinput
if ($LASTEXITCODE -ne 0) { throw 'Cutover migration failed.' }
$after=& $python -B $maintenance fingerprint --source "$runtimeRoot\data\db.sqlite3"
if ($LASTEXITCODE -ne 0 -or $before -ne $after) { throw 'Household data changed during migration.' }
$state.stagingCopy=$false
$state | ConvertTo-Json | Set-Content -LiteralPath $marker -Encoding UTF8
Start-Service DenHub
for ($attempt=0;$attempt -lt 20;$attempt++) {
    try {
        if ((Invoke-WebRequest $origin -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200) { break }
    } catch { Start-Sleep -Seconds 1 }
}
if ($attempt -eq 20) { throw 'Production did not become healthy.' }
if (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue) { throw 'Legacy port remains open.' }
if (-not (Get-NetFirewallRule -Name 'DenHub-Legacy8080' -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name 'DenHub-Legacy8080' -DisplayName 'DenHub retired LAN listener' -Direction Inbound -Action Block -Protocol TCP -LocalPort 8080 -Profile Any | Out-Null
}
$origin | Set-Content "$PSScriptRoot\live-url.txt" -Encoding ASCII
$result=@{passed=$true;origin=$origin;freshBackup=$legacyBackup;fingerprints=($after|ConvertFrom-Json);legacyPortClosed=$true}
$result | ConvertTo-Json -Depth 5 | Set-Content "$sourceRoot\.hardening\cutover-evidence.json"
$result | ConvertTo-Json -Depth 5
