param(
  [ValidateSet('Motion','Gameplay','Kneel')][string]$Mode='Motion',
  [switch]$NoLaunch
)
$ErrorActionPreference='Stop'
$taskFixture=Join-Path $PSScriptRoot 'client-fourteen-skin3-motion-v2'
if (@(Get-Process | Where-Object { $_.ProcessName -ieq 'nwmain' }).Count -ne 0) {
  throw 'Close the running NWN client before selecting another isolated test.'
}
$taskCases=@{
  Motion=@{pid=26740;receipt='ce27e69d4a30fe82a164cb81afda1746fe045301ab23722704fca585918b933b';module='6fbe425671c9317f2e3f6da08fd7de118963b3f4005bf033a79b4689978ee079'}
  Gameplay=@{pid=40868;receipt='78beba25081d47250efc0462a4c439a19dbb8e00a58642ea79b13d4c9381cb9e';module='9a25dc111eccc0c363b242ed393c6dd6518bd0c402acc029e67be8e36c471b0d'}
  Kneel=@{pid=48948;receipt='e8dfb9ad08b3c57fd5e6b26a2e564695ebea9004810263594c69362599b43633';module='dbf696bf7e5c305026e2015c45d62d06b42ba02c4237b14a9cf45eaa51cfe7cc'}
}
$taskCase=$taskCases[$Mode]
$taskArchive=Join-Path $taskFixture ('client-evidence-run-'+$taskCase.pid)
$taskReceipt=Join-Path $taskArchive 'receipt.json'
$taskModule=Join-Path $taskFixture ('build-archive\'+$taskCase.module+'\srn_pheno_test.mod')
$taskHak=Join-Path $taskFixture 'userdir\hak\srn_pheno_test.hak'
foreach($taskPin in @(@{path=$taskReceipt;hash=$taskCase.receipt},@{path=$taskModule;hash=$taskCase.module},@{path=$taskHak;hash='1af9fe160af8be024c3ffe761a2c7dd746a89eee3c1d7ad5117cd09e5b8ac245'})) {
  if ((Get-FileHash -LiteralPath $taskPin.path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskPin.hash) {
    throw ('Frozen tested input changed: '+$taskPin.path)
  }
}
Copy-Item -LiteralPath $taskModule -Destination (Join-Path $taskFixture 'userdir\modules\srn_pheno_test.mod') -Force
Copy-Item -LiteralPath $taskReceipt -Destination (Join-Path $taskFixture 'test-module\receipt.json') -Force
$taskSelection=@{selectedAt=[DateTime]::UtcNow.ToString('o');mode=$Mode;testedProcessId=$taskCase.pid;fixtureReceiptSha256=$taskCase.receipt;moduleSha256=$taskCase.module;hakSha256='1af9fe160af8be024c3ffe761a2c7dd746a89eee3c1d7ad5117cd09e5b8ac245';launched=$false}
$taskSelection|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $PSScriptRoot 'client-fixture-selection.json') -Encoding UTF8
if(-not $NoLaunch) {
  $taskWorkspace=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
  & (Join-Path $taskWorkspace 'tools\phenotypes\Launch-CompleteBodyClient.ps1') -Fixture $taskFixture -ReceiptSha256 $taskCase.receipt
}
