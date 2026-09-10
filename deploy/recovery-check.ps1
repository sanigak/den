# DOC: deployment#recovery
$ErrorActionPreference='Stop'
$runtimeRoot='C:\ProgramData\DenHub'
$state=Get-Content "$runtimeRoot\den-runtime.json" -Raw | ConvertFrom-Json
if ($state.root -ne $runtimeRoot -or $state.mode -ne 'staging') { throw 'Recovery checks require staging.' }
$servicePython=$state.python
if (-not $servicePython) { $servicePython="$runtimeRoot\venv\Scripts\python.exe" }
$maintenance="$runtimeRoot\tools\maintenance.py"
$report=@{}
$previous=Get-ScheduledTaskInfo -TaskName 'DenHub Daily Backup'
Start-ScheduledTask -TaskName 'DenHub Daily Backup'
for ($attempt=0;$attempt -lt 30;$attempt++) {
    Start-Sleep -Seconds 1
    $info=Get-ScheduledTaskInfo -TaskName 'DenHub Daily Backup'
    if ($info.LastRunTime -gt $previous.LastRunTime -and (Get-ScheduledTask 'DenHub Daily Backup').State -ne 'Running') { break }
}
if ($info.LastRunTime -le $previous.LastRunTime -or $info.LastTaskResult -ne 0) { throw 'Scheduled backup did not succeed.' }
$report.scheduledTask=@{result=$info.LastTaskResult;lastRun=$info.LastRunTime.ToString('o')}
$backup=Get-ChildItem "$runtimeRoot\backups\den-*.sqlite3" | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
$restored="$runtimeRoot\recovery-test\db.sqlite3"
$expected=& $servicePython -B $maintenance fingerprint --source $backup.FullName
if ($LASTEXITCODE -ne 0) { throw 'Backup fingerprint failed.' }
$actual=& $servicePython -B $maintenance copy --source $backup.FullName --destination $restored
if ($LASTEXITCODE -ne 0 -or $actual -ne $expected) { throw 'Restored contents differ.' }
$env:DEN_ENV='staging'; $env:DEN_SECRET_FILE="$runtimeRoot\secrets.json"
$env:DEN_DATA_DIR="$runtimeRoot\recovery-test"; $env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
$waitress=Join-Path (Split-Path $servicePython) 'waitress-serve.exe'
$probe=Start-Process -FilePath $waitress -WindowStyle Hidden -WorkingDirectory $state.release -PassThru -ArgumentList @('--listen=127.0.0.1:8083','--threads=4','infonet.wsgi:application')
try {
    for ($attempt=0;$attempt -lt 20;$attempt++) {
        try { $response=Invoke-WebRequest 'http://127.0.0.1:8083/' -UseBasicParsing -TimeoutSec 2; break } catch { Start-Sleep -Seconds 1 }
    }
    if ($response.StatusCode -ne 200) { throw 'Restored instance did not start.' }
    foreach ($path in @('shopping','recipes','planner','projects')) {
        if ((Invoke-WebRequest "http://127.0.0.1:8083/$path/" -UseBasicParsing -TimeoutSec 5).StatusCode -ne 200) {
            throw 'Restored workflow page failed.'
        }
    }
    $report.restore=@{backup=$backup.Name;fingerprints=($actual|ConvertFrom-Json);isolatedHttp=$true}
} finally {
    $children=Get-CimInstance Win32_Process -Filter "ParentProcessId=$($probe.Id)"
    foreach ($child in $children) { Stop-Process -Id $child.ProcessId -Force -ErrorAction SilentlyContinue }
    Stop-Process -Id $probe.Id -Force -ErrorAction SilentlyContinue
}
$service=Get-CimInstance Win32_Service -Filter "Name='DenHub'"
$oldPid=$service.ProcessId
if ($service.StartName -ne 'NT SERVICE\DenHub' -or $service.State -ne 'Running') { throw 'Unexpected service state.' }
$timer=[Diagnostics.Stopwatch]::StartNew()
& taskkill.exe /PID $oldPid /T /F
if ($LASTEXITCODE -ne 0) { throw 'Could not stop the verified staging service tree.' }
for ($attempt=0;$attempt -lt 50;$attempt++) {
    Start-Sleep -Seconds 1
    $service=Get-CimInstance Win32_Service -Filter "Name='DenHub'"
    if ($service.State -eq 'Running' -and $service.ProcessId -ne $oldPid) {
        try {
            if ((Invoke-WebRequest 'http://127.0.0.1:8082/' -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200) { break }
        } catch { }
    }
}
if ($service.State -ne 'Running' -or $service.ProcessId -eq $oldPid) { throw 'Automatic service recovery failed.' }
$listener=Get-NetTCPConnection -LocalPort 8082 -State Listen
if ($listener.LocalAddress -ne '127.0.0.1') { throw 'Recovery exposed a non-loopback listener.' }
$ancestor=$listener.OwningProcess
for ($attempt=0;$attempt -lt 8 -and $ancestor -ne $service.ProcessId;$attempt++) {
    $ancestor=(Get-CimInstance Win32_Process -Filter "ProcessId=$ancestor").ParentProcessId
}
if ($ancestor -ne $service.ProcessId) { throw 'Recovered listener is not owned by the new service tree.' }
$report.restart=@{recovered=$true;seconds=[Math]::Round($timer.Elapsed.TotalSeconds,1);newPid=$service.ProcessId}
$report | ConvertTo-Json -Depth 6 | Set-Content (Join-Path (Split-Path $PSScriptRoot) '.hardening\recovery-evidence.json')
$report | ConvertTo-Json -Depth 6
