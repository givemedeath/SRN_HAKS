[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Analyze', 'Repair', 'Apply')][string]$Mode,
    [Parameter(Mandatory)][string]$InputHak,
    [Parameter(Mandatory)][string]$OutputRelativePath,
    [string]$ProfilePath,
    [string]$NwnRoot,
    [string]$NwnUserDirectory,
    [string]$ExpectedSha256
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'SrnHaks.Common.psm1') -Force
$repoRoot = Get-SrnRepositoryRoot
$quarantineRoot = Join-Path $repoRoot '.quarantine'

function Resolve-QuarantinePath {
    param([string]$RelativePath)
    if ([string]::IsNullOrWhiteSpace($RelativePath) -or [IO.Path]::IsPathRooted($RelativePath)) {
        throw 'OutputRelativePath must be a non-empty relative path beneath .quarantine.'
    }
    $root = [IO.Path]::GetFullPath($quarantineRoot)
    $resolved = [IO.Path]::GetFullPath((Join-Path $root $RelativePath))
    $prefix = $root.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "OutputRelativePath escapes .quarantine: $RelativePath"
    }
    return $resolved
}

function Add-Relation {
    param([hashtable]$Map, [string]$Resource, [string]$Value)
    $Resource = $Resource.ToLowerInvariant()
    if (-not $Map.ContainsKey($Resource)) {
        $Map[$Resource] = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    }
    [void]$Map[$Resource].Add($Value)
}

function Read-SetFile {
    param([string]$Path)
    $text = Get-Content -LiteralPath $Path -Raw -Encoding Default
    $sections = @{}
    $structuralIssues = [Collections.Generic.List[object]]::new()
    $current = $null
    foreach ($rawLine in ($text -split "`r?`n")) {
        $line = $rawLine.Trim()
        if ($line -match '^\[([^]]+)\]$') {
            $current = $matches[1].ToUpperInvariant()
            if ($sections.ContainsKey($current)) {
                $structuralIssues.Add([pscustomobject]@{ kind = 'duplicate-section'; section = $current })
            }
            else {
                $sections[$current] = @{}
            }
        }
        elseif ($current -and $line.Contains('=')) {
            $parts = $line.Split('=', 2)
            $sections[$current][$parts[0].Trim().ToLowerInvariant()] = $parts[1].Trim()
        }
    }
    $declaredCounts = @{}
    foreach ($declaration in @(
        [pscustomobject]@{ section = 'TILES'; itemPrefix = 'TILE'; minimum = 1 },
        [pscustomobject]@{ section = 'GROUPS'; itemPrefix = 'GROUP'; minimum = 0 }
    )) {
        $count = -1
        $countText = if ($sections.ContainsKey($declaration.section) -and $sections[$declaration.section].ContainsKey('count')) {
            [string]$sections[$declaration.section]['count']
        }
        else {
            '<missing>'
        }
        if (-not [int]::TryParse($countText, [ref]$count) -or $count -lt $declaration.minimum -or $count -gt 100000) {
            $structuralIssues.Add([pscustomobject]@{
                kind = 'invalid-declared-count'; section = $declaration.section
                value = $countText; minimum = $declaration.minimum; maximum = 100000
            })
            $count = -1
        }
        $declaredCounts[$declaration.section] = $count
        $indices = @($sections.Keys | Where-Object { $_ -match "^$($declaration.itemPrefix)(\d+)$" } |
            ForEach-Object { [int]([regex]::Match($_, '(\d+)$').Value) } | Sort-Object)
        $expected = if ($count -gt 0) { @(0..($count - 1)) } else { @() }
        if (($indices -join ',') -cne ($expected -join ',')) {
            $structuralIssues.Add([pscustomobject]@{
                kind = 'declared-section-mismatch'; section = $declaration.section
                declaredCount = $count; indices = $indices
            })
        }
    }
    $tileCount = [int]$declaredCounts['TILES']
    $friendlyName = [IO.Path]::GetFileNameWithoutExtension($Path)
    if ($sections.ContainsKey('GENERAL')) {
        foreach ($field in @('unlocalizedname', 'name')) {
            if ($sections['GENERAL'].ContainsKey($field)) {
                $candidate = [string]$sections['GENERAL'][$field]
                if (-not [string]::IsNullOrWhiteSpace($candidate) -and $candidate -ne '-1') {
                    $friendlyName = $candidate
                    break
                }
            }
        }
    }
    $repairs = [Collections.Generic.List[object]]::new()
    $nonContiguous = [Collections.Generic.List[object]]::new()
    for ($tile = 0; $tile -lt $tileCount; $tile++) {
        $tileSection = "TILE$tile"
        if (-not $sections.ContainsKey($tileSection)) { continue }
        foreach ($kind in @('DOOR', 'SOUND')) {
            $field = if ($kind -eq 'DOOR') { 'doors' } else { 'sounds' }
            $indices = @($sections.Keys | Where-Object { $_ -match "^TILE${tile}${kind}(\d+)$" } | ForEach-Object { [int]([regex]::Match($_, '(\d+)$').Value) } | Sort-Object)
            $expected = if ($indices.Count) { @(0..($indices.Count - 1)) } else { @() }
            if (($indices -join ',') -cne ($expected -join ',')) {
                $nonContiguous.Add([pscustomobject]@{ tile = $tile; kind = $kind.ToLowerInvariant(); indices = $indices })
            }
            $oldText = if ($sections[$tileSection].ContainsKey($field)) { [string]$sections[$tileSection][$field] } else { '<missing>' }
            $oldValue = 0
            if (-not [int]::TryParse($oldText, [ref]$oldValue) -or $oldValue -ne $indices.Count) {
                $repairs.Add([pscustomobject]@{ tile = $tile; field = $field; old = $oldText; new = $indices.Count })
            }
        }
    }
    [pscustomobject]@{
        tileCount = $tileCount
        friendlyName = $friendlyName
        models = @([regex]::Matches($text, '(?im)^Model=(\S+)') | ForEach-Object { $_.Groups[1].Value.ToLowerInvariant() } | Sort-Object -Unique)
        repairs = @($repairs)
        nonContiguous = @($nonContiguous)
        structuralIssues = @($structuralIssues)
        structurallyClean = ($repairs.Count -eq 0 -and $nonContiguous.Count -eq 0 -and $structuralIssues.Count -eq 0)
    }
}

function Read-ModelTextures {
    param([string]$Path)
    $text = Get-Content -LiteralPath $Path -Raw -Encoding Default
    @([regex]::Matches($text, '(?im)^\s*(?:bitmap|texture\d*)\s+([^\s]+)') |
        ForEach-Object { $_.Groups[1].Value.ToLowerInvariant() } |
        Where-Object { $_ -notin @('null', 'none', 'default') } | Sort-Object -Unique)
}

function Write-RepairedSet {
    param(
        [Parameter(Mandatory)][string]$SourcePath,
        [Parameter(Mandatory)][string]$DestinationPath,
        [Parameter(Mandatory)]$SetAnalysis,
        $DoorRowMap
    )

    $encoding = [Text.Encoding]::GetEncoding(1252)
    $sourceBytes = [IO.File]::ReadAllBytes($SourcePath)
    $text = $encoding.GetString($sourceBytes)
    $newline = if ($text.Contains("`r`n")) { "`r`n" } else { "`n" }
    $hasFinalNewline = $text.EndsWith("`n")
    $lines = @($text -split "`r?`n")
    if ($hasFinalNewline -and $lines.Count -and $lines[-1] -eq '') {
        $lines = @($lines[0..($lines.Count - 2)])
    }

    $repairByKey = @{}
    foreach ($repair in @($SetAnalysis.repairs)) {
        $repairByKey["$($repair.tile):$($repair.field)"] = $repair
    }
    $changes = [Collections.Generic.List[object]]::new()
    $currentSection = ''
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index].Trim() -match '^\[([^]]+)\]$') {
            $currentSection = $matches[1].ToUpperInvariant()
            continue
        }
        if ($currentSection -match '^TILE(\d+)$' -and $lines[$index] -match '^(\s*)(Doors|Sounds)(\s*=\s*)(.*?)(\s*)$') {
            $field = $matches[2].ToLowerInvariant()
            $key = "$($currentSection.Substring(4)):$field"
            if ($repairByKey.ContainsKey($key)) {
                $old = $matches[4]
                $new = [string]$repairByKey[$key].new
                $lines[$index] = "$($matches[1])$($matches[2])$($matches[3])$new$($matches[5])"
                $changes.Add([pscustomobject]@{
                    kind = 'section-count'; line = $index + 1; section = $currentSection
                    field = $field; old = $old; new = $new
                })
                [void]$repairByKey.Remove($key)
            }
        }
        elseif ($DoorRowMap -and $currentSection -match '^TILE\d+DOOR\d+$' -and $lines[$index] -match '^(\s*)Type(\s*=\s*)(\d+)(\s*)$') {
            $old = $matches[3]
            if (@($DoorRowMap.PSObject.Properties | Where-Object Name -eq $old).Count) {
                $new = [string]$DoorRowMap.$old
                $lines[$index] = "$($matches[1])Type$($matches[2])$new$($matches[4])"
                $changes.Add([pscustomobject]@{
                    kind = 'door-row-remap'; line = $index + 1; section = $currentSection
                    field = 'type'; old = $old; new = $new
                })
            }
        }
    }
    if ($repairByKey.Count) {
        throw "Could not locate $($repairByKey.Count) declared repair fields in $SourcePath."
    }

    $output = $lines -join $newline
    if ($hasFinalNewline) { $output += $newline }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $DestinationPath) | Out-Null
    [IO.File]::WriteAllText($DestinationPath, $output, $encoding)
    return @($changes)
}

