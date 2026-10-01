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
    param([Parameter(Mandatory)][ValidateSet('erf', 'gff', 'tlk', 'resman_cat', 'resman_grep')][string]$Name)

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

function Resolve-SrnQuarantinePath {
    param([Parameter(Mandatory)][string]$RelativePath)
    if ([string]::IsNullOrWhiteSpace($RelativePath) -or [IO.Path]::IsPathRooted($RelativePath)) { throw 'Expected a quarantine-relative path.' }
    $root = [IO.Path]::GetFullPath((Join-Path (Get-SrnRepositoryRoot) '.quarantine'))
    $resolved = [IO.Path]::GetFullPath((Join-Path $root $RelativePath))
    $comparison = if ($IsWindows) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
    if (-not $resolved.StartsWith($root + [IO.Path]::DirectorySeparatorChar, $comparison)) { throw 'Path escapes quarantine.' }
    $current = $resolved
    while ($current -and $current.Length -ge $root.Length) {
        if ((Test-Path -LiteralPath $current) -and
            ((Get-Item -LiteralPath $current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Reparse point not allowed: $current" }
        $current = Split-Path $current -Parent
    }
    $resolved
}

function Publish-SrnDirectorySet {
    param([Parameter(Mandatory)][object[]]$Replacements)
    $quarantine = [IO.Path]::GetFullPath((Join-Path (Get-SrnRepositoryRoot) '.quarantine'))
    $targets = @($Replacements | ForEach-Object {
        $source = Resolve-SrnQuarantinePath ([IO.Path]::GetRelativePath($quarantine, [IO.Path]::GetFullPath($_.source)))
        $destination = Resolve-SrnQuarantinePath ([IO.Path]::GetRelativePath($quarantine, [IO.Path]::GetFullPath($_.destination)))
        if (-not (Test-Path -LiteralPath $source -PathType Container)) { throw "Missing replacement directory: $source" }
        if ((Test-Path -LiteralPath $destination) -and -not (Test-Path -LiteralPath $destination -PathType Container)) { throw "Destination is not a directory: $destination" }
        [pscustomobject]@{source=$source; destination=$destination; name=[IO.Path]::GetFileName($destination)}
    })
    $backupParent = Split-Path (Split-Path $targets[0].destination -Parent) -Parent
    $backupPath = Resolve-SrnQuarantinePath ([IO.Path]::GetRelativePath($quarantine, (Join-Path $backupParent ('.analysis-backup-' + [Guid]::NewGuid().ToString('N')))))
    $backupRoot = New-Item -ItemType Directory -Path $backupPath
    $backedUp = [Collections.Generic.List[object]]::new()
    $installed = [Collections.Generic.List[object]]::new()
    $preserveBackup = $false
    try {
        foreach ($target in $targets) {
            New-Item -ItemType Directory -Path (Split-Path $target.destination -Parent) -Force | Out-Null
            if (Test-Path -LiteralPath $target.destination) {
                [IO.Directory]::Move($target.destination, (Join-Path $backupRoot.FullName $target.name))
                $backedUp.Add($target)
            }
        }
        foreach ($target in $targets) {
            [IO.Directory]::Move($target.source, $target.destination)
            $installed.Add($target)
        }
    }
    catch {
        $publishFailure = $_
        try {
            foreach ($target in $installed) { Remove-Item -LiteralPath $target.destination -Recurse -Force }
            foreach ($target in $backedUp) { [IO.Directory]::Move((Join-Path $backupRoot.FullName $target.name), $target.destination) }
        }
        catch {
            $preserveBackup = $true
            throw "Could not restore previous analysis; backups preserved at $($backupRoot.FullName): $($_.Exception.Message)"
        }
        throw $publishFailure
    }
    finally {
        if (-not $preserveBackup -and (Test-Path -LiteralPath $backupRoot.FullName)) { Remove-Item -LiteralPath $backupRoot.FullName -Recurse -Force }
    }
}

Export-ModuleMember -Function Get-SrnRepositoryRoot, Get-SrnConfiguration, Resolve-SrnRepositoryPath, Get-SrnTool, Write-SrnJsonAtomic, Resolve-SrnQuarantinePath, Publish-SrnDirectorySet
