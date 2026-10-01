[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$InputHak,
    [Parameter(Mandatory)][string]$OutputRelativePath,
    [string]$ProfilePath = (Join-Path $PSScriptRoot 'import-profiles/mdrnee_item.json'),
    [string]$NwnRoot,
    [string]$NwnUserDirectory,
    [switch]$SkipImport
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'SrnHaks.Common.psm1') -Force

$repoRoot = Get-SrnRepositoryRoot
$quarantineRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot '.quarantine'))
if ([string]::IsNullOrWhiteSpace($OutputRelativePath) -or [IO.Path]::IsPathRooted($OutputRelativePath)) {
    throw 'OutputRelativePath must be a non-empty relative path beneath .quarantine.'
}
$workspace = [IO.Path]::GetFullPath((Join-Path $quarantineRoot $OutputRelativePath))
$prefix = $quarantineRoot.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) +
    [IO.Path]::DirectorySeparatorChar
$comparison = if ($IsWindows) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
if (-not $workspace.StartsWith($prefix, $comparison)) {
    throw "OutputRelativePath escapes .quarantine: $OutputRelativePath"
}

if (-not $SkipImport) {
    $arguments = @{
        Mode = 'Analyze'
        InputHak = $InputHak
        OutputRelativePath = $OutputRelativePath
        ProfilePath = $ProfilePath
    }
    if ($NwnRoot) { $arguments.NwnRoot = $NwnRoot }
    if ($NwnUserDirectory) { $arguments.NwnUserDirectory = $NwnUserDirectory }
    & (Join-Path $PSScriptRoot 'Import-Hak.ps1') @arguments
}

$rawRoot = Join-Path $workspace 'raw'
$analysisRoot = Join-Path $workspace 'analysis'
$manifestPath = Join-Path $analysisRoot 'manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Missing import analysis manifest: $manifestPath"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json -Depth 64
$sourceHash = (Get-FileHash -LiteralPath (Resolve-Path -LiteralPath $InputHak).Path -Algorithm SHA256).Hash.ToUpperInvariant()
if ([string]$manifest.sourceSha256 -cne $sourceHash) {
    throw 'Analysis manifest does not match InputHak.'
}

function Write-AnalysisJson {
    param([Parameter(Mandatory)][string]$Name, [Parameter(Mandatory)]$Value)
    $path = Join-Path $analysisRoot $Name
    [IO.File]::WriteAllText($path, ($Value | ConvertTo-Json -Depth 16) + "`n", [Text.UTF8Encoding]::new($false))
}

function Get-2daTokens {
    param([Parameter(Mandatory)][string]$Line)
    @([regex]::Matches($Line, '"[^"]*"|\S+') | ForEach-Object { $_.Value.Trim('"') })
}

function Read-2daTable {
    param([Parameter(Mandatory)][string]$Path)
    $allLines = @(Get-Content -LiteralPath $Path -Encoding Default)
    $hasHeader = @($allLines | Select-Object -First 4 | Where-Object { $_ -match '^\s*2DA\s+V' }).Count -gt 0
    $lines = @($allLines | Where-Object { $_.Trim() -and $_ -notmatch '^\s*//' })
    $headerIndex = 0
    while ($headerIndex -lt $lines.Count -and
        ($lines[$headerIndex] -match '^\s*2DA\s' -or $lines[$headerIndex] -match '^\s*DEFAULT:')) {
        $headerIndex++
    }
    if (-not $hasHeader -or $headerIndex -ge $lines.Count) {
        return [pscustomobject]@{ validHeader = $false; headers = @(); rows = @{}; duplicateRows = @() }
    }
    $headers = @(Get-2daTokens $lines[$headerIndex])
    $rows = @{}
    $rowCounts = @{}
    for ($index = $headerIndex + 1; $index -lt $lines.Count; $index++) {
        $tokens = @(Get-2daTokens $lines[$index])
        if (-not $tokens.Count -or $tokens[0] -notmatch '^\d+$') { continue }
        $rowNumber = [int]$tokens[0]
        if (-not $rowCounts.ContainsKey($rowNumber)) { $rowCounts[$rowNumber] = 0 }
        $rowCounts[$rowNumber]++
        $values = @{}
        for ($column = 0; $column -lt $headers.Count; $column++) {
            $values[$headers[$column]] = if ($column + 1 -lt $tokens.Count) { $tokens[$column + 1] } else { '****' }
        }
        if (-not $rows.ContainsKey($rowNumber)) {
            $rows[$rowNumber] = [pscustomobject]@{ row = $rowNumber; values = $values }
        }
    }
    [pscustomobject]@{
        validHeader = $true
        headers = $headers
        rows = $rows
        duplicateRows = @($rowCounts.GetEnumerator() | Where-Object Value -gt 1 |
            Sort-Object Name | ForEach-Object { [pscustomobject]@{ row = [int]$_.Name; occurrences = $_.Value } })
    }
}

