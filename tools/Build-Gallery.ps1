[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Toolchain,
    [Parameter(Mandatory)][string]$MigrationReceipt,
    [Parameter(Mandatory)][string]$Binding,
    [Parameter(Mandatory)][string]$OutputDirectory,
    [string]$Configuration = 'test-modules/srn_gallery/gallery.json'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Push-Location $repoRoot
try {
    Import-Module ./tools/SrnTools.psm1 -Force
    $chain = Get-Content -LiteralPath $Toolchain -Raw | ConvertFrom-Json
    $runtime = if ($chain.schemaVersion -eq 2) { $chain.runtimes.python } else { $chain.tools.python }
    $python = Resolve-SrnRuntime -Name python -Path $runtime.path -ExpectedSha256 $runtime.sha256
    $local = Get-Content -LiteralPath $Binding -Raw | ConvertFrom-Json
    $builder = Get-Content ./hakbuilder.json -Raw | ConvertFrom-Json
    $files = [System.Collections.Generic.List[string]]::new()
    foreach ($path in @($Configuration,$Binding,'hakbuilder.json',$PSCommandPath,'tools/heads/head_workflow.py','tools/phenotypes/tool_runtime.py','tools/shared_tools.py')) { $files.Add($path) }
    foreach ($path in Get-ChildItem tools/gallery -File -Filter '*.py') { $files.Add($path.FullName) }
    foreach ($path in Get-ChildItem tools/gallery/scripts -File -Filter '*.nss') { $files.Add($path.FullName) }
    foreach ($pack in $builder.HakList) {
        foreach ($path in Get-ChildItem -LiteralPath $pack.Path -File) { if (-not $path.Name.StartsWith('.')) { $files.Add($path.FullName) } }
    }
    foreach ($inputPin in $local.inputs) { $files.Add($inputPin.path) }
    foreach ($fixturePin in $local.fixtures) {
        $files.Add($fixturePin.path)
        $fixture = Get-Content -LiteralPath $fixturePin.path -Raw | ConvertFrom-Json
        $files.Add($fixture.config.path)
        $fixtureConfig = Get-Content -LiteralPath $fixture.config.path -Raw | ConvertFrom-Json
        foreach ($inputPin in $fixtureConfig.inputs) { $files.Add($inputPin.path) }
        foreach ($inputPin in $fixture.haks) { $files.Add($inputPin.path) }
        foreach ($name in @('bodyResources','target','rigAudit')) {
            if ($fixture.PSObject.Properties.Name -contains $name) {
                foreach ($inputPin in @($fixture.$name)) { $files.Add($inputPin.path) }
            }
        }
    }
    $destination = [System.IO.Path]::GetFullPath($OutputDirectory)
    if (Test-Path -LiteralPath $destination) { throw 'Use a fresh output directory for each gallery rebuild.' }
    New-Item -ItemType Directory -Path $destination | Out-Null
    $pins = @($files | Sort-Object -Unique | ForEach-Object {
        $path = (Get-Item -LiteralPath $_).FullName
        @{ path=$path; sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
    })
    $manifest = Join-Path $destination 'inputs.json'
    [System.IO.File]::WriteAllText($manifest,($pins | ConvertTo-Json -Depth 6)+"`n",[System.Text.UTF8Encoding]::new($false))
    & $python.path -B tools/phenotypes/launch_shared_tool.py --toolchain $Toolchain --migration-receipt $MigrationReceipt --tool python --output "$destination/launch" --input-manifest $manifest -- -B tools/gallery/build_gallery.py --repository $repoRoot --config $Configuration --binding $Binding --output "$destination/build"
    if ($LASTEXITCODE) { throw 'Gallery build failed; inspect the retained launch logs.' }
    $result = Get-Content -LiteralPath "$destination/build/build.json" -Raw | ConvertFrom-Json
    Copy-Item -LiteralPath $result.module.path -Destination ./output/srn_gallery.mod -Force
    Copy-Item -LiteralPath $result.testHak.path -Destination ./output/srn_gallery_test.hak -Force
    Write-Host 'Saved output/srn_gallery.mod and output/srn_gallery_test.hak. Client inspection remains pending.'
}
finally { Pop-Location }
