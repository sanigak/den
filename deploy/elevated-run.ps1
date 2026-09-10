# DOC: deployment#commands
param([string]$Action='Install')
$ErrorActionPreference='Stop'
$sourceRoot=Split-Path $PSScriptRoot -Parent
$resultFile=Join-Path $sourceRoot ".hardening\$Action-result.json"
Start-Transcript -Path (Join-Path $sourceRoot ".hardening\$Action-transcript.txt") -Force | Out-Null
try {
    if ($Action -eq 'Recovery') { & "$PSScriptRoot\recovery-check.ps1" }
    elseif ($Action -eq 'HttpsStage') { & "$PSScriptRoot\https-stage.ps1" }
    elseif ($Action -eq 'Comments') {
        $maintenancePython=(Get-Content 'C:\ProgramData\DenHub\den-runtime.json' -Raw | ConvertFrom-Json).python
        Stop-Service DenHub
        $before=& $maintenancePython -B "$PSScriptRoot\maintenance.py" fingerprint --source 'C:\ProgramData\DenHub\data\db.sqlite3'
        if ($LASTEXITCODE -ne 0) { Start-Service DenHub; throw 'Pre-upgrade household fingerprint failed.' }
        & "$PSScriptRoot\den.ps1" -Action Upgrade
        $after=& $maintenancePython -B "$PSScriptRoot\maintenance.py" fingerprint --source 'C:\ProgramData\DenHub\data\db.sqlite3'
        if ($LASTEXITCODE -ne 0 -or $before -ne $after) { throw 'Household fingerprint changed during upgrade.' }
        $after | Set-Content (Join-Path $sourceRoot '.hardening\comments-preserved-data.json')
        & "$PSScriptRoot\den.ps1" -Action Verify
        $runtime=Get-Content 'C:\ProgramData\DenHub\den-runtime.json' -Raw | ConvertFrom-Json
        & $runtime.python -B "$PSScriptRoot\verify_comments.py"
        if ($LASTEXITCODE -ne 0) { throw 'Live comment verification failed.' }
        & "$PSScriptRoot\den.ps1" -Action Backup
    }
    elseif ($Action -eq 'Cutover') { & "$PSScriptRoot\cutover.ps1" }
    elseif ($Action -eq 'OpenRouter') {
        & "$PSScriptRoot\den.ps1" -Action Upgrade
        & "$PSScriptRoot\set-ai-key.ps1" -ProtectedKeyFile (Join-Path $sourceRoot '.hardening\openrouter-key.dpapi')
        & "$PSScriptRoot\den.ps1" -Action Verify
    }
    elseif ($Action -eq 'ImportOpenRouter') {
        & "$PSScriptRoot\set-ai-key.ps1" -ProtectedKeyFile (Join-Path $sourceRoot '.hardening\openrouter-key.dpapi')
        & "$PSScriptRoot\den.ps1" -Action Verify
    }
    elseif ($Action -eq 'FinishRollout') {
        $runtime=Get-Content 'C:\ProgramData\DenHub\den-runtime.json' -Raw | ConvertFrom-Json
        & $runtime.python -B (Join-Path $sourceRoot '.hardening\openrouter-live-smoke.py')
        if ($LASTEXITCODE -ne 0) { throw 'Live provider verification failed; household cutover was not attempted.' }
        & "$PSScriptRoot\cutover.ps1"
        & "$PSScriptRoot\den.ps1" -Action Backup
    }
    elseif ($Action -eq 'FinalStaging') {
        & "$PSScriptRoot\den.ps1" -Action Upgrade
        & "$PSScriptRoot\den.ps1" -Action Verify
        & "$PSScriptRoot\recovery-check.ps1"
    } else { & "$PSScriptRoot\den.ps1" -Action $Action }
    if ($Action -eq 'Upgrade') {
        Get-Content 'C:\ProgramData\DenHub\logs\requests.log' -Tail 80 |
            Where-Object { $_ -match '^\d{4}-\d{2}-\d{2} [\d:,]+ (status=\d{3} elapsed_ms=\d+|csrf_rejected category=(origin|referer|token))$' } |
            Set-Content (Join-Path $sourceRoot '.hardening\request-statuses.txt')
    }
    @{success=$true;action=$Action;finishedUtc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content $resultFile
} catch {
    @{success=$false;action=$Action;error=$_.Exception.Message} | ConvertTo-Json | Set-Content $resultFile
    Write-Error $_ -ErrorAction Continue
} finally { Stop-Transcript | Out-Null }
