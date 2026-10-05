#Requires -Version 7.0
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Text.UTF8Encoding]::new($false)
if ($IsWindows -and -not ('SrnCanonicalPaths.NativeMethods' -as [type])) {
    Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
using System.Text;
namespace SrnCanonicalPaths {
    public static class NativeMethods {
        [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
        public static extern uint GetLongPathName(string path, StringBuilder output, uint size);
    }
}
'@
}
function Resolve-SrnRealPath {
    param([Parameter(Mandatory)][string]$Path)
    $full = [IO.Path]::GetFullPath($Path); $root = [IO.Path]::GetPathRoot($full); $current = $root
    foreach ($part in $full.Substring($root.Length).Split([char[]]@('/', '\'), [StringSplitOptions]::RemoveEmptyEntries)) {
        $current = Join-Path $current $part
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force
            if ($item.LinkTarget) { $current = $item.ResolveLinkTarget($true).FullName }
            if ($IsWindows) {
                $buffer=[Text.StringBuilder]::new(32768)
                $length=[SrnCanonicalPaths.NativeMethods]::GetLongPathName($current,$buffer,32768)
                if (-not $length -or $length -ge 32768) { throw "Cannot canonicalize Windows path: $current" }
                $current=$buffer.ToString()
            }
        }
    }
    [IO.Path]::GetFullPath($current)
}
function Test-SrnWithin {
    param([string]$Path, [string]$Root)
    $p = Resolve-SrnRealPath $Path; $r = Resolve-SrnRealPath $Root
    $c = if ($IsWindows) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
    $p.Equals($r, $c) -or $p.StartsWith($r.TrimEnd('/', '\') + [IO.Path]::DirectorySeparatorChar, $c)
}
function Get-SrnWorktrees {
    param([string]$RepositoryRoot)
    $lines = @(& git -c core.quotepath=false -C $RepositoryRoot worktree list --porcelain 2>$null)
    if ($LASTEXITCODE -ne 0) { throw 'Git metadata unavailable; supply an explicit tools root' }
    $result = @(); $row = $null
    foreach ($line in $lines) {
        if ($line.StartsWith('worktree ')) {
            $p=$line.Substring(9); if ($p.StartsWith('"')) { $p=$p | ConvertFrom-Json }
            $row = @{path=Resolve-SrnRealPath $p; bare=$false}; $result += $row
        }
        elseif ($line -eq 'bare') { $row.bare = $true }
    }
    $result
}
function Assert-SrnDurablePath {
    param([string]$Path, [string]$RepositoryRoot = (Split-Path $PSScriptRoot -Parent))
    $resolved = Resolve-SrnRealPath $Path
    try { $entries = @(Get-SrnWorktrees $RepositoryRoot) } catch { $entries = @() }
    foreach ($entry in @($entries | Select-Object -Skip 1)) {
        if (Test-SrnWithin $resolved $entry.path) { throw "Shared/installed tool is inside a linked worktree: $resolved" }
    }
    $ancestor = if (Test-Path -LiteralPath $resolved -PathType Leaf) { Split-Path $resolved -Parent } else { $resolved }
    while ($ancestor) {
        $gitPath = Join-Path $ancestor '.git'
        if (Test-Path -LiteralPath $gitPath -PathType Leaf) {
            $local = & git -C $ancestor rev-parse --path-format=absolute --git-dir
            $common = & git -C $ancestor rev-parse --path-format=absolute --git-common-dir
            if ($LASTEXITCODE -ne 0 -or (Resolve-SrnRealPath $local) -ne (Resolve-SrnRealPath $common)) { throw "Shared/installed tool is inside a linked worktree: $resolved" }
            break
        }
        if (Test-Path -LiteralPath $gitPath -PathType Container) { break }
        $parent = Split-Path $ancestor -Parent
        if ($parent -eq $ancestor) { break }; $ancestor = $parent
    }
}
function Get-SrnToolsRoot {
    param([string]$ToolsRoot, [string]$RepositoryRoot = (Split-Path $PSScriptRoot -Parent))
    if ($ToolsRoot) { $chosen = $ToolsRoot; $origin = 'argument' }
    elseif ($env:SRN_TOOLS_ROOT) { $chosen = $env:SRN_TOOLS_ROOT; $origin = 'environment' }
    else {
        $entries = @(Get-SrnWorktrees $RepositoryRoot)
        if (-not $entries.Count -or $entries[0].bare) { throw 'Bare repository requires an explicit tools root' }
        $chosen = Join-Path $entries[0].path '.tools'; $origin = 'primary-checkout'
    }
    $chosen = Resolve-SrnRealPath $chosen; Assert-SrnDurablePath $chosen $RepositoryRoot
    [pscustomobject]@{path=$chosen; origin=$origin}
}
function Resolve-SrnTool {
    param([Parameter(Mandatory)][string]$Name, [string]$ToolsRoot, [string]$Path, [string]$RepositoryRoot = (Split-Path $PSScriptRoot -Parent))
    $root = Get-SrnToolsRoot -ToolsRoot $ToolsRoot -RepositoryRoot $RepositoryRoot
    $lockPath = Join-Path $RepositoryRoot 'tools/shared-tools.lock.json'
    $inventoryHash=(Get-FileHash $lockPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $lock = Get-Content -Raw -Encoding utf8 -LiteralPath $lockPath | ConvertFrom-Json -AsHashtable
    if (-not $lock.tools.ContainsKey($Name)) { throw "Unknown tool: $Name" }
    $tool = $lock.tools[$Name]
    $platform = if ($IsWindows) { 'windows-x64' } elseif ($IsLinux) { 'linux-x64' } else { throw 'Unsupported platform' }
    if ([Runtime.InteropServices.RuntimeInformation]::OSArchitecture -ne 'X64' -or -not $tool.platforms.ContainsKey($platform)) { throw "Tool unsupported on this platform: $Name" }
    $entry = $tool.platforms[$platform]
    $base = if ($tool.origin -eq 'vendored') { Join-Path $RepositoryRoot 'tools' } else { $root.path }
    $target = Resolve-SrnRealPath $(if ($Path) { $Path } else { Join-Path $base $entry.relativePath })
    if (-not (Test-SrnWithin $target $base)) { throw "Tool path escapes its declared installation: $target" }
    if ($tool.origin -eq 'vendored') {
        if (-not (Test-SrnWithin $target (Join-Path $RepositoryRoot 'tools/vendor'))) { throw 'Vendored tool must belong to the consuming checkout' }
    } else { Assert-SrnDurablePath $target $RepositoryRoot }
    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) { throw "Missing tool: $target. Run Bootstrap-Tools.ps1 for Neverwinter utilities; manually install the pinned Armory version for armory." }
    $hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -cne $entry.sha256) { throw "Tool binary changed: $target" }
    if ((Get-FileHash $lockPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $inventoryHash) { throw 'Tool inventory changed during resolution' }
    [pscustomobject]@{name=$Name; path=$target; version=$tool.version; sha256=$hash; origin=$tool.origin; toolsRoot=$root.path; rootOrigin=$root.origin; inventorySha256=$inventoryHash}
}
function Register-SrnToolUse {
    param([Parameter(Mandatory)]$Tool, [string[]]$Inputs = @(), [string]$RepositoryRoot = (Split-Path $PSScriptRoot -Parent))
    $repo = Resolve-SrnRealPath $RepositoryRoot; $identity = if ($IsWindows) { $repo.ToLowerInvariant() } else { $repo }
    $id = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($identity))).ToLowerInvariant()
    $folder = Join-Path $Tool.toolsRoot "consumers/$id"; New-Item -ItemType Directory -Force -Path $folder | Out-Null
    $lock = [IO.File]::Open((Join-Path $folder 'registration.lock'), 'OpenOrCreate', 'ReadWrite', 'ReadWrite')
    if (-not $lock.Length) { $lock.WriteByte(48); $lock.Flush() }
    $acquired=$false; $end=[DateTime]::UtcNow.AddSeconds(30)
    try {
        while (-not $acquired) { try { $lock.Lock(0, 1); $acquired=$true } catch { if ([DateTime]::UtcNow -ge $end) { throw }; Start-Sleep -Milliseconds 50 } }
        $refs = @(@{path=$Tool.path; role='tool'; sha256=$Tool.sha256})
        foreach ($input in $Inputs) { $p=Resolve-SrnRealPath $input; $refs+=@{path=$p; role='input'; sha256=$(if (Test-Path $p -PathType Leaf) { (Get-FileHash $p -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null })} }
        $current=Join-Path $folder 'current.json'
        if (Test-Path -LiteralPath $current) { $refs+=(Get-Content -Raw -Encoding utf8 $current | ConvertFrom-Json -AsHashtable).references }
        $refs=@($refs | Group-Object { $_.role+':'+$_.path } | ForEach-Object { $_.Group[0] })
        $report=@{schemaVersion=1; kind='shared-tool-consumer'; worktree=$repo; createdUtc=[DateTime]::UtcNow.ToString('o'); toolsRoot=$Tool.toolsRoot; rootOrigin=$Tool.rootOrigin; completeDeclaration=$false; references=$refs; inventorySha256=$Tool.inventorySha256}
        $local=Join-Path $repo ('.tmp/tool-dependencies/'+[guid]::NewGuid().ToString('N')+'.json'); New-Item -ItemType Directory -Force -Path (Split-Path $local -Parent) | Out-Null
        $json=($report | ConvertTo-Json -Depth 32)+"`n"; [IO.File]::WriteAllText($local,$json,[Text.UTF8Encoding]::new($false))
        $temp="$current.$([guid]::NewGuid().ToString('N')).tmp"; [IO.File]::WriteAllText($temp,$json,[Text.UTF8Encoding]::new($false)); [IO.File]::Move($temp,$current,$true)
    } finally { if ($acquired) { $lock.Unlock(0,1) }; $lock.Dispose() }
}
function Resolve-SrnRuntime {
    param([Parameter(Mandatory)][string]$Name, [Parameter(Mandatory)][string]$Path, [string]$ExpectedSha256,
          [string]$RepositoryRoot = (Split-Path $PSScriptRoot -Parent))
    $target=Resolve-SrnRealPath $Path
    if ($Name -eq 'python' -and $target -match '(?i)[/\\]WindowsApps[/\\]') { throw 'Windows Store Python shim is unsupported; use bundled workspace Python' }
    Assert-SrnDurablePath $target $RepositoryRoot
    $hash=(Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($ExpectedSha256 -and $hash -cne $ExpectedSha256) { throw "Installed runtime changed: $target" }
    [pscustomobject]@{name=$Name;path=$target;sha256=$hash;origin='installed'}
}
Export-ModuleMember -Function Resolve-SrnRealPath, Test-SrnWithin, Assert-SrnDurablePath, Get-SrnToolsRoot, Resolve-SrnTool, Register-SrnToolUse, Resolve-SrnRuntime
