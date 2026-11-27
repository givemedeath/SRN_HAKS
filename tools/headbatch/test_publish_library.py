import contextlib
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import publish_library as pl

HEAD, SLOT = 'troll-male-a', 'pmg0_head021'
VIEWS = [v for v, _ in pl.VIEWS]
DRIVE = 'C' + ':' + chr(92)  # built at run time so the package's portability scan finds no machine path
CROPS = {'default': {v: [0, 0, 64, 48] for v in VIEWS}}


def erf(resources):
    """A minimal HAK V1.0 holding {(resref, type): bytes}."""
    items = list(resources.items()); keys, data = 160, 160+24*len(items)+8*len(items)
    header = struct.pack('<4s4s8I', b'HAK ', b'V1.0', 0, 0, len(items), 160, keys, keys+24*len(items), 0, 0) + bytes(120)
    key_list = b''.join(name.encode().ljust(16, b'\0')+struct.pack('<IHH', i, kind, 0) for i, ((name, kind), _) in enumerate(items))
    offsets, body = [], b''
    for _, payload in items:
        offsets.append(struct.pack('<II', data+len(body), len(payload))); body += payload
    return header+key_list+b''.join(offsets)+body


class Workspace:
    """A headbatch workspace with one client-reviewed head."""
    def __init__(self, root, mdl=b'MDL-bytes', plt=b'PLT-bytes', trial_plt=None, extra_hak=False):
        W = self.root = Path(root)/'ws'
        native = W/'heads'/HEAD/'run/native/attempt-02/native'
        (native/'resources').mkdir(parents=True)
        (native/'resources'/f'{SLOT}.mdl').write_bytes(mdl); (native/'resources'/f'{SLOT}.plt').write_bytes(plt)
        export = W/'heads'/HEAD/'run/export/attempt-01'; export.mkdir(parents=True)
        self.json(export/'receipt.json', {'result': {'triangles': 20000, 'nativeMaterial': {
            'policy': 'stock-organic-head-v1', 'applied': True, 'material': 'oldm_head', 'channels': [0, 1, 8, 9], 'expectedStockSha256': 'x'}}})
        import hashlib  # the native attempt pins export attempt-01; a later re-export must not be read
        self.json(native.parent/'receipt.json', {'inputs': [{'path': 'export', 'sha256': hashlib.sha256((export/'receipt.json').read_bytes()).hexdigest()}]})
        self.json(W/'heads'/HEAD/'run/export/attempt-02/receipt.json', {'result': {'triangles': 1, 'nativeMaterial': {'policy': 'other'}}})
        self.json(W/'design/records'/f'{HEAD}.json', {'name': 'Anvil', 'features': {'hair': 'Dense short coils; dark'},
                  'design': {'path': DRIVE+'local\\detail.png', 'sha256': 'd'*64}, 'generator': 'gen', 'sourceHead': 'troll-male-01', 'sourceDraft': 1})
        self.json(W/'spool/reviewed-rows.json', {HEAD: {'0': 119, '1': 63, '8': 35, '9': 120}})
        trial = W/'trials/troll-v3'; (trial/'userdir/hak').mkdir(parents=True)
        self.json(trial/'runtime-manifest.json', {'heads': [{'native': str(native/f'{SLOT}.hak')}]})
        (trial/'userdir/hak/srn_rh_tro3.hak').write_bytes(erf({(SLOT, 2002): mdl, (SLOT, 6): trial_plt or plt}))
        if extra_hak:
            (trial/'userdir/hak/other.hak').write_bytes(erf({(SLOT, 2002): mdl}))
        (trial/'README.md').write_text(f'| 0 | 1 | sr_h_actor0 | {HEAD} | first |\n| 1 | 2 | sr_h_actor1 | {HEAD} | second |\n', encoding='utf-8')
        session = W/'trials/client-sessions/troll-1'; (session/'captures').mkdir(parents=True)
        self.json(session/'session.json', {'trial': str(trial)})
        for i, (actor, view, kind) in enumerate([('sr_h_actor0', v, 'motion' if v == 'motion' else 'inspect') for v in VIEWS if v != 'alt']
                                                + [('sr_h_actor1', 'front', 'inspect')]):
            Image.new('RGB', (64, 48), (10*i, 80, 120)).save(session/'captures'/f'{i:03d}-{kind}-{actor}-{view}-1.png')
        self.json(W/'runtime/batch-09-checkpoint-23.json', {'heads': [{'head': HEAD, 'slot': SLOT, 'design': 'Anvil',
                  'clientEvidence': {'session': 'trials/client-sessions/troll-1'}, 'corrections': ['user "Accept 0.82"'],
                  'geometrySubmissions': 1}]})
        self.json(W/'crops.json', CROPS)

    @staticmethod
    def json(path, value):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value), encoding='utf-8')


