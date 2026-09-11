#Requires -Version 7.0

[CmdletBinding()]
param(
    [string]$FixturePath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'test-modules/mdrnee_tilesets/fixture.json'),
    [string]$OutputDirectory = (Join-Path (Split-Path -Parent $PSScriptRoot) 'output'),
    [switch]$SkipHakBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$resolvedFixture = [IO.Path]::GetFullPath($FixturePath)
$resolvedOutput = [IO.Path]::GetFullPath($OutputDirectory)
$temporaryRoot = [IO.Path]::GetFullPath((Join-Path $repositoryRoot '.tmp/mdrnee-tileset-test-module'))
$allowedTemporaryRoot = [IO.Path]::GetFullPath((Join-Path $repositoryRoot '.tmp'))

if (-not $temporaryRoot.StartsWith($allowedTemporaryRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing unexpected temporary path '$temporaryRoot'."
}
if (-not (Test-Path -LiteralPath $resolvedFixture -PathType Leaf)) {
    throw "Fixture descriptor not found: $resolvedFixture"
}

$fixture = Get-Content -LiteralPath $resolvedFixture -Raw | ConvertFrom-Json -Depth 64
if ($fixture.schemaVersion -ne 1) { throw "Unsupported fixture schema version '$($fixture.schemaVersion)'." }
$expectedHakCount = @($fixture.haks).Count
if ($expectedHakCount -lt 1) { throw 'Fixture must declare at least one HAK.' }
if (@($fixture.areas).Count -ne 18) { throw "Fixture must declare exactly 18 areas; found $(@($fixture.areas).Count)." }
if ($fixture.defaultAreaWidth -lt 8 -or $fixture.defaultAreaWidth -gt 32 -or
    $fixture.defaultAreaHeight -lt 8 -or $fixture.defaultAreaHeight -gt 32) {
    throw 'Default test-area dimensions must each be between 8 and 32 tiles.'
}

$duplicates = @($fixture.haks | Group-Object | Where-Object Count -gt 1)
if ($duplicates.Count -gt 0) { throw "Duplicate HAK declarations: $($duplicates.Name -join ', ')" }
$duplicates = @($fixture.areas.resref | Group-Object | Where-Object Count -gt 1)
if ($duplicates.Count -gt 0) { throw "Duplicate area resrefs: $($duplicates.Name -join ', ')" }

$registered = Get-Content -LiteralPath (Join-Path $repositoryRoot 'hakbuilder.json') -Raw | ConvertFrom-Json -Depth 32
$registeredNames = @($registered.HakList.Name)
$fixtureHakNames = @($fixture.haks)
$sameHakOrder = $registeredNames.Count -eq $fixtureHakNames.Count
for ($i = 0; $sameHakOrder -and $i -lt $registeredNames.Count; $i++) {
    $sameHakOrder = $registeredNames[$i] -ceq $fixtureHakNames[$i]
}
if (-not $sameHakOrder) {
    throw 'Fixture HAK declarations do not exactly match hakbuilder.json.'
}
if ([IO.Path]::GetFileNameWithoutExtension([string]$fixture.outputFile) -cne [string]$fixture.moduleResRef) {
    throw 'Fixture outputFile must use moduleResRef as its filename.'
}

foreach ($area in $fixture.areas) {
    if ([string]::IsNullOrWhiteSpace($area.resref) -or $area.resref.Length -gt 16 -or $area.resref -cnotmatch '^[a-z0-9_]+$') {
        throw "Invalid area resref '$($area.resref)'."
    }
    if ($area.tileset.Length -gt 16 -or $area.tileset -cnotmatch '^[a-z0-9_]+$') {
        throw "Invalid tileset resref '$($area.tileset)'."
    }
    if ($area.pack -notin $fixture.haks) { throw "Area '$($area.resref)' names undeclared pack '$($area.pack)'." }
    $setPath = Join-Path $repositoryRoot "$($area.pack)/$($area.tileset).set"
    if (-not (Test-Path -LiteralPath $setPath -PathType Leaf)) {
        throw "Area '$($area.resref)' cannot find its SET resource at '$setPath'."
    }
    $areaWidth = if ($area.PSObject.Properties.Name -contains 'width') { [int]$area.width } else { [int]$fixture.defaultAreaWidth }
    $areaHeight = if ($area.PSObject.Properties.Name -contains 'height') { [int]$area.height } else { [int]$fixture.defaultAreaHeight }
    if ($areaWidth -lt 8 -or $areaWidth -gt 32 -or $areaHeight -lt 8 -or $areaHeight -gt 32) {
        throw "Area '$($area.resref)' dimensions must each be between 8 and 32 tiles."
    }
}

if (-not $SkipHakBuild) {
    & (Join-Path $PSScriptRoot 'Build-Haks.ps1')
    if ($LASTEXITCODE -ne 0) { throw "Build-Haks.ps1 failed with exit code $LASTEXITCODE." }
}

$hakRecords = foreach ($hakName in $fixture.haks) {
    $hakPath = Join-Path $repositoryRoot "output/$hakName.hak"
    if (-not (Test-Path -LiteralPath $hakPath -PathType Leaf)) { throw "Required HAK is missing: $hakPath" }
    $file = Get-Item -LiteralPath $hakPath
    [ordered]@{
        name = $hakName
        path = [IO.Path]::GetRelativePath($repositoryRoot, $file.FullName).Replace('\', '/')
        size = $file.Length
        sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

$toolRoot = & (Join-Path $PSScriptRoot 'Bootstrap-Tools.ps1')
$nwnGff = Join-Path $toolRoot 'nwn_gff.exe'
$nwnErf = Join-Path $toolRoot 'nwn_erf.exe'
if (-not (Test-Path -LiteralPath $nwnGff -PathType Leaf)) { throw "Pinned nwn_gff not found beneath '$toolRoot'." }
if (-not (Test-Path -LiteralPath $nwnErf -PathType Leaf)) { throw "Pinned nwn_erf not found beneath '$toolRoot'." }

if (Test-Path -LiteralPath $temporaryRoot) { Remove-Item -LiteralPath $temporaryRoot -Recurse -Force }
$jsonRoot = New-Item -ItemType Directory -Force -Path (Join-Path $temporaryRoot 'json')
$binaryRoot = New-Item -ItemType Directory -Force -Path (Join-Path $temporaryRoot 'binary')
New-Item -ItemType Directory -Force -Path $resolvedOutput | Out-Null

function New-GffField([string]$Type, $Value) {
    if ($Type -eq 'list') {
        return [ordered]@{ type = $Type; value = @($Value) }
    }
    $typedValue = switch ($Type) {
        'byte' { [byte]$Value; break }
        'word' { [uint16]$Value; break }
        'int' { [int32]$Value; break }
        'dword' { [uint32]$Value; break }
        'float' { [single]$Value; break }
        default { $Value }
    }
    [ordered]@{ type = $Type; value = $typedValue }
}

function Write-GffJson([string]$Path, $Value) {
    $Value | ConvertTo-Json -Depth 64 -Compress | Set-Content -LiteralPath $Path -Encoding utf8NoBOM
}

$areaList = @()
foreach ($area in $fixture.areas) {
    $areaList += [ordered]@{ __struct_id = 6; Area_Name = New-GffField 'resref' $area.resref }
    $areaWidth = if ($area.PSObject.Properties.Name -contains 'width') { [int]$area.width } else { [int]$fixture.defaultAreaWidth }
    $areaHeight = if ($area.PSObject.Properties.Name -contains 'height') { [int]$area.height } else { [int]$fixture.defaultAreaHeight }
    $tiles = [Collections.Generic.List[object]]::new()
    for ($tileIndex = 0; $tileIndex -lt ($areaWidth * $areaHeight); $tileIndex++) {
        $tiles.Add([ordered]@{
            __struct_id = 1
            Tile_AnimLoop1 = New-GffField 'byte' 1
            Tile_AnimLoop2 = New-GffField 'byte' 1
            Tile_AnimLoop3 = New-GffField 'byte' 1
            Tile_Height = New-GffField 'int' 0
            Tile_ID = New-GffField 'int' ([int]$area.tileId)
            Tile_MainLight1 = New-GffField 'byte' 0
            Tile_MainLight2 = New-GffField 'byte' 0
            Tile_Orientation = New-GffField 'int' 0
            Tile_SrcLight1 = New-GffField 'byte' 0
            Tile_SrcLight2 = New-GffField 'byte' 0
        })
    }
    $are = [ordered]@{
        __data_type = 'ARE '
        __struct_id = -1
        ChanceLightning = New-GffField 'int' 0
        ChanceRain = New-GffField 'int' 0
        ChanceSnow = New-GffField 'int' 0
        Comments = New-GffField 'cexostring' "Tileset palette-test area for $($area.friendlyName) ($($area.tileset)); $areaWidth x $areaHeight tiles."
        Creator_ID = New-GffField 'int' -1
        DayNightCycle = New-GffField 'byte' 0
        Expansion_List = New-GffField 'list' @()
        Flags = New-GffField 'dword' 4
        FogClipDist = New-GffField 'float' 45.0
        Height = New-GffField 'int' $areaHeight
        ID = New-GffField 'int' -1
        IsNight = New-GffField 'byte' 0
        LightingScheme = New-GffField 'byte' 0
        LoadScreenID = New-GffField 'word' 0
        ModListenCheck = New-GffField 'int' 0
        ModSpotCheck = New-GffField 'int' 0
        MoonAmbientColor = New-GffField 'dword' 0
        MoonDiffuseColor = New-GffField 'dword' 0
        MoonFogAmount = New-GffField 'byte' 0
        MoonFogColor = New-GffField 'dword' 0
        MoonShadows = New-GffField 'byte' 0
        Name = New-GffField 'cexolocstring' ([ordered]@{ '0' = "$($area.friendlyName) [$($area.tileset)]" })
        NoRest = New-GffField 'byte' 0
        OnEnter = New-GffField 'resref' ''
        OnExit = New-GffField 'resref' ''
        OnHeartbeat = New-GffField 'resref' ''
        OnUserDefined = New-GffField 'resref' ''
        PlayerVsPlayer = New-GffField 'byte' 0
        ResRef = New-GffField 'resref' $area.resref
        ShadowOpacity = New-GffField 'byte' 0
        SkyBox = New-GffField 'byte' 0
        SunAmbientColor = New-GffField 'dword' 7368816
        SunDiffuseColor = New-GffField 'dword' 12303291
        SunFogAmount = New-GffField 'byte' 0
        SunFogColor = New-GffField 'dword' 0
        SunShadows = New-GffField 'byte' 0
        Tag = New-GffField 'cexostring' $area.resref
        TileBrdrDisabled = New-GffField 'byte' 0
        Tile_List = New-GffField 'list' @($tiles)
        Tileset = New-GffField 'resref' $area.tileset
        Version = New-GffField 'dword' 2
        Width = New-GffField 'int' $areaWidth
        WindPower = New-GffField 'int' 0
    }
    $git = [ordered]@{
        __data_type = 'GIT '
        __struct_id = -1
        'Creature List' = New-GffField 'list' @()
        'Door List' = New-GffField 'list' @()
        'Placeable List' = New-GffField 'list' @()
        TriggerList = New-GffField 'list' @()
        WaypointList = New-GffField 'list' @()
    }
    Write-GffJson (Join-Path $jsonRoot "$($area.resref).are.json") $are
    Write-GffJson (Join-Path $jsonRoot "$($area.resref).git.json") $git
}

$hakList = @($fixture.haks | ForEach-Object {
    [ordered]@{ __struct_id = 8; Mod_Hak = New-GffField 'cexostring' $_ }
})
$entryArea = $fixture.areas[0].resref

$ifo = [ordered]@{
    __data_type = 'IFO '
    __struct_id = -1
    Expansion_Pack = New-GffField 'word' 0
    Mod_Area_list = New-GffField 'list' $areaList
    Mod_CacheNSSList = New-GffField 'list' @()
    Mod_Creator_ID = New-GffField 'int' -1
    Mod_CustomTlk = New-GffField 'cexostring' ''
    Mod_CutSceneList = New-GffField 'list' @()
    Mod_DawnHour = New-GffField 'byte' 6
    Mod_Description = New-GffField 'cexolocstring' ([ordered]@{ '0' = $fixture.description })
    Mod_DuskHour = New-GffField 'byte' 18
    Mod_Entry_Area = New-GffField 'resref' $entryArea
    Mod_Entry_Dir_X = New-GffField 'float' 1.0
    Mod_Entry_Dir_Y = New-GffField 'float' 0.0
    Mod_Entry_X = New-GffField 'float' 5.0
    Mod_Entry_Y = New-GffField 'float' 5.0
    Mod_Entry_Z = New-GffField 'float' 0.0
    Mod_Expan_List = New-GffField 'list' @()
    Mod_GVar_List = New-GffField 'list' @()
    Mod_HakList = New-GffField 'list' $hakList
    Mod_IsSaveGame = New-GffField 'byte' 0
    Mod_MinGameVer = New-GffField 'cexostring' '1.69'
    Mod_MinPerHour = New-GffField 'byte' 2
    Mod_Name = New-GffField 'cexolocstring' ([ordered]@{ '0' = $fixture.moduleName })
    Mod_OnAcquirItem = New-GffField 'resref' ''
    Mod_OnActvtItem = New-GffField 'resref' ''
    Mod_OnClientEntr = New-GffField 'resref' ''
    Mod_OnClientLeav = New-GffField 'resref' ''
    Mod_OnCutsnAbort = New-GffField 'resref' ''
    Mod_OnHeartbeat = New-GffField 'resref' ''
    Mod_OnModLoad = New-GffField 'resref' ''
    Mod_OnModStart = New-GffField 'resref' ''
    Mod_OnPlrChat = New-GffField 'resref' ''
    Mod_OnPlrDeath = New-GffField 'resref' ''
    Mod_OnPlrDying = New-GffField 'resref' ''
    Mod_OnPlrEqItm = New-GffField 'resref' ''
    Mod_OnPlrLvlUp = New-GffField 'resref' ''
    Mod_OnPlrRest = New-GffField 'resref' ''
    Mod_OnPlrUnEqItm = New-GffField 'resref' ''
    Mod_OnSpawnBtnDn = New-GffField 'resref' ''
    Mod_OnUnAqreItem = New-GffField 'resref' ''
    Mod_OnUsrDefined = New-GffField 'resref' ''
    Mod_StartDay = New-GffField 'byte' 1
    Mod_StartHour = New-GffField 'byte' 12
    Mod_StartMonth = New-GffField 'byte' 1
    Mod_StartMovie = New-GffField 'resref' ''
    Mod_StartYear = New-GffField 'dword' 1372
    Mod_Tag = New-GffField 'cexostring' 'SRN_MDRNEE_TEST'
    Mod_Version = New-GffField 'dword' 3
    Mod_XPScale = New-GffField 'byte' 10
}
Write-GffJson (Join-Path $jsonRoot 'module.ifo.json') $ifo

$factions = @('PC', 'Hostile', 'Commoner', 'Merchant', 'Defender')
$factionList = for ($i = 0; $i -lt $factions.Count; $i++) {
    [ordered]@{
        __struct_id = $i
        FactionGlobal = New-GffField 'word' 1
        FactionName = New-GffField 'cexostring' $factions[$i]
        FactionParentID = New-GffField 'dword' 4294967295
    }
}
$repList = @()
$repId = 0
for ($i = 0; $i -lt $factions.Count; $i++) {
    for ($j = 0; $j -lt $factions.Count; $j++) {
        if ($i -eq $j) { continue }
        $repList += [ordered]@{
            __struct_id = $repId
            FactionID1 = New-GffField 'dword' $i
            FactionID2 = New-GffField 'dword' $j
            FactionRep = New-GffField 'dword' 50
        }
        $repId++
    }
}
$fac = [ordered]@{
    __data_type = 'FAC '
    __struct_id = -1
    FactionList = New-GffField 'list' @($factionList)
    RepList = New-GffField 'list' @($repList)
}
Write-GffJson (Join-Path $jsonRoot 'repute.fac.json') $fac

foreach ($jsonFile in Get-ChildItem -LiteralPath $jsonRoot -Filter '*.json' -File) {
    $outputName = $jsonFile.Name.Substring(0, $jsonFile.Name.Length - 5)
    $binaryPath = Join-Path $binaryRoot $outputName
    & $nwnGff -i $jsonFile.FullName -o $binaryPath
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $binaryPath -PathType Leaf)) {
        throw "nwn_gff failed converting '$($jsonFile.Name)'."
    }
}

$modulePath = Join-Path $resolvedOutput $fixture.outputFile
if (Test-Path -LiteralPath $modulePath) { Remove-Item -LiteralPath $modulePath -Force }
$filesToPack = @(Get-ChildItem -LiteralPath $binaryRoot -File | Sort-Object Name | ForEach-Object FullName)
& $nwnErf -c -f $modulePath -e MOD @filesToPack
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $modulePath -PathType Leaf)) {
    throw 'nwn_erf failed to pack the module.'
}

