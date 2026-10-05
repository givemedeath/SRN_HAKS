param(
  [Parameter(Mandatory=$true)][string]$Fixture,
  [Parameter(Mandatory=$true)][string]$ReceiptSha256,
  [Parameter(Mandatory=$true)][ValidateScript({Test-Path -LiteralPath $_ -PathType Leaf})][string]$Client,
  [Parameter(Mandatory=$true)][ValidateScript({Test-Path -LiteralPath $_ -PathType Leaf})][string]$WorkspacePython,
  [switch]$NoLaunch
)
$ErrorActionPreference='Stop'
Import-Module (Join-Path (Split-Path $PSScriptRoot -Parent) 'SrnTools.psm1') -Force
$taskPython=Resolve-SrnRuntime -Name python -Path $WorkspacePython
$taskClient=Resolve-SrnRuntime -Name nwn -Path $Client
$WorkspacePython=$taskPython.path; $Client=$taskClient.path
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; $env:PYTHONDONTWRITEBYTECODE='1'
$taskStage=(Resolve-Path -LiteralPath $Fixture).Path
$taskPreflight=Join-Path $taskStage ('client-preflight-'+[guid]::NewGuid().ToString('N')+'.json')
& $WorkspacePython (Join-Path $PSScriptRoot 'preflight_complete_body_client.py') --fixture $taskStage --receipt-sha256 $ReceiptSha256 --client $Client --output $taskPreflight
if ($LASTEXITCODE -ne 0) { throw 'Complete-body client preflight failed' }
$null=Resolve-SrnRuntime -Name python -Path $WorkspacePython -ExpectedSha256 $taskPython.sha256
$null=Resolve-SrnRuntime -Name nwn -Path $Client -ExpectedSha256 $taskClient.sha256
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
$taskLaunch.pythonRuntime=$taskPython
$taskLaunch | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath (Join-Path $taskStage ('client-launch-'+$taskStarted.Id+'.json'))
$taskLaunch | ConvertTo-Json