function Get-Recommendation {
    param([IO.FileInfo]$File, [string[]]$ResourceOwners, $Profile)
    $name = $File.Name.ToLowerInvariant()
    $stem = $File.BaseName.ToLowerInvariant()
    $ownerArray = @($ResourceOwners | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $ownerCount = $ownerArray.Count
    if ($ownerCount -gt 1) { return 'srn_t_common' }
    if ($ownerCount -eq 1 -and $Profile -and $Profile.packNames.PSObject.Properties.Name -contains $ownerArray[0]) {
        return [string]$Profile.packNames.($ownerArray[0])
    }
    if ($name -match '_edge\.2da$' -or $name -eq 'doortypes.2da') { return 'srn_2da' }
    if ($name -eq 'genericdoors.2da' -or $File.Extension -ieq '.dwk') { return 'srn_door' }
    if ($File.Extension -ieq '.pwk') { return 'srn_placeable' }
    if ($name -eq 'ambientmusic.2da') { return 'srn_music' }
    if ($name -eq 'ambientsound.2da') { return 'srn_sound' }
    if ($File.Extension -ieq '.bmu') { return 'srn_music' }
    if ($File.Extension -ieq '.wav') { return 'srn_sound' }
    if ($name -eq 'skyboxes.2da' -or $name -match 'sky|asteroid|nebula') { return 'srn_skybox' }
    if ($Profile -and $Profile.PSObject.Properties.Name -contains 'resourcePrefixes') {
        foreach ($property in $Profile.resourcePrefixes.PSObject.Properties) {
            foreach ($prefix in @($property.Value)) {
                if ($stem.StartsWith([string]$prefix, [StringComparison]::OrdinalIgnoreCase)) {
                    return [string]$Profile.packNames.($property.Name)
                }
            }
        }
    }
    if ($File.Extension -ieq '.mdl') {
        $classification = [regex]::Match((Get-Content -LiteralPath $File.FullName -Raw -Encoding Default), '(?im)^classification\s+(\S+)').Groups[1].Value.ToLowerInvariant()
        if ($classification -eq 'effect') { return 'srn_fx' }
        if ($classification -eq 'door') { return 'srn_door' }
    }
    if ($File.Extension -in @('.wok', '.set', '.itp')) { return '.quarantine/deferred/unused-tile-assets' }
    if ($File.Extension -in @('.dds', '.tga', '.txi')) { return '.quarantine/deferred/unproven-textures' }
    if ($File.Extension -ieq '.mdl') { return '.quarantine/deferred/unproven-models' }
    return '.quarantine/deferred/miscellaneous'
}

function Get-2daRowLineIndex {
    param($Lines, [int]$Row)
    for ($index = 0; $index -lt $Lines.Count; $index++) {
        if ($Lines[$index] -match '^\s*(\d+)\s+' -and [int]$matches[1] -eq $Row) { return $index }
    }
    return -1
}

function Set-2daRowNumber {
    param([string]$Line, [int]$Row)
    if ($Line -notmatch '^(\s*)\d+(\s+.*)$') { throw "Cannot parse 2DA row: $Line" }
    return "$($matches[1])$Row$($matches[2])"
}

function Get-2daTokens {
    param([Parameter(Mandatory)][string]$Line)
    return @([regex]::Matches($Line, '"[^"]*"|\S+') | ForEach-Object { $_.Value.Trim('"') })
}

function Update-GffNode {
    param(
        $Node,
        [object[]]$RemoveRules,
        [hashtable]$RemapByValue,
        [hashtable]$RemapCounts,
        [ref]$RemovedCount
    )
    if ($null -eq $Node) { return }
    if ($Node -is [Management.Automation.PSCustomObject]) {
        foreach ($property in @($Node.PSObject.Properties)) {
            $value = $property.Value
            if ($property.Name -ceq 'STRREF' -and $value -is [Management.Automation.PSCustomObject] -and
                [string]$value.type -ceq 'dword') {
                $key = [string][int64]$value.value
                if ($RemapByValue.ContainsKey($key)) {
                    $value.value = [int64]$RemapByValue[$key].targetGameStrRef
                    $RemapCounts[$key] = [int]$RemapCounts[$key] + 1
                }
            }
            elseif ($value -is [Management.Automation.PSCustomObject] -and [string]$value.type -ceq 'list') {
                $kept = [Collections.Generic.List[object]]::new()
                foreach ($item in @($value.value)) {
                    $remove = $false
                    foreach ($rule in $RemoveRules) {
                        $field = @($item.PSObject.Properties | Where-Object Name -ceq ([string]$rule.field))
                        if ($field.Count -eq 1 -and $field[0].Value -is [Management.Automation.PSCustomObject] -and
                            [string]$field[0].Value.value -ceq [string]$rule.value) {
                            $remove = $true
                            break
                        }
                    }
                    if ($remove) { $RemovedCount.Value++ }
                    else {
                        Update-GffNode -Node $item -RemoveRules $RemoveRules -RemapByValue $RemapByValue -RemapCounts $RemapCounts -RemovedCount $RemovedCount
                        $kept.Add($item)
                    }
                }
                $value.value = @($kept)
            }
            else {
                Update-GffNode -Node $value -RemoveRules $RemoveRules -RemapByValue $RemapByValue -RemapCounts $RemapCounts -RemovedCount $RemovedCount
            }
        }
    }
    elseif ($Node -is [Collections.IEnumerable] -and $Node -isnot [string]) {
        foreach ($item in $Node) {
            Update-GffNode -Node $item -RemoveRules $RemoveRules -RemapByValue $RemapByValue -RemapCounts $RemapCounts -RemovedCount $RemovedCount
        }
    }
}

function Replace-2daIntegerToken {
    param(
        [Parameter(Mandatory)][AllowEmptyString()][AllowEmptyCollection()][Collections.Generic.List[string]]$Lines,
        [Parameter(Mandatory)][int64]$SourceValue,
        [Parameter(Mandatory)][int64]$TargetValue,
        [Parameter(Mandatory)][int]$ExpectedOccurrences,
        [Parameter(Mandatory)][string]$Resource
    )
    $pattern = '(?<!\S)' + [regex]::Escape([string]$SourceValue) + '(?!\S)'
    $count = 0
    for ($index = 0; $index -lt $Lines.Count; $index++) {
        $matches = [regex]::Matches($Lines[$index], $pattern)
        if ($matches.Count) {
            $count += $matches.Count
            $Lines[$index] = [regex]::Replace($Lines[$index], $pattern, [string]$TargetValue)
        }
    }
    if ($count -ne $ExpectedOccurrences) {
        throw "$Resource contains $count occurrences of string ref $SourceValue; expected $ExpectedOccurrences."
    }
    return $count
}

function Write-2daLines {
    param(
        [Parameter(Mandatory)][AllowEmptyString()][AllowEmptyCollection()]$Lines,
        [Parameter(Mandatory)][string]$Path
    )
    $normalized = @($Lines | ForEach-Object { ([string]$_).TrimEnd() })
    [IO.File]::WriteAllLines($Path, $normalized, [Text.Encoding]::GetEncoding(1252))
}

$workspace = Resolve-QuarantinePath $OutputRelativePath
$rawRoot = Join-Path $workspace 'raw'
$analysisRoot = Join-Path $workspace 'analysis'
$manifestPath = Join-Path $analysisRoot 'manifest.json'
$reportPath = Join-Path $analysisRoot 'report.md'
$resolvedInput = (Resolve-Path -LiteralPath $InputHak).Path
$resolvedProfilePath = if ($ProfilePath) { (Resolve-Path -LiteralPath $ProfilePath).Path } else { $null }
$profile = if ($resolvedProfilePath) { Get-Content -LiteralPath $resolvedProfilePath -Raw | ConvertFrom-Json -Depth 64 } else { $null }
$profileSha256 = if ($resolvedProfilePath) { (Get-FileHash -LiteralPath $resolvedProfilePath -Algorithm SHA256).Hash.ToUpperInvariant() } else { $null }
if ($profile -and [int]$profile.schemaVersion -ne 1) { throw 'Unsupported import profile schema.' }

if ($Mode -eq 'Analyze') {
    New-Item -ItemType Directory -Force -Path $workspace, $analysisRoot | Out-Null
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedInput).Hash.ToUpperInvariant()
    $requiredHash = if ($ExpectedSha256) { $ExpectedSha256 } elseif ($profile) { [string]$profile.expectedSha256 } else { $null }
    if ($requiredHash -and $actualHash -cne $requiredHash.ToUpperInvariant()) { throw "Input HAK hash mismatch: $actualHash" }

    $erf = Get-SrnTool -Name erf
    $archiveInventory = @(& $erf -f $resolvedInput -t | ForEach-Object { $_.Trim().ToLowerInvariant() } | Where-Object { $_ })
    if ($LASTEXITCODE -ne 0) { throw 'Unable to list input HAK.' }
    if ($profile -and $archiveInventory.Count -ne [int]$profile.expectedResourceCount) { throw "Expected $($profile.expectedResourceCount) resources; found $($archiveInventory.Count)." }
    $stagingRoot = Join-Path $workspace "raw.stage.$([Guid]::NewGuid().ToString('N'))"
    New-Item -ItemType Directory -Path $stagingRoot | Out-Null
    try {
        Push-Location $stagingRoot
        try {
            & $erf -f $resolvedInput -x
            if ($LASTEXITCODE -ne 0) { throw 'HAK extraction failed.' }
        }
        finally {
            Pop-Location
        }
        $rawFiles = @(Get-ChildItem -LiteralPath $stagingRoot -File)
        $archiveSorted = @($archiveInventory | Sort-Object)
        $extractedSorted = @($rawFiles | ForEach-Object { $_.Name.ToLowerInvariant() } | Sort-Object)
        if (($archiveSorted -join "`n") -cne ($extractedSorted -join "`n")) {
            throw 'Extracted inventory does not match the HAK.'
        }
        if (Test-Path -LiteralPath $rawRoot) {
            $rawItem = Get-Item -LiteralPath $rawRoot -Force
            $expectedRawRoot = [IO.Path]::GetFullPath((Join-Path $workspace 'raw'))
            if ([IO.Path]::GetFullPath($rawItem.FullName) -cne $expectedRawRoot -or
                ($rawItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                throw "Refusing to replace unsafe quarantine directory: $($rawItem.FullName)"
            }
            Remove-Item -LiteralPath $rawRoot -Recurse -Force
        }
        Move-Item -LiteralPath $stagingRoot -Destination $rawRoot
        $rawFiles = @(Get-ChildItem -LiteralPath $rawRoot -File)
    }
    finally {
        if (Test-Path -LiteralPath $stagingRoot) {
            Remove-Item -LiteralPath $stagingRoot -Recurse -Force
        }
    }
    $archiveSorted = @($archiveInventory | Sort-Object)
    $extractedSorted = @($rawFiles | ForEach-Object { $_.Name.ToLowerInvariant() } | Sort-Object)
    if (($archiveSorted -join "`n") -cne ($extractedSorted -join "`n")) { throw 'Extracted inventory does not match the HAK.' }

    $fileByName = @{}; foreach ($file in $rawFiles) { $fileByName[$file.Name.ToLowerInvariant()] = $file }
    $owners = @{}; $references = @{}; $setResults = @{}
    foreach ($setFile in @($rawFiles | Where-Object { $_.Extension -ieq '.set' } | Sort-Object Name)) {
        $code = $setFile.BaseName.ToLowerInvariant(); $result = Read-SetFile $setFile.FullName; $setResults[$code] = $result
        Add-Relation $owners $setFile.Name $code
        foreach ($sidecar in @("$code.ini")) { if ($fileByName.ContainsKey($sidecar)) { Add-Relation $owners $sidecar $code } }
        if ($profile -and $profile.paletteFiles.PSObject.Properties.Name -contains $code) {
            foreach ($palette in @($profile.paletteFiles.$code)) { if ($fileByName.ContainsKey($palette)) { Add-Relation $owners $palette $code } }
        }
        $models = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        foreach ($model in $result.models) { [void]$models.Add($model) }
        $edgeName = "${code}_edge.2da"
        if ($fileByName.ContainsKey($edgeName)) {
            $edgeText = Get-Content -LiteralPath $fileByName[$edgeName].FullName -Raw -Encoding Default
            foreach ($match in [regex]::Matches($edgeText, '(?m)^\s*\d+\s+.*?\s([A-Za-z0-9_]+)\s*$')) { [void]$models.Add($match.Groups[1].Value.ToLowerInvariant()) }
        }
        $result | Add-Member -NotePropertyName dependencyModels -NotePropertyValue @($models)
        foreach ($model in $models) {
            foreach ($extension in @('.mdl', '.wok')) { $resource = "$model$extension"; if ($fileByName.ContainsKey($resource)) { Add-Relation $owners $resource $code; Add-Relation $references $resource $setFile.Name } }
            if ($fileByName.ContainsKey("$model.mdl")) {
                foreach ($texture in Read-ModelTextures $fileByName["$model.mdl"].FullName) {
                    foreach ($extension in @('.dds', '.tga', '.txi')) { $resource = "$texture$extension"; if ($fileByName.ContainsKey($resource)) { Add-Relation $owners $resource $code; Add-Relation $references $resource "$model.mdl" } }
                }
            }
        }
        if ($profile -and $profile.lightmapPrefixes.PSObject.Properties.Name -contains $code) {
            foreach ($prefix in @($profile.lightmapPrefixes.$code)) {
                foreach ($file in $rawFiles | Where-Object { $_.BaseName.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) }) { Add-Relation $owners $file.Name $code; Add-Relation $references $file.Name "$code lightmap family" }
            }
        }
    }

    $baseNames = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $baseHashes = @{}
    if ($NwnRoot -and $NwnUserDirectory) {
        $grep = Join-Path (Split-Path -Parent $erf) 'nwn_resman_grep.exe'
        & $grep --root $NwnRoot --userdirectory $NwnUserDirectory --no-ovr --all --md5 | ForEach-Object { if ($_ -match '^\s*(\S+)\s+([0-9a-f]{32})') { [void]$baseNames.Add($matches[1]); $baseHashes[$matches[1].ToLowerInvariant()] = $matches[2].ToLowerInvariant() } }
    }

    $landing = @{}
    if ($profile) {
        foreach ($name in $owners.Keys) {
            $resourceOwners = @($owners[$name] | Sort-Object)
            if (@($resourceOwners | Where-Object { $_ -in @($profile.promotedTilesets) }).Count) {
                $landing[$name] = if ($resourceOwners.Count -gt 1) { 'srn_t_common' } else { [string]$profile.packNames.($resourceOwners[0]) }
            }
        }
        if ($profile.PSObject.Properties.Name -contains 'resourcePrefixes') {
            foreach ($property in $profile.resourcePrefixes.PSObject.Properties) {
                if ($property.Name -notin @($profile.promotedTilesets)) { continue }
                foreach ($file in $rawFiles) {
                    foreach ($prefix in @($property.Value)) {
                        if ($file.BaseName.StartsWith([string]$prefix, [StringComparison]::OrdinalIgnoreCase)) {
                            if (-not $landing.ContainsKey($file.Name)) {
                                $landing[$file.Name] = [string]$profile.packNames.($property.Name)
                            }
                            break
                        }
                    }
                }
            }
        }
        foreach ($edge in @($profile.promotedEdges)) { $landing[$edge] = 'srn_2da' }
        if (@($profile.customDoorRows).Count) {
            if (-not $fileByName.ContainsKey('doortypes.2da')) { throw 'Profile declares custom door rows but the HAK has no doortypes.2da.' }
            $doorTable = @(Get-Content -LiteralPath $fileByName['doortypes.2da'].FullName -Encoding Default)
            foreach ($doorRow in @($profile.customDoorRows)) {
                $line = @($doorTable | Where-Object { $_ -match "^\s*$($doorRow.sourceRow)\s+" }); if ($line.Count -ne 1) { throw "Missing doortypes row $($doorRow.sourceRow)." }
                $model = @($line[0].Trim() -split '\s+')[2].ToLowerInvariant()
                foreach ($extension in @('.mdl', '.dwk')) { $name = "$model$extension"; if ($fileByName.ContainsKey($name)) { $landing[$name] = 'srn_door' } }
                if ($fileByName.ContainsKey("$model.mdl")) {
                    foreach ($texture in Read-ModelTextures $fileByName["$model.mdl"].FullName) { foreach ($extension in @('.dds', '.tga', '.txi')) { $name = "$texture$extension"; if ($fileByName.ContainsKey($name)) { $landing[$name] = 'srn_door' } } }
                }
            }
        }
        if ($profile.PSObject.Properties.Name -contains 'extensionPacks') {
            foreach ($file in $rawFiles) {
                $extension = $file.Extension.TrimStart('.').ToLowerInvariant()
                if ($profile.extensionPacks.PSObject.Properties.Name -contains $extension) {
                    $landing[$file.Name] = [string]$profile.extensionPacks.$extension
                }
            }
        }
        if ($profile.PSObject.Properties.Name -contains 'indexedResourceTableMerges') {
            foreach ($merge in @($profile.indexedResourceTableMerges)) {
                $resource = ([string]$merge.resource).ToLowerInvariant()
                if (-not $fileByName.ContainsKey($resource)) { throw "Missing indexed resource table: $resource" }
                $landing[$resource] = [string]$merge.outputPack
            }
        }
        if ($profile.PSObject.Properties.Name -contains 'skyboxMerge') {
            $resource = ([string]$profile.skyboxMerge.resource).ToLowerInvariant()
            if (-not $fileByName.ContainsKey($resource)) { throw "Missing skybox table: $resource" }
            $landing[$resource] = [string]$profile.skyboxMerge.outputPack
        }
        if ($profile.PSObject.Properties.Name -contains 'genericDoorMerge') {
            $doorPack = if ($profile.genericDoorMerge.PSObject.Properties.Name -contains 'assetPack') {
                [string]$profile.genericDoorMerge.assetPack
            }
            else {
                [string]$profile.genericDoorMerge.outputPack
            }
            $doorTableName = [string]$profile.genericDoorMerge.resource
            if (-not $fileByName.ContainsKey($doorTableName)) { throw "Missing generic-door table: $doorTableName" }
            $landing[$doorTableName] = [string]$profile.genericDoorMerge.outputPack
            foreach ($line in Get-Content -LiteralPath $fileByName[$doorTableName].FullName -Encoding Default) {
                if ($line -notmatch '^\s*\d+\s+\S+\s+\S+\s+(\S+)\s+') { continue }
                $model = $matches[1].ToLowerInvariant()
                if ($model -eq '****' -or -not $fileByName.ContainsKey("$model.mdl")) { continue }
                foreach ($extension in @('.mdl', '.dwk')) {
                    $name = "$model$extension"
                    if ($fileByName.ContainsKey($name)) { $landing[$name] = $doorPack }
                }
                foreach ($texture in Read-ModelTextures $fileByName["$model.mdl"].FullName) {
                    foreach ($extension in @('.dds', '.tga', '.txi')) {
                        $name = "$texture$extension"
                        if ($fileByName.ContainsKey($name)) { $landing[$name] = $doorPack }
                    }
                }
            }
        }
        if ($profile.PSObject.Properties.Name -contains 'promoteRecommendedPacks') {
            $explicitTableResources = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
            if ($profile.PSObject.Properties.Name -contains 'genericDoorMerge') {
                [void]$explicitTableResources.Add([string]$profile.genericDoorMerge.resource)
            }
            if ($profile.PSObject.Properties.Name -contains 'skyboxMerge') {
                [void]$explicitTableResources.Add([string]$profile.skyboxMerge.resource)
            }
            if ($profile.PSObject.Properties.Name -contains 'indexedResourceTableMerges') {
                foreach ($merge in @($profile.indexedResourceTableMerges)) {
                    [void]$explicitTableResources.Add([string]$merge.resource)
                }
            }
            foreach ($file in $rawFiles) {
                if ($explicitTableResources.Contains($file.Name)) { continue }
                $recommendedPack = Get-Recommendation $file @() $profile
                if ($recommendedPack -notin @($profile.promoteRecommendedPacks)) { continue }
                $landing[$file.Name] = $recommendedPack
                if ($file.Extension -ieq '.mdl') {
                    foreach ($texture in Read-ModelTextures $file.FullName) {
                        foreach ($extension in @('.dds', '.tga', '.txi')) {
                            $name = "$texture$extension"
                            if ($fileByName.ContainsKey($name)) { $landing[$name] = $recommendedPack }
                        }
                    }
                }
            }
        }
        foreach ($excluded in @($profile.excludedBaseResources)) { [void]$landing.Remove([string]$excluded) }
        if ($profile.PSObject.Properties.Name -contains 'quarantinedResources') {
            foreach ($deferred in @($profile.quarantinedResources)) { [void]$landing.Remove([string]$deferred) }
        }
        if ($profile.PSObject.Properties.Name -contains 'excludedResources') {
            foreach ($excluded in @($profile.excludedResources)) { [void]$landing.Remove([string]$excluded) }
        }
    }

    $quarantinedNames = if ($profile -and $profile.PSObject.Properties.Name -contains 'quarantinedResources') {
        @($profile.quarantinedResources)
    }
    else {
        @()
    }
    $excludedNames = if ($profile -and $profile.PSObject.Properties.Name -contains 'excludedResources') {
        @($profile.excludedResources)
    }
    else {
        @()
    }
    $records = [Collections.Generic.List[object]]::new()
    foreach ($file in $rawFiles | Sort-Object Name) {
        $name = $file.Name.ToLowerInvariant(); $resourceOwners = if ($owners.ContainsKey($name)) { @($owners[$name] | Sort-Object) } else { @() }
        $resourceOwnerCount = @($resourceOwners).Count
        $disposition = if ($landing.ContainsKey($name)) { 'land' } elseif ($name -eq 'credits.txt' -or $name -in $excludedNames) { 'exclude' } else { 'quarantine' }
        $recommended = if ($landing.ContainsKey($name)) { $landing[$name] } else { Get-Recommendation $file $resourceOwners $profile }
        $landingName = $name
        if ($profile -and $profile.PSObject.Properties.Name -contains 'resourceRenames') {
            $rename = @($profile.resourceRenames.PSObject.Properties | Where-Object Name -ceq $name)
            if ($rename.Count -gt 1) { throw "Duplicate resource rename for $name." }
            if ($rename.Count -eq 1) {
                $landingName = [string]$rename[0].Value
                if ($landingName -cne $landingName.ToLowerInvariant() -or
                    [IO.Path]::GetFileName($landingName) -cne $landingName -or
                    [IO.Path]::GetFileNameWithoutExtension($landingName) -cnotmatch '^[a-z0-9_-]{1,16}$') {
                    throw "Invalid resource rename target '$landingName' for $name."
                }
            }
        }
        $records.Add([pscustomobject]@{
            name = $name; landingName = $landingName; type = $file.Extension.TrimStart('.').ToLowerInvariant(); size = $file.Length
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
            references = if ($references.ContainsKey($name)) { @($references[$name] | Sort-Object) } else { @() }
            owningTilesets = $resourceOwners; baseCollision = if ($baseNames.Contains($name)) { if ((Get-FileHash -Algorithm MD5 -LiteralPath $file.FullName).Hash.ToLowerInvariant() -eq $baseHashes[$name]) { 'same' } else { 'different' } } else { 'none' }
            disposition = $disposition; recommendedPack = $recommended
            confidence = if ($disposition -eq 'land') { 'high' } elseif ($resourceOwnerCount) { 'medium' } else { 'low' }
            prerequisites = if ($disposition -eq 'land') { @() } else { @('Dependency packaging', 'Provenance review', 'Targeted visual/walkmesh validation') }
            reason = if ($disposition -eq 'land') { 'Approved by the reviewed import profile.' } elseif ($name -eq 'credits.txt') { 'Transferred to tracked attribution documents.' } elseif ($name -in $excludedNames) { 'Explicitly excluded by the reviewed import profile.' } elseif ($name -in $quarantinedNames) { 'Explicitly deferred by the reviewed import profile.' } elseif ($resourceOwnerCount) { 'Candidate tileset is not yet promoted or dependency ownership is deferred.' } else { 'No proven dependency from an initially promoted tileset.' }
        })
    }
    if ($records.Count -ne $archiveInventory.Count) { throw 'Manifest coverage failed.' }
    $duplicateLandings = @($records | Where-Object disposition -eq 'land' | Group-Object recommendedPack,landingName | Where-Object Count -gt 1)
    if ($duplicateLandings.Count) { throw "Multiple resources target the same pack identity: $($duplicateLandings.Name -join ', ')." }
    $setSummary = [ordered]@{}; foreach ($code in @($setResults.Keys | Sort-Object)) { $missing = @($setResults[$code].dependencyModels | Where-Object { -not $fileByName.ContainsKey("$_.mdl") }); $setSummary[$code] = [ordered]@{ friendlyName = $setResults[$code].friendlyName; tileCount = $setResults[$code].tileCount; structurallyClean = $setResults[$code].structurallyClean; repairs = $setResults[$code].repairs; nonContiguous = $setResults[$code].nonContiguous; structuralIssues = $setResults[$code].structuralIssues; baseModelDependencies = @($missing | Where-Object { $baseNames.Contains("$_.mdl") }); unresolvedModels = @($missing | Where-Object { -not $baseNames.Contains("$_.mdl") }) } }
    $manifest = [ordered]@{ schemaVersion = 1; profile = if ($profile) { $profile.name } else { $null }; profileSha256 = $profileSha256; sourceFile = [IO.Path]::GetFileName($resolvedInput); sourceSha256 = $actualHash; sourceSize = (Get-Item $resolvedInput).Length; resourceCount = $records.Count; generatedAtUtc = [DateTime]::UtcNow.ToString('o'); setAnalysis = $setSummary; resources = @($records) }
    [IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 64) + "`n", [Text.UTF8Encoding]::new($false))

    $sourceName = [IO.Path]::GetFileName($resolvedInput)
    $report = [Collections.Generic.List[string]]::new(); $report.Add("# ``$sourceName`` import analysis"); $report.Add('')
    $report.Add("- SHA-256: ``$actualHash``"); $report.Add("- Source resources: $($records.Count)"); $report.Add("- Initially landed: $(@($records | Where-Object disposition -eq 'land').Count)"); $report.Add("- Quarantined: $(@($records | Where-Object disposition -eq 'quarantine').Count)"); $report.Add("- Excluded: $(@($records | Where-Object disposition -eq 'exclude').Count)"); $report.Add("- Base collisions: $(@($records | Where-Object baseCollision -ne 'none').Count) ($(@($records | Where-Object baseCollision -eq 'different').Count) different)"); $report.Add('')
    $report.Add('## Tileset readiness'); $report.Add(''); $report.Add('| Code | Friendly name | Tiles | Clean | Repairs | Non-contiguous | Structural issues | EE model dependencies | Known missing models | Recommended pack |'); $report.Add('|---|---|---:|:---:|---:|---:|---:|---:|---:|---|')
    foreach ($code in @($setResults.Keys | Sort-Object)) { $destination = if ($profile -and $profile.packNames.PSObject.Properties.Name -contains $code) { $profile.packNames.$code } else { 'review-required' }; $report.Add("| $code | $($setResults[$code].friendlyName) | $($setResults[$code].tileCount) | $($setResults[$code].structurallyClean) | $(@($setResults[$code].repairs).Count) | $(@($setResults[$code].nonContiguous).Count) | $(@($setResults[$code].structuralIssues).Count) | $(@($setSummary[$code].baseModelDependencies).Count) | $(@($setSummary[$code].unresolvedModels).Count) | $destination |") }
    $report.Add(''); $report.Add('## Disposition by recommended landing'); $report.Add(''); $report.Add('| Landing | Land | Quarantine | Exclude | Bytes |'); $report.Add('|---|---:|---:|---:|---:|')
    foreach ($group in $records | Group-Object recommendedPack | Sort-Object Name) { $report.Add("| $($group.Name) | $(@($group.Group | Where-Object disposition -eq 'land').Count) | $(@($group.Group | Where-Object disposition -eq 'quarantine').Count) | $(@($group.Group | Where-Object disposition -eq 'exclude').Count) | $(($group.Group | Measure-Object size -Sum).Sum) |") }
    $report.Add(''); $report.Add('## Quarantine landing policy'); $report.Add('')
    $report.Add('- Candidate `srn_t_*` resources may be promoted after deterministic SET repair and dependency packaging; targeted engine checks should catalogue visual or walkmesh defects rather than treat them as whole-tileset failures.')
    $report.Add('- `srn_t_common` is reserved for dependencies proven to be shared by multiple promoted tilesets.')
    if ($profile -and $profile.PSObject.Properties.Name -contains 'registerPacks' -and 'srn_placeable' -in @($profile.registerPacks)) {
        $report.Add('- `srn_placeable` is an active component destination for this reviewed profile; its global table rows and palette transforms remain separately validated.')
    }
    else {
        $report.Add('- `srn_door`, `srn_skybox`, `srn_music`, and `srn_sound` are active component destinations when a reviewed profile proves their registrations and dependencies; `srn_placeable` and `srn_fx` remain deferred.')
    }
    $report.Add('- `.quarantine/deferred/unproven-textures` and `.quarantine/deferred/unproven-models` have no proven consumer; they stay local until ownership is established.')
    $report.Add('- `.quarantine/deferred/unused-tile-assets` contains unreferenced tile companions or variants awaiting a SET consumer.')
    $report.Add('- Missing edge models are tracked as localized known issues. Preserve the edge table unless a tested replacement or remap is available.')
    $report.Add(''); $report.Add('## Profile notes'); $report.Add(''); if ($profile -and $profile.PSObject.Properties.Name -contains 'reportNotes') { foreach ($note in @($profile.reportNotes)) { $report.Add("- $note") } } else { $report.Add('- No archive-specific profile notes were supplied; all resources require review before Apply.') }
    [IO.File]::WriteAllLines($reportPath, $report, [Text.UTF8Encoding]::new($false)); Write-Host "Analysis complete: $manifestPath"; exit 0
}

