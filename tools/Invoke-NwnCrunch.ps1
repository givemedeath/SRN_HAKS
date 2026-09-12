#Requires -Version 7.0

[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$InputTexture,
    [Parameter(Mandatory)][string]$OutputTexture,
    [Parameter(Mandatory)][ValidateSet('png', 'tga', 'bmp', 'dds', 'nwn')][string]$OutputFormat,
    [ValidateSet('UseSourceOrGenerate', 'UseSource', 'Generate', 'None')][string]$MipMode = 'UseSource'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$tool = Join-Path $PSScriptRoot 'vendor/nwn_crunch/nwn_crunch.exe'
$expectedSha256 = '6AABE212EE8A4A5C166801C3C7830239E3EB15910F2743232C33666BC91AA46C'
if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) {
    throw "Missing vendored NWN Crunch executable: $tool"
}
$actualSha256 = (Get-FileHash -LiteralPath $tool -Algorithm SHA256).Hash
if ($actualSha256 -cne $expectedSha256) {
    throw "Vendored nwn_crunch.exe hash mismatch. Expected $expectedSha256; found $actualSha256."
}

$inputPath = (Resolve-Path -LiteralPath $InputTexture).Path
$outputPath = [IO.Path]::GetFullPath($OutputTexture)
if ([string]::Equals($inputPath, $outputPath, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'InputTexture and OutputTexture must be different paths.'
}
$outputDirectory = Split-Path -Parent $outputPath
if (-not (Test-Path -LiteralPath $outputDirectory -PathType Container)) {
    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
}

& $tool -file $inputPath -out $outputPath -fileformat $OutputFormat -mipMode $MipMode -noprogress
if ($LASTEXITCODE -ne 0) {
    throw "NWN Crunch failed with exit code $LASTEXITCODE."
}
if (-not (Test-Path -LiteralPath $outputPath -PathType Leaf)) {
    throw "NWN Crunch did not produce the requested output: $outputPath"
}
Write-Host "Texture conversion complete: $outputPath"