function Test-Active2daRow {
    param($Entry, [string[]]$Headers)
    $labelKey = @($Headers | Where-Object { $_ -ieq 'label' } | Select-Object -First 1)
    if ($labelKey.Count) {
        $label = [string]$Entry.values[$labelKey[0]]
        if ($label -match '^(\*{4}|USER|bio_reserved|CEP_RESERVED|OS_RESERVED|XP2SpecialRequest|XP2SpecReq)$') {
            return $false
        }
    }
    return @($Entry.values.Values | Where-Object { $_ -ne '****' }).Count -gt 0
}

$erf = Get-SrnTool -Name erf
$gff = Get-SrnTool -Name gff
$cat = Get-SrnTool -Name resman_cat
$grep = Get-SrnTool -Name resman_grep

# Decode and flatten the item palette. These are category definitions, not UTI blueprints.
$palettePath = Join-Path $rawRoot 'itempal.itp'
if (Test-Path -LiteralPath $palettePath -PathType Leaf) {
    $paletteJsonPath = Join-Path $analysisRoot 'itempal.json'
    & $gff -i $palettePath -l gff -o $paletteJsonPath -k json --pretty
    if ($LASTEXITCODE -ne 0) { throw 'Unable to decode itempal.itp.' }
    $palette = Get-Content -LiteralPath $paletteJsonPath -Raw | ConvertFrom-Json -Depth 64

    function Visit-PaletteNode {
        param($Nodes, [string[]]$Path, [string]$TopLevel)
        foreach ($node in @($Nodes)) {
            $name = if ($node.PSObject.Properties.Name -contains 'DELETE_ME') {
                [string]$node.DELETE_ME.value
            }
            else { '(unnamed)' }
            $nodePath = @($Path) + $name
            $top = if ($TopLevel) { $TopLevel } else { $name }
            if ($node.PSObject.Properties.Name -contains 'ID') {
                [pscustomobject][ordered]@{
                    id = [int]$node.ID.value
                    name = $name
                    path = $nodePath -join ' > '
                    topLevel = $top
                    strRef = if ($node.PSObject.Properties.Name -contains 'STRREF') { [long]$node.STRREF.value } else { $null }
                }
            }
            if ($node.PSObject.Properties.Name -contains 'LIST') {
                Visit-PaletteNode -Nodes $node.LIST.value -Path $nodePath -TopLevel $top
            }
        }
    }

    $leaves = @(Visit-PaletteNode -Nodes $palette.MAIN.value -Path @() -TopLevel '')
    $categoryDocument = [ordered]@{
        schemaVersion = 1
        source = 'itempal.itp'
        sourceHakSha256 = $sourceHash
        nextUseableId = [int]$palette.NEXT_USEABLE_ID.value
        blueprintResourceCount = @($manifest.resources | Where-Object type -eq 'uti').Count
        note = 'These are palette category definitions from the HAK. Join an authoritative companion UTI ERF with Analyze-ItemBlueprintErf.ps1 to assign individual blueprints.'
        topLevelCategories = @($leaves | Group-Object topLevel | Sort-Object Name | ForEach-Object {
            [pscustomobject][ordered]@{ name = $_.Name; leafCount = $_.Count; ids = @($_.Group.id | Sort-Object) }
        })
        leafCategories = @($leaves | Sort-Object id)
    }
    Write-AnalysisJson -Name 'item-category-map.json' -Value $categoryDocument
}

