#Requires -Version 7.0

[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Analyze', 'Apply')][string]$Mode,
    [Parameter(Mandatory)][string]$InputTlk,
    [Parameter(Mandatory)][string]$OutputRelativePath,
    [Parameter(Mandatory)][string]$ProfilePath,
    [string]$ExpectedSha256
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'SrnHaks.Common.psm1') -Force

$repoRoot = Get-SrnRepositoryRoot
$quarantineRoot = Join-Path $repoRoot '.quarantine'

function Resolve-QuarantinePath {
    param([Parameter(Mandatory)][string]$RelativePath)
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

function Get-TlkPayloadFingerprint {
    param([Parameter(Mandatory)]$Entry)
    $payload = [ordered]@{}
    foreach ($property in @($Entry.PSObject.Properties | Where-Object Name -cne 'id' | Sort-Object Name)) {
        $value = $property.Value
        if ($property.Name -ceq 'text' -and $null -ne $value) {
            $value = ([string]$value).Replace("`r`n", "`n").Replace("`r", "`n").Normalize([Text.NormalizationForm]::FormC)
        }
        $payload[$property.Name] = $value
    }
    return ($payload | ConvertTo-Json -Compress -Depth 8)
}

function New-CanonicalEntry {
    param([Parameter(Mandatory)][int]$Id, [Parameter(Mandatory)]$Source)
    $entry = [ordered]@{ id = $Id }
    foreach ($property in @($Source.PSObject.Properties | Where-Object Name -cne 'id')) {
        $entry[$property.Name] = $property.Value
    }
    return [pscustomobject]$entry
}

$inputPath = [IO.Path]::GetFullPath($InputTlk)
$profileFile = [IO.Path]::GetFullPath($ProfilePath)
if (-not (Test-Path -LiteralPath $inputPath -PathType Leaf)) { throw "Input TLK not found: $inputPath" }
if (-not (Test-Path -LiteralPath $profileFile -PathType Leaf)) { throw "TLK import profile not found: $profileFile" }
$workspace = Resolve-QuarantinePath $OutputRelativePath
New-Item -ItemType Directory -Force -Path $workspace | Out-Null

$profile = Get-Content -Raw -LiteralPath $profileFile | ConvertFrom-Json -Depth 32
if ([int]$profile.schemaVersion -ne 1) { throw "Unsupported TLK import profile schema '$($profile.schemaVersion)'." }
$profileHash = (Get-FileHash -LiteralPath $profileFile -Algorithm SHA256).Hash.ToUpperInvariant()
$inputHash = (Get-FileHash -LiteralPath $inputPath -Algorithm SHA256).Hash.ToUpperInvariant()
$requiredHash = if ($ExpectedSha256) { $ExpectedSha256 } else { [string]$profile.expectedSha256 }
if ($requiredHash -and $inputHash -cne $requiredHash.ToUpperInvariant()) {
    throw "TLK hash mismatch. Expected $($requiredHash.ToUpperInvariant()); found $inputHash."
}

$extractedPath = Join-Path $workspace 'source.json'
$tool = Get-SrnTool -Name tlk
& $tool -i $inputPath -l tlk -o $extractedPath -k json --pretty
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $extractedPath -PathType Leaf)) {
    throw 'nwn_tlk failed to extract the input talk table.'
}
$sourceTlk = Get-Content -Raw -LiteralPath $extractedPath | ConvertFrom-Json -Depth 32
$profileKeys = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
$sourceIds = [Collections.Generic.HashSet[int]]::new()
$candidates = [Collections.Generic.List[object]]::new()
foreach ($mapping in @($profile.entries)) {
    $key = [string]$mapping.key
    if ($key -cnotmatch '^[a-z0-9]+(?:[._-][a-z0-9]+)*$') { throw "Invalid TLK allocation key '$key'." }
    if (-not $profileKeys.Add($key)) { throw "Duplicate TLK profile key '$key'." }
    $sourceEntry = $null
    $sourceId = $null
    if ($mapping.PSObject.Properties.Name -contains 'sourceId' -and $null -ne $mapping.sourceId) {
        $sourceId = [int]$mapping.sourceId
        if (-not $sourceIds.Add($sourceId)) { throw "Duplicate TLK source ID '$sourceId'." }
        $matches = @($sourceTlk.entries | Where-Object { [int]$_.id -eq $sourceId })
        if ($matches.Count -ne 1) { throw "Expected exactly one source TLK entry $sourceId; found $($matches.Count)." }
        $sourceEntry = $matches[0]
        if ($mapping.PSObject.Properties.Name -contains 'expectedText' -and [string]$sourceEntry.text -cne [string]$mapping.expectedText) {
            throw "Source TLK entry $sourceId text does not match the profile."
        }
    }
    elseif ($mapping.PSObject.Properties.Name -contains 'text') {
        $sourceEntry = [pscustomobject]@{ text = [string]$mapping.text }
    }
    else {
        throw "TLK mapping '$key' needs sourceId or text."
    }
    $candidates.Add([pscustomobject][ordered]@{
        key = $key
        owner = [string]$mapping.owner
        sourceId = $sourceId
        sourceGameStrRef = if ($null -ne $sourceId) { 0x01000000 + $sourceId } else { $null }
        sourceValue = if ($mapping.PSObject.Properties.Name -contains 'sourceValue') { [int64]$mapping.sourceValue } else { $null }
        reason = if ($mapping.PSObject.Properties.Name -contains 'reason') { [string]$mapping.reason } else { 'legacy-tlk-migration' }
        payload = $sourceEntry
        fingerprint = Get-TlkPayloadFingerprint $sourceEntry
    })
}

