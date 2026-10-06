param(
  [Parameter(Mandatory=$true)][string]$FixtureReceipt,
  [Parameter(Mandatory=$true)][string]$Binding,
  [Parameter(Mandatory=$true)][string]$Output
)
# Launch the isolated robe-trial module (Windows PowerShell 5.1 compatible).
# Hashes the bound client, binding, fixture receipt, HAK and module before dispatch, refuses to disturb
# a running client, waits for the session to end and re-verifies every launch input before writing
# the receipt, so screenshots and logs from the session are tied to bytes that stayed unchanged.
# A launch is not client evidence.
$ErrorActionPreference='Stop'
if (Test-Path -LiteralPath $Output) { throw 'Fresh launch receipt required' }
function Get-TaskPin([string]$Path) {
  @{path=(Resolve-Path -LiteralPath $Path).Path;sha256=(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
}
$taskBindingPin=Get-TaskPin $Binding
$taskFixturePin=Get-TaskPin $FixtureReceipt
$taskBinding=Get-Content -LiteralPath $Binding -Raw | ConvertFrom-Json
$taskClient=$taskBinding.runtimes.nwn
$taskFixture=Get-Content -LiteralPath $FixtureReceipt -Raw | ConvertFrom-Json
$taskPins=@(@{path=$taskClient.path;sha256=$taskClient.sha256},@{path=$taskFixture.hak.path;sha256=$taskFixture.hak.sha256},
  @{path=$taskFixture.module.path;sha256=$taskFixture.module.sha256},$taskBindingPin,$taskFixturePin)
function Test-TaskPins([string]$Stage) {
  foreach ($taskPin in $taskPins) {
    if ((Get-FileHash -LiteralPath $taskPin.path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskPin.sha256) { throw "Launch input changed ($Stage): $($taskPin.path)" }
  }
}
Test-TaskPins 'before launch'
$taskOverride=Join-Path $taskFixture.userDirectory 'override'
if ((Test-Path -LiteralPath $taskOverride) -and @(Get-ChildItem -LiteralPath $taskOverride).Count -ne 0) { throw 'Isolated override must be empty' }
if (@(Get-Process | Where-Object { $_.ProcessName -ieq 'nwmain' }).Count -ne 0) { throw 'A client is already running; not replacing another experiment' }
$taskModule=[IO.Path]::GetFileNameWithoutExtension($taskFixture.module.path)
$taskLauncher=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
$taskStarted=Start-Process -FilePath $taskClient.path -WorkingDirectory (Split-Path -Parent $taskClient.path) -WindowStyle Normal -ArgumentList @('-userdirectory',('"'+$taskFixture.userDirectory+'"'),'+TestNewModule',$taskModule) -PassThru
$taskLaunchedAt=(Get-Date).ToUniversalTime().ToString('o')
$taskStarted.WaitForExit()
Test-TaskPins 'after the client session'
$taskLaunch=[ordered]@{kind='srn-robe-client-launch';processId=$taskStarted.Id;launchedAt=$taskLaunchedAt;
  exitedAt=(Get-Date).ToUniversalTime().ToString('o');exitCode=$taskStarted.ExitCode;
  userDirectory=$taskFixture.userDirectory;client=$taskClient;module=$taskModule;
  binding=$taskBindingPin;fixtureReceipt=$taskFixturePin;
  hakSha256=$taskFixture.hak.sha256;moduleSha256=$taskFixture.module.sha256;launcherSha256=$taskLauncher;
  inputsVerifiedAfterSession=$true;
  note='Launch receipt only; client evidence requires observed screenshots and logged actor rows.'}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Output) | Out-Null
$taskLaunch | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 -LiteralPath $Output
$taskLaunch | ConvertTo-Json -Depth 5
