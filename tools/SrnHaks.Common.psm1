Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-SrnRepositoryRoot {
    return Split-Path -Parent $PSScriptRoot
}

function Get-SrnConfiguration {
    $path = Join-Path (Get-SrnRepositoryRoot) 'hakbuilder.json'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing configuration: $path"
    }

    try {
        return Get-Content -Raw -LiteralPath $path | ConvertFrom-Json -Depth 32
    }
    catch {
        throw "Invalid hakbuilder.json: $($_.Exception.Message)"
    }
}

function Resolve-SrnRepositoryPath {
    param([Parameter(Mandatory)][string]$Path)

    $root = [System.IO.Path]::GetFullPath((Get-SrnRepositoryRoot))
    $resolved = [System.IO.Path]::GetFullPath((Join-Path $root $Path))
    $prefix = $root.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Configured path escapes the repository: $Path"
    }
    return $resolved
}

function Get-SrnTool {
    param([Parameter(Mandatory)][ValidateSet('erf', 'tlk')][string]$Name)

    $toolRoot = & (Join-Path $PSScriptRoot 'Bootstrap-Tools.ps1')
    $markerPath = Join-Path $toolRoot '.complete.json'
    $marker = Get-Content -Raw -LiteralPath $markerPath | ConvertFrom-Json
    $fileName = $marker.executables.$Name
    $matches = @(Get-ChildItem -LiteralPath $toolRoot -Recurse -File | Where-Object { $_.Name -ceq $fileName })
    if ($matches.Count -ne 1) {
        throw "Expected exactly one $fileName under $toolRoot; found $($matches.Count)."
    }
    if (-not $IsWindows) {
        & chmod +x -- $matches[0].FullName
        if ($LASTEXITCODE -ne 0) { throw "Could not mark $fileName executable." }
    }
    return $matches[0].FullName
}

function Write-SrnJsonAtomic {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)]$Value
    )

    $temporary = "$Path.tmp.$([Guid]::NewGuid().ToString('N'))"
    try {
        $json = $Value | ConvertTo-Json -Depth 32
        [System.IO.File]::WriteAllText($temporary, $json + "`n", [System.Text.UTF8Encoding]::new($false))
        [System.IO.File]::Move($temporary, $Path, $true)
    }
    finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

Export-ModuleMember -Function Get-SrnRepositoryRoot, Get-SrnConfiguration, Resolve-SrnRepositoryPath, Get-SrnTool, Write-SrnJsonAtomic