$analysis = [ordered]@{
    schemaVersion = 1
    profile = [string]$profile.name
    profileSha256 = $profileHash
    source = $inputPath
    sourceSha256 = $inputHash
    sourceLanguage = [int]$sourceTlk.language
    candidateCount = $candidates.Count
    candidates = @($candidates | ForEach-Object {
        [ordered]@{ key = $_.key; owner = $_.owner; sourceId = $_.sourceId; sourceGameStrRef = $_.sourceGameStrRef; sourceValue = $_.sourceValue; reason = $_.reason; text = [string]$_.payload.text }
    })
}
$analysisPath = Join-Path $workspace 'analysis.json'
Write-SrnJsonAtomic -Path $analysisPath -Value $analysis
if ($Mode -eq 'Analyze') {
    Write-Host "TLK analysis complete: $analysisPath"
    exit 0
}

if ([int]$sourceTlk.language -ne 0) { throw "Expected English source TLK language 0; found $($sourceTlk.language)." }
$allocationPath = Join-Path $repoRoot 'srn_tlk/allocations.json'
$tlkPath = Join-Path $repoRoot 'srn_tlk/srn.tlk.json'
$lockPath = Join-Path $repoRoot 'srn_tlk/.allocation.lock'
$lockStream = $null
$lockOwned = $false
try {
    $lockStream = [IO.File]::Open($lockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    $lockOwned = $true
    $allocationBytes = [IO.File]::ReadAllBytes($allocationPath)
    $tlkBytes = [IO.File]::ReadAllBytes($tlkPath)
    $registry = [Text.Encoding]::UTF8.GetString($allocationBytes) | ConvertFrom-Json -Depth 32
    $canonical = [Text.Encoding]::UTF8.GetString($tlkBytes) | ConvertFrom-Json -Depth 32
    $results = [Collections.Generic.List[object]]::new()
    $knownKeys = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($allocation in @($registry.allocations)) {
        $allocationKeys = @([string]$allocation.key)
        if ($allocation.PSObject.Properties.Name -contains 'aliases') { $allocationKeys += @($allocation.aliases) }
        foreach ($allocationKey in $allocationKeys) {
            if ([string]$allocationKey -cnotmatch '^[a-z0-9]+(?:[._-][a-z0-9]+)*$') {
                throw "Invalid canonical TLK key or alias '$allocationKey'."
            }
            if (-not $knownKeys.Add([string]$allocationKey)) { throw "Duplicate canonical TLK key or alias '$allocationKey'." }
        }
    }

    foreach ($candidate in $candidates) {
        if ($candidate.owner -notin @('shared', 'SR_NWN', 'SRN_NWN')) { throw "Invalid owner '$($candidate.owner)' for $($candidate.key)." }
        $keyMatches = @($registry.allocations | Where-Object {
            [string]$_.key -ceq $candidate.key -or
            ($_.PSObject.Properties.Name -contains 'aliases' -and @($_.aliases) -ccontains $candidate.key)
        })
        if ($keyMatches.Count -gt 1) { throw "Duplicate canonical allocation key '$($candidate.key)'." }
        $selectedAllocation = $null
        $deduplicated = $false
        if ($keyMatches.Count -eq 1) {
            $selectedAllocation = $keyMatches[0]
            $deduplicated = [string]$selectedAllocation.key -cne $candidate.key
            if ([string]$selectedAllocation.status -cne 'active') { throw "TLK allocation '$($candidate.key)' is not active." }
            if ([string]$selectedAllocation.owner -cne $candidate.owner) {
                throw "TLK allocation '$($candidate.key)' belongs to '$($selectedAllocation.owner)', not '$($candidate.owner)'."
            }
            $canonicalMatch = @($canonical.entries | Where-Object { [int]$_.id -eq [int]$selectedAllocation.id })
            if ($canonicalMatch.Count -ne 1 -or (Get-TlkPayloadFingerprint $canonicalMatch[0]) -cne $candidate.fingerprint) {
                throw "TLK allocation '$($candidate.key)' exists with a different payload."
            }
        }
        else {
            $payloadMatches = @($canonical.entries | Where-Object { (Get-TlkPayloadFingerprint $_) -ceq $candidate.fingerprint })
            if ($payloadMatches.Count -gt 1) { throw "Canonical TLK already contains duplicate payloads matching '$($candidate.key)'." }
            if ($payloadMatches.Count -eq 1) {
                $selectedAllocation = @($registry.allocations | Where-Object { [int]$_.id -eq [int]$payloadMatches[0].id -and [string]$_.status -ceq 'active' })
                if ($selectedAllocation.Count -ne 1) { throw "Matching TLK payload for '$($candidate.key)' lacks one active allocation." }
                $selectedAllocation = $selectedAllocation[0]
                $deduplicated = $true
                if (-not $knownKeys.Add($candidate.key)) { throw "Duplicate canonical TLK alias '$($candidate.key)'." }
                if (-not ($selectedAllocation.PSObject.Properties.Name -contains 'aliases')) {
                    $selectedAllocation | Add-Member -MemberType NoteProperty -Name aliases -Value @()
                }
                $selectedAllocation.aliases = @($selectedAllocation.aliases) + $candidate.key
            }
            else {
                $id = [int]$registry.nextId
                $selectedAllocation = [pscustomobject][ordered]@{ id = $id; key = $candidate.key; owner = $candidate.owner; status = 'active' }
                $registry.allocations = @($registry.allocations) + $selectedAllocation
                if (-not $knownKeys.Add($candidate.key)) { throw "Duplicate canonical TLK key '$($candidate.key)'." }
                $registry.nextId = $id + 1
                $canonical.entries = @($canonical.entries) + (New-CanonicalEntry -Id $id -Source $candidate.payload)
            }
        }
        $results.Add([pscustomobject][ordered]@{
            requestedKey = $candidate.key
            canonicalKey = [string]$selectedAllocation.key
            canonicalOwner = [string]$selectedAllocation.owner
            id = [int]$selectedAllocation.id
            gameStrRef = 0x01000000 + [int]$selectedAllocation.id
            deduplicated = $deduplicated
            sourceId = $candidate.sourceId
            sourceGameStrRef = $candidate.sourceGameStrRef
            sourceValue = $candidate.sourceValue
            reason = $candidate.reason
            text = [string]$candidate.payload.text
        })
    }

    try {
        Write-SrnJsonAtomic -Path $allocationPath -Value $registry
        Write-SrnJsonAtomic -Path $tlkPath -Value $canonical
    }
    catch {
        [IO.File]::WriteAllBytes($allocationPath, $allocationBytes)
        [IO.File]::WriteAllBytes($tlkPath, $tlkBytes)
        throw
    }

    $migration = [ordered]@{
        schemaVersion = 1
        profile = [string]$profile.name
        profileSha256 = $profileHash
        sourceFile = [IO.Path]::GetFileName($inputPath)
        sourceSha256 = $inputHash
        importedAtUtc = [DateTime]::UtcNow.ToString('o')
        requestedCount = $results.Count
        canonicalEntryCount = @($results.id | Sort-Object -Unique).Count
        deduplicatedCount = @($results | Where-Object deduplicated).Count
        mappings = @($results)
    }
    $migrationPath = Join-Path $workspace 'migration.json'
    Write-SrnJsonAtomic -Path $migrationPath -Value $migration
    $docs = Join-Path $repoRoot 'docs/imports'
    New-Item -ItemType Directory -Force -Path $docs | Out-Null
    Write-SrnJsonAtomic -Path (Join-Path $docs "$($profile.reportStem)-migration.json") -Value $migration
    Write-Host "TLK import complete: $migrationPath"
}
finally {
    if ($null -ne $lockStream) { $lockStream.Dispose() }
    if ($lockOwned -and (Test-Path -LiteralPath $lockPath)) { Remove-Item -LiteralPath $lockPath -Force }
}
