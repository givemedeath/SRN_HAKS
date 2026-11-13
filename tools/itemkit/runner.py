"""Immutable item stage attempts, dependency reviews, and bounded resumption."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import time
import traceback
import uuid
import numpy as np
from PIL import Image
from tools.headkit.common import ROOT, read, write, pin, verify, require, asset, bindings, digest, library, python_package_pins
from .contracts import all_pins, code_pins, is_code_path, source_version, manifest, family, evidence_pins, stage_roles
from .geometry import corner_hash
from .routes import PACKAGED_FIREARMS, ROUTES, needs_grip_standard
from .verification import VerificationPass

DEPENDENCIES = {'prepare': (), 'inspect': (), 'donor': (), 'fit': (), 'reduce': ('fit',), 'unwrap': ('reduce',),
                'finish': ('unwrap',), 'bake': ('finish',), 'shadow': ('bake','reduce'), 'render': ('shadow', 'bake'),
                'export': ('render', 'shadow', 'bake'), 'native': ('export',),
                'fixture': ('native',), 'client': ('fixture',)}


def blender_environment(local,environment=None):
    """Keep Blender's embedded Python ABI separate from the CLI package bank."""
    env=dict(os.environ if environment is None else environment)
    directory=local.get('pythonPackages',{}).get('directory')
    if directory and 'PYTHONPATH' in env:
        bank=os.path.normcase(str(Path(directory).resolve()))
        env['PYTHONPATH']=os.pathsep.join(part for part in env['PYTHONPATH'].split(os.pathsep)
            if not part or os.path.normcase(str(Path(part).resolve()))!=bank)
    return env


def attempt_snapshot(receipt):
    """Identity of what an attempt consumed; input order and duplicate pins do not matter."""
    return digest({key: receipt.get(key) for key in ('manifestHash', 'bindingsHash', 'codeVersion', 'runtimeIdentity', 'dependencies')}
                  | {'inputs': sorted({(str(row['path']), row['sha256']) for row in receipt.get('inputs', [])})})