if (-not $profile) { throw "$Mode requires -ProfilePath." }
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "Missing analysis manifest: $manifestPath" }
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json -Depth 64
$inputHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedInput).Hash.ToUpperInvariant()
if ($manifest.sourceSha256 -cne $inputHash -or
    $manifest.profile -cne $profile.name -or
    $manifest.profileSha256 -cne $profileSha256 -or
    [int]$manifest.resourceCount -ne [int]$profile.expectedResourceCount) {
    throw 'Manifest does not match the input HAK/profile.'
}
if ($Mode -eq 'Repair') {
    $repairRoot = Join-Path $workspace 'repaired'
    $experimentRoot = Join-Path $workspace 'experiments'
    $repairLogPath = Join-Path $analysisRoot 'repair-log.json'
    $entries = [Collections.Generic.List[object]]::new()
    foreach ($property in @($manifest.setAnalysis.PSObject.Properties | Sort-Object Name)) {
        $code = $property.Name.ToLowerInvariant()
        $analysis = $property.Value
        $doorRowMap = [pscustomobject]@{}
        if ($profile.PSObject.Properties.Name -contains 'futureDoorRows') {
            foreach ($row in @($profile.futureDoorRows | Where-Object tileset -eq $code)) {
                $doorRowMap | Add-Member -NotePropertyName ([string]$row.sourceRow) -NotePropertyValue ([int]$row.targetRow)
            }
        }
        if (@($analysis.repairs).Count -eq 0 -and $doorRowMap.PSObject.Properties.Count -eq 0) { continue }
        if (@($analysis.nonContiguous).Count) {
            throw "Refusing to guess non-contiguous sections in $code.set."
        }
        if (@($analysis.structuralIssues).Count) {
            throw "Refusing to repair structurally invalid sections in $code.set."
        }
        $source = Join-Path $rawRoot "$code.set"
        $destination = Join-Path (Join-Path $repairRoot $code) "$code.set"
        $changes = @(Write-RepairedSet -SourcePath $source -DestinationPath $destination -SetAnalysis $analysis -DoorRowMap $doorRowMap)
        $validation = Read-SetFile $destination
        if (-not $validation.structurallyClean) {
            throw "Repaired $code.set failed structural validation."
        }
        $entries.Add([pscustomobject]@{
            tileset = $code
            friendlyName = [string]$analysis.friendlyName
            source = "raw/$code.set"
            output = "repaired/$code/$code.set"
            sourceSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash.ToLowerInvariant()
            repairedSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $destination).Hash.ToLowerInvariant()
            changes = $changes
            structurallyClean = $true
            unresolvedModels = @($analysis.unresolvedModels)
            promotionStatus = if (@($analysis.unresolvedModels).Count) { 'candidate-known-visual-walkmesh-gaps' } else { 'candidate-ready-targeted-validation' }
        })
    }
    $edgeExperiments = [Collections.Generic.List[object]]::new()
    if ($profile.PSObject.Properties.Name -contains 'edgeModelExperiments') {
        foreach ($experiment in @($profile.edgeModelExperiments)) {
            $source = Join-Path $rawRoot ([string]$experiment.resource)
            if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
                throw "Missing edge-table experiment source: $source"
            }
            $encoding = [Text.Encoding]::GetEncoding(1252)
            $lines = [Collections.Generic.List[string]]::new()
            foreach ($line in [IO.File]::ReadAllLines($source, $encoding)) { $lines.Add($line) }
            $changes = [Collections.Generic.List[object]]::new()
            foreach ($mapping in @($experiment.modelRemaps)) {
                $targetModel = Join-Path $rawRoot "$($mapping.target).mdl"
                if (-not (Test-Path -LiteralPath $targetModel -PathType Leaf)) {
                    throw "Missing experiment target model: $targetModel"
                }
                $found = 0
                for ($index = 0; $index -lt $lines.Count; $index++) {
                    $pattern = "(?<![A-Za-z0-9_])$([regex]::Escape([string]$mapping.source))(?![A-Za-z0-9_])"
                    if ($lines[$index] -match $pattern) {
                        $lines[$index] = [regex]::Replace($lines[$index], $pattern, [string]$mapping.target)
                        $changes.Add([pscustomobject]@{
                            line = $index + 1; source = [string]$mapping.source
                            target = [string]$mapping.target
                        })
                        $found++
                    }
                }
                if ($found -eq 0) { throw "Experiment source model was not referenced: $($mapping.source)" }
            }
            if ($experiment.PSObject.Properties.Name -contains 'tokenRemaps') {
                foreach ($mapping in @($experiment.tokenRemaps)) {
                    $targetSet = Join-Path $rawRoot "$($experiment.tileset).set"
                    if (-not (Test-Path -LiteralPath $targetSet -PathType Leaf) -or
                        -not [regex]::IsMatch((Get-Content -LiteralPath $targetSet -Raw -Encoding Default), "(?im)^Name=$([regex]::Escape([string]$mapping.target))\r?$") ) {
                        throw "Edge-table remap target is not declared by $($experiment.tileset).set: $($mapping.target)"
                    }
                    $found = 0
                    for ($index = 0; $index -lt $lines.Count; $index++) {
                        $pattern = "(?<![A-Za-z0-9_])$([regex]::Escape([string]$mapping.source))(?![A-Za-z0-9_])"
                        if ($lines[$index] -match $pattern) {
                            $lines[$index] = [regex]::Replace($lines[$index], $pattern, [string]$mapping.target)
                            $changes.Add([pscustomobject]@{
                                line = $index + 1; source = [string]$mapping.source
                                target = [string]$mapping.target
                            })
                            $found++
                        }
                    }
                    if ($found -eq 0) { throw "Edge-table source token was not referenced: $($mapping.source)" }
                }
            }
            $destination = Join-Path (Join-Path $experimentRoot ([string]$experiment.tileset)) ([string]$experiment.resource)
            New-Item -ItemType Directory -Force (Split-Path -Parent $destination) | Out-Null
            [IO.File]::WriteAllLines($destination, $lines, $encoding)
            $edgeExperiments.Add([pscustomobject]@{
                tileset = [string]$experiment.tileset
                friendlyName = [string]$manifest.setAnalysis.([string]$experiment.tileset).friendlyName
                resource = [string]$experiment.resource
                output = "experiments/$($experiment.tileset)/$($experiment.resource)"
                sourceSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash.ToLowerInvariant()
                experimentSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $destination).Hash.ToLowerInvariant()
                changes = @($changes)
                activation = if ($experiment.activate) { 'approved-repair-pending-retest' } else { 'optional-targeted-visual-walkmesh-comparison' }
            })
        }
    }
    $repairLog = [ordered]@{
        schemaVersion = 1
        profile = $profile.name
        profileSha256 = $profileSha256
        sourceSha256 = $inputHash
        generatedAtUtc = [DateTime]::UtcNow.ToString('o')
        rawResourcesModified = 0
        repairedSetCount = $entries.Count
        entries = @($entries)
        edgeExperiments = @($edgeExperiments)
    }
    [IO.File]::WriteAllText($repairLogPath, ($repairLog | ConvertTo-Json -Depth 64) + "`n", [Text.UTF8Encoding]::new($false))

    $reportLines = [Collections.Generic.List[string]]::new()
    foreach ($line in [IO.File]::ReadAllLines($reportPath)) {
        if ($line -eq '<!-- repair-results -->') { break }
        $reportLines.Add($line)
    }
    $reportLines.Add('')
    $reportLines.Add('<!-- repair-results -->')
    $reportLines.Add('## Repaired SET artifacts')
    $reportLines.Add('')
    $reportLines.Add('Raw extraction remains byte-for-byte unchanged. Repaired SETs are generated beneath the quarantine workspace; Apply selects them for promoted packs unless `preserveRawSets` names the tileset.')
    $reportLines.Add('')
    $reportLines.Add('| Code | Friendly name | Changes | Structural result | Readiness |')
    $reportLines.Add('|---|---|---:|---|---|')
    foreach ($entry in $entries) {
        $reportLines.Add("| $($entry.tileset) | $($entry.friendlyName) | $(@($entry.changes).Count) | clean | $($entry.promotionStatus) |")
    }
    $reportLines.Add('')
    $reportLines.Add('Every changed line, old value, new value, and repaired-file hash is recorded in `repair-log.json`.')
    if ($edgeExperiments.Count) {
        $reportLines.Add('')
        $reportLines.Add('## Edge-table repair candidates')
        $reportLines.Add('')
        $reportLines.Add('| Code | Friendly name | Resource | Remapped references | Activation |')
        $reportLines.Add('|---|---|---|---:|---|')
        foreach ($experiment in $edgeExperiments) {
            $reportLines.Add("| $($experiment.tileset) | $($experiment.friendlyName) | $($experiment.resource) | $(@($experiment.changes).Count) | $($experiment.activation) |")
        }
        $reportLines.Add('')
        if (@($edgeExperiments | Where-Object activation -eq 'approved-repair-pending-retest').Count) {
            $reportLines.Add('Repairs marked `approved-repair-pending-retest` are selected by Apply. Other experiments remain quarantined until targeted visual and walkmesh comparison.')
        }
        else {
            $reportLines.Add('Experimental edge tables remain quarantined and do not replace the preserved source table without targeted visual and walkmesh comparison.')
        }
    }
    [IO.File]::WriteAllLines($reportPath, $reportLines, [Text.UTF8Encoding]::new($false))

    $docs = Join-Path $repoRoot 'docs\imports'
    New-Item -ItemType Directory -Force $docs | Out-Null
    Copy-Item $manifestPath (Join-Path $docs "$($profile.reportStem)-manifest.json") -Force
    Copy-Item $repairLogPath (Join-Path $docs "$($profile.reportStem)-repair-log.json") -Force
    Copy-Item $reportPath (Join-Path $docs "$($profile.reportStem)-analysis.md") -Force
    Write-Host "Repair complete: $repairLogPath"
    exit 0
}
$configPath = Join-Path $repoRoot 'hakbuilder.json'
$configuration = Get-Content $configPath -Raw | ConvertFrom-Json -Depth 32
if ($profile.PSObject.Properties.Name -contains 'expectedOverrides') {
    $configuredOverrides = @($configuration.ExpectedOverrides)
    foreach ($requested in @($profile.expectedOverrides)) {
        $resource = ([string]$requested.resource).ToLowerInvariant()
        $packs = @($requested.packs | ForEach-Object { [string]$_ } | Sort-Object -Unique)
        $existing = @($configuredOverrides | Where-Object { ([string]$_.Resource).ToLowerInvariant() -ceq $resource })
        if ($existing.Count -gt 1) { throw "Duplicate configured expected override '$resource'." }
        if ($existing.Count -eq 1) {
            $existingPacks = @($existing[0].Packs | ForEach-Object { [string]$_ } | Sort-Object -Unique)
            if (($existingPacks -join "`n") -cne ($packs -join "`n")) {
                throw "Configured expected override '$resource' differs from the reviewed import profile."
            }
        }
    }
}
$repairLogPath = Join-Path $analysisRoot 'repair-log.json'
$repairLog = if (Test-Path -LiteralPath $repairLogPath -PathType Leaf) {
    Get-Content -LiteralPath $repairLogPath -Raw | ConvertFrom-Json -Depth 64
}
else {
    $null
}
$resolvedStringRefRemaps = @{}
$stringRefAllocations = [Collections.Generic.List[object]]::new()
$handledStringRefResources = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
if ($profile.PSObject.Properties.Name -contains 'stringRefRemaps') {
    $registry = Get-Content -Raw -LiteralPath (Join-Path $repoRoot 'srn_tlk/allocations.json') | ConvertFrom-Json -Depth 32
    $canonicalTlk = Get-Content -Raw -LiteralPath (Join-Path $repoRoot 'srn_tlk/srn.tlk.json') | ConvertFrom-Json -Depth 32
    foreach ($remap in @($profile.stringRefRemaps)) {
        $resource = ([string]$remap.resource).ToLowerInvariant()
        $allocation = @($registry.allocations | Where-Object {
            ([string]$_.key -ceq [string]$remap.key -or
                ($_.PSObject.Properties.Name -contains 'aliases' -and @($_.aliases) -ccontains [string]$remap.key)) -and
            [string]$_.status -ceq 'active'
        })
        if ($allocation.Count -ne 1) { throw "String-ref key '$($remap.key)' does not resolve to one active allocation." }
        $tlkEntry = @($canonicalTlk.entries | Where-Object { [int]$_.id -eq [int]$allocation[0].id })
        if ($tlkEntry.Count -ne 1) { throw "String-ref key '$($remap.key)' has no canonical TLK entry." }
        if (-not $resolvedStringRefRemaps.ContainsKey($resource)) {
            $resolvedStringRefRemaps[$resource] = [Collections.Generic.List[object]]::new()
        }
        $targetValue = 0x01000000 + [int]$allocation[0].id
        $resolvedStringRefRemaps[$resource].Add([pscustomobject]@{
            key = [string]$remap.key
            sourceGameStrRef = [int64]$remap.sourceGameStrRef
            targetGameStrRef = [int64]$targetValue
            expectedOccurrences = [int]$remap.expectedOccurrences
            text = [string]$tlkEntry[0].text
        })
    }
}
$generatedResources = @{}
$globalAllocations = [Collections.Generic.List[object]]::new()
if (($profile.PSObject.Properties.Name -contains 'genericDoorMerge') -or
    ($profile.PSObject.Properties.Name -contains 'skyboxMerge') -or
    ($profile.PSObject.Properties.Name -contains 'indexedResourceTableMerges') -or
    ($profile.PSObject.Properties.Name -contains 'gffTransforms')) {
    if (-not $NwnRoot -or -not $NwnUserDirectory) {
        throw 'Apply requires NWN root and user directory for baseline-preserving global 2DA merges.'
    }
    $erf = Get-SrnTool -Name erf
    $cat = Join-Path (Split-Path -Parent $erf) 'nwn_resman_cat.exe'
    $generatedRoot = Join-Path $workspace 'generated'
    New-Item -ItemType Directory -Force -Path $generatedRoot | Out-Null
}
if ($profile.PSObject.Properties.Name -contains 'genericDoorMerge') {
    $merge = $profile.genericDoorMerge
    $resource = ([string]$merge.resource).ToLowerInvariant()
    $baseLines = [Collections.Generic.List[string]]::new()
    foreach ($line in @(& $cat --root $NwnRoot --userdirectory $NwnUserDirectory --no-ovr $resource)) { $baseLines.Add($line) }
    if ($LASTEXITCODE -ne 0 -or -not $baseLines.Count) { throw "Unable to read EE baseline $resource." }
    $baseModels = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($line in $baseLines) {
        if ($line -match '^\s*\d+\s+\S+\s+\S+\s+(\S+)\s+' -and $matches[1] -ne '****') {
            [void]$baseModels.Add($matches[1])
        }
    }
    $sourceLines = @([IO.File]::ReadAllLines((Join-Path $rawRoot $resource), [Text.Encoding]::GetEncoding(1252)))
    $targetRow = [int]$merge.allocationStart
    $added = 0
    foreach ($line in $sourceLines) {
        if ($line -notmatch '^\s*(\d+)\s+(\S+)\s+\S+\s+(\S+)\s+') { continue }
        $sourceRow = [int]$matches[1]
        $label = $matches[2]
        $model = $matches[3]
        if ($model -eq '****' -or -not (Test-Path -LiteralPath (Join-Path $rawRoot "$model.mdl"))) { continue }
        if ($baseModels.Contains($model)) { continue }
        while ($true) {
            $targetIndex = Get-2daRowLineIndex $baseLines $targetRow
            if ($targetIndex -lt 0) { throw "$resource does not declare allocation row $targetRow." }
            if ($baseLines[$targetIndex] -match '^\s*\d+\s+(\S+)\s+\S+\s+(\S+)\s+' -and
                $matches[1] -eq '****' -and $matches[2] -eq '****') { break }
            $targetRow++
        }
        $baseLines[$targetIndex] = Set-2daRowNumber $line $targetRow
        [void]$baseModels.Add($model)
        $globalAllocations.Add([pscustomobject]@{
            table = $resource; sourceRow = $sourceRow; targetRow = $targetRow
            label = $label; model = $model; pack = [string]$merge.outputPack
        })
        $targetRow++
        $added++
    }
    if ($merge.PSObject.Properties.Name -contains 'expectedAddedRows' -and $added -ne [int]$merge.expectedAddedRows) {
        throw "$resource added $added rows; expected $($merge.expectedAddedRows)."
    }
    $destination = Join-Path $generatedRoot $resource
    [IO.File]::WriteAllLines($destination, $baseLines, [Text.Encoding]::GetEncoding(1252))
    $generatedResources[$resource] = [pscustomobject]@{
        path = $destination
        sha256 = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
if ($profile.PSObject.Properties.Name -contains 'skyboxMerge') {
    $merge = $profile.skyboxMerge
    $resource = ([string]$merge.resource).ToLowerInvariant()
    $baseLines = [Collections.Generic.List[string]]::new()
    foreach ($line in @(& $cat --root $NwnRoot --userdirectory $NwnUserDirectory --no-ovr $resource)) { $baseLines.Add($line) }
    if ($LASTEXITCODE -ne 0 -or -not $baseLines.Count) { throw "Unable to read EE baseline $resource." }
    $sourceLines = @([IO.File]::ReadAllLines((Join-Path $rawRoot $resource), [Text.Encoding]::GetEncoding(1252)))
    foreach ($row in @($merge.rows)) {
        $sourceLine = @($sourceLines | Where-Object { $_ -match "^\s*$($row.sourceRow)\s+" })
        if ($sourceLine.Count -ne 1) { throw "Cannot locate $resource source row $($row.sourceRow)." }
        $replacement = Set-2daRowNumber $sourceLine[0] ([int]$row.targetRow)
        $targetIndex = Get-2daRowLineIndex $baseLines ([int]$row.targetRow)
        if ($targetIndex -ge 0) {
            throw "$resource baseline row $($row.targetRow) is occupied; refusing to replace it."
        }
        $baseLines.Add($replacement)
        $tokens = @($sourceLine[0].Trim() -split '\s+')
        $globalAllocations.Add([pscustomobject]@{
            table = $resource; sourceRow = [int]$row.sourceRow; targetRow = [int]$row.targetRow
            label = $tokens[1]; model = $null; pack = [string]$merge.outputPack
        })
    }
    $destination = Join-Path $generatedRoot $resource
    [IO.File]::WriteAllLines($destination, $baseLines, [Text.Encoding]::GetEncoding(1252))
    $generatedResources[$resource] = [pscustomobject]@{
        path = $destination
        sha256 = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
if ($profile.PSObject.Properties.Name -contains 'indexedResourceTableMerges') {
    foreach ($merge in @($profile.indexedResourceTableMerges)) {
        $resource = ([string]$merge.resource).ToLowerInvariant()
        $baseLines = [Collections.Generic.List[string]]::new()
        foreach ($line in @(& $cat --root $NwnRoot --userdirectory $NwnUserDirectory --no-ovr $resource)) { $baseLines.Add($line) }
        if ($LASTEXITCODE -ne 0 -or -not $baseLines.Count) { throw "Unable to read EE baseline $resource." }
        $sourceLines = @([IO.File]::ReadAllLines((Join-Path $rawRoot $resource), [Text.Encoding]::GetEncoding(1252)))
        $mappings = [Collections.Generic.List[object]]::new()
        foreach ($range in @($merge.sourceRowRanges)) {
            if ([string]$range -notmatch '^(\d+)-(\d+)$') { throw "Invalid $resource source row range: $range" }
            $first = [int]$matches[1]; $last = [int]$matches[2]
            if ($last -lt $first) { throw "Invalid descending $resource source row range: $range" }
            for ($row = $first; $row -le $last; $row++) { $mappings.Add([pscustomobject]@{ sourceRow = $row; targetRow = $row }) }
        }
        foreach ($row in @($merge.rowMappings)) {
            $mappings.Add([pscustomobject]@{ sourceRow = [int]$row.sourceRow; targetRow = [int]$row.targetRow })
        }
        $duplicateTargets = @($mappings | Group-Object targetRow | Where-Object Count -gt 1)
        if ($duplicateTargets.Count) { throw "$resource has duplicate target mappings: $($duplicateTargets.Name -join ', ')" }
        $header = @($baseLines | Where-Object { $_ -match '^\s*[A-Za-z]' } | Select-Object -First 1)
        if ($header.Count -ne 1) { throw "Unable to identify $resource columns." }
        $headerTokens = @(Get-2daTokens $header[0])
        $columnCount = $headerTokens.Count
        $existingRows = @($baseLines | Where-Object { $_ -match '^\s*\d+\s+' } | ForEach-Object { [int]([regex]::Match($_, '^\s*(\d+)').Groups[1].Value) })
        $lastExistingRow = if ($existingRows.Count) { ($existingRows | Measure-Object -Maximum).Maximum } else { -1 }
        $maximumTarget = if ($mappings.Count) { ($mappings.targetRow | Measure-Object -Maximum).Maximum } else { $lastExistingRow }
        for ($row = $lastExistingRow + 1; $row -le $maximumTarget; $row++) {
            $baseLines.Add("$row " + ((@('****') * $columnCount) -join ' '))
        }
        foreach ($mapping in @($mappings | Sort-Object targetRow)) {
            $sourceLine = @($sourceLines | Where-Object { $_ -match "^\s*$($mapping.sourceRow)\s+" })
            if ($sourceLine.Count -ne 1) { throw "Cannot locate $resource source row $($mapping.sourceRow)." }
            $targetIndex = Get-2daRowLineIndex $baseLines ([int]$mapping.targetRow)
            if ($targetIndex -lt 0) { throw "Cannot locate $resource target row $($mapping.targetRow)." }
            $targetTokens = @(Get-2daTokens $baseLines[$targetIndex])
            $allowedTargetTokens = if ($merge.PSObject.Properties.Name -contains 'allowedTargetTokens') {
                @($merge.allowedTargetTokens | ForEach-Object { [string]$_ })
            }
            else { @() }
            $occupiedTokens = @($targetTokens | Select-Object -Skip 1 | Where-Object {
                $_ -ne '****' -and $_ -notin $allowedTargetTokens
            })
            if ($occupiedTokens.Count) {
                throw "$resource baseline row $($mapping.targetRow) is occupied; refusing to replace it."
            }
            $baseLines[$targetIndex] = Set-2daRowNumber $sourceLine[0] ([int]$mapping.targetRow)
            $sourceTokens = @(Get-2daTokens $sourceLine[0])
            $reportResource = if ($merge.PSObject.Properties.Name -contains 'reportResourceColumn') {
                $columnName = [string]$merge.reportResourceColumn
                $columnIndex = [Array]::IndexOf([string[]]$headerTokens, $columnName)
                if ($columnIndex -lt 0) { throw "$resource has no report resource column '$columnName'." }
                $sourceTokens[$columnIndex + 1]
            }
            elseif ($sourceTokens.Count -gt 2) { $sourceTokens[2] }
            else { $null }
            $globalAllocations.Add([pscustomobject]@{
                table = $resource; sourceRow = [int]$mapping.sourceRow; targetRow = [int]$mapping.targetRow
                label = $sourceTokens[1]; resource = $reportResource; pack = [string]$merge.outputPack
            })
        }
        if ($merge.PSObject.Properties.Name -contains 'expectedAddedRows' -and $mappings.Count -ne [int]$merge.expectedAddedRows) {
            throw "$resource added $($mappings.Count) rows; expected $($merge.expectedAddedRows)."
        }
        $destination = Join-Path $generatedRoot $resource
        [IO.File]::WriteAllLines($destination, $baseLines, [Text.Encoding]::GetEncoding(1252))
        $generatedResources[$resource] = [pscustomobject]@{
            path = $destination
            sha256 = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
}
$gffTransformResults = [Collections.Generic.List[object]]::new()
if ($profile.PSObject.Properties.Name -contains 'gffTransforms') {
    $gff = Join-Path (Split-Path -Parent (Get-SrnTool -Name erf)) 'nwn_gff.exe'
    foreach ($transform in @($profile.gffTransforms)) {
        $resource = ([string]$transform.resource).ToLowerInvariant()
        $source = Join-Path $rawRoot $resource
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing GFF transform source: $resource" }
        $jsonPath = Join-Path $generatedRoot "$resource.json"
        $destination = Join-Path $generatedRoot $resource
        & $gff -i $source -o $jsonPath -k json --pretty
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $jsonPath -PathType Leaf)) {
            throw "Unable to decode GFF resource $resource."
        }
        $document = Get-Content -LiteralPath $jsonPath -Raw | ConvertFrom-Json -Depth 100
        $remapByValue = @{}
        $remapCounts = @{}
        foreach ($remap in @($resolvedStringRefRemaps[$resource])) {
            $key = [string][int64]$remap.sourceGameStrRef
            if ($remapByValue.ContainsKey($key)) { throw "$resource has duplicate GFF string-ref remap $key." }
            $remapByValue[$key] = $remap
            $remapCounts[$key] = 0
        }
        $removedCount = 0
        $removeRules = if ($transform.PSObject.Properties.Name -contains 'removeStructs') { @($transform.removeStructs) } else { @() }
        Update-GffNode -Node $document -RemoveRules $removeRules -RemapByValue $remapByValue -RemapCounts $remapCounts -RemovedCount ([ref]$removedCount)
        $expectedRemoved = if ($transform.PSObject.Properties.Name -contains 'expectedRemovedStructs') { [int]$transform.expectedRemovedStructs } else { 0 }
        if ($removedCount -ne $expectedRemoved) {
            throw "$resource removed $removedCount GFF structures; expected $expectedRemoved."
        }
        foreach ($key in $remapByValue.Keys) {
            $remap = $remapByValue[$key]
            if ([int]$remapCounts[$key] -ne [int]$remap.expectedOccurrences) {
                throw "$resource contains $($remapCounts[$key]) GFF occurrences of string ref $key; expected $($remap.expectedOccurrences)."
            }
            $stringRefAllocations.Add([pscustomobject]@{
                table = $resource; key = $remap.key; sourceGameStrRef = $remap.sourceGameStrRef
                targetGameStrRef = $remap.targetGameStrRef; occurrences = [int]$remapCounts[$key]; text = $remap.text
            })
        }
        [IO.File]::WriteAllText($jsonPath, ($document | ConvertTo-Json -Depth 100), [Text.UTF8Encoding]::new($false))
        & $gff -i $jsonPath -l json -o $destination -k gff
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $destination -PathType Leaf)) {
            throw "Unable to encode transformed GFF resource $resource."
        }
        $generatedResources[$resource] = [pscustomobject]@{
            path = $destination
            sha256 = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
        }
        [void]$handledStringRefResources.Add($resource)
        $gffTransformResults.Add([pscustomobject]@{
            resource = $resource; removedStructs = $removedCount; remappedStringRefs = ($remapCounts.Values | Measure-Object -Sum).Sum
        })
    }
}
foreach ($resource in @($resolvedStringRefRemaps.Keys | Where-Object { $generatedResources.ContainsKey($_) })) {
    if ($handledStringRefResources.Contains($resource)) { continue }
    $generated = $generatedResources[$resource]
    $lines = [Collections.Generic.List[string]]::new()
    foreach ($line in [IO.File]::ReadAllLines([string]$generated.path, [Text.Encoding]::GetEncoding(1252))) { $lines.Add($line) }
    foreach ($remap in @($resolvedStringRefRemaps[$resource])) {
        $occurrences = Replace-2daIntegerToken -Lines $lines -SourceValue $remap.sourceGameStrRef -TargetValue $remap.targetGameStrRef -ExpectedOccurrences $remap.expectedOccurrences -Resource $resource
        $stringRefAllocations.Add([pscustomobject]@{
            table = $resource; key = $remap.key; sourceGameStrRef = $remap.sourceGameStrRef
            targetGameStrRef = $remap.targetGameStrRef; occurrences = $occurrences; text = $remap.text
        })
    }
    Write-2daLines -Path ([string]$generated.path) -Lines $lines
    $generated.sha256 = (Get-FileHash -LiteralPath ([string]$generated.path) -Algorithm SHA256).Hash.ToLowerInvariant()
    [void]$handledStringRefResources.Add($resource)
}
$applyPlan = [Collections.Generic.List[object]]::new()
foreach ($record in @($manifest.resources | Where-Object disposition -eq 'land')) {
    $pack = [string]$record.recommendedPack
    if ($pack -cnotmatch '^srn_[a-z0-9_]{1,12}$' -or $pack -notin @($profile.registerPacks)) {
        throw "Ambiguous or unregistered landing for $($record.name): $pack"
    }
    $rawSource = Join-Path $rawRoot $record.name
    if (-not (Test-Path -LiteralPath $rawSource -PathType Leaf)) {
        throw "Missing analyzed resource: $rawSource"
    }
    $rawHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $rawSource).Hash.ToLowerInvariant()
    if ($rawHash -cne [string]$record.sha256) {
        throw "Analyzed resource hash mismatch: $rawSource"
    }

    $source = $rawSource
    $expectedHash = [string]$record.sha256
    if ($record.type -eq 'set') {
        $code = [IO.Path]::GetFileNameWithoutExtension([string]$record.name).ToLowerInvariant()
        $setProperty = @($manifest.setAnalysis.PSObject.Properties | Where-Object Name -eq $code)
        $preserveRawSet = $profile.PSObject.Properties.Name -contains 'preserveRawSets' -and
            $code -in @($profile.preserveRawSets)
        $hasDoorRowRemaps = $profile.PSObject.Properties.Name -contains 'futureDoorRows' -and
            @($profile.futureDoorRows | Where-Object tileset -eq $code).Count -gt 0
        if (-not $preserveRawSet -and $setProperty.Count -eq 1 -and
            (@($setProperty[0].Value.repairs).Count -gt 0 -or $hasDoorRowRemaps)) {
            if (-not $repairLog -or $repairLog.sourceSha256 -cne $inputHash -or
                $repairLog.profile -cne $profile.name -or $repairLog.profileSha256 -cne $profileSha256) {
                throw "Missing or mismatched repair log for $($record.name)."
            }
            $repairEntry = @($repairLog.entries | Where-Object tileset -eq $code)
            if ($repairEntry.Count -ne 1 -or -not $repairEntry[0].structurallyClean -or $repairEntry[0].sourceSha256 -cne $rawHash) {
                throw "Missing or invalid repaired SET entry for $($record.name)."
            }
            $source = Join-Path (Join-Path $workspace 'repaired') "$code\$code.set"
            $expectedHash = [string]$repairEntry[0].repairedSha256
            if (-not (Test-Path -LiteralPath $source -PathType Leaf) -or
                (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash.ToLowerInvariant() -cne $expectedHash) {
                throw "Repaired SET hash mismatch: $source"
            }
        }
    }
    elseif ($profile.PSObject.Properties.Name -contains 'edgeModelExperiments') {
        $activeEdgeRepair = @($profile.edgeModelExperiments | Where-Object {
            $_.activate -and [string]$_.resource -ceq [string]$record.name
        })
        if ($activeEdgeRepair.Count -gt 1) {
            throw "Multiple active edge-table repairs target $($record.name)."
        }
        if ($activeEdgeRepair.Count -eq 1) {
            if (-not $repairLog -or $repairLog.sourceSha256 -cne $inputHash -or
                $repairLog.profile -cne $profile.name -or $repairLog.profileSha256 -cne $profileSha256) {
                throw "Missing or mismatched repair log for $($record.name)."
            }
            $edgeEntry = @($repairLog.edgeExperiments | Where-Object {
                [string]$_.tileset -ceq [string]$activeEdgeRepair[0].tileset -and
                [string]$_.resource -ceq [string]$record.name
            })
            if ($edgeEntry.Count -ne 1 -or $edgeEntry[0].sourceSha256 -cne $rawHash) {
                throw "Missing or invalid edge-table repair entry for $($record.name)."
            }
            $source = Join-Path $workspace ([string]$edgeEntry[0].output).Replace('/', [IO.Path]::DirectorySeparatorChar)
            $expectedHash = [string]$edgeEntry[0].experimentSha256
            if (-not (Test-Path -LiteralPath $source -PathType Leaf) -or
                (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash.ToLowerInvariant() -cne $expectedHash) {
                throw "Repaired edge-table hash mismatch: $source"
            }
        }
    }
    if ($generatedResources.ContainsKey(([string]$record.name).ToLowerInvariant())) {
        $generated = $generatedResources[([string]$record.name).ToLowerInvariant()]
        $source = [string]$generated.path
        $expectedHash = [string]$generated.sha256
    }

    $destinationDirectory = Join-Path $repoRoot $pack
    $landingName = if ($record.PSObject.Properties.Name -contains 'landingName') { [string]$record.landingName } else { [string]$record.name }
    $destination = Join-Path $destinationDirectory $landingName
    if (Test-Path -LiteralPath $destination) {
        if ((Get-FileHash -Algorithm SHA256 -LiteralPath $destination).Hash.ToLowerInvariant() -cne $expectedHash) {
            throw "Refusing to overwrite $destination"
        }
    }
    $applyPlan.Add([pscustomobject]@{
        source = $source; destinationDirectory = $destinationDirectory
        destination = $destination; expectedHash = $expectedHash
    })
}
$mergedDoorLines = $null
if (@($profile.customDoorRows).Count) {
    if (-not $NwnRoot -or -not $NwnUserDirectory) { throw 'Apply requires NWN root and user directory for the pinned 2DA baseline.' }
    $erf = Get-SrnTool -Name erf; $cat = Join-Path (Split-Path -Parent $erf) 'nwn_resman_cat.exe'; $baseLines = @(& $cat --root $NwnRoot --userdirectory $NwnUserDirectory --no-ovr doortypes.2da); $sourceLines = @(Get-Content (Join-Path $rawRoot 'doortypes.2da') -Encoding Default)
    foreach ($row in @($profile.customDoorRows)) {
        $sourceLine = @($sourceLines | Where-Object { $_ -match "^\s*$($row.sourceRow)\s+" })
        $target = -1
        for ($i = 0; $i -lt $baseLines.Count; $i++) {
            if ($baseLines[$i] -match "^\s*$($row.targetRow)\s+") { $target = $i; break }
        }
        if ($sourceLine.Count -ne 1 -or $target -lt 0) { throw "Cannot merge doortypes row $($row.sourceRow)." }
        $sourceMatch = [regex]::Match($sourceLine[0], '^(\s*)\d+')
        if (-not $sourceMatch.Success) { throw "Cannot parse doortypes row $($row.sourceRow)." }
        $baseLines[$target] = "$($sourceMatch.Groups[1].Value)$($row.targetRow)$($sourceLine[0].Substring($sourceMatch.Length))"
    }
    $duplicateRows = @($baseLines | Where-Object { $_ -match '^\s*(\d+)\s+' } |
        ForEach-Object { [regex]::Match($_, '^\s*(\d+)').Groups[1].Value } |
        Group-Object | Where-Object Count -gt 1)
    if ($duplicateRows.Count) { throw "Merged doortypes.2da has duplicate row labels: $($duplicateRows.Name -join ', ')" }
    if ($resolvedStringRefRemaps.ContainsKey('doortypes.2da')) {
        $doorLines = [Collections.Generic.List[string]]::new()
        foreach ($line in $baseLines) { $doorLines.Add($line) }
        foreach ($remap in @($resolvedStringRefRemaps['doortypes.2da'])) {
            $occurrences = Replace-2daIntegerToken -Lines $doorLines -SourceValue $remap.sourceGameStrRef -TargetValue $remap.targetGameStrRef -ExpectedOccurrences $remap.expectedOccurrences -Resource 'doortypes.2da'
            $stringRefAllocations.Add([pscustomobject]@{
                table = 'doortypes.2da'; key = $remap.key; sourceGameStrRef = $remap.sourceGameStrRef
                targetGameStrRef = $remap.targetGameStrRef; occurrences = $occurrences; text = $remap.text
            })
        }
        $baseLines = @($doorLines)
        [void]$handledStringRefResources.Add('doortypes.2da')
    }
    $mergedDoorLines = $baseLines
}
$unhandledStringRefResources = @($resolvedStringRefRemaps.Keys | Where-Object { -not $handledStringRefResources.Contains($_) })
if ($unhandledStringRefResources.Count) {
    throw "String-ref remaps target resources that were not generated: $($unhandledStringRefResources -join ', ')."
}
foreach ($item in $applyPlan) {
    if (-not (Test-Path -LiteralPath $item.destination)) {
        New-Item -ItemType Directory -Force -Path $item.destinationDirectory | Out-Null
        Copy-Item -LiteralPath $item.source -Destination $item.destination
    }
}
if ($null -ne $mergedDoorLines) {
    New-Item -ItemType Directory -Force (Join-Path $repoRoot 'srn_2da') | Out-Null
    Write-2daLines -Path (Join-Path $repoRoot 'srn_2da\doortypes.2da') -Lines $mergedDoorLines
}
$docs = Join-Path $repoRoot 'docs\imports'; New-Item -ItemType Directory -Force $docs | Out-Null; Copy-Item $manifestPath (Join-Path $docs "$($profile.reportStem)-manifest.json") -Force; Copy-Item $reportPath (Join-Path $docs "$($profile.reportStem)-analysis.md") -Force
if ($globalAllocations.Count) {
    $allocationReport = [ordered]@{
        schemaVersion = 1; profile = $profile.name; profileSha256 = $profileSha256; sourceSha256 = $inputHash
        generatedAtUtc = [DateTime]::UtcNow.ToString('o'); allocations = @($globalAllocations)
    }
    $allocationPath = Join-Path $analysisRoot 'global-row-allocations.json'
    [IO.File]::WriteAllText($allocationPath, ($allocationReport | ConvertTo-Json -Depth 16) + "`n", [Text.UTF8Encoding]::new($false))
    Copy-Item $allocationPath (Join-Path $docs "$($profile.reportStem)-global-row-allocations.json") -Force
}
if ($stringRefAllocations.Count) {
    $stringRefReport = [ordered]@{
        schemaVersion = 1; profile = $profile.name; profileSha256 = $profileSha256; sourceSha256 = $inputHash
        generatedAtUtc = [DateTime]::UtcNow.ToString('o'); remaps = @($stringRefAllocations)
    }
    $stringRefPath = Join-Path $analysisRoot 'string-ref-remaps.json'
    Write-SrnJsonAtomic -Path $stringRefPath -Value $stringRefReport
    Write-SrnJsonAtomic -Path (Join-Path $docs "$($profile.reportStem)-string-ref-remaps.json") -Value $stringRefReport
}
if ($gffTransformResults.Count) {
    $gffReport = [ordered]@{
        schemaVersion = 1; profile = $profile.name; profileSha256 = $profileSha256; sourceSha256 = $inputHash
        generatedAtUtc = [DateTime]::UtcNow.ToString('o'); transforms = @($gffTransformResults)
    }
    Write-SrnJsonAtomic -Path (Join-Path $analysisRoot 'gff-transforms.json') -Value $gffReport
    Write-SrnJsonAtomic -Path (Join-Path $docs "$($profile.reportStem)-gff-transforms.json") -Value $gffReport
}
$registered = @($configuration.HakList)
foreach ($name in @($profile.registerPacks)) { if ($name -notin @($registered | ForEach-Object { $_.Name })) { $registered += [pscustomobject]@{ Name = $name; Path = "./$name/"; CompileModels = $false } } }
$configuration.HakList = $registered
if ($profile.PSObject.Properties.Name -contains 'expectedOverrides') {
    $overrides = @($configuration.ExpectedOverrides)
    foreach ($requested in @($profile.expectedOverrides)) {
        $resource = ([string]$requested.resource).ToLowerInvariant()
        $packs = @($requested.packs | ForEach-Object { [string]$_ } | Sort-Object -Unique)
        $existing = @($overrides | Where-Object { ([string]$_.Resource).ToLowerInvariant() -ceq $resource })
        if ($existing.Count -gt 1) { throw "Duplicate configured expected override '$resource'." }
        if ($existing.Count -eq 1) {
            $existingPacks = @($existing[0].Packs | ForEach-Object { [string]$_ } | Sort-Object -Unique)
            if (($existingPacks -join "`n") -cne ($packs -join "`n")) {
                throw "Configured expected override '$resource' differs from the reviewed import profile."
            }
        }
        else {
            $overrides += [pscustomobject][ordered]@{ Resource = $resource; Packs = $packs }
        }
    }
    $configuration.ExpectedOverrides = @($overrides | Sort-Object Resource)
}
[IO.File]::WriteAllText($configPath, ($configuration | ConvertTo-Json -Depth 32) + "`n", [Text.UTF8Encoding]::new($false)); Write-Host 'Apply complete.'
