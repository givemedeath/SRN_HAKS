[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Stock,
    [Parameter(Mandatory)][string]$GameRoot,
    [string[]]$Fixture = @(),
    [Parameter(Mandatory)][string]$Output
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
function Get-GalleryPin([string]$Path) {
    $file = Get-Item -LiteralPath $Path
    if ($file.PSIsContainer) { throw "Individual file required: $Path" }
    @{ path=$file.FullName; sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
}
Push-Location $repoRoot
try {
    $destination = [System.IO.Path]::GetFullPath($Output)
    if (Test-Path -LiteralPath $destination) { throw 'Use a fresh ignored binding filename.' }
    if (-not $destination.StartsWith((Join-Path $repoRoot 'output')+[System.IO.Path]::DirectorySeparatorChar,[System.StringComparison]::OrdinalIgnoreCase)) { throw 'Local bindings must stay under ignored output/.' }
    $builder = Get-Content ./hakbuilder.json -Raw | ConvertFrom-Json
    $inputs = @('ttr01.set','ttr01_edge.2da','nw_humanmerc001.utc.json' | ForEach-Object { Get-GalleryPin (Join-Path $Stock $_) })
    $inputs += @($builder.HakList | ForEach-Object { Get-GalleryPin (Join-Path $builder.OutputPath ($_.Name+'.hak')) })
    $inputs += Get-GalleryPin $builder.TlkPath
    $binding = @{ stock=(Resolve-Path -LiteralPath $Stock).Path; gameRoot=(Resolve-Path -LiteralPath $GameRoot).Path; fixtures=@($Fixture | ForEach-Object { Get-GalleryPin $_ }); inputs=$inputs }
    New-Item -ItemType Directory -Force -Path (Split-Path $destination -Parent) | Out-Null
    [System.IO.File]::WriteAllText($destination,($binding | ConvertTo-Json -Depth 8)+"`n",[System.Text.UTF8Encoding]::new($false))
}
finally { Pop-Location }