def run_logged(command, log, timeout, **options):
    """Run a launcher, retain its output, and stop its whole process tree on timeout."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='replace', **options)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        # The launcher runs Blender as its own child, which Popen.kill alone would orphan.
        if os.name == 'nt':
            subprocess.run(['taskkill', '/T', '/F', '/PID', str(process.pid)], capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        process.kill(); stdout, stderr = process.communicate()
        log.write_text(stdout+'\n'+stderr, encoding='utf-8')
        raise
    log.write_text(stdout+'\n'+stderr, encoding='utf-8')
    return process.returncode


class Runner:
    def __init__(self, manifest_path, bindings_path, run, *, runtime=None, evidence=None, package_pins=None):
        self.manifest_path = Path(manifest_path).resolve(); self.bindings_path = Path(bindings_path).resolve()
        self.data = manifest(self.manifest_path,input_roles=set(),validate_native=False); self.local = bindings(self.bindings_path)
        self.profile_path = Path(asset(self.manifest_path, self.data['familyProfile'])['path'])
        self.family = family(self.profile_path,validate_native=False); self.run = Path(run).resolve(); self.runtime = runtime
        self.evidence = Path(evidence).resolve() if evidence else None; self.package_pins = package_pins
        self.state_path = self.run/'state.json'
        self.state = read(self.state_path) if self.state_path.exists() else {'schemaVersion': 1, 'id': self.data['id'], 'stages': {}, 'reviews': {}}
        require(self.state['id'] == self.data['id'], 'Run belongs to another item')

    def input(self, role):
        require(role in self.data['inputs'], 'Missing pinned item input: '+role)
        return asset(self.manifest_path, self.data['inputs'][role])['path']

    def result(self, stage, *, review=True, seen=None, _audit=None):
        audit = VerificationPass() if _audit is None else _audit
        seen = set() if seen is None else seen
        require(stage not in seen, 'Cyclic stage receipts'); seen = seen | {stage}
        if (stage, review) in audit.results:
            return audit.results[stage, review]
        row = self.state['stages'].get(stage); require(row is not None, 'Stage not completed: '+stage)
        audit.verify([row])
        if stage not in audit.receipts: audit.receipts[stage] = read(row['path'])
        receipt = audit.receipts[stage]
        # A historical audit (rebuild_fixture) checks the receipt's recorded code version instead of today's code bytes.
        historical = getattr(audit, 'historical_code', None)
        audit.verify([row for row in receipt['inputs'] if historical is None or not historical(row['path'])]+receipt['outputs'])
        require(receipt['state'] == 'complete', 'Stage failed: '+stage)
        if stage == 'client' and self.evidence is not None:
            require(pin(self.evidence) in receipt['inputs'], 'Client review evidence changed')
        if audit.code_version is None: audit.code_version = source_version()
        require(receipt['manifestHash'] == digest(self.data) and receipt['bindingsHash'] == digest(self.local)
                and receipt['codeVersion'] == audit.code_version, 'Stale item stage: '+stage)
        if self.runtime is not None: require(receipt['runtimeIdentity'] == self.runtime, 'Stage launcher identity changed')
        for parent, expected in receipt['dependencies'].items():
            require(self.state['stages'].get(parent) == expected, 'Dependency changed: '+parent)
            self.result(parent, seen=seen, _audit=audit)
        if review:
            decision = self.state.get('reviews', {}).get(stage); require(decision is not None, 'Review pending: '+stage)
            audit.verify([decision]); decision = read(decision['path'])
            require(decision['stageReceipt'] == row and decision['decision'] == 'approved', 'Stale or rejected review: '+stage)
        audit.results[stage, review] = receipt['result']
        return receipt['result']

    def execute(self, stage):
        require(stage in DEPENDENCIES, 'Unknown item stage')
        require(self.runtime is not None, 'Processing requires the verified shared-tool launcher')
        if stage in self.state['stages']:
            try: return {'reused': True, 'result': self.result(stage, review=False)}
            except (ValueError, OSError): pass
        # Launched CLI startup already proved these imports for this one-stage process.
        package_pins = self.package_pins or python_package_pins(self.local)
        inputs = all_pins(self.manifest_path,roles=stage_roles(stage),native=stage in ('fit','export'))+code_pins()+[pin(self.bindings_path)]+package_pins
        for library in self.local.get('libraries',{}).values():inputs += library['files']
        inputs += [self.runtime[key] for key in ('toolchain', 'migrationReceipt', 'python')]
        if stage == 'fixture': inputs += list(self.local.get('fixtureHaks', {}).values())
        if stage == 'fixture': inputs += list(self.local.get('comparisonHaks', {}).values())
        if stage == 'client':
            require(self.evidence is not None, 'Supply --evidence without modifying the processing manifest')
            inputs += evidence_pins(self.evidence)
        for key in ('blender', 'client'):
            if key in self.local: inputs.append(self.local[key])
        parents = {}; parent_results = {}; parent_audit = VerificationPass()
        for parent in DEPENDENCIES[stage]:
            parent_results[parent] = self.result(parent, _audit=parent_audit)
            row = self.state['stages'][parent]; parents[parent] = row
            inputs += [row, self.state['reviews'][parent]]+parent_audit.receipts[parent]['outputs']
        root = self.run/stage; root.mkdir(parents=True, exist_ok=True)
        attempts = list(root.glob('attempt-*/receipt.json'))
        version = parent_audit.code_version if parent_audit.code_version is not None else source_version()
        manifest_hash = digest(self.data)
        receipt = {'stage': stage, 'state': 'running', 'manifestHash': manifest_hash,
                   'bindingsHash': digest(self.local), 'codeVersion': version,
                   'runtimeIdentity': self.runtime, 'inputs': inputs, 'dependencies': parents, 'outputs': []}
        # A snapshot is every consumed byte and dependency, not only the manifest and code:
        # correcting separately supplied evidence, bindings or an ancestor permits a new attempt.
        snapshot = attempt_snapshot(receipt)
        failed = [attempt for attempt in map(read, attempts)
                  if attempt['state'] == 'failed' and attempt_snapshot(attempt) == snapshot]
        require(len(failed) < 2, 'Two failures on this snapshot; correct inputs/code before another attempt')
        folder = root/('attempt-'+uuid.uuid4().hex); folder.mkdir()
        write(folder/'intent.json', receipt, fresh=True); started = time.monotonic()
        try:
            result = self._execute(stage, folder, parent_results=parent_results); digest(result)
            # One fresh completion boundary: each consumed file and ancestor artifact is reread once.
            completion_audit = VerificationPass(); completion_audit.verify(inputs)
            for parent in parents:
                require(self.state['stages'].get(parent) == parents[parent], 'Dependency changed: '+parent)
                self.result(parent, _audit=completion_audit)
            python_package_pins(self.local)
            receipt.update(state='complete', result=result)
        except Exception as exc:
            receipt.update(state='failed', error=str(exc), traceback=traceback.format_exc())
            raise
        finally:
            receipt['elapsedSeconds'] = time.monotonic()-started
            receipt['outputs'] = [pin(p) for p in sorted(folder.rglob('*')) if p.is_file() and p.name not in ('intent.json', 'receipt.json')]
            write(folder/'receipt.json', receipt, fresh=True)
            self.state['stages'][stage] = pin(folder/'receipt.json'); write(self.state_path, self.state)
        return {'reused': False, 'result': result}

    def worker(self, stage, folder, **values):
        require(self.local.get('blender'), 'Missing pinned Blender runtime')
        verify([self.local['blender']])
        if stage=='bake' and self.data.get('processing',{}).get('donorFinish'):
            values.setdefault('reference',self.input('reference'))
        if stage in ('fit', 'fit-measure') and 'gripStandard' in self.data['inputs']:
            values['gripStandard'] = self.input('gripStandard')
        config = {'stage': stage, 'family': self.family, 'fit': self.data.get('fit', {}),
                  'processing': self.data.get('processing', {}),'render':self.data.get('render',{}), 'output': str(folder/'worker'), **values}
        roles_stage = 'fit' if stage == 'fit-measure' else stage
        config['inputs'] = all_pins(self.manifest_path,roles=stage_roles(roles_stage),native=roles_stage=='fit')+code_pins()+[self.local['blender']]
        config['inputs'] += [pin(values[key]) for key in ('source', 'workingSource', 'scene', 'texture', 'reference', 'atlas', 'gripStandard') if key in values]
        for key in ('shadowCandidates', 'visibleCandidates'):
            if key in values: config['inputs'] += [row['arrays'] for row in values[key].values()]
        target = folder/'worker.json'; write(target, config, fresh=True)
        inputs = folder/'worker-inputs.json'; write(inputs, config['inputs']+[pin(target)], fresh=True)
        command = [sys.executable, str(ROOT/'tools/phenotypes/launch_shared_tool.py'),
                   '--toolchain', self.local['toolchain'], '--migration-receipt', self.local['migrationReceipt'],
                   '--tool', 'blender', '--output', str(folder/'worker-launch'), '--input-manifest', str(inputs),
                   '--', '--python', str(Path(__file__).parent/'blender_worker.py'), '--', '--config', str(target)]
        returncode = run_logged(command, folder/'blender.log', 2700, env=blender_environment(self.local),
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        require(returncode == 0, 'Blender worker failed; inspect retained log')
        # Worker inputs are stage inputs or this stage's own outputs; execute()'s completion audit rereads them fresh.
        verify(config['inputs']); return read(folder/'worker'/'result.json')

    def constrained_candidates(self, scene, folder):
        """Reduce each fitted part outside its seam band; the worker validates these before use."""
        from .parts import active_parts
        from .reduction import policy, reduce
        extracted = self.worker('uv-arrays', folder/'extract', scene=scene)
        meshlab = library(self.local, 'pymeshlab'); igl = library(self.local, 'igl'); joins = self.data['processing'].get('joinY', [])
        root = folder/'constrained'; root.mkdir(); candidates = {}
        with np.load(extracted['arrays']['path'], allow_pickle=False) as data:
            for part in active_parts(self.family):
                p, f = data[part+'_positions'], data[part+'_faces']
                budget = self.family['budgets']['parts'][part]['visible']
                v, t, _ = reduce(p, f, budget, joins, meshlab,
                                 lambda points: np.sqrt(igl.point_mesh_squared_distance(points, p, f)[0]))
                target = root/(part+'.npz'); np.savez_compressed(target, positions=v, faces=t)
                candidates[part] = {'arrays': pin(target), 'policyHash': policy(budget, joins),
                                    'sourceCornerHash': corner_hash(p[f])}
        return candidates

    def _execute(self, stage, folder, *, parent_results):
        parent_result = parent_results.__getitem__
        if stage == 'prepare':
            require(self.data.get('approval', {}).get('referenceDesignReviewed') is True, 'Reference design review required')
            source = Path(self.input('reference')); target = folder/'reference.png'
            with Image.open(source) as image:
                require(image.format == 'PNG' and min(image.size) >= 512, 'Use a PNG reference at least 512 pixels on each axis')
                info = {'size': list(image.size), 'mode': image.mode}
            shutil.copyfile(source, target)
            clay = self.data.get('conditioning', 'detailed-v1') == 'clay-detail-v1'
            return {'reference': pin(target), 'geometryAndAppearanceUseSameReference': not clay,
                    'clayReferenceRequired': clay, 'image': info, 'cameraReviewPending': True}
        if stage == 'inspect':
            return self.worker('inspect', folder, source=self.input('geometryRaw'))
        if stage == 'donor':
            source=self.input('geometryDonor');field=self.input('field')
            review=self.data.get('approval',{}).get('sourceDonor',{})
            require(review.get('decision')=='approved' and review.get('geometryDonorSha256')==pin(source)['sha256']
                    and review.get('fieldSha256')==pin(field)['sha256'] and review.get('notes','').strip(),
                    'Review the exact exported donor geometry and appearance field before source baking')
            from .donor import build,unwrap_source
            uv=unwrap_source(source,self.local,folder/'source-unwrap',
                             topology_policy=self.data['processing'].get('sourceDonorTopologyPolicy','closed-solid-v1'))
            sampling=uv['samplingSource']['path'] if 'samplingSource' in uv else source
            return build(sampling,uv['uvMesh']['path'],field,self.data['processing'].get('sourceFieldPolicy'),folder/'donor')
        if stage == 'fit':
            require(self.family['nativePackaging'] == 'enabled', 'Fitting requires a measured native contract')
            if needs_grip_standard(self.family['family'], self.data.get('fit', {})):
                require('gripStandard' in self.data['inputs'], 'Bind the approved grip standard before fitting this weapon')
            donor = self.input('texturedDonor'); review = self.data.get('approval', {}).get('texturedDonor', {})
            require(review.get('decision') == 'approved' and review.get('sha256') == pin(donor)['sha256']
                    and review.get('notes', '').strip(), 'Review this exact generated textured donor before fitting')
            require(self.data.get('processing', {}).get('openingProbes') or not self.data['openings'], 'Intentional openings need measured probes')
            require(self.data.get('processing', {}).get('thicknessProbes'), 'Measure protected thin-edge thickness before reduction')
            values = {'source': donor}
            if 'workingMesh' in self.data['inputs']:
                working = self.input('workingMesh'); working_review = self.data.get('approval', {}).get('workingMesh', {})
                require(working_review.get('decision') == 'approved' and working_review.get('sha256') == pin(working)['sha256']
                        and working_review.get('notes', '').strip(), 'Review the exact repaired working mesh before fitting')
                values['workingSource'] = working
            return self.worker(stage, folder, **values)
        if stage == 'unwrap':
            from .atlas import unwrap_parts
            parent=parent_result('reduce')
            extracted=self.worker('uv-arrays',folder/'extract',scene=parent['scene']['path'])
            from .parts import active_parts
            atlas=unwrap_parts(extracted['arrays']['path'],self.local,folder/'atlas',self.family['runtimeTextureSize'],
                               packing_paddings=self.data.get('processing',{}).get('uvPackingPaddings'),parts=active_parts(self.family),
                               coordinate_scale=self.data.get('processing',{}).get('uvCoordinateScale',1.0))
            result=self.worker('unwrap',folder/'apply',scene=parent['scene']['path'],atlas=atlas['atlas']['path'])
            result['validation']=atlas;return result
        if stage in ('reduce', 'finish', 'bake', 'shadow'):
            parent = parent_result(DEPENDENCIES[stage][0]); values = {'scene': parent['scene']['path']}
            if stage == 'finish': values['reference'] = self.input('reference')
            if stage == 'reduce' and self.data.get('processing',{}).get('constrainedReduction'):
                values['visibleCandidates'] = self.constrained_candidates(parent['scene']['path'], folder)
            if stage=='shadow' and self.data.get('processing',{}).get('shadowProxies'):
                values['shadowCandidates']=parent_result('reduce')['shadowPreflight']
            result = self.worker(stage, folder, **values)
            if stage=='reduce' and self.data.get('processing',{}).get('shadowProxies'):
                from .shadow import build_candidates
                quadric=any(row.get('method')=='quadric' for row in self.data['processing']['shadowProxies'].values())
                libraries={'meshlab':library(self.local,'pymeshlab'),'igl':library(self.local,'igl')} if quadric else {}
                result['shadowPreflight']=build_candidates(result['shadowSource']['path'],self.family,self.data['processing'],
                                                           folder/'shadow-preflight',**libraries)
            if stage == 'bake':
                from .textures import finish_bake
                result.update(finish_bake(result['linear']['path'], result['masks']['path'], folder/'textures',
                                               palettes=self.data['processing'].get('materialPalettes',())))
                from .texture_check import SIZE, check_bake
                if str(SIZE) in result['maps']:     # advisory: a person looks at the flagged blobs; never a gate
                    try: result['textureOutliers'] = check_bake(result['maps'][str(SIZE)]['path'], result['masks']['path'], folder/'texture-check')
                    except Exception as exc: result['textureOutliers'] = {'advisory': True, 'error': f'{type(exc).__name__}: {exc}'}
            return result
        if stage == 'render':
            return self.worker(stage, folder, scene=parent_result('shadow')['scene']['path'],
                               texture=parent_result('bake')['maps'][str(self.family['runtimeTextureSize'])]['path'])
        if stage == 'export':
            adapter = ROUTES[self.family['family']].adapter
            require(adapter != 'shield',
                    'Shield native export requires the reviewed shield_native adapter; '
                    'the rigid Runner exporter cannot preserve the pane material contract')
            require(adapter not in ('rigged', 'whole-skinned'),
                    'Rigged native export requires the reviewed skinned_native adapter and inactive placeholders; '
                    'the rigid Runner exporter cannot preserve skin weights or animation')
            arrays = self.worker('export-arrays', folder, scene=parent_result('shadow')['scene']['path'])
            icons = parent_result('render')['icons']
            if self.family['family'] in PACKAGED_FIREARMS:
                from .parts import active_parts
                slot, = active_parts(self.family)
                require(set(arrays['parts']) == set(icons) == {slot}, 'Whole firearm export contains unexpected parts')
                result = {'kind':'firearm-processed-variant', 'slot':slot, 'arrays':arrays['parts'][slot],
                          'texture':parent_result('bake')['maps'][str(self.family['runtimeTextureSize'])],
                          'icon':icons[slot], 'profile':pin(self.profile_path), 'clientValidated':False}
                write(folder/'variant.json', result, fresh=True)
                return result
            from .native import prepare
            return {'preparedDirectory': str(folder/'export'), **prepare(self.profile_path, self.family, arrays['parts'],
                parent_result('bake')['maps'][str(self.family['runtimeTextureSize'])]['path'], icons, folder/'export')}
        if stage == 'native':
            require(self.family['family'] not in PACKAGED_FIREARMS,
                    'Combine reviewed Color exports with firearm-prepare, firearm-native and firearm-fixture')
            from .native import compile_package
            return compile_package(parent_result('export')['preparedDirectory'], self.local['client'], folder/'native')
        if stage == 'fixture':
            from .fixture import build
            return build(self.manifest_path, self.data, parent_result('native'), self.local, folder/'fixture')
        if stage == 'client':
            from .fixture import validate_evidence
            return validate_evidence(self.evidence, parent_result('fixture'))
        raise ValueError('Unsupported stage')

    def measure_fit(self, output):
        """The fit worker's measure-only pass: its own grip measurement, digest and a fit preview, no stage attempt.

        A one-hand round grip, or a two-hand grip whose depth departs, is refused by the fit stage until a review is
        bound to the worker's measurement digest. Measuring in-process gives the same numbers but not the same digest
        (Blender's float32 mesh), so the old route spent a failed fit attempt to learn it. This runs the same grip code
        on the same imported working mesh and writes `measurement.json` and two preview images; nothing is approved."""
        require(self.runtime is not None, 'Measuring requires the verified shared-tool launcher')
        require(self.family['nativePackaging'] == 'enabled', 'Fitting requires a measured native contract')
        output = Path(output).resolve(); require(not output.exists(), 'Use a fresh measurement folder'); output.mkdir(parents=True)
        values = {'source': self.input('texturedDonor')}
        if 'workingMesh' in self.data['inputs']: values['workingSource'] = self.input('workingMesh')
        started = time.monotonic(); result = self.worker('fit-measure', output, **values)
        receipt = {'kind': 'fit-measurement', 'manifestHash': digest(self.data), 'bindingsHash': digest(self.local),
                   'codeVersion': source_version(), 'runtimeIdentity': self.runtime, 'elapsedSeconds': time.monotonic() - started,
                   'outputs': [pin(p) for p in sorted(output.rglob('*')) if p.is_file()], 'result': result,
                   'stageAttempt': False, 'approved': False, 'productionAccepted': False}
        write(output/'receipt.json', receipt, fresh=True)
        return result

    def rebuild_fixture(self, fixture_inputs, output):
        """A new private fixture from this run's reviewed native package, without re-running the stages before it.

        Every toolkit change makes the run's earlier stages stale (their receipts carry the code version), so a
        fixture change used to cost a full fit-to-fixture rerun. Here the native chain is verified byte for byte, with
        its manifest, reviews and dependency graph, at the code version it was built with, and only the fixture is
        built with the current code. The fixture's own inputs come from `fixture_inputs` (a `fixture-inputs` document
        beside the manifest), so the manifest and the native receipts stay valid. The result is review evidence for
        the in-game capture; it is not the pipeline's fixture stage and cannot feed the client stage."""
        from .fixture import build
        require(self.runtime is not None, 'Fixture builds require the verified shared-tool launcher')
        row = self.state['stages'].get('native'); require(row is not None, 'Stage not completed: native')
        verify([row]); recorded = read(row['path'])['codeVersion']
        audit = VerificationPass(); audit.code_version = recorded
        audit.historical_code = is_code_path()      # source files, even since-deleted ones: identified by the recorded version
        native = self.result('native', _audit=audit)
        fixture_inputs = Path(fixture_inputs).resolve(); extra = read(fixture_inputs)
        require(extra.get('kind') == 'fixture-inputs' and fixture_inputs.parent == self.manifest_path.parent,
                'A fixture-inputs document beside the manifest required')
        allowed = stage_roles('fixture')
        require(set(extra['inputs']) and all(key in allowed or key.startswith('comparisonBlueprint') for key in extra['inputs']),
                'Fixture inputs only')
        data = {**self.data, 'inputs': {**self.data['inputs'], **extra['inputs']}}
        # Fixture HAKs may come with the document, so the bindings the native receipts pin stay untouched.
        local = {**self.local, 'fixtureHaks': extra['fixtureHaks']} if 'fixtureHaks' in extra else self.local
        require(isinstance(local.get('fixtureHaks', {}), dict), 'Fixture HAK pins are a name -> pin map')
        inputs = [pin(fixture_inputs)]+[asset(fixture_inputs, value) for value in extra['inputs'].values()]+code_pins()+[pin(self.bindings_path)]
        inputs += list(local.get('fixtureHaks', {}).values())+list(local.get('comparisonHaks', {}).values())
        inputs += [row]+audit.receipts['native']['outputs']
        verify(inputs); output = Path(output).resolve(); require(not output.exists(), 'Use a fresh fixture folder'); output.mkdir(parents=True)
        started = time.monotonic(); result = build(fixture_inputs, data, native, local, output/'fixture')
        verify(inputs, fresh=True)
        receipt = {'kind': 'fixture-rebuild', 'state': 'complete', 'manifestHash': digest(self.data), 'nativeReceipt': row,
                   'nativeCodeVersion': recorded, 'codeVersion': source_version(), 'runtimeIdentity': self.runtime,
                   'inputs': inputs, 'outputs': [pin(p) for p in sorted((output/'fixture').rglob('*')) if p.is_file()],
                   'elapsedSeconds': time.monotonic() - started, 'result': result, 'pipelineStage': False,
                   'clientStageEligible': False, 'productionAccepted': False}
        write(output/'receipt.json', receipt, fresh=True)
        return result

    def review(self, stage, decision, notes):
        require(self.runtime is not None, 'Review writes require the verified launcher')
        require(decision in ('approved', 'rejected') and notes.strip(), 'Explicit decision and review notes required')
        self.result(stage, review=False)
        target = self.run/'reviews'/f'{stage}-{uuid.uuid4().hex}.json'
        result = {'stageReceipt': self.state['stages'][stage], 'decision': decision, 'notes': notes, 'productionAccepted': False}
        write(target, result, fresh=True); self.state['reviews'][stage] = pin(target); write(self.state_path, self.state)
        return result

    def _current_review(self, stage):
        """The filed review of the stage's current receipt, or None when it has none (or it reviews an older attempt)."""
        decision = self.state.get('reviews', {}).get(stage)
        if decision is None: return None
        verify([decision]); decision = read(decision['path'])
        return decision if decision['stageReceipt'] == self.state['stages'][stage] else None

    def chain(self, stages, notes, *, progress=None):
        """Run consecutive stages in this one verified launch, approving each but the last on its numerical gates.

        A stage launched on its own pays for the launcher's input freeze, the input listing and a review launch each
        time; that bookkeeping was about three quarters of a measured 41-minute run. Here they are paid once for the
        chain. Nothing inside a stage is relaxed: every stage still takes its own fresh verification passes, writes
        its own attempt and receipt, and a failure stops the chain where it happened. The last stage is left
        unreviewed so that a person looks at it before anything consumes it. `client` is never chained: it needs
        reviewed evidence."""
        stages = list(stages)
        require(stages and len(set(stages)) == len(stages) and all(stage in DEPENDENCIES and stage != 'client' for stage in stages),
                'A chain is distinct processing stages, without the client stage')
        require(isinstance(notes, str) and notes.strip(), 'Chain review notes required: they are filed with every automatic approval')
        for index, stage in enumerate(stages):
            for parent in DEPENDENCIES[stage]:
                if parent in stages[:index]: continue
                review = self._current_review(parent) if parent in self.state.get('stages', {}) else None
                require(review is not None and review['decision'] == 'approved',
                        f'Chain stage {stage} needs {parent} earlier in the chain or already reviewed and approved')
        done = []
        for index, stage in enumerate(stages):
            started = time.monotonic(); row = {'stage': stage, 'reviewed': False}; done.append(row)
            row['failed'] = True       # cleared on success: the failing stage still reports itself
            try:
                row['reused'] = self.execute(stage)['reused']
                if index < len(stages) - 1:
                    existing = self._current_review(stage) if row['reused'] else None
                    # A reused stage keeps the review a person already filed for that exact receipt; a rejection stops here.
                    require(existing is None or existing['decision'] == 'approved', f'Chain stage {stage} was rejected on review')
                    if existing is None: self.review(stage, 'approved', notes)
                    row['reviewed'] = True
                del row['failed']
            finally:
                row['seconds'] = round(time.monotonic() - started, 1)
                if progress is not None: progress(row)
        return {'stages': done, 'unreviewed': stages[-1], 'productionAccepted': False}

    def status(self):
        result = {}; audit = VerificationPass()
        for stage in DEPENDENCIES:
            try:
                self.result(stage, review=False, _audit=audit)
                try: self.result(stage, _audit=audit); result[stage] = {'state': 'complete', 'review': 'approved'}
                except (ValueError, OSError, KeyError) as exc: result[stage] = {'state': 'complete', 'review': str(exc)}
            except (ValueError, OSError, KeyError) as exc: result[stage] = {'state': 'pending-or-stale', 'reason': str(exc)}
        return {'id': self.data['id'], 'stages': result, 'productionAccepted': False}
