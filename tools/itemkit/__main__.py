"""Item toolkit. Mutating processing uses the maintained shared-tool launcher."""
import argparse
import json
from pathlib import Path
import shutil
from tools.headkit import comfy
from tools.headkit.common import asset, bindings, launched, pin, read, require, verify, write, python_package_pins, verification_pass
from .contracts import all_pins, code_pins, family, manifest, source_version, evidence_pins,stage_roles
from .generation import request_stage, shared_ledger, initialize_trial, set_trial_limit


def intake(reference, output, design_id='cougar-fineblade-longblade', family_name='shortsword'):
    import re
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', design_id), 'Safe item ID required')
    require(family_name in ('shortsword', 'dagger', 'longsword', 'firearm-sling'), 'Supported intake family required')
    if family_name == 'firearm-sling':
        from .firearm_intake import intake_pistol
        require(design_id != 'cougar-fineblade-longblade', 'Firearm intake requires an explicit design ID')
        return intake_pistol(reference, output, design_id)
    output = Path(output).resolve(); require(not output.exists(), 'Use a fresh intake directory')
    output.mkdir(parents=True); (output/'intake').mkdir()
    target = output/'intake'/'reference-original.png'; shutil.copyfile(reference, target)
    profile = Path(__file__).parent/'profiles'/'cougar-shortsword.json'
    profile_data = read(profile)
    profile_data['family'] = family_name
    profile_data['allowedAssemblies'] = [dict.fromkeys(('b','m','t'), design_id)]
    if family_name == 'dagger':
        profile_data['sourceExport'] = {'remeshResolution':768,'targetFaceCount':200000,'signMode':'udf'}
        profile_data['budgets'] = {'visible':5000,'shadow':500,'parts':{
            'b':{'visible':800,'shadow':100},'m':{'visible':1400,'shadow':100},'t':{'visible':2800,'shadow':300}}}
        profile_data['resources'] = {'texturePrefix':'sr_cfk','blueprint':'sr_cfk','hak':'srn_cfk_test',
            'module':'sr_cfk_test','displayName':'Cougar Fineblade Knife'}
    if family_name == 'longsword':
        profile_data['sourceExport'] = {'remeshResolution':768,'targetFaceCount':200000,'signMode':'udf'}
        profile_data['budgets'] = {'visible':12000,'shadow':500,'parts':{
            'b':{'visible':1200,'shadow':100},'m':{'visible':2300,'shadow':100},'t':{'visible':8500,'shadow':300}}}
        profile_data['resources'] = {'texturePrefix':'sr_cfs','blueprint':'sr_cfs','hak':'srn_cfs_test',
            'module':'sr_cfs_test','displayName':'Cougar Fineblade Longsword'}
    write(output/'family.json', profile_data, fresh=True)
    data = read(Path(__file__).parent/'examples'/'cougar.json')
    data['id'] = design_id
    data['inputs']['reference'] = {'path': 'intake/reference-original.png', 'sha256': pin(target)['sha256']}
    data['familyProfile'] = {'path': 'family.json', 'sha256': pin(output/'family.json')['sha256']}
    write(output/'asset.json', data, fresh=True)
    return {'manifest': pin(output/'asset.json'), 'reference': pin(target), 'clayReferenceRequired': False}


def consumed_inputs(manifest_path, bindings_path, run=None, extra=(),stage=None):
    with verification_pass('item-consumed-inputs'):
        return _consumed_inputs(manifest_path, bindings_path, run, extra, stage)


def consumed_pins(manifest_path, bindings_path, run=None, extra=(),stage=None):
    """Return verified pins directly instead of making callers hash paths again."""
    with verification_pass('item-consumed-inputs'):
        return _consumed_inputs(manifest_path, bindings_path, run, extra, stage, as_pins=True)


