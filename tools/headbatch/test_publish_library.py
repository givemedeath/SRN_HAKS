import json
import struct
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import publish_library as pl

HEAD, SLOT = 'troll-male-a', 'pmg0_head021'
VIEWS = [v for v, _ in pl.VIEWS]
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
        self.json(W/'design/records'/f'{HEAD}.json', {'name': 'Anvil', 'features': {'hair': 'Dense short coils; dark'},
                  'design': {'path': 'C:\\local\\detail.png', 'sha256': 'd'*64}, 'generator': 'gen', 'sourceHead': 'troll-male-01', 'sourceDraft': 1})
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

    def test_existing_manifest_refuses(self):
        ws = Workspace(self.tmp.name); self.assertEqual(self.stage(ws)[0], 0)
        self.assertEqual(self.stage(ws)[0], 1)


class NativeSources(unittest.TestCase):
    def test_attempts_and_fit_variants(self):
        manifest = {'a': ['S:\\ws\\heads\\troll-male-a\\run\\native\\attempt-03\\native\\x.hak'],
                    'b': {'c': 'S:\\ws\\trials\\fit-variants\\human-v4\\human-male-c\\native\\native.json'},
                    'd': 'S:\\ws\\trials\\client-sessions\\troll-male-a\\native\\ignored'}
        self.assertEqual(list(pl.native_sources(manifest, 'troll-male-a').values()), ['attempt-03'])
        self.assertEqual(list(pl.native_sources(manifest, 'human-male-c').values()), ['fit-variant human-v4'])
        self.assertEqual(pl.native_sources(manifest, 'elf-male-a'), {})


if __name__ == '__main__':
    unittest.main()