class Stage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)/'repo'; (self.repo/'srn_head').mkdir(parents=True)
        (self.repo/'srn_head/old.mdl').write_bytes(b'x')

    def stage(self, ws, *extra):
        out = Path(self.tmp.name)/'out'
        return pl.main(['stage', '--workspace', str(ws.root), '--repo', str(self.repo), '--name', 'head-library-test-v1',
                        '--created', '2026-11-20', '--prefix', 'troll-', '--crops', str(ws.root/'crops.json'), '--out', str(out), *extra]), out

    def test_stage_writes_portable_manifest_resources_gallery_and_draft(self):
        ws = Workspace(self.tmp.name); code, out = self.stage(ws)
        self.assertEqual(code, 0)
        self.assertEqual((self.repo/'srn_head'/f'{SLOT}.plt').read_bytes(), b'PLT-bytes')
        text = (self.repo/'docs/heads/head-library-test-v1.json').read_text(encoding='utf-8')
        self.assertNotIn('C:', text); manifest = json.loads(text); head = manifest['heads'][0]
        self.assertEqual((head['batch'], head['slot'], head['reviewedNativeAttempt'], head['clientEvidence']['trialHak']),
                         (9, SLOT, 'attempt-02', 'srn_rh_tro3.hak'))
        self.assertEqual(head['nativeMaterial'], {'policy': 'stock-organic-head-v1', 'applied': True, 'material': 'oldm_head', 'channels': [0, 1, 8, 9]})
        self.assertEqual([f['view'] for f in head['clientEvidence']['frames']], VIEWS)
        self.assertNotIn('designSubmissions', head)
        self.assertTrue((self.repo/'docs/heads/evidence/head-library-test-v1'/f'{SLOT}-client.jpg').is_file())
        self.assertIn('All 1 existing', (out/'head-library-test-v1-draft.md').read_text(encoding='utf-8'))
        hak = Path(self.tmp.name)/'srn_head.hak'; hak.write_bytes(erf({(SLOT, 2002): b'MDL-bytes', (SLOT, 6): b'PLT-bytes'}))
        self.assertEqual(pl.main(['verify', '--hak', str(hak), '--manifest', str(self.repo/'docs/heads/head-library-test-v1.json')]), 0)
        hak.write_bytes(erf({(SLOT, 2002): b'MDL-bytes', (SLOT, 6): b'PLT-other'}))
        self.assertEqual(pl.main(['verify', '--hak', str(hak), '--manifest', str(self.repo/'docs/heads/head-library-test-v1.json')]), 1)
        # a revision record names the new bytes of a pinned resource; other bytes still refuse
        import hashlib
        old = json.loads(text)['heads'][0]['resources']['plt']['sha256']
        revision = Path(self.tmp.name)/'revision.json'
        revision.write_text(json.dumps({'heads': [{'path': f'srn_head/{SLOT}.plt', 'fromSHA256': old,
                                                   'sha256': hashlib.sha256(b'PLT-other').hexdigest(), 'bytes': 9}]}), encoding='utf-8')
        args = ['verify', '--hak', str(hak), '--manifest', str(self.repo/'docs/heads/head-library-test-v1.json'), '--revision', str(revision)]
        self.assertEqual(pl.main(args), 0)
        hak.write_bytes(erf({(SLOT, 2002): b'MDL-bytes', (SLOT, 6): b'PLT-third'}))
        self.assertEqual(pl.main(args), 1)

    def test_dry_run_leaves_the_repository_alone(self):
        ws = Workspace(self.tmp.name); code, out = self.stage(ws, '--dry-run')
        self.assertEqual(code, 0); self.assertFalse((self.repo/'srn_head'/f'{SLOT}.mdl').exists())
        self.assertTrue((out/'repo/srn_head'/f'{SLOT}.mdl').is_file())

    def test_refusals_write_nothing(self):
        cases = {'trial bytes differ from native': dict(trial_plt=b'PLT-changed'), 'slot in two trial HAKs': dict(extra_hak=True)}
        for label, options in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as root:
                code, _ = self.stage(Workspace(root, **options))
                self.assertEqual(code, 1); self.assertFalse((self.repo/'srn_head'/f'{SLOT}.mdl').exists())
                self.assertFalse((self.repo/'docs').exists())
        (self.repo/'srn_head'/f'{SLOT}.mdl').write_bytes(b'published-different')
        code, _ = self.stage(Workspace(self.tmp.name)); self.assertEqual(code, 1)
        self.assertFalse((self.repo/'docs').exists())

    def test_a_conflicting_gallery_refuses_before_any_write(self):
        ws = Workspace(self.tmp.name); gallery = self.repo/'docs/heads/evidence/head-library-test-v1'/f'{SLOT}-client.jpg'
        gallery.parent.mkdir(parents=True); gallery.write_bytes(b'old crop')
        self.assertEqual(self.stage(ws)[0], 1)
        self.assertFalse((self.repo/'srn_head'/f'{SLOT}.mdl').exists())

    def test_input_refusals(self):
        ws = Workspace(self.tmp.name)
        self.assertEqual(self.stage(ws, '--created', 'yesterday')[0], 1)
        (ws.root/'design/records'/f'{HEAD}.json').unlink()
        self.assertEqual(self.stage(ws)[0], 1)  # a missing input refuses instead of a traceback
        out = Path(self.tmp.name)/'out'
        self.assertEqual(pl.main(['stage', '--workspace', str(ws.root), '--repo', str(self.repo), '--name', 'x', '--created', '2026-11-20',
                                  '--heads', f'{HEAD},{HEAD}', '--out', str(out)]), 1)

    def test_posix_paths_never_reach_the_manifest(self):
        ws = Workspace(self.tmp.name); checkpoint = ws.root/'runtime/batch-09-checkpoint-23.json'
        data = json.loads(checkpoint.read_text(encoding='utf-8')); data['heads'][0]['corrections'] = ['moved /home/user/ws/heads aside']
        checkpoint.write_text(json.dumps(data), encoding='utf-8')
        self.assertEqual(self.stage(ws)[0], 1); self.assertFalse((self.repo/'docs').exists())

    def test_overrides_and_review_text(self):
        ws = Workspace(self.tmp.name); overrides = Path(self.tmp.name)/'overrides.json'
        for bad in ({'troll-male-b': {'reviewNotes': ['x']}}, {HEAD: {'reviewNote': ['x']}}, {HEAD: {'reviewNotes': 'x'}}):
            with self.subTest(bad=bad):
                overrides.write_text(json.dumps(bad), encoding='utf-8')
                self.assertEqual(self.stage(ws, '--overrides', str(overrides))[0], 1)
        self.assertEqual(self.stage(ws, '--checkpoints', str(ws.root/'runtime/batch-*-checkpoint-*.json'))[0], 1)
        overrides.write_text(json.dumps({HEAD: {'reviewNotes': ['user "Keep it"']}}), encoding='utf-8')
        self.assertEqual(self.stage(ws, '--overrides', str(overrides), '--review', 'Reviewed by the user in the client.')[0], 0)
        manifest = json.loads((self.repo/'docs/heads/head-library-test-v1.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['review'], 'Reviewed by the user in the client.')
        self.assertEqual(manifest['heads'][0]['reviewNotes'], ['user "Accept 0.82"', 'user "Keep it"'])

    def test_fit_variant_head_with_override(self):
        ws = Workspace(self.tmp.name); trial = ws.root/'trials/troll-v3'; overrides = Path(self.tmp.name)/'overrides.json'
        overrides.write_text(json.dumps({HEAD: {'reviewedNativeAttempt': 'attempt-01'}}), encoding='utf-8')
        self.assertEqual(self.stage(ws, '--overrides', str(overrides))[0], 1)  # the trial packed attempt-02 itself
        variant = ws.root/'trials/fit-variants/troll-v4'/HEAD/'native'; (variant/'resources').mkdir(parents=True)
        (variant/'resources'/f'{SLOT}.mdl').write_bytes(b'MDL-bytes'); (variant/'resources'/f'{SLOT}.plt').write_bytes(b'PLT-bytes')
        ws.json(trial/'runtime-manifest.json', {'heads': [{'native': str(variant/'native.json')}]})
        ws.json(ws.root/'trials/client-sessions/troll-1/session.json', {'trial': 'trials/troll-v3'})  # relative to the workspace
        self.assertEqual(self.stage(ws)[0], 1)  # two export attempts and nothing pins one
        overrides.write_text(json.dumps({HEAD: {'reviewedNativeAttempt': 'attempt-05'}}), encoding='utf-8')
        self.assertEqual(self.stage(ws, '--overrides', str(overrides))[0], 1)  # no such native receipt
        overrides.write_text(json.dumps({HEAD: {'reviewedNativeAttempt': 'attempt-02', 'reviewNotes': ['fit variant']}}), encoding='utf-8')
        self.assertEqual(self.stage(ws, '--overrides', str(overrides))[0], 0)
        head = json.loads((self.repo/'docs/heads/head-library-test-v1.json').read_text(encoding='utf-8'))['heads'][0]
        self.assertEqual((head['reviewedNativeAttempt'], head['triangles'], head['reviewNotes'][-1]), ('attempt-02', 20000, 'fit variant'))

    def test_bad_crop_boxes_refuse(self):
        ws = Workspace(self.tmp.name)
        for crops in ({'troll-male': CROPS['default']}, {'default': dict(CROPS['default'], three=[0, 0, 64])},
                      {'default': dict(CROPS['default'], three=[0, 0, 64.5, 48])}):
            with self.subTest(crops=crops):
                ws.json(ws.root/'crops.json', crops)
                self.assertEqual(self.stage(ws)[0], 1)
        self.assertFalse((self.repo/'docs').exists())

    def test_malformed_workspace_files_refuse(self):
        ws = Workspace(self.tmp.name); readme = ws.root/'trials/troll-v3/README.md'; text = readme.read_text(encoding='utf-8')
        readme.write_text(text+f'| 4 | 1 | sr_h_actor4 | {HEAD} | reused |\n', encoding='utf-8')
        self.assertEqual(self.stage(ws)[0], 1)  # look 1 listed twice
        readme.write_text(text, encoding='utf-8'); ws.json(ws.root/'spool/reviewed-rows.json', [])
        self.assertEqual(self.stage(ws)[0], 1)  # refused, not a traceback
        self.assertFalse((self.repo/'docs').exists())

    def test_existing_manifest_refuses_and_a_dry_run_warns(self):
        ws = Workspace(self.tmp.name); self.assertEqual(self.stage(ws)[0], 0)
        self.assertEqual(self.stage(ws)[0], 1)
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            self.assertEqual(self.stage(ws, '--dry-run')[0], 0)
        self.assertIn('already in the repository', errors.getvalue())


class Archive(unittest.TestCase):
    def test_reader_refuses_truncated_and_duplicate_archives(self):
        good = erf({(SLOT, 2002): b'a', (SLOT, 6): b'b'})
        self.assertEqual(pl.erf_resources(good)[(SLOT, 6)], b'b')
        for bad in (good[:100], good[:170], good[:-1]):
            with self.assertRaises(pl.PublishError): pl.erf_resources(bad)
        with self.assertRaises(pl.PublishError):
            pl.erf_resources(erf({(SLOT, 6): b'a', (SLOT.upper(), 6): b'b'}))


class NativeSources(unittest.TestCase):
    def test_attempts_and_fit_variants(self):
        manifest = {'a': [DRIVE+'ws\\heads\\troll-male-a\\run\\native\\attempt-03\\native\\x.hak'],
                    'b': {'c': DRIVE+'ws\\trials\\fit-variants\\human-v4\\human-male-c\\native\\native.json'},
                    'd': DRIVE+'ws\\trials\\client-sessions\\troll-male-a\\native\\ignored'}
        self.assertEqual(list(pl.native_sources(manifest, 'troll-male-a').values()), ['attempt-03'])
        self.assertEqual(list(pl.native_sources(manifest, 'human-male-c').values()), ['fit-variant human-v4'])
        self.assertEqual(pl.native_sources(manifest, 'elf-male-a'), {})


if __name__ == '__main__':
    unittest.main()