# Compare legacy global tables with the pinned EE view and flag malformed inputs.
$baselineRoot = Join-Path $analysisRoot 'ee-baseline'
New-Item -ItemType Directory -Force -Path $baselineRoot | Out-Null
$tableSummaries = [Collections.Generic.List[object]]::new()
foreach ($sourceFile in @(Get-ChildItem -LiteralPath $rawRoot -Filter '*.2da' | Sort-Object Name)) {
    $sourceTable = Read-2daTable $sourceFile.FullName
    $baselinePath = Join-Path $baselineRoot $sourceFile.Name
    $baselineAvailable = $false
    if ($NwnRoot -and $NwnUserDirectory -and $sourceTable.validHeader) {
        $baselineLines = @(& $cat --root $NwnRoot --userdirectory $NwnUserDirectory --no-ovr $sourceFile.Name 2>$null)
        if ($LASTEXITCODE -eq 0 -and $baselineLines.Count) {
            [IO.File]::WriteAllLines($baselinePath, $baselineLines, [Text.Encoding]::GetEncoding(1252))
            $baselineAvailable = $true
        }
    }
    $baselineTable = if ($baselineAvailable) { Read-2daTable $baselinePath } else { $null }
    $activeRows = if ($sourceTable.validHeader) {
        @($sourceTable.rows.Values | Where-Object { Test-Active2daRow $_ $sourceTable.headers })
    }
    else { @() }
    $commonColumns = if ($baselineAvailable) {
        @($sourceTable.headers | Where-Object { $_ -in $baselineTable.headers })
    }
    else { @() }
    $changedRows = if ($baselineAvailable) {
        @(foreach ($entry in $activeRows) {
            if (-not $baselineTable.rows.ContainsKey($entry.row)) { continue }
            $baselineEntry = $baselineTable.rows[$entry.row]
            $differences = @($commonColumns | Where-Object {
                [string]$entry.values[$_] -cne [string]$baselineEntry.values[$_]
            })
            if ($differences.Count) { $entry.row }
        })
    }
    else { @() }
    $newRows = if ($baselineAvailable) {
        @($activeRows | Where-Object { -not $baselineTable.rows.ContainsKey($_.row) })
    }
    else { @($activeRows) }
    $newRowNumbers = @($newRows | ForEach-Object { $_.row } | Sort-Object)
    $sourceRowCount = [int]$sourceTable.rows.Count
    $baselineRowCount = if ($baselineAvailable) { [int]$baselineTable.rows.Count } else { 0 }
    $tableSummaries.Add([pscustomobject][ordered]@{
        resource = $sourceFile.Name
        validHeader = $sourceTable.validHeader
        duplicateRows = @($sourceTable.duplicateRows)
        sourceColumns = @($sourceTable.headers).Length
        sourceRows = $sourceRowCount
        sourceActiveRows = @($activeRows).Length
        baselineAvailable = $baselineAvailable
        baselineColumns = if ($baselineAvailable) { @($baselineTable.headers).Length } else { 0 }
        baselineRows = $baselineRowCount
        commonColumns = @($commonColumns).Length
        changedOverlappingActiveRows = @($changedRows).Length
        newActiveRows = @($newRows).Length
        newActiveRowNumbers = $newRowNumbers
    })
}
Write-AnalysisJson -Name '2da-comparison.json' -Value ([ordered]@{
    schemaVersion = 1
    comparison = 'Legacy tables compared on shared columns with the requested NWN:EE baseline. Counts are screening evidence, not approved merge plans.'
    tables = @($tableSummaries)
})

