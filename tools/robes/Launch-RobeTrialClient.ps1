param(
  [Parameter(Mandatory=$true)][string]$FixtureReceipt,
  [Parameter(Mandatory=$true)][string]$Binding,
  [Parameter(Mandatory=$true)][string]$Output
)
# Launch the isolated robe-trial module (Windows PowerShell 5.1 compatible).
# Verifies the bound client bytes and package hashes, refuses to disturb a running client,
# and records a launch receipt. A launch is not client evidence.
$ErrorActionPreference='Stop'
if (Test-Path -LiteralPath $Output) { throw 'Fresh launch receipt required' }
$taskBinding=Get-Content -LiteralPath $Binding -Raw | ConvertFrom-Json
$taskClient=$taskBinding.runtimes.nwn
if ((Get-FileHash -LiteralPath $taskClient.path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskClient.sha256) { throw 'Bound NWN client bytes changed' }
$taskFixture=Get-Content -LiteralPath $FixtureReceipt -Raw | ConvertFrom-Json
foreach ($taskPin in @($taskFixture.hak,$taskFixture.module)) {
  if ((Get-FileHash -LiteralPath $taskPin.path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskPin.sha256) { throw "Packaged file changed: $($taskPin.path)" }
}
$taskOverride=Join-Path $taskFixture.userDirectory 'override'
if ((Test-Path $taskOverride) -and @(Get-ChildItem -LiteralPath $taskOverride).Count -ne 0) { throw 'Isolated override must be empty' }
if (@(Get-Process | Where-Object { $_.ProcessName -ieq 'nwmain' }).Count -ne 0) { throw 'A client is already running; not replacing another experiment' }
$taskModule=[IO.Path]::GetFileNameWithoutExtension($taskFixture.module.path)
$taskStarted=Start-Process -FilePath $taskClient.path -WorkingDirectory (Split-Path -Parent $taskClient.path) -WindowStyle Normal -ArgumentList @('-userdirectory',('"'+$taskFixture.userDirectory+'"'),'+TestNewModule',$taskModule) -PassThru
$taskLaunch=[ordered]@{kind='srn-robe-client-launch';processId=$taskStarted.Id;launchedAt=(Get-Date).ToUniversalTime().ToString('o');
  userDirectory=$taskFixture.userDirectory;client=$taskClient;module=$taskModule;
  binding=@{path=(Resolve-Path -LiteralPath $Binding).Path;sha256=(Get-FileHash -LiteralPath $Binding -Algorithm SHA256).Hash.ToLowerInvariant()};
  fixtureReceipt=@{path=(Resolve-Path -LiteralPath $FixtureReceipt).Path;sha256=(Get-FileHash -LiteralPath $FixtureReceipt -Algorithm SHA256).Hash.ToLowerInvariant()};
  hakSha256=$taskFixture.hak.sha256;moduleSha256=$taskFixture.module.sha256;
  launcherSha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();
  note='Launch receipt only; client evidence requires observed screenshots and logged actor rows.'}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Output) | Out-Null
$taskLaunch | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 -LiteralPath $Output
$taskLaunch | ConvertTo-Json -Depth 5