def _consumed_inputs(manifest_path, bindings_path, run=None, extra=(),stage=None, *, as_pins=False):
    local = bindings(bindings_path)
    roles=None if stage is None else ({'exportSource'} if stage=='export' and run is None else stage_roles(stage))
    pins = all_pins(manifest_path,roles=roles,native=stage is None or (run is not None and stage in ('fit','export')))+code_pins()+[pin(bindings_path)]+python_package_pins(local)
    for key in ('toolchain', 'migrationReceipt'):
        if key in local: pins.append(pin(local[key]))
    for key in ('python', 'blender', 'client', 'embree'):
        if key in local: pins.append(local[key])
    cpu=run is not None or stage in {'prepare','inspect','donor','fit','reduce','unwrap','finish','bake','shadow','render','native','fixture','client'}
    models={} if cpu else local.get('models', {})
    # New GPU requests bind model paths/hashes in the configuration, but only
    # Comfy consumes those bytes. Its fresh preparation/dispatch/completion
    # checks replace redundant client and launcher weight reads. Unscoped
    # legacy input enumeration remains conservative.
    pins += (list(models.values()) if stage is None else [])+([] if cpu else local.get('comfySources', []))
    if stage in ('fixture','client') or stage is None:
        pins += list(local.get('fixtureHaks', {}).values())+list(local.get('comparisonHaks',{}).values())
    for row in local.get('libraries', {}).values(): pins += row['files']
    if not cpu and local.get('comfyCustomNodes'):
        directory = Path(local['comfyCustomNodes'])/'srn_headkit'
        pins += [pin(p) for p in sorted(directory.glob('*.py'))]
        if (directory/'source-roots.json').exists(): pins.append(pin(directory/'source-roots.json'))
    if run and (Path(run)/'state.json').exists():
        state = read(Path(run)/'state.json')  # Mutable state is output, not an immutable consumed asset.
        pins += list(state['reviews'].values())
        for row in state['stages'].values():
            verify([row]); receipt = read(row['path']); pins += [row]+receipt['inputs']+receipt['outputs']
    for path in extra:
        row = pin(path); pins.append(row)
        document = read(path)
        if isinstance(document, dict):
            if 'observations' in document: pins += evidence_pins(path)
            prepared = document.get('prepared', document)
            if 'prompt' in prepared: pins += prepared.get('inputs', [])
    verify(pins)
    if as_pins:
        # Verify every expected digest before deduplication: two pins for the
        # same file must not silently replace one another on disagreement.
        canonical={str(Path(row['path']).resolve()):row['sha256'] for row in pins}
        return [{'path':path,'sha256':canonical[path]} for path in sorted(canonical)]
    return sorted({row['path'] for row in pins})


def preflight(manifest_path, bindings_path, probe=False):
    data = manifest(manifest_path); profile = family(asset(manifest_path, data['familyProfile'])['path'])
    local = read(bindings_path); issues = []
    for key in ('toolchain', 'migrationReceipt', 'python', 'pythonPackages', 'blender', 'client', 'submissionLedger'):
        if not local.get(key): issues.append('Missing runtime binding: '+key)
    for key in ('python', 'blender', 'client'):
        if local.get(key):
            try: verify([local[key]])
            except (OSError, ValueError) as exc: issues.append(str(exc))
    adapter = Path(local.get('comfyCustomNodes', '.'))/'srn_headkit'
    if not (adapter/'source-roots.json').is_file(): issues.append('Pinned headkit Comfy adapter/source snapshot not installed')
    if profile['nativePackaging'] != 'enabled': issues.append('Measured effective native contract pending')
    if not data.get('camera', {}).get('reviewed'): issues.append('Camera calibration/review pending')
    try:
        from .conditioning import require_conditioning_review
        require_conditioning_review(manifest_path,data)
    except (KeyError,OSError,ValueError) as exc:issues.append('Background isolation pending: '+str(exc))
    live = None
    if probe:
        try:
            client = comfy.Client(local['comfyUrl']); live = {'idle': client.idle()}
            identity = client.request('/headkit/runtime-identity'); live['runtimeFingerprint'] = identity['fingerprint']
        except Exception as exc: issues.append('Comfy preflight unavailable: '+str(exc))
    return {'id': data['id'], 'ready': not issues, 'issues': issues, 'comfy': live, 'clayReferenceRequired': False}


