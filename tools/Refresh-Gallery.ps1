[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Toolchain,
    [Parameter(Mandatory)][string]$MigrationReceipt,
    [Parameter(Mandatory)][string]$BindingTemplate,
    [Parameter(Mandatory)][string]$OutputDirectory,
    [string]$Configuration = 'test-modules/srn_gallery/gallery.json'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Push-Location $repoRoot
try {
    $destination = [System.IO.Path]::GetFullPath($OutputDirectory)
    if (Test-Path -LiteralPath $destination) { throw 'Use a fresh gallery refresh directory.' }
    if (-not $destination.StartsWith((Join-Path $repoRoot 'output')+[System.IO.Path]::DirectorySeparatorChar,[System.StringComparison]::OrdinalIgnoreCase)) { throw 'Refresh receipts and bindings must stay under ignored output/.' }
    $template = Get-Content -LiteralPath $BindingTemplate -Raw | ConvertFrom-Json
    & ./tools/Build-Haks.ps1
    New-Item -ItemType Directory -Path $destination | Out-Null
    $binding = Join-Path $destination 'binding.json'
    & ./tools/Bind-Gallery.ps1 -Stock $template.stock -GameRoot $template.gameRoot `
        -Fixture @($template.fixtures | ForEach-Object { $_.path }) -Output $binding
    & ./tools/Build-Gallery.ps1 -Toolchain $Toolchain -MigrationReceipt $MigrationReceipt `
        -Binding $binding -Configuration $Configuration -OutputDirectory (Join-Path $destination 'run')
}
finally { Pop-Location }
