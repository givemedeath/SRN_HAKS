param(
  [Parameter(Mandatory=$true)][ValidateScript({Test-Path -LiteralPath $_ -PathType Leaf})][string]$TargetContract,
  [Parameter(Mandatory=$true)][string]$Fixture,
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{64}$')][string]$ReceiptSha256,
  [Parameter(Mandatory=$true)][ValidateScript({Test-Path -LiteralPath $_ -PathType Leaf})][string]$Client,
  [Parameter(Mandatory=$true)][ValidateScript({Test-Path -LiteralPath $_ -PathType Leaf})][string]$WorkspacePython,
  [Parameter(Mandatory=$true)][ValidateScript({Test-Path -LiteralPath $_ -PathType Leaf})][string]$Toolchain,
  [Parameter(Mandatory=$true)][ValidateScript({Test-Path -LiteralPath $_ -PathType Leaf})][string]$MigrationReceipt,
  [switch]$NoLaunch
)
$ErrorActionPreference='Stop'
$taskStage=(Resolve-Path -LiteralPath $Fixture).Path
$taskTarget=(Resolve-Path -LiteralPath $TargetContract).Path
$taskPython=(Resolve-Path -LiteralPath $WorkspacePython).Path
$taskClient=(Resolve-Path -LiteralPath $Client).Path
if ($taskPython -match '[\\/]WindowsApps[\\/]') { throw 'Use the bundled workspace Python; Windows Store shims are unsupported' }
$taskPreflight=Join-Path $taskStage ('client-preflight-'+[guid]::NewGuid().ToString('N')+'.json')
# Keep helper snapshots short enough for Windows paths. Historical evidence stays intact.
$taskRepo=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$taskTemp=Join-Path $taskRepo '.tmp'
[System.IO.Directory]::CreateDirectory($taskTemp) | Out-Null
$taskPrefix=Join-Path $taskTemp ('hf-client-'+[guid]::NewGuid().ToString('N'))
$taskDispatch=$taskPrefix+'-launch'
$taskAdapter=$taskPrefix+'-argv.py'
$taskRequest=$taskPrefix+'-request.json'
$taskInputs=$taskPrefix+'-inputs.json'
# The adapter builds repeated --input arguments in-process to avoid Windows argv limits.
# It declares the exact preflight file reads, not an opaque historical directory scan.
$taskAdapterSource=@'
import ast
import hashlib
import json
from pathlib import Path
import re
import runpy
import sys

request_path = Path(sys.argv[1]).resolve()
request = json.loads(request_path.read_text(encoding="utf-8-sig"))
inputs = {}
helper_edges = {}

def add(path, expected=None):
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError("Consumed input must be a file: " + str(path))
    hasher = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    if expected is not None and (not isinstance(expected, str) or
            not re.fullmatch(r"[a-f0-9]{64}", expected) or digest != expected):
        raise ValueError("Declared consumed input changed: " + str(path))
    if str(path) in inputs and inputs[str(path)] != digest:
        raise ValueError("Consumed input changed during preparation: " + str(path))
    inputs[str(path)] = digest
    return path

def read(path, expected=None):
    return json.loads(add(path, expected).read_text(encoding="utf-8"))

def pinned(entry):
    return add(entry["path"], entry["sha256"])

def frozen(value):
    pins = value.get("frozenInputs", {})
    if not isinstance(pins, dict):
        raise ValueError("Consumed frozenInputs must be an explicit path/hash mapping")
    for path, expected in pins.items():
        add(path, expected)

def flat(folder):
    folder = Path(folder).resolve(strict=True)
    if not folder.is_dir():
        raise ValueError("Consumed resource directory missing: " + str(folder))
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            raise ValueError("Flat consumed resource directory required: " + str(folder))
        add(path)

def helpers(entry):
    roots = (entry.parent, entry.parent.parent)
    pending = [entry]
    seen = set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        add(path)
        imports = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        edges = []
        for name in sorted(imports):
            choices = [root / (name + ".py") for root in roots]
            found = next((choice.resolve() for choice in choices if choice.is_file()), None)
            if found is not None:
                edges.append(str(found))
                pending.append(found)
        helper_edges[str(path)] = edges

def native(folder, composition):
    folder = Path(folder).resolve(strict=True)
    if composition:
        frozen(read(folder / "conversion.json"))
    read(folder / "native-compile.json")
    flat(folder / "ascii")
    flat(folder / "resources")


