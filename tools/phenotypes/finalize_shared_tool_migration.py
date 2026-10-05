"""Bind a local shared-tool migration to freshly executed, byte-verified smokes.

This verifies CLI/tool behavior and one stock ASCII import. It never accepts
production equipment profiles, body candidates, or the game client.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from shared_toolchain import load, sha
from shared_tools import worktrees,inside,tools_root


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def entry(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': sha(path)}


def verify_pin(pin):
    require(sha(pin['path']) == pin['sha256'], 'Frozen verification input changed: ' + pin['path'])


def fixture_declaration(inputs, equipment, inventory):
    """Fixture identity is declared before dispatch, never inferred from count."""
    declaration=inputs.get('equipmentFixtures')
    require(isinstance(declaration,list) and declaration, 'Declared equipment fixtures required')
    names=[Path(row['fixturePath']).name for row in equipment['fixtures']]
    require(len(names)==len(set(names)) and set(names)==set(declaration)
            and len(declaration)==len(set(declaration)), 'Equipment fixture declaration differs')
    require(inventory['sourcePrefix']==inputs['sourcePrefix'] and inventory['overridesDisabled'] is True,
            'Declared stock equipment prefix/override isolation differs')


def verify_launch(folder, tool, config, toolchain):
    config = Path(config).resolve()
    folder = Path(folder).resolve()
    path = folder / 'launch.json'
    report = read(path)
    require(report.get('kind') == 'verified-shared-tool-launch' and report.get('tool') == tool
            and report.get('exitCode') == 0 and report.get('inputsUnchanged',True) is True,
            'Fresh successful smoke launch required: ' + str(folder))
    require(report.get('preMigrationSmoke') is True and report.get('migrationReceipt') is None,
            'Migration must use fresh pre-migration execution')
    require(Path(report['toolchain']).resolve() == config and report['toolchainSha256'] == sha(config),
            'Smoke belongs to another toolchain')
    require(report['toolBinary'] == toolchain['tools'][tool], 'Smoke used another executable')
    require(Path(report['command'][0]).resolve() == Path(report['toolBinary']['path']).resolve(),
            'Smoke command executable differs')
    for name, expected in report['frozenInputs'].items():
        verify_pin({'path': name, 'sha256': expected})
    for value in report['helperSnapshots'].values():
        verify_pin({'path': value['snapshot'], 'sha256': value['sha256']})
    require(sha(folder / 'stdout.log') == report['stdoutSha256']
            and sha(folder / 'stderr.log') == report['stderrSha256'], 'Smoke logs changed')
    return report


def finalize(config, verification_dir, output):
    config, root, output = Path(config).resolve(), Path(verification_dir).resolve(), Path(output).resolve()
    require(not output.exists(), 'Fresh immutable migration receipt required')
    toolchain = load(config,required=['python','blender','armory'])
    inputs = read(root / 'input-pins.json')
    require(Path(inputs['toolchain']['path']).resolve() == config, 'Verification inputs belong to another configuration')
    verify_pin(inputs['toolchain']); verify_pin(inputs['toolchainInitialSnapshot'])
    for value in inputs['launchHelpers'].values():
        verify_pin({'path': value['snapshot'], 'sha256': value['snapshotSha256']})
    for name, value in inputs['launchHelpers'].items():
        verify_pin({'path': name, 'sha256': value['sha256']})
    for value in inputs['preservedHistoricalReceipts']:
        verify_pin(value)
    for name in ('stockAscii', 'equipmentInventory'):
        verify_pin(inputs[name])
    saved = inputs['blenderSavedPreferencesBefore']; prefs = Path(saved['path'])
    require(prefs.exists() == saved['exists'] and (sha(prefs) if prefs.is_file() else None) == saved['sha256'],
            'Saved Blender preferences changed during verification')
    launches = {
        'pythonCli': ('python-cli-smoke', 'python'),
        'armoryCli': ('armory-cli-smoke', 'armory'),
        'blenderImportLaunch': ('blender-import-smoke', 'blender'),
        'armoryEquipmentLaunch': ('armory-equipment-launch', 'python'),
    }
    reports = {name: verify_launch(root / folder, tool, config, toolchain)
               for name, (folder, tool) in launches.items()}
    python = read(root / 'python-cli-smoke/stdout.log')
    require(Path(python['executable']).resolve() == Path(toolchain['tools']['python']['path']).resolve(),
            'Python smoke used another interpreter')
    armory_version = (root / 'armory-cli-smoke/stdout.log').read_text(encoding='utf-8').strip()
    require(armory_version == 'nwnarmory 1.3.4', 'Pinned Armory CLI version differs')
    imported = read(root / 'blender-import.json')
    require(imported.get('kind') == 'shared-blender-import-smoke' and imported['background'] is True
            and imported['result'] == ['FINISHED'] and imported['sourceChanged'] is False
            and imported['enabledAndLoaded'] == [True, True], 'Fresh Blender stock import failed')
    require(entry(imported['source']) == inputs['stockAscii']
            and imported['sourceSha256'] == inputs['stockAscii']['sha256'], 'Declared stock import source differs')
    require(imported['importedMeshes'] and all(row['vertices'] > 0 and row['faces'] > 0
            for row in imported['importedMeshes']), 'No usable imported stock mesh')
    bootstrap = read(root / 'blender-import-smoke/loaded-addons.json')
    require(bootstrap.get('kind') == 'shared-blender-addon-bootstrap'
            and bootstrap['factoryStartup'] is True and bootstrap['preferencesChanged'] is False
            and bootstrap['savedPreferencesChanged'] is False and bootstrap['migrationReceipt'] is None,
            'Factory shared addon bootstrap required')
    require(Path(bootstrap['toolchain']).resolve() == config and bootstrap['toolchainSha256'] == sha(config),
            'Bootstrap belongs to another toolchain')
    addon_root = Path(toolchain['addons']['root']).resolve()
    modules = bootstrap['loadedModules']
    require(modules and len({row['module'] for row in modules}) == len(modules), 'Unique actually loaded addon modules required')
    for row in modules:
        path = Path(row['path']).resolve()
        require(path.is_relative_to(addon_root), 'Loaded addon escaped pinned shared bank')
        relative = path.relative_to(addon_root).as_posix()
        require(toolchain['addons']['files'].get(relative) == row['sha256'] == sha(path), 'Loaded addon bytes differ')
    require(imported['actuallyLoadedAddon'] == str(addon_root / 'neverblender/__init__.py')
            and imported['loadedAddonSha256'] == sha(imported['actuallyLoadedAddon']), 'Import addon origin differs')
    command = reports['blenderImportLaunch']['command']
    require('--factory-startup' in command and '-b' in command, 'Isolated Blender startup command required')
    equipment = read(root / 'equipment-smoke/proof.json')
    inventory = read(inputs['equipmentInventory']['path'])
    fixture_declaration(inputs,equipment,inventory)
    require(equipment['sourceInventory'] == inputs['equipmentInventory']
            and equipment['armorySha256'] == toolchain['tools']['armory']['sha256'], 'Armory equipment proof input differs')
    require(equipment['dryRunExitCode'] == equipment['batchExitCode'] == 0
            and equipment['collisionExitCode'] == equipment['partialBatchExitCode'] == 1
            and equipment['existingOutputsPreserved'] is True and equipment['partialBatchAcceptanceBlocked'] is True,
            'Armory success/collision/partial-batch behavior differs')
    require(equipment['profilesAccepted'] is False and equipment['clientAccepted'] is False,
            'Tool smoke cannot accept production equipment')
    verify_pin({'path': equipment['profilePath'], 'sha256': equipment['profileSha256']})
    for row in equipment['fixtures']:
        for field in ('source', 'fixture'):
            verify_pin({'path': row[field+'Path'], 'sha256': row[field+'Sha256']})
        verify_pin({'path': row['correctedPath'], 'sha256': row['correction']['correctedSha256']})
        verify_pin({'path': str(root / 'equipment-smoke/raw' / Path(row['fixturePath']).name), 'sha256': row['rawSha256']})
        require(row['fitExitCode'] == 0 and all(value <= 1e-5 for value in row['fitResiduals'])
                and row['correction']['maximumWorldTransformError'] <= 1e-5
                and row['correction']['vertexOrderTopologyUvsMaterialsPreserved'] is True,
                'Armory fixture verification failed')
    smoke_paths = {name: root / folder / 'launch.json' for name, (folder, _) in launches.items()}
    smoke_paths.update(blenderImport=root / 'blender-import.json',
                       blenderActuallyLoadedAddons=root / 'blender-import-smoke/loaded-addons.json',
                       armoryEquipment=root / 'equipment-smoke/proof.json')
    frozen_files = {str(path): sha(path) for folder, _ in launches.values()
                    for path in (root / folder).rglob('*') if path.is_file()}
    frozen_files.update({str(path): sha(path) for path in (root / 'equipment-smoke').rglob('*') if path.is_file()})
    frozen_files[str(root / 'blender-import.json')] = sha(root / 'blender-import.json')
    core = {'shared_toolchain.py', 'launch_shared_tool.py', 'bootstrap_shared_blender_addons.py'}
    helpers = {name: value for name, value in inputs['launchHelpers'].items() if Path(name).name in core}
    active = Path(inputs['activeWorktree']).resolve()
    require(all(Path(name).resolve().is_relative_to(active) for name in helpers), 'Active launcher helpers must belong to this worktree')
    linked=[Path(row['path']) for row in worktrees(active)[1:] if Path(row['path'])!=active]
    verification_sources=[inputs['stockAscii']['path'],inputs['equipmentInventory']['path'],
                          *[row['sourcePath'] for row in equipment['fixtures']]]
    borrowed=sorted(set(path for path in verification_sources if any(inside(path,root) for root in linked)))
    shared_root,_=tools_root(active,toolchain.get('toolsRoot'))
    report = {'schemaVersion': 1, 'kind': 'phenotype-shared-tool-migration',
        'toolsRoot':str(shared_root),'inventorySha256':sha(active/'tools/shared-tools.lock.json'),
        'createdUtc': datetime.now(timezone.utc).isoformat(), 'activeWorktree': str(active),
        'retiringWorktree': toolchain.get('retiringWorktree'), 'toolchain': entry(config),
        'toolchainInitialSnapshot': inputs['toolchainInitialSnapshot'], 'verificationInputs': entry(root / 'input-pins.json'),
        'tools': {**toolchain['tools'], 'versions': {'python': python['version'], 'armory': armory_version,
                                                  'blender': imported['blenderVersion']}},
        'addons': {**toolchain['addons'], 'version': imported['neverblenderVersion'],
                   'sourceFileCount': len(toolchain['addons']['files']), 'actuallyLoadedModuleCount': len(modules)},
        'smokeChecks': {name: entry(path) for name, path in smoke_paths.items()}, 'frozenSmokeFiles': frozen_files,
        'smokeChecksPassed': True, 'launchHelpers': helpers,
        'executedSmokeHelpers': {name: value for name, value in inputs['launchHelpers'].items() if Path(name).name not in core},
        'executedFinalizer': entry(Path(__file__).resolve()),
        'preservedHistoricalReceipts': inputs['preservedHistoricalReceipts'],
        'blenderSavedPreferencesBeforeAndAfter': saved, 'savedBlenderPreferencesModified': False,
        'sourceWorktreeInputsActive': bool(borrowed),'borrowedVerificationInputs':borrowed,
        'gameClientTesting': False, 'oldWorktreeOrToolsDeleted': False,
        'launchPolicy': 'Use the local shared-tools.json and this receipt via launch_shared_tool.py; Blender uses factory background startup and the byte-verified primary addon bank.',
        'historicalReceiptPolicy': 'Historical receipts remain immutable. This local receipt replaces active launch resolution only.',
        'limits': ['Tool execution and source registration only; production assets, equipment sizing and client acceptance remain separate.',
                   'Armory support fixtures include synthetic nested/authored-normal examples; transformed smoke files are not production equipment.']}
    snapshot = output.with_name(output.stem+'-executed-finalizer.py')
    require(not snapshot.exists(), 'Fresh finalizer snapshot required')
    shutil.copyfile(Path(__file__).resolve(), snapshot)
    report['executedFinalizerSnapshot'] = entry(snapshot)
    output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    load(config, output)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--verification-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    path = finalize(args.toolchain, args.verification_dir, args.output)
    print(json.dumps({'migration': str(path), 'sha256': sha(path)}))
