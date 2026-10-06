param(
  [string]$BaseSha = '',
  [string]$HeadSha = 'HEAD'
)
# Decide whether a change touches item import and therefore needs Test-ItemImportTools.ps1.
# Prints run=true|false (also to GITHUB_OUTPUT when present). Fails safe: a missing,
# all-zero or undiffable base runs the regressions.
$ErrorActionPreference = 'Stop'
$scope = @(
  '^tools/(Test-ItemImportTools|Import-Hak|Analyze-ItemHak|Analyze-ItemBlueprintErf|Stage-ItemMatches)\.ps1$',
  '^tools/(SrnHaks\.Common|SrnTools)\.psm1$',
  '^tools/(toolchain|shared-tools)\.lock\.json$',
  '^tools/import-profiles/',
  '^docs/imports/',
  '^srn_item/'
)
$run = $true
$reason = 'no comparable base; running item-import regressions'
if (-not [string]::IsNullOrWhiteSpace($BaseSha) -and $BaseSha -notmatch '^0+$') {
  $changed = @(git diff --name-only "$BaseSha...$HeadSha" 2>$null)
  if ($LASTEXITCODE -eq 0) {
    $matched = @($changed | Where-Object { $path = $_; $scope | Where-Object { $path -match $_ } })
    $run = $matched.Count -gt 0
    $reason = if ($run) { 'item-import paths changed: ' + ($matched -join ', ') } else { "no item-import paths among $($changed.Count) changed files" }
  }
}
Write-Host $reason
$line = 'run=' + $run.ToString().ToLowerInvariant()
Write-Output $line
if ($env:GITHUB_OUTPUT) { $line | Out-File -LiteralPath $env:GITHUB_OUTPUT -Encoding utf8 -Append }
