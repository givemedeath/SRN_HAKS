[CmdletBinding()]
param(
    [string]$OutputRelativePath = 'mdrnee_item/migration',
    [string]$ItemSourceRelativePath = 'mdrnee_item/raw',
    [string]$BlueprintSourceRelativePath = 'mdrnee_item/blueprints/raw'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'SrnHaks.Common.psm1') -Force
$root = Get-SrnRepositoryRoot
$quarantine = [IO.Path]::GetFullPath((Join-Path $root '.quarantine'))
function Resolve-LocalPath([string]$Relative) {
    if ([string]::IsNullOrWhiteSpace($Relative) -or [IO.Path]::IsPathRooted($Relative)) { throw 'Expected a quarantine-relative path.' }
    $path = [IO.Path]::GetFullPath((Join-Path $quarantine $Relative))
    $comparison = if ($IsWindows) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
    if (-not $path.StartsWith($quarantine + [IO.Path]::DirectorySeparatorChar, $comparison)) { throw 'Path escapes quarantine.' }
    $current = $path
    while ($current -and $current.Length -ge $quarantine.Length) {
        if ((Test-Path -LiteralPath $current) -and ((Get-Item -LiteralPath $current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Reparse point not allowed: $current" }
        $current = Split-Path $current -Parent
    }
    $path
}
$output = Resolve-LocalPath $OutputRelativePath
$items = Resolve-LocalPath $ItemSourceRelativePath
$blueprints = Resolve-LocalPath $BlueprintSourceRelativePath
$comparison = if ($IsWindows) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
foreach ($source in @($items, $blueprints)) {
    if ($output.Equals($source, $comparison) -or
        $output.StartsWith($source + [IO.Path]::DirectorySeparatorChar, $comparison) -or
        $source.StartsWith($output + [IO.Path]::DirectorySeparatorChar, $comparison)) {
        throw 'Staging output must not overlap either source directory.'
    }
}
if (Test-Path -LiteralPath $output) { throw 'Output already exists; choose a new OutputRelativePath to preserve previous runs.' }
$selection = Get-Content (Join-Path $root 'docs/imports/mdrnee_item-match-tier.json') -Raw | ConvertFrom-Json
$analysis = Get-Content (Join-Path $root 'docs/imports/mdrnee_item-blueprint-analysis.json') -Raw | ConvertFrom-Json
$itemManifest = Get-Content (Join-Path $root 'docs/imports/mdrnee_item-manifest.json') -Raw | ConvertFrom-Json
$erfManifest = Get-Content (Join-Path $root 'docs/imports/mdrnee_item-blueprint-erf-manifest.json') -Raw | ConvertFrom-Json
if ($selection.sourceWorkbook.archiveSha256 -ne $erfManifest.sourceSha256 -or
    $analysis.sourceErf.sha256 -ne $erfManifest.sourceSha256 -or
    $analysis.itemHak.sourceHakSha256 -ne $itemManifest.sourceSha256) { throw 'Source manifest mismatch.' }
$selected = @($selection.tiers.blueprints | Sort-Object rank)
if ($selected.Count -ne 93 -or @($selected.blueprintResRef | Sort-Object -Unique).Count -ne 93) { throw 'Expected 93 unique selected blueprints.' }
if (@($selected | Where-Object matchTier -NotIn @('Exact identity','Visual stand-in')).Count) { throw 'Unexpected match tier.' }
$utiIndex = @{}; foreach ($b in $analysis.blueprints) { $utiIndex[$b.resref] = $b }
$resourceIndex = @{}; foreach ($r in $itemManifest.resources) { $resourceIndex[$r.name] = $r }
$erfIndex = @{}; foreach ($r in $erfManifest.resources) { $erfIndex[$r.name] = $r }
$assets = @{}; $records = [Collections.Generic.List[object]]::new()
function Add-Asset([string]$Name, [string]$Owner, [string]$Reason) {
    $Name = $Name.ToLowerInvariant()
    if (-not $resourceIndex.ContainsKey($Name)) { return $false }
    if (-not $assets.ContainsKey($Name)) { $assets[$Name] = [ordered]@{ name=$Name; sha256=$resourceIndex[$Name].sha256; owners=[Collections.Generic.HashSet[string]]::new(); reasons=[Collections.Generic.HashSet[string]]::new() } }
    [void]$assets[$Name].owners.Add($Owner); [void]$assets[$Name].reasons.Add($Reason)
    return $true
}
function Add-Image([string]$Stem, [string]$Owner, [string]$Reason) {
    $found = $false
    foreach ($extension in @('dds','tga','plt','txi')) { if (Add-Asset "$Stem.$extension" $Owner $Reason) { $found = $true } }
    return $found
}
foreach ($candidate in $selected) {
    $b = $utiIndex[$candidate.blueprintResRef]
    if (-not $b -or $b.baseItem -ne $candidate.baseItem) { throw "Blueprint join mismatch: $($candidate.blueprintResRef)" }
    $unresolved = [Collections.Generic.List[string]]::new()
    $prefix = $b.itemClass.ToLowerInvariant()
    if ($b.modelType -eq '2' -and $prefix -ne 'wamar') {
        foreach ($part in @(@('b',$b.modelPart1),@('m',$b.modelPart2),@('t',$b.modelPart3))) {
            if ($null -eq $part[1]) { continue }
            $stem = '{0}_{1}_{2:000}' -f $prefix,$part[0],[int]$part[1]
            if (-not (Add-Asset "$stem.mdl" $b.resref 'Multipart appearance')) { $unresolved.Add("Model outside item HAK (base/other HAK check needed): $stem") }
            [void](Add-Image "i$stem" $b.resref 'Multipart icon candidate')
        }
    } elseif ($b.modelType -eq '0') {
        $stem = '{0}_{1:000}' -f $prefix,[int]$b.modelPart1
        if (-not (Add-Image "i$stem" $b.resref 'Inventory appearance')) { $unresolved.Add("Icon outside item HAK (base/other HAK check needed): i$stem") }
        if (-not (Add-Asset "$stem.mdl" $b.resref 'Matching simple-model candidate')) {
            $unresolved.Add("Matching simple-model candidate outside item HAK: $stem (check declared DefaultModel and EE/shared assets; this candidate may be optional)")
        }
    } else {
        $unresolved.Add('Special appearance mapping requires inspection: armor, helmet, or ammunition')
    }
    # Traverse only observed ASCII model references. Unresolved references remain explicit.
    $processed = [Collections.Generic.HashSet[string]]::new()
    do {
        $pending = @($assets.Keys | Where-Object { $_ -like '*.mdl' -and $assets[$_].owners.Contains($b.resref) -and -not $processed.Contains($_) })
        foreach ($name in $pending) {
            [void]$processed.Add($name)
            $model = Get-Content -LiteralPath (Join-Path $items $name) -Raw
            foreach ($match in [regex]::Matches($model,'(?im)^\s*(?:bitmap|texture\d*)\s+(\S+)')) {
                $texture = $match.Groups[1].Value.ToLowerInvariant()
                if ($texture -notin @('null','****') -and -not (Add-Image $texture $b.resref "Texture referenced by $name")) { $unresolved.Add("Texture outside item HAK: $texture (from $name)") }
            }
            foreach ($match in [regex]::Matches($model,'(?im)^\s*setsupermodel\s+\S+\s+(\S+)')) {
                $super = $match.Groups[1].Value.ToLowerInvariant()
                if ($super -ne 'null' -and -not (Add-Asset "$super.mdl" $b.resref "Supermodel referenced by $name")) { $unresolved.Add("Supermodel outside item HAK: $super") }
            }
        }
    } while ($pending.Count)
    $records.Add([pscustomobject]@{ resref=$b.resref; name=$b.name; category=$b.categoryPath; matchTier=$candidate.matchTier; catalogName=$candidate.catalogName; baseItem=$b.baseItem; itemClass=$b.itemClass; modelType=$b.modelType; propertyCount=$b.propertyCount; unresolved=@($unresolved | Sort-Object -Unique); status='staged-original-not-runtime-ready' })
}
# Verify all selected source bytes before creating any output.
foreach ($record in $records) {
    $name = "$($record.resref).uti"
    if (-not $erfIndex.ContainsKey($name) -or (Get-FileHash -LiteralPath (Join-Path $blueprints $name)).Hash -ne $erfIndex[$name].sha256) { throw "Blueprint hash mismatch: $name" }
}
foreach ($name in $assets.Keys) { if ((Get-FileHash -LiteralPath (Join-Path $items $name)).Hash -ne $assets[$name].sha256) { throw "Asset hash mismatch: $name" } }
$destination = $output
$parent = Split-Path $destination -Parent
New-Item -ItemType Directory -Path $parent -Force | Out-Null
$output = Resolve-LocalPath ([IO.Path]::GetRelativePath($quarantine, (Join-Path $parent ('.item-staging-' + [Guid]::NewGuid().ToString('N')))))
try {
$utiOut = New-Item -ItemType Directory -Path (Join-Path $output 'blueprints') -Force
$assetOut = New-Item -ItemType Directory -Path (Join-Path $output 'srn_item-candidate') -Force
foreach ($record in $records) { Copy-Item -LiteralPath (Join-Path $blueprints "$($record.resref).uti") -Destination $utiOut.FullName }
foreach ($name in $assets.Keys) { Copy-Item -LiteralPath (Join-Path $items $name) -Destination $assetOut.FullName }
$assetRecords = @($assets.Keys | Sort-Object | ForEach-Object { $a=$assets[$_]; [ordered]@{ name=$_; sha256=$a.sha256; owners=@($a.owners | Sort-Object); reasons=@($a.reasons | Sort-Object) } })
$manifest = [ordered]@{ schemaVersion=1; status='candidate-staging-only'; sourceErfSha256=$erfManifest.sourceSha256; sourceHakSha256=$itemManifest.sourceSha256; sourceWorkbookSha256=$selection.sourceWorkbook.sha256; blueprintCount=$records.Count; assetCount=$assets.Count; blueprints=@($records.ToArray()); assets=$assetRecords }
[IO.File]::WriteAllText((Join-Path $output 'migration-manifest.json'), ($manifest | ConvertTo-Json -Depth 20) + "`n")
$erf = Get-SrnTool -Name erf
$packed = Join-Path $output 'srn_item_matches_source.erf'
& $erf -c -f $packed -e ERF @(Get-ChildItem $utiOut.FullName -File | Sort-Object Name | ForEach-Object FullName)
if ($LASTEXITCODE -ne 0) { throw 'Failed to pack selected blueprint ERF.' }
# Normalize ERF build-date fields so identical inputs produce identical archives.
$archiveBytes = [IO.File]::ReadAllBytes($packed)
if ([Text.Encoding]::ASCII.GetString($archiveBytes,0,8) -ne 'ERF V1.0') { throw 'Unexpected ERF header.' }
[Array]::Clear($archiveBytes,32,8)
[IO.File]::WriteAllBytes($packed,$archiveBytes)
$roundtrip = New-Item -ItemType Directory -Path (Join-Path $output 'roundtrip')
Push-Location $roundtrip.FullName
try { & $erf -x -f $packed | Out-Null; if ($LASTEXITCODE -ne 0) { throw 'ERF verification extraction failed.' } } finally { Pop-Location }
if (@(Get-ChildItem $roundtrip.FullName -File).Count -ne $records.Count) { throw 'ERF resource count mismatch.' }
foreach ($record in $records) { $name="$($record.resref).uti"; if ((Get-FileHash (Join-Path $roundtrip.FullName $name)).Hash -ne $erfIndex[$name].sha256) { throw "ERF roundtrip mismatch: $name" } }
$lines = [Collections.Generic.List[string]]::new()
$lines.Add('# MDRNEE selected-item migration — first stage')
$lines.Add('')
$lines.Add("Staged $($records.Count) unchanged blueprints (12 Exact identity; 81 Visual stand-in) and $($assets.Count) candidate assets. Source and ERF roundtrip hashes verified. No production pack or global table was changed.")
$lines.Add('')
$lines.Add('The ERF preserves source gameplay, tags, palette IDs, and BaseItem IDs. It is an archival migration input, **not ready for import into an SRN module**. Candidate assets are a conservative first pass, not a complete runtime closure. Texture formats have not yet been consolidated; collisions have not yet been resolved.')
$lines.Add('')
$lines.Add('## Remaining migration gates')
$lines.Add('')
$lines.Add('- Reconcile the selected BaseItem rows against the pinned EE baseline and allocate custom rows; migrate their TLK references with deduplication.')
$lines.Add('- Review legacy properties, local variables, descriptions and palette IDs before writing SRN-ready blueprints. Match tier describes appearance suitability, not gameplay compatibility.')
$lines.Add('- Resolve external assets, special armor/helmet/ammunition mappings, TXI dependencies, and shared-pack collisions before registering a pack.')
$lines.Add('- Build the resulting HAK/ERF, verify inventories and test appearances in the toolset and game.')
foreach ($group in ($records | Group-Object category | Sort-Object Name)) {
    $lines.Add(''); $lines.Add("## $($group.Name)"); $lines.Add('')
    $lines.Add('| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |'); $lines.Add('|---|---|---|---:|---|')
    foreach ($r in $group.Group) { $notes= if ($r.unresolved.Count) { $r.unresolved -join '; ' } else { 'Direct appearance candidates found; table/property/collision review still required' }; $lines.Add("| $($r.name) ($($r.resref)) | $($r.matchTier) | $($r.catalogName) | $($r.baseItem) | $notes |".Replace('| |','| |')) }
}
[IO.File]::WriteAllText((Join-Path $output 'migration-report.md'), ($lines -join "`n") + "`n")
[IO.Directory]::Move($output, $destination)
}
finally {
    # This is the generated staging directory, never the requested destination.
    if (Test-Path -LiteralPath $output) { Remove-Item -LiteralPath $output -Recurse -Force }
}
Write-Output "Verified candidate staging: $destination ($($records.Count) blueprints, $($assets.Count) assets)."