# Resolve every ASCII model texture and supermodel reference against the archive and EE view.
$allFiles = @(Get-ChildItem -LiteralPath $rawRoot -File)
$archiveNames = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($file in $allFiles) { [void]$archiveNames.Add($file.Name) }
$baseNames = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
if ($NwnRoot -and $NwnUserDirectory) {
    & $grep --root $NwnRoot --userdirectory $NwnUserDirectory --no-ovr --all --silent | ForEach-Object {
        if ($_ -match '^\s*(\S+)') { [void]$baseNames.Add($matches[1]) }
    }
}
$textureReferences = @{}
$supermodelReferences = @{}
$classifications = @{}
foreach ($model in @($allFiles | Where-Object Extension -ieq '.mdl')) {
    $text = Get-Content -LiteralPath $model.FullName -Raw -Encoding Default
    $match = [regex]::Match($text, '(?im)^\s*classification\s+(\S+)')
    $classification = if ($match.Success) { $match.Groups[1].Value.ToLowerInvariant() } else { 'unknown' }
    if (-not $classifications.ContainsKey($classification)) { $classifications[$classification] = 0 }
    $classifications[$classification]++
    foreach ($reference in [regex]::Matches($text, '(?im)^\s*(?:bitmap|texture\d*)\s+([^\s]+)')) {
        $stem = $reference.Groups[1].Value.ToLowerInvariant()
        if ($stem -in @('null', 'none', 'default', '****')) { continue }
        if (-not $textureReferences.ContainsKey($stem)) {
            $textureReferences[$stem] = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        }
        [void]$textureReferences[$stem].Add($model.Name)
    }
    foreach ($reference in [regex]::Matches($text, '(?im)^\s*setsupermodel\s+\S+\s+([^\s]+)')) {
        $stem = $reference.Groups[1].Value.ToLowerInvariant()
        if ($stem -in @('null', 'none', 'default', '****')) { continue }
        if (-not $supermodelReferences.ContainsKey($stem)) {
            $supermodelReferences[$stem] = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        }
        [void]$supermodelReferences[$stem].Add($model.Name)
    }
}
$textureClosure = @(foreach ($stem in $textureReferences.Keys) {
    $archiveResources = @(foreach ($extension in @('.dds', '.tga', '.txi')) {
        if ($archiveNames.Contains("$stem$extension")) { "$stem$extension" }
    })
    $baseResources = @(foreach ($extension in @('.dds', '.tga', '.txi')) {
        if ($baseNames.Contains("$stem$extension")) { "$stem$extension" }
    })
    [pscustomobject][ordered]@{
        stem = $stem
        referencedByCount = $textureReferences[$stem].Count
        referencingModels = @($textureReferences[$stem] | Sort-Object)
        archiveResources = $archiveResources
        baseResources = $baseResources
        status = if ($archiveResources.Count) { 'archive' } elseif ($baseResources.Count) { 'ee-base' } else { 'unresolved' }
    }
})
$supermodelClosure = @(foreach ($stem in $supermodelReferences.Keys) {
    [pscustomobject][ordered]@{
        model = $stem
        referencedByCount = $supermodelReferences[$stem].Count
        referencingModels = @($supermodelReferences[$stem] | Sort-Object)
        status = if ($archiveNames.Contains("$stem.mdl")) { 'archive' } elseif ($baseNames.Contains("$stem.mdl")) { 'ee-base' } else { 'unresolved' }
    }
})
$modelFamilies = @($allFiles | Where-Object Extension -ieq '.mdl' | Group-Object {
    if ($_.BaseName -match '^([^_]+)') { $matches[1].ToLowerInvariant() } else { $_.BaseName.ToLowerInvariant() }
} | Sort-Object Count -Descending | ForEach-Object { [pscustomobject]@{ prefix = $_.Name; modelCount = $_.Count } })
Write-AnalysisJson -Name 'model-dependencies.json' -Value ([ordered]@{
    schemaVersion = 1
    modelCount = @($allFiles | Where-Object Extension -ieq '.mdl').Count
    classifications = @($classifications.GetEnumerator() | Sort-Object Name |
        ForEach-Object { [pscustomobject]@{ classification = $_.Name; count = $_.Value } })
    modelFamilies = $modelFamilies
    textureReferenceStems = $textureClosure.Count
    textureClosure = [ordered]@{
        archive = @($textureClosure | Where-Object status -eq 'archive').Count
        eeBase = @($textureClosure | Where-Object status -eq 'ee-base').Count
        unresolved = @($textureClosure | Where-Object status -eq 'unresolved').Count
    }
    unresolvedTextureReferences = @($textureClosure | Where-Object status -eq 'unresolved' | Sort-Object stem)
    supermodelReferences = $supermodelClosure
})

