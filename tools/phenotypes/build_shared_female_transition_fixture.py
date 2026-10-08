"""Prepare then execute script-only shared-female transition fixture descendants.

Every execution consumes a frozen preparation. Uncertain or failed operations
are retained and never automatically retried. Body and animation bytes are read
only; this builder creates no visual, client, production or publication approval.
"""
import argparse
import ast
import copy
import json
from pathlib import Path
import shutil
import subprocess
import time
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import target_contract as contract
import shared_female_transition_fixture as transition
import shared_female_animation_overlay as overlay
import shared_female_posture_fixture as fixture
import shared_female_stock_basis as basis
import pack_stock_target_fixture as packer
from shared_tools import resolve_tool, sha
from target_fixture import user_layout
from target_animation_overlay import NativeIdleReader
from animation_verification_preparation import AnimationVerificationPreparation
from audit_thigh_package import compare_archive

REPO = Path(__file__).resolve().parents[2]
AREA = REPO / 'output/phenotypes' / transition.TARGET
SELECTED = '669cd38aa1ae3fe96e1444edd6cbe89bde82e2f06ed225fa8eb4baacdc595f2e'
CONFIG_FIELDS = {'schemaVersion', 'kind', 'targetContract', 'nativeSourceExecution',
    'animationOverlay', 'postureStockBinding', 'visualApproval', 'header',
    'sources', 'protectedBodyPins', 'toolsRoot', 'gameRoot', 'prepareOutput', 'executeOutput'}


def file_pin(path):
    return {'path': str(Path(path).resolve()), 'sha256': sha(path)}


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')


def fresh(path):
    path = Path(path).resolve()
    contract.require(path.is_relative_to(AREA) and not path.exists(), 'Fresh own-target output required')
    return path


