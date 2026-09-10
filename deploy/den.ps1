# DOC: deployment#commands
[CmdletBinding()]
param(
    [ValidateSet('Install','Upgrade','Verify','Backup','Restore','Remove','Status','Open','SyncDevices')]
    [string]$Action='Status',
    [string]$BackupFile,
    [string]$Python=$env:DEN_PYTHON,
    [string]$OwnersFile=$env:DEN_OWNERS_FILE,
    [string]$ImportDatabase
)
$ErrorActionPreference='Stop'
$runtimeRoot='C:\ProgramData\DenHub'
$sourceRoot=Split-Path $PSScriptRoot -Parent
$marker=Join-Path $runtimeRoot 'den-runtime.json'
$serviceExe=Join-Path $runtimeRoot 'DenHub.exe'
$serviceXml=Join-Path $runtimeRoot 'DenHub.xml'
$servicePython=Join-Path $runtimeRoot 'venv\Scripts\python.exe'

function Run-Native([string]$File,[string[]]$Arguments) {
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $File (exit $LASTEXITCODE)" }
}

function Protect-Path([string]$Path,[string]$Account='',[string]$Rights='ReadAndExecute') {
    $entry=Get-Item -LiteralPath $Path
    $directory=$entry.PSIsContainer
    if ($directory) { $acl=[Security.AccessControl.DirectorySecurity]::new() }
    else { $acl=[Security.AccessControl.FileSecurity]::new() }
    $acl.SetAccessRuleProtection($true,$false)
    $inherit=[Security.AccessControl.InheritanceFlags]::None
    if ($directory) { $inherit=[Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit' }
    foreach ($id in @('S-1-5-18','S-1-5-32-544')) {
        $sid=[Security.Principal.SecurityIdentifier]::new($id)
        $rule=[Security.AccessControl.FileSystemAccessRule]::new($sid,'FullControl',$inherit,'None','Allow')
        $acl.AddAccessRule($rule)
    }
    $acl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
    if ($Account) {
        $sid=([Security.Principal.NTAccount]::new($Account)).Translate([Security.Principal.SecurityIdentifier])
        $rule=[Security.AccessControl.FileSystemAccessRule]::new($sid,$Rights,$inherit,'None','Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Wait-Den {
    $headers=@{}
    if ($env:DEN_PUBLIC_ORIGIN) { $headers.Host=([uri]$env:DEN_PUBLIC_ORIGIN).Host }
    for ($attempt=0; $attempt -lt 30; $attempt++) {
        try {
            $response=Invoke-WebRequest 'http://127.0.0.1:8082/' -Headers $headers -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { return }
        } catch { }
        Start-Sleep -Seconds 1
    }
    throw 'Den did not become healthy on loopback.'
}

function Read-State {
    if (-not (Test-Path -LiteralPath $marker)) { throw 'Den runtime marker not found.' }
    $state=Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
    if ($state.root -ne $runtimeRoot) { throw 'Unexpected runtime marker.' }
    return $state
}

if ($Action -eq 'Open') {
    $url='http://127.0.0.1:8082'
    $publicUrl=Join-Path $PSScriptRoot 'live-url.txt'
    if (Test-Path -LiteralPath $publicUrl) {
        $candidate=(Get-Content -LiteralPath $publicUrl -Raw).Trim()
        if ($candidate -notmatch '^https://[a-z0-9-]+\.[a-z0-9-]+\.ts\.net$') { throw 'Invalid public URL.' }
        $url=$candidate
    }
    if ($env:DEN_PUBLIC_ORIGIN) {
        if ($env:DEN_PUBLIC_ORIGIN -notmatch '^https://[a-z0-9-]+\.[a-z0-9-]+\.ts\.net$') { throw 'Invalid DEN_PUBLIC_ORIGIN.' }
        $url=$env:DEN_PUBLIC_ORIGIN
    }
    Start-Process $url
    return
}
if ($Action -eq 'Status') {
    Get-Service DenHub -ErrorAction SilentlyContinue | Format-List Name,Status,StartType
    try { Read-State | Format-List } catch { Write-Output 'Elevate PowerShell to read protected deployment details.' }
    return
}
$principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this deployment command from an elevated PowerShell session.'
}

if ($Action -in @('Install','Upgrade')) {
    if ($Action -eq 'Install' -and (Get-Service DenHub -ErrorAction SilentlyContinue)) {
        throw 'DenHub already exists; use Upgrade.'
    }
    if (Test-Path -LiteralPath $runtimeRoot) {
        if (-not (Test-Path -LiteralPath $marker)) { throw 'Refusing to replace an unrecognized runtime directory.' }
        $oldState=Read-State
    }
    if ($Action -eq 'Upgrade' -and -not $oldState) { throw 'Upgrade requires an existing runtime.' }
    if (-not $Python -and $oldState) {
        $Python=(& $oldState.python -I -c 'import sys; print(sys._base_executable)').Trim()
        if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve installed Python.' }
    }
    if (-not $Python -or -not [IO.Path]::IsPathRooted($Python) -or -not (Test-Path -LiteralPath $Python)) {
        throw 'Set DEN_PYTHON or -Python to an absolute system-wide Python executable.'
    }
    if ($ImportDatabase -and ($Action -ne 'Install' -or (Test-Path "$runtimeRoot\data\db.sqlite3"))) {
        throw 'Database import is available only during a fresh installation.'
    }
    if ($ImportDatabase) { $ImportDatabase=(Resolve-Path -LiteralPath $ImportDatabase).Path }
    if (-not (Test-Path "$runtimeRoot\identity\owners.json")) {
        if (-not $OwnersFile) { $OwnersFile=Join-Path $PSScriptRoot 'household-owners.json' }
        if (-not (Test-Path -LiteralPath $OwnersFile)) { throw 'Set DEN_OWNERS_FILE or -OwnersFile to your private owner mapping.' }
        $OwnersFile=(Resolve-Path -LiteralPath $OwnersFile).Path
        Run-Native $Python @('-I','-B',"$PSScriptRoot\sync_devices.py",'--validate-owners',$OwnersFile)
    }
    $mode='staging'; $productionOrigin=''; $aiEnabled='0'
    $displayTimeZone=$env:DEN_DISPLAY_TIME_ZONE
    if (-not $displayTimeZone) { $displayTimeZone='America/New_York' }
    if ($oldState) {
        $mode=$oldState.mode; $productionOrigin=$oldState.productionOrigin
        [xml]$oldXml=Get-Content -LiteralPath $serviceXml -Raw
        $aiEnabled=($oldXml.service.env | Where-Object name -eq 'DEN_AI_ENABLED').value
        $savedTimeZone=($oldXml.service.env | Where-Object name -eq 'DEN_DISPLAY_TIME_ZONE').value
        if (-not $env:DEN_DISPLAY_TIME_ZONE -and $savedTimeZone) { $displayTimeZone=$savedTimeZone }
    }
    New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
    Protect-Path $runtimeRoot
    foreach ($name in @('data','logs','tmp','backups','releases','tools','identity')) {
        New-Item -ItemType Directory -Path (Join-Path $runtimeRoot $name) -Force | Out-Null
    }
    $release=Join-Path $runtimeRoot ('releases\'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfff'))
    Run-Native $Python @('-X','utf8',"$PSScriptRoot\package.py",$sourceRoot,$release)
    $servicePython=Join-Path $release 'venv\Scripts\python.exe'
    Run-Native $Python @('-m','venv',"$release\venv")
    $wheelDir=Join-Path $sourceRoot '.hardening\wheels'
    if (-not (Test-Path -LiteralPath $wheelDir)) { throw 'Download the hash-locked wheels before installing.' }
    Run-Native $servicePython @('-m','pip','install','--no-index','--require-hashes','--find-links',$wheelDir,'-r',"$release\requirements.txt")
    Run-Native $servicePython @('-I','-c','from zoneinfo import ZoneInfo; import sys; ZoneInfo(sys.argv[1])',$displayTimeZone)
    $manifest=Get-Content "$PSScriptRoot\vendor-manifest.json" -Raw | ConvertFrom-Json
    $entry=$manifest | Where-Object { $_.file -eq 'deploy/vendor/DenHub.exe' }
    $actual=(Get-FileHash "$PSScriptRoot\vendor\DenHub.exe" -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($entry.sha256 -ne $actual) { throw 'WinSW hash mismatch.' }
    if ($Action -eq 'Upgrade') {
        Stop-Service DenHub
        try { Run-Native $servicePython @('-X','utf8',"$runtimeRoot\tools\maintenance.py",'backup','--root',$runtimeRoot) }
        catch { Start-Service DenHub; throw }
    }
    Copy-Item -LiteralPath "$PSScriptRoot\maintenance.py","$PSScriptRoot\identity_probe.py","$PSScriptRoot\sync_devices.py" -Destination "$runtimeRoot\tools" -Force
    if (-not (Test-Path "$runtimeRoot\identity\owners.json")) {
        Copy-Item -LiteralPath $OwnersFile -Destination "$runtimeRoot\identity\owners.json"
    }
    if (-not (Test-Path "$runtimeRoot\identity\devices.json")) {
        '{"version":1,"generated_at":0,"devices":[]}' | Set-Content "$runtimeRoot\identity\devices.json" -Encoding ASCII
    }
    Copy-Item -LiteralPath "$PSScriptRoot\vendor\DenHub.exe" -Destination $serviceExe -Force
    Copy-Item -LiteralPath "$PSScriptRoot\vendor\WinSW-LICENSE.txt" -Destination "$runtimeRoot\WinSW-LICENSE.txt" -Force
    Copy-Item -LiteralPath "$sourceRoot\LICENSE" -Destination "$runtimeRoot\LICENSE.txt" -Force
    $secretPath=Join-Path $runtimeRoot 'secrets.json'
    if (-not (Test-Path -LiteralPath $secretPath)) {
        $bytes=New-Object byte[] 64
        [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        @{django_secret=[Convert]::ToBase64String($bytes);openrouter_api_key=''} | ConvertTo-Json | Set-Content $secretPath -Encoding UTF8
    }
    if ($ImportDatabase) {
        Run-Native $servicePython @('-X','utf8',"$runtimeRoot\tools\maintenance.py",'copy','--source',$ImportDatabase,'--destination',"$runtimeRoot\data\db.sqlite3")
    }
    $env:DEN_ENV=$mode; $env:DEN_PUBLIC_ORIGIN=$productionOrigin
    $env:DEN_SECRET_FILE=$secretPath; $env:DEN_DATA_DIR="$runtimeRoot\data"
    $env:DEN_DISPLAY_TIME_ZONE=$displayTimeZone
    $env:PYTHONUTF8='1'; $env:PYTHONDONTWRITEBYTECODE='1'
    Run-Native $servicePython @('-B',"$release\manage.py",'migrate','--noinput')
    Run-Native $servicePython @('-B',"$release\manage.py",'collectstatic','--noinput')
    if ($mode -eq 'production') { Run-Native $servicePython @('-B',"$release\manage.py",'check','--deploy','--fail-level','WARNING') }
    $displayTimeZoneXml=[Security.SecurityElement]::Escape($displayTimeZone)
    $xml=@"
<service>
  <id>DenHub</id><name>Den Household Hub</name><description>Private household application.</description>
  <executable>$servicePython</executable><arguments>-X utf8 -B "$release\serve.py"</arguments>
  <workingdirectory>$release</workingdirectory>
  <serviceaccount><domain>NT SERVICE</domain><user>DenHub</user></serviceaccount>
  <startmode>Automatic</startmode><delayedAutoStart>true</delayedAutoStart>
  <onfailure action="restart" delay="10 sec"/><onfailure action="restart" delay="30 sec"/>
  <onfailure action="restart" delay="60 sec"/><resetfailure>1 hour</resetfailure>
  <stoptimeout>40 sec</stoptimeout><logpath>$runtimeRoot\logs</logpath>
  <log mode="roll-by-size"><sizeThreshold>2048</sizeThreshold><keepFiles>4</keepFiles></log>
  <env name="DEN_ENV" value="$mode"/><env name="DEN_AI_ENABLED" value="$aiEnabled"/>
  <env name="DEN_PUBLIC_ORIGIN" value="$productionOrigin"/>
  <env name="DEN_SECRET_FILE" value="$secretPath"/><env name="DEN_DATA_DIR" value="$runtimeRoot\data"/>
  <env name="DEN_LOG_DIR" value="$runtimeRoot\logs"/><env name="DEN_RUNTIME_ROOT" value="$runtimeRoot"/>
  <env name="DEN_DEVICE_MAP_FILE" value="$runtimeRoot\identity\devices.json"/>
  <env name="DEN_DISPLAY_TIME_ZONE" value="$displayTimeZoneXml"/>
  <env name="TEMP" value="$runtimeRoot\tmp"/><env name="TMP" value="$runtimeRoot\tmp"/>
  <env name="PYTHONUTF8" value="1"/><env name="PYTHONDONTWRITEBYTECODE" value="1"/>
</service>
"@
    $xml | Set-Content -LiteralPath $serviceXml -Encoding UTF8
    if ($Action -eq 'Install') { Run-Native $serviceExe @('install') }
    Run-Native 'sc.exe' @('privs','DenHub','SeChangeNotifyPrivilege')
    Run-Native 'sc.exe' @('sidtype','DenHub','unrestricted')
    $identity='NT SERVICE\DenHub'
    Protect-Path "$runtimeRoot\releases" $identity
    Protect-Path "$runtimeRoot\tools" $identity
    Protect-Path "$runtimeRoot\identity" $identity 'ReadAndExecute'
    foreach ($name in @('data','logs','tmp')) { Protect-Path (Join-Path $runtimeRoot $name) $identity 'Modify' }
    Protect-Path $serviceExe $identity
    Protect-Path $serviceXml $identity 'Read'
    Protect-Path $secretPath $identity 'Read'
    Protect-Path "$runtimeRoot\backups"
    $state=@{root=$runtimeRoot;release=$release;python=$servicePython;mode=$mode;productionOrigin=$productionOrigin;createdUtc=[DateTime]::UtcNow.ToString('o')}
    if ($oldState -and $null -ne $oldState.stagingCopy) { $state.stagingCopy=$oldState.stagingCopy }
    $state | ConvertTo-Json | Set-Content -LiteralPath $marker -Encoding UTF8
    $taskAction=New-ScheduledTaskAction -Execute $servicePython -Argument "-X utf8 -B `"$runtimeRoot\tools\maintenance.py`" backup --root `"$runtimeRoot`""
    $trigger=New-ScheduledTaskTrigger -Daily -At '03:00'
    $taskPrincipal=New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $taskSettings=New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
    Register-ScheduledTask -TaskName 'DenHub Daily Backup' -Action $taskAction -Trigger $trigger -Principal $taskPrincipal -Settings $taskSettings -Force | Out-Null
    $syncAction=New-ScheduledTaskAction -Execute $Python -Argument "-I -B `"$runtimeRoot\tools\sync_devices.py`""
    $syncTrigger=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
    $syncSettings=New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName 'DenHub Device Map' -Action $syncAction -Trigger @($syncTrigger,(New-ScheduledTaskTrigger -AtStartup)) -Principal $taskPrincipal -Settings $syncSettings -Force | Out-Null
    if ($mode -eq 'production') { Run-Native $Python @('-I','-B',"$runtimeRoot\tools\sync_devices.py") }
    Start-Service DenHub
    Wait-Den
    Run-Native $servicePython @('-X','utf8',"$runtimeRoot\tools\maintenance.py",'backup','--root',$runtimeRoot)
    Write-Output "Den service installed in $mode mode on loopback port 8082."
    return
}

$state=Read-State
if ($state.python) { $servicePython=$state.python }
$env:DEN_PUBLIC_ORIGIN=$state.productionOrigin
if ($Action -eq 'Backup') {
    Run-Native $servicePython @('-X','utf8',"$runtimeRoot\tools\maintenance.py",'backup','--root',$runtimeRoot)
} elseif ($Action -eq 'SyncDevices') {
    Start-ScheduledTask -TaskName 'DenHub Device Map'
    Write-Output 'Protected device map refresh requested.'
} elseif ($Action -eq 'Restore') {
    if (-not $BackupFile) { throw 'Restore requires -BackupFile.' }
    $restorePath=(Resolve-Path -LiteralPath $BackupFile).Path
    if (-not $restorePath.StartsWith("$runtimeRoot\backups\",[StringComparison]::OrdinalIgnoreCase)) {
        throw 'Restore accepts only protected Den backups.'
    }
    $candidateDir="$runtimeRoot\restore-candidate"
    New-Item -ItemType Directory -Path $candidateDir -Force | Out-Null
    Protect-Path $candidateDir
    $candidate="$candidateDir\db.sqlite3"
    $expected=Run-Native $servicePython @('-X','utf8',"$runtimeRoot\tools\maintenance.py",'copy','--source',$restorePath,'--destination',$candidate)
    $env:DEN_ENV=$state.mode; $env:DEN_SECRET_FILE="$runtimeRoot\secrets.json"; $env:DEN_DATA_DIR=$candidateDir
    Run-Native $servicePython @('-B',"$($state.release)\manage.py",'migrate','--noinput')
    $actual=Run-Native $servicePython @('-X','utf8',"$runtimeRoot\tools\maintenance.py",'fingerprint','--source',$candidate)
    if ($expected -ne $actual) { throw 'Restored household data changed during migration.' }
    Stop-Service DenHub
    try {
        Run-Native $servicePython @('-X','utf8',"$runtimeRoot\tools\maintenance.py",'backup','--root',$runtimeRoot)
        Run-Native $servicePython @('-X','utf8',"$runtimeRoot\tools\maintenance.py",'copy','--source',$candidate,'--destination',"$runtimeRoot\data\db.sqlite3")
    } finally { Start-Service DenHub }
    Wait-Den
} elseif ($Action -eq 'Remove') {
    Stop-Service DenHub -ErrorAction SilentlyContinue
    $tailscale='C:\Program Files\Tailscale\tailscale.exe'
    if ((Test-Path -LiteralPath $tailscale) -and $state.productionOrigin) {
        $proxy=& $tailscale serve status --json | ConvertFrom-Json
        $hostKey=([uri]$state.productionOrigin).Host+':443'
        if ($proxy.Web.$hostKey.Handlers.'/'.Proxy -eq 'http://127.0.0.1:8082') {
            Run-Native $tailscale @('serve','--https=443','off')
        }
    }
    Run-Native $serviceExe @('uninstall')
    Unregister-ScheduledTask -TaskName 'DenHub Daily Backup' -Confirm:$false -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName 'DenHub Device Map' -Confirm:$false -ErrorAction SilentlyContinue
    Get-NetFirewallRule -Name 'DenHub-Legacy8080' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    Write-Output 'Service and scheduled task removed. Data and backups retained.'
} elseif ($Action -eq 'Verify') {
    $service=Get-CimInstance Win32_Service -Filter "Name='DenHub'"
    if ($service.StartName -ne 'NT SERVICE\DenHub') { throw 'Unexpected service identity.' }
    $canary=Join-Path $sourceRoot '.hardening\private-canary.txt'
    'Synthetic permission probe.' | Set-Content -LiteralPath $canary
    Protect-Path $canary
    $backupCanary=Join-Path $runtimeRoot 'backups\permission-canary.txt'
    'Synthetic protected backup.' | Set-Content -LiteralPath $backupCanary
    $denyRead=@{private_canary=$canary;private_profile=$env:USERPROFILE;private_appdata="$env:USERPROFILE\AppData";protected_backup=$backupCanary}
    if (Test-Path 'C:\ProgramData\Tailscale\server-state.conf') {
        $denyRead.tailscale_credentials='C:\ProgramData\Tailscale\server-state.conf'
    }
    $venvRoot=Split-Path (Split-Path $servicePython) -Parent
    $baseRoot=Split-Path $Python
    @{deny_read=$denyRead;deny_write=@{code="$($state.release)\serve.py";secrets="$runtimeRoot\secrets.json";backup=$backupCanary;
        service_config=$serviceXml;device_map="$runtimeRoot\identity\devices.json";device_owners="$runtimeRoot\identity\owners.json";
        device_sync="$runtimeRoot\tools\sync_devices.py";python_runtime=$servicePython;python_base=$Python;
        django_dependency="$venvRoot\Lib\site-packages\django\__init__.py";python_library="$baseRoot\Lib\site.py"};
        deny_delete=@{backup_delete=$backupCanary;code_delete="$($state.release)\serve.py";secret_delete="$runtimeRoot\secrets.json";
        device_map_delete="$runtimeRoot\identity\devices.json"}
    } | ConvertTo-Json | Set-Content "$runtimeRoot\probe-config.json" -Encoding UTF8
    Protect-Path "$runtimeRoot\probe-config.json" 'NT SERVICE\DenHub' 'Read'
    Stop-Service DenHub
    $original=Get-Content -LiteralPath $serviceXml -Raw
    try {
        $probeXml=$original -replace '<arguments>.*?</arguments>',"<arguments>-X utf8 -B `"$runtimeRoot\tools\identity_probe.py`"</arguments>"
        $probeXml | Set-Content -LiteralPath $serviceXml -Encoding UTF8
        Remove-Item -LiteralPath "$runtimeRoot\logs\identity-probe.json" -ErrorAction SilentlyContinue
        Start-Service DenHub
        for ($attempt=0; $attempt -lt 20; $attempt++) {
            if (Test-Path "$runtimeRoot\logs\identity-probe.json") { break }
            Start-Sleep -Seconds 1
        }
        $probe=Get-Content "$runtimeRoot\logs\identity-probe.json" -Raw | ConvertFrom-Json
        if (-not $probe.pass) { throw 'Service identity isolation probe failed.' }
        $probe | ConvertTo-Json -Depth 5
    } finally {
        Stop-Service DenHub -ErrorAction SilentlyContinue
        $original | Set-Content -LiteralPath $serviceXml -Encoding UTF8
        Start-Service DenHub
        Remove-Item -LiteralPath $canary -ErrorAction SilentlyContinue
    }
    Wait-Den
    $listeners=Get-NetTCPConnection -LocalPort 8082 -State Listen
    if ($listeners.LocalAddress -ne '127.0.0.1') { throw 'Staging listener is not loopback-only.' }
    Write-Output 'Live service identity and listener verification passed.'
}
