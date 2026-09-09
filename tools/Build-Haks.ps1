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
    & $tool -f $destination --no-symlinks -c $source
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $destination -PathType Leaf)) {
        throw "Failed to build $($hak.Name).hak"
    }
    $listing = @(& $tool -f $destination -t | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($LASTEXITCODE -ne 0) { throw "Failed to reopen $($hak.Name).hak" }
    $expected = @(Get-ChildItem -LiteralPath $source -File | ForEach-Object { $_.Name } | Sort-Object)
    $actual = @($listing | Sort-Object)
    if (($actual -join "`n") -cne ($expected -join "`n")) {
        throw "$($hak.Name).hak inventory does not match its source directory."
    }
    Write-Host "Built and reopened $destination ($($expected.Count) resources)"
}
