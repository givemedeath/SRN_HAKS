[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$InputErf,
    [Parameter(Mandatory)][string]$OutputRelativePath,
    [string]$ItemHakOutputRelativePath = 'mdrnee_item',
    [string]$CategoryMapPath = (Join-Path $PSScriptRoot '../docs/imports/mdrnee_item-category-map.json'),
    [string]$MatchTierPath,
    [string]$ExpectedSha256,
    [int]$ExpectedResourceCount = -1
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'SrnHaks.Common.psm1') -Force

$repoRoot = Get-SrnRepositoryRoot
$quarantineRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot '.quarantine'))

function Resolve-QuarantinePath {
    param([Parameter(Mandatory)][string]$RelativePath)
    if ([string]::IsNullOrWhiteSpace($RelativePath) -or [IO.Path]::IsPathRooted($RelativePath)) {
        throw 'Quarantine paths must be non-empty relative paths.'
    }
    $resolved = [IO.Path]::GetFullPath((Join-Path $quarantineRoot $RelativePath))
    $prefix = $quarantineRoot.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) +
        [IO.Path]::DirectorySeparatorChar
    $comparison = if ($IsWindows) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
    if (-not $resolved.StartsWith($prefix, $comparison)) {
        throw "Relative path escapes .quarantine: $RelativePath"
    }
    $current = $resolved
    while ($current -and $current.Length -ge $quarantineRoot.Length) {
        if ((Test-Path -LiteralPath $current) -and
            ((Get-Item -LiteralPath $current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Reparse point not allowed: $current"
        }
        $current = Split-Path $current -Parent
    }
    $resolved
}

function Get-GffValue {
    param($Object, [Parameter(Mandatory)][string]$Name, $Default = $null)
    if ($null -eq $Object -or $Object.PSObject.Properties.Name -notcontains $Name) { return $Default }
    $field = $Object.$Name
    if ($null -eq $field -or $field.PSObject.Properties.Name -notcontains 'value') { return $Default }
    $field.value
}

function Get-LocalizedText {
    param($Field, [string]$Fallback)
    if ($null -eq $Field -or $Field.PSObject.Properties.Name -notcontains 'value') { return $Fallback }
    $value = $Field.value
    if ($value -is [string] -and -not [string]::IsNullOrWhiteSpace($value)) { return $value }
    if ($null -ne $value -and $value.PSObject) {
        foreach ($property in @($value.PSObject.Properties | Sort-Object {
            if ($_.Name -eq '0') { 0 } else { 1 }
        })) {
            if ($property.Value -is [string] -and -not [string]::IsNullOrWhiteSpace($property.Value)) {
                return [string]$property.Value
            }
        }
    }
    $Fallback
}

function Get-2daTokens {
    param([Parameter(Mandatory)][string]$Line)
    @([regex]::Matches($Line, '"[^"]*"|\S+') | ForEach-Object { $_.Value.Trim('"') })
}

function Read-2daRows {
    param([Parameter(Mandatory)][string]$Path)
    $lines = @(Get-Content -LiteralPath $Path -Encoding Default | Where-Object {
        $_.Trim() -and $_ -notmatch '^\s*//'
    })
    $headerIndex = 0
    while ($headerIndex -lt $lines.Count -and
        ($lines[$headerIndex] -match '^\s*2DA\s' -or $lines[$headerIndex] -match '^\s*DEFAULT:')) {
        $headerIndex++
    }
    if ($headerIndex -ge $lines.Count) { throw "Unable to find 2DA header: $Path" }
    $headers = @(Get-2daTokens $lines[$headerIndex])
    $rows = @{}
    for ($index = $headerIndex + 1; $index -lt $lines.Count; $index++) {
        $tokens = @(Get-2daTokens $lines[$index])
        if (-not $tokens.Count -or $tokens[0] -notmatch '^\d+$') { continue }
        $values = @{}
        for ($column = 0; $column -lt $headers.Count; $column++) {
            $values[$headers[$column]] = if ($column + 1 -lt $tokens.Count) { $tokens[$column + 1] } else { '****' }
        }
        $rows[[int]$tokens[0]] = $values
    }
    $rows
}

function Write-JsonFile {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)]$Value, [int]$Depth = 32)
    [IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth $Depth) + "`n", [Text.UTF8Encoding]::new($false))
}

