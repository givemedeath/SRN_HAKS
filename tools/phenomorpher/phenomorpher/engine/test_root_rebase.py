"""Root rebase regressions on synthetic native rigs and libraries."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from . import anim_library as lib
from .native_motion import sample, sample_times
from .root_rebase import rebase
from .test_anim_library import clip, native, rotation
from .. import cli
from ..inputs import consumed

OFFSET = [0.0, 0.0, -0.0477]


def geometry(root, offset=OFFSET, orientation=(0.0, 0.0, 0.0, 1.0)):
    """Dwarf-like rig: an offset root over rootdummy (with a deeper node) and the two conjure dummies."""
    top = {8: ([0.0], [list(offset)]), 20: ([0.0], [list(orientation)])}
    return [(root, '', top), ('rootdummy', root, {8: ([0.0], [[-0.0024, 0.0146, 0.8618]]), 20: ([0.0], [[0.0, 0.0, 0.0, 1.0]])}),
            ('torso_g', 'rootdummy', {8: ([0.0], [[0.0, 0.0, 0.25]]), 20: ([0.0], [rotation(10)])}),
            ('handconjure', root, {8: ([0.0], [[0.0, 0.1987, 1.0042]])}),
            ('headconjure', root, {8: ([0.0], [[0.0, -0.0199, 1.6867]])})]


def library_clips(root):
    swing = clip('swing', root, angle=-20)
    swing['nodes'] += [('torso_g', 'rootdummy', {20: ([0.0, 0.5, 1.0], [rotation(0), rotation(40), rotation(5)])}),
                       ('headconjure', root, {8: ([0.0, 1.0], [[0.0, -0.02, 1.68], [0.01, -0.02, 1.7]])})]
    pause = clip('pause1', root, angle=15); del pause['nodes'][1][2][8]
    return [clip('walk', root, angle=30), swing, pause]


def release(root, **models):
    """Female Fit/Large rigs over an offset library, plus a male rig at the origin straight on a_ba.
    models: {name: (parent, nodes, clips)} overrides."""
    specs = {'pfx0': ('srn_an_xf', geometry('pfx0'), []), 'pfx2': ('srn_an_xf', geometry('pfx2'), []),
             'srn_an_xf': ('a_fa', geometry('srn_an_xf'), library_clips('srn_an_xf')),
             'pmx0': ('a_ba', geometry('pmx0', [0.0, 0.0, 0.0]), []), **models}
    roles = {'srn_an_xf': 'animation-library'}; (root/'srn_body').mkdir(); resources = []
    for name, (parent, nodes, clips) in specs.items():
        blob = native(name, parent, nodes, clips); (root/'srn_body'/(name + '.mdl')).write_bytes(blob)
        row = {'path': f'srn_body/{name}.mdl', 'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob),
               'role': roles.get(name, 'rig-inheritance' if name.startswith('pc') else 'fitted-rig')}
        if row['role'] == 'animation-library':
            row['restorationSHA256'] = '0'*64
        resources.append(row)
    manifest = {'version': '1.0.0', 'resources': resources, 'modelDependencies': [],
                'installedGameDependencies': ['a_fa.mdl', 'a_ba.mdl'],
                'targets': [{'target': t, 'modelPrefix': p} for t, p in
                            (('x_female_fit', 'pfx0'), ('x_female_large', 'pfx2'), ('x_male_fit', 'pmx0'))]}
    (root/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    return root/'manifest.json'


def load(path):
    blob = Path(path).read_bytes(); return blob, lib.NativeModel(blob).decode()


class RootRebaseTests(unittest.TestCase):
    def test_offset_moves_into_children_and_library_keys_without_moving_the_world(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest = release(root); out = root/'out'
            receipt = rebase(root, manifest, out, '1.1.0')
            self.assertEqual(set(receipt['models']), {'pfx0', 'pfx2', 'srn_an_xf'})
            self.assertEqual(set(receipt['equivalence']), {'pfx0', 'pfx2'})
            self.assertEqual(receipt['equivalence']['pfx0']['clips'], 3)
            self.assertTrue(receipt['runtimeRules']['passed']); self.assertFalse(receipt['assetApprovalCreated'])
            self.assertEqual(receipt['models']['srn_an_xf']['patchedClipKeyControllers'], 3)  # walk, swing rootdummy + headconjure
            self.assertFalse((out/'files/srn_body/pmx0.mdl').exists())
            offset = np.float32(OFFSET)
            for name in ('pfx0', 'pfx2', 'srn_an_xf'):
                old, before = load(root/'srn_body'/(name + '.mdl')); new, after = load(out/'files/srn_body'/(name + '.mdl'))
                self.assertEqual(after['nodes'][name]['controls'][8]['values'].tolist(), [[0.0, 0.0, 0.0]])
                mask = np.zeros(len(old), bool); spans = [before['nodes'][name]['controls'][8]['dataRange']]
                for child in ('rootdummy', 'handconjure', 'headconjure'):
                    spans.append(before['nodes'][child]['controls'][8]['dataRange'])
                    expected = (np.float32(before['nodes'][child]['controls'][8]['values']) + offset).astype(np.float32)
                    self.assertTrue(np.array_equal(np.float32(after['nodes'][child]['controls'][8]['values']), expected))
                self.assertTrue(np.array_equal(after['nodes']['torso_g']['controls'][8]['values'], before['nodes']['torso_g']['controls'][8]['values']))
                for clip_name, row in before['clips'].items():
                    for child in ('rootdummy', 'headconjure'):
                        control = row['nodes'].get(child, {}).get('controls', {}).get(8)
                        if control:
                            spans.append(control['dataRange']); keys = after['clips'][clip_name]['nodes'][child]['controls'][8]['values']
                            self.assertTrue(np.array_equal(np.float32(keys), (np.float32(control['values']) + offset).astype(np.float32)))
                for a, b in spans:
                    mask[a:b] = True
                diff = np.frombuffer(old, np.uint8) != np.frombuffer(new, np.uint8)
                self.assertFalse((diff & ~mask).any()); self.assertEqual(int(mask.sum()), receipt['models'][name]['patchedBytes'])
            # World frames of every node below the root, at bind and through each library clip.
            _, rig_before = load(root/'srn_body/pfx2.mdl'); _, rig_after = load(out/'files/srn_body/pfx2.mdl')
            _, lib_before = load(root/'srn_body/srn_an_xf.mdl'); _, lib_after = load(out/'files/srn_body/srn_an_xf.mdl')
            for name, c in lib_before['clips'].items():
                first = {('pfx2' if n == 'srn_an_xf' else n): r for n, r in c['nodes'].items()}
                second = {('pfx2' if n == 'srn_an_xf' else n): r for n, r in lib_after['clips'][name]['nodes'].items()}
                for time in [0.0] + sample_times(c):
                    wa, wb = sample(rig_before['nodes'], first, time), sample(rig_after['nodes'], second, time)
                    for node in ('rootdummy', 'torso_g', 'handconjure', 'headconjure'):
                        self.assertLess(np.abs(wa[node] - wb[node]).max(), 1e-6)
            contract = json.loads((out/'game-ready-assets.json').read_text(encoding='utf-8'))
            rows = {Path(r['path']).stem: r for r in contract['resources']}
            self.assertEqual(contract['version'], '1.1.0')
            self.assertEqual(rows['pfx0']['sha256'], hashlib.sha256((out/'files/srn_body/pfx0.mdl').read_bytes()).hexdigest())
            self.assertEqual(rows['srn_an_xf']['rootRebase']['fromSHA256'], receipt['models']['srn_an_xf']['fromSHA256'])
            self.assertAlmostEqual(rows['pfx0']['rootRebase']['offset'][2], -0.0477, places=7)
            self.assertNotIn('rootRebase', rows['pmx0'])
            stored = json.loads((out/'root-rebase-receipt.json').read_text(encoding='utf-8'))
            self.assertEqual((stored['kind'], stored['schemaVersion']), ('PhenoMorpher-root-rebase', 1))
            self.assertLessEqual(stored['summary']['worstClipMetres'], 1e-6)
            self.assertIn(b'\n', (out/'root-rebase-receipt.json').read_bytes()); self.assertNotIn(b'\r\n', (out/'root-rebase-receipt.json').read_bytes())
            with self.assertRaisesRegex(ValueError, 'Fresh output'):
                rebase(root, manifest, out, '1.1.0')
            declared = consumed(['rebase-roots', '--root', str(root), '--manifest', str(manifest), '--output', str(root/'o'),
                                 '--version', '1.1.0'])
            self.assertEqual(declared, {manifest.resolve()} | {(root/'srn_body'/(n + '.mdl')).resolve()
                                                               for n in ('pfx0', 'pfx2', 'srn_an_xf', 'pmx0')})
            # The subcommand's --version is the staged contract version, not the program version.
            argv = ['rebase-roots', '--root', str(root), '--manifest', str(manifest), '--output', str(root/'o'), '--version', '1.1.0']
            with patch.dict('os.environ', {'SRN_VERIFIED_INPUTS': ''}), patch.object(cli, '_PINS', None):
                with self.assertRaisesRegex(ValueError, 'run.py'):
                    cli.main(argv)
            self.assertFalse((root/'o').exists())

    def refuses(self, pattern, **models):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest = release(root, **models)
            with self.assertRaisesRegex(ValueError, pattern):
                rebase(root, manifest, root/'out', '1.1.0')
            self.assertFalse((root/'out').exists())

    def test_refusals(self):
        self.refuses('Root orientation is not identity: pfx0', pfx0=('srn_an_xf', geometry('pfx0', orientation=rotation(5)), []))
        keyed = library_clips('srn_an_xf'); keyed[0]['nodes'][0] = ('srn_an_xf', '', {8: ([0.0], [OFFSET])})
        self.refuses('Clip keys the model root: srn_an_xf walk', srn_an_xf=('a_fa', geometry('srn_an_xf'), keyed))
        self.refuses('Root offsets disagree: pfx2 and srn_an_xf', pfx2=('srn_an_xf', geometry('pfx2', [0.0, 0.0, -0.05]), []))
        self.refuses('Root offsets disagree: pmx0 and srn_an_xf', pmx0=('srn_an_xf', geometry('pmx0', [0.0, 0.0, 0.0]), []))
        bare = geometry('pfx0'); bare[3] = ('handconjure', 'pfx0', {})
        self.refuses('Root child has no static position: pfx0 handconjure', pfx0=('srn_an_xf', bare, []))
        moving = geometry('pfx0'); moving[0] = ('pfx0', '', {8: ([0.0, 1.0], [OFFSET, OFFSET])})
        self.refuses('keyed more than once: pfx0', pfx0=('srn_an_xf', moving, []))
        scaled = geometry('pfx0'); scaled[0][2][36] = ([0.0], [[1.0]])
        self.refuses('scale controller: pfx0', pfx0=('srn_an_xf', scaled, []))
        # A carrier between the rig and the library keeps clips relative to the old root.
        self.refuses('Carrier pcx0 in the chain of pfx0 keys the root', pfx0=('pcx0', geometry('pfx0'), []),
                     pcx0=('srn_an_xf', geometry('pcx0', [0.0, 0.0, 0.0]), [clip('walk', 'pcx0')]))
        self.refuses('without a library: pfx0', pfx0=('a_fa', geometry('pfx0'), []), pfx2=('a_fa', geometry('pfx2'), []),
                     srn_an_xf=('a_fa', geometry('srn_an_xf', [0.0, 0.0, 0.0]), library_clips('srn_an_xf')))

    def test_tampered_input_and_nothing_to_rebase_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest = release(root, pfx0=('srn_an_xf', geometry('pfx0', [0.0, 0.0, 0.0]), []),
                                                 pfx2=('srn_an_xf', geometry('pfx2', [0.0, 0.0, 0.0]), []),
                                                 srn_an_xf=('a_fa', geometry('srn_an_xf', [0.0, 0.0, 0.0]), library_clips('srn_an_xf')))
            with self.assertRaisesRegex(ValueError, 'No published model root carries an offset'):
                rebase(root, manifest, root/'out', '1.1.0')
            (root/'srn_body/pfx0.mdl').write_bytes(b'\0' + (root/'srn_body/pfx0.mdl').read_bytes()[1:] + b'\0')
            with self.assertRaisesRegex(ValueError, 'differs from the contract'):
                rebase(root, manifest, root/'out', '1.1.0')


if __name__ == '__main__':
    unittest.main()