def animation_overlay(entry):
    # These are the documented direct reads of target_animation_overlay.py.
    # Historical frozenInputs claims inside its evidence are not consumed here.
    overlay = read(pinned(entry))
    if overlay.get("kind") == "executed-shared-female-source-native-idle-overlay":
        helpers(Path(request["preflight"]).parent / "shared_female_animation_overlay.py")
        from shared_female_animation_overlay import collect_overlay_inputs
        for path, expected in collect_overlay_inputs(entry, request["targetContract"]).items():
            add(path, expected)
        return
    for key in ("compile", "preparation", "rangePlan", "restoration", "independentReview",
                "sourceRoot", "sourceNativeOwner", "numericCorrectedArrays"):
        pinned(overlay[key])
    for pin in overlay["resources"].values():
        pinned(pin)
    compilation = read(pinned(overlay["compile"]))
    pinned(compilation["native"])
    pinned(compilation["execution"])

entry = Path(request["preflight"]).resolve(strict=True)
sys.path[:0] = [str(entry.parent), str(entry.parent.parent)]
helpers(entry)
add(request["launcher"])
add(__file__)
add(request_path)
add(request["client"])
target = read(request["targetContract"])
frozen(target)
stock_exact = target.get("rig", {}).get("mode") == "stock-exact"
if stock_exact:
    proof = read(pinned(target["rig"]["stockReferenceReceipt"]))
    frozen(proof)
    pinned(proof["rootAscii"])
stage = Path(request["fixture"]).resolve(strict=True)
build = read(stage / "test-module" / "receipt.json", request["receiptSha256"])
if "animationOverlay" in build:
    animation_overlay(build["animationOverlay"])
if 'transitionSourceProof' in build or 'transitionAnimationAuthority' in build:
    if 'transitionSourceProof' not in build or 'transitionAnimationAuthority' not in build:
        raise ValueError('Complete transition proof/animation authority required')
    helpers(Path(request['preflight']).parent / 'shared_female_transition_fixture.py')
    from shared_female_transition_fixture import collect_source_inputs
    for path, expected in collect_source_inputs(build['transitionSourceProof'], request['targetContract']).items():
        add(path, expected)
    pinned(build['transitionAnimationAuthority'])
    pinned(build['sourcePreparation'])

if 'postureStockBinding' in build and 'postureRoster' not in build:
    raise ValueError('Stock posture binding requires its declared roster')
if "postureRoster" in build:
    if 'postureStockBinding' not in build:
        raise ValueError('Shared posture roster requires its installed stock binding')
    helpers(Path(request["preflight"]).parent / "shared_female_posture_fixture.py")
    from shared_female_posture_fixture import verify_roster
    roster = verify_roster(build["postureRoster"], request["targetContract"])
    for path, expected in roster["frozenInputs"].items():
        add(path, expected)
    helpers(Path(request["preflight"]).parent / "shared_female_stock_basis.py")
    from shared_female_stock_basis import collect_stock_basis_inputs
    for path, expected in collect_stock_basis_inputs(build["postureStockBinding"], request["targetContract"], build["postureRoster"]).items():
        add(path, expected)
for key in ("hak", "module", "gffTool", "resmanTool"):
    if key in build:
        add(build[key], build[key + "Sha256"])
for pin in build.get("stockTableBaselines", {}).values():
    pinned(pin)
if "equipmentSelection" in build:
    equipment = read(pinned(build["equipmentSelection"]))
    if stock_exact:
        frozen(equipment)
if build.get("bodyConverted"):
    native(build["bodyConverted"], True)
if not stock_exact:
    for key in ("rigConverted", "provisionalConverted"):
        if build.get(key):
            native(build[key], False)
    if build.get("validationScope") != "full" and build.get("stockConverted"):
        native(build["stockConverted"], False)
flat(stage / "test-module" / "hak-resources")
flat(stage / "test-module" / "module-resources")
add(stage / "userdir" / "nwn.ini")
manifest = Path(request["inputManifest"])
manifest.write_text(json.dumps({"schemaVersion":1, "kind":"target-client-preflight-consumed-inputs",
    "inputs":inputs, "repositoryLocalImportEdges":helper_edges,
    "targetContract":request["targetContract"], "fixtureReceiptSha256":request["receiptSha256"],
    "clientLaunched":False}, indent=2) + "\n", encoding="utf-8")
add(manifest)
argv = ["--toolchain", request["toolchain"], "--migration-receipt", request["migrationReceipt"],
        "--tool", "python", "--output", request["dispatch"]]
for path in sorted(inputs):
    argv += ["--input", path]
argv += ["--", "-B", str(entry), "--target-contract", request["targetContract"],
         "--fixture", request["fixture"], "--receipt-sha256", request["receiptSha256"],
         "--client", request["client"], "--output", request["output"]]
