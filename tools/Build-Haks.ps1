[CmdletBinding()]
param(
    [string[]]$Pack,
    [switch]$SkipTlk
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'SrnHaks.Common.psm1') -Force

$configuration = Get-SrnConfiguration
if (-not $SkipTlk) { & (Join-Path $PSScriptRoot 'Build-Tlk.ps1') }

$registered = @($configuration.HakList)
if ($Pack) {
    $unknown = @($Pack | Where-Object { $_ -notin @($registered.Name) })
    if ($unknown.Count -gt 0) { throw "Unknown HAK pack(s): $($unknown -join ', ')" }
    $registered = @($registered | Where-Object { $_.Name -in $Pack })
}

$outputDirectory = Resolve-SrnRepositoryPath -Path $configuration.OutputPath
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
if ($registered.Count -eq 0) {
    Write-Host 'No HAKs are registered; TLK build completed.'
    exit 0
}

$tool = Get-SrnTool -Name erf
foreach ($hak in $registered) {
    $source = Resolve-SrnRepositoryPath -Path $hak.Path
    if (-not (Test-Path -LiteralPath $source -PathType Container)) { throw "Missing HAK source directory: $source" }
    $destination = Join-Path $outputDirectory "$($hak.Name).hak"
    # Files the pack leaves out as copies of files it holds (Get-SrnHakCopies) are packed from a folder of hard
    # links to those files, each under the copy's name; a file system without hard links gets real copies.
    $copies = Get-SrnHakCopies -Hak $hak
    $entries = @($source)
    $stage = Join-Path $outputDirectory ".copies-$($hak.Name)"
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
    try {
        if ($copies.Count -gt 0) {
            New-Item -ItemType Directory -Path $stage | Out-Null
            foreach ($copy in $copies.Keys) {
                $held = Join-Path $source $copies[$copy]
                try { New-Item -ItemType HardLink -Path (Join-Path $stage $copy) -Target $held -ErrorAction Stop | Out-Null }
                catch { Copy-Item -LiteralPath $held -Destination (Join-Path $stage $copy) }
            }
            $entries += $stage
        }
        & $tool -f $destination --no-symlinks -c @entries
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $destination -PathType Leaf)) {
            throw "Failed to build $($hak.Name).hak"
        }
    }
    finally {
        if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
    }
    $listing = @(& $tool -f $destination -t | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($LASTEXITCODE -ne 0) { throw "Failed to reopen $($hak.Name).hak" }
    $expected = @(@(Get-ChildItem -LiteralPath $source -File | ForEach-Object { $_.Name }) + @($copies.Keys) | Sort-Object)
    $actual = @($listing | Sort-Object)
    if (($actual -join "`n") -cne ($expected -join "`n")) {
        throw "$($hak.Name).hak inventory does not match its source directory and copies list."
    }
    Write-Host "Built and reopened $destination ($($expected.Count) resources$(if ($copies.Count) { ", $($copies.Count) of them copies" }))"
}
