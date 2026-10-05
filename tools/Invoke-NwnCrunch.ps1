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

Import-Module (Join-Path $PSScriptRoot 'SrnTools.psm1') -Force
$resolvedTool = Resolve-SrnTool -Name 'crunch'
Register-SrnToolUse -Tool $resolvedTool -Inputs @($InputTexture)
$tool = $resolvedTool.path

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
