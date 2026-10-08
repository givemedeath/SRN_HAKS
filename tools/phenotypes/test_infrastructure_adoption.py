"""Explicit adoption guards, old-validator failure and declaration-only boundaries."""
import copy
import json
import os
import subprocess
from pathlib import Path
import tempfile
import unittest

import phenotype_infrastructure_adoption as adoption
import target_contract as contract
from target_part_pipeline import verify_source_receipt
from test_human_female_stock_exact import stock_fixture


class AdoptionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.bank = self.root/'tools'/'phenotypes'; self.bank.mkdir(parents=True)
        self.out = self.root/'output'; self.out.mkdir()
        self.archive = self.out/'preservation-v2'; (self.archive/'files').mkdir(parents=True)
        self.target_path, self.target = stock_fixture(self.out)
        self.old = self.bank/'rig_pose_audit.py'
        # This code must remain inert evidence. Executing it would create a sentinel.
        old_bytes = ("from pathlib import Path\nPath("+repr(str(self.root/'OLD_CODE_EXECUTED'))+").write_text('bad')\n").encode()
        snapshot = self.out/'helpers'/'rig_pose_audit.py'; snapshot.parent.mkdir(); snapshot.write_bytes(old_bytes)
        backup = self.archive/'files'/'00000000.bin'; backup.write_bytes(old_bytes)
        old_digest = adoption.sha(backup)
        benchmark = {}; helpers = {}
        for name in adoption.SAMPLERS:
            path = self.bank/name
            content = ('# main '+name+'\n').encode()
            if name == 'target_contract.py':
                path.write_bytes(content.replace(b'\n', b'\r\n'))
            else:
                path.write_bytes(content)
            benchmark[name] = __import__('hashlib').sha256(content).hexdigest()
            helpers[str(path)] = adoption.sha(path)
        validation = self.write(self.root/'docs'/'shared-tool-validation.json', {'boundBenchmarkHelperHashes': benchmark})
        self.geometry_rows = []
        parts = {}; assets = {}; closure = {str(self.target_path): adoption.sha(self.target_path), str(self.old): old_digest}
        for part in sorted(contract.BODY_PARTS):
            joint = contract.PART_JOINTS[part]
            candidate = self.out/(part+'.glb'); candidate.write_bytes(('immutable-'+part).encode())
            source = self.out/(part+'-original.glb'); source.write_bytes(('source-'+part).encode())
            original = self.write(self.out/(part+'-source.json'), {'kind': 'original-donor'})
            receipt = {'schemaVersion': 2, 'kind': 'target-part-geometry',
                **contract.binding(self.target_path, self.target, 'working'), 'part': part, 'joint': joint,
                'model': contract.model(self.target, part), 'candidate': str(candidate), 'candidateSha256': adoption.sha(candidate),
                'source': str(source), 'sourceSha256': adoption.sha(source), 'sourceReceipt': str(original),
                'sourceReceiptSha256': adoption.sha(original), 'attachmentWorld': self.target['rig']['frames']['working'][joint],
                'statureApplications': 0, 'frozenInputs': {**closure, str(source): adoption.sha(source), str(original): adoption.sha(original)}}
            path = self.write(self.out/(part+'-geometry.json'), receipt)
            self.geometry_rows.append({'receipt': self.pin(path), 'kind': receipt['kind'], 'closures': ['frozenInputs']})
            parts[part] = {'candidate': self.pin(candidate), 'geometry': self.pin(path)}
            assets[str(path)] = self.pin(path); assets[str(candidate)] = self.pin(candidate)
            closure.update(receipt['frozenInputs'])
        self.original_bank = self.write(self.out/'bank.json', {'kind': 'unselected-fourteen-part-working-diagnostic-bank',
            'target': self.pin(self.target_path), 'parts': parts, 'sourceClosure': closure})
        self.manifest_data = {'kind': 'pre-main-adoption-recoverable-byte-copy', 'mergedBase': 'a'*40,
            'copiesIndependentlyHashVerified': True, 'sourceWorktreeResetOrClean': False,
            'helperHashes': {str(self.old): old_digest},
            'authority': {str(self.original_bank): adoption.sha(self.original_bank), str(self.target_path): adoption.sha(self.target_path)},
            'files': [{'source': str(snapshot), 'relative': snapshot.relative_to(self.root).as_posix(),
                       'copy': str(backup), 'size': len(old_bytes), 'sha256': old_digest, 'role': 'ignoredAssetOrEvidence'}]}
        self.manifest = self.write(self.archive/'preservation.json', self.manifest_data)
        reconciliation = self.write(self.out/'reconciliation.json', {'schemaVersion': 1,
            'kind': 'phenotype-infrastructure-feature-reconciliation', 'targetId': self.target['id'], 'upstreamCommit': 'a'*40,
            'helpers': {name: {'sha256': value, 'features': ['Explicit unchanged main sampler']} for name, value in helpers.items()}})
        runtime_exe = self.out/'python.exe'; runtime_exe.write_bytes(b'only-pinned-never-executed')
        tool_root = self.out/'toolbank'; tool_root.mkdir()
        runtime = self.write(self.out/'runtime.json', {'schemaVersion': 2, 'kind': 'phenotype-shared-toolchain',
            'toolsRoot': str(tool_root), 'requiredTools': ['python'], 'runtimes': {'python': self.pin(runtime_exe)}})
        self.migration = self.write(self.out/'migration.json', {'kind': 'phenotype-shared-tool-migration',
            'smokeChecksPassed': True, 'toolchain': self.pin(runtime), 'launchHelpers': {}})
        lock = self.write(self.root/'tools'/'shared-tools.lock.json', {'schemaVersion': 1})
        self.proof = {'schemaVersion': 1, 'kind': adoption.KIND, 'operation': adoption.OPERATION, 'adoptionApplications': 1,
            'targetContract': self.pin(self.target_path), 'targetId': self.target['id'], 'rigRevision': self.target['rig']['revision'],
            'coordinateSpace': 'working', 'originalBank': self.pin(self.original_bank),
            'historicalReceipts': [{'receipt': self.pin(self.original_bank), 'kind': 'unselected-fourteen-part-working-diagnostic-bank',
                                    'closures': ['sourceClosure']}, *self.geometry_rows],
            'helperMappings': [{'originalClaimedSource': {'path': str(self.old), 'sha256': old_digest},
                'actualArchivedSourcePath': str(snapshot), 'archivedCopy': self.pin(backup), 'size': len(old_bytes)}],
            'preservationManifest': self.pin(self.manifest), 'currentHelpers': helpers,
            'reconciliation': self.pin(reconciliation), 'upstreamValidation': self.pin(validation), 'portableToolLock': self.pin(lock),
            'runtimeToolchain': self.pin(runtime), 'runtimeMigration': self.pin(self.migration), 'unchangedAssets': list(assets.values()),
            'originalReceiptsRewritten': False, 'historicalHelpersExecuted': False, 'sourceAssetsChanged': False, 'approvalStateChanged': False}
        self.proof_path = self.out/'proof.json'; self.save()

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value), encoding='utf-8'); return path

    def pin(self, path):
        return {'path': str(path), 'sha256': adoption.sha(path)}

    def save(self):
        self.write(self.proof_path, self.proof)

    def verify(self):
        self.save(); return adoption.verify_proof(self.pin(self.proof_path), repo=self.root)

    def request(self):
        return {'schemaVersion': 1, 'kind': adoption.REQUEST_KIND, 'proof': self.pin(self.proof_path),
            **{name: self.proof[name] for name in ('targetContract', 'targetId', 'rigRevision', 'coordinateSpace', 'originalBank')},
            'consumer': 'resume-declaration', 'preparationInputs': []}

    def refresh_asset_fixture_pins(self):
        """Finish constructing fixture evidence; later tests preserve these bytes."""
        bank = adoption.read_json(self.original_bank)
        by_geometry = {row['receipt']['path']: row for row in self.geometry_rows}
        for item in bank['parts'].values():
            geometry_path = Path(item['geometry']['path'])
            item['geometry'] = self.pin(geometry_path)
            by_geometry[str(geometry_path)]['receipt'] = item['geometry']
        self.write(self.original_bank, bank)
        self.proof['originalBank'] = self.pin(self.original_bank)
        self.proof['historicalReceipts'][0]['receipt'] = self.pin(self.original_bank)
        for item in self.proof['unchangedAssets']:
            item['sha256'] = adoption.sha(item['path'])
        self.manifest_data['authority'][str(self.original_bank)] = adoption.sha(self.original_bank)
        self.write(self.manifest, self.manifest_data)
        self.proof['preservationManifest'] = self.pin(self.manifest)
        self.save()

    def add_external_asset_mapping(self, suffix='.glb', *, claimed=True):
        external = tempfile.TemporaryDirectory(); self.addCleanup(external.cleanup)
        external_root = Path(external.name).resolve()
        self.assertFalse(external_root.is_relative_to(self.root))
        ordinal = len(self.manifest_data['files'])
        original = external_root/('user-source'+suffix)
        payload = ('literal-original-source-'+str(ordinal)+suffix).encode()
        original.write_bytes(payload)
        relative = 'output/external-inputs/source-'+str(ordinal)+'/source'+suffix
        local = self.root/relative; local.parent.mkdir(parents=True); local.write_bytes(payload)
        archive = self.archive/'files'/('%08d.bin' % ordinal); archive.write_bytes(payload)
        expected = adoption.sha(original)
        self.manifest_data['files'].append({'source':str(local),'relative':relative,
            'copy':str(archive),'size':len(payload),'sha256':expected,'role':'ignoredAssetOrEvidence'})
        self.proof['schemaVersion'] = 2
        mapping = {'originalClaimedSource':self.pin(original),
                   'worktreeRelativeCopy':{'path':relative,'sha256':expected}}
        self.proof.setdefault('assetSourceMappings', []).append(mapping)
        if claimed:
            bank = adoption.read_json(self.original_bank)
            bank['sourceClosure'][str(original)] = expected
            self.write(self.original_bank, bank)
            geometry = Path(self.geometry_rows[0]['receipt']['path'])
            document = adoption.read_json(geometry)
            document['frozenInputs'][str(original)] = expected
            self.write(geometry, document)
        self.refresh_asset_fixture_pins()
        return {'original':original,'local':local,'archive':archive,'mapping':mapping,'bytes':payload}

    def test_v2_missing_external_glb_and_png_resolve_only_to_preserved_local_bytes(self):
        samples = [self.add_external_asset_mapping('.glb'), self.add_external_asset_mapping('.png')]
        historical = {str(self.original_bank):self.original_bank.read_bytes(),
                      **{row['receipt']['path']:Path(row['receipt']['path']).read_bytes() for row in self.geometry_rows}}
        for sample in samples:
            sample['original'].unlink()
        result = self.verify()
        self.assertEqual(len(result.assetResolutions), 2)
        for sample in samples:
            self.assertNotIn(str(sample['original']), result.inputs)
            self.assertEqual(result.inputs[str(sample['local'])], sample['mapping']['originalClaimedSource']['sha256'])
            self.assertEqual(sample['local'].read_bytes(), sample['bytes'])
        self.assertEqual([adoption.plain(row['originalClaimedSource']) for row in result.assetResolutions],
                         [sample['mapping']['originalClaimedSource'] for sample in samples])
        request_path = self.write(self.out/'request-v2.json', self.request())
        declaration = adoption.declare_preparation(self.pin(request_path), self.out/'binding-v2.json', repo=self.root)
        self.assertEqual(declaration['historicalAssetResolutions'], adoption.plain(result.assetResolutions))
        self.assertEqual(declaration['operations'], [])
        self.assertFalse(declaration['consumerExecutionSupported'])
        self.assertFalse(declaration['sourceAssetsChanged'])
        for path, expected in historical.items():
            self.assertEqual(Path(path).read_bytes(), expected)
        for sample in samples:
            self.assertNotIn(str(sample['original']), declaration['resolvedInputs'])

    def test_v2_relative_resolution_is_independent_of_cwd_and_changed_original(self):
        sample = self.add_external_asset_mapping()
        sample['original'].write_bytes(b'changed-original-must-not-be-consumed')
        old_cwd = Path.cwd()
        try:
            os.chdir(sample['original'].parent)
            result = self.verify()
        finally:
            os.chdir(old_cwd)
        self.assertEqual(result.inputs[str(sample['local'])], adoption.sha(sample['local']))
        self.assertNotIn(str(sample['original']), result.inputs)
        self.assertEqual(sample['local'].read_bytes(), sample['bytes'])

    def test_v2_noncanonical_absolute_drive_unc_backslash_and_parent_paths_rejected(self):
        sample = self.add_external_asset_mapping()
        original = copy.deepcopy(self.proof)
        paths = ['', '.', '../source.glb', '/absolute/source.glb', str(sample['local']),
                 'C:source.glb', 'C:/source.glb', '//server/share/source.glb',
                 r'\\server\share\source.glb', r'output\external-inputs\source.glb',
                 'output//external-inputs/source.glb', './output/external-inputs/source.glb',
                 'output/external-inputs/../source.glb', 'output/external-inputs/name:stream.glb']
        for value in paths:
            with self.subTest(path=value):
                self.proof = copy.deepcopy(original)
                self.proof['assetSourceMappings'][0]['worktreeRelativeCopy']['path'] = value
                with self.assertRaises(ValueError): self.verify()

    def test_v2_real_directory_link_escape_is_rejected(self):
        sample = self.add_external_asset_mapping()
        shortcut = self.out/'external-link'
        if os.name == 'nt':
            subprocess.run(['cmd','/c','mklink','/J',str(shortcut),str(sample['original'].parent)],
                           check=True,capture_output=True)
        else:
            shortcut.symlink_to(sample['original'].parent, target_is_directory=True)
        try:
            self.proof['assetSourceMappings'][0]['worktreeRelativeCopy']['path'] = 'output/external-link/user-source.glb'
            self.assertTrue((self.root/'output/external-link/user-source.glb').is_file())
            with self.assertRaises(ValueError): self.verify()
        finally:
            if os.name == 'nt': shortcut.rmdir()
            else: shortcut.unlink()
        self.assertEqual(sample['original'].read_bytes(), sample['bytes'])

    def test_v2_digest_replacement_and_fresh_hashing_cannot_hide_stale_copy(self):
        sample = self.add_external_asset_mapping()
        original = copy.deepcopy(self.proof)
        for field in ('originalClaimedSource', 'worktreeRelativeCopy'):
            with self.subTest(field=field):
                self.proof = copy.deepcopy(original)
                self.proof['assetSourceMappings'][0][field]['sha256'] = '0'*64
                with self.assertRaises(ValueError): self.verify()
        self.proof = copy.deepcopy(original)
        sample['local'].write_bytes(b'new-local-copy')
        with self.assertRaises(ValueError): self.verify()
        new_digest = adoption.sha(sample['local'])
        for field in ('originalClaimedSource', 'worktreeRelativeCopy'):
            self.proof['assetSourceMappings'][0][field]['sha256'] = new_digest
        with self.assertRaises(ValueError): self.verify()

    def test_v2_missing_local_copy_or_corrupt_preservation_archive_rejected(self):
        sample = self.add_external_asset_mapping()
        sample['local'].unlink()
        with self.assertRaises(ValueError): self.verify()
        sample['local'].write_bytes(sample['bytes'])
        sample['archive'].write_bytes(b'corrupt-preservation')
        with self.assertRaises(ValueError): self.verify()
        sample['archive'].unlink()
        with self.assertRaises(ValueError): self.verify()

    def test_v2_duplicate_unused_and_unsupported_original_mappings_rejected(self):
        sample = self.add_external_asset_mapping()
        original = copy.deepcopy(self.proof)
        self.proof['assetSourceMappings'].append(copy.deepcopy(sample['mapping']))
        with self.assertRaises(ValueError): self.verify()
        self.proof = copy.deepcopy(original)
        for path in (str(sample['local']), str(sample['original'].with_suffix('.json')), 'relative-source.glb'):
            with self.subTest(originalPath=path):
                self.proof = copy.deepcopy(original)
                self.proof['assetSourceMappings'][0]['originalClaimedSource']['path'] = path
                with self.assertRaises(ValueError): self.verify()
        self.proof = copy.deepcopy(original)
        self.add_external_asset_mapping('.png', claimed=False)
        with self.assertRaises(ValueError): self.verify()

    def test_v2_exact_original_closure_digest_and_preservation_identity_required(self):
        sample = self.add_external_asset_mapping()
        bank = adoption.read_json(self.original_bank)
        bank['sourceClosure'][str(sample['original'])] = '0'*64
        self.write(self.original_bank, bank); self.refresh_asset_fixture_pins()
        with self.assertRaises(ValueError): self.verify()
        bank['sourceClosure'][str(sample['original'])] = sample['mapping']['originalClaimedSource']['sha256']
        self.write(self.original_bank, bank); self.refresh_asset_fixture_pins()
        original = copy.deepcopy(self.manifest_data)
        for field, value in [('relative','output/wrong-source.glb'), ('size',1), ('sha256','0'*64)]:
            with self.subTest(field=field):
                self.manifest_data = copy.deepcopy(original)
                self.manifest_data['files'][-1][field] = value
                self.write(self.manifest, self.manifest_data)
                self.proof['preservationManifest'] = self.pin(self.manifest)
                with self.assertRaises(ValueError): self.verify()

    def test_v2_post_verification_copy_drift_invalidates_declaration(self):
        sample = self.add_external_asset_mapping()
        sample['original'].unlink()
        result = self.verify()
        sample['local'].write_bytes(b'changed-after-verification')
        with self.assertRaisesRegex(ValueError, 'Adoption input changed'): result.verify()
        request_path = self.write(self.out/'stale-request.json', self.request())
        with self.assertRaises(ValueError):
            adoption.declare_preparation(self.pin(request_path), self.out/'stale-binding.json', repo=self.root)
        self.assertFalse((self.out/'stale-binding.json').exists())

    def test_v1_keeps_literal_external_input_requirement_and_does_not_infer_mapping(self):
        sample = self.add_external_asset_mapping()
        self.proof['schemaVersion'] = 1
        del self.proof['assetSourceMappings']
        self.verify()
        sample['original'].unlink()
        with self.assertRaisesRegex(ValueError, 'Changed adoption input'): self.verify()

    def test_v2_mapping_field_schema_is_explicit_and_not_accepted_by_v1(self):
        sample = self.add_external_asset_mapping()
        original = copy.deepcopy(self.proof)
        for mutate in (lambda: self.proof.pop('assetSourceMappings'),
                       lambda: self.proof['assetSourceMappings'][0].update(implicitFallback=True),
                       lambda: self.proof.update(schemaVersion=True),
                       lambda: self.proof.update(schemaVersion=1)):
            with self.subTest(mutate=mutate):
                self.proof = copy.deepcopy(original); mutate()
                with self.assertRaises(ValueError): self.verify()

    def test_exact_content_address_snapshot_and_raw_vs_committed_are_distinct(self):
        result = self.verify()
        self.assertFalse((self.root/'OLD_CODE_EXECUTED').exists())
        representation = result.samplerRepresentations['target_contract.py']
        self.assertNotEqual(representation['actualRawSha256'], representation['committedLfSha256'])
        self.assertFalse(representation['rawEqualsCommittedBytes'])
        self.assertFalse(representation['runtimeBenchmarkIdentityClaimed'])
        self.assertEqual(result.helperResolutions[0]['originalClaimedSource']['path'], str(self.old))
        self.assertNotEqual(result.helperResolutions[0]['actualArchivedSourcePath'], str(self.old))
        with self.assertRaises(TypeError): result.inputs['invented'] = 'bad'
        with self.assertRaises(TypeError): result.proof['helperMappings'][0]['size'] = 0

    def test_real_female_sixteen_attachments_keep_stock_head_neck_out_of_fourteen_body_bank(self):
        target_before = self.target_path.read_bytes()
        loaded = contract.load(self.target_path)
        self.assertEqual(loaded['identity']['prefix'], 'pfh0')
        self.assertEqual(len(contract.PART_JOINTS), 16)
        self.assertEqual(set(loaded['models']), set(contract.PART_JOINTS))
        bank = adoption.read_json(self.original_bank)
        self.assertEqual(len(bank['parts']), 14)
        self.assertEqual(set(bank['parts']), contract.BODY_PARTS)
        self.assertEqual(set(loaded['models'])-set(bank['parts']), {'head', 'neck'})
        self.verify()
        self.assertEqual(self.target_path.read_bytes(), target_before)
        original = copy.deepcopy(bank)
        for retained in ('head', 'neck'):
            with self.subTest(retained=retained):
                changed = copy.deepcopy(original); changed['parts'][retained] = changed['parts']['chest']
                self.write(self.original_bank, changed)
                self.proof['originalBank'] = self.pin(self.original_bank)
                manifest = copy.deepcopy(self.manifest_data)
                manifest['authority'][str(self.original_bank)] = adoption.sha(self.original_bank)
                self.write(self.manifest, manifest); self.proof['preservationManifest'] = self.pin(self.manifest)
                with self.assertRaisesRegex(ValueError, 'Exact target fourteen-part bank'):
                    self.verify()
    def test_original_validator_still_rejects_unadapted_stale_receipt(self):
        self.verify(); entry = self.geometry_rows[0]['receipt']; receipt = adoption.read_json(entry['path'])
        with self.assertRaisesRegex(ValueError, 'Frozen input changed'):
            verify_source_receipt(Path(receipt['candidate']), Path(entry['path']), self.target_path, self.target, receipt['part'], 'working')

    def test_fresh_declaration_has_no_executable_operations_or_history_changes(self):
        before = {str(p): adoption.sha(p) for p in self.out.glob('*') if p.is_file() and p != self.proof_path}
        self.verify(); request_path = self.write(self.out/'request.json', self.request())
        output = self.out/'binding.json'
        result = adoption.declare_preparation(self.pin(request_path), output, repo=self.root)
        self.assertEqual(result['kind'], adoption.BINDING_KIND); self.assertEqual(result['operations'], [])
        self.assertFalse(result['consumerExecutionSupported']); self.assertFalse(result['historicalHelpersExecuted'])
        self.assertEqual(result, adoption.read_json(output))
        for path, expected in before.items(): self.assertEqual(adoption.sha(path), expected)
        with self.assertRaises(FileExistsError): adoption.declare_preparation(self.pin(request_path), output, repo=self.root)

    def test_changed_archive_size_manifest_association_or_digest_rejected(self):
        original = copy.deepcopy(self.proof)
        for mutate in [lambda: self.proof['helperMappings'][0].update(size=1),
                       lambda: self.proof['helperMappings'][0].update(actualArchivedSourcePath=str(self.out/'wrong.py')),
                       lambda: self.proof['helperMappings'][0]['archivedCopy'].update(sha256='0'*64),
                       lambda: self.proof['helperMappings'][0]['originalClaimedSource'].update(sha256='0'*64)]:
            with self.subTest(mutate=mutate):
                self.proof = copy.deepcopy(original); mutate()
                with self.assertRaises(ValueError): self.verify()
        self.proof = original; Path(self.proof['helperMappings'][0]['archivedCopy']['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Changed adoption input'): self.verify()

    def test_nonhelper_cross_checkout_unused_and_duplicate_mappings_rejected(self):
        original = copy.deepcopy(self.proof)
        for mutate in [lambda: self.proof['helperMappings'][0]['originalClaimedSource'].update(path=str(self.out/'asset.glb')),
                       lambda: self.proof['helperMappings'][0]['originalClaimedSource'].update(path=str(self.root.parent/'other'/'rig_pose_audit.py')),
                       lambda: self.proof['helperMappings'].append(copy.deepcopy(self.proof['helperMappings'][0])),
                       lambda: self.proof.update(helperMappings=[])]:
            with self.subTest(mutate=mutate):
                self.proof = copy.deepcopy(original); mutate()
                with self.assertRaises(ValueError): self.verify()

    def test_archive_copy_escape_and_wrong_relative_source_rejected(self):
        data = copy.deepcopy(self.manifest_data)
        outside = self.root/'outside.bin'; outside.write_bytes(Path(data['files'][0]['copy']).read_bytes())
        data['files'][0]['copy'] = str(outside); self.write(self.manifest, data)
        self.proof['preservationManifest'] = self.pin(self.manifest)
        self.proof['helperMappings'][0]['archivedCopy'] = self.pin(outside)
        with self.assertRaisesRegex(ValueError, 'flat preservation'): self.verify()
        self.write(self.manifest, self.manifest_data); self.proof['preservationManifest'] = self.pin(self.manifest)
        self.manifest_data['files'][0]['relative'] = '../escape.py'; self.write(self.manifest, self.manifest_data)
        self.proof['preservationManifest'] = self.pin(self.manifest)
        with self.assertRaisesRegex(ValueError, 'relative identity'): self.verify()

    def test_original_receipt_candidate_asset_and_frame_corruption_rejected(self):
        geometry = Path(self.geometry_rows[0]['receipt']['path']); original = geometry.read_bytes()
        geometry.write_bytes(b'{}')
        with self.assertRaises(ValueError): self.verify()
        geometry.write_bytes(original); document = adoption.read_json(geometry)
        candidate = Path(document['candidate']); saved = candidate.read_bytes(); candidate.write_bytes(b'changed')
        with self.assertRaises(ValueError): self.verify()
        candidate.write_bytes(saved)
        document['attachmentWorld'][0][3] += .01; self.write(geometry, document)
        with self.assertRaises(ValueError): self.verify()

    def test_target_space_repeat_and_approval_scope_rejected(self):
        original = copy.deepcopy(self.proof)
        for field, value in [('targetId', 'other'), ('rigRevision', 'other'), ('coordinateSpace', 'runtime'),
                             ('adoptionApplications', 2), ('adoptionApplications', True),
                             ('approvalStateChanged', True), ('historicalHelpersExecuted', True),
                             ('originalReceiptsRewritten', True), ('sourceAssetsChanged', True)]:
            with self.subTest(field=field):
                self.proof = copy.deepcopy(original); self.proof[field] = value
                with self.assertRaises(ValueError): self.verify()

    def test_current_helper_benchmark_and_runtime_staleness_rejected(self):
        self.old.write_bytes(b'# wrong main shape\n')
        with self.assertRaisesRegex(ValueError, 'Changed adoption input'): self.verify()
        self.proof['currentHelpers'][str(self.old)] = adoption.sha(self.old)
        reconciliation = adoption.read_json(self.proof['reconciliation']['path'])
        reconciliation['helpers'][str(self.old)]['sha256'] = adoption.sha(self.old)
        self.write(Path(self.proof['reconciliation']['path']), reconciliation)
        self.proof['reconciliation'] = self.pin(self.proof['reconciliation']['path'])
        with self.assertRaisesRegex(ValueError, 'Committed sampler'): self.verify()

    def test_missing_failed_or_differently_bound_runtime_migration_rejected(self):
        original = adoption.read_json(self.migration)
        for field, value in [('smokeChecksPassed', False), ('toolchain', {'path': str(self.root/'other.json'), 'sha256': '0'*64})]:
            with self.subTest(field=field):
                data = copy.deepcopy(original); data[field] = value; self.write(self.migration, data)
                self.proof['runtimeMigration'] = self.pin(self.migration)
                with self.assertRaises(ValueError): self.verify()

    def test_access_and_completion_drift_invalidate_verified_declaration(self):
        result = self.verify(); candidate = Path(adoption.read_json(self.geometry_rows[0]['receipt']['path'])['candidate'])
        candidate.write_bytes(b'changed-after-verification')
        with self.assertRaisesRegex(ValueError, 'Adoption input changed'): result.verify()

    def test_request_cannot_cross_target_promote_or_replace_a_source_digest(self):
        self.verify(); original = self.request()
        for field, value in [('targetId', 'other'), ('coordinateSpace', 'runtime'), ('consumer', 'native-compile'),
                             ('preparationInputs', [{'path': str(self.target_path), 'sha256': '0'*64}])]:
            with self.subTest(field=field):
                request = copy.deepcopy(original); request[field] = value
                path = self.write(self.out/'request.json', request)
                with self.assertRaises(ValueError): adoption.declare_preparation(self.pin(path), self.out/'binding.json', repo=self.root)
                self.assertFalse((self.out/'binding.json').exists())

    def test_duplicate_json_keys_and_unknown_schema_do_not_silently_override(self):
        self.proof_path.write_text('{"kind":"a","kind":"b"}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON'): adoption.verify_proof(self.pin(self.proof_path), repo=self.root)
        self.proof['unexpectedFallback'] = True
        with self.assertRaisesRegex(ValueError, 'Exact adoption proof'): self.verify()


if __name__ == '__main__':
    unittest.main()
