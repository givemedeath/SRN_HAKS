#Requires -Version 7.0
[CmdletBinding()]
param([switch]$Force, [string]$ToolsRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'SrnTools.psm1') -Force
$root = (Get-SrnToolsRoot -ToolsRoot $ToolsRoot).path
$lock = Get-Content -Raw -Encoding utf8 (Join-Path $PSScriptRoot 'toolchain.lock.json') | ConvertFrom-Json -AsHashtable
$platformKey = if ($IsWindows) { 'windows-x64' } elseif ($IsLinux) { 'linux-x64' } else { throw 'Unsupported platform' }
if ([Runtime.InteropServices.RuntimeInformation]::OSArchitecture -ne 'X64') { throw 'Pinned tools require x64' }
$platform = $lock.platforms[$platformKey]
$destination = Join-Path $root "neverwinter/$($lock.releaseTag)/$platformKey"
$locks = Join-Path $root 'locks'; New-Item -ItemType Directory -Force -Path $locks | Out-Null
$stream = [IO.File]::Open((Join-Path $locks "neverwinter-$($lock.releaseTag)-$platformKey.lock"), 'OpenOrCreate', 'ReadWrite', 'ReadWrite')
if (-not $stream.Length) { $stream.WriteByte(48); $stream.Flush() }
$acquired=$false; $stage=$null; $backup=$null; $end=[DateTime]::UtcNow.AddMinutes(5)
try {
    while (-not $acquired) { try { $stream.Lock(0,1); $acquired=$true } catch { if ([DateTime]::UtcNow -ge $end) { throw }; Start-Sleep -Milliseconds 100 } }
    # Force never replaces a byte-verified installation. Markers are informational.
    $valid=$true
    foreach ($name in $platform.executables.Keys) { try { $null=Resolve-SrnTool -Name $name -ToolsRoot $root } catch { $valid=$false; break } }
    if ($valid) { Write-Output $destination; return }
    $cache=Join-Path $root 'downloads'; New-Item -ItemType Directory -Force -Path $cache | Out-Null
    $archive=Join-Path $cache $platform.fileName
    $archiveValid=(Test-Path -LiteralPath $archive -PathType Leaf) -and ((Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $platform.sha256)
    if (-not $archiveValid) {
        $partial="$archive.$([guid]::NewGuid().ToString('N')).partial"
        try {
            Invoke-WebRequest -Uri $platform.url -OutFile $partial
            if ((Get-FileHash $partial -Algorithm SHA256).Hash.ToLowerInvariant() -cne $platform.sha256) { throw 'Tool archive hash mismatch' }
            [IO.File]::Move($partial,$archive,$true)
        } finally { if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Force } }
    }
    $stage=Join-Path $root ('staging/neverwinter-'+[guid]::NewGuid().ToString('N')); New-Item -ItemType Directory -Force -Path $stage | Out-Null
    Expand-Archive -LiteralPath $archive -DestinationPath $stage
    $inventory=Get-Content -Raw -Encoding utf8 (Join-Path $PSScriptRoot 'shared-tools.lock.json') | ConvertFrom-Json -AsHashtable
    foreach ($name in $platform.executables.Keys) {
        $relative=[IO.Path]::GetRelativePath($destination,(Join-Path $root $inventory.tools[$name].platforms[$platformKey].relativePath))
        $file=Resolve-SrnRealPath (Join-Path $stage $relative)
        if (-not (Test-SrnWithin $file $stage) -or -not (Test-Path $file -PathType Leaf) -or (Get-FileHash $file -Algorithm SHA256).Hash.ToLowerInvariant() -cne $platform.executableSha256[$name]) { throw "Staged executable failed verification: $name" }
        if (-not $IsWindows) { & chmod +x -- $file; if ($LASTEXITCODE) { throw 'chmod failed' } }
    }
    @{schemaVersion=2; releaseTag=$lock.releaseTag; platform=$platformKey; archiveSha256=$platform.sha256; executables=$platform.executables; executableSha256=$platform.executableSha256} | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath (Join-Path $stage '.complete.json') -Encoding utf8
    New-Item -ItemType Directory -Force -Path (Split-Path $destination -Parent) | Out-Null
    if (-not (Test-SrnWithin $destination $root)) { throw 'Publication escapes shared root' }; Assert-SrnDurablePath $destination
    if (Test-Path -LiteralPath $destination) { $backup=Join-Path $root ('staging/replaced-'+[guid]::NewGuid().ToString('N')); [IO.Directory]::Move($destination,$backup) }
    try { [IO.Directory]::Move($stage,$destination); $stage=$null }
    catch { if ($backup) { [IO.Directory]::Move($backup,$destination); $backup=$null }; throw }
    # Invalid prior installs remain available for diagnosis.
    Write-Output $destination
} finally {
    if ($stage -and (Test-Path -LiteralPath $stage)) {
        $resolved=Resolve-SrnRealPath $stage
        if (-not (Test-SrnWithin $resolved (Join-Path $root 'staging'))) { throw 'Refusing cleanup outside staging' }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
    if ($acquired) { $stream.Unlock(0,1) }; $stream.Dispose()
}
