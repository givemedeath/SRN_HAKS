"""Execution adoption: exact caller/scope, immutable history, literal PNUT guards.

Synthetic assets are constructed beneath the consuming checkout. Real current
modules, sampler bytes, lock and validation record are pinned; archived code is
never imported, and synthetic runtimes are only byte-read, never launched.
"""
import copy
from dataclasses import FrozenInstanceError
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import phenotype_execution_adoption as execution
import phenotype_infrastructure_adoption as adoption
import target_contract as contract
import target_part_pipeline as pipeline
import pose_preview_target_parts as preview
import replay_stage_skin_intensity as intensity
from place_purposebuilt_pelvis import raw_corners, read_glb, write_glb
from test_human_female_stock_exact import stock_fixture
from test_mirror_stock_limb_part import fixture

REPO = Path(__file__).resolve().parents[2]


class ExecutionFixture:
    """Portable, independently enumerated real-14-body/16-attachment fixture."""
    def __init__(self, owner):
        scratch = REPO/'.tmp'; scratch.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix='exec-adoption-test-', dir=scratch)
        owner.addCleanup(temporary.cleanup); self.out = Path(temporary.name).resolve()
        external = tempfile.TemporaryDirectory(prefix='exec-adoption-runtime-')
        owner.addCleanup(external.cleanup); self.external = Path(external.name).resolve()
        self.target_path, self.target = stock_fixture(self.out)
        self.target = contract.load(self.target_path)
        self.archive = self.out/'preservation-v2'; (self.archive/'files').mkdir(parents=True)
        self.old_helper = REPO/'tools/phenotypes/rig_pose_audit.py'
        self.snapshot = self.out/'helpers/rig_pose_audit.py'; self.snapshot.parent.mkdir()
        self.sentinel = self.out/'OLD_CODE_EXECUTED'
        old_bytes = ("from pathlib import Path\nPath("+repr(str(self.sentinel))+ ").write_text('bad')\n").encode()
        self.snapshot.write_bytes(old_bytes)
        self.saved_helper = self.archive/'files/00000000.bin'; self.saved_helper.write_bytes(old_bytes)
        self.old_digest = contract.sha(self.saved_helper)
        doc, binary = fixture()
        self.external_source = self.external/'user-source.glb'; write_glb(self.external_source, doc, binary)
        self.local_source = self.out/'external-inputs/source.glb'; self.local_source.parent.mkdir()
        self.local_source.write_bytes(self.external_source.read_bytes())
        self.saved_source = self.archive/'files/00000001.bin'; self.saved_source.write_bytes(self.local_source.read_bytes())
        self.part_paths = {}; self.candidates = {}; self.documents = {}
        for part in sorted(contract.BODY_PARTS):
            candidate = self.out/(part+'.glb'); write_glb(candidate, doc, binary)
            original = self.write(self.out/(part+'-donor.json'), {'kind': 'original-donor', 'part': part})
            source = self.external_source if part == 'bicepl' else self.local_source
            receipt = {'schemaVersion':2, 'kind':'target-part-geometry',
                **contract.binding(self.target_path, self.target, 'working'),
                'part':part, 'joint':contract.PART_JOINTS[part], 'model':contract.model(self.target,part),
                'candidate':str(candidate), 'candidateSha256':contract.sha(candidate),
                'source':str(source), 'sourceSha256':contract.sha(source),
                'sourceReceipt':str(original), 'sourceReceiptSha256':contract.sha(original),
                'statureApplications':0,
                'attachmentWorld':self.target['rig']['frames']['working'][contract.PART_JOINTS[part]],
                'frozenInputs':{str(self.target_path):contract.sha(self.target_path),
                    str(self.old_helper):self.old_digest, str(source):contract.sha(source),
                    str(original):contract.sha(original)}}
            self.part_paths[part] = self.out/(part+'-geometry.json')
            self.candidates[part] = candidate; self.documents[part] = receipt
        extra = {}; p,n,uv,_ = raw_corners(doc,binary,extra=extra)
        native_uv = uv.copy(); native_uv[:,:,1] = 1-native_uv[:,:,1]
        self.corners = self.out/'bicepl-native-corners.npz'
        np.savez(self.corners, positions=p, normals=n, uvGltf=uv, uvNative=native_uv,
                 authoredTangents=np.concatenate(extra['TANGENT']['rows']))
        self.documents['bicepl']['nativeCornerArchive'] = self.pin(self.corners)
        self.documents['bicepl']['frozenInputs'][str(self.corners)] = contract.sha(self.corners)
        self.bank_path = self.out/'bank.json'
        self.manifest_path = self.archive/'preservation.json'
        self.proof_path = self.out/'proof.json'
        current = {str(REPO/'tools/phenotypes'/name):contract.sha(REPO/'tools/phenotypes'/name)
                   for name in (*adoption.SAMPLERS, 'phenotype_execution_adoption.py', *execution.CONSUMERS.values())}
        reconciliation = self.write(self.out/'reconciliation.json', {'schemaVersion':1,
            'kind':'phenotype-infrastructure-feature-reconciliation', 'targetId':self.target['id'],
            'upstreamCommit':'a'*40, 'helpers':{name:{'sha256':digest,
                'features':['Explicit execution-source validator fixture']} for name,digest in current.items()}})
        runtime_exe = self.external/'python.exe'; runtime_exe.write_bytes(b'only-read-never-executed')
        toolroot = self.external/'toolbank'; toolroot.mkdir()
        runtime = self.write(self.out/'runtime.json', {'schemaVersion':2, 'kind':'phenotype-shared-toolchain',
            'toolsRoot':str(toolroot), 'requiredTools':['python'], 'runtimes':{'python':self.pin(runtime_exe)}})
        migration = self.write(self.out/'migration.json', {'kind':'phenotype-shared-tool-migration',
            'smokeChecksPassed':True, 'toolchain':self.pin(runtime), 'launchHelpers':{}})
        self.proof = {'schemaVersion':2, 'kind':adoption.KIND, 'operation':adoption.OPERATION,
            'adoptionApplications':1, 'targetContract':self.pin(self.target_path), 'targetId':self.target['id'],
            'rigRevision':self.target['rig']['revision'], 'coordinateSpace':'working',
            'originalBank':{}, 'historicalReceipts':[], 'preservationManifest':{},
            'helperMappings':[{'originalClaimedSource':{'path':str(self.old_helper),'sha256':self.old_digest},
                'actualArchivedSourcePath':str(self.snapshot), 'archivedCopy':self.pin(self.saved_helper),
                'size':len(old_bytes)}],
            'assetSourceMappings':[{'originalClaimedSource':self.pin(self.external_source),
                'worktreeRelativeCopy':{'path':self.local_source.relative_to(REPO).as_posix(),
                                        'sha256':contract.sha(self.local_source)}}],
            'currentHelpers':current, 'reconciliation':self.pin(reconciliation),
            'upstreamValidation':self.pin(REPO/'docs/shared-tool-validation.json'),
            'portableToolLock':self.pin(REPO/'tools/shared-tools.lock.json'),
            'runtimeToolchain':self.pin(runtime), 'runtimeMigration':self.pin(migration), 'unchangedAssets':[],
            'originalReceiptsRewritten':False, 'historicalHelpersExecuted':False,
            'sourceAssetsChanged':False, 'approvalStateChanged':False}
        self.seal()

    @staticmethod
    def write(path, data):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data),encoding='utf-8'); return path

    @staticmethod
    def pin(path): return {'path':str(path),'sha256':contract.sha(path)}

    def seal(self):
        """Finish synthetic evidence construction, before any verification."""
        parts = {}; assets = []; closure = {}; historical = []
        for part, receipt in self.documents.items():
            path = self.write(self.part_paths[part],receipt)
            parts[part] = {'candidate':self.pin(self.candidates[part]),'geometry':self.pin(path)}
            assets.extend(parts[part].values()); closure.update(receipt['frozenInputs'])
            historical.append({'receipt':self.pin(path),'kind':receipt['kind'],'closures':['frozenInputs']})
        self.write(self.bank_path, {'kind':'unselected-fourteen-part-working-diagnostic-bank',
            'target':self.pin(self.target_path),'parts':parts,'sourceClosure':closure})
        rows = []
        for source, saved in ((self.snapshot,self.saved_helper),(self.local_source,self.saved_source)):
            rows.append({'source':str(source),'relative':source.relative_to(REPO).as_posix(),
                'copy':str(saved),'size':saved.stat().st_size,'sha256':contract.sha(saved),
                'role':'ignoredAssetOrEvidence'})
        self.write(self.manifest_path, {'kind':'pre-main-adoption-recoverable-byte-copy','mergedBase':'a'*40,
            'copiesIndependentlyHashVerified':True,'sourceWorktreeResetOrClean':False,
            'helperHashes':{str(self.old_helper):self.old_digest},'files':rows,
            'authority':{str(self.bank_path):contract.sha(self.bank_path),str(self.target_path):contract.sha(self.target_path)}})
        self.proof.update(originalBank=self.pin(self.bank_path), preservationManifest=self.pin(self.manifest_path),
            historicalReceipts=[{'receipt':self.pin(self.bank_path),
                'kind':'unselected-fourteen-part-working-diagnostic-bank','closures':['sourceClosure']},*historical],
            unchangedAssets=assets)
        self.save()

    def save(self): self.write(self.proof_path,self.proof)

    def context(self, consumer='target_part_pipeline.verify_source_receipt', parts=('bicepl',), **kw):
        return execution.prepare_execution_adoption(self.pin(self.proof_path),
            target_path=self.target_path,target=self.target,space='working',consumer=consumer,
            receipt_pins=[self.pin(self.part_paths[p]) for p in parts],**kw)

    def assembly(self):
        return {'schemaVersion':2,'kind':'target-stock-diagnostic',
            'target':contract.binding(self.target_path,self.target,'working'),
            'parts':[{'part':p,'model':contract.model(self.target,p)} for p in contract.PART_JOINTS],
            'resources':{contract.model(self.target,p)+'.mdl':'frozen-resource' for p in contract.PART_JOINTS}}


