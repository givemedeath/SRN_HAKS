[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'SrnHaks.Common.psm1') -Force
$repoRoot = Get-SrnRepositoryRoot
$realErf = Get-SrnTool -Name erf
$realGff = Get-SrnTool -Name gff
$realCat = Get-SrnTool -Name resman_cat
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
foreach ($name in @('Stage-ItemMatches.ps1','Analyze-ItemBlueprintErf.ps1','Analyze-ItemHak.ps1','Import-Hak.ps1')) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination $fixtureTools }
function Write-TestJson([string]$Path, $Value) { [IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 30) + "`n") }
Write-TestJson (Join-Path $fixtureTools 'test-tools.json') @{ erf=$realErf; gff=$realGff }
# The fixture resolver uses the real pinned binaries; its ERF path can be replaced to inject a failure.
$fixtureCommon = Join-Path $fixtureTools 'SrnHaks.Common.psm1'
[IO.File]::WriteAllText($fixtureCommon, [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'SrnHaks.Common.psm1')) + "`n" + @'
function Get-SrnRepositoryRoot { Split-Path -Parent $PSScriptRoot }
function Get-SrnTool([string]$Name) {
    $tools = Get-Content (Join-Path $PSScriptRoot 'test-tools.json') -Raw | ConvertFrom-Json
    $tools.$Name
}
Export-ModuleMember -Function Get-SrnRepositoryRoot,Get-SrnTool,Resolve-SrnQuarantinePath,Publish-SrnDirectorySet
'@)
$sourceHash = 'A' * 64
foreach ($overlap in @('mdrnee_item/raw/migration','mdrnee_item/blueprints/raw/migration')) {
    try {
        & (Join-Path $fixtureTools 'Stage-ItemMatches.ps1') -OutputRelativePath $overlap
        throw 'Source-nested staging output unexpectedly accepted.'
    } catch { if ($_.Exception.Message -ne 'Staging output must not overlap either source directory.') {throw} }
    if (Test-Path (Join-Path $fixture ".quarantine/$overlap")) {throw 'Overlap rejection contaminated source extraction.'}
}
$selected = @(); $blueprints = @(); $resources = @()
1..93 | ForEach-Object {
    $resref = 'item{0:000}' -f $_
    $name = "$resref.uti"
    [IO.File]::WriteAllText((Join-Path $utiRaw $name), "Fixture resource $_")
    $resources += @{name=$name; sha256=(Get-FileHash (Join-Path $utiRaw $name)).Hash}
    $selected += @{rank=$_; blueprintResRef=$resref; baseItem=24; matchTier=$(if ($_ -le 13) {'Exact identity'} else {'Visual stand-in'}); catalogName=$resref}
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
if ((Get-Content (Join-Path $destination 'migration-report.md') -Raw) -notmatch '13 Exact identity; 80 Visual stand-in') { throw 'Migration report tier counts do not match the selection.' }
$stagedManifest = Get-Content (Join-Path $destination 'migration-manifest.json') -Raw | ConvertFrom-Json
if (-not (($stagedManifest | ConvertTo-Json -Depth 30) -match 'Matching simple-model candidate outside item HAK: test_001')) { throw 'Missing simple-model candidate was not reported.' }
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

# A failed repeat must preserve the complete previous analysis, even after decoding or late validation.
$anomalyWorkspace = Join-Path $fixture '.quarantine/anomalies'
[IO.File]::WriteAllText((Join-Path $anomalyWorkspace 'notes.txt'), 'Keep workspace notes')
$snapshot = @{}
foreach ($file in Get-ChildItem $anomalyWorkspace -Recurse -File) { $snapshot[[IO.Path]::GetRelativePath($anomalyWorkspace,$file.FullName)] = (Get-FileHash $file.FullName).Hash }
function Assert-PreviousAnalysis {
    $files = @(Get-ChildItem $anomalyWorkspace -Recurse -File)
    if ($files.Count -ne $snapshot.Count) {throw 'Failed repeat changed the prior inventory.'}
    foreach ($file in $files) {
        $relative = [IO.Path]::GetRelativePath($anomalyWorkspace,$file.FullName)
        if (-not $snapshot.ContainsKey($relative) -or (Get-FileHash $file.FullName).Hash -ne $snapshot[$relative]) {throw "Failed repeat changed prior data: $relative"}
    }
    if (@(Get-ChildItem (Join-Path $fixture '.quarantine') -Directory -Force -Filter '.blueprint-build-*').Count) {throw 'Failed repeat left temporary analysis output.'}
}
Write-TestJson (Join-Path $fixtureTools 'test-tools.json') @{erf=$failingErf; gff=$realGff}
try {
    & (Join-Path $fixtureTools 'Analyze-ItemBlueprintErf.ps1') -InputErf $anomalyErf -OutputRelativePath anomalies
    throw 'Expected repeat extraction failure.'
} catch { if ($_.Exception.Message -ne 'Injected packing failure') {throw} }
Assert-PreviousAnalysis
$failingGff = Join-Path $fixtureTools 'fail-gff.ps1'
[IO.File]::WriteAllText($failingGff, "throw 'Injected decoding failure'")
Write-TestJson (Join-Path $fixtureTools 'test-tools.json') @{erf=$realErf; gff=$failingGff}
try {
    & (Join-Path $fixtureTools 'Analyze-ItemBlueprintErf.ps1') -InputErf $anomalyErf -OutputRelativePath anomalies
    throw 'Expected repeat decoding failure.'
} catch { if ($_.Exception.Message -ne 'Injected decoding failure') {throw} }
Assert-PreviousAnalysis
Write-TestJson (Join-Path $fixtureTools 'test-tools.json') @{erf=$realErf; gff=$realGff}
$badMatchTier = Join-Path $fixture 'bad-match-tier.json'
Write-TestJson $badMatchTier @{sourceWorkbook=@{archiveSha256=('B' * 64)}}
try {
    & (Join-Path $fixtureTools 'Analyze-ItemBlueprintErf.ps1') -InputErf $anomalyErf -OutputRelativePath anomalies -MatchTierPath $badMatchTier
    throw 'Expected late match-tier failure.'
} catch { if ($_.Exception.Message -ne 'Match Tier source archive SHA-256 does not match InputErf.') {throw} }
Assert-PreviousAnalysis

# Inject a failure after the new raw directory is published to exercise the actual rollback.
$fixtureAnalyzer = Join-Path $fixtureTools 'Analyze-ItemBlueprintErf.ps1'
$analyzerCode = [IO.File]::ReadAllText($fixtureCommon)
$moveStatement = '[IO.Directory]::Move($target.source, $target.destination)'
if (-not $analyzerCode.Contains($moveStatement)) {throw 'Publication failure injection point is missing.'}
$injectedCode = $analyzerCode.Replace($moveStatement, "if (`$target.name -eq 'analysis') { throw 'Injected publication failure' }; " + $moveStatement)
[IO.File]::WriteAllText($fixtureCommon,$injectedCode)
try {
    & $fixtureAnalyzer -InputErf $anomalyErf -OutputRelativePath anomalies
    throw 'Expected publication failure was not raised.'
} catch { if ($_.Exception.Message -ne 'Injected publication failure') {throw} }
finally { [IO.File]::WriteAllText($fixtureCommon,$analyzerCode) }
Assert-PreviousAnalysis
& (Join-Path $fixtureTools 'Analyze-ItemBlueprintErf.ps1') -InputErf $anomalyErf -OutputRelativePath anomalies -ExpectedResourceCount 2
Assert-PreviousAnalysis

# Fresh nested HAK analysis must resolve the baseline helper through the platform manifest.
$hakSource = New-Item -ItemType Directory -Path (Join-Path $fixture 'hak-source')
$modelText = "newmodel test`nclassification item`nsetsupermodel test null`n"
$modelPath = Join-Path $hakSource.FullName 'test.mdl'
[IO.File]::WriteAllText($modelPath,$modelText)
$hakPath = Join-Path $fixture 'fixture.hak'
& $realErf -c -f $hakPath -e HAK $modelPath
if ($LASTEXITCODE -ne 0) {throw 'Fixture HAK packing failed.'}
$profile = Get-Content (Join-Path $PSScriptRoot 'import-profiles/mdrnee_item.json') -Raw | ConvertFrom-Json
$profile.expectedSha256 = (Get-FileHash $hakPath).Hash
$profile.expectedResourceCount = 1
$profilePath = Join-Path $fixture 'hak-profile.json'
Write-TestJson $profilePath $profile
$baselineSpy = Join-Path $fixtureTools 'baseline-spy.ps1'
[IO.File]::WriteAllText($baselineSpy,@'
param([Parameter(ValueFromRemainingArguments)]$Arguments)
[IO.File]::AppendAllText((Join-Path $PSScriptRoot 'baseline-calls.txt'), "call`n")
Write-Output 'base.mdl 00000000000000000000000000000000'
$global:LASTEXITCODE = 0
'@)
Write-TestJson (Join-Path $fixtureTools 'test-tools.json') @{erf=$realErf; gff=$realGff; resman_cat=$realCat; resman_grep=$baselineSpy}
& (Join-Path $fixtureTools 'Analyze-ItemHak.ps1') -InputHak $hakPath -OutputRelativePath hak -ProfilePath $profilePath -NwnRoot fixture-game -NwnUserDirectory fixture-user
if (@(Get-Content (Join-Path $fixtureTools 'baseline-calls.txt')).Count -ne 2) {throw 'Nested and supplemental baseline queries did not use the resolved helper.'}
$hakWorkspace = Join-Path $fixture '.quarantine/hak'
$nestedHak = Join-Path $hakWorkspace 'raw/source.hak'
Copy-Item -LiteralPath $hakPath -Destination $nestedHak
try {
    & (Join-Path $fixtureTools 'Analyze-ItemHak.ps1') -InputHak $nestedHak -OutputRelativePath hak -ProfilePath $profilePath
    throw 'Input HAK beneath the replacement target unexpectedly accepted.'
} catch { if ($_.Exception.Message -ne 'InputHak must be outside the output raw and analysis directories.') {throw} }
if ((Get-FileHash $nestedHak).Hash -ne $profile.expectedSha256) {throw 'Overlap rejection modified the input archive.'}
[IO.File]::Delete($nestedHak)
$rawModel = Join-Path $hakWorkspace 'raw/test.mdl'
$hakSnapshot = @{}
foreach ($file in Get-ChildItem (Join-Path $hakWorkspace 'analysis') -Recurse -File) { $hakSnapshot[$file.FullName] = (Get-FileHash $file.FullName).Hash }
function Assert-HakReportsPreserved {
    foreach ($path in $hakSnapshot.Keys) { if ((Get-FileHash $path).Hash -ne $hakSnapshot[$path]) {throw "Rejected raw input modified a report: $path"} }
}
[IO.File]::WriteAllText($rawModel,$modelText.Replace('item','Item'))
try {
    & (Join-Path $fixtureTools 'Analyze-ItemHak.ps1') -InputHak $hakPath -OutputRelativePath hak -SkipImport
    throw 'Modified raw model unexpectedly accepted.'
} catch { if ($_.Exception.Message -ne 'Raw resource hash/size mismatch: test.mdl') {throw} }
Assert-HakReportsPreserved
[IO.File]::WriteAllText($rawModel,$modelText)
$rawBackup = Join-Path $fixture 'saved-model.mdl'
[IO.File]::Move($rawModel,$rawBackup)
try {
    & (Join-Path $fixtureTools 'Analyze-ItemHak.ps1') -InputHak $hakPath -OutputRelativePath hak -SkipImport
    throw 'Missing raw model unexpectedly accepted.'
} catch { if ($_.Exception.Message -ne 'Raw inventory does not match the analysis manifest.') {throw} }
Assert-HakReportsPreserved
[IO.File]::Move($rawBackup,$rawModel)
$extra = Join-Path $hakWorkspace 'raw/.extra'
[IO.File]::WriteAllText($extra,'Stale resource')
try {
    & (Join-Path $fixtureTools 'Analyze-ItemHak.ps1') -InputHak $hakPath -OutputRelativePath hak -SkipImport
    throw 'Extra raw resource unexpectedly accepted.'
} catch { if ($_.Exception.Message -ne 'Raw inventory does not match the analysis manifest.') {throw} }
Assert-HakReportsPreserved
[IO.File]::Delete($extra)
# Both supplemental and nested baseline failures must leave the prior extraction/reports intact.
$baselineCode = [IO.File]::ReadAllText($baselineSpy)
[IO.File]::WriteAllText($baselineSpy,$baselineCode.Replace('$global:LASTEXITCODE = 0','$global:LASTEXITCODE = 7'))
foreach ($reuse in @($true,$false)) {
    try {
        & (Join-Path $fixtureTools 'Analyze-ItemHak.ps1') -InputHak $hakPath -OutputRelativePath hak -ProfilePath $profilePath -NwnRoot fixture-game -NwnUserDirectory fixture-user -SkipImport:$reuse
        throw 'Failed baseline inventory unexpectedly accepted.'
    } catch { if ($_.Exception.Message -ne 'Unable to inventory the requested NWN:EE baseline.') {throw} }
    Assert-HakReportsPreserved
    if ([IO.File]::ReadAllText($rawModel) -cne $modelText) {throw 'Failed baseline query changed the raw extraction.'}
    if (@(Get-ChildItem (Join-Path $fixture '.quarantine') -Directory -Force -Filter '.item-analysis-build-*').Count) {throw 'Failed HAK analysis left temporary output.'}
}
[IO.File]::WriteAllText($baselineSpy,$baselineCode)
$global:LASTEXITCODE = 0 # Clear the deliberately injected native failure before a lookup-free run.
& (Join-Path $fixtureTools 'Analyze-ItemHak.ps1') -InputHak $hakPath -OutputRelativePath hak -SkipImport
Write-Host 'Item import regression checks passed, including reused-inventory verification, nested platform helper calls, failed repeat preservation, and publication rollback.'
