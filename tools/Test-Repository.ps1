[CmdletBinding()]
param(
    [string]$ChangedSince,
    [switch]$AllPacks,
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

Import-Module (Join-Path $PSScriptRoot 'SrnHaks.Common.psm1') -Force

$repoRoot = Get-SrnRepositoryRoot
$configuration = Get-SrnConfiguration
$errors = [System.Collections.Generic.List[string]]::new()

function Add-ValidationError {
    param([Parameter(Mandatory)][string]$Message)
    $script:errors.Add($Message)
}

function Normalize-RelativePath {
    param([Parameter(Mandatory)][string]$Path)
    return $Path.Replace('\\', '/').TrimStart('./').TrimEnd('/')
}

function Test-GitLfsPointer {
    param([Parameter(Mandatory)][string]$Path)
    $signature = [System.Text.Encoding]::ASCII.GetBytes('version https://git-lfs.github.com/spec/v1')
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        if ($stream.Length -lt $signature.Length) { return $false }
        $buffer = [byte[]]::new($signature.Length)
        if ($stream.Read($buffer, 0, $buffer.Length) -ne $buffer.Length) { return $false }
        return [System.Linq.Enumerable]::SequenceEqual($buffer, $signature)
    }
    finally { $stream.Dispose() }
}

function Get-SizeExceptions {
    $entries = @{}
    $provenanceText = Get-Content -LiteralPath (Join-Path $repoRoot 'PROVENANCE.md') -Raw
    $matches = [regex]::Matches($provenanceText, '<!--\s*srn-size-exception\s+(\{.*?\})\s*-->', 'Singleline')
    foreach ($match in $matches) {
        try {
            $entry = $match.Groups[1].Value | ConvertFrom-Json
            $path = Normalize-RelativePath ([string]$entry.path)
            if ([string]::IsNullOrWhiteSpace($path) -or [string]::IsNullOrWhiteSpace([string]$entry.reason)) {
                Add-ValidationError 'A PROVENANCE.md size exception is missing path or reason.'
                continue
            }
            if ($entries.ContainsKey($path)) { Add-ValidationError "Duplicate size exception for '$path'." }
            else { $entries[$path] = [string]$entry.reason }
        }
        catch { Add-ValidationError "Invalid PROVENANCE.md size-exception marker: $($_.Exception.Message)" }
    }
    return $entries
}

$packByName = @{}
$packByPath = @{}
foreach ($pack in @($configuration.HakList)) {
    $name = [string]$pack.Name
    $relativePath = Normalize-RelativePath ([string]$pack.Path)
    if ($name -cnotmatch '^srn_[a-z0-9_]+$' -or $name.Length -gt 16) {
        Add-ValidationError "Invalid HAK name '$name'; expected lowercase srn_* and at most 16 characters."
    }
    if ($packByName.ContainsKey($name)) { Add-ValidationError "Duplicate HAK name '$name'." }
    else { $packByName[$name] = $pack }
    if ($relativePath -ne $name) { Add-ValidationError "HAK '$name' must use the flat path './$name/'." }
    if ($packByPath.ContainsKey($relativePath)) { Add-ValidationError "Duplicate HAK path '$relativePath'." }
    else { $packByPath[$relativePath] = $pack }
    if ($pack.CompileModels -ne $false) { Add-ValidationError "HAK '$name' must set CompileModels to false." }
}

$registeredNames = @($packByName.Keys)
$topLevelHakDirectories = @(Get-ChildItem -LiteralPath $repoRoot -Directory | Where-Object { $_.Name -like 'srn_*' -and $_.Name -ne 'srn_tlk' })
foreach ($directory in $topLevelHakDirectories) {
    if (-not $packByName.ContainsKey($directory.Name)) { Add-ValidationError "Unregistered top-level HAK directory '$($directory.Name)'." }
}

$sizeExceptions = Get-SizeExceptions
$resourceProviders = @{}
$provenanceText = Get-Content -LiteralPath (Join-Path $repoRoot 'PROVENANCE.md') -Raw
$softLimit = 15MB
$hardLimit = 100MB

