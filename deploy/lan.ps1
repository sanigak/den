# DOC: deployment#home-network-access
[CmdletBinding()]
param(
    [ValidateSet('Enable','Disable','Status')][string]$Action='Status',
    [string]$Address,
    [ValidateRange(1024,65535)][int]$Port=8080
)
$ErrorActionPreference='Stop'
$runtimeRoot='C:\ProgramData\DenHub'
$serviceXml=Join-Path $runtimeRoot 'DenHub.xml'
$principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this deployment command from an elevated PowerShell session.'
}
$state=Get-Content "$runtimeRoot\den-runtime.json" -Raw | ConvertFrom-Json
if ($state.root -ne $runtimeRoot -or $state.mode -ne 'production') { throw 'LAN access requires an installed production service.' }
$original=Get-Content -LiteralPath $serviceXml -Raw
[xml]$xml=$original
$oldOrigin=($xml.service.env | Where-Object name -eq 'DEN_LAN_ORIGIN').value
$oldSubnet=($xml.service.env | Where-Object name -eq 'DEN_LAN_SUBNET').value
if ($Action -eq 'Status') {
    @{enabled=[bool]$oldOrigin;origin=$oldOrigin;subnet=$oldSubnet} | ConvertTo-Json
    Get-NetFirewallRule -Name 'DenHub-LAN' -ErrorAction SilentlyContinue | Format-List Name,Enabled,Direction,Action
    return
}
if ((Get-Service DenHub).Status -ne 'Running') { throw 'Start DenHub before changing LAN access.' }

function Set-EnvironmentValue([string]$Name,[string]$Value) {
    $node=$xml.service.env | Where-Object name -eq $Name
    if (-not $node) {
        $node=$xml.CreateElement('env')
        $node.SetAttribute('name',$Name)
        $xml.service.AppendChild($node) | Out-Null
    }
    $node.SetAttribute('value',$Value)
}

function Wait-Page([string]$Url,[string]$HostHeader='') {
    for ($attempt=0; $attempt -lt 30; $attempt++) {
        try {
            $request=[Net.HttpWebRequest]::Create($Url)
            $request.Proxy=$null; $request.Timeout=2000
            if ($HostHeader) { $request.Host=$HostHeader }
            $response=$request.GetResponse()
            try { if ([int]$response.StatusCode -eq 200) { return } }
            finally { $response.Close() }
        } catch { }
        Start-Sleep -Seconds 1
    }
    throw 'Den listener did not become healthy.'
}

if ($Action -eq 'Enable') {
    if (-not (Test-Path "$($state.release)\infonet\lan.py")) { throw 'Upgrade Den before enabling LAN access.' }
    $adapters=@(Get-NetIPAddress -AddressFamily IPv4 -IPAddress $Address -ErrorAction Stop |
        Where-Object { $_.AddressState -eq 'Preferred' -and $_.PrefixLength -lt 31 })
    if ($adapters.Count -ne 1 -or $Port -eq 8082) { throw 'Choose one assigned home IPv4 address and a separate port.' }
    $adapter=$adapters[0]
    $origin="http://${Address}:$Port"
    $subnet=(& $state.python -I -c 'import ipaddress,sys; print(ipaddress.ip_network(sys.argv[1], strict=False))' "$Address/$($adapter.PrefixLength)").Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Cannot determine the home subnet.' }
    Push-Location $state.release
    try {
        & $state.python -B -c 'from infonet.lan import lan_configuration; import sys; lan_configuration(sys.argv[1], sys.argv[2])' $origin $subnet
        if ($LASTEXITCODE -ne 0) { throw 'Invalid LAN configuration.' }
    } finally { Pop-Location }
    if ($oldOrigin) {
        if ($oldOrigin -ne $origin -or $oldSubnet -ne $subnet) { throw 'Disable existing LAN access before changing its network.' }
        Wait-Page $origin
        Write-Output 'LAN access is already configured.'
        return
    }
    if (Get-NetFirewallRule -Name 'DenHub-LAN' -ErrorAction SilentlyContinue) { throw 'A LAN firewall rule already exists; inspect it first.' }
    if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) { throw 'The requested port is already in use.' }
    $legacy=Get-NetFirewallRule -Name 'DenHub-Legacy8080' -ErrorAction SilentlyContinue
    $restoreLegacy=$legacy -and $legacy.Enabled -eq 'True'
    Stop-Service DenHub
    try {
        Set-EnvironmentValue 'DEN_LAN_ORIGIN' $origin
        Set-EnvironmentValue 'DEN_LAN_SUBNET' $subnet
        $xml.Save($serviceXml)
        New-NetFirewallRule -Name 'DenHub-LAN' -DisplayName 'Den household home-network access' `
            -Direction Inbound -Action Allow -Protocol TCP -LocalAddress $Address -LocalPort $Port `
            -RemoteAddress $subnet -InterfaceAlias $adapter.InterfaceAlias -Profile Any -EdgeTraversalPolicy Block | Out-Null
        if ($Port -eq 8080 -and $restoreLegacy) { Disable-NetFirewallRule -Name 'DenHub-Legacy8080' }
        Start-Service DenHub
        Wait-Page 'http://127.0.0.1:8082/' ([uri]$state.productionOrigin).Host
        Wait-Page $origin
    } catch {
        Stop-Service DenHub -ErrorAction SilentlyContinue
        $original | Set-Content -LiteralPath $serviceXml -Encoding UTF8
        Get-NetFirewallRule -Name 'DenHub-LAN' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
        if ($restoreLegacy) { Enable-NetFirewallRule -Name 'DenHub-Legacy8080' }
        Start-Service DenHub
        throw
    }
    @{enabled=$true;origin=$origin;subnet=$subnet} | ConvertTo-Json
} else {
    Stop-Service DenHub
    try {
        Set-EnvironmentValue 'DEN_LAN_ORIGIN' ''
        Set-EnvironmentValue 'DEN_LAN_SUBNET' ''
        $xml.Save($serviceXml)
        Get-NetFirewallRule -Name 'DenHub-LAN' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
        Get-NetFirewallRule -Name 'DenHub-Legacy8080' -ErrorAction SilentlyContinue | Enable-NetFirewallRule
    } finally { Start-Service DenHub }
    Wait-Page 'http://127.0.0.1:8082/' ([uri]$state.productionOrigin).Host
    Write-Output 'LAN access disabled; Tailscale access remains available.'
}
