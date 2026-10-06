"""Regression coverage for review evidence, attachment frames, and stock fixtures."""
import ast
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np

import derive_rig
from retarget import nodes, transforms
from derived_equipment import audit_hand_dummies
from equipment_frames import verify_attachment_frames
from fixture_appearance import patch_appearance
import run_derived_dwarf_client_test as runner
import build_derived_elf_fixture as elf
import build_derived_orc_fixture as orc

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def skeleton(grip_offset=0, hook_offset=0, hook_angle=0):
    lines = ['beginmodelgeom test', 'node dummy root', ' parent null', 'endnode']
    for hook, sign in [('lhand', 1), ('rhand', -1)]:
        lines += [f'node dummy {hook}_g', ' parent root', f' position {sign + grip_offset} 0 0', ' orientation 0 0 1 0', 'endnode',
                  f'node dummy {hook}', f' parent {hook}_g', f' position {0.2 + hook_offset} 0 0', f' orientation 0 0 1 {hook_angle}', 'endnode']
    return '\n'.join([*lines, 'endmodelgeom test'])


class EquipmentFramesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source, self.rig = self.root / 'stock.mdl', self.root / 'pmd0.mdl'
        self.source.write_text(skeleton())
        self.rig.write_text(skeleton(grip_offset=0.5))
        self.target = {'id': 'test', 'identity': {'prefix': 'pmd0'}, 'rig': {'frames': {'working': {k: v.tolist() for k, v in transforms(nodes(skeleton(grip_offset=0.5))).items()}}}}
        for hand in ['handl', 'handr']:
            (self.root / f'pmd0_{hand}001.mdl').write_text('hand mesh')
        self.pin()

    def pin(self):
        (self.root / 'rig-receipt.json').write_text(json.dumps({'kind': 'derived-rig-receipt', 'status': 'verified-exact', 'targetId': 'test', 'supermodel': 'pmd0',
            'targetRootMdl': str(self.rig), 'targetRootMdlSha256': sha(self.rig), 'sourceRootMdl': str(self.source), 'sourceRootMdlSha256': sha(self.source)}))

    def test_approved_widening_preserves_stock_local_weapon_seating(self):
        result = audit_hand_dummies(self.root, self.rig, target_config=self.target)
        self.assertTrue(all(meta['attachmentFramesValid'] for meta in result.values()))
        self.assertEqual(len(result['handl']['inputHashes']), 3)

    def test_re_pinned_hook_translation_rotation_and_grip_drift_rejected(self):
        for kwargs in [{'grip_offset': 0.5, 'hook_offset': 10}, {'grip_offset': 0.5, 'hook_angle': np.pi / 2}, {'grip_offset': 10}]:
            with self.subTest(kwargs=kwargs):
                self.rig.write_text(skeleton(**kwargs))
                self.pin()
                with self.assertRaisesRegex(ValueError, 'attachment transform mismatch'):
                    verify_attachment_frames(self.rig, self.target)

    def test_source_drift_and_wrong_target_rejected(self):
        self.source.write_text(skeleton(hook_offset=1))
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            verify_attachment_frames(self.rig, self.target)
        self.pin()
        with self.assertRaisesRegex(ValueError, 'target mismatch'):
            verify_attachment_frames(self.rig, {**self.target, 'id': 'other'})

    def test_incomplete_hierarchy_rejected_even_if_re_pinned(self):
        self.rig.write_text(skeleton(grip_offset=0.5).replace(' parent root', ' parent missing'))
        self.pin()
        with self.assertRaisesRegex(ValueError, 'Missing parent'):
            verify_attachment_frames(self.rig, self.target)


