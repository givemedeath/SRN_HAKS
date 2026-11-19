"""A building terrain copied under a name of its own: the models, the set file, the edge table and the palette."""
import json
import tempfile
import unittest
from pathlib import Path

from tools.tilekit import inventory, terrain

SET = ('[GENERAL]\r\nDefault=Ground\r\n\r\n[TERRAIN TYPES]\r\nCount=2\r\n\r\n[TERRAIN0]\r\nName=Ground\r\n\r\n[TERRAIN1]\r\nName=Tower\r\n\r\n'
       '[TILES]\r\nCount=3\r\n\r\n[TILE0]\r\nModel=t_a01\r\nTopLeft=Ground\r\nTopRight=Ground\r\nBottomLeft=Ground\r\nBottomRight=Ground\r\n\r\n'
       '[TILE1]\r\nModel=t_t01\r\nTopLeft=Tower\r\nTopRight=Ground\r\nBottomLeft=Ground\r\nBottomRight=Ground\r\nDoors=1\r\n\r\n[TILE1DOOR0]\r\nType=0\r\nX=1.0\r\n\r\n'
       '[TILE2]\r\nModel=T_T02\r\nTopLeft=Tower\r\nTopRight=Tower\r\nBottomLeft=Tower\r\nBottomRight=Tower\r\n\r\n'
       '[GROUPS]\r\nCount=1\r\n\r\n[GROUP0]\r\nName=Tower_Roof\r\nRows=1\r\nColumns=1\r\nTile0=2\r\n')
EDGE = '2DA V2.0\r\n\r\n   Corner1 Edge Corner2 Height Model\r\n0  Tower **** Tower 0 t_t02\r\n1  Ground **** Ground 0 t_a01\r\n'
MODEL = 'newmodel t_t01\nnode trimesh t_t01wall\n  bitmap tower_wall\nendnode\nnode aabb t_t01walk\n  verts 1\n    0 0 0\nendnode\ndonemodel t_t01\n'
COPY = {'terrain': 'Tower_2', 'from': 'Tower', 'display': 'Flats', 'models': {'t_t01': 'n_t01', 't_t02': 'n_t02'}, 'groups': {'Tower_Roof': 'Flats_Roof'},
        'textures': {'tower_wall': 'flat_wall'}}
PALETTE = {'__data_type': 'ITP ', 'MAIN': {'type': 'list', 'value': [
    {'ID': {'type': 'byte', 'value': 0}, 'LIST': {'type': 'list', 'value': [{'NAME': {'type': 'cexostring', 'value': 'Tower 1, Roof'}, 'RESREF': {'type': 'resref', 'value': 't_t02'}}]}},
    {'ID': {'type': 'byte', 'value': 2}, 'LIST': {'type': 'list', 'value': [{'NAME': {'type': 'cexostring', 'value': 'Tower 1\r\n'}, 'RESREF': {'type': 'resref', 'value': 'tower'}}]}}]}}


