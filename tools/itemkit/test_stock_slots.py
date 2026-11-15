"""Stock appearance slots: a new design takes a base-game slot only on the explicit opt-in, once 1..25 hold no free one."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.headkit.common import pin, read, write
from tools.itemkit import contracts
from tools.itemkit.test_itemkit import Fixture


def slot(index, cls='wswss', dds=True):
    """The names the installed base game holds for one shape's colour-1 variant (models, TGA icons and their DDS twins)."""
    names = {f'{cls}_{p}_{index:02d}1.mdl' for p in 'bmt'} | {f'i{cls}_{p}_{index:02d}1.tga' for p in 'bmt'}
    return names | ({f'i{cls}_{p}_{index:02d}1.dds' for p in 'bmt'} if dds else set())


def project(index, cls='wswss'):
    return {f'{cls}_{p}_{index:02d}1.mdl' for p in 'bmt'} | {f'i{cls}_{p}_{index:02d}1.tga' for p in 'bmt'}


class ReserveStockTests(Fixture):
    def setUp(self):
        super().setUp(); self.native()
        self.stock = set().union(*(slot(i) for i in range(1, 10)))             # stock shapes 1..9, as on every melee carrier
        self.full = self.stock | set().union(*(project(i) for i in range(10, 26)))

    def test_a_free_slot_comes_first_even_with_the_opt_in(self):
        resources = self.full - project(17)
        for opt_in in (False, True):
            result = contracts.reserve(self.profile, resources, stock=self.stock, replace_stock=opt_in)
            self.assertEqual(result['modelIndex'], 17); self.assertNotIn('replacesStock', result)

    def test_a_full_carrier_takes_the_highest_stock_slot_only_on_the_opt_in(self):
        with self.assertRaisesRegex(ValueError, 'replace-stock opt-in'): contracts.reserve(self.profile, self.full, stock=self.stock)
        result = contracts.reserve(self.profile, self.full, stock=self.stock, replace_stock=True)
        self.assertEqual(result['modelIndex'], 9)
        self.assertEqual(result['models'], {'b': 'wswss_b_091', 'm': 'wswss_m_091', 't': 'wswss_t_091'})
        self.assertEqual(result['replacesStock'], sorted(slot(9)))
        self.assertEqual(result['texture'], 'sr_cfl' + '_09')

    def test_a_slot_a_project_or_sibling_resource_holds_is_never_taken(self):
        # srn_weapon (or a live sibling) already overrides shape 9's blade: that slot is not stock-only any more.
        result = contracts.reserve(self.profile, self.full, stock=self.stock - {'wswss_t_091.mdl'}, replace_stock=True)
        self.assertEqual(result['modelIndex'], 8)
        with self.assertRaisesRegex(ValueError, 'every slot holds project or sibling'):
            contracts.reserve(self.profile, self.full, stock=set(), replace_stock=True)

    def test_a_slot_whose_texture_name_is_taken_is_skipped(self):
        texture = 'sr_cfl' + '_09.tga'
        result = contracts.reserve(self.profile, self.full | {texture}, stock=self.stock, replace_stock=True)
        self.assertEqual(result['modelIndex'], 8)

    def test_a_pinned_stock_slot_needs_exactly_its_recorded_replacement(self):
        self.profile['resources'] = {**self.profile.get('resources', {}), 'appearanceIndex': 9, 'replacesStock': sorted(slot(9))}
        result = contracts.reserve(self.profile, self.full, 9, stock=self.stock)
        self.assertEqual((result['modelIndex'], result['replacesStock']), (9, sorted(slot(9))))
        with self.assertRaisesRegex(ValueError, 'overlaps project or sibling'):
            contracts.reserve(self.profile, self.full, 9, stock=self.stock - {'wswss_b_091.mdl'})
        self.profile['resources']['replacesStock'] = sorted(slot(9) - {'iwswss_b_091.dds'})
        with self.assertRaisesRegex(ValueError, 'pinned index 9'): contracts.reserve(self.profile, self.full, 9, stock=self.stock)
        del self.profile['resources']['replacesStock']
        with self.assertRaisesRegex(ValueError, 'collision-free'): contracts.reserve(self.profile, self.full, 9, stock=self.stock)

    def test_the_family_contract_checks_its_recorded_replacement(self):
        base = {k: v for k, v in self.profile.get('resources', {}).items() if k not in ('appearanceIndex', 'replacesStock')}
        def family(resources):
            self.profile['resources'] = {**base, **resources}; write(self.profile_path, self.profile)
            return contracts.family(self.profile_path, validate_native=False)
        self.assertEqual(family({'appearanceIndex': 9, 'replacesStock': sorted(slot(9))})['resources']['appearanceIndex'], 9)
        for bad, message in (({'replacesStock': sorted(slot(9))}, 'sorted list'),
                             ({'appearanceIndex': 9, 'replacesStock': sorted(slot(9))[::-1]}, 'sorted list'),
                             ({'appearanceIndex': 9, 'replacesStock': []}, 'sorted list'),
                             ({'appearanceIndex': 9, 'replacesStock': sorted(slot(8))}, 'outside its appearance slot')):
            with self.assertRaisesRegex(ValueError, message): family(bad)


