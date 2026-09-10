# DOC: deployment#secrets
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Security
$key=[Environment]::GetEnvironmentVariable('OPENROUTER_API_KEY','Process')
if ($key -notmatch '^sk-or-[a-zA-Z0-9_-]{20,}$') { throw 'OPENROUTER_API_KEY is missing or invalid.' }
$handoff=Join-Path (Split-Path $PSScriptRoot -Parent) '.hardening\openrouter-key.dpapi'
$plainBytes=[Text.Encoding]::UTF8.GetBytes($key)
try {
    $encrypted=[Security.Cryptography.ProtectedData]::Protect(
        $plainBytes,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
    [IO.File]::WriteAllBytes($handoff,$encrypted)
    $acl=[Security.AccessControl.FileSecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    $owner=[Security.Principal.WindowsIdentity]::GetCurrent().User
    $acl.SetOwner($owner)
    foreach ($sid in @($owner.Value,'S-1-5-18','S-1-5-32-544')) {
        $identity=[Security.Principal.SecurityIdentifier]::new($sid)
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($identity,'FullControl','Allow'))
    }
    Set-Acl -LiteralPath $handoff -AclObject $acl
} finally {
    [Array]::Clear($plainBytes,0,$plainBytes.Length)
    $key=$null
}
Write-Output 'Encrypted OpenRouter handoff prepared; no plaintext key was written.'
