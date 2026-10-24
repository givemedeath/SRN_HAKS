"""Firearm allocation and surgical private-override regressions."""
import copy
import unittest
import numpy as np

from . import firearms as f
from .contracts import model_names
from .fixture import blueprint
from .firearm_native import placeholder_geometry, placeholder_ascii, variant_blueprint


TABLE = (b'2DA V2.0\r\n\r\n// keep this byte-for-byte\r\n'
         b'label ItemClass ModelType MinRange MaxRange WeaponWield AmmunitionType\r\n'
         b'1 longsword WSwLs 2 10 100 **** ****\r\n'
         b'61\tsling\tWBwSl   0  0 50 10 3\r\n'
         b'62 other thing 0 0 100 7 1\r\n')


class FirearmTests(unittest.TestCase):
    def allocation(self, occupied=(), colours=(1, 2), subtype='pistol'):
        return f.plan(subtype, colours, occupied, 'sr_pt', 'sr_pt')

    def test_pistol_and_reserved_slots(self):
        for subtype, slot in f.SLOTS.items():
            result = self.allocation(subtype=subtype)
            self.assertEqual(result['slot'], slot)
            self.assertEqual(result['modelIndex'], 2)
            self.assertEqual(len(result['variants']), 2)
            for variant in result['variants']:
                c = variant['colour']
                self.assertEqual(variant['utiParts'], {
                    field: (21 if p == slot else 11)+c-1 for p, field in f.PART_FIELDS.items()})
                self.assertEqual(variant['models'][slot], f'wbwsl_{slot}_02{c}')

    def test_all_colour_resources_unique_and_placeholders_complete(self):
        a = self.allocation()
        self.assertEqual(len(a['placeholders']), 6)
        self.assertEqual(len(a['resources']), len(set(a['resources'])))
        self.assertEqual(len(a['resources']), 20)
        self.assertNotEqual(a['variants'][0]['models']['b'], a['variants'][1]['models']['b'])

    def test_other_colour_and_orphan_icons_reserve_shape(self):
        result = self.allocation(['IWBWSL_B_024.TGA', 'wbwsl_b_039.mdl', 'iwbwsl_b_044.dds'])
        self.assertEqual(result['modelIndex'], 5)

    def test_slot_reservations_do_not_consume_other_slots(self):
        self.assertEqual(self.allocation(['wbwsl_t_021.mdl'])['modelIndex'], 2)

    def test_placeholder_collisions_fail(self):
        for name in ['wbwsl_t_011.mdl', 'iwbwsl_m_012.dds', 'iwbwsl_b_011.tga']:
            with self.assertRaisesRegex(ValueError, 'Placeholder'): self.allocation([name])

    def test_blueprint_collision_fails(self):
        with self.assertRaisesRegex(ValueError, 'Blueprint resource collision'): self.allocation(['sr_pt_2.uti'])

    def test_occupied_texture_or_material_skips_to_next_free_index(self):
        for name in ['sr_pt_021.mtr', 'sr_pt_022.txi', 'sr_pt_021.dds', 'SR_PT_022.TGA']:
            with self.subTest(name=name):
                a = self.allocation([name]); self.assertEqual(a['modelIndex'], 3)
                self.assertEqual([v['texture'] for v in a['variants']], ['sr_pt_031', 'sr_pt_032'])
        with self.assertRaisesRegex(ValueError, 'No collision-free'):
            self.allocation([f'sr_pt_{i:02d}1.tga' for i in range(2, 26)])

    def test_no_identity_aliasing(self):
        with self.assertRaises(ValueError): f.plan('pistol', [1, 2], [], 'this_resref_is_too_long', 'item')
        with self.assertRaises(ValueError): f.plan('pistol', [1, 2], [], '../bad', 'item')

    def test_bad_colours_rejected(self):
        for colours in [[], [1, 1], [0], [10], [True], [1, 3], ['1']]:
            with self.subTest(colours=colours), self.assertRaises(ValueError): self.allocation(colours=colours)

    def test_exhaustion_and_byte_limit(self):
        occupied = [f'wbwsl_b_{i*10+1:03d}.mdl' for i in range(2, 26)]
        with self.assertRaisesRegex(ValueError, 'No collision-free'): self.allocation(occupied)
        occupied.pop()
        self.assertEqual(self.allocation(occupied)['modelIndex'], 25)
        with self.assertRaises(ValueError): self.allocation(occupied, colours=[6])

    def test_private_override_changes_only_model_type_when_range_sufficient(self):
        output, evidence = f.private_override(TABLE, self.allocation())
        self.assertEqual(output, TABLE.replace(b'WBwSl   0', b'WBwSl   2'))
        self.assertEqual(evidence['changes'], {'ModelType': {'before': '0', 'after': '2'}})

    def test_range_extended_only_as_required(self):
        a = self.allocation([f'iwbwsl_b_0{i}4.tga' for i in (2, 3, 4)])
        output, evidence = f.private_override(TABLE, a)
        self.assertEqual(output, TABLE.replace(b'WBwSl   0  0 50', b'WBwSl   2  0 52'))
        self.assertEqual(evidence['changes']['MaxRange']['after'], '52')
        self.assertTrue(evidence['unrelatedBytesPreserved'])
        same, second = f.private_override(output, a)
        self.assertEqual(same, output)
        self.assertEqual(second['changes'], {})

    def test_bom_default_and_missing_final_newline_preserved(self):
        source = b'\xef\xbb\xbf'+TABLE.replace(b'\r\n\r\n', b'\r\nDEFAULT: ****\r\n', 1).rstrip(b'\r\n')
        result, _ = f.private_override(source, self.allocation())
        self.assertEqual(result, source.replace(b'WBwSl   0', b'WBwSl   2'))

    def test_wrong_native_identity_fails(self):
        for source in [TABLE.replace(b'61\t', b'60\t'), TABLE.replace(b'WBwSl', b'Foo'),
                       TABLE.replace(b'WBwSl   0', b'WBwSl   1'), TABLE.replace(b'0 50 10', b'0 256 10')]:
            with self.assertRaises(ValueError): f.private_override(source, self.allocation())

    def test_complete_budget_and_exact_assembly(self):
        a = self.allocation(); v = a['variants'][0]
        counts = {'b': {'visible': 9992, 'shadow': 500},
                  'm': {'visible': 4, 'shadow': 0}, 't': {'visible': 4, 'shadow': 0}}
        self.assertTrue(f.validate_assembly(a, v, counts))
        counts['b']['visible'] += 1
        with self.assertRaisesRegex(ValueError, 'Complete'): f.validate_assembly(a, v, counts)
        counts['b']['visible'] -= 1
        counts['t']['shadow'] = 4
        with self.assertRaisesRegex(ValueError, 'Placeholder'): f.validate_assembly(a, v, counts)
        counts['t']['shadow'] = 0
        mixed = copy.deepcopy(v); mixed['models']['b'] = 'wbwsl_b_031'
        with self.assertRaisesRegex(ValueError, 'Undeclared'): f.validate_assembly(a, mixed, counts)
        v['models']['b'] = 'wbwsl_b_031'
        with self.assertRaisesRegex(ValueError, 'Mixed'): f.validate_assembly(a, v, counts)

    def test_legacy_melee_naming_and_blueprint_unchanged(self):
        profile = {'nativePackaging': 'enabled', 'native': {'itemClass': 'wswls'}}
        self.assertEqual(model_names(profile, 10), {p: f'wswls_{p}_101' for p in ('b', 'm', 't')})
        item = blueprint(1, {'modelIndex': 10, 'colourIndex': 1})
        self.assertEqual([item['ModelPart'+str(i)]['value'] for i in (1, 2, 3)], [101]*3)

    def test_placeholder_is_tiny_valid_and_never_rendered_or_shadowed(self):
        geometry = placeholder_geometry()
        text = placeholder_ascii('wbwsl_t_011', geometry)
        self.assertIn('  render 0\n  shadow 0\n', text)
        self.assertEqual(text.count('node trimesh'), 1)
        self.assertIn('  faces 4', text)
        for radius in (0, -.001, .01, float('nan')):
            with self.assertRaises(ValueError): placeholder_geometry(radius=radius)
        geometry['positions'] *= 10
        with self.assertRaisesRegex(ValueError, 'size'): placeholder_ascii('wbwsl_t_011', geometry)

    def test_placeholder_rejects_degenerate_geometry_and_nonunit_normals(self):
        geometry = placeholder_geometry(); geometry['positions'][:] = 0
        with self.assertRaisesRegex(ValueError, 'Closed'): placeholder_ascii('wbwsl_t_011', geometry)
        geometry = placeholder_geometry(); geometry['normals'] *= 2
        with self.assertRaisesRegex(ValueError, 'Unit'): placeholder_ascii('wbwsl_t_011', geometry)

    def test_pistol_blueprint_maps_bottom_middle_top_independently(self):
        allocation = self.allocation()
        counts = {p: {'visible': 4, 'shadow': 0} for p in ('b', 'm', 't')}
        for variant in allocation['variants']:
            result = variant_blueprint(allocation, variant, counts, 'Synthetic '+str(variant['colour']))
            self.assertEqual(result['BaseItem']['value'], 61)
            self.assertEqual(result['ModelPart1']['value'], 20+variant['colour'])
            self.assertEqual(result['ModelPart2']['value'], 10+variant['colour'])
            self.assertEqual(result['ModelPart3']['value'], 10+variant['colour'])
            self.assertEqual(result['TemplateResRef']['value'], variant['blueprint'])


if __name__ == '__main__': unittest.main()