foreach ($name in $registeredNames) {
    $pack = $packByName[$name]
    $packPath = Resolve-SrnRepositoryPath -Path ([string]$pack.Path)
    if (-not (Test-Path -LiteralPath $packPath -PathType Container)) {
        Add-ValidationError "Registered HAK directory '$name' does not exist."
        continue
    }
    if (@(Get-ChildItem -LiteralPath $packPath -Directory -Force).Count -gt 0) {
        Add-ValidationError "HAK '$name' contains subdirectories; packable directories must be flat."
    }
    $files = @(Get-ChildItem -LiteralPath $packPath -File -Force)
    if ($files.Count -gt 0 -and $provenanceText -cnotmatch [regex]::Escape($name)) {
        Add-ValidationError "PROVENANCE.md has no content-batch entry mentioning '$name'."
    }
    $identities = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($file in $files) {
        if ($file.Name -cne $file.Name.ToLowerInvariant()) { Add-ValidationError "Resource '$name/$($file.Name)' must be lowercase." }
        if ($file.BaseName -cnotmatch '^[a-z0-9_]{1,16}$') { Add-ValidationError "Resource stem '$name/$($file.BaseName)' must match [a-z0-9_]{1,16}." }
        if ([string]::IsNullOrWhiteSpace($file.Extension)) { Add-ValidationError "Resource '$name/$($file.Name)' has no extension." }
        $identity = $file.Name.ToLowerInvariant()
        if (-not $identities.Add($identity)) { Add-ValidationError "HAK '$name' has a case-insensitive duplicate resource '$identity'." }
        if (-not $resourceProviders.ContainsKey($identity)) { $resourceProviders[$identity] = [System.Collections.Generic.List[string]]::new() }
        $resourceProviders[$identity].Add($name)
        if ($file.Extension -ieq '.2da' -and $name -ne 'srn_2da') { Add-ValidationError "2DA resource '$name/$($file.Name)' must live in srn_2da." }
        $relativeFile = "$name/$($file.Name)"
        if ($file.Length -ge $hardLimit) { Add-ValidationError "Resource '$relativeFile' is at or above GitHub's 100 MiB limit." }
        elseif ($file.Length -gt $softLimit -and -not $sizeExceptions.ContainsKey($relativeFile)) {
            Add-ValidationError "Resource '$relativeFile' exceeds 15 MiB without a PROVENANCE.md exception."
        }
        if (Test-GitLfsPointer -Path $file.FullName) {
            Add-ValidationError "Git LFS pointer detected at '$relativeFile'; this repository does not use LFS."
        }
    }
}

foreach ($exceptionPath in $sizeExceptions.Keys) {
    $absoluteExceptionPath = Join-Path $repoRoot $exceptionPath.Replace('/', [IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path -LiteralPath $absoluteExceptionPath -PathType Leaf)) {
        Add-ValidationError "Stale size exception references missing file '$exceptionPath'."
    }
}

$declaredOverrides = @{}
foreach ($override in @($configuration.ExpectedOverrides)) {
    $resource = ([string]$override.Resource).ToLowerInvariant()
    $providers = @($override.Packs | ForEach-Object { [string]$_ } | Sort-Object -Unique)
    if ($resource -cnotmatch '^[a-z0-9_]{1,16}\.[a-z0-9_]+$') { Add-ValidationError "Invalid ExpectedOverrides resource '$resource'." }
    if ($providers.Count -lt 2) { Add-ValidationError "Expected override '$resource' must name at least two packs." }
    foreach ($provider in $providers) {
        if (-not $packByName.ContainsKey($provider)) { Add-ValidationError "Expected override '$resource' references unknown pack '$provider'." }
    }
    if ($declaredOverrides.ContainsKey($resource)) { Add-ValidationError "Duplicate ExpectedOverrides entry for '$resource'." }
    else { $declaredOverrides[$resource] = $providers }
}

foreach ($resource in $resourceProviders.Keys) {
    $actualProviders = @($resourceProviders[$resource] | Sort-Object -Unique)
    if ($actualProviders.Count -le 1) { continue }
    if (-not $declaredOverrides.ContainsKey($resource)) {
        Add-ValidationError "Cross-HAK duplicate '$resource' occurs in $($actualProviders -join ', ') but is not declared as an expected override."
        continue
    }
    $declared = @($declaredOverrides[$resource] | Sort-Object -Unique)
    if (($actualProviders -join "`n") -cne ($declared -join "`n")) { Add-ValidationError "Expected override '$resource' pack list does not match its actual providers." }
}
foreach ($resource in $declaredOverrides.Keys) {
    if (-not $resourceProviders.ContainsKey($resource) -or @($resourceProviders[$resource] | Sort-Object -Unique).Count -le 1) {
        Add-ValidationError "Stale ExpectedOverrides entry '$resource' does not describe a current cross-HAK duplicate."
    }
}

