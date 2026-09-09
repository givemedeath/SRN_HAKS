[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'SrnHaks.Common.psm1') -Force

$configuration = Get-SrnConfiguration
$source = Resolve-SrnRepositoryPath -Path $configuration.TlkSource
$output = Resolve-SrnRepositoryPath -Path $configuration.TlkPath
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing canonical TLK source: $source" }

$outputDirectory = Split-Path -Parent $output
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$tool = Get-SrnTool -Name tlk

& $tool -i $source -l json -o $output -k tlk
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $output -PathType Leaf)) {
    throw 'nwn_tlk failed to produce the shared TLK.'
}
Write-Host "Built $output"
