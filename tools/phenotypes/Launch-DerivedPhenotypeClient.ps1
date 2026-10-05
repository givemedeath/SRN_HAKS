param(
  [Parameter(Mandatory=$true)][string]$Fixture,
  [Parameter(Mandatory=$true)][string]$ReceiptSha256,
  [Parameter(Mandatory=$true)][ValidateScript({Test-Path -LiteralPath $_ -PathType Leaf})][string]$Client,
  [Parameter(Mandatory=$true)][ValidateScript({Test-Path -LiteralPath $_ -PathType Leaf})][string]$WorkspacePython,
  [switch]$NoLaunch
)
$ErrorActionPreference='Stop'
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; $env:PYTHONDONTWRITEBYTECODE='1'
$taskStage=(Resolve-Path -LiteralPath $Fixture).Path
$taskPreflight=Join-Path $taskStage ('client-preflight-'+[guid]::NewGuid().ToString('N')+'.json')

# Identify target race and prefix from fixture manifest if present
$manifestPath=Join-Path $taskStage 'manifest.json'
$race='dwarf'
$prefix='pmd0'
if (Test-Path -LiteralPath $manifestPath) {
  $manifest=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
  if ($manifest.combinations -and $manifest.combinations.Count -gt 0) {
    $comb=$manifest.combinations[0]
    if ($comb.race) { $race=$comb.race.ToLower() }
    if ($comb.slug -and ($comb.slug -match '^([a-z]+)_')) { $race=$Matches[1] }
  }
}
$prefixMap=@{dwarf='pmd0'; troll='pmg0'; elf='pme0'; orc='pmo0'}
if ($prefixMap.ContainsKey($race)) { $prefix=$prefixMap[$race] }

& $WorkspacePython (Join-Path $PSScriptRoot 'preflight_derived_dwarf_client.py') `
  --stage $taskStage `
  --client $Client `
  --race $race `
  --prefix $prefix `
  --output-receipt $taskPreflight

if ($LASTEXITCODE -ne 0) { throw 'Derived-phenotype client preflight failed' }

# Verify and compare ReceiptSha256 against the fixture build receipt hash
$fixtureReceiptPath=Join-Path $taskStage 'test-module/receipt.json'
if (-not (Test-Path -LiteralPath $fixtureReceiptPath)) {
  $fixtureReceiptPath=Join-Path $taskStage 'receipt.json'
}
if (Test-Path -LiteralPath $fixtureReceiptPath) {
  $actualReceiptSha=(Get-FileHash -LiteralPath $fixtureReceiptPath -Algorithm SHA256).Hash.ToLower()
  if ($ReceiptSha256 -and ($actualReceiptSha -ne $ReceiptSha256.ToLower())) {
    throw "Fixture receipt SHA256 mismatch: expected $ReceiptSha256, actual $actualReceiptSha"
  }
}

$taskProof=Get-Content -LiteralPath $taskPreflight -Raw | ConvertFrom-Json

if ($NoLaunch) {
  $taskProof | ConvertTo-Json -Depth 10
  return
}

$taskRunning=@(Get-Process | Where-Object { $_.ProcessName -ieq 'nwmain' })
if ($taskRunning.Count -ne 0) { throw 'A client is already running; observe ownership before replacing it' }

# Explicitly authorized interactive game test window
$taskStarted=Start-Process -FilePath $Client -WorkingDirectory (Split-Path -Parent $Client) -WindowStyle Normal -ArgumentList @('-userdirectory',$taskProof.userDirectory,'+TestNewModule','srn_pheno_test') -PassThru
$taskLaunch=@{
  processId=$taskStarted.Id;
  launchedAt=(Get-Date).ToUniversalTime().ToString('o');
  userDirectory=$taskProof.userDirectory;
  workingDirectory=(Split-Path -Parent $Client);
  hakSha256=$taskProof.hakSha256;
  moduleSha256=$taskProof.moduleSha256;
  fixtureReceiptSha256=$ReceiptSha256;
  preflight=$taskPreflight;
  clientSha256=$taskProof.clientSha256;
  directLoad='+TestNewModule srn_pheno_test'
}
$taskLaunch | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath (Join-Path $taskStage ('client-launch-'+$taskStarted.Id+'.json'))
$taskLaunch | ConvertTo-Json
