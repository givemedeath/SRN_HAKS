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

Import-Module (Join-Path $PSScriptRoot 'SrnTools.psm1') -Force
$resolvedTool = Resolve-SrnTool -Name 'mdlcomp'
Register-SrnToolUse -Tool $resolvedTool -Inputs @($InputModel)
$tool = $resolvedTool.path

$inputPath = (Resolve-Path -LiteralPath $InputModel).Path
$outputPath = [IO.Path]::GetFullPath($OutputModel)
if ([string]::Equals($inputPath, $outputPath, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'InputModel and OutputModel must be different paths.'
}
$outputDirectory = Split-Path -Parent $outputPath
if (-not (Test-Path -LiteralPath $outputDirectory -PathType Container)) {
    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
}
if (Test-Path -LiteralPath $outputPath -PathType Leaf) {
    Remove-Item -LiteralPath $outputPath -Force
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