shared = Path(request["sharedLauncher"]).resolve(strict=True)
sys.path.insert(0, str(shared.parent.parent))
sys.path.insert(0, str(shared.parent))
sys.argv = [str(shared), *argv]
runpy.run_path(str(shared), run_name="__main__")
'@
[System.IO.File]::WriteAllText($taskAdapter,$taskAdapterSource,[System.Text.UTF8Encoding]::new($false))
$taskConfiguration=@{
  launcher=$PSCommandPath;sharedLauncher=(Join-Path $PSScriptRoot 'launch_shared_tool.py')
  preflight=(Join-Path $PSScriptRoot 'preflight_target_body_client.py')
  targetContract=$taskTarget;fixture=$taskStage;receiptSha256=$ReceiptSha256;client=$taskClient
  toolchain=(Resolve-Path -LiteralPath $Toolchain).Path;migrationReceipt=(Resolve-Path -LiteralPath $MigrationReceipt).Path
  dispatch=$taskDispatch;output=$taskPreflight;inputManifest=$taskInputs
}
[System.IO.File]::WriteAllText($taskRequest,($taskConfiguration | ConvertTo-Json -Depth 10),[System.Text.UTF8Encoding]::new($false))
& $taskPython -B $taskAdapter $taskRequest | Out-Null
if ($LASTEXITCODE -ne 0) { throw ('Target-body client preflight failed; inspect '+$taskDispatch+' and '+$taskRequest) }
$taskProof=Get-Content -LiteralPath $taskPreflight -Raw | ConvertFrom-Json
$taskBuildPath=Join-Path $taskStage 'test-module/receipt.json'
if ((Get-FileHash -LiteralPath $taskBuildPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ReceiptSha256) { throw 'Fixture receipt changed after preflight' }
$taskBuild=Get-Content -LiteralPath $taskBuildPath -Raw | ConvertFrom-Json
if ($taskProof.pass -ne $true -or $taskProof.fixtureReceiptSha256 -ne $ReceiptSha256 -or $taskProof.targetContractSha256 -ne (Get-FileHash -LiteralPath $taskTarget -Algorithm SHA256).Hash.ToLowerInvariant()) { throw 'Preflight proof is incomplete or belongs to another target/fixture' }
$taskModule=$taskProof.moduleName
if ($taskModule -cnotmatch '^[a-z0-9_]{1,16}$' -or $taskBuild.moduleName -cne $taskModule -or [System.IO.Path]::GetFileNameWithoutExtension($taskBuild.module) -cne $taskModule) { throw 'Preflight module name differs from the declared fixture' }
foreach ($taskKind in @('hak','module')) {
  $taskExpected=$taskProof.($taskKind+'Sha256')
  if ($taskExpected -cne $taskBuild.($taskKind+'Sha256') -or (Get-FileHash -LiteralPath $taskBuild.$taskKind -Algorithm SHA256).Hash.ToLowerInvariant() -cne $taskExpected) { throw ('Fixture '+$taskKind+' changed after preflight') }
}
if ((Get-FileHash -LiteralPath $taskClient -Algorithm SHA256).Hash.ToLowerInvariant() -cne $taskProof.clientSha256) { throw 'Client changed after preflight' }
if ($NoLaunch) { $taskProof | ConvertTo-Json -Depth 20; return }
$taskRunning=@(Get-Process | Where-Object { $_.ProcessName -ieq 'nwmain' })
if ($taskRunning.Count -ne 0) { throw 'A client is already running; observe ownership before replacing it' }
# This is the explicitly authorized interactive game test window.
$taskStarted=Start-Process -FilePath $taskClient -WorkingDirectory (Split-Path -Parent $taskClient) -WindowStyle Normal -ArgumentList @('-userdirectory',('"'+$taskProof.userDirectory+'"'),'+TestNewModule',$taskModule) -PassThru
$taskLaunch=@{processId=$taskStarted.Id;launchedAt=(Get-Date).ToUniversalTime().ToString('o');targetContract=$taskTarget;targetContractSha256=$taskProof.targetContractSha256;userDirectory=$taskProof.userDirectory;workingDirectory=(Split-Path -Parent $taskClient);hakSha256=$taskProof.hakSha256;moduleSha256=$taskProof.moduleSha256;moduleName=$taskModule;fixtureReceiptSha256=$ReceiptSha256;preflight=$taskPreflight;preflightSha256=(Get-FileHash -LiteralPath $taskPreflight -Algorithm SHA256).Hash.ToLowerInvariant();verifiedToolLaunch=$taskDispatch;consumedInputManifest=$taskInputs;consumedInputManifestSha256=(Get-FileHash -LiteralPath $taskInputs -Algorithm SHA256).Hash.ToLowerInvariant();launcherSha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();clientSha256=$taskProof.clientSha256;directLoad=('+TestNewModule '+$taskModule);cameraLocked=$false}
$taskLaunch | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskStage ('client-launch-'+$taskStarted.Id+'.json'))
$taskLaunch | ConvertTo-Json