def main():
    p = argparse.ArgumentParser(description=__doc__); commands = p.add_subparsers(dest='command', required=True)
    c = commands.add_parser('intake'); c.add_argument('--reference', type=Path, required=True); c.add_argument('--output', type=Path, required=True)
    c.add_argument('--id', default='cougar-fineblade-longblade'); c.add_argument('--family', choices=['shortsword','dagger','longsword','firearm-sling'], default='shortsword')
    c = commands.add_parser('firearm-inputs'); c.add_argument('--bindings', type=Path, required=True)
    group = c.add_mutually_exclusive_group(required=True)
    group.add_argument('--spec', type=Path); group.add_argument('--prepared', type=Path); group.add_argument('--native', type=Path)
    c.add_argument('--manifest', type=Path)
    c.add_argument('--output', type=Path, required=True)
    c = commands.add_parser('firearm-prepare'); c.add_argument('--bindings', type=Path, required=True)
    c.add_argument('--spec', type=Path, required=True); c.add_argument('--output', type=Path, required=True)
    c = commands.add_parser('firearm-native'); c.add_argument('--bindings', type=Path, required=True)
    c.add_argument('--prepared', type=Path, required=True); c.add_argument('--output', type=Path, required=True)
    c = commands.add_parser('firearm-fixture'); c.add_argument('--bindings', type=Path, required=True)
    c.add_argument('--native', type=Path, required=True); c.add_argument('--manifest', type=Path, required=True)
    c.add_argument('--output', type=Path, required=True)
    c = commands.add_parser('init-trial'); c.add_argument('--bindings', type=Path, required=True); c.add_argument('--evidence', required=True)
    c = commands.add_parser('set-trial-limit'); c.add_argument('--bindings', type=Path, required=True)
    c.add_argument('--maximum', type=int, choices=[5], required=True)
    c.add_argument('--evidence', type=Path, required=True); c.add_argument('--output', type=Path, required=True)
    c = commands.add_parser('resize-corners'); c.add_argument('--bindings',type=Path,required=True)
    c.add_argument('--arrays',type=Path,required=True);c.add_argument('--matrix',type=Path,required=True);c.add_argument('--output',type=Path,required=True)
    for name in ('prepare', 'run', 'resume', 'review', 'status'):
        c = commands.add_parser(name)
        for key in ('manifest', 'bindings', 'run'): c.add_argument('--'+key, type=Path, required=True)
        if name in ('run', 'resume', 'review'): c.add_argument('--stage', required=True)
        if name in ('run', 'resume'): c.add_argument('--evidence', type=Path)
        if name == 'review':
            c.add_argument('--decision', choices=['approved', 'rejected'], required=True); c.add_argument('--notes', required=True)
    c = commands.add_parser('preflight'); c.add_argument('--manifest', type=Path, required=True)
    c.add_argument('--bindings', type=Path, required=True); c.add_argument('--probe', action='store_true')
    c = commands.add_parser('inputs'); c.add_argument('--manifest', type=Path, required=True)
    c.add_argument('--bindings', type=Path, required=True); c.add_argument('--run', type=Path)
    c.add_argument('--stage',choices=['calibrate','geometry','appearance','export','prepare','inspect','donor',
                                    'fit','reduce','unwrap','finish','bake','shadow','render','native','fixture','client'])
    c.add_argument('--extra', type=Path, action='append', default=[]); c.add_argument('--output', type=Path, required=True)
    c = commands.add_parser('request')
    for key in ('manifest', 'bindings', 'output'): c.add_argument('--'+key, type=Path, required=True)
    c.add_argument('--stage', choices=['calibrate', 'geometry', 'appearance', 'export'], required=True)
    for name in ('submit', 'collect', 'reconcile', 'release'):
        c = commands.add_parser(name); c.add_argument('--bindings', type=Path, required=True); c.add_argument('--ledger', type=Path)
        if name in ('submit', 'collect'): c.add_argument('--output', type=Path, required=True)
        if name == 'submit': c.add_argument('--request', type=Path, required=True)
        if name in ('collect', 'reconcile'): c.add_argument('--token', required=True)
        if name == 'collect': c.add_argument('--wait', action='store_true')
    a = p.parse_args()
    with verification_pass('item-cli-startup'):
        runtime = None if a.command in ('intake', 'inputs', 'firearm-inputs', 'status', 'preflight') else launched(a.bindings)
        if runtime is not None: python_package_pins(bindings(a.bindings), require_imports=True)
    if a.command == 'intake': result = intake(a.reference, a.output, a.id, a.family)
    elif a.command == 'firearm-inputs':
        from .firearm_package import specification_inputs, prepared_inputs, native_inputs
        with verification_pass('firearm-consumed-inputs'):
            local = bindings(a.bindings)
            if a.native:
                require(a.manifest is not None, 'Fixture manifest required with --native')
                pins = native_inputs(a.native)+all_pins(a.manifest, roles=stage_roles('fixture'), native=False)
                pins += list(local.get('fixtureHaks', {}).values())+list(local.get('comparisonHaks', {}).values())
            else:
                require(a.manifest is None, '--manifest is only used with --native')
                pins = specification_inputs(a.spec) if a.spec else prepared_inputs(a.prepared)
            pins += code_pins()+[pin(a.bindings), pin(local['toolchain']), pin(local['migrationReceipt'])]
            pins += python_package_pins(local)+[local['python']]
            if a.prepared: pins.append(local['client'])
            verify(pins)
        write(a.output, sorted({p['path'] for p in pins}), fresh=True)
        result = {'inputs': str(a.output), 'count': len({p['path'] for p in pins})}
    elif a.command == 'firearm-prepare':
        from .firearm_package import prepare
        result = prepare(a.spec, a.output)
    elif a.command == 'firearm-native':
        from .firearm_package import compile_package
        result = compile_package(a.prepared, bindings(a.bindings)['client'], a.output)
    elif a.command == 'firearm-fixture':
        from .firearm_package import native_inputs
        from .fixture import build
        pins = native_inputs(a.native)
        data = manifest(a.manifest, input_roles=stage_roles('fixture'), validate_native=False)
        result = build(a.manifest, data, read(a.native), bindings(a.bindings), a.output)
        verify(pins)
    elif a.command == 'resize-corners':
        from .resize import transform_part
        matrix_pin=pin(a.matrix);result=transform_part(a.arrays,read(a.matrix),a.output);verify([matrix_pin])
    elif a.command == 'init-trial':
        local=bindings(a.bindings)
        require(local.get('submissionLedger') and local.get('itemTrialId'), 'Bind trial ID and shared ledger first')
        initialize_trial(local['submissionLedger'], local['itemTrialId'], a.evidence)
        result={'ledger': local['submissionLedger'], 'trial': local['itemTrialId'], 'maximumGeometryAttemptsPerModel': 5}
    elif a.command == 'set-trial-limit':
        local=bindings(a.bindings)
        result=set_trial_limit(shared_ledger(local), local['itemTrialId'], a.maximum, a.evidence, a.output)
    elif a.command == 'preflight': result = preflight(a.manifest, a.bindings, a.probe)
    elif a.command == 'inputs':
        paths = consumed_inputs(a.manifest, a.bindings, a.run, a.extra,a.stage); write(a.output, paths, fresh=True)
        result = {'inputs': str(a.output), 'count': len(paths)}
    elif a.command in ('prepare', 'run', 'resume', 'review', 'status'):
        from .runner import Runner
        if a.command == 'status': result = Runner(a.manifest, a.bindings, a.run).status()
        else:
            with comfy.locked(a.run/'runner'):
                runner = Runner(a.manifest, a.bindings, a.run, runtime=runtime, evidence=getattr(a, 'evidence', None))
                result = runner.review(a.stage, a.decision, a.notes) if a.command == 'review' else runner.execute('prepare' if a.command == 'prepare' else a.stage)
    elif a.command == 'request':
        local = bindings(a.bindings); identity = comfy.Client(local['comfyUrl']).request('/headkit/runtime-identity')
        result = request_stage(a.manifest, a.bindings, a.stage, a.output, runtime=runtime, comfy_runtime=identity)
    else:
        local = bindings(a.bindings); ledger = shared_ledger(local, a.ledger); client = comfy.Client(local['comfyUrl'])
        if a.command == 'submit':
            prepared = read(a.request); require(prepared['codeVersion'] == source_version(), 'Stale item request')
            result = comfy.submit(client, ledger, prepared, a.output, runtime_identity=runtime, bindings_path=a.bindings)
        elif a.command == 'collect': result = comfy.collect(client, ledger, a.token, local['comfyOutput'], a.output, wait=a.wait)
        elif a.command == 'reconcile': result = comfy.reconcile(client, ledger, a.token)
        else: result = comfy.release(client, ledger)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__': main()
