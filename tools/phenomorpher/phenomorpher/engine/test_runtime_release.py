"""Runtime adoption regressions: pinned evidence, carrier closure and staged contract."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np

from . import anim_library as lib
from .motion_compare import compare
from .runtime_release import adopt
from . import test_anim_library as fixtures
from .texture_downsample import downsample


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class AdoptionTests(unittest.TestCase):
    def release(self, root):
        manifest, stock = fixtures.LibraryBuildTests().release(root); data = json.loads(manifest.read_text())
        for row in data['resources']:
            row['bytes'] = (root/row['path']).stat().st_size
        chest = b'PLT V1  ' + struct.pack('<IIII', 10, 0, 8, 8) + np.zeros((8, 8, 2), np.uint8).tobytes()
        (root/'srn_body/pfx0_chest001.plt').write_bytes(chest)
        data['resources'].append({'path': 'srn_body/pfx0_chest001.plt', 'sha256': hashlib.sha256(chest).hexdigest(),
                                  'bytes': len(chest), 'role': 'selected-palette'})
        data.update({'schemaVersion': 1, 'kind': 'PhenoMorpher-game-ready-bodies', 'publicationNotes': ['Original global a_* note'],
                     'targets': [{'target': 'x_fit', 'modelPrefix': 'pfx0'}, {'target': 'x_large', 'modelPrefix': 'pfx2'}],
                     'modelDependencies': [{'model': m, 'supermodel': p, 'role': r, 'textureSlots': []} for m, p, r in (
                         ('pfx0', 'pcf0', 'fitted-rig'), ('pcf0', 'null', 'rig-inheritance'),
                         ('pfx2', 'pcf2', 'fitted-rig'), ('pcf2', 'null', 'rig-inheritance'))]})
        manifest.write_text(json.dumps(data)); (root/'retired.json').write_text('[]')
        out = root/'build'; lib.build(root, manifest, stock, 'pfx0', 'pfx2', 'srn_an_xf', out, allowed=['slash'])
        compiled = out/'converted/resources/srn_an_xf.mdl'
        compiled.write_bytes(fixtures.simulated_compile((out/'converted/ascii/srn_an_xf.mdl').read_text()))
        library = root/'restored/srn_an_xf.mdl'; lib.restore(root, out/'restoration-plan.json', compiled, library)
        roots = []
        for target, allowed in (('pfx0', ()), ('pfx2', ('slash',))):
            path = root/'roots'/f'{target}.mdl'; path.parent.mkdir(exist_ok=True)
            path.write_bytes(lib.repoint((root/'srn_body'/f'{target}.mdl').read_bytes(), 'srn_an_xf'))
            report = root/f'compare-{target}.json'
            report.write_text(json.dumps(compare(root, manifest, stock, target, library, path, allowed)))
            roots.append({'resource': target+'.mdl', 'path': f'roots/{target}.mdl', 'sha256': sha(path),
                          'comparison': {'path': report.name, 'sha256': sha(report)}})
        downsample(root, manifest, root/'textures', max_size=4)
        rel = lambda p: {'path': Path(p).relative_to(root).as_posix(), 'sha256': sha(p)}
        plan = {'schemaVersion': 1, 'kind': 'PhenoMorpher-runtime-adoption-plan', 'version': '1.1.0',
                'baseContract': rel(manifest), 'retiredResources': rel(root/'retired.json'), 'stock': rel(stock),
                'textures': rel(root/'textures/downsample-receipt.json'),
                'libraries': [{'resource': 'srn_an_xf.mdl', **rel(library), 'restoration': rel(library.with_suffix('.restoration.json'))}],
                'roots': roots, 'publicationNotes': ['Libraries'], 'runtimeOptimization': {'basedOn': {'version': '1.0.0'}},
                'retiredCarrierReason': 'carrier', 'retiredTextureReason': 'texture', 'assetsIntro': 'All {count} resources.'}
        (root/'plan.json').write_text(json.dumps(plan))
        return plan

    def test_adoption_stages_libraries_roots_textures_and_retires_unreachable_carriers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.release(root)
            receipt = adopt(root, root/'plan.json', root/'staged')
            self.assertEqual({k: receipt['summary'][k] for k in ('libraries', 'repointedRoots', 'downsampledTextures', 'retiredCarriers')},
                             {'libraries': 1, 'repointedRoots': 2, 'downsampledTextures': 1, 'retiredCarriers': 2})
            contract = json.loads((root/'staged/game-ready-assets.json').read_text())
            paths = [r['path'] for r in contract['resources']]
            self.assertNotIn('srn_body/pcf0.mdl', paths); self.assertIn('srn_body/srn_an_xf.mdl', paths)
            row = next(r for r in contract['resources'] if r['path'] == 'srn_body/pfx0.mdl')
            self.assertEqual(row['supermodel'], {'from': 'pcf0', 'to': 'srn_an_xf'})
            self.assertEqual(row['sha256'], sha(root/'staged/files/srn_body/pfx0.mdl'))
            chest = next(r for r in contract['resources'] if r['path'].endswith('.plt'))
            self.assertEqual((chest['size'], chest['downsampledFrom']['size']), ([4, 4], [8, 8]))
            self.assertEqual({d['model']: d['supermodel'] for d in contract['modelDependencies']},
                             {'pfx0': 'srn_an_xf', 'pfx2': 'srn_an_xf', 'srn_an_xf': 'a_fa'})
            self.assertEqual([r['resource'] for r in contract['installedAnimationChain']], ['a_fa.mdl', 'a_ba.mdl'])
            self.assertEqual(contract['publicationNotes'], ['Libraries'])
            removed = json.loads((root/'staged/remove.json').read_text())
            self.assertEqual(sorted(r['path'] for r in removed), ['srn_body/pcf0.mdl', 'srn_body/pcf2.mdl'])
            retired = json.loads((root/'staged/retired-runtime-resources.json').read_text())
            self.assertEqual(sorted(r['reason'] for r in retired), ['carrier', 'carrier', 'texture'])
            self.assertTrue((root/'staged/ASSETS.md').read_text().startswith('# PhenoMorpher runtime file inventory\n\nAll 4 resources.'))
            # The adopted release inventories as root > library > stock with no private carriers.
            for path in (root/'staged/files').rglob('*'):
                if path.is_file():
                    (root/path.relative_to(root/'staged/files')).write_bytes(path.read_bytes())
            for row in removed:
                (root/row['path']).unlink()
            inventory = lib.inventory(root, root/'staged/game-ready-assets.json', root/'stock/stock-models.json')
            self.assertEqual([t['chain'] for t in inventory['targets']],
                             [['pfx0', 'srn_an_xf', 'a_fa', 'a_ba'], ['pfx2', 'srn_an_xf', 'a_fa', 'a_ba']])
            self.assertEqual((inventory['summary']['privateCarriers'], inventory['summary']['animationLibraries']), (0, ['srn_an_xf']))
            self.assertEqual(inventory['targets'][0]['libraries'], ['srn_an_xf'])

    def test_failed_comparisons_and_unrepointed_roots_stop_adoption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); plan = self.release(root)
            report = root/'compare-pfx2.json'; data = json.loads(report.read_text()); data['passed'] = False
            report.write_text(json.dumps(data)); plan['roots'][1]['comparison']['sha256'] = sha(report)
            (root/'plan.json').write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'passing comparison'):
                adopt(root, root/'plan.json', root/'a')
            plan['roots'] = plan['roots'][:1]; (root/'plan.json').write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'still reach private carriers: pfx2'):
                adopt(root, root/'plan.json', root/'b')
            plan['libraries'][0]['sha256'] = '0'*64; (root/'plan.json').write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'Pinned input changed'):
                adopt(root, root/'plan.json', root/'c')


if __name__ == '__main__':
    unittest.main()
