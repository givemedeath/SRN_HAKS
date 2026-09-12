[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('shared', 'SR_NWN', 'SRN_NWN')][string]$Owner,
    [Parameter(Mandatory)][ValidatePattern('^[a-z0-9]+(?:[._-][a-z0-9]+)*$')][string]$Key,
    [Parameter(Mandatory)][AllowEmptyString()][string]$Text
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'SrnHaks.Common.psm1') -Force

$root = Get-SrnRepositoryRoot
$allocationPath = Join-Path $root 'srn_tlk/allocations.json'
$tlkPath = Join-Path $root 'srn_tlk/srn.tlk.json'
$lockPath = Join-Path $root 'srn_tlk/.allocation.lock'
$lockStream = $null
$lockOwned = $false

try {
    $lockStream = [System.IO.File]::Open($lockPath, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    $lockOwned = $true
    $allocationBytes = [System.IO.File]::ReadAllBytes($allocationPath)
    $tlkBytes = [System.IO.File]::ReadAllBytes($tlkPath)
    $registry = [System.Text.Encoding]::UTF8.GetString($allocationBytes) | ConvertFrom-Json -Depth 16
    $tlk = [System.Text.Encoding]::UTF8.GetString($tlkBytes) | ConvertFrom-Json -Depth 16

    if (@($registry.allocations | Where-Object {
        $_.key -ceq $Key -or
        ($_.PSObject.Properties.Name -contains 'aliases' -and @($_.aliases) -ccontains $Key)
    }).Count -gt 0) {
        throw "StrRef key already exists: $Key"
    }

    $id = [int]$registry.nextId
    $registry.allocations = @($registry.allocations) + [pscustomobject][ordered]@{
        id = $id
        key = $Key
        owner = $Owner
        status = 'active'
    }
    $registry.nextId = $id + 1
    $tlk.entries = @($tlk.entries) + [pscustomobject][ordered]@{ id = $id; text = $Text }

    try {
        Write-SrnJsonAtomic -Path $allocationPath -Value $registry
        Write-SrnJsonAtomic -Path $tlkPath -Value $tlk
    }
    catch {
        [System.IO.File]::WriteAllBytes($allocationPath, $allocationBytes)
        [System.IO.File]::WriteAllBytes($tlkPath, $tlkBytes)
        throw
    }

    $gameStrRef = 0x01000000 + $id
    Write-Output ([pscustomobject]@{ Id = $id; GameStrRef = $gameStrRef; Key = $Key; Owner = $Owner })
}
finally {
    if ($null -ne $lockStream) { $lockStream.Dispose() }
    if ($lockOwned -and (Test-Path -LiteralPath $lockPath)) { Remove-Item -LiteralPath $lockPath -Force }
}
