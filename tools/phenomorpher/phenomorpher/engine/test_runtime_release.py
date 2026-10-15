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

    def test_comparisons_must_pin_the_contract_stock_chain_and_old_motion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); plan = self.release(root); report = root/'compare-pfx0.json'; good = report.read_text()
            self.assertEqual([e['name'] for e in json.loads(good)['inputs']['oldChain']], json.loads(good)['oldChain'])
            for change, message in ((lambda d: d['inputs']['manifest'].update(sha256='0'*64), 'base contract and stock chain'),
                                    (lambda d: d['inputs']['stockManifest'].update(sha256='0'*64), 'base contract and stock chain'),
                                    (lambda d: d['inputs']['oldChain'][1].update(sha256='0'*64), 'different old-chain motion'),
                                    (lambda d: d['inputs'].update(oldChain=d['inputs']['oldChain'][:1]), 'whole old chain'),
                                    (lambda d: d.pop('inputs'), 'base contract and stock chain')):
                data = json.loads(good); change(data); report.write_text(json.dumps(data))
                plan['roots'][0]['comparison']['sha256'] = sha(report); (root/'plan.json').write_text(json.dumps(plan))
                with self.subTest(message), self.assertRaisesRegex(ValueError, message):
                    adopt(root, root/'plan.json', root/'out')
            # A carrier edited after the contract cannot be compared at all.
            carrier = root/'srn_body/pcf0.mdl'; carrier.write_bytes(carrier.read_bytes() + b'\0')
            with self.assertRaisesRegex(ValueError, 'differs from the manifest'):
                compare(root, root/plan['baseContract']['path'], root/plan['stock']['path'], 'pfx0',
                        root/'restored/srn_an_xf.mdl', root/'roots/pfx0.mdl')

    def test_retained_published_libraries_must_match_the_compared_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); plan = self.release(root); report = root/'compare-pfx2.json'
            # pfx2 keeps a published parent (as Human Large keeps srn_fa_h0) instead of a staged library.
            path = root/'roots/pfx2.mdl'; path.write_bytes(lib.repoint(path.read_bytes(), 'pcf2'))
            plan['roots'][1]['sha256'] = sha(path); good = json.loads(report.read_text())
            good['repointedRoot']['sha256'] = sha(path)
            for library, message in (({'name': 'pcf2', 'sha256': '0'*64}, 'different library build'),
                                     (None, 'differs from the root supermodel'),
                                     ({'name': 'pcf2', 'sha256': sha(root/'srn_body/pcf2.mdl')}, 'do not reach the installed stock chain: pfx2')):
                report.write_text(json.dumps({**good, 'library': library}))
                plan['roots'][1]['comparison']['sha256'] = sha(report); (root/'plan.json').write_text(json.dumps(plan))
                with self.subTest(message), self.assertRaisesRegex(ValueError, message):
                    adopt(root, root/'plan.json', root/'out')

    def test_intermediate_bases_drop_unpublished_carriers_and_anchor_is_configurable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); plan = self.release(root)
            plan.update(baseKind='intermediate', libraryAnchor='srn_body/pfx0.mdl'); (root/'plan.json').write_text(json.dumps(plan))
            receipt = adopt(root, root/'plan.json', root/'staged')
            self.assertEqual((receipt['summary']['baseKind'], receipt['summary']['retiredCarriers']), ('intermediate', 2))
            retired = json.loads((root/'staged/retired-runtime-resources.json').read_text())
            self.assertEqual([r['reason'] for r in retired], ['texture'])
            paths = [r['path'] for r in json.loads((root/'staged/game-ready-assets.json').read_text())['resources']]
            self.assertEqual(paths[paths.index('srn_body/pfx0.mdl') + 1], 'srn_body/srn_an_xf.mdl')
            for change, message in ((dict(baseKind='published', libraryAnchor='srn_body/pcf0.mdl'), 'not a retained rig row'),
                                    (dict(baseKind='draft', libraryAnchor=None), 'Unknown base kind')):
                plan.update(change); (root/'plan.json').write_text(json.dumps(plan))
                with self.subTest(message), self.assertRaisesRegex(ValueError, message):
                    adopt(root, root/'plan.json', root/'other')

    def test_nested_stock_and_texture_paths_cannot_escape_their_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); plan = self.release(root)
            receipt = root/plan['textures']['path']; data = json.loads(receipt.read_text())
            data['resources'][0]['path'] = '../../outside.plt'; receipt.write_text(json.dumps(data))
            plan['textures']['sha256'] = sha(receipt); (root/'plan.json').write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'escapes its folder'):
                adopt(root, root/'plan.json', root/'a')
            stock = root/plan['stock']['path']; data = json.loads(stock.read_text())
            next(iter(data['models'].values()))['path'] = '../outside.mdl'; stock.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'escapes its folder'):
                lib.stock_files(stock)


if __name__ == '__main__':
    unittest.main()