class ClientEvidenceTests(unittest.TestCase):
    def test_bare_and_equipment_runs_with_reused_pid_keep_every_evidence_pin(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            stage = root / 'output/phenotypes/derived-dwarf-male-v1/test-stage'
            (stage / 'test-module').mkdir(parents=True)
            receipt = stage / 'test-module/receipt.json'
            logs = stage / 'userdir/logs'
            logs.mkdir(parents=True)
            client = root / 'nwmain.exe'
            client.write_bytes(b'fake')
            phases = ['front-idle', 'front-raised', 'side-idle', 'rear-idle', 'rear-raised', 'rear-crouch', 'complete-front-idle']
            bare_log = '\n'.join('PHENOTYPE_TORSO_PHASE phase=' + phase for phase in phases) + '\nPHENOTYPE_TORSO_SEQUENCE_COMPLETE\nFull raw client notice\n'
            def preflight(stage, client, output, **kwargs):
                result = {'pass': True, 'userDirectory': str(stage / 'userdir'), 'client': str(client), 'hakSha256': 'hak', 'moduleSha256': 'mod', 'clientSha256': sha(client)}
                output.write_text(json.dumps(result))
                return result
            def launch(*args, **kwargs):
                equipped = json.loads(receipt.read_text()).get('cameraEquipmentTarget', False)
                (logs / 'nwclientLog1.txt').write_text('PHENOTYPE_CAMERA_SET\nPHENOTYPE_EQUIPMENT_WORN\n' if equipped else bare_log)
                (logs / 'nwengineLog.txt').write_text('complete engine output\n' + ('equipment' if equipped else 'bare'))
                return SimpleNamespace(pid=1234, poll=lambda: None, terminate=lambda: None, wait=lambda **kw: None)
            with patch.object(runner, 'REPO', root), patch.object(runner, 'check_no_nwmain'), patch.object(runner, 'run_preflight', side_effect=preflight), patch.object(runner.subprocess, 'Popen', side_effect=launch), patch.object(runner, 'get_process_metrics', return_value=None), patch.object(runner.time, 'time', side_effect=[0, 1, 143, 0, 1, 26]):
                receipt.write_text('{}')
                bare = runner.run_client_test(client=client)
                receipt.write_text('{"cameraEquipmentTarget": true}')
                equipped = runner.run_client_test(client=client)
            self.assertNotEqual(bare['launch'], equipped['launch'])
            for evidence in [bare, equipped]:
                self.assertTrue(evidence['cleanLogsVerified'])
                for field in ['fixtureReceipt', 'launch', 'filteredPhenotypeLog', 'runtimeMetricsFile']:
                    hash_field = 'runtimeMetricsSha256' if field == 'runtimeMetricsFile' else field + 'Sha256'
                    self.assertEqual(sha(evidence[field]), evidence[hash_field])
                for path, expected in evidence['sourceLogs'].items():
                    self.assertEqual(sha(path), expected)
                launch_info = json.loads(Path(evidence['launch']).read_text())
                self.assertTrue(Path(launch_info['preflight']).is_file())
            self.assertIn('Full raw client notice', next(Path(p).read_text() for p in bare['sourceLogs'] if p.endswith('nwclientLog1.txt')))
            self.assertEqual(Path(bare['fixtureReceipt']).read_text(), '{}')


COLUMNS = 'LABEL HEIGHT SIZECATEGORY WEAPONSCALE WING_TAIL_SCALE HELMET_SCALE_M HELMET_SCALE_F WALKDIST RUNDIST CREPERSPACE PREFATCKDIST'
TABLE = '2DA V2.0\n\n' + COLUMNS + '\n0 Human 1.9 3 1 1 .9 .82 1 1.94 .4 1.3\n1 Elf 1.7 3 1 1 .9 .82 1 1.94 .4 1.3\n5 Orc 1.9 3 1 1 .9 .82 1 1.94 .4 1.3\n'


class AppearanceTests(unittest.TestCase):
    def test_every_source_is_patched_and_other_rows_unchanged(self):
        for race, builder in [('elf', elf), ('orc', orc)]:
            target_path = HERE / f'configurations/derived/target-{race}-male-fit.json'
            target = json.loads(target_path.read_text())
            for source in ['explicit', 'game', 'durable']:
                with self.subTest(race=race, source=source), tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    (root / target_path.relative_to(HERE.parents[1])).parent.mkdir(parents=True)
                    (root / target_path.relative_to(HERE.parents[1])).write_text(target_path.read_text())
                    durable = root / 'tools/phenotypes/references/fixtures/appearance.2da'
                    durable.parent.mkdir(parents=True)
                    durable.write_text(TABLE)
                    explicit = root / 'explicit.2da'
                    explicit.write_text(TABLE)
                    with patch.object(builder, 'REPO', root), patch.object(builder, 'resolve_game_root', return_value=root), patch.object(builder, 'run_tool', return_value=TABLE.encode() if source == 'game' else b''):
                        digest = builder.stage_fixture_resources(root / 'stage', root / 'compiler', appearance_path=explicit if source == 'explicit' else None)
                    output = root / 'stage/fixture-resources/appearance.2da'
                    self.assertEqual(sha(output), digest)
                    row = str(target['identity']['appearanceRow'])
                    for line in TABLE.splitlines():
                        if line.split() and line.split()[0].isdigit() and line.split()[0] != row:
                            self.assertIn(line, output.read_text())
                    values = next(line.split()[1:] for line in output.read_text().splitlines() if line.startswith(row + ' '))
                    self.assertAlmostEqual(float(values[COLUMNS.split().index('HEIGHT')]), target['heightMeters'])
                    self.assertAlmostEqual(float(values[COLUMNS.split().index('WEAPONSCALE')]), target['rig']['runtimeScale'])

    def test_missing_row_columns_or_truncated_row_rejected(self):
        target = json.loads((HERE / 'configurations/derived/target-elf-male-fit.json').read_text())
        for text in [TABLE.replace('1 Elf', '7 Elf'), TABLE.replace('WEAPONSCALE', 'BROKEN'), TABLE.replace('1 Elf 1.7 3 1 1 .9 .82 1 1.94 .4 1.3', '1 Elf 1.7')]:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'appearance.2da'
                path.write_text(text)
                with self.assertRaises(ValueError):
                    patch_appearance(path, target)


class NativeReviewRootsTests(unittest.TestCase):
    def test_review_consumers_decode_binary_roots_and_keep_frozen_bytes(self):
        scripts = ['render_derived_dwarf_review', 'render_derived_elf_review', 'render_derived_orc_review', 'render_derived_troll_review', 'render_human_baseline_review', 'render_assembly_comparison', 'measure_body_assembly']
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'stock').mkdir()
            for name in ['pmh0', 'pmd0', 'rig']:
                (root / 'stock' / (name + '.mdl')).write_bytes(b'\0\0\0\0\x81\x8d native root')
            original = {p: sha(p) for p in (root / 'stock').iterdir()}
            def decompile(command, **kwargs):
                Path(command[-1]).write_text(skeleton(), encoding='cp1252')
            for script in scripts:
                with self.subTest(script=script):
                    tree = ast.parse((HERE / (script + '.py')).read_text())
                    # Exercise the consumer's actual root loading statements independently
                    # of Blender rendering and the geometry measurement workload.
                    loads = [node for node in ast.walk(tree) if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id.endswith('_text') for t in node.targets)]
                    namespace = {'args': SimpleNamespace(masters_dir=root, rig_file=root / 'stock/rig.mdl'), 'master_dir': root, 'read_mdl_text': derive_rig.read_mdl_text}
                    with patch.object(derive_rig, 'resolve_mdlcomp', return_value=Path('fake-mdlcomp')), patch.object(derive_rig.subprocess, 'run', side_effect=decompile):
                        exec(compile(ast.Module(body=loads, type_ignores=[]), script, 'exec'), namespace)
                    texts = [v for k, v in namespace.items() if k.endswith('_text') and isinstance(v, str)]
                    self.assertTrue(texts)
                    for text in texts:
                        self.assertIn('lhand_g', transforms(nodes(text)))
            self.assertEqual(original, {p: sha(p) for p in original})


if __name__ == '__main__':
    unittest.main()
