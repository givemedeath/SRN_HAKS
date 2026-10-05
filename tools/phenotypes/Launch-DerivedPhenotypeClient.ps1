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

& $WorkspacePython (Join-Path $PSScriptRoot 'preflight_derived_dwarf_client.py')
if ($LASTEXITCODE -ne 0) { throw 'Derived-phenotype client preflight failed' }

$taskPreflightSrc=Join-Path (Split-Path (Split-Path $taskStage -Parent) -Parent) 'derived-dwarf-male-v1/review/client-preflight-receipt.json'
if (-not (Test-Path -LiteralPath $taskPreflightSrc)) {
  $taskPreflightSrc=Join-Path $taskStage 'client-preflight-receipt.json'
}
Copy-Item -LiteralPath $taskPreflightSrc -Destination $taskPreflight
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
