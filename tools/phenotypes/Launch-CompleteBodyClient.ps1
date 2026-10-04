param(
  [Parameter(Mandatory=$true)][string]$Fixture,
  [Parameter(Mandatory=$true)][string]$ReceiptSha256,
  [Parameter(Mandatory=$true)][ValidateScript({Test-Path -LiteralPath $_ -PathType Leaf})][string]$Client,
  [Parameter(Mandatory=$true)][ValidateScript({Test-Path -LiteralPath $_ -PathType Leaf})][string]$WorkspacePython,
  [switch]$NoLaunch
)
$ErrorActionPreference='Stop'
$taskStage=(Resolve-Path -LiteralPath $Fixture).Path
$taskPreflight=Join-Path $taskStage ('client-preflight-'+[guid]::NewGuid().ToString('N')+'.json')
& $WorkspacePython (Join-Path $PSScriptRoot 'preflight_complete_body_client.py') --fixture $taskStage --receipt-sha256 $ReceiptSha256 --client $Client --output $taskPreflight
if ($LASTEXITCODE -ne 0) { throw 'Complete-body client preflight failed' }
$taskProof=Get-Content -LiteralPath $taskPreflight -Raw | ConvertFrom-Json
if ($NoLaunch) {
  $taskProof | ConvertTo-Json -Depth 10
  return
}
$taskRunning=@(Get-Process | Where-Object { $_.ProcessName -ieq 'nwmain' })
if ($taskRunning.Count -ne 0) { throw 'A client is already running; observe ownership before replacing it' }
# This is the explicitly authorized interactive game test window.
$taskStarted=Start-Process -FilePath $Client -WorkingDirectory (Split-Path -Parent $Client) -WindowStyle Normal -ArgumentList @('-userdirectory',('"'+$taskProof.userDirectory+'"'),'+TestNewModule','srn_pheno_test') -PassThru
$taskLaunch=@{processId=$taskStarted.Id;launchedAt=(Get-Date).ToUniversalTime().ToString('o');userDirectory=$taskProof.userDirectory;workingDirectory=(Split-Path -Parent $Client);hakSha256=$taskProof.hakSha256;moduleSha256=$taskProof.moduleSha256;fixtureReceiptSha256=$ReceiptSha256;preflight=$taskPreflight;preflightSha256=(Get-FileHash -LiteralPath $taskPreflight -Algorithm SHA256).Hash.ToLowerInvariant();launcherSha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();clientSha256=$taskProof.clientSha256;directLoad='+TestNewModule srn_pheno_test';cameraLocked=$false}
$taskLaunch | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskStage ('client-launch-'+$taskStarted.Id+'.json'))
$taskLaunch | ConvertTo-Json