$source = (Resolve-Path -LiteralPath $InputErf).Path
$sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToUpperInvariant()
if ($ExpectedSha256) {
    $expectedHash = $ExpectedSha256.Trim().ToUpperInvariant()
    if ($expectedHash -notmatch '^[0-9A-F]{64}$') { throw 'ExpectedSha256 must contain exactly 64 hexadecimal characters.' }
    if ($sourceHash -cne $expectedHash) { throw "ERF SHA-256 mismatch. Expected $expectedHash; found $sourceHash." }
}
$workspace = Resolve-QuarantinePath $OutputRelativePath
$itemWorkspace = Resolve-QuarantinePath $ItemHakOutputRelativePath
$rawRoot = Join-Path $workspace 'raw'
$analysisRoot = Join-Path $workspace 'analysis'
$decodedRoot = Join-Path $analysisRoot 'uti-json'

$separator = [IO.Path]::DirectorySeparatorChar
$comparison = if ($IsWindows) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
foreach ($protectedPath in @((Join-Path $itemWorkspace 'raw'), (Join-Path $itemWorkspace 'analysis'))) {
    $workspaceInsideProtected = $workspace.Equals($protectedPath, $comparison) -or
        $workspace.StartsWith($protectedPath.TrimEnd($separator) + $separator, $comparison)
    $protectedInsideWorkspace = $protectedPath.StartsWith($workspace.TrimEnd($separator) + $separator, $comparison)
    if ($workspaceInsideProtected -or $protectedInsideWorkspace) {
        throw "OutputRelativePath overlaps the item HAK's protected raw/analysis data: $protectedPath"
    }
}

# Validate both deletion targets and the item inputs before touching either output directory.
foreach ($path in @($rawRoot, $analysisRoot, (Join-Path $itemWorkspace 'raw'), (Join-Path $itemWorkspace 'analysis'))) {
    [void](Resolve-QuarantinePath ([IO.Path]::GetRelativePath($quarantineRoot, $path)))
}
foreach ($path in @($rawRoot, $analysisRoot)) {
    if ($source.StartsWith($path.TrimEnd($separator) + $separator, $comparison)) {
        throw 'InputErf is inside an output directory that would be cleared.'
    }
}
$categoryMap = Get-Content -LiteralPath (Resolve-Path -LiteralPath $CategoryMapPath).Path -Raw | ConvertFrom-Json -Depth 64
$itemManifestPath = Join-Path $itemWorkspace 'analysis/manifest.json'
if (-not (Test-Path -LiteralPath $itemManifestPath -PathType Leaf)) {
    throw "The item HAK analysis must exist first; missing $itemManifestPath"
}
$itemManifest = Get-Content -LiteralPath $itemManifestPath -Raw | ConvertFrom-Json -Depth 64
if ([string]::IsNullOrWhiteSpace([string]$categoryMap.sourceHakSha256) -or
    [string]$categoryMap.sourceHakSha256 -ine [string]$itemManifest.sourceSha256) {
    throw 'Category map source HAK SHA-256 does not match the item HAK analysis.'
}
$baseItemsPath = Join-Path $itemWorkspace 'raw/baseitems.2da'
if (-not (Test-Path -LiteralPath $baseItemsPath -PathType Leaf)) {
    throw "The item HAK analysis must exist first; missing $baseItemsPath"
}
$baseItemRecords = @($itemManifest.resources | Where-Object name -ieq 'baseitems.2da')
if ($baseItemRecords.Count -ne 1 -or
    (Get-FileHash -LiteralPath $baseItemsPath -Algorithm SHA256).Hash -ine [string]$baseItemRecords[0].sha256) {
    throw 'baseitems.2da does not match the item HAK analysis manifest.'
}
$baseItems = Read-2daRows $baseItemsPath
$categories = @{}
foreach ($category in $categoryMap.leafCategories) { $categories[[int]$category.id] = $category }

