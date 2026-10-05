#Requires -Version 7.0
[CmdletBinding()]
param([Parameter(Mandatory)][string]$Worktree, [Parameter(Mandatory)][string]$Python, [string]$ToolsRoot)
Import-Module (Join-Path $PSScriptRoot 'SrnTools.psm1') -Force
$runtime=Resolve-SrnRealPath $Python
if ($runtime -match '(?i)[/\\]WindowsApps[/\\]') { throw 'Use the bundled workspace Python; Store shim is unsupported' }
Assert-SrnDurablePath $runtime
$root=(Get-SrnToolsRoot -ToolsRoot $ToolsRoot).path
& $runtime -B (Join-Path $PSScriptRoot 'shared_tools.py') --tools-root $root retirement $Worktree
if ($LASTEXITCODE) { throw 'Retirement audit failed' }
