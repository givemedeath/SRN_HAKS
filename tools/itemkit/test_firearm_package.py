"""Final-array firearm packaging and intake regression checks without a GPU."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from tools.headkit.common import pin, read, write
from .__main__ import intake
from .contracts import family, manifest
from .firearm_native import placeholder_geometry, audit_blueprint_roundtrip
from . import firearm_package
from .firearm_package import prepare, prepared_inputs
from .native import archive_helpers
from .fixture import packaged_blueprints
from .firearms import plan


class FirearmPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.profile = self.root/'profile.json'; write(self.profile, {})
        self.table = self.root/'baseitems.2da'
        self.table.write_text('2DA V2.0\n\nlabel ItemClass ModelType MinRange MaxRange InvSlotWidth InvSlotHeight\n'
                              '61 sling WBwSl 0 0 50 1 2\n')
        geometry = placeholder_geometry(radius=.001)
        arrays = self.root/'corners.npz'
        np.savez(arrays, **geometry, shadowVertices=geometry['positions'].reshape(-1, 3),
                 shadowFaces=np.arange(12).reshape(-1, 3))
        texture = self.root/'texture.png'; Image.new('RGB', (1024, 1024), (50, 60, 70)).save(texture)
        icon = self.root/'icon.png'; Image.new('RGBA', (32, 64), (50, 60, 70, 255)).save(icon)
        self.spec = {'schemaVersion': 1, 'sourceProfile': pin(self.profile), 'comparisonHaks': [],
                     'subtype': 'pistol', 'identity': {'texturePrefix': 'sr_p', 'blueprintPrefix': 'sr_p',
                         'hak': 'sr_p_test', 'module': 'sr_p_test', 'displayName': 'Test pistol'},
                     'variants': [{'colour': colour, 'displayName': 'Test '+str(colour),
                                   'arrays': pin(arrays), 'texture': pin(texture), 'icon': pin(icon)}
                                  for colour in (1, 2)]}
        self.spec_path = self.root/'spec.json'; self.output = self.root/'prepared'
        self.resources = {'baseitems.2da': pin(self.table), 'iwbwsl_b_024.tga': None}

    def prepare(self):
        write(self.spec_path, self.spec)
        # Only installed-stack discovery is replaced. Real array/image/pin,
        # allocation, topology, assembly and file preparation code all runs.
        with patch.object(firearm_package, 'stack_inputs', return_value=[pin(self.table)]), \
             patch.object(firearm_package, 'native_contract', return_value=({}, self.resources)):
            return prepare(self.spec_path, self.output)

    def test_complete_colours_hidden_resources_and_per_part_bytes(self):
        result = self.prepare()
        self.assertEqual(result['allocation']['modelIndex'], 3)
        self.assertEqual(len(list((self.output/'ascii').glob('*.mdl'))), 8)
        self.assertEqual(result['iconSize'], [32, 64])
        for colour in (1, 2):
            bp = read(self.output/f'sr_p_{colour}.json')
            self.assertEqual([bp[f'ModelPart{i}']['value'] for i in (1, 2, 3)], [30+colour, 10+colour, 10+colour])
        self.assertIn(str(self.table.resolve()), {row['path'] for row in prepared_inputs(self.output)})
        for name in result['allocation']['placeholders']:
            self.assertIn('render 0\n  shadow 0', (self.output/'ascii'/f'{name}.mdl').read_text())
            with Image.open(self.output/'resources'/f'i{name}.tga') as image:
                self.assertIsNone(image.getchannel('A').getbbox())

    def test_changed_corner_bytes_rejected_before_output(self):
        Path(self.spec['variants'][0]['arrays']['path']).write_bytes(b'stale')
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse(self.output.exists())

    def test_changed_source_or_prepared_output_rejected_before_compile(self):
        self.prepare()
        (self.output/'resources'/'sr_p_031.tga').write_bytes(b'stale')
        with self.assertRaises(ValueError): prepared_inputs(self.output)

    def test_correct_dimensions_required_before_output(self):
        bad = self.root/'bad-icon.png'; Image.new('RGBA', (64, 64)).save(bad)
        self.spec['variants'][0]['icon'] = pin(bad)
        with self.assertRaisesRegex(ValueError, 'dimensions'): self.prepare()
        self.assertFalse(self.output.exists())

    def test_placeholder_budget_included_before_output(self):
        target = self.root/'over-budget.npz'
        with np.load(self.spec['variants'][0]['arrays']['path']) as data:
            np.savez(target, positions=np.tile(data['positions'], (2499, 1, 1)),
                     normals=np.tile(data['normals'], (2499, 1, 1)), uv=np.tile(data['uv'], (2499, 1, 1)),
                     shadowVertices=data['shadowVertices'], shadowFaces=data['shadowFaces'])
        self.spec['variants'][0]['arrays'] = pin(target)
        with self.assertRaisesRegex(ValueError, 'Complete firearm'): self.prepare()
        self.assertFalse(self.output.exists())

    def test_combined_fixture_namespace_collision(self):
        hak = self.root/'comparison.hak'; helper = archive_helpers()
        helper.write_hak(hak, [('sr_p_1', 2025, b'existing blueprint')])
        self.spec['comparisonHaks'] = [pin(hak)]
        with self.assertRaisesRegex(ValueError, 'Blueprint resource collision'): self.prepare()

    def test_geometry_changing_color_retains_separate_expected_arrays(self):
        path = self.root/'other-corners.npz'
        with np.load(self.spec['variants'][0]['arrays']['path']) as data:
            changed = {k: data[k].copy() for k in data.files}
        changed['positions'][:,:,2] *= 2; changed['shadowVertices'][:,2] *= 2
        p = changed['positions']; n = np.cross(p[:,1]-p[:,0], p[:,2]-p[:,0]); n /= np.linalg.norm(n,axis=1)[:,None]
        changed['normals'] = np.repeat(n[:,None,:],3,axis=1)
        np.savez(path, **changed); self.spec['variants'][1]['arrays'] = pin(path)
        result = self.prepare()
        self.assertEqual(len({p['sha256'] for p in result['expected'].values()}), 2)

    def test_pistol_intake_has_no_melee_materials_or_false_native_approval(self):
        image = self.root/'reference.png'; Image.new('RGB', (512,512)).save(image)
        result = intake(image, self.root/'intake', 'example-pistol', 'firearm-sling')
        data = manifest(result['manifest']['path']); profile = family(self.root/'intake/family.json')
        self.assertEqual(data['id'], 'example-pistol')
        self.assertNotIn('Cougar', str(data)); self.assertNotIn('pommel', str(data))
        self.assertFalse(data['approval']['inputReviewComplete'])
        self.assertEqual(profile['nativePackaging'], 'blocked')
        self.assertEqual(profile['budgets']['parts']['m'], {'visible':4, 'shadow':0})
        self.assertEqual(profile['sourceExport']['signMode'], 'udf')
        profile['budgets']['parts']['m']['shadow'] = 4
        write(self.root/'intake/family.json', profile)
        with self.assertRaisesRegex(ValueError, 'hidden placeholders'): family(self.root/'intake/family.json')

    def test_firearm_intake_requires_explicit_identity(self):
        with self.assertRaisesRegex(ValueError, 'explicit design ID'):
            intake(self.root/'unused.png', self.root/'intake', family_name='firearm-sling')

    def test_uti_root_sentinel_and_every_field_remain_verified(self):
        import struct
        raw=bytearray(68);raw[:8]=b'UTI V3.2'
        struct.pack_into('<II',raw,8,56,1);struct.pack_into('<I',raw,56,0xffffffff)
        path=self.root/'item.uti';path.write_bytes(raw)
        expected={'__data_type':'UTI ','__struct_id':-1,'BaseItem':{'type':'int','value':61}}
        decoded={k:v for k,v in expected.items() if k!='__struct_id'}
        self.assertTrue(audit_blueprint_roundtrip(path,decoded,expected)['allFieldsExact'])
        with self.assertRaisesRegex(ValueError,'field roundtrip'):
            audit_blueprint_roundtrip(path,{'__data_type':'UTI '},expected)
        struct.pack_into('<I',raw,56,0);path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'root struct ID'):audit_blueprint_roundtrip(path,decoded,expected)

    def test_fixture_uses_exact_hak_blueprints_and_rejects_substitution(self):
        allocation = plan('pistol', [1,2], [], 'test', 'test')
        rows = []; payload = []
        for variant in allocation['variants']:
            target = self.root/(variant['blueprint']+'.uti'); target.write_bytes(bytes([variant['colour']]))
            payload.append((target.stem, 2025, target.read_bytes()))
            rows.append({'colour': variant['colour'], 'utiParts': variant['utiParts'], 'file': pin(target)})
        hak = self.root/'native.hak'; archive_helpers().write_hak(hak, payload)
        native = {'kind':'firearm-native-package', 'baseItem':61, 'hak':pin(hak),
                  'allocation':allocation, 'blueprints':rows, 'identity':{'blueprint':'test_1'},
                  'counts':{str(c):{p:{'visible':4,'shadow':0} for p in ('b','m','t')} for c in (1,2)}}
        self.assertEqual([name for name, _ in packaged_blueprints(native)], ['test_1','test_2'])
        swapped = copy.deepcopy(native); swapped['blueprints'][1]['utiParts']['ModelPart1'] = 99
        with self.assertRaisesRegex(ValueError, 'UTI part'): packaged_blueprints(swapped)
        missing = copy.deepcopy(native); missing['blueprints'].pop()
        with self.assertRaisesRegex(ValueError, 'Incomplete'): packaged_blueprints(missing)
        target.write_bytes(b'new uncompiled variant'); native['blueprints'][1]['file'] = pin(target)
        with self.assertRaisesRegex(ValueError, 'packaged bytes'): packaged_blueprints(native)


if __name__ == '__main__': unittest.main()
