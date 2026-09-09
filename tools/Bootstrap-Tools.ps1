[CmdletBinding()]
param([switch]$Force)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$lockPath = Join-Path $PSScriptRoot 'toolchain.lock.json'
$lock = Get-Content -Raw -LiteralPath $lockPath | ConvertFrom-Json -Depth 16

$architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture
if ($architecture -ne [System.Runtime.InteropServices.Architecture]::X64) {
    throw "Unsupported architecture '$architecture'. The pinned toolchain supports x64 only."
}

$platformKey = if ($IsWindows) { 'windows-x64' } elseif ($IsLinux) { 'linux-x64' } else { throw 'Only Windows x64 and Linux x64 are supported.' }
$platform = $lock.platforms.$platformKey
$destination = Join-Path $repositoryRoot ".tools/neverwinter/$($lock.releaseTag)/$platformKey"
$markerPath = Join-Path $destination '.complete.json'

if (-not $Force -and (Test-Path -LiteralPath $markerPath -PathType Leaf)) {
    try {
        $marker = Get-Content -Raw -LiteralPath $markerPath | ConvertFrom-Json
        if ($marker.archiveSha256 -eq $platform.sha256 -and $marker.releaseTag -eq $lock.releaseTag) {
            Write-Output $destination
            exit 0
        }
    }
    catch {
        Write-Verbose "Ignoring an invalid tool marker: $($_.Exception.Message)"
    }
}

$cacheRoot = Join-Path $repositoryRoot '.tools/downloads'
New-Item -ItemType Directory -Force -Path $cacheRoot | Out-Null
$archivePath = Join-Path $cacheRoot $platform.fileName

if ($Force -or -not (Test-Path -LiteralPath $archivePath -PathType Leaf)) {
    $partialPath = "$archivePath.partial"
    try {
        Invoke-WebRequest -Uri $platform.url -OutFile $partialPath
        [System.IO.File]::Move($partialPath, $archivePath, $true)
    }
    finally {
        if (Test-Path -LiteralPath $partialPath) { Remove-Item -LiteralPath $partialPath -Force }
    }
}

$actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath).Hash.ToLowerInvariant()
if ($actualHash -ne $platform.sha256) {
    throw "Tool archive hash mismatch. Expected $($platform.sha256), got $actualHash. Delete $archivePath and retry."
}

if (Test-Path -LiteralPath $destination) {
    $resolvedDestination = [System.IO.Path]::GetFullPath($destination)
    $resolvedToolsRoot = [System.IO.Path]::GetFullPath((Join-Path $repositoryRoot '.tools'))
    if (-not $resolvedDestination.StartsWith($resolvedToolsRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to replace unexpected tool path: $resolvedDestination"
    }
    Remove-Item -LiteralPath $resolvedDestination -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $destination | Out-Null
Expand-Archive -LiteralPath $archivePath -DestinationPath $destination

foreach ($toolName in @($platform.executables.erf, $platform.executables.tlk)) {
    $matches = @(Get-ChildItem -LiteralPath $destination -Recurse -File | Where-Object { $_.Name -ceq $toolName })
    if ($matches.Count -ne 1) {
        throw "Verified archive did not contain exactly one $toolName."
    }
}

$marker = [ordered]@{
    schemaVersion = 1
    sourceRepository = $lock.sourceRepository
    releaseTag = $lock.releaseTag
    commit = $lock.commit
    platform = $platformKey
    archiveSha256 = $platform.sha256
    executables = $platform.executables
}
$marker | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $markerPath -Encoding utf8
Write-Output $destination
