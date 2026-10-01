[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'SrnHaks.Common.psm1') -Force
$repoRoot = Get-SrnRepositoryRoot
$realErf = Get-SrnTool -Name erf
$realGff = Get-SrnTool -Name gff
foreach ($name in @('gff','resman_cat','resman_grep')) {
    $tool = Get-SrnTool -Name $name
    $expected = 'nwn_' + $name + $(if ($IsWindows) { '.exe' } else { '' })
    if ([IO.Path]::GetFileName($tool) -cne $expected) { throw "Incorrect platform tool: $tool" }
}
$fixture = Join-Path $repoRoot ('.quarantine/item-import-tests/' + [Guid]::NewGuid().ToString('N'))
$fixtureTools = Join-Path $fixture 'tools'
$docs = Join-Path $fixture 'docs/imports'
$itemRaw = Join-Path $fixture '.quarantine/mdrnee_item/raw'
$utiRaw = Join-Path $fixture '.quarantine/mdrnee_item/blueprints/raw'
foreach ($directory in @($fixtureTools,$docs,$itemRaw,$utiRaw)) { New-Item -ItemType Directory -Path $directory -Force | Out-Null }
foreach ($name in @('Stage-ItemMatches.ps1','Analyze-ItemBlueprintErf.ps1')) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination $fixtureTools }
function Write-TestJson([string]$Path, $Value) { [IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 30) + "`n") }
Write-TestJson (Join-Path $fixtureTools 'test-tools.json') @{ erf=$realErf; gff=$realGff }
# The fixture resolver uses the real pinned binaries; its ERF path can be replaced to inject a failure.
[IO.File]::WriteAllText((Join-Path $fixtureTools 'SrnHaks.Common.psm1'), @'
function Get-SrnRepositoryRoot { Split-Path -Parent $PSScriptRoot }
function Get-SrnTool([string]$Name) {
    $tools = Get-Content (Join-Path $PSScriptRoot 'test-tools.json') -Raw | ConvertFrom-Json
    $tools.$Name
}
Export-ModuleMember -Function Get-SrnRepositoryRoot,Get-SrnTool
'@)
$sourceHash = 'A' * 64
$selected = @(); $blueprints = @(); $resources = @()
1..93 | ForEach-Object {
    $resref = 'item{0:000}' -f $_
    $name = "$resref.uti"
    [IO.File]::WriteAllText((Join-Path $utiRaw $name), "Fixture resource $_")
    $resources += @{name=$name; sha256=(Get-FileHash (Join-Path $utiRaw $name)).Hash}
    $selected += @{rank=$_; blueprintResRef=$resref; baseItem=24; matchTier=$(if ($_ -le 12) {'Exact identity'} else {'Visual stand-in'}); catalogName=$resref}
    $blueprints += @{resref=$resref; baseItem=24; itemClass='test'; modelType='0'; modelPart1=1; name=$resref; categoryPath='General'; propertyCount=0}
}
Write-TestJson (Join-Path $docs 'mdrnee_item-match-tier.json') @{sourceWorkbook=@{archiveSha256=$sourceHash; sha256=$sourceHash}; tiers=@(@{blueprints=$selected})}
$blueprintAnalysisPath = Join-Path $docs 'mdrnee_item-blueprint-analysis.json'
Write-TestJson $blueprintAnalysisPath @{sourceErf=@{sha256=$sourceHash}; itemHak=@{sourceHakSha256=$sourceHash}; blueprints=$blueprints}
[IO.File]::WriteAllText((Join-Path $itemRaw 'itest_001.tga'), 'Fixture icon')
Write-TestJson (Join-Path $docs 'mdrnee_item-manifest.json') @{sourceSha256=$sourceHash; resources=@(@{name='itest_001.tga'; sha256=(Get-FileHash (Join-Path $itemRaw 'itest_001.tga')).Hash})}
Write-TestJson (Join-Path $docs 'mdrnee_item-blueprint-erf-manifest.json') @{sourceSha256=$sourceHash; resources=$resources}
Write-TestJson $blueprintAnalysisPath @{sourceErf=@{sha256=('B' * 64)}; itemHak=@{sourceHakSha256=$sourceHash}; blueprints=$blueprints}
try {
    & (Join-Path $fixtureTools 'Stage-ItemMatches.ps1') -OutputRelativePath mismatched-erf
    throw 'Mismatched blueprint analysis unexpectedly accepted.'
} catch { if ($_.Exception.Message -ne 'Source manifest mismatch.') {throw} }
if (Test-Path (Join-Path $fixture '.quarantine/mismatched-erf')) {throw 'Mismatched analysis created output.'}
Write-TestJson $blueprintAnalysisPath @{sourceErf=@{sha256=$sourceHash}; itemHak=@{sourceHakSha256=$sourceHash}; blueprints=$blueprints}
$failingErf = Join-Path $fixtureTools 'fail-erf.ps1'
[IO.File]::WriteAllText($failingErf, "throw 'Injected packing failure'")
Write-TestJson (Join-Path $fixtureTools 'test-tools.json') @{erf=$failingErf; gff=$realGff}
$destination = Join-Path $fixture '.quarantine/selected'
try {
    & (Join-Path $fixtureTools 'Stage-ItemMatches.ps1') -OutputRelativePath selected
    throw 'Expected packing failure was not raised.'
} catch { if ($_.Exception.Message -ne 'Injected packing failure') {throw} }
if ((Test-Path $destination) -or @(Get-ChildItem (Join-Path $fixture '.quarantine') -Directory -Force -Filter '.item-staging-*').Count) { throw 'Failed run left partial staging output.' }
Write-TestJson (Join-Path $fixtureTools 'test-tools.json') @{erf=$realErf; gff=$realGff}
& (Join-Path $fixtureTools 'Stage-ItemMatches.ps1') -OutputRelativePath selected
if (@(Get-ChildItem (Join-Path $destination 'blueprints') -File).Count -ne 93) { throw 'Retry did not publish all 93 blueprints.' }
$savedHash = (Get-FileHash (Join-Path $destination 'migration-manifest.json')).Hash
try {
    & (Join-Path $fixtureTools 'Stage-ItemMatches.ps1') -OutputRelativePath selected
    throw 'Existing output was unexpectedly replaced.'
} catch { if ($_.Exception.Message -notlike 'Output already exists;*') {throw} }
if ((Get-FileHash (Join-Path $destination 'migration-manifest.json')).Hash -ne $savedHash) { throw 'Existing output changed.' }
$escape = if ($IsWindows) { '../outside' } else { '../.QUARANTINE/selected' }
try {
    & (Join-Path $fixtureTools 'Stage-ItemMatches.ps1') -OutputRelativePath $escape
    throw 'Quarantine escape unexpectedly succeeded.'
} catch { if ($_.Exception.Message -ne 'Path escapes quarantine.') {throw} }

# A real two-resource ERF with duplicate TemplateResRefs and one unmapped palette/base row.
$anomalyRoot = New-Item -ItemType Directory -Path (Join-Path $fixture 'anomaly')
foreach ($index in 1..2) {
    $record = @{
        __data_type='UTI '
        TemplateResRef=@{type='resref'; value='duplicate'}
        PaletteID=@{type='byte'; value=$(if ($index -eq 1) {1} else {250})}
        BaseItem=@{type='int'; value=$(if ($index -eq 1) {24} else {999})}
    }
    $json = Join-Path $anomalyRoot.FullName "anomaly$index.json"
    Write-TestJson $json $record
    & $realGff -i $json -l json -o (Join-Path $anomalyRoot.FullName "anomaly$index.uti") -k gff
    if ($LASTEXITCODE -ne 0) {throw 'Fixture GFF encoding failed.'}
}
$anomalyErf = Join-Path $fixture 'anomaly.erf'
& $realErf -c -f $anomalyErf -e ERF @(Get-ChildItem $anomalyRoot.FullName -Filter '*.uti' -File | Sort-Object Name | ForEach-Object FullName)
if ($LASTEXITCODE -ne 0) {throw 'Fixture ERF packing failed.'}
[IO.File]::WriteAllText((Join-Path $itemRaw 'baseitems.2da'), "2DA V2.0`n`nlabel ItemClass ModelType`n24 misc test 0`n")
$itemAnalysisRoot = New-Item -ItemType Directory -Path (Join-Path $fixture '.quarantine/mdrnee_item/analysis') -Force
Write-TestJson (Join-Path $itemAnalysisRoot.FullName 'manifest.json') @{sourceSha256=$sourceHash; resources=@(@{name='baseitems.2da'; sha256=(Get-FileHash (Join-Path $itemRaw 'baseitems.2da')).Hash})}
$categoryMapPath = Join-Path $docs 'mdrnee_item-category-map.json'
$categoryMap = @{source='itempal.itp'; sourceHakSha256=$sourceHash; leafCategories=@(@{id=1; name='General'; path='General'; topLevel='General'})}
Write-TestJson $categoryMapPath $categoryMap

# Linked workspaces, their ancestors, and deletion-target children must be rejected before clearing data.
$protected = New-Item -ItemType Directory -Path (Join-Path $fixture 'protected-data')
foreach ($directory in @('raw','analysis','child/raw','child/analysis')) {
    $sentinelDirectory = New-Item -ItemType Directory -Path (Join-Path $protected.FullName $directory) -Force
    [IO.File]::WriteAllText((Join-Path $sentinelDirectory.FullName 'keep.txt'), 'Preserve this fixture data')
}
$sentinels = @(Get-ChildItem $protected.FullName -Recurse -File | ForEach-Object FullName)
$linkType = if ($IsWindows) {'Junction'} else {'SymbolicLink'}
New-Item -ItemType $linkType -Path (Join-Path $fixture '.quarantine/linked') -Target $protected.FullName | Out-Null
$linkedRawWorkspace = New-Item -ItemType Directory -Path (Join-Path $fixture '.quarantine/linked-raw')
New-Item -ItemType $linkType -Path (Join-Path $linkedRawWorkspace.FullName 'raw') -Target (Join-Path $protected.FullName 'raw') | Out-Null
foreach ($case in @(@{output='linked'; item='mdrnee_item'}, @{output='linked/child'; item='mdrnee_item'}, @{output='linked-raw'; item='mdrnee_item'}, @{output='item-link-test'; item='linked'})) {
    try {
        & (Join-Path $fixtureTools 'Analyze-ItemBlueprintErf.ps1') -InputErf $anomalyErf -OutputRelativePath $case.output -ItemHakOutputRelativePath $case.item
        throw 'Linked analysis workspace unexpectedly accepted.'
    } catch { if ($_.Exception.Message -notlike 'Reparse point not allowed:*') {throw} }
    foreach ($sentinel in $sentinels) { if (-not (Test-Path -LiteralPath $sentinel)) {throw "Linked workspace removed protected data: $sentinel"} }
}

# Bad source metadata must leave an existing analysis untouched.
$preservedOutput = Join-Path $fixture '.quarantine/category-mismatch'
foreach ($directory in @('raw','analysis')) {
    $sentinelDirectory = New-Item -ItemType Directory -Path (Join-Path $preservedOutput $directory) -Force
    [IO.File]::WriteAllText((Join-Path $sentinelDirectory.FullName 'keep.txt'), 'Preserve previous run')
}
$categoryMap.sourceHakSha256 = 'B' * 64
Write-TestJson $categoryMapPath $categoryMap
try {
    & (Join-Path $fixtureTools 'Analyze-ItemBlueprintErf.ps1') -InputErf $anomalyErf -OutputRelativePath category-mismatch
    throw 'Mismatched category map unexpectedly accepted.'
} catch { if ($_.Exception.Message -ne 'Category map source HAK SHA-256 does not match the item HAK analysis.') {throw} }
$categoryMap.sourceHakSha256 = $sourceHash
Write-TestJson $categoryMapPath $categoryMap
[IO.File]::AppendAllText((Join-Path $itemRaw 'baseitems.2da'), "999 changed other 0`n")
try {
    & (Join-Path $fixtureTools 'Analyze-ItemBlueprintErf.ps1') -InputErf $anomalyErf -OutputRelativePath category-mismatch
    throw 'Changed baseitems bytes unexpectedly accepted.'
} catch { if ($_.Exception.Message -ne 'baseitems.2da does not match the item HAK analysis manifest.') {throw} }
[IO.File]::WriteAllText((Join-Path $itemRaw 'baseitems.2da'), "2DA V2.0`n`nlabel ItemClass ModelType`n24 misc test 0`n")
foreach ($directory in @('raw','analysis')) { if (-not (Test-Path (Join-Path $preservedOutput "$directory/keep.txt"))) {throw 'Source mismatch cleared existing output.'} }
$nestedInput = Join-Path $preservedOutput 'raw/source.erf'
Copy-Item -LiteralPath $anomalyErf -Destination $nestedInput
try {
    & (Join-Path $fixtureTools 'Analyze-ItemBlueprintErf.ps1') -InputErf $nestedInput -OutputRelativePath category-mismatch
    throw 'Input inside the deletion target unexpectedly accepted.'
} catch { if ($_.Exception.Message -ne 'InputErf is inside an output directory that would be cleared.') {throw} }
if (-not (Test-Path -LiteralPath $nestedInput)) {throw 'Analyzer deleted its own input.'}
& (Join-Path $fixtureTools 'Analyze-ItemBlueprintErf.ps1') -InputErf $anomalyErf -OutputRelativePath anomalies -ExpectedResourceCount 2
$report = Get-Content (Join-Path $fixture '.quarantine/anomalies/analysis/blueprint-report.md') -Raw
foreach ($claim in @('**1** distinct ResRefs across **2** blueprints; **1** repeated occurrences.', '**1 of 2** Palette IDs', '**1** are unmapped.', '**1 of 2** BaseItem values', '**1** are missing.')) {
    if (-not $report.Contains($claim)) { throw "Missing measured integrity claim: $claim" }
}
Write-Host 'Item import regression checks passed: platform tools, failed-run cleanup/retry, output preservation, quarantine containment, linked-directory rejection, source provenance, and measured anomaly reporting.'
