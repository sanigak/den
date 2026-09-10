# DOC: deployment#secrets
[CmdletBinding()]
param([switch]$FromEnvironment,[string]$ProtectedKeyFile)
$ErrorActionPreference='Stop'
$principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Use elevated PowerShell.' }
$runtimeRoot='C:\ProgramData\DenHub'
$state=Get-Content "$runtimeRoot\den-runtime.json" -Raw | ConvertFrom-Json
if ($state.root -ne $runtimeRoot) { throw 'Unexpected runtime marker.' }
$secretPath="$runtimeRoot\secrets.json"
$temporary="$runtimeRoot\secrets.pending.json"
$secureKey=$null; $pointer=[IntPtr]::Zero; $plainBytes=$null
try {
    if ($ProtectedKeyFile) {
        Add-Type -AssemblyName System.Security
        $protectedPath=(Resolve-Path -LiteralPath $ProtectedKeyFile).Path
        $plainBytes=[Security.Cryptography.ProtectedData]::Unprotect(
            [IO.File]::ReadAllBytes($protectedPath),$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
        $key=[Text.Encoding]::UTF8.GetString($plainBytes)
    } elseif ($FromEnvironment) {
        $key=[Environment]::GetEnvironmentVariable('OPENROUTER_API_KEY','Process')
    } else {
        $secureKey=Read-Host 'OpenRouter key (hidden)' -AsSecureString
        $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
        $key=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    if ($key -notmatch '^sk-or-[a-zA-Z0-9_-]{20,}$') { throw 'Missing or invalid OpenRouter key.' }
    $secrets=Get-Content -LiteralPath $secretPath -Raw | ConvertFrom-Json
    $secrets.PSObject.Properties.Remove('anthropic_api_key')
    $secrets | Add-Member -NotePropertyName openrouter_api_key -NotePropertyValue $key -Force
    $secrets | ConvertTo-Json | Set-Content -LiteralPath $temporary -Encoding UTF8
    Set-Acl -LiteralPath $temporary -AclObject (Get-Acl -LiteralPath $secretPath)
    [IO.File]::Replace($temporary,$secretPath,[NullString]::Value)
} finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary }
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    if ($plainBytes) { [Array]::Clear($plainBytes,0,$plainBytes.Length) }
    if ($ProtectedKeyFile -and (Test-Path -LiteralPath $ProtectedKeyFile)) { Remove-Item -LiteralPath $ProtectedKeyFile }
    $key=$null; $secrets=$null
    if ($secureKey) { $secureKey.Dispose() }
}
$config="$runtimeRoot\DenHub.xml"
[xml]$xml=Get-Content -LiteralPath $config -Raw
($xml.service.env | Where-Object name -eq 'DEN_AI_ENABLED').value='1'
$xml.Save($config)
Restart-Service DenHub
Write-Output 'OpenRouter key saved in protected storage; Smart Export enabled.'
