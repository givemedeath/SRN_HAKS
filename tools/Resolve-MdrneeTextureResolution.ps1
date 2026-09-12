#Requires -Version 7.0

[CmdletBinding()]
param(
    [switch]$Apply,
    [string]$TileRawPath,
    [string]$PlaceableRawPath,
    [string]$AuditPath,
    [string]$ReportPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
if (-not $TileRawPath) { $TileRawPath = Join-Path $repositoryRoot '.quarantine/mdrnee_tile/raw' }
if (-not $PlaceableRawPath) { $PlaceableRawPath = Join-Path $repositoryRoot '.quarantine/mdrnee_placeable/raw' }
if (-not $AuditPath) { $AuditPath = Join-Path $repositoryRoot 'docs/imports/mdrnee_placeable-cross-hak-audit.json' }
if (-not $ReportPath) { $ReportPath = Join-Path $repositoryRoot 'docs/imports/mdrnee_texture-resolution-normalization.json' }

$tileRaw = (Resolve-Path -LiteralPath $TileRawPath).Path
$placeableRaw = (Resolve-Path -LiteralPath $PlaceableRawPath).Path
$audit = Get-Content -LiteralPath $AuditPath -Raw | ConvertFrom-Json
$packRoots = @(Get-ChildItem -LiteralPath $repositoryRoot -Directory | Where-Object Name -Like 'srn_*')

function Get-TextureDimensions {
    param([Parameter(Mandatory)][string]$Path)

    $extension = [IO.Path]::GetExtension($Path).ToLowerInvariant()
    $stream = [IO.File]::OpenRead($Path)
    $reader = [IO.BinaryReader]::new($stream)
    try {
        if ($extension -eq '.dds') {
            $width = $reader.ReadUInt32()
            $height = $reader.ReadUInt32()
        }
        elseif ($extension -eq '.tga') {
            $stream.Position = 12
            $width = $reader.ReadUInt16()
            $height = $reader.ReadUInt16()
        }
        else {
            throw "Unsupported texture extension: $extension"
        }
    }
    finally {
        $reader.Dispose()
        $stream.Dispose()
    }
    if ($width -le 0 -or $height -le 0) { throw "Invalid texture dimensions in $Path" }
    [pscustomobject]@{ width = [int]$width; height = [int]$height; pixels = [long]$width * [long]$height }
}

$records = [Collections.Generic.List[object]]::new()
foreach ($overlap in @($audit.tileOverlap | Where-Object {
    -not $_.sameBytes -and $_.type -in @('dds', 'tga')
})) {
    $tilePath = Join-Path $tileRaw $overlap.name
    $placeablePath = Join-Path $placeableRaw $overlap.name
    $tileDimensions = Get-TextureDimensions -Path $tilePath
    $placeableDimensions = Get-TextureDimensions -Path $placeablePath
    if ($tileDimensions.width -eq $placeableDimensions.width -and
        $tileDimensions.height -eq $placeableDimensions.height) {
        continue
    }
    if ($tileDimensions.pixels -eq $placeableDimensions.pixels) {
        throw "Ambiguous equal-area dimensions for $($overlap.name)."
    }

    $winner = if ($tileDimensions.pixels -gt $placeableDimensions.pixels) { 'tile' } else { 'placeable' }
    $winnerPath = if ($winner -eq 'tile') { $tilePath } else { $placeablePath }
    $winnerDimensions = if ($winner -eq 'tile') { $tileDimensions } else { $placeableDimensions }
    $loserDimensions = if ($winner -eq 'tile') { $placeableDimensions } else { $tileDimensions }
    $expectedWinnerHash = if ($winner -eq 'tile') { $overlap.tileSha256 } else { $overlap.placeableSha256 }
    $winnerHash = (Get-FileHash -LiteralPath $winnerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($winnerHash -cne $expectedWinnerHash.ToLowerInvariant()) {
        throw "Source hash mismatch for $($overlap.name): expected $expectedWinnerHash; found $winnerHash."
    }

    $staged = @($packRoots | ForEach-Object {
        $candidate = Join-Path $_.FullName $overlap.name
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { Get-Item -LiteralPath $candidate }
    })
    if ($staged.Count -eq 0) { throw "No staged copy found for $($overlap.name)." }

    $updatedPacks = [Collections.Generic.List[string]]::new()
    foreach ($target in $staged) {
        $targetHash = (Get-FileHash -LiteralPath $target.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($targetHash -cne $winnerHash) {
            $updatedPacks.Add($target.Directory.Name)
            if ($Apply) {
                Copy-Item -LiteralPath $winnerPath -Destination $target.FullName -Force
                $copiedHash = (Get-FileHash -LiteralPath $target.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($copiedHash -cne $winnerHash) { throw "Copy verification failed: $($target.FullName)" }
            }
        }
    }

    $records.Add([ordered]@{
        resource = $overlap.name
        winner = $winner
        winnerDimensions = "$($winnerDimensions.width)x$($winnerDimensions.height)"
        supersededDimensions = "$($loserDimensions.width)x$($loserDimensions.height)"
        winnerSha256 = $winnerHash
        stagedPacks = @($staged.Directory.Name | Sort-Object)
        updatedPacks = @($updatedPacks | Sort-Object)
    })
}

$report = [ordered]@{
    schemaVersion = 1
    policy = 'For differing MDRNEE texture identities with unequal dimensions, propagate the greater pixel-area source bytes to every staged pack carrying that identity.'
    applied = [bool]$Apply
    textureCount = $records.Count
    tileWinners = @($records | Where-Object winner -eq 'tile').Count
    placeableWinners = @($records | Where-Object winner -eq 'placeable').Count
    records = @($records)
}

if ($Apply) {
    $json = $report | ConvertTo-Json -Depth 8
    [IO.File]::WriteAllText([IO.Path]::GetFullPath($ReportPath), $json + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
}
$report | ConvertTo-Json -Depth 8