class StockNamespaceTests(Fixture):
    """native_contract(stock=...): installed KEY names that no project layer lists or inventories."""
    def stock(self, layers):
        self.native(); stack = self.path.parent/'stack/stack.json'; document = read(stack); folder = stack.parent/'base'
        for name, files, inventory in layers:
            rows = []
            for resource in files:
                (folder/resource).write_bytes(resource.encode()); rows.append({'resource': resource, 'file': {'path': 'base/'+resource, 'sha256': pin(folder/resource)['sha256']}})
            document['layers'].insert(0 if inventory else len(document['layers']), {'name': name, 'resources': rows,
                                                                                   **({'nameInventory': inventory} if inventory else {})})
        write(stack, document); self.profile['native']['stack']['sha256'] = pin(stack)['sha256']
        installed = slot(1) | slot(2) | slot(3) | {'baseitems.2da'}
        def namespace(path, layer):
            if 'nameInventory' not in layer: return set(), None, []
            if layer['nameInventory'] == 'key': return installed, {}, []
            return {'pmh0.mdl'}, None, []                    # a published-human style inventory: project names
        stock = set()
        with mock.patch('tools.itemkit.native_stack.namespace', namespace):
            contracts.native_contract(self.profile_path, self.profile, stock=stock)
        return stock

    def test_installed_names_count_as_stock_unless_a_project_layer_holds_them(self):
        stock = self.stock([('installed-stock-key', [], 'key'),
                            ('installed-stock-wswss-donors', ['iwswss_b_011.tga'], None),
                            ('published-approved-weapons-srn_weapon', ['wswss_t_021.mdl', 'iwswss_t_021.tga'], None),
                            ('shipped-bodies', [], 'bodies')])
        self.assertTrue(slot(3) <= stock); self.assertIn('iwswss_b_011.tga', stock)   # a stock extraction layer is still stock
        self.assertTrue({'wswss_t_021.mdl', 'iwswss_t_021.tga'}.isdisjoint(stock))   # srn_weapon overrides them already
        self.assertIn('wswss_b_021.mdl', stock); self.assertNotIn('pmh0.mdl', stock)
        # The fixture's own unnamed base layer lists the shortsword donors and the table: project files, not stock.
        self.assertNotIn('wswss_b_011.mdl', stock); self.assertNotIn('baseitems.2da', stock)

    def test_without_a_key_namespace_nothing_is_stock(self):
        self.assertEqual(self.stock([('installed-stock-wswss-donors', ['iwswss_b_011.tga'], None)]), set())


class DdsTwinTests(unittest.TestCase):
    def test_nwn_crunch_makes_a_bioware_dxt5_twin_of_the_icon(self):
        import struct
        from PIL import Image
        from tools.itemkit.native import nwn_dds
        with tempfile.TemporaryDirectory() as folder:
            for size in ((32, 128), (32, 96)):                     # a stock canvas, and a bare 1x3 footprint
                tga = Path(folder)/f'icon{size[1]}.tga'; target = tga.with_suffix('.dds')
                image = Image.new('RGBA', size, (0, 0, 0, 0)); image.paste((200, 40, 40, 255), (8, 8, 24, size[1] - 8)); image.save(tga)
                converter = nwn_dds(tga, target)
                data = target.read_bytes()
                self.assertEqual(struct.unpack_from('<3I', data), (*size, 4)); self.assertNotEqual(data[:4], b'DDS ')
                self.assertEqual(converter['sha256'], '6aabe212ee8a4a5c166801c3c7830239e3eb15910f2743232c33666bc91aa46c')
                with self.assertRaisesRegex(ValueError, 'exists'): nwn_dds(tga, target)


class DriverFlagTests(unittest.TestCase):
    def test_replace_stock_is_an_explicit_contract_flag(self):
        from tools.itemkit.drive import parser
        self.assertFalse(parser().parse_args(['contract', 'club', 'sr4-x-1', '--wave', 'w']).replace_stock)
        self.assertTrue(parser().parse_args(['contract', 'club', 'sr4-x-1', '--wave', 'w', '--replace-stock']).replace_stock)


class PublishedNamesTests(unittest.TestCase):
    def test_the_current_srn_weapon_listing_is_held(self):
        from tools.itemkit.family_contract import published_names
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(published_names(folder), set())
            (Path(folder)/'srn_weapon').mkdir(); (Path(folder)/'srn_weapon/WSWLS_B_091.MDL').write_bytes(b'x')
            self.assertEqual(published_names(folder), {'wswls_b_091.mdl'})


if __name__ == '__main__':
    unittest.main()
