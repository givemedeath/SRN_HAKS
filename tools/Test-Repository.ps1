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
        if ($file.BaseName -cnotmatch '^[a-z0-9_-]{1,16}$') { Add-ValidationError "Resource stem '$name/$($file.BaseName)' must match [a-z0-9_-]{1,16}." }
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
        if ($file.Length -lt 1024 -and (Test-GitLfsPointer -Path $file.FullName)) {
            Add-ValidationError "Git LFS pointer detected at '$relativeFile'; this repository does not use LFS."
        }
        if ($file.Extension -ieq '.set') {
            $setLineNumber = 0
            foreach ($setLine in [System.IO.File]::ReadLines($file.FullName)) {
                $setLineNumber++
                if ($setLine -match '^(Interior|HasHeightTransition|Grass|MainLight1|MainLight2|SourceLight1|SourceLight2|AnimLoop1|AnimLoop2|AnimLoop3)=(-?\d+)$' -and $Matches[2] -notin @('0', '1')) {
                    Add-ValidationError "SET boolean field '$($Matches[1])' must be 0 or 1 at '$relativeFile`:$setLineNumber'; found '$($Matches[2])'."
                }
            }
            $setText = [System.Text.Encoding]::GetEncoding(28591).GetString([System.IO.File]::ReadAllBytes($file.FullName))
            $loneLineFeed = [regex]::Match($setText, '(?<!\r)\n')
            if ($loneLineFeed.Success) {
                $setLineNumber = $setText.Substring(0, $loneLineFeed.Index).Split("`n").Count
                Add-ValidationError "SET resource '$relativeFile`:$setLineNumber' has a lone LF; SET files must use CRLF."
            }
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
    if ($resource -cnotmatch '^[a-z0-9_-]{1,16}\.[a-z0-9_]+$') { Add-ValidationError "Invalid ExpectedOverrides resource '$resource'." }
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
        $entryKeys = @([string]$entry.key)
        if ($entry.PSObject.Properties.Name -contains 'aliases') { $entryKeys += @($entry.aliases) }
        foreach ($entryKey in $entryKeys) {
            if ([string]$entryKey -cnotmatch '^[a-z0-9]+(?:[._-][a-z0-9]+)*$') {
                Add-ValidationError "TLK allocation '$($entry.key)' has invalid key or alias '$entryKey'."
            }
            if (-not $keys.Add([string]$entryKey)) { Add-ValidationError "Duplicate TLK allocation key or alias '$entryKey'." }
        }
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

# Additions catalog: above the imported baseline, the placeables table's rows and each listed tileset's tiles and
# groups are exactly the catalog's, and each listed model, walkmesh and blueprint is a file of the pack named.
$additionsPath = Join-Path $repoRoot 'docs/additions/catalog.json'
try {
    $additions = Get-Content -LiteralPath $additionsPath -Raw | ConvertFrom-Json
    if ($additions.kind -cne 'srn-additions-catalog' -or $additions.schemaVersion -ne 1) { throw 'not an additions catalog (schema 1)' }
    $tableRelative = [string]$additions.baseline.placeables.table
    $gameText = [Text.Encoding]::GetEncoding(1252)  # as envkit writes the table and the set files
    $lastImported = [int]$additions.baseline.placeables.lastImportedRow
    # A model with a glow map has the whole lights-out set of docs/envkit/lights.md, and its entry says so.
    $packFile = { param($pack, $name) Test-Path -LiteralPath (Join-Path $repoRoot (Join-Path $pack $name)) -PathType Leaf }
    $checkLights = {
        param($entry, $material, $what)
        $lights = if ($entry.PSObject.Properties['lights']) { $entry.lights } else { $null }
        if (-not $lights) {
            if (& $packFile $entry.pack "${material}_i.dds") { Add-ValidationError "$what has a glow map ($($entry.pack)/${material}_i.dds) and no lights in the additions catalog." }
            return
        }
        if ([string]$lights.lit -cne $material -or [string]$lights.out -cne "${material}_o" -or [string]$lights.glow -cne "${material}_i") { Add-ValidationError "The lights of $what do not follow its material $material." }
        $needed = @("$($lights.lit).mtr", "$($lights.out).mtr", "$($lights.out).dds", "$($lights.glow).dds")
        if ($lights.PSObject.Properties['halo']) { $needed += "$($lights.halo).mtr", "$($lights.halo).dds", "$($lights.halo).txi" }
        foreach ($name in $needed) { if (-not (& $packFile $entry.pack $name)) { Add-ValidationError "$($entry.pack) has no $name for the lights of $what." } }
        if ($lights.PSObject.Properties['dark']) {
            foreach ($suffix in '.mtr', '.dds', '.txi') {
                $holders = @(Get-ChildItem -LiteralPath $repoRoot -Directory -Filter 'srn_*' | Where-Object { & $packFile $_.Name "$($lights.dark)$suffix" })
                if ($holders.Count -eq 0) { Add-ValidationError "No pack has $($lights.dark)$suffix, the dark halo of $what." }  # in two, it is a cross-HAK duplicate above
            }
        }
    }
    $tableRows = @{}
    foreach ($line in [IO.File]::ReadAllLines((Join-Path $repoRoot $tableRelative), $gameText)) {
        if ($line -notmatch '^\s*(\d+)\s' -or [int]$Matches[1] -le $lastImported) { continue }
        $tokens = @([regex]::Matches($line, '"[^"]*"|\S+') | ForEach-Object { $_.Value })
        if ($tokens.Count -gt 3) { $tableRows[[int]$tokens[0]] = @($tokens[1].Trim('"'), $tokens[3].ToLowerInvariant()) }
    }
    $listedRows = @{}
    foreach ($entry in @($additions.placeables)) {
        if ($listedRows.ContainsKey([int]$entry.row)) { Add-ValidationError "The additions catalog has more than one entry for row $($entry.row)." }
        $listedRows[[int]$entry.row] = $entry
    }
    foreach ($row in @($tableRows.Keys | Sort-Object)) {
        if (-not $listedRows.ContainsKey($row)) { Add-ValidationError "$tableRelative row $row ($($tableRows[$row][1])) is not in docs/additions/catalog.json."; continue }
        $entry = $listedRows[$row]
        if ($tableRows[$row][0] -cne [string]$entry.label -or $tableRows[$row][1] -cne ([string]$entry.model).ToLowerInvariant()) {
            Add-ValidationError "Row $row is $($tableRows[$row][1]) '$($tableRows[$row][0])' in $tableRelative and $($entry.model) '$($entry.label)' in the additions catalog."
        }
        & $checkLights $entry ([string]$entry.model) "placeables row $row"
        $needed = @("$($entry.model).mdl")
        if ($entry.PSObject.Properties['blueprint']) { $needed += "$($entry.blueprint).utp" }
        foreach ($name in $needed) {
            if (-not (Test-Path -LiteralPath (Join-Path $repoRoot (Join-Path $entry.pack $name)) -PathType Leaf)) { Add-ValidationError "$($entry.pack) has no $name for placeables row $row." }
        }
    }
    foreach ($row in @($listedRows.Keys | Sort-Object)) {
        if (-not $tableRows.ContainsKey($row)) { Add-ValidationError "The additions catalog lists row $row ($($listedRows[$row].model)), which $tableRelative does not have." }
    }
    $expectedRow = $lastImported + 1
    foreach ($row in @($tableRows.Keys | Sort-Object)) {
        if ($row -ne $expectedRow) { Add-ValidationError "$tableRelative has a gap in its rows after $lastImported (found $row where $expectedRow was expected)."; break }
        $expectedRow++
    }
    $baselineNames = @($additions.baseline.tilesets.PSObject.Properties | ForEach-Object { $_.Name })
    foreach ($entry in @($additions.tileGroups)) {
        if ($baselineNames -cnotcontains [string]$entry.tileset) { Add-ValidationError "The additions catalog lists a group of $($entry.tileset), which has no baseline." }
    }
    foreach ($tilesetName in $baselineNames) {
        $baseline = $additions.baseline.tilesets.$tilesetName
        $setText = [IO.File]::ReadAllText((Join-Path $repoRoot $baseline.set), $gameText)
        $tileModels = @{}
        foreach ($match in [regex]::Matches($setText, '(?m)^\[TILE(\d+)\]\r?\nModel=([^\r\n]+)')) { $tileModels[[int]$match.Groups[1].Value] = $match.Groups[2].Value }
        $setGroups = @{}
        foreach ($match in [regex]::Matches($setText, '(?ms)^\[GROUP(\d+)\]\r?\n(.*?)(?=^\[|\z)')) {
            $fields = @{}
            foreach ($line in ($match.Groups[2].Value -split '\r?\n')) { $pair = $line -split '=', 2; if ($pair.Count -eq 2) { $fields[$pair[0]] = $pair[1] } }
            $count = [int]$fields['Rows'] * [int]$fields['Columns']
            $setGroups[[int]$match.Groups[1].Value] = @{ name = $fields['Name']; rows = [int]$fields['Rows']; columns = [int]$fields['Columns']
                tiles = @(for ($index = 0; $index -lt $count; $index++) { [int]$fields["Tile$index"] }) }
        }
        $listedGroups = @{}
        foreach ($entry in @($additions.tileGroups | Where-Object { $_.tileset -ceq $tilesetName })) {
            if ($listedGroups.ContainsKey([int]$entry.group)) { Add-ValidationError "The additions catalog has more than one entry for group $($entry.group) of $tilesetName." }
            $listedGroups[[int]$entry.group] = $entry
        }
        $collected = [System.Collections.Generic.HashSet[int]]::new()
        foreach ($number in @($setGroups.Keys | Where-Object { $_ -ge [int]$baseline.importedGroups } | Sort-Object)) {
            if (-not $listedGroups.ContainsKey($number)) { Add-ValidationError "$($baseline.set) group $number ($($setGroups[$number].name)) is not in docs/additions/catalog.json."; continue }
            $entry = $listedGroups[$number]; $group = $setGroups[$number]
            & $checkLights $entry (([string]@($entry.models)[0]) -replace '_t\d\d$', '') "group $number of $tilesetName"
            if ($group.name -cne [string]$entry.name -or $group.rows -ne [int]$entry.rows -or $group.columns -ne [int]$entry.columns -or (($group.tiles -join ',') -cne (@($entry.tiles) -join ','))) {
                Add-ValidationError "Group $number of $tilesetName is '$($group.name)' $($group.rows)x$($group.columns) [$($group.tiles -join ',')] in the set file and '$($entry.name)' $($entry.rows)x$($entry.columns) [$(@($entry.tiles) -join ',')] in the additions catalog."
            }
            for ($index = 0; $index -lt @($entry.tiles).Count; $index++) {
                $tile = [int]@($entry.tiles)[$index]; $model = [string]@($entry.models)[$index]; [void]$collected.Add($tile)
                if (-not $tileModels.ContainsKey($tile) -or $tileModels[$tile].ToLowerInvariant() -cne $model.ToLowerInvariant()) {
                    Add-ValidationError "Tile $tile of $tilesetName is '$($tileModels[$tile])' in the set file and '$model' in the additions catalog."
                }
                foreach ($suffix in '.mdl', '.wok') {
                    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot (Join-Path $entry.pack "$model$suffix")) -PathType Leaf)) { Add-ValidationError "$($entry.pack) has no $model$suffix for tile $tile of $tilesetName." }
                }
            }
        }
        foreach ($number in @($listedGroups.Keys | Sort-Object)) {
            if (-not $setGroups.ContainsKey($number) -or $number -lt [int]$baseline.importedGroups) { Add-ValidationError "The additions catalog lists group $number ($($listedGroups[$number].name)) of $tilesetName, which $($baseline.set) does not have above its imported groups." }
        }
        foreach ($tile in @($tileModels.Keys | Where-Object { $_ -ge [int]$baseline.importedTiles } | Sort-Object)) {
            if (-not $collected.Contains($tile)) { Add-ValidationError "$($baseline.set) tile $tile ($($tileModels[$tile])) belongs to no group in docs/additions/catalog.json." }
        }
    }
}
catch { Add-ValidationError "Additions catalog validation failed: $($_.Exception.Message)" }

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
    $changedPaths = @(& git -C $repoRoot diff --name-only --no-renames "$ChangedSince...HEAD")
    if ($LASTEXITCODE -ne 0) { throw "Unable to determine changes since '$ChangedSince'." }
    $mustBuildAll = $false
    $packBuildPatterns = @((Get-Content -LiteralPath (Join-Path $PSScriptRoot 'ci-scope.json') -Raw | ConvertFrom-Json).packBuild)
    foreach ($changedPath in $changedPaths) {
        $normalized = $changedPath.Replace('\\', '/')
        if ($packBuildPatterns | Where-Object { $normalized -match $_ }) { $mustBuildAll = $true }
        $firstSegment = $normalized.Split('/')[0]
        if ($packByName.ContainsKey($firstSegment)) { [void]$packsToBuild.Add($firstSegment) }
    }
    if ($mustBuildAll) { foreach ($name in $registeredNames) { [void]$packsToBuild.Add($name) } }
}
if ($packsToBuild.Count -gt 0) { & (Join-Path $PSScriptRoot 'Build-Haks.ps1') -Pack @($packsToBuild) -SkipTlk }
else { Write-Host 'No HAK packs require a build for this change.' }
Write-Host 'Repository verification passed.'
