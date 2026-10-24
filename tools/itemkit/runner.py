"""Immutable item stage attempts, dependency reviews, and bounded resumption."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import time
import traceback
import uuid
from PIL import Image
from tools.headkit.common import ROOT, read, write, pin, verify, require, asset, bindings, digest, python_package_pins
from .contracts import all_pins, code_pins, source_version, manifest, family, evidence_pins, stage_roles
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


class Runner:
    def __init__(self, manifest_path, bindings_path, run, *, runtime=None, evidence=None):
        self.manifest_path = Path(manifest_path).resolve(); self.bindings_path = Path(bindings_path).resolve()
        self.data = manifest(self.manifest_path,input_roles=set(),validate_native=False); self.local = bindings(self.bindings_path)
        self.profile_path = Path(asset(self.manifest_path, self.data['familyProfile'])['path'])
        self.family = family(self.profile_path,validate_native=False); self.run = Path(run).resolve(); self.runtime = runtime
        self.evidence = Path(evidence).resolve() if evidence else None
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
        receipt = audit.receipts[stage]; audit.verify(receipt['inputs']+receipt['outputs'])
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
        package_pins = python_package_pins(self.local, require_imports=True)
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
            python_package_pins(self.local, require_imports=True)
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
        if stage=='fit' and 'gripStandard' in self.data['inputs']:
            values['gripStandard'] = self.input('gripStandard')
        config = {'stage': stage, 'family': self.family, 'fit': self.data.get('fit', {}),
                  'processing': self.data.get('processing', {}),'render':self.data.get('render',{}), 'output': str(folder/'worker'), **values}
        config['inputs'] = all_pins(self.manifest_path,roles=stage_roles(stage),native=stage=='fit')+code_pins()+[self.local['blender']]
        config['inputs'] += [pin(values[key]) for key in ('source', 'workingSource', 'scene', 'texture', 'reference', 'atlas', 'gripStandard') if key in values]
        if 'shadowCandidates' in values:config['inputs'] += [row['arrays'] for row in values['shadowCandidates'].values()]
        target = folder/'worker.json'; write(target, config, fresh=True)
        inputs = folder/'worker-inputs.json'; write(inputs, config['inputs']+[pin(target)], fresh=True)
        command = [sys.executable, str(ROOT/'tools/phenotypes/launch_shared_tool.py'),
                   '--toolchain', self.local['toolchain'], '--migration-receipt', self.local['migrationReceipt'],
                   '--tool', 'blender', '--output', str(folder/'worker-launch'), '--input-manifest', str(inputs),
                   '--', '--python', str(Path(__file__).parent/'blender_worker.py'), '--', '--config', str(target)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=2700,env=blender_environment(self.local),
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        (folder/'blender.log').write_text(result.stdout+'\n'+result.stderr, encoding='utf-8')
        require(result.returncode == 0, 'Blender worker failed; inspect retained log')
        # Worker inputs are stage inputs or this stage's own outputs; execute()'s completion audit rereads them fresh.
        verify(config['inputs']); return read(folder/'worker'/'result.json')

    def _execute(self, stage, folder, *, parent_results=None):
        # Only this synchronous stage shares dependency verification. Completion
        # above uses a new pass, including ancestor bytes and review decisions.
        dependency_audit = VerificationPass()
        def parent_result(stage):
            if parent_results is not None:
                return parent_results[stage]
            return self.result(stage, _audit=dependency_audit)
        if stage == 'prepare':
            require(self.data.get('approval', {}).get('referenceDesignReviewed') is True, 'Reference design review required')
            source = Path(self.input('reference')); target = folder/'reference.png'
            with Image.open(source) as image:
                require(image.format == 'PNG' and min(image.size) >= 512, 'Use a PNG reference at least 512 pixels on each axis')
                info = {'size': list(image.size), 'mode': image.mode}
            shutil.copyfile(source, target)
            return {'reference': pin(target), 'geometryAndAppearanceUseSameReference': True,
                    'clayReferenceRequired': False, 'image': info, 'cameraReviewPending': True}
        if stage == 'inspect':
            return self.worker('inspect', folder, source=self.input('geometryRaw'))
        if stage == 'donor':
            source=self.input('geometryDonor');field=self.input('field')
            review=self.data.get('approval',{}).get('sourceDonor',{})
            require(review.get('decision')=='approved' and review.get('geometryDonorSha256')==pin(source)['sha256']
                    and review.get('fieldSha256')==pin(field)['sha256'] and review.get('notes','').strip(),
                    'Review the exact exported donor geometry and appearance field before source baking')
            from .donor import build,unwrap_source
            uv=unwrap_source(source,self.local,folder/'source-unwrap')
            return build(source,uv['uvMesh']['path'],field,self.data['processing'].get('sourceFieldPolicy'),folder/'donor')
        if stage == 'fit':
            require(self.family['nativePackaging'] == 'enabled', 'Fitting requires a measured native contract')
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
                               packing_paddings=self.data.get('processing',{}).get('uvPackingPaddings'),parts=active_parts(self.family))
            result=self.worker('unwrap',folder/'apply',scene=parent['scene']['path'],atlas=atlas['atlas']['path'])
            result['validation']=atlas;return result
        if stage in ('reduce', 'finish', 'bake', 'shadow'):
            parent = parent_result(DEPENDENCIES[stage][0]); values = {'scene': parent['scene']['path']}
            if stage == 'finish': values['reference'] = self.input('reference')
            if stage=='shadow' and self.data.get('processing',{}).get('shadowProxies'):
                values['shadowCandidates']=parent_result('reduce')['shadowPreflight']
            result = self.worker(stage, folder, **values)
            if stage=='reduce' and self.data.get('processing',{}).get('shadowProxies'):
                from .shadow import build_candidates
                result['shadowPreflight']=build_candidates(result['shadowSource']['path'],self.family,self.data['processing'],folder/'shadow-preflight')
            if stage == 'bake':
                from .textures import finish_bake
                result.update(finish_bake(result['linear']['path'], result['masks']['path'], folder/'textures'))
            return result
        if stage == 'render':
            return self.worker(stage, folder, scene=parent_result('shadow')['scene']['path'],
                               texture=parent_result('bake')['maps'][str(self.family['runtimeTextureSize'])]['path'])
        if stage == 'export':
            arrays = self.worker('export-arrays', folder, scene=parent_result('shadow')['scene']['path'])
            icons = parent_result('render')['icons']
            if self.family['family'] == 'firearm-sling':
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
            require(self.family['family'] != 'firearm-sling',
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

    def review(self, stage, decision, notes):
        require(self.runtime is not None, 'Review writes require the verified launcher')
        require(decision in ('approved', 'rejected') and notes.strip(), 'Explicit decision and review notes required')
        self.result(stage, review=False)
        target = self.run/'reviews'/f'{stage}-{uuid.uuid4().hex}.json'
        result = {'stageReceipt': self.state['stages'][stage], 'decision': decision, 'notes': notes, 'productionAccepted': False}
        write(target, result, fresh=True); self.state['reviews'][stage] = pin(target); write(self.state_path, self.state)
        return result

    def status(self):
        result = {}; audit = VerificationPass()
        for stage in DEPENDENCIES:
            try:
                self.result(stage, review=False, _audit=audit)
                try: self.result(stage, _audit=audit); result[stage] = {'state': 'complete', 'review': 'approved'}
                except (ValueError, OSError, KeyError) as exc: result[stage] = {'state': 'complete', 'review': str(exc)}
            except (ValueError, OSError, KeyError) as exc: result[stage] = {'state': 'pending-or-stale', 'reason': str(exc)}
        return {'id': self.data['id'], 'stages': result, 'productionAccepted': False}
