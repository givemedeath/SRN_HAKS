param(
  [Parameter(Mandatory=$true)][string]$OutputDirectory,
  [Parameter(Mandatory=$true)][ValidateScript({Test-Path -LiteralPath $_ -PathType Container})][string]$ComfyRoot,
  [Parameter(Mandatory=$true)][string]$SharedRoot
)
$ErrorActionPreference='Stop'
$service='http://127.0.0.1:8188'
$source=Join-Path $PSScriptRoot 'comfy_nodes/srn_orthographic_multiview/__init__.py'
$ComfyRoot=[IO.Path]::GetFullPath($ComfyRoot,$PWD.ProviderPath);$SharedRoot=[IO.Path]::GetFullPath($SharedRoot,$PWD.ProviderPath)
$customRoot=Join-Path $ComfyRoot 'custom_nodes'
$target=[IO.Path]::GetFullPath((Join-Path $customRoot 'srn_orthographic_multiview'))
if (-not $target.StartsWith($customRoot+[IO.Path]::DirectorySeparatorChar)) { throw 'Unexpected install target' }
if (Test-Path -LiteralPath $target) { throw 'Fresh additive node target required; inspect prior install instead' }
$queue=Invoke-RestMethod -Uri "$service/queue"
if ($queue.queue_running.Count -or $queue.queue_pending.Count) { throw 'ComfyUI queue occupied; do not restart' }
$stats=Invoke-RestMethod -Uri "$service/system_stats"
$shared=[WildcardPattern]::Escape($SharedRoot.TrimEnd('\','/'))
if (($stats.system.argv -join ' ') -notlike "*ComfyUI*main.py*--input-directory $shared\input*--output-directory $shared\output*") { throw 'Different service launch; reobserve' }
$pins=@{
 'comfy/ldm/trellis2/model.py'='BAA8B081DE2EADA84754B867282BD21D498233816326F8842943857FE1D07E0C'
 'comfy_extras/nodes_trellis2.py'='5D99F8FD2D1A1CC252B860D941717FC4E53CFBC48B623730C9FDD9139DD7F98C'
}
foreach($entry in $pins.GetEnumerator()) { if((Get-FileHash -LiteralPath (Join-Path $ComfyRoot $entry.Key) -Algorithm SHA256).Hash -ne $entry.Value) { throw 'Unreviewed ComfyUI source version' } }
$out=[IO.Path]::GetFullPath($OutputDirectory,$PWD.ProviderPath)
if (Test-Path -LiteralPath $out) { throw 'Fresh install receipt directory required' }
New-Item -ItemType Directory -Path $out | Out-Null
New-Item -ItemType Directory -Path $target | Out-Null
Copy-Item -LiteralPath $source -Destination (Join-Path $target '__init__.py')
$digest=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
if ((Get-FileHash -LiteralPath (Join-Path $target '__init__.py') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $digest) { throw 'Node copy differs' }
$record=@{schemaVersion=1;target=$target;source=$source;sha256=$digest;queueBefore=$queue;systemBefore=$stats;coreFilesEdited=$false;restartRequested=$true;installedSelfTestsPending=$true;newGenerationSubmitted=$false}
$record | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $out 'installation.json')
try {
 Invoke-RestMethod -Method Post -Uri "$service/v2/manager/reboot" -ContentType 'application/json' -Body '{}' | Out-Null
 $record.restartRequestResult='returned'
} catch {
 $record.restartRequestResult=$_.Exception.Message
}
$record | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $out 'installation.json')
$record | Select-Object target,sha256,coreFilesEdited,restartRequestResult | ConvertTo-Json