# nwn_erf writes the wall-clock date. Pin the two ERF V1 date fields so equal inputs produce
# byte-identical modules on different days.
$bytes = [IO.File]::ReadAllBytes($modulePath)
if ($bytes.Length -lt 160 -or [Text.Encoding]::ASCII.GetString($bytes, 0, 8) -ne 'MOD V1.0') {
    throw 'Packed module has an unrecognized ERF header.'
}
$sourceDate = ([DateTime]$fixture.sourceDateUtc).ToUniversalTime()
[BitConverter]::GetBytes([uint32]($sourceDate.Year - 1900)).CopyTo($bytes, 32)
[BitConverter]::GetBytes([uint32]($sourceDate.DayOfYear - 1)).CopyTo($bytes, 36)
[IO.File]::WriteAllBytes($modulePath, $bytes)

$inventory = @(& $nwnErf -t -f $modulePath | Where-Object { $_ -match '\S' })
if ($LASTEXITCODE -ne 0) { throw 'Unable to reopen the packed module.' }
$expectedResourceCount = 2 + (2 * @($fixture.areas).Count)
if ($inventory.Count -ne $expectedResourceCount) {
    throw "Packed module inventory has $($inventory.Count) resources; expected $expectedResourceCount."
}

$roundTripRoot = New-Item -ItemType Directory -Force -Path (Join-Path $temporaryRoot 'roundtrip')
Push-Location $roundTripRoot
try {
    & $nwnErf -x -f $modulePath | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Unable to extract the packed module for verification.' }
}
finally {
    Pop-Location
}
$roundTripIfo = Join-Path $roundTripRoot 'module.ifo'
$roundTripJson = Join-Path $temporaryRoot 'roundtrip-module.ifo.json'
& $nwnGff -i $roundTripIfo -o $roundTripJson -p
if ($LASTEXITCODE -ne 0) { throw 'Unable to decode the packed module.ifo.' }
$decodedIfo = Get-Content -LiteralPath $roundTripJson -Raw | ConvertFrom-Json -Depth 64
if (@($decodedIfo.Mod_HakList.value).Count -ne $expectedHakCount) { throw "Round-trip module.ifo does not declare $expectedHakCount HAKs." }
if (@($decodedIfo.Mod_Area_list.value).Count -ne 18) { throw 'Round-trip module.ifo does not declare 18 areas.' }
if (@($decodedIfo.Mod_HakList.value | Where-Object __struct_id -ne 8).Count -gt 0) {
    throw 'Round-trip HAK list contains an invalid Aurora struct id.'
}
foreach ($area in $fixture.areas) {
    $areaWidth = if ($area.PSObject.Properties.Name -contains 'width') { [int]$area.width } else { [int]$fixture.defaultAreaWidth }
    $areaHeight = if ($area.PSObject.Properties.Name -contains 'height') { [int]$area.height } else { [int]$fixture.defaultAreaHeight }
    $roundTripAre = Join-Path $roundTripRoot "$($area.resref).are"
    $roundTripAreJson = Join-Path $temporaryRoot "roundtrip-$($area.resref).are.json"
    & $nwnGff -i $roundTripAre -o $roundTripAreJson -p
    if ($LASTEXITCODE -ne 0) { throw "Unable to decode packed area '$($area.resref)'." }
    $decodedAre = Get-Content -LiteralPath $roundTripAreJson -Raw | ConvertFrom-Json -Depth 64
    if ([int]$decodedAre.Width.value -ne $areaWidth -or [int]$decodedAre.Height.value -ne $areaHeight) {
        throw "Packed area '$($area.resref)' dimensions do not match its fixture."
    }
    if (@($decodedAre.Tile_List.value).Count -ne ($areaWidth * $areaHeight)) {
        throw "Packed area '$($area.resref)' tile count does not match its dimensions."
    }
    $unexpectedSeedTiles = @($decodedAre.Tile_List.value | Where-Object {
        [int]$_.Tile_ID.value -ne [int]$area.tileId
    })
    if ($unexpectedSeedTiles.Count -gt 0) {
        throw "Packed area '$($area.resref)' does not consistently use configured seed tile $($area.tileId)."
    }
}

$moduleFile = Get-Item -LiteralPath $modulePath
$receipt = [ordered]@{
    schemaVersion = 1
    generatedAtUtc = [DateTime]::UtcNow.ToString('o')
    fixture = [IO.Path]::GetRelativePath($repositoryRoot, $resolvedFixture).Replace('\', '/')
    module = [ordered]@{
        file = $moduleFile.Name
        size = $moduleFile.Length
        sha256 = (Get-FileHash -LiteralPath $modulePath -Algorithm SHA256).Hash.ToLowerInvariant()
        resourceCount = $inventory.Count
        areaCount = 18
        hakCount = $expectedHakCount
        entryArea = $entryArea
        defaultAreaWidth = [int]$fixture.defaultAreaWidth
        defaultAreaHeight = [int]$fixture.defaultAreaHeight
    }
    haks = @($hakRecords)
}
$receiptPath = Join-Path $resolvedOutput 'srn_mdrnee_test.receipt.json'
$receipt | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $receiptPath -Encoding utf8NoBOM

Write-Host "Built $modulePath"
Write-Host "Verified 18 areas, $expectedHakCount HAK declarations, and $($inventory.Count) packed resources."
Write-Host "Receipt: $receiptPath"
