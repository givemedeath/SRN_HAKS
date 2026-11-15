"""Stock appearance slots: a new design takes a base-game slot only on the explicit opt-in, once 1..25 hold no free one."""
import json
from pathlib import Path
import sys
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


@unittest.skipUnless(sys.platform == 'win32', 'NWN Crunch is vendored for Windows x64 only')
class DdsTwinTests(unittest.TestCase):
    def test_nwn_crunch_makes_bioware_twins_of_icons_and_diffuse(self):
        import struct
        from PIL import Image
        import sys
        from tools.headkit.common import ROOT
        from tools.itemkit.native import dds_converter, nwn_dds
        sys.path.insert(0, str(ROOT/'tools/phenotypes')); import tool_runtime
        from tools.shared_tools import resolve_tool
        # The temporary TGAs must not be registered in the worktree's shared consumer record.
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(tool_runtime, 'register_run', lambda *a, **k: None):
            # A stock icon canvas and a bare 1x3 footprint (DXT5), and a diffuse (DXT1).
            for size, mode, compression, channels in (((32, 128), 'RGBA', 'DXT5', 4), ((32, 96), 'RGBA', 'DXT5', 4), ((256, 256), 'RGB', 'DXT1', 3)):
                tga = Path(folder)/f'image{size[1]}.tga'; target = tga.with_suffix('.dds')
                image = Image.new(mode, size, (0, 0, 0, 0)[:len(mode)]); image.paste((200, 40, 40, 255)[:len(mode)], (8, 8, 24, size[1] - 8)); image.save(tga)
                nwn_dds(tga, target, compression, crunch=dds_converter([tga]) if channels == 3 else None)
                data = target.read_bytes()
                self.assertEqual(struct.unpack_from('<3I', data), (*size, channels)); self.assertNotEqual(data[:4], b'DDS ')
                with self.assertRaisesRegex(ValueError, 'exists'): nwn_dds(tga, target)
            self.assertEqual(Path(dds_converter([tga])), Path(resolve_tool('crunch')['path']))      # the lock-pinned converter


class DdsHeaderTests(unittest.TestCase):
    def test_a_whole_mip_bioware_dds_the_size_of_its_tga(self):
        from tools.itemkit.dds import bioware_dds, twin_problem
        from tools.itemkit.test_publish import bioware_dds as make, tga
        self.assertEqual(bioware_dds(make(32, 128)), (32, 128, 4, 8))
        self.assertEqual(bioware_dds(make(1024, 1024, 3)), (1024, 1024, 3, 11))
        self.assertEqual(bioware_dds(make(32, 128)[:20 + 4096]), (32, 128, 4, 1))      # a top level alone is whole
        self.assertIsNone(twin_problem(make(32, 96), tga(32, 96)))
        self.assertIn('differs from its TGA', twin_problem(make(32, 64), tga(32, 96)))
        for bad, message in ((make(32, 128)[:-1], 'whole mip chain'), (b'DDS ' + make(32, 128)[4:], 'standard DDS'),
                             (make(32, 128) + b'x', 'whole mip chain'), (b'\x20\0\0\0' * 2 + b'\x02\0\0\0' + bytes(8), 'Unsupported')):
            with self.assertRaisesRegex(ValueError, message): bioware_dds(bad)


class PackageNamesTests(unittest.TestCase):
    def test_a_new_package_has_one_dds_twin_per_tga_and_an_old_one_none(self):
        from tools.itemkit.native import package_names_ok
        old = ['wswls_b_101.mdl', 'iwswls_b_101.tga', 'sr12345678_10.tga']
        new = old + ['iwswls_b_101.dds', 'sr12345678_10.dds']
        self.assertTrue(package_names_ok(old, False)); self.assertTrue(package_names_ok(new, True))
        self.assertFalse(package_names_ok(old, True)); self.assertFalse(package_names_ok(new, False))
        self.assertFalse(package_names_ok(new + ['iwswls_m_101.dds'], True)); self.assertFalse(package_names_ok(new + ['x.mtr'], True))


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

    def test_main_is_read_when_the_checkout_lags_it(self):
        import subprocess
        from tools.itemkit.family_contract import published_names
        with tempfile.TemporaryDirectory() as folder:
            git = lambda *a: subprocess.run(['git', '-C', folder, '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', *a],
                                            check=True, capture_output=True)
            git('init', '-q', '-b', 'main'); (Path(folder)/'srn_weapon').mkdir()
            (Path(folder)/'srn_weapon/wswls_t_081.mdl').write_bytes(b'published on main'); git('add', '.'); git('commit', '-q', '-m', 'main')
            git('switch', '-q', '-c', 'behind', 'HEAD'); git('rm', '-q', 'srn_weapon/wswls_t_081.mdl'); git('commit', '-q', '-m', 'lagging')
            self.assertFalse((Path(folder)/'srn_weapon/wswls_t_081.mdl').exists())
            self.assertIn('wswls_t_081.mdl', published_names(folder))
            # An inherited GIT_DIR naming another repository does not redirect the lookup.
            with tempfile.TemporaryDirectory() as other, mock.patch.dict('os.environ', {'GIT_DIR': str(Path(other)/'.git')}):
                self.assertIn('wswls_t_081.mdl', published_names(folder))
            # Without git, the checkout's own listing stands.
            (Path(folder)/'srn_weapon').mkdir(exist_ok=True); (Path(folder)/'srn_weapon/kept.tga').write_bytes(b'x')
            with mock.patch('subprocess.run', side_effect=FileNotFoundError('git')):
                self.assertEqual(published_names(folder), {'kept.tga'})


if __name__ == '__main__':
    unittest.main()
