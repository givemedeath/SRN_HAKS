"""Animation-library inventory regressions on synthetic native/ASCII models."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np

from . import anim_library as lib
from ..inputs import consumed


def native(name, parent, nodes, clips=(), scale=1.0):
    """Minimal native character writer: nodes are (name, parent, {kind: (times, rows)})."""
    data = bytearray(0xe8)
    def allocate(payload):
        data.extend(b'\0'*(-len(data) % 4)); at = len(data); data.extend(payload); return at
    def text(at, width, value):
        data[at:at+width] = value.encode().ljust(width, b'\0')
    def array(at, payload, width):
        start = allocate(payload) if payload else 0
        struct.pack_into('<III', data, at, start, len(payload)//width, len(payload)//width)
    def tree(specs):
        offsets = {n: allocate(bytes(0x70)) for n, _, _ in specs}
        for n, p, controls in specs:
            at = offsets[n]; text(at+0x20, 32, n.split('#')[0]); struct.pack_into('<I', data, at+0x6c, 1)
            array(at+0x48, b''.join(struct.pack('<I', offsets[c]) for c, q, _ in specs if q == n), 4)
            floats = []; keys = []
            for kind, (times, rows) in controls.items():
                t = len(floats); floats.extend(times); v = len(floats); floats.extend(x for r in rows for x in r)
                keys.append(struct.pack('<ihhhbb', kind, len(rows), t, v, len(rows[0]), 0))
            array(at+0x54, b''.join(keys), 12); array(at+0x60, struct.pack('<%df' % len(floats), *floats), 4)
        return offsets[specs[0][0]], len(specs)
    text(8, 64, name); text(0xa8, 64, parent); struct.pack_into('<B', data, 0x72, 4); struct.pack_into('<f', data, 0xa4, scale)
    struct.pack_into('<II', data, 0x48, *tree(nodes)); pointers = []
    for clip in clips:
        at = allocate(bytes(0xc4)); pointers.append(at)
        text(at+8, 64, clip['name']); text(at+0x78, 64, clip.get('animroot', 'rootdummy'))
        struct.pack_into('<ff', data, at+0x70, clip.get('length', 1.0), clip.get('transition', 0.25))
        struct.pack_into('<II', data, at+0x48, *tree(clip['nodes']))
        array(at+0xb8, b''.join(struct.pack('<f32s', t, e.encode()) for t, e in clip.get('events', [])), 36)
    array(0x78, b''.join(struct.pack('<I', p) for p in pointers), 4)
    return struct.pack('<III', 0, len(data), 0) + bytes(data)


def rotation(degrees):
    half = np.radians(degrees)/2
    return [0.0, 0.0, float(np.sin(half)), float(np.cos(half))]


def clip(name, root, angle=0.0, offset=0.0, events=((0.5, 'hit'), (0.5, 'blur_end')), animroot='rootdummy', keys=2):
    times = [0.0, 1.0][:keys]
    return {'name': name, 'animroot': animroot, 'events': list(events), 'nodes': [
        (root, '', {}), ('rootdummy', root, {8: (times, [[0.0, 0.0, 1.0+offset]]*keys), 20: (times, [rotation(angle)]*keys)})]}


GEOMETRY = lambda root: [(root, '', {}), ('rootdummy', root, {}), ('impact', 'rootdummy', {}), ('impact#2', 'rootdummy', {})]


class NativeReaderTests(unittest.TestCase):
    def test_clip_metadata_duplicate_impacts_and_controller_byte_ranges(self):
        blob = native('lib', 'a_ba', GEOMETRY('lib'), [clip('walk', 'lib', angle=10, events=[(0.25, 'snd_footstep')])])
        model = lib.NativeModel(blob).decode()
        self.assertEqual((model['name'], model['parent'], model['scale']), ('lib', 'a_ba', 1.0))
        self.assertIn('impact__duplicate_2', model['nodes'])
        walk = model['clips']['walk']
        self.assertEqual((walk['animroot'], walk['events']), ('rootdummy', [[0.25, 'snd_footstep']]))
        control = walk['nodes']['rootdummy']['controls'][20]; start, end = control['dataRange']
        self.assertTrue(np.allclose(np.frombuffer(blob[start:end], '<f4').reshape(-1, 4), control['values']))

    def test_ascii_counted_and_listed_keys_become_quaternions(self):
        text = '\n'.join(['newmodel a_ba_custom', 'setsupermodel a_ba_custom a_ba_casts', 'beginmodelgeom a_ba_custom',
            'node dummy a_ba_custom', 'parent NULL', 'endnode', 'node dummy impact', 'parent a_ba_custom', 'endnode',
            'node dummy impact', 'parent a_ba_custom', 'endnode', 'endmodelgeom a_ba_custom',
            'newanim mount1lp a_ba_custom', 'length 0.5', 'transtime 0.2', 'animroot rootdummy', 'event 0.25 hit',
            'node dummy rootdummy', 'parent a_ba_custom', 'positionkey 2', '0 0 0 1', '0.5 0 0 2',
            'orientationkey', '0 0 0 1 0', '0.5 0 0 1 1.5707963', 'endlist', 'endnode', 'doneanim mount1lp a_ba_custom'])
        model = lib.ascii_model(text)
        self.assertEqual((model['parent'], set(model['nodes'])), ('a_ba_casts', {'a_ba_custom', 'impact', 'impact__duplicate_2'}))
        mount = model['clips']['mount1lp']; controls = mount['nodes']['rootdummy']['controls']
        self.assertEqual((mount['length'], mount['transition'], mount['events']), (0.5, 0.2, [[0.25, 'hit']]))
        self.assertEqual(controls[8]['values'].tolist(), [[0, 0, 1], [0, 0, 2]])
        self.assertTrue(np.allclose(controls[20]['values'], [rotation(0), rotation(90)], atol=1e-6))


class ChainTests(unittest.TestCase):
    models = {'root': {'parent': 'lib', 'clips': {'pause1': 1}}, 'lib': {'parent': 'a_ba', 'clips': {'pause1': 1, 'walk': 1}},
              'a_ba': {'parent': 'null', 'clips': {'walk': 1, 'run': 1}}}

    def test_nearest_owner_wins_and_shadowed_copies_are_listed(self):
        names = lib.chain('root', self.models)
        self.assertEqual(names, ['root', 'lib', 'a_ba'])
        self.assertEqual(lib.effective(names, self.models), {'pause1': {'owner': 'root', 'shadowed': ['lib']},
            'run': {'owner': 'a_ba', 'shadowed': []}, 'walk': {'owner': 'lib', 'shadowed': ['a_ba']}})

    def test_gaps_and_cycles_stop_the_inventory(self):
        with self.assertRaisesRegex(ValueError, 'Inventory gap'):
            lib.chain('root', {**self.models, 'a_ba': {'parent': 'a_ba_non_combat', 'clips': {}}})
        with self.assertRaisesRegex(ValueError, 'Cyclic'):
            lib.chain('root', {**self.models, 'a_ba': {'parent': 'root', 'clips': {}}})


class ComparisonTests(unittest.TestCase):
    def decode(self, name, *clips):
        return lib.NativeModel(native(name, 'null', GEOMETRY(name), clips)).decode()['clips']['walk']

    def test_renamed_carrier_root_and_reordered_simultaneous_events_keep_structure(self):
        stock = self.decode('a_ba', clip('walk', 'a_ba', animroot='a_ba'))
        carrier = self.decode('p17_00_03', clip('walk', 'p17_00_03', animroot='a_ba', events=((0.5, 'blur_end'), (0.5, 'hit'))))
        row = lib.clip_row(carrier, 'p17_00_03')
        self.assertEqual((row['animroot'], row['animrootRaw']), (lib.ROOT, 'a_ba'))
        result = lib.compare_clip(carrier, 'p17_00_03', stock, 'a_ba')
        self.assertTrue(result['structure'] and result['eventOrderChanged'])
        self.assertFalse(result['identical'])
        self.assertEqual((result['positionMetres'], result['rotationDegrees']), (0.0, 0.0))

    def test_worst_key_deltas_and_key_count_changes(self):
        stock = self.decode('a_ba', clip('walk', 'a_ba'))
        near = lib.compare_clip(self.decode('lib', clip('walk', 'lib', angle=0.04, offset=5e-5)), 'lib', stock, 'a_ba')
        self.assertTrue(near['structure'])
        self.assertAlmostEqual(near['rotationDegrees'], 0.04, places=3); self.assertAlmostEqual(near['positionMetres'], 5e-5, places=6)
        self.assertFalse(lib.compare_clip(self.decode('lib', clip('walk', 'lib', keys=1)), 'lib', stock, 'a_ba')['structure'])

    def test_scale_or_other_controller_differences_are_never_inherited(self):
        def scaled(root, value):
            c = clip('walk', root); c['nodes'][1][2][36] = ([0.0, 1.0], [[value]]*2); return c
        source, stock = self.decode('lib', scaled('lib', 1.0)), self.decode('a_ba', scaled('a_ba', 1.2))
        row = lib.compare_clip(source, 'lib', stock, 'a_ba')
        self.assertTrue(row['structure']); self.assertEqual(row['positionMetres'], 0.0); self.assertAlmostEqual(row['otherMax'], 0.2, places=5)
        models = {'lib': {'clips': {'walk': source}}, 'a_ba': {'clips': {'walk': stock}}}
        result = lib.classify(models, [], 'lib', 'a_ba', 'walk', lib.DEFAULT_TOLERANCES)
        self.assertFalse(result['inherit']); self.assertEqual(result['reason'], 'override')


class InventoryTests(unittest.TestCase):
    def test_inventory_records_chains_owners_stock_deltas_and_own_palette_routing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'srn_body').mkdir(); (root/'srn_body_tex').mkdir(); stock_dir = root/'stock'; stock_dir.mkdir()
            def put(path, data):
                (root/path).write_bytes(data); return {'path': path, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
            stock = {}
            for name, parent, clips in (('a_fa', 'a_ba', [clip('pause1', 'a_fa')]), ('a_ba', 'null', [clip('walk', 'a_ba', animroot='a_ba'), clip('pause1', 'a_ba')])):
                data = native(name, parent, GEOMETRY(name), clips); (stock_dir/(name+'.mdl')).write_bytes(data)
                stock[name] = {'path': name+'.mdl', 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'format': 'binary', 'parent': parent}
            (stock_dir/'stock-models.json').write_text(json.dumps({'schemaVersion': 1, 'kind': lib.STOCK_KIND, 'seeds': ['a_ba', 'a_fa'],
                                                                   'models': stock}))
            resources = [
                {**put('srn_body/pfx0.mdl', native('pfx0', 'p_carrier', GEOMETRY('pfx0'))), 'role': 'fitted-rig'},
                {**put('srn_body/p_carrier.mdl', native('p_carrier', 'a_fa', GEOMETRY('p_carrier'),
                    [clip('walk', 'p_carrier', angle=0.01, animroot='a_ba'), clip('pause1', 'p_carrier', angle=3)])), 'role': 'rig-inheritance'},
                {**put('srn_body/pmx0.mdl', native('pmx0', 'a_ba', GEOMETRY('pmx0'))), 'role': 'fitted-rig'},
                {**put('srn_body/pfx0_chest001.plt', b'PLT V1  ' + bytes(8) + struct.pack('<II', 2048, 2048) + bytes(8)), 'role': 'selected-palette'},
                {**put('srn_body_tex/skin_n.tga', struct.pack('<BBB9xHHBB', 0, 0, 2, 1024, 512, 24, 0)), 'role': 'selected-map'},
                {**put('srn_body_tex/skin.mtr', b'renderhint NormalTangents\ntexture1 skin_n\ntexture3 skin_r\n'), 'role': 'selected-material'}]
            manifest = {'version': '1.0.0', 'resources': resources,
                'targets': [{'target': 'x_female_fit', 'modelPrefix': 'pfx0'}, {'target': 'x_male_fit', 'modelPrefix': 'pmx0'}],
                'modelDependencies': [{'model': 'pfx0_chest001', 'role': 'body-part', 'textureSlots': [['pfh0_chest001', '', '', 'skin']]}]}
            (root/'manifest.json').write_text(json.dumps(manifest))
            result = lib.inventory(root, root/'manifest.json', stock_dir/'stock-models.json')
            female, male = result['targets']
            self.assertEqual(female['chain'], ['pfx0', 'p_carrier', 'a_fa', 'a_ba'])
            self.assertEqual((female['privateCarriers'], female['storedPrivateClips']), (['p_carrier'], 2))
            walk = female['clips']['walk']['stock']; pause = female['clips']['pause1']['stock']
            self.assertEqual((walk['seed'], walk['owner'], walk['structure']), ('a_fa', 'a_ba', True))
            self.assertLess(walk['rotationDegrees'], 0.05); self.assertGreater(pause['rotationDegrees'], 2.9)
            self.assertEqual(male['chain'], ['pmx0', 'a_ba']); self.assertTrue(male['clips']['walk']['stock']['identical'])
            usage, = result['textureUsage']
            self.assertEqual((usage['bitmapResource'], usage['storedTexture0']), ('pfx0_chest001.plt', 'pfh0_chest001'))
            self.assertEqual(usage['materialTextures'], {'texture1': 'skin_n.tga', 'texture3': 'installed-game:skin_r'})
            self.assertEqual(result['summary']['texturesAbove1024'], ['pfx0_chest001.plt'])
            self.assertEqual(result['textures']['skin_n.tga']['width'], 1024)
            self.assertEqual(result['unusedPrivateCarriers'], [])
            declared = consumed(['anim-library', 'inventory', '--root', str(root), '--manifest', str(root/'manifest.json'),
                                 '--stock', str(stock_dir/'stock-models.json'), '--output', str(root/'out.json')])
            self.assertTrue({(stock_dir/'a_ba.mdl').resolve(), (root/'srn_body/p_carrier.mdl').resolve(),
                             (root/'srn_body_tex/skin.mtr').resolve()} <= declared)
            with self.assertRaisesRegex(ValueError, 'Unknown anim-library action'):
                consumed(['anim-library', 'bogus'])


def simulated_compile(text):
    """Stand-in for the EE compiler: same layout, axis-angle rounding and time-sorted events."""
    model = lib.ascii_model(text)
    def specs(nodes):
        named = {}
        for name, row in nodes.items():
            named[name] = name.replace('__duplicate_', '#')
        return [(named[n], named.get(r['parent'], ''), {k: (list(c['times']), [list(v) for v in c['values']])
                for k, c in r['controls'].items()}) for n, r in nodes.items()]
    clips = [{'name': n, 'animroot': c['animroot'], 'length': c['length'], 'transition': c['transition'],
              'events': sorted(c['events']), 'nodes': specs(c['nodes'])} for n, c in model['clips'].items()]
    return native(model['name'], model['parent'], specs(model['nodes']), clips, model['scale'])


class LibraryBuildTests(unittest.TestCase):
    def release(self, root, large_slash=7.0):
        """Female Fit/Large roots on private carriers, plus the stock a_fa > a_ba chain."""
        (root/'srn_body').mkdir(); stock_dir = root/'stock'; stock_dir.mkdir(); stock = {}; resources = []
        for name, parent, clips in (('a_fa', 'a_ba', [clip('pause1', 'a_fa')]),
                                    ('a_ba', 'null', [clip('walk', 'a_ba', animroot='a_ba'), clip('run', 'a_ba', animroot='a_ba')])):
            data = native(name, parent, GEOMETRY(name), clips); (stock_dir/(name+'.mdl')).write_bytes(data)
            stock[name] = {'path': name+'.mdl', 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'format': 'binary', 'parent': parent}
        (stock_dir/'stock-models.json').write_text(json.dumps({'schemaVersion': 1, 'kind': lib.STOCK_KIND, 'seeds': ['a_fa'], 'models': stock}))
        for root_name, carrier, slash in (('pfx0', 'pcf0', 5.0), ('pfx2', 'pcf2', large_slash)):
            for name, parent, clips, role in ((root_name, carrier, [], 'fitted-rig'), (carrier, 'null', [
                    clip('walk', carrier, angle=0.01, animroot='a_ba', events=((0.5, 'blur_end'), (0.5, 'hit'))),
                    clip('run', carrier, angle=4, animroot='a_ba'), clip('pause1', carrier, angle=3), clip('slash', carrier, angle=slash)],
                    'rig-inheritance')):
                data = native(name, parent, GEOMETRY(name), clips); (root/'srn_body'/(name+'.mdl')).write_bytes(data)
                resources.append({'path': f'srn_body/{name}.mdl', 'sha256': hashlib.sha256(data).hexdigest(), 'role': role})
        (root/'manifest.json').write_text(json.dumps({'version': '1.0.0', 'resources': resources, 'targets': [], 'modelDependencies': []}))
        return root/'manifest.json', stock_dir/'stock-models.json'

    def test_build_restore_repoint_and_compare_motion(self):
        from .motion_compare import compare
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, stock = self.release(root); out = root/'build'
            with self.assertRaisesRegex(ValueError, 'Unauthorized Fit/Large difference: slash'):
                lib.build(root, manifest, stock, 'pfx0', 'pfx2', 'srn_an_xf', root/'refused')
            result = lib.build(root, manifest, stock, 'pfx0', 'pfx2', 'srn_an_xf', out, allowed=['slash'])
            self.assertEqual((result['retained'], result['inherited'], result['fitLargeDifferences']), (3, 1, ['slash']))
            walk = result['clips']['walk']
            self.assertTrue(walk['inherit'] and walk['eventOrderChanged'])
            self.assertLess(max(d['metres'] for d in walk['assembledDrift'].values()), 1e-3)
            self.assertEqual(result['clips']['slash']['reason'], 'not in stock')
            text = (out/'converted/ascii/srn_an_xf.mdl').read_text()
            self.assertIn('setsupermodel srn_an_xf a_fa', text); self.assertNotIn('newanim walk', text)
            compiled = out/'converted/resources/srn_an_xf.mdl'; compiled.write_bytes(simulated_compile(text))
            receipt = lib.restore(root, out/'restoration-plan.json', compiled, root/'restored/srn_an_xf.mdl')
            self.assertTrue(receipt['exactSourcePayload']); self.assertEqual(receipt['clips'], 3)
            restored = lib.NativeModel((root/'restored/srn_an_xf.mdl').read_bytes()).decode()
            carrier = lib.load_model(root/'srn_body/pcf0.mdl')
            for name in ('run', 'pause1', 'slash'):
                self.assertTrue(lib.clips_equal(restored['clips'][name], 'srn_an_xf', carrier['clips'][name], 'pcf0'))
            reports = {}
            for target, allowed in (('pfx0', ()), ('pfx2', ('slash',))):
                repointed = root/f'{target}.mdl'; repointed.write_bytes(lib.repoint((root/'srn_body'/f'{target}.mdl').read_bytes(), 'srn_an_xf'))
                reports[target] = compare(root, manifest, stock, target, root/'restored/srn_an_xf.mdl', repointed, allowed)
            self.assertTrue(reports['pfx0']['passed'])
            self.assertEqual(reports['pfx0']['newChain'], ['pfx0', 'srn_an_xf', 'a_fa', 'a_ba'])
            self.assertEqual(reports['pfx0']['counts'], {'exact': 3, 'inherited-within-tolerance': 1})
            self.assertEqual(reports['pfx2']['clips']['slash']['status'], 'authorized-fit-clip')

    def test_layout_changes_and_tampering_fail_instead_of_resampling(self):
        from .motion_compare import compare
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, stock = self.release(root); out = root/'build'
            lib.build(root, manifest, stock, 'pfx0', 'pfx2', 'srn_an_xf', out, allowed=['slash'])
            text = (out/'converted/ascii/srn_an_xf.mdl').read_text()
            # A compiler that dropped a key must stop the restore.
            lines = text.splitlines(); first = lines.index('    positionkey') + 1; del lines[first]
            compiled = out/'converted/resources/srn_an_xf.mdl'; compiled.write_bytes(simulated_compile('\n'.join(lines)))
            with self.assertRaisesRegex(ValueError, 'layout differs'):
                lib.restore(root, out/'restoration-plan.json', compiled, root/'bad.mdl')
            compiled.write_bytes(simulated_compile(text))
            lib.restore(root, out/'restoration-plan.json', compiled, root/'good.mdl')
            blob = bytearray((root/'good.mdl').read_bytes()); model = lib.NativeModel(bytes(blob)).decode()
            a, b = model['clips']['run']['nodes']['rootdummy']['controls'][20]['dataRange']; blob[a:a+4] = struct.pack('<f', 0.5)
            (root/'tampered.mdl').write_bytes(bytes(blob)); repointed = root/'pfx0.mdl'
            repointed.write_bytes(lib.repoint((root/'srn_body/pfx0.mdl').read_bytes(), 'srn_an_xf'))
            report = compare(root, manifest, stock, 'pfx0', root/'tampered.mdl', repointed)
            self.assertEqual((report['passed'], report['failures']), (False, ['run']))
            moved = bytearray(repointed.read_bytes()); moved[20] ^= 1; (root/'moved.mdl').write_bytes(bytes(moved))
            with self.assertRaisesRegex(ValueError, 'outside the supermodel field'):
                compare(root, manifest, stock, 'pfx0', root/'good.mdl', root/'moved.mdl')

    def test_root_repointed_straight_to_stock_compares_without_a_library(self):
        from .motion_compare import compare
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, stock = self.release(root); data = json.loads(manifest.read_text())
            for name, parent, clips, role in (('pmx2', 'pcm2', [], 'fitted-rig'), ('pcm2', 'null', [
                    clip('walk', 'pcm2', animroot='a_ba'), clip('run', 'pcm2', animroot='a_ba', offset=2e-5)], 'rig-inheritance')):
                blob = native(name, parent, GEOMETRY(name), clips); (root/'srn_body'/(name+'.mdl')).write_bytes(blob)
                data['resources'].append({'path': f'srn_body/{name}.mdl', 'sha256': hashlib.sha256(blob).hexdigest(), 'role': role})
            manifest.write_text(json.dumps(data)); repointed = root/'pmx2.mdl'
            repointed.write_bytes(lib.repoint((root/'srn_body/pmx2.mdl').read_bytes(), 'a_ba'))
            report = compare(root, manifest, stock, 'pmx2', None, repointed)
            self.assertEqual((report['newChain'], report['library'], report['passed']), (['pmx2', 'a_ba'], None, True))
            self.assertEqual(report['counts'], {'inherited-exact': 1, 'inherited-within-tolerance': 1})
            (root/'odd.mdl').write_bytes(lib.repoint((root/'srn_body/pmx2.mdl').read_bytes(), 'pcf0'))
            with self.assertRaisesRegex(ValueError, 'installed stock model'):
                compare(root, manifest, stock, 'pmx2', None, root/'odd.mdl')

    def test_repoint_changes_only_the_supermodel_field(self):
        blob = native('pfx0', 'pcf0', GEOMETRY('pfx0'))
        result = lib.repoint(blob, 'srn_an_xf'); a, b = lib.PARENT_FIELD
        self.assertEqual((result[:a], result[b:]), (blob[:a], blob[b:]))
        self.assertEqual(lib.NativeModel(result).decode()['parent'], 'srn_an_xf')


if __name__ == '__main__':
    unittest.main()
