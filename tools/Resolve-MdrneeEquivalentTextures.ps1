#Requires -Version 7.0

[CmdletBinding()]
param(
    [switch]$Apply,
    [string]$TileRawPath,
    [string]$PlaceableRawPath,
    [string]$AuditPath,
    [string]$ExceptionsPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
if (-not $TileRawPath) { $TileRawPath = Join-Path $repositoryRoot '.quarantine/mdrnee_tile/raw' }
if (-not $PlaceableRawPath) { $PlaceableRawPath = Join-Path $repositoryRoot '.quarantine/mdrnee_placeable/raw' }
if (-not $AuditPath) { $AuditPath = Join-Path $repositoryRoot 'docs/imports/mdrnee_placeable-cross-hak-audit.json' }
if (-not $ExceptionsPath) { $ExceptionsPath = Join-Path $repositoryRoot 'docs/imports/mdrnee_texture-equivalence-exceptions.json' }

$tileRaw = (Resolve-Path -LiteralPath $TileRawPath).Path
$placeableRaw = (Resolve-Path -LiteralPath $PlaceableRawPath).Path
$audit = Get-Content -LiteralPath $AuditPath -Raw | ConvertFrom-Json
$configuration = Get-Content -LiteralPath $ExceptionsPath -Raw | ConvertFrom-Json
$packRoots = @(Get-ChildItem -LiteralPath $repositoryRoot -Directory | Where-Object Name -Like 'srn_*')

if ($configuration.schemaVersion -ne 1) { throw 'Unsupported equivalence-exception schema.' }
$exceptions = @($configuration.exceptions)
if ($exceptions.Count -ne 32) { throw "Expected 32 equivalence exceptions; found $($exceptions.Count)." }
$duplicateNames = @($exceptions.resource | Group-Object | Where-Object Count -ne 1)
if ($duplicateNames.Count -gt 0) { throw "Duplicate equivalence exception: $($duplicateNames.Name -join ', ')" }

function Get-NwnDdsMetadata {
    param([Parameter(Mandatory)][string]$Path)
    $stream = [IO.File]::OpenRead($Path)
    $reader = [IO.BinaryReader]::new($stream)
    try {
        [pscustomobject]@{
            width = [int]$reader.ReadUInt32()
            height = [int]$reader.ReadUInt32()
            encoding = [int]$reader.ReadUInt32()
            bytes = $stream.Length
        }
    }
    finally {
        $reader.Dispose()
        $stream.Dispose()
    }
}

$records = [Collections.Generic.List[object]]::new()
foreach ($exception in $exceptions) {
    $name = [string]$exception.resource
    $selectedSource = [string]$exception.selectedSource
    if ($selectedSource -notin @('tile', 'placeable')) {
        throw "Invalid selectedSource '$selectedSource' for $name."
    }
    $overlaps = @($audit.tileOverlap | Where-Object name -CEQ $name)
    if ($overlaps.Count -ne 1 -or $overlaps[0].sameBytes -or $overlaps[0].type -ne 'dds') {
        throw "Exception does not identify one differing DDS overlap: $name"
    }
    $overlap = $overlaps[0]
    $tilePath = Join-Path $tileRaw $name
    $placeablePath = Join-Path $placeableRaw $name
    $tileMetadata = Get-NwnDdsMetadata -Path $tilePath
    $placeableMetadata = Get-NwnDdsMetadata -Path $placeablePath
    if ($tileMetadata.width -ne $placeableMetadata.width -or
        $tileMetadata.height -ne $placeableMetadata.height) {
        throw "Equivalence exception has unequal dimensions: $name"
    }

    $selectedPath = if ($selectedSource -eq 'tile') { $tilePath } else { $placeablePath }
    $expectedHash = if ($selectedSource -eq 'tile') { $overlap.tileSha256 } else { $overlap.placeableSha256 }
    $selectedHash = (Get-FileHash -LiteralPath $selectedPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($selectedHash -cne $expectedHash.ToLowerInvariant()) {
        throw "Selected source hash mismatch for $name."
    }

    $staged = @($packRoots | ForEach-Object {
        $candidate = Join-Path $_.FullName $name
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { Get-Item -LiteralPath $candidate }
    })
    if ($staged.Count -lt 2) { throw "Expected at least two staged copies for $name; found $($staged.Count)." }
    $updatedPacks = [Collections.Generic.List[string]]::new()
    foreach ($target in $staged) {
        $targetHash = (Get-FileHash -LiteralPath $target.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($targetHash -cne $selectedHash) {
            $updatedPacks.Add($target.Directory.Name)
            if ($Apply) {
                Copy-Item -LiteralPath $selectedPath -Destination $target.FullName -Force
                $copiedHash = (Get-FileHash -LiteralPath $target.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($copiedHash -cne $selectedHash) { throw "Copy verification failed: $($target.FullName)" }
            }
        }
    }
    $records.Add([ordered]@{
        resource = $name
        selectedSource = $selectedSource
        dimensions = "$($tileMetadata.width)x$($tileMetadata.height)"
        tileEncoding = $tileMetadata.encoding
        placeableEncoding = $placeableMetadata.encoding
        selectedSha256 = $selectedHash
        stagedPacks = @($staged.Directory.Name | Sort-Object)
        updatedPacks = @($updatedPacks | Sort-Object)
    })
}

[ordered]@{
    schemaVersion = 1
    applied = [bool]$Apply
    exceptionCount = $records.Count
    tileSelections = @($records | Where-Object selectedSource -eq 'tile').Count
    placeableSelections = @($records | Where-Object selectedSource -eq 'placeable').Count
    records = @($records)
} | ConvertTo-Json -Depth 8