def helper_closure(inputs):
    transition.current_helper_closure(inputs)
    pending, seen = [Path(__file__).resolve()], set()
    roots = (REPO/'tools/phenotypes', REPO/'tools')
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        inputs.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            names = [x.name for x in node.names] if isinstance(node, ast.Import) else (
                [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for name in names:
                child = next((root/(name.split('.')[0]+'.py') for root in roots
                    if (root/(name.split('.')[0]+'.py')).is_file()), None)
                if child:
                    pending.append(child.resolve())


def context(config_path):
    inputs = transition.Inputs()
    config_path = inputs.add(Path(config_path).resolve())
    c = transition.strict_json(config_path)
    contract.require(set(c) in (CONFIG_FIELDS, CONFIG_FIELDS | {'recoveredFirstCompile'}) and c['schemaVersion'] == 1 and
        type(c['schemaVersion']) is int and c['kind'] == 'shared-female-transition-build-configuration',
        'Exact transition build configuration required')
    helper_closure(inputs)
    tp = inputs.pin(c['targetContract'])
    target = contract.load(tp)
    overlay.require_target(target, tp)
    contract.require(c['animationOverlay']['sha256'] == SELECTED, 'Approved animation selection differs')
    approval = inputs.read(c['visualApproval'])
    contract.require(approval['kind'] == 'human-observed-posture-preview-approval' and
        approval['visualApprovedByHuman'] is True and approval['selectedAnimationOverlay'] == c['animationOverlay'],
        'Observed Human preview approval must bind the exact selected overlay')
    sources = inputs.read(c['nativeSourceExecution'])
    contract.verify_binding(sources, tp, target, 'runtime')
    contract.require(sources['kind'] == 'executed-shared-female-stockbody-roster-native-source' and
        len(sources['batches']) == 4 and sources['postureStockBinding'] == c['postureStockBinding'],
        'Four original native source parents required')
    stock = inputs.read(c['postureStockBinding'])
    inputs.merge(basis.collect_stock_basis_inputs(c['postureStockBinding'], tp, stock['rosters'][0]))
    inputs.merge(overlay.collect_overlay_inputs(c['animationOverlay'], tp))
    inputs.merge(fixture.verify_cumulative_coverage(sources['coverage'], tp)['frozenInputs'])
    parents = []
    for entry in sources['batches']:
        parent = inputs.read(entry)
        contract.verify_binding(parent, tp, target, 'runtime')
        inputs.add(Path(parent['module']), parent['moduleSha256'])
        proof = inputs.read(parent['sourceProof'])
        for pin in proof.values():
            if isinstance(pin, dict) and set(pin) == {'path', 'sha256'}:
                inputs.pin(pin)
        folder = Path(entry['path']).resolve().parent
        for directory, key in (('module-resources', 'moduleResourceHashes'), ('hak-resources', 'fixtureResourceHashes')):
            for name, digest in parent[key].items():
                inputs.add(folder/directory/name, digest)
        parents.append(entry)
    contract.require(set(c['sources']) == transition.SOURCES and len(c['protectedBodyPins']) == 29,
        'Two canonical scripts and 29 protected body pins required')
    for name, pin in c['sources'].items():
        source = inputs.pin(pin)
        contract.require(source.name == name, 'Canonical source identity differs')
    inputs.pin(c['header'])
    inputs.merge(c['protectedBodyPins'])
    tools = {name: resolve_tool(name, REPO, c['toolsRoot']) for name in ('script_comp', 'gff', 'erf', 'resman_cat')}
    for entry in tools.values():
        inputs.add(Path(entry['path']), entry['sha256'])
    contract.require(Path(c['gameRoot']).resolve() == Path(stock['gameRoot']).resolve(), 'Installed game root differs')
    recovery_pin = c.get('recoveredFirstCompile')
    if recovery_pin is not None:
        recovered = inputs.read(recovery_pin)
        contract.require(recovered['schemaVersion'] == 1 and recovered['kind'] ==
            'recovered-successful-first-transition-script-output' and
            recovered['compileCallsRecovered'] == 1 and recovered['compileCallsResubmitted'] == 0 and
            recovered['secondScriptCompiled'] is False and recovered['source']['sha256'] ==
            c['sources']['sr_tm_enter.nss']['sha256'], 'Exact successful first-script recovery required')
        for key in ('source','native','originalOutput','header','commandReceipt','failedExecution','outerLaunch'):
            inputs.pin(recovered[key])
        original_command = inputs.read(recovered['commandReceipt'])
        original_launch = inputs.read(recovered['outerLaunch'])
        contract.require(original_command == recovered['command'] and original_command['exitCode'] == 0 and
            original_command['argv'][0] == tools['script_comp']['path'] and
            recovered['source']['path'] in original_command['argv'] and
            original_launch['inputsUnchanged'] is True and original_launch['exitCode'] == 1 and
            original_launch['frozenInputs'].get(tools['script_comp']['path']) == tools['script_comp']['sha256'],
            'Recovered command/tool/original launch differs')
        native = inputs.pin(recovered['native']).read_bytes()
        contract.require(native == inputs.pin(recovered['originalOutput']).read_bytes() and
            native[:9] == b'NCS V1.0B' and int.from_bytes(native[9:13],'big') == len(native) and
            recovered['header']['sha256'] == c['header']['sha256'], 'Recovered native script/header differs')
    return c, tp, target, sources, stock, parents, tools, inputs


def prepare(config_path):
    started = time.monotonic()
    c, tp, target, sources, stock, parents, tools, inputs = context(config_path)
    output = fresh(c['prepareOutput'])
    fresh(c['executeOutput'])
    output.mkdir()
    user_layout(output/'lookup-userdir')
    canonical = output/'canonical'
    canonical.mkdir()
    copied = {}
    for name, entry in c['sources'].items():
        shutil.copyfile(inputs.pin(entry), canonical/name)
        contract.require(sha(canonical/name) == entry['sha256'], 'Canonical copy differs')
        copied[name] = file_pin(canonical/name)
    command = [tools['resman_cat']['path'], '--root', c['gameRoot'], '--userdirectory',
        str(output/'lookup-userdir'), '--no-ovr', 'nwscript.nss']
    result = subprocess.run(command, capture_output=True)
    (output/'header-lookup.stdout').write_bytes(result.stdout)
    (output/'header-lookup.stderr').write_bytes(result.stderr)
    contract.require(result.returncode == 0 and result.stdout == inputs.pin(c['header']).read_bytes(),
        'Fresh installed no-override compiler header differs')
    (canonical/'nwscript.nss').write_bytes(result.stdout)
    family = inputs.read(stock['familyPreparation'])
    timings = {}
    for row in family['rows']:
        pin = row['sourceIdleNative']
        decoded = NativeIdleReader(inputs.pin(pin).read_bytes()).decode(('pause1', 'pause2'))
        timings[row['root']] = {'sourceNative': pin, 'owner': row['winningIdleOwner'],
            **{name: {k: decoded['clips'][name][k] for k in ('length', 'transition')}
                for name in ('pause1', 'pause2')}}
    contract.require(all(abs(v[name]['length']-2) < 1e-6 and
        abs(v[name]['transition']-(.7 if root[2] in 'do' else 1.0)) < 1e-6
        for root,v in timings.items() for name in ('pause1', 'pause2')),
        'Canonical holds require the measured 2-second idles and .7/1-second native blends')
    rosters = [fixture.verify_roster(pin, tp)['document'] for pin in stock['rosters']]
    groups = []
    for roster in rosters:
        for purpose in ('required-case', 'equipment-control'):
            for race in dict.fromkeys(a['raceId'] for a in roster['actors'] if a['purpose'] == purpose):
                groups.append({'batchId': roster['batchId'], 'groupId': roster['batchId']+'-'+purpose+'-race-'+str(race),
                    'actorTags': [a['tag'] for a in roster['actors'] if a['purpose'] == purpose and a['raceId'] == race]})
    schedule = {'schemaVersion': 1, 'kind': 'shared-female-transition-schedule',
        **contract.binding(tp, target, 'runtime'), 'familyPreparation': stock['familyPreparation'],
        'coverage': sources['coverage'], 'rosters': stock['rosters'], 'groups': groups, 'idleTimings': timings,
        'camera': {'distance': 4.5, 'pitch': 75., 'height': .95}, 'outboundDistanceMetres': 12.,
        'arrivalToleranceMetres': .1, 'postureHoldSeconds': 8.,
        'samplingLimit': 'Serial actor cameras, unpaused .1-second script clock, 12.20/12.50-second idle holds and 9.50-second crouch/kneel holds with extra callback-clock margin. Native transition lengths remain unchanged. Actual callbacks gate phase progression without resets. Logs prove protocol only; literal close motion, breathing and floor review remain separate.',
        'sourceNSSHashes': {n: p['sha256'] for n, p in copied.items()}}
    transition.validate_schedule(schedule, rosters)
    save(output/'schedule.json', schedule)
    frozen = inputs.finish()
    recipe = {'schemaVersion': 1, 'kind': 'prepared-shared-female-transition-build',
        **contract.binding(tp, target, 'runtime'), 'config': file_pin(config_path), 'worker': file_pin(__file__),
        'parents': parents, 'sources': copied, 'header': file_pin(canonical/'nwscript.nss'),
        'headerLookup': {'argv': command, 'exitCode': result.returncode,
            'stdout': file_pin(output/'header-lookup.stdout'), 'stderr': file_pin(output/'header-lookup.stderr')},
        'schedule': file_pin(output/'schedule.json'), 'animationOverlay': c['animationOverlay'],
        'protectedBodyPins': c['protectedBodyPins'], 'tools': tools, 'frozenInputs': frozen,
        'executeOutput': c['executeOutput'], 'gameRoot': c['gameRoot'], 'toolsRoot': c['toolsRoot'],
        'recoveredFirstCompile': c.get('recoveredFirstCompile'),
        'operationBudget': {'scriptCompileCalls': 2, 'nativeMODPackCalls': 4, 'nativeGITEncodeCalls': 0,
            'modelCompileCalls': 0, 'HAKBuilt': 0}, 'clientLaunched': False,
        'clientAccepted': False, 'runtimeSelected': False, 'productionAccepted': False,
        'elapsedSeconds': time.monotonic()-started}
    save(output/'preparation.json', recipe)
    print(json.dumps({'preparation': file_pin(output/'preparation.json'), 'groups': len(groups), 'compileCalls': 0}))


def execute(preparation_path, preparation_sha):
    started = time.monotonic()
    inputs = transition.Inputs()
    recipe = inputs.read({'path': str(Path(preparation_path).resolve()), 'sha256': preparation_sha})
    contract.require(recipe['kind'] == 'prepared-shared-female-transition-build' and recipe['worker'] == file_pin(__file__),
        'Exact reviewed preparation/worker required')
    inputs.merge(recipe['frozenInputs'])
    inputs.pin(recipe['config']); inputs.pin(recipe['schedule']); inputs.pin(recipe['header'])
    for pin in recipe['sources'].values(): inputs.pin(pin)
    for key in ('stdout', 'stderr'): inputs.pin(recipe['headerLookup'][key])
    tp = Path(recipe['targetContract']); target = contract.load(tp)
    contract.verify_binding(recipe, tp, target, 'runtime')
    output = fresh(recipe['executeOutput']); output.mkdir()
    save(output/'reservation.json', {'kind': 'reserved-shared-female-transition-native-build',
        'preparation': file_pin(preparation_path), 'automaticRetryForbidden': True,
        'operationBudget': recipe['operationBudget']})
    canonical = output/'canonical'; canonical.mkdir(); user_layout(output/'compile-userdir')
    for entry in (*recipe['sources'].values(), recipe['header']):
        shutil.copyfile(inputs.pin(entry), canonical/Path(entry['path']).name)
    sources = {name: file_pin(canonical/name) for name in transition.SOURCES}
    header = file_pin(canonical/'nwscript.nss')
    commands, products = [], {}
    recovered = inputs.read(recipe['recoveredFirstCompile']) if recipe.get('recoveredFirstCompile') else None
    if recovered is not None:
        inputs.pin(recovered['source']);inputs.pin(recovered['native']);inputs.pin(recovered['header'])
        sources['sr_tm_enter.nss'] = recovered['source']
        header = recovered['header']
    try:
        for name in sorted(transition.SOURCES):
            inputs.finish()
            if name == 'sr_tm_enter.nss' and recovered is not None:
                native = canonical/'sr_tm_enter.ncs'
                shutil.copyfile(recovered['native']['path'],native)
                contract.require(sha(native) == recovered['native']['sha256'], 'Recovered copy differs')
                products[native.name] = file_pin(native)
                commands.append(recovered['command'])
                save(output/'first-script-reused.json', {'recovery':recipe['recoveredFirstCompile'],
                    'source':recovered['source'],'native':file_pin(native),'recompiled':False})
                continue
            source = canonical/name; native = source.with_suffix('.ncs')
            contract.require(not native.exists(), 'Fresh native script output required')
            command = [recipe['tools']['script_comp']['path'], '--root', recipe['gameRoot'],
                '--userdirectory', str(output/'compile-userdir'), '--no-ovr', str(source)]
            result = subprocess.run(command, capture_output=True)
            stdout = output/(name+'.stdout'); stderr = output/(name+'.stderr')
            stdout.write_bytes(result.stdout); stderr.write_bytes(result.stderr)
            row = {'source': name, 'output': native.name, 'argv': command, 'exitCode': result.returncode,
                'stdout': file_pin(stdout), 'stderr': file_pin(stderr)}
            commands.append(row)
            save(output/(name+'-compile.json'), row)
            contract.require(result.returncode == 0, 'Native script compile failed; result retained')
            # Successful compiler return can precede visible output. Recover only
            # that same output; never resubmit a successful or uncertain command.
            for attempt in range(40):
                if native.is_file(): break
                time.sleep(.25)
            contract.require(native.is_file(), 'Successful compiler output unavailable; recover before another submission')
            products[native.name] = file_pin(native)
        inputs.finish()
        # Compiler inputs are immutable source/header copies, its binary, and
        # installed archives. Current guard helpers belong to the run receipt,
        # not to historical NCS input identity.
        stock = transition.strict_json(Path(transition.strict_json(Path(recipe['config']['path']))['postureStockBinding']['path']))
        compile_inputs = dict(stock['installedArchiveHashes'])
        compile_inputs[recipe['tools']['script_comp']['path']] = recipe['tools']['script_comp']['sha256']
        for entry in (*sources.values(), header): compile_inputs[entry['path']] = entry['sha256']
        compile_inputs[str(canonical/'nwscript.nss')] = sha(canonical/'nwscript.nss')
        compiled = {'schemaVersion': 1, 'kind': 'executed-shared-female-transition-script-compile',
            **contract.binding(tp, target, 'runtime'), **{k: False for k in transition.FALSE_FLAGS},
            'compilerTool': {'path': recipe['tools']['script_comp']['path'], 'sha256': recipe['tools']['script_comp']['sha256']},
            'header': header, 'sources': sources, 'outputs': products, 'commands': commands,
            'scriptCompileCalls': 2, 'frozenInputs': compile_inputs}
        save(output/'compile-execution.json', compiled)
        compile_pin = file_pin(output/'compile-execution.json')
        batches = []
        animation_preparation = AnimationVerificationPreparation(recipe["animationOverlay"], tp)
        for index, parent_pin in enumerate(recipe['parents'], 1):
            inputs.finish()
            parent = transition.strict_json(Path(parent_pin['path']))
            parent_folder = Path(parent_pin['path']).resolve().parent
            folder = output/('batch-'+str(index)); folder.mkdir()
            shutil.copytree(parent_folder/'module-resources', folder/'module-resources')
            shutil.copytree(parent_folder/'hak-resources', folder/'hak-resources')
            for name, entry in {**sources, **products}.items():
                shutil.copyfile(entry['path'], folder/'module-resources'/name)
            module = folder/parent['moduleName']; module = module.with_suffix('.mod')
            command = [recipe['tools']['erf']['path'], '-c', '-f', str(module), '-e', 'MOD', str(folder/'module-resources')]
            result = subprocess.run(command, capture_output=True)
            (folder/'pack.stdout').write_bytes(result.stdout); (folder/'pack.stderr').write_bytes(result.stderr)
            save(folder/'pack-command.json', {'argv': command, 'exitCode': result.returncode,
                'stdout': file_pin(folder/'pack.stdout'), 'stderr': file_pin(folder/'pack.stderr')})
            contract.require(result.returncode == 0, 'Native MOD pack failed; result retained')
            compare_archive(packer.archive(module), folder/'module-resources')
            decoded = folder/'decoded-native-git.json'
            command = [recipe['tools']['gff']['path'], '-i', str(folder/'module-resources/sr_tm_floor.git'), '-o', str(decoded), '-p']
            result = subprocess.run(command, capture_output=True)
            (folder/'decode.stdout').write_bytes(result.stdout); (folder/'decode.stderr').write_bytes(result.stderr)
            contract.require(result.returncode == 0, 'Native GIT decode failed; result retained')
            hashes = {p.name: sha(p) for p in (folder/'module-resources').iterdir()}
            proof = {'schemaVersion': 1, 'kind': 'shared-female-stockbody-transition-native-source-proof',
                **contract.binding(tp, target, 'runtime'), **{k: False for k in transition.FALSE_FLAGS},
                'parentPreparation': parent_pin, 'parentSourceProof': parent['sourceProof'],
                'postureRoster': parent['postureRoster'], 'postureStockBinding': parent['postureStockBinding'],
                'selectedOverlay': recipe['animationOverlay'], 'schedule': recipe['schedule'],
                'compileExecution': compile_pin, 'nativeModule': file_pin(module),
                'nativeGIT': file_pin(folder/'module-resources/sr_tm_floor.git'), 'decodedNativeGIT': file_pin(decoded),
                'moduleResourceHashes': hashes, 'fixtureResourceHashes': parent['fixtureResourceHashes'],
                'stockTableBaselines': parent['stockTableBaselines'], 'protected11ModuleResourceHashes':
                    {n: h for n, h in parent['moduleResourceHashes'].items() if n not in transition.CHANGED},
                'operationCounts': {'nativeMODPackCalls': 1, 'nativeGITEncodeCalls': 0, 'modelCompileCalls': 0}}
            save(folder/'source-proof.json', proof); proof_pin = file_pin(folder/'source-proof.json')
            child = copy.deepcopy(parent)
            child.update(module=str(module), moduleSha256=sha(module), moduleResourceHashes=hashes,
                sourceProof=proof_pin, transitionSourceProof=proof_pin, transitionAnimationAuthority=recipe['animationOverlay'])
            save(folder/'preparation.json', child)
            review = transition.verify_source(proof_pin, tp, recipe['gameRoot'], recipe['tools']['gff']['path'],
                selected_overlay_pin=recipe['animationOverlay'], tools_root=recipe['toolsRoot'], animation_preparation=animation_preparation)
            save(folder/'verification.json', review)
            inputs.finish()
            batches.append({'batchId': 'batch-'+str(index), 'source': file_pin(folder/'preparation.json'),
                'proof': proof_pin, 'verification': file_pin(folder/'verification.json')})
            print(json.dumps({'batch': index, 'source': batches[-1]['source'], 'protectedResources': 11}), flush=True)
        report = {'schemaVersion': 1, 'kind': 'executed-shared-female-transition-native-build',
            **contract.binding(tp, target, 'runtime'), 'preparation': file_pin(preparation_path),
            'compileExecution': compile_pin, 'batches': batches, 'operationCounts': recipe['operationBudget'],
            'recoveredFirstCompile':recipe.get('recoveredFirstCompile'),
            'newScriptCompileCalls':1 if recovered else 2,'scriptCompileCallsResubmitted':0,
            'animationPreparation':animation_preparation.receipt(),
            'frozenInputs': inputs.finish(), 'inputsUnchanged': True, 'clientLaunched': False,
            'clientAccepted': False, 'runtimeSelected': False, 'productionAccepted': False,
            'elapsedSeconds': time.monotonic()-started}
        save(output/'execution.json', report)
        print(json.dumps({'execution': file_pin(output/'execution.json'), 'batches': 4, 'clientLaunched': False}))
    except Exception as error:
        save(output/'failure.json', {'kind': 'retained-shared-female-transition-build-failure',
            'error': str(error), 'preparation': file_pin(preparation_path), 'automaticRetryForbidden': True,
            'completedCompileCommands': commands, 'clientLaunched': False})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare', type=Path)
    group.add_argument('--execute', type=Path)
    parser.add_argument('--preparation-sha256')
    args = parser.parse_args()
    if args.prepare:
        contract.require(args.preparation_sha256 is None, 'Preparation hash belongs only to execution')
        prepare(args.prepare)
    else:
        contract.require(args.preparation_sha256 is not None, 'Execution requires its exact preparation hash')
        execute(args.execute, args.preparation_sha256)


if __name__ == '__main__':
    main()