class TerrainTests(unittest.TestCase):
    def test_a_model_takes_its_new_name_in_every_node_and_its_textures_are_renamed(self):
        made = terrain.retextured(terrain.renamed(MODEL, {'t_t01': 'n_t01'}), {'tower_wall': 'flat_wall'})
        self.assertNotIn('t_t01', made); self.assertIn('node trimesh n_t01wall', made); self.assertIn('bitmap flat_wall', made)
        self.assertEqual(inventory.walk_hash(terrain.renamed(made, {'n_t01': 't_t01'})), inventory.walk_hash(MODEL))

    def test_the_set_gains_the_terrain_its_tiles_with_their_doors_and_its_group(self):
        text, numbers = terrain.copied_set(SET, [COPY])
        laid = inventory.read_set(text)
        self.assertEqual((laid['terrains'], numbers), (['Ground', 'Tower', 'Tower_2'], {'Tower_2': {1: 3, 2: 4}}))
        self.assertEqual([(tile['number'], tile['model'], tile['corners']) for tile in laid['tiles'][3:]],
                         [(3, 'n_t01', ['Tower_2', 'Ground', 'Ground', 'Ground']), (4, 'n_t02', ['Tower_2'] * 4)])
        self.assertEqual(laid['groups'][1], {'name': 'Flats_Roof', 'tiles': [4]}); self.assertIn('[TILE3DOOR0]\r\nType=0\r\nX=1.0', text)
        self.assertIn('[TILES]\r\nCount=5', text); self.assertIn('[TERRAIN TYPES]\r\nCount=3', text); self.assertTrue(text.startswith(SET[:SET.index('[TERRAIN TYPES]')]))
        self.assertIn('[TERRAIN1]\r\nName=Tower\r\n\r\n[TERRAIN2]\r\nName=Tower_2\r\n\r\n[TILES]', text)
        with self.assertRaisesRegex(ValueError, 'names no new model for t_t02'):
            terrain.copied_set(SET, [{**COPY, 'models': {'t_t01': 'n_t01'}}])

    def test_the_edge_table_gains_the_source_rows_for_the_copy(self):
        rows = terrain.copied_edge(EDGE, [COPY]).split('\r\n')
        self.assertEqual(rows[-2].split(), ['2', 'Tower_2', '****', 'Tower_2', '0', 'n_t02']); self.assertEqual(len([row for row in rows if row.strip()]), 5)  # the header, three rows

    def test_the_palette_gains_the_copy_s_entries_and_takes_descriptive_names(self):
        made = terrain.palette(PALETTE, [COPY], {'Tower 1': 'Stone Tower'})
        features, terrains = (category['LIST']['value'] for category in made['MAIN']['value'])
        self.assertEqual([(entry['RESREF']['value'], entry['NAME']['value']) for entry in features], [('t_t02', 'Stone Tower, Roof'), ('n_t02', 'Flats, Roof')])
        self.assertEqual([(entry['RESREF']['value'], entry['NAME']['value']) for entry in terrains], [('tower', 'Stone Tower'), ('tower_2', 'Flats')])
        self.assertEqual(PALETTE['MAIN']['value'][1]['LIST']['value'][0]['NAME']['value'], 'Tower 1\r\n')  # the document given is left as it was

    def test_copy_writes_the_models_the_set_the_edge_table_and_the_palette(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary); own = repo / 'srn_t_tst'; (repo / 'srn_t_common').mkdir(); (repo / 'srn_2da').mkdir(); own.mkdir()
            (own / 'tst.set').write_bytes(SET.encode('cp1252')); (repo / 'srn_2da' / 'tst_edge.2da').write_bytes(EDGE.encode('cp1252')); (own / 'tstpalstd.itp').write_bytes(b'ITP ')
            (own / 't_t01.mdl').write_text(MODEL); (own / 't_t01.wok').write_text('node aabb t_t01walk\n'); (own / 't_t02.mdl').write_text(MODEL.replace('t_t01', 't_t02'))

            def gff(arguments):
                if '-k' in arguments:
                    return json.dumps(PALETTE).encode()
                Path(arguments[-1]).write_text(Path(arguments[1]).read_text(encoding='utf-8')); return b''
            told = terrain.copy(repo, {'tileset': 'tst', 'copies': [COPY]}, repo / 'out', gff=gff)
            self.assertEqual(told['Tower_2'], {'models': 2, 'tiles': [3, 4]})
            self.assertEqual(sorted(path.name for path in (repo / 'out').iterdir()), ['n_t01.mdl', 'n_t01.wok', 'n_t02.mdl', 'tst.set', 'tst_edge.2da', 'tstpalstd.itp'])
            self.assertEqual((repo / 'out' / 'n_t01.wok').read_text(), 'node aabb n_t01walk\n')
            with self.assertRaisesRegex(ValueError, 'A pack holds n_t01.mdl already'):
                (own / 'n_t01.mdl').write_text(MODEL); terrain.copy(repo, {'tileset': 'tst', 'copies': [COPY]}, repo / 'again', gff=gff)


if __name__ == '__main__':
    unittest.main()