# Associate WAV resources with exact tokens in 2DAs and model animation data.
$waveLinks = @(foreach ($wave in @($allFiles | Where-Object Extension -ieq '.wav' | Sort-Object Name)) {
    $stem = $wave.BaseName
    $pattern = '(?i)(?<![A-Za-z0-9_])' + [regex]::Escape($stem) + '(?![A-Za-z0-9_])'
    $tables = @(Get-ChildItem -LiteralPath $rawRoot -Filter '*.2da' | Where-Object {
        Select-String -LiteralPath $_.FullName -Pattern $pattern -Quiet
    } | ForEach-Object Name | Sort-Object -Unique)
    $models = @(Get-ChildItem -LiteralPath $rawRoot -Filter '*.mdl' | Where-Object {
        Select-String -LiteralPath $_.FullName -Pattern $pattern -Quiet
    } | ForEach-Object Name | Sort-Object -Unique)
    [pscustomobject][ordered]@{ name = $wave.Name; size = $wave.Length; tables = $tables; models = $models }
})
Write-AnalysisJson -Name 'sound-linkages.json' -Value ([ordered]@{
    schemaVersion = 1
    waveCount = $waveLinks.Count
    linkedBy2daOrModelCount = @($waveLinks | Where-Object { $_.tables.Count -or $_.models.Count }).Count
    unlinkedCount = @($waveLinks | Where-Object { -not $_.tables.Count -and -not $_.models.Count }).Count
    resources = $waveLinks
})

# Detect exact duplicates and true resource-identity conflicts with packs already in this repository.
$sourceByName = @{}
foreach ($resource in $manifest.resources) { $sourceByName[[string]$resource.name] = $resource }
$crossPackPairs = @(foreach ($pack in @(Get-ChildItem -LiteralPath $repoRoot -Directory -Filter 'srn_*')) {
    foreach ($existing in @(Get-ChildItem -LiteralPath $pack.FullName -File)) {
        $name = $existing.Name.ToLowerInvariant()
        if (-not $sourceByName.ContainsKey($name)) { continue }
        $sourceResource = $sourceByName[$name]
        [pscustomobject][ordered]@{
            name = $name
            pack = $pack.Name
            sameBytes = ((Get-FileHash -LiteralPath $existing.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -ceq
                [string]$sourceResource.sha256)
        }
    }
})
Write-AnalysisJson -Name 'cross-hak-collisions.json' -Value ([ordered]@{
    schemaVersion = 1
    identityCount = @($crossPackPairs | ForEach-Object name | Sort-Object -Unique).Count
    pairCount = $crossPackPairs.Count
    identicalPairs = @($crossPackPairs | Where-Object sameBytes).Count
    differingPairs = @($crossPackPairs | Where-Object { -not $_.sameBytes }).Count
    pairs = @($crossPackPairs | Sort-Object pack, name)
})

Write-Host "Item HAK supplements complete: $analysisRoot"
