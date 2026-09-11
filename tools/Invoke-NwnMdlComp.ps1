#Requires -Version 7.0

[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Compile', 'Decompile')][string]$Mode,
    [Parameter(Mandatory)][string]$InputModel,
    [Parameter(Mandatory)][string]$OutputModel,
    [switch]$KeepEmptyFaces
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$tool = Join-Path $PSScriptRoot 'vendor/nwnmdlcomp/nwnmdlcomp.exe'
$expectedSha256 = '0E32070C3E00A07A5F9E93B7E4A63A40DD5486B974900BBB8A0D2F4424C612BB'
if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) { throw "Missing vendored model compiler: $tool" }
$actualSha256 = (Get-FileHash -LiteralPath $tool -Algorithm SHA256).Hash
if ($actualSha256 -cne $expectedSha256) {
    throw "Vendored nwnmdlcomp.exe hash mismatch. Expected $expectedSha256; found $actualSha256."
}

$inputPath = (Resolve-Path -LiteralPath $InputModel).Path
$outputPath = [IO.Path]::GetFullPath($OutputModel)
if ([string]::Equals($inputPath, $outputPath, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'InputModel and OutputModel must be different paths.'
}
$outputDirectory = Split-Path -Parent $outputPath
if (-not (Test-Path -LiteralPath $outputDirectory -PathType Container)) {
    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
}

$arguments = [Collections.Generic.List[string]]::new()
$arguments.Add($(if ($Mode -eq 'Compile') { '-c' } else { '-d' }))
$arguments.Add('-e')
if ($Mode -eq 'Compile' -and $KeepEmptyFaces) { $arguments.Add('-n') }
$arguments.Add($inputPath)
$arguments.Add($outputPath)

& $tool @arguments
if ($LASTEXITCODE -ne 0) { throw "nwnmdlcomp failed with exit code $LASTEXITCODE." }
if (-not (Test-Path -LiteralPath $outputPath -PathType Leaf)) {
    throw "nwnmdlcomp did not produce the requested output: $outputPath"
}
Write-Host "$Mode complete: $outputPath"