try {
    $registry = Get-Content -LiteralPath (Join-Path $repoRoot 'srn_tlk/allocations.json') -Raw | ConvertFrom-Json
    $tlk = Get-Content -LiteralPath (Join-Path $repoRoot 'srn_tlk/srn.tlk.json') -Raw | ConvertFrom-Json
    $allocations = @($registry.allocations)
    $tlkEntries = @($tlk.entries)
    $nextId = [int64]$registry.nextId
    if ([int]$registry.schemaVersion -ne 1) { Add-ValidationError 'The TLK allocation registry must use schemaVersion 1.' }
    if ([int]$tlk.language -ne 0) { Add-ValidationError 'The canonical TLK source must use language 0.' }
    if ($nextId -lt 0 -or $allocations.Count -ne $nextId) { Add-ValidationError 'TLK nextId must equal the number of permanent allocation records.' }
    $keys = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    $ids = [System.Collections.Generic.HashSet[int64]]::new()
    foreach ($entry in $allocations) {
        $id = [int64]$entry.id
        if (-not $keys.Add([string]$entry.key)) { Add-ValidationError "Duplicate TLK allocation key '$($entry.key)'." }
        if (-not $ids.Add($id)) { Add-ValidationError "Duplicate TLK allocation ID '$id'." }
        if ([string]$entry.owner -notin @('shared', 'SR_NWN', 'SRN_NWN')) { Add-ValidationError "TLK allocation '$($entry.key)' has invalid owner '$($entry.owner)'." }
        if ([string]$entry.status -notin @('active', 'retired')) { Add-ValidationError "TLK allocation '$($entry.key)' has invalid status '$($entry.status)'." }
    }
    for ($id = 0; $id -lt $nextId; $id++) {
        if (-not $ids.Contains($id)) { Add-ValidationError "TLK allocation ID '$id' is missing and may not be reused." }
    }
    $tlkIds = [System.Collections.Generic.HashSet[int64]]::new()
    foreach ($entry in $tlkEntries) {
        $id = [int64]$entry.id
        if (-not $tlkIds.Add($id)) { Add-ValidationError "Duplicate canonical TLK entry ID '$id'." }
    }
    if ($tlkIds.Count -ne $ids.Count) { Add-ValidationError 'Canonical TLK entries must correspond one-to-one with allocation records, including retired IDs.' }
    foreach ($id in $ids) { if (-not $tlkIds.Contains($id)) { Add-ValidationError "Canonical TLK entry '$id' is missing." } }
}
catch { Add-ValidationError "TLK allocation validation failed: $($_.Exception.Message)" }

if ($errors.Count -gt 0) {
    foreach ($validationError in $errors) { Write-Error $validationError -ErrorAction Continue }
    throw "Repository validation failed with $($errors.Count) error(s)."
}
Write-Host "Repository structure validated ($($registeredNames.Count) registered HAK pack(s))."
if ($SkipBuild) { return }

& (Join-Path $PSScriptRoot 'Build-Tlk.ps1')
$packsToBuild = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
if ($AllPacks -or [string]::IsNullOrWhiteSpace($ChangedSince)) {
    foreach ($name in $registeredNames) { [void]$packsToBuild.Add($name) }
}
else {
    $changedPaths = @(& git -C $repoRoot diff --name-only "$ChangedSince...HEAD")
    if ($LASTEXITCODE -ne 0) { throw "Unable to determine changes since '$ChangedSince'." }
    $mustBuildAll = $false
    foreach ($changedPath in $changedPaths) {
        $normalized = $changedPath.Replace('\\', '/')
        if ($normalized -match '^hakbuilder\.json$|^tools/(Bootstrap-Tools|Build-Haks|Build-Tlk|Test-Repository|SrnHaks\.Common)\.|^tools/toolchain\.lock\.json$|^\.github/workflows/verify\.yml$') { $mustBuildAll = $true }
        $firstSegment = $normalized.Split('/')[0]
        if ($packByName.ContainsKey($firstSegment)) { [void]$packsToBuild.Add($firstSegment) }
    }
    if ($mustBuildAll) { foreach ($name in $registeredNames) { [void]$packsToBuild.Add($name) } }
}
if ($packsToBuild.Count -gt 0) { & (Join-Path $PSScriptRoot 'Build-Haks.ps1') -Pack @($packsToBuild) -SkipTlk }
else { Write-Host 'No HAK packs require a build for this change.' }
Write-Host 'Repository verification passed.'
