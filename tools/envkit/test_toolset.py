"""The Toolset check's module, what is read back from a saved one, and the junction that must go before its folder."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.armorkit.client_fixture import field

from . import toolset


def area(tileset, width, tiles, doors=()):
    are = {'Tileset': field('resref', tileset), 'Width': field('int', width), 'Height': field('int', len(tiles) // width),
           'Tile_List': field('list', [{'Tile_ID': field('int', tile), 'Tile_Orientation': field('int', turn)} for tile, turn in tiles])}
    return are, {'Door List': field('list', [{'Appearance': field('dword', 58), 'X': field('float', x), 'Y': field('float', y), 'Bearing': field('float', -3.14),
                                              'Tag': field('cexostring', 'Door'), 'Locked': field('byte', 0)} for x, y in doors])}


class ToolsetTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup); self.root = Path(self.folder.name)

    def test_the_module_has_one_plain_area_for_each_tileset_and_the_projects_packs(self):
        made = toolset.documents(); ifo = made['module.ifo']
        for name in ('ektdg_a', 'ektud_a'):
            self.assertTrue({name + '.are', name + '.git', name + '.gic'} <= set(made))  # the Toolset opens no area without all three
        self.assertEqual([row['Area_Name']['value'] for row in ifo['Mod_Area_list']['value']], ['ektdg_a', 'ektud_a']); self.assertEqual(ifo['Mod_Entry_Area']['value'], 'ektdg_a')
        self.assertEqual([row['Mod_Hak']['value'] for row in ifo['Mod_HakList']['value']], list(toolset.HAKS)); self.assertEqual(ifo['Mod_CustomTlk']['value'], 'srn')
        self.assertEqual((ifo['Mod_Entry_X']['value'], ifo['Mod_Entry_Y']['value']), toolset.START)  # a corner tile: the Toolset refuses to save with the start on a painted-over tile
        suburbs = made['ektud_a.are']
        self.assertEqual((suburbs['Tileset']['value'], {laid['Tile_ID']['value'] for laid in suburbs['Tile_List']['value']}, len(suburbs['Tile_List']['value'])), ('udp1', {52}, 64))
        self.assertEqual(made['ektdg_a.gic']['Door List']['value'], [])
        one = toolset.documents(('udp1',)); self.assertEqual(one['module.ifo']['Mod_Entry_Area']['value'], 'ektud_a'); self.assertNotIn('ektdg_a.are', one)
        with self.assertRaisesRegex(ValueError, 'A check area is laid in'):
            toolset.documents(('ttr01',))

    def test_a_saved_module_is_read_for_the_group_tiles_laid_and_the_doors_made(self):
        tiles = [(0, 0)] * 16; tiles[5], tiles[6], tiles[9] = (201, 1), (202, 1), (7, 2)  # the Toolset repaints the tiles round a group
        told = toolset.report({'ektdg_a': area('dgt04', 4, tiles, doors=[(15.0, 20.0)]), 'ektud_a': area('udp1', 4, [(52, 0)] * 16)}, {'dgt04': 200, 'udp1': None})
        self.assertEqual(told['ektdg_a']['groupTiles'], [{'tile': 201, 'column': 1, 'row': 1, 'turn': 1}, {'tile': 202, 'column': 2, 'row': 1, 'turn': 1}])
        self.assertEqual((told['ektdg_a']['otherTiles'], told['ektdg_a']['size']), ({0: 13, 7: 1}, [4, 4]))
        self.assertEqual(told['ektdg_a']['doors'], [{'Appearance': 58, 'X': 15.0, 'Y': 20.0, 'Bearing': -3.14, 'Tag': 'Door'}])
        self.assertEqual((told['ektud_a']['groupTiles'], told['ektud_a']['doors']), ([], []))  # a tileset with no envkit tiles has no group tiles

    def test_a_tilesets_first_envkit_tile_is_found_in_its_set_file(self):
        text = '[TILES]\r\nCount=3\r\n[TILE0]\r\nModel=tdg01_a01_01\r\n[TILE1]\r\nModel=ek_ss_shop_t00\r\n[TILE2]\r\nModel=ek_ss_shop_t01\r\n[TILE1DOOR0]\r\nType=58\r\n'
        self.assertEqual(toolset.first_envkit_tile(text), 1); self.assertIsNone(toolset.first_envkit_tile(text.replace('ek_', 'tk_')))

    def test_prepare_wants_a_fresh_folder_and_the_built_packs(self):
        built = self.root / 'output'; built.mkdir(); (self.root / 'user').mkdir()
        with self.assertRaisesRegex(ValueError, 'A fresh user folder'):
            toolset.prepare(self.root / 'user', built)
        (built / 'srn_2da.hak').write_bytes(b'')
        with self.assertRaisesRegex(ValueError, 'The built packs are needed.*srn_t_dgt04.*srn.tlk'):
            toolset.prepare(self.root / 'fresh', built)
        self.assertFalse((self.root / 'fresh').exists())

    @unittest.skipUnless(os.name == 'nt', 'junctions are made with mklink')
    def test_retiring_takes_the_junction_away_and_leaves_the_packs(self):
        built, user = self.root / 'output', self.root / 'user'; built.mkdir(); user.mkdir(); (built / 'srn_2da.hak').write_bytes(b'pack')
        self.assertFalse(toolset.retire(user))  # nothing to take away
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(user / 'hak'), str(built)], check=True, capture_output=True)
        self.assertTrue((user / 'hak' / 'srn_2da.hak').is_file()); self.assertTrue(toolset.retire(user))
        self.assertFalse(os.path.lexists(user / 'hak')); self.assertEqual((built / 'srn_2da.hak').read_bytes(), b'pack')
        (user / 'hak').mkdir(); (user / 'hak' / 'mine.hak').write_bytes(b'kept')
        with self.assertRaisesRegex(ValueError, 'a real folder here'):
            toolset.retire(user)
        self.assertTrue((user / 'hak' / 'mine.hak').is_file())


if __name__ == '__main__':
    unittest.main()