$publishedRawRoot = $rawRoot
$publishedAnalysisRoot = $analysisRoot
$parent = Split-Path $workspace -Parent
New-Item -ItemType Directory -Path $parent -Force | Out-Null
$buildRoot = Resolve-QuarantinePath ([IO.Path]::GetRelativePath($quarantineRoot, (Join-Path $parent ('.blueprint-build-' + [Guid]::NewGuid().ToString('N')))))
$rawRoot = Join-Path $buildRoot 'raw'
$analysisRoot = Join-Path $buildRoot 'analysis'
$decodedRoot = Join-Path $analysisRoot 'uti-json'
try {
New-Item -ItemType Directory -Path $rawRoot, $analysisRoot -Force | Out-Null
New-Item -ItemType Directory -Force -Path $decodedRoot | Out-Null

$erf = Get-SrnTool -Name erf
$gff = Get-SrnTool -Name gff
Push-Location $rawRoot
try {
    & $erf -x -f $source
    if ($LASTEXITCODE -ne 0) { throw "Unable to extract ERF: $source" }
}
finally { Pop-Location }

$listedResources = @(& $erf -f $source -t)
if ($LASTEXITCODE -ne 0) { throw "Unable to inventory ERF: $source" }
$resources = @(Get-ChildItem -LiteralPath $rawRoot -File | Sort-Object Name | ForEach-Object {
    [pscustomobject][ordered]@{
        name = $_.Name.ToLowerInvariant()
        type = $_.Extension.TrimStart('.').ToLowerInvariant()
        size = $_.Length
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
})
if ($resources.Count -ne $listedResources.Count) {
    throw "Extracted resource count $($resources.Count) does not match ERF inventory count $($listedResources.Count)."
}
if ($ExpectedResourceCount -ge 0 -and $resources.Count -ne $ExpectedResourceCount) {
    throw "ERF resource count mismatch. Expected $ExpectedResourceCount; found $($resources.Count)."
}
$manifest = [ordered]@{
    schemaVersion = 1
    sourceFile = [IO.Path]::GetFileName($source)
    sourcePath = $source
    sourceSize = (Get-Item -LiteralPath $source).Length
    sourceSha256 = $sourceHash
    resourceCount = $resources.Count
    typeCounts = @($resources | Group-Object type | Sort-Object Name | ForEach-Object {
        [pscustomobject][ordered]@{ type = $_.Name; count = $_.Count }
    })
    resources = $resources
}
Write-JsonFile -Path (Join-Path $analysisRoot 'manifest.json') -Value $manifest

$blueprints = [Collections.Generic.List[object]]::new()
foreach ($uti in @(Get-ChildItem -LiteralPath $rawRoot -Filter '*.uti' | Sort-Object Name)) {
    $decodedPath = Join-Path $decodedRoot ($uti.BaseName + '.json')
    & $gff -i $uti.FullName -l gff -o $decodedPath -k json
    if ($LASTEXITCODE -ne 0) { throw "Unable to decode $($uti.Name)" }
    $record = Get-Content -LiteralPath $decodedPath -Raw | ConvertFrom-Json -Depth 64
    $paletteId = [int](Get-GffValue $record 'PaletteID' -1)
    $baseItemId = [int](Get-GffValue $record 'BaseItem' -1)
    $category = if ($categories.ContainsKey($paletteId)) { $categories[$paletteId] } else { $null }
    $baseItem = if ($baseItems.ContainsKey($baseItemId)) { $baseItems[$baseItemId] } else { $null }
    $properties = @()
    $propertyList = Get-GffValue $record 'PropertiesList' @()
    foreach ($property in @($propertyList)) {
        $properties += [pscustomobject][ordered]@{
            propertyName = Get-GffValue $property 'PropertyName'
            subtype = Get-GffValue $property 'Subtype'
            costTable = Get-GffValue $property 'CostTable'
            costValue = Get-GffValue $property 'CostValue'
            param1 = Get-GffValue $property 'Param1'
            param1Value = Get-GffValue $property 'Param1Value'
            chanceAppear = Get-GffValue $property 'ChanceAppear'
        }
    }
    $resref = [string](Get-GffValue $record 'TemplateResRef' $uti.BaseName)
    $localizedName = if ($record.PSObject.Properties.Name -contains 'LocalizedName') { $record.LocalizedName } else { $null }
    $blueprints.Add([pscustomobject][ordered]@{
        resource = $uti.Name.ToLowerInvariant()
        resref = $resref
        name = Get-LocalizedText $localizedName $resref
        tag = [string](Get-GffValue $record 'Tag' '')
        paletteId = $paletteId
        category = if ($category) { $category.name } else { '(unmapped)' }
        categoryPath = if ($category) { $category.path } else { "Unmapped palette ID $paletteId" }
        topLevelCategory = if ($category) { $category.topLevel } else { '(unmapped)' }
        baseItem = $baseItemId
        baseItemPresentInItemHak = $null -ne $baseItem
        baseItemLabel = if ($baseItem) { [string]$baseItem.label } else { '(missing)' }
        itemClass = if ($baseItem) { [string]$baseItem.ItemClass } else { '(missing)' }
        modelType = if ($baseItem) { [string]$baseItem.ModelType } else { '(missing)' }
        modelPart1 = Get-GffValue $record 'ModelPart1'
        modelPart2 = Get-GffValue $record 'ModelPart2'
        modelPart3 = Get-GffValue $record 'ModelPart3'
        identified = Get-GffValue $record 'Identified'
        plot = Get-GffValue $record 'Plot'
        cost = Get-GffValue $record 'Cost'
        addCost = Get-GffValue $record 'AddCost'
        charges = Get-GffValue $record 'Charges'
        stackSize = Get-GffValue $record 'StackSize'
        propertyCount = $properties.Count
        properties = $properties
    })
}

$categoryGroups = @($blueprints | Group-Object categoryPath | Sort-Object Name | ForEach-Object {
    $first = $_.Group[0]
    [pscustomobject][ordered]@{
        paletteId = $first.paletteId
        path = $_.Name
        topLevel = $first.topLevelCategory
        count = $_.Count
        baseItems = @($_.Group | Group-Object baseItem | Sort-Object { [int]$_.Name } | ForEach-Object {
            [pscustomobject][ordered]@{
                row = [int]$_.Name
                label = $_.Group[0].baseItemLabel
                itemClass = $_.Group[0].itemClass
                count = $_.Count
            }
        })
        blueprints = @($_.Group | Sort-Object name, resref)
    }
})
$topLevelGroups = @($blueprints | Group-Object topLevelCategory | Sort-Object Name | ForEach-Object {
    [pscustomobject][ordered]@{
        name = $_.Name
        blueprintCount = $_.Count
        usedLeafCount = @($_.Group.categoryPath | Sort-Object -Unique).Count
    }
})
$baseItemGroups = @($blueprints | Group-Object baseItem | Sort-Object { [int]$_.Name } | ForEach-Object {
    [pscustomobject][ordered]@{
        row = [int]$_.Name
        label = $_.Group[0].baseItemLabel
        itemClass = $_.Group[0].itemClass
        blueprintCount = $_.Count
        categories = @($_.Group.categoryPath | Sort-Object -Unique)
    }
})
$propertyInstances = @($blueprints | ForEach-Object { @($_.properties) })
$propertyNameUsage = @($propertyInstances | Group-Object propertyName | Sort-Object -Property @{ Expression = 'Count'; Descending = $true }, Name | ForEach-Object {
    [pscustomobject][ordered]@{ row = [int]$_.Name; count = $_.Count }
})
$costTableUsage = @($propertyInstances | Where-Object { $null -ne $_.costTable } |
    Group-Object costTable | Sort-Object -Property @{ Expression = 'Count'; Descending = $true }, Name | ForEach-Object {
        [pscustomobject][ordered]@{ row = [int]$_.Name; count = $_.Count }
    })
$duplicateTags = @($blueprints | Group-Object tag | Where-Object Count -gt 1 | Sort-Object -Property @{ Expression = 'Count'; Descending = $true }, Name |
    ForEach-Object {
        [pscustomobject][ordered]@{
            tag = $_.Name
            count = $_.Count
            resrefs = @($_.Group.resref | Sort-Object)
        }
    })

$analysis = [ordered]@{
    schemaVersion = 1
    sourceErf = [ordered]@{
        file = [IO.Path]::GetFileName($source)
        size = (Get-Item -LiteralPath $source).Length
        sha256 = $sourceHash
        resourceCount = $resources.Count
    }
    itemHak = [ordered]@{
        categorySource = $categoryMap.source
        sourceHakSha256 = $categoryMap.sourceHakSha256
        baseItemsSource = 'baseitems.2da'
    }
    blueprintCount = $blueprints.Count
    categorizedBlueprintCount = @($blueprints | Where-Object category -ne '(unmapped)').Count
    unmappedBlueprintCount = @($blueprints | Where-Object category -eq '(unmapped)').Count
    missingBaseItemCount = @($blueprints | Where-Object { -not $_.baseItemPresentInItemHak }).Count
    usedLeafCategoryCount = $categoryGroups.Count
    availableLeafCategoryCount = @($categoryMap.leafCategories).Count
    uniqueResRefCount = @($blueprints.resref | Sort-Object -Unique).Count
    uniqueTagCount = @($blueprints.tag | Sort-Object -Unique).Count
    duplicateTags = $duplicateTags
    itemPropertyUsage = [ordered]@{
        blueprintsWithProperties = @($blueprints | Where-Object propertyCount -gt 0).Count
        propertyInstanceCount = $propertyInstances.Count
        propertyNameRows = $propertyNameUsage
        costTableRows = $costTableUsage
    }
    topLevelCategories = $topLevelGroups
    categories = $categoryGroups
    baseItems = $baseItemGroups
    blueprints = @($blueprints | Sort-Object categoryPath, name, resref)
}
Write-JsonFile -Path (Join-Path $analysisRoot 'blueprint-analysis.json') -Value $analysis -Depth 64

$markdown = [Text.StringBuilder]::new()
[void]$markdown.AppendLine('# MDRN item blueprint ERF analysis')
[void]$markdown.AppendLine()
[void]$markdown.AppendLine("The companion ``$([IO.Path]::GetFileName($source))`` ERF supplies **$($blueprints.Count) UTI item blueprints** for ``mdrnee_item.hak``. The HAK itself still contains no UTIs; this report joins the ERF records to its ``itempal.itp`` palette and ``baseitems.2da`` registrations.")
[void]$markdown.AppendLine()
[void]$markdown.AppendLine('## Reproducible source identity')
[void]$markdown.AppendLine()
[void]$markdown.AppendLine('| Property | Value |')
[void]$markdown.AppendLine('|---|---|')
[void]$markdown.AppendLine("| Source | ``$([IO.Path]::GetFileName($source))`` |")
[void]$markdown.AppendLine("| Size | $((Get-Item -LiteralPath $source).Length.ToString('N0')) bytes |")
[void]$markdown.AppendLine("| SHA-256 | ``$sourceHash`` |")
[void]$markdown.AppendLine("| All ERF resources | $($resources.Count.ToString('N0')) |")
[void]$markdown.AppendLine("| UTI blueprints | $($blueprints.Count.ToString('N0')) |")
[void]$markdown.AppendLine("| Friendly-category matches | $(@($blueprints | Where-Object category -ne '(unmapped)').Count.ToString('N0')) |")
[void]$markdown.AppendLine("| Missing source ``baseitems.2da`` rows | $(@($blueprints | Where-Object { -not $_.baseItemPresentInItemHak }).Count.ToString('N0')) |")
[void]$markdown.AppendLine()
[void]$markdown.AppendLine('Only the UTI records are in item-import scope. The ERF also contains areas, creatures, doors, placeables, scripts, and other module resources; those remain quarantined evidence and are not proposed for `srn_item`.')
[void]$markdown.AppendLine()
[void]$markdown.AppendLine('## Integrity and item-property usage')
[void]$markdown.AppendLine()
[void]$markdown.AppendLine("- **$($analysis.uniqueResRefCount)** distinct ResRefs across **$($blueprints.Count)** blueprints; **$($blueprints.Count - $analysis.uniqueResRefCount)** repeated occurrences.")
[void]$markdown.AppendLine("- **$($analysis.categorizedBlueprintCount) of $($blueprints.Count)** Palette IDs resolve to a friendly ``itempal.itp`` leaf; **$($analysis.unmappedBlueprintCount)** are unmapped.")
[void]$markdown.AppendLine("- **$($blueprints.Count - $analysis.missingBaseItemCount) of $($blueprints.Count)** BaseItem values resolve to a row in the source ``baseitems.2da``; **$($analysis.missingBaseItemCount)** are missing.")
[void]$markdown.AppendLine("- **$(@($blueprints | Where-Object propertyCount -gt 0).Count)** blueprints carry **$($propertyInstances.Count)** item-property instances. Their PropertyName and CostTable rows must be remapped with the merged 2DAs.")
[void]$markdown.AppendLine("- **$($duplicateTags.Count)** tag values are non-unique; this does not invalidate the blueprints, but tag-based scripts may intentionally target more than one template.")
[void]$markdown.AppendLine()
[void]$markdown.AppendLine('## Blueprint categories')
[void]$markdown.AppendLine()
[void]$markdown.AppendLine('| Top-level category | Blueprints | Used leaves |')
[void]$markdown.AppendLine('|---|---:|---:|')
foreach ($group in $topLevelGroups) {
    [void]$markdown.AppendLine("| $($group.name) | $($group.blueprintCount) | $($group.usedLeafCount) |")
}
[void]$markdown.AppendLine()
[void]$markdown.AppendLine('## Base-item usage')
[void]$markdown.AppendLine()
[void]$markdown.AppendLine('| Row | Label | Item class | Blueprints |')
[void]$markdown.AppendLine('|---:|---|---|---:|')
foreach ($group in $baseItemGroups) {
    [void]$markdown.AppendLine("| $($group.row) | ``$($group.label)`` | ``$($group.itemClass)`` | $($group.blueprintCount) |")
}
[void]$markdown.AppendLine()
[void]$markdown.AppendLine('## Detailed blueprints by friendly palette category')
[void]$markdown.AppendLine()
foreach ($group in $categoryGroups) {
    [void]$markdown.AppendLine("### $($group.path) (ID $($group.paletteId), $($group.count))")
    [void]$markdown.AppendLine()
    [void]$markdown.AppendLine('| Blueprint | ResRef | Base item | Item class | Model parts | Properties |')
    [void]$markdown.AppendLine('|---|---|---|---|---|---:|')
    foreach ($blueprint in $group.blueprints) {
        $name = ([string]$blueprint.name).Replace('|', '\|')
        $parts = @($blueprint.modelPart1, $blueprint.modelPart2, $blueprint.modelPart3) |
            Where-Object { $null -ne $_ } | ForEach-Object { [string]$_ }
        [void]$markdown.AppendLine("| $name | ``$($blueprint.resref)`` | $($blueprint.baseItem) ``$($blueprint.baseItemLabel)`` | ``$($blueprint.itemClass)`` | $($parts -join '/') | $($blueprint.propertyCount) |")
    }
    [void]$markdown.AppendLine()
}
if ($MatchTierPath) {
    $matchTier = Get-Content -LiteralPath (Resolve-Path -LiteralPath $MatchTierPath).Path -Raw |
        ConvertFrom-Json -Depth 64
    if ([string]$matchTier.sourceWorkbook.archiveSha256 -cne $sourceHash) {
        throw 'Match Tier source archive SHA-256 does not match InputErf.'
    }
    if ([int]$matchTier.join.unmatchedBlueprints -ne 0 -or
        [int]$matchTier.join.duplicateCandidateResRefs -ne 0 -or
        [int]$matchTier.join.baseItemMismatches -ne 0) {
        throw 'Match Tier input contains unresolved blueprint joins.'
    }
    $allowedTiers = @('Exact identity', 'Visual stand-in')
    $tiers = @($matchTier.tiers)
    if (@($tiers | Where-Object name -notin $allowedTiers).Count) {
        throw 'Match Tier input contains an unsupported tier.'
    }
    foreach ($tierName in $allowedTiers) {
        if (@($tiers | Where-Object name -ceq $tierName).Count -ne 1) {
            throw 'Match Tier input must contain exactly one Exact identity and one Visual stand-in tier.'
        }
    }
    $matchRows = @($tiers | ForEach-Object { @($_.blueprints) })
    if ($matchRows.Count -ne [int]$matchTier.join.matchedBlueprints) {
        throw 'Match Tier detail count does not match its join summary.'
    }
    $seenMatchResRefs = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($tier in $tiers) {
        $tierRows = @($tier.blueprints)
        if ($tierRows.Count -ne [int]$tier.count) {
            throw "Match Tier count does not match its detail: $($tier.name)"
        }
        foreach ($row in $tierRows) {
            if ([string]$row.matchTier -cne [string]$tier.name) {
                throw "Match Tier row is filed under the wrong tier: $($row.blueprintResRef)"
            }
            if (-not $seenMatchResRefs.Add([string]$row.blueprintResRef)) {
                throw "Duplicate Match Tier blueprint ResRef: $($row.blueprintResRef)"
            }
            $known = @($blueprints | Where-Object resref -ieq ([string]$row.blueprintResRef))
            if ($known.Count -ne 1 -or [int]$known[0].baseItem -ne [int]$row.baseItem) {
                throw "Match Tier row no longer matches blueprint analysis: $($row.blueprintResRef)"
            }
        }
    }

    [void]$markdown.AppendLine('## Match Tier subset from the SR3 candidate workbook')
    [void]$markdown.AppendLine()
    [void]$markdown.AppendLine("Source: ``$($matchTier.sourceWorkbook.file)``; SHA-256 ``$($matchTier.sourceWorkbook.sha256)``; classification range ``$($matchTier.sourceWorkbook.candidateSheet)``.")
    [void]$markdown.AppendLine()
    [void]$markdown.AppendLine("The workbook classifies **$($matchRows.Count) of $($blueprints.Count)** MDRN item blueprints as SR3 catalog candidates. Every candidate joins uniquely to this report by Blueprint ResRef and agrees on the UTI base-item row.")
    [void]$markdown.AppendLine()
    [void]$markdown.AppendLine('| Match Tier | Blueprints |')
    [void]$markdown.AppendLine('|---|---:|')
    foreach ($tier in $tiers) {
        [void]$markdown.AppendLine("| $($tier.name) | $($tier.count) |")
    }
    [void]$markdown.AppendLine("| **Total** | **$($matchRows.Count)** |")
    [void]$markdown.AppendLine()
    [void]$markdown.AppendLine('This is an appearance-only shortlist. The workbook explicitly does not transfer costs, properties, descriptions, scripts, combat behavior, models, icons, or 2DA definitions. Its dependency and rights statements were written without the item HAK analysis and remain advisory; this repository''s dependency closure and provenance records control landing decisions.')
    [void]$markdown.AppendLine()
    foreach ($tier in $tiers) {
        [void]$markdown.AppendLine("### $($tier.name) ($($tier.count))")
        [void]$markdown.AppendLine()
        $distribution = @($tier.topLevelCategories | ForEach-Object { "$($_.name): $($_.count)" }) -join '; '
        [void]$markdown.AppendLine("Friendly-category distribution: $distribution.")
        [void]$markdown.AppendLine()
        [void]$markdown.AppendLine('| Rank | Blueprint | ResRef | Friendly MDRN category | Catalog identity | Catalog category | Source tier | Confidence |')
        [void]$markdown.AppendLine('|---:|---|---|---|---|---|---|---|')
        foreach ($row in @($tier.blueprints | Sort-Object rank)) {
            $blueprintName = ([string]$row.blueprintName).Replace('|', '\|').Replace("`r", ' ').Replace("`n", ' ')
            $blueprintResRef = ([string]$row.blueprintResRef).Replace('|', '\|')
            $friendlyCategory = ([string]$row.friendlyCategory).Replace('|', '\|').Replace("`r", ' ').Replace("`n", ' ')
            $catalogId = ([string]$row.catalogId).Replace('|', '\|')
            $catalogName = ([string]$row.catalogName).Replace('|', '\|').Replace("`r", ' ').Replace("`n", ' ')
            $catalogCategory = ([string]$row.catalogCategory).Replace('|', '\|').Replace("`r", ' ').Replace("`n", ' ')
            $catalogSourceTier = ([string]$row.catalogSourceTier).Replace('|', '\|')
            $confidence = ([string]$row.confidence).Replace('|', '\|')
            [void]$markdown.AppendLine("| $($row.rank) | $blueprintName | ``$blueprintResRef`` | $friendlyCategory | $catalogId — $catalogName | $catalogCategory | ``$catalogSourceTier`` | $confidence |")
        }
        [void]$markdown.AppendLine()
    }
}
[IO.File]::WriteAllText((Join-Path $analysisRoot 'blueprint-report.md'), $markdown.ToString().TrimEnd() + "`n", [Text.UTF8Encoding]::new($false))

Publish-SrnDirectorySet @(
    @{ source=$rawRoot; destination=$publishedRawRoot },
    @{ source=$analysisRoot; destination=$publishedAnalysisRoot }
)
}
finally {
    if (Test-Path -LiteralPath $buildRoot) {
        Remove-Item -LiteralPath $buildRoot -Recurse -Force
    }
}
Write-Host "Item blueprint ERF analysis complete: $publishedAnalysisRoot"