class ExecutionAdoptionTests(unittest.TestCase):
    def setUp(self): self.f = ExecutionFixture(self)

    def pipeline(self, context=None, part='bicepl', **kw):
        return pipeline.verify_source_receipt(self.f.candidates[part],self.f.part_paths[part],
            self.f.target_path,self.f.target,part,'working',execution_adoption=context,**kw)

    def select(self, context=None, parts=('bicepl',)):
        return preview.select_receipts([self.f.part_paths[p] for p in parts],self.f.target_path,
            self.f.target,'working',self.f.assembly(),execution_adoption=context)

    def intensity(self, context=None):
        return intensity.source_receipt(self.f.candidates['bicepl'],self.f.part_paths['bicepl'],
            self.f.target_path,self.f.target,'bicepl',execution_adoption=context)

    def test_all_three_explicit_consumers_accept_preserved_bytes_without_rewriting_history(self):
        history = {p:p.read_bytes() for p in [self.f.bank_path,self.f.proof_path,*self.f.part_paths.values()]}
        assets = {p:p.read_bytes() for p in self.f.candidates.values()}
        self.f.external_source.unlink()
        receipt = self.pipeline(self.f.context())
        self.assertEqual(receipt,self.f.documents['bicepl'])
        result = self.select(self.f.context('pose_preview_target_parts.select_receipts'))
        self.assertEqual(result['parts'],{'bicepl':self.f.candidates['bicepl']})
        self.assertEqual(set(result['retainedTargetStockParts']),set(contract.PART_JOINTS)-{'bicepl'})
        self.assertEqual(len(result['retainedTargetStockParts']),15)
        self.assertEqual(result['inputs'][str(self.f.local_source)],contract.sha(self.f.local_source))
        self.assertEqual(result['inputs'][str(self.f.saved_helper)],self.f.old_digest)
        self.assertNotIn(str(self.f.old_helper),result['inputs'])
        self.assertNotIn(str(self.f.external_source),result['inputs'])
        receipt,pins,lineage = self.intensity(self.f.context('replay_stage_skin_intensity.source_receipt'))
        self.assertEqual(receipt,self.f.documents['bicepl']); self.assertTrue(lineage)
        self.assertIn(str(self.f.corners),pins)
        for p,raw in {**history,**assets}.items(): self.assertEqual(p.read_bytes(),raw)
        self.assertFalse(self.f.sentinel.exists())

    def test_defaults_still_reject_stale_helpers_without_any_implicit_environment_fallback(self):
        self.f.external_source.unlink()
        with patch.dict(os.environ, {'SRN_EXECUTION_ADOPTION_PROOF':str(self.f.proof_path)}):
            for call in (self.pipeline,self.select,self.intensity):
                with self.subTest(consumer=call.__name__),self.assertRaises(ValueError): call()
        self.assertFalse(self.f.sentinel.exists())

    def test_original_missing_or_changed_external_source_is_never_read(self):
        self.f.external_source.write_bytes(b'changed-original-must-not-be-consumed')
        ctx = self.f.context(); self.pipeline(ctx)
        evidence = adoption.plain(ctx.evidence())
        rows = evidence['sourceResolutions'][str(self.f.part_paths['bicepl'])]
        source = next(row for row in rows if row['resolution']=='external-source-copy')
        self.assertEqual(source['originalClaimedSource']['sha256'],contract.sha(self.f.local_source))
        self.assertEqual(source['physicalSource']['path'],str(self.f.local_source))
        self.assertNotIn(str(self.f.external_source),evidence['verificationInputs'])
        self.assertFalse(evidence['sourceAssetsChanged']); self.assertEqual(evidence['assetOperations'],[])

    def test_context_and_nested_scope_evidence_are_immutable(self):
        ctx = self.f.context()
        with self.assertRaises(FrozenInstanceError): ctx._consumer='other'
        with self.assertRaises(TypeError): ctx._closures['extra']={}
        with self.assertRaises(TypeError): ctx.evidence()['sourceResolutions']['extra']=[]
        with self.assertRaises(TypeError): ctx._closures[str(self.f.part_paths['bicepl'])]['original']['part']='handl'

    def test_consumer_identity_cannot_be_borrowed_by_another_controlled_callsite(self):
        ctx = self.f.context()
        with self.assertRaisesRegex(ValueError,'controlled consumer'): self.select(ctx)
        with self.assertRaisesRegex(ValueError,'controlled consumer'): self.intensity(ctx)
        with self.assertRaisesRegex(ValueError,'controlled consumer'):
            execution.resolve_frozen_inputs(ctx,module_file=str(self.f.snapshot),
                consumer='target_part_pipeline.verify_source_receipt',receipt_path=self.f.part_paths['bicepl'],
                receipt=self.f.documents['bicepl'],target_path=self.f.target_path,target=self.f.target,space='working')

    def test_only_explicit_requested_receipts_can_be_consumed(self):
        ctx = self.f.context()
        with self.assertRaisesRegex(ValueError,'outside requested'): self.pipeline(ctx,'bicepr')
        ctx = self.f.context('pose_preview_target_parts.select_receipts')
        with self.assertRaisesRegex(ValueError,'outside requested'): self.select(ctx,('bicepl','bicepr'))
        self.assertEqual(len(ctx.evidence()['receiptPins']),1)

    def test_undeclared_changed_duplicate_or_empty_requested_pins_rejected(self):
        proper = self.f.pin(self.f.part_paths['bicepl'])
        outside = self.f.write(self.f.out/'unlisted.json',self.f.documents['bicepl'])
        samples = [[],[proper,proper],[{**proper,'sha256':'0'*64}],[self.f.pin(outside)]]
        for pins in samples:
            with self.subTest(pins=pins),self.assertRaises(ValueError):
                execution.prepare_execution_adoption(self.f.pin(self.f.proof_path),target_path=self.f.target_path,
                    target=self.f.target,space='working',consumer='target_part_pipeline.verify_source_receipt',receipt_pins=pins)

    def test_exact_new_helper_and_controlled_consumer_must_be_in_fresh_current_helpers(self):
        original = copy.deepcopy(self.f.proof)
        for name in ('phenotype_execution_adoption.py','target_part_pipeline.py'):
            with self.subTest(helper=name):
                self.f.proof = copy.deepcopy(original)
                path = str(REPO/'tools/phenotypes'/name); del self.f.proof['currentHelpers'][path]
                reconciled = {'schemaVersion':1, 'kind':'phenotype-infrastructure-feature-reconciliation',
                    'targetId':self.f.target['id'], 'upstreamCommit':'a'*40,
                    'helpers':{k:{'sha256':v,'features':['Explicit scoped test validator']}
                               for k,v in self.f.proof['currentHelpers'].items()}}
                fresh = self.f.write(self.f.out/(name+'-reconciliation.json'),reconciled)
                self.f.proof['reconciliation'] = self.f.pin(fresh); self.f.save()
                with self.assertRaisesRegex(ValueError,'absent or stale'): self.f.context()

    def test_stale_current_helper_hash_is_not_rehashed_or_replaced(self):
        path = str(REPO/'tools/phenotypes/target_part_pipeline.py')
        self.f.proof['currentHelpers'][path]='0'*64; self.f.save()
        with self.assertRaises(ValueError): self.f.context()

    def test_cross_target_space_and_uncontrolled_consumers_rejected(self):
        for consumer in ('pose_preview.py','staging','replay_stage_skin_calibration.geometry_input'):
            with self.subTest(consumer=consumer),self.assertRaisesRegex(ValueError,'Unsupported'):
                self.f.context(consumer)
        changed = copy.deepcopy(self.f.target); changed['id']='different-target'
        for target,space in ((changed,'working'),(self.f.target,'runtime')):
            with self.subTest(space=space),self.assertRaisesRegex(ValueError,'target/rig/space'):
                execution.prepare_execution_adoption(self.f.pin(self.f.proof_path),target_path=self.f.target_path,
                    target=target,space=space,consumer='target_part_pipeline.verify_source_receipt',
                    receipt_pins=[self.f.pin(self.f.part_paths['bicepl'])])
        ctx = self.f.context()
        with self.assertRaises(ValueError):
            execution.resolve_frozen_inputs(ctx,module_file=pipeline.__file__,
                consumer='target_part_pipeline.verify_source_receipt',receipt_path=self.f.part_paths['bicepl'],
                receipt=self.f.documents['bicepl'],target_path=self.f.target_path,target=changed,space='working')

    def test_changed_in_memory_receipt_cannot_substitute_a_new_closure_or_digest(self):
        ctx = self.f.context(); changed=copy.deepcopy(self.f.documents['bicepl'])
        changed['frozenInputs'][str(self.f.old_helper)] = contract.sha(self.f.old_helper)
        with self.assertRaisesRegex(ValueError,'receipt or closure changed'):
            execution.resolve_frozen_inputs(ctx,module_file=pipeline.__file__,
                consumer='target_part_pipeline.verify_source_receipt',receipt_path=self.f.part_paths['bicepl'],
                receipt=changed,target_path=self.f.target_path,target=self.f.target,space='working')

    def test_post_verification_helper_archive_drift_is_rejected(self):
        ctx=self.f.context(); self.f.saved_helper.write_bytes(b'changed-archive')
        with self.assertRaises(ValueError): self.pipeline(ctx)
        self.assertFalse(self.f.sentinel.exists())

    def test_post_verification_local_asset_drift_is_rejected(self):
        ctx=self.f.context(); self.f.local_source.write_bytes(b'changed-local')
        with self.assertRaises(ValueError): self.pipeline(ctx)

    def test_post_verification_receipt_and_candidate_bytes_remain_protected(self):
        for kind in ('receipt','candidate'):
            with self.subTest(kind=kind):
                ctx=self.f.context(); path=self.f.part_paths['bicepl'] if kind=='receipt' else self.f.candidates['bicepl']
                raw=path.read_bytes(); path.write_bytes(raw+b' ')
                with self.assertRaises(ValueError): self.pipeline(ctx)
                path.write_bytes(raw)

    def test_bank_neighbor_target_and_frames_remain_protected(self):
        ctx=self.f.context()
        for path in (self.f.candidates['handr'],self.f.target_path):
            with self.subTest(path=path):
                raw=path.read_bytes(); path.write_bytes(raw+b' ')
                with self.assertRaises(ValueError): self.pipeline(ctx)
                path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'part/attachment'):
            pipeline.verify_source_receipt(self.f.candidates['bicepl'],self.f.part_paths['bicepl'],
                self.f.target_path,self.f.target,'handl','working',execution_adoption=ctx)

    def test_original_source_provenance_and_attachment_guards_are_not_bypassed(self):
        original=copy.deepcopy(self.f.documents['bicepl'])
        for key,value in [('model','pfh0_handl001'),('statureApplications',1),('joint','rhand_g')]:
            with self.subTest(field=key):
                self.f.documents['bicepl']=copy.deepcopy(original); self.f.documents['bicepl'][key]=value; self.f.seal()
                with self.assertRaises(ValueError): self.f.context()
        self.f.documents['bicepl']=copy.deepcopy(original)
        del self.f.documents['bicepl']['frozenInputs'][original['sourceReceipt']]; self.f.seal()
        with self.assertRaisesRegex(ValueError,'provenance missing'): self.f.context()

    def test_repeated_or_non_geometry_adoption_receipts_are_not_execution_sources(self):
        ctx=self.f.context()
        repeated=self.f.write(self.f.out/'context.json',adoption.plain(ctx.evidence()))
        with self.assertRaises(ValueError):
            execution.prepare_execution_adoption(self.f.pin(self.f.proof_path),target_path=self.f.target_path,
                target=self.f.target,space='working',consumer='target_part_pipeline.verify_source_receipt',
                receipt_pins=[self.f.pin(repeated)])
        self.f.proof['adoptionApplications']=2; self.f.save()
        with self.assertRaises(ValueError): self.f.context()

    def test_resolution_is_independent_of_cwd(self):
        ctx=self.f.context(); old=Path.cwd()
        try:
            os.chdir(self.f.external)
            self.pipeline(ctx)
        finally: os.chdir(old)
        self.assertFalse(self.f.sentinel.exists())

    def test_serialized_corner_normals_uv_and_tangents_still_have_literal_byte_guards(self):
        with np.load(self.f.corners,allow_pickle=False) as saved:
            arrays={k:saved[k].copy() for k in saved.files}
        for key in ('positions','normals','uvGltf','uvNative','authoredTangents'):
            with self.subTest(attribute=key):
                changed={k:v.copy() for k,v in arrays.items()}; changed[key].flat[0]+=.125
                np.savez(self.f.corners,**changed)
                self.f.documents['bicepl']['nativeCornerArchive']=self.f.pin(self.f.corners)
                self.f.documents['bicepl']['frozenInputs'][str(self.f.corners)]=contract.sha(self.f.corners)
                self.f.seal()
                ctx=self.f.context('replay_stage_skin_intensity.source_receipt')
                with self.assertRaisesRegex(ValueError,'corner archive differs|tangent archive differs'): self.intensity(ctx)
        self.assertFalse(self.f.sentinel.exists())

    def test_unverified_context_objects_are_not_accepted(self):
        for fake in (object(), {}, execution.ExecutionAdoption(), adoption.verify_proof(self.f.pin(self.f.proof_path))):
            with self.subTest(type=type(fake).__name__),self.assertRaisesRegex(ValueError,'Verified explicit|Unverified execution'):
                self.pipeline(fake)

    def test_legacy_intensity_explicit_helpers_behavior_is_unchanged(self):
        helper=self.f.out/'legacy/helpers/old-helper.py'; helper.parent.mkdir(parents=True); helper.write_bytes(b'old-data')
        # The original generic helper resolver remains a separate legacy policy.
        old=Path(intensity.__file__).with_name('old-helper.py')
        digest=contract.sha(helper)
        receipt={'frozenInputs':{str(old):digest,str(helper):digest}}
        pins,resolutions=intensity.frozen_inputs(receipt,self.f.out/'legacy/receipt.json')
        self.assertEqual(pins,{str(helper):digest})
        self.assertEqual(resolutions,[{'originalPath':str(old),'recordedSha256':digest,'snapshot':self.f.pin(helper)}])


if __name__=='__main__': unittest.main()
