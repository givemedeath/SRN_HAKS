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
MODEL = 'newmodel t_t01\nnode trimesh t_t01wall\n  bitmap tower_wall\n  materialname tower_wall\nendnode\nnode aabb t_t01walk\n  verts 1\n    0 0 0\nendnode\ndonemodel t_t01\n'
COPY = {'terrain': 'Tower_2', 'from': 'Tower', 'display': 'Flats', 'models': {'t_t01': 'n_t01', 't_t02': 'n_t02'}, 'groups': {'Tower_Roof': 'Flats_Roof'},
        'textures': {'tower_wall': 'flat_wall'}}
PALETTE = {'__data_type': 'ITP ', 'MAIN': {'type': 'list', 'value': [
    {'ID': {'type': 'byte', 'value': 0}, 'LIST': {'type': 'list', 'value': [{'NAME': {'type': 'cexostring', 'value': 'Tower 1, Roof'}, 'RESREF': {'type': 'resref', 'value': 't_t02'}}]}},
    {'ID': {'type': 'byte', 'value': 2}, 'LIST': {'type': 'list', 'value': [{'NAME': {'type': 'cexostring', 'value': 'Tower 1\r\n'}, 'RESREF': {'type': 'resref', 'value': 'tower'}}]}}]}}


class TerrainTests(unittest.TestCase):
    def test_a_model_takes_its_new_name_in_every_node_and_its_textures_are_renamed(self):
        made = terrain.retextured(terrain.renamed(MODEL, {'t_t01': 'n_t01'}), {'tower_wall': 'flat_wall'})
        self.assertNotIn('t_t01', made); self.assertIn('node trimesh n_t01wall', made); self.assertIn('bitmap flat_wall', made); self.assertIn('materialname flat_wall', made)
        self.assertEqual(inventory.walk_hash(terrain.renamed(made, {'n_t01': 't_t01'})), inventory.walk_hash(MODEL))
        own = MODEL.replace('bitmap tower_wall', 'bitmap t_t01_wall')  # a texture named after its model keeps its name unless `textures` renames it
        self.assertIn('bitmap t_t01_wall', terrain.renamed(own, {'t_t01': 'n_t01'}))
        self.assertIn('bitmap flat_t01', terrain.retextured(terrain.renamed(own, {'t_t01': 'n_t01'}), {'t_t01_wall': 'flat_t01'}))

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
        with self.assertRaisesRegex(ValueError, 'no tile of Tower is t_a01'):  # nor a model of another terrain
            terrain.copied_set(SET, [{**COPY, 'models': {**COPY['models'], 't_a01': 'n_a01'}}])
        for copies in ([COPY, COPY], [{**COPY, 'terrain': 'TOWER'}]):  # a terrain name is the set's once, in any case
            with self.assertRaisesRegex(ValueError, 'has a terrain (Tower_2|TOWER) already'):
                terrain.copied_set(SET, copies)
        with self.assertRaisesRegex(ValueError, 'no tile of the set has a corner of Tower'):  # a terrain no tile uses
            terrain.copied_set(SET.replace('Tower\r\n', 'Brick\r\n').replace('Name=Ground\r\n\r\n[TERRAIN1]\r\nName=Brick', 'Name=Ground\r\n\r\n[TERRAIN1]\r\nName=Tower'), [{**COPY, 'models': {}, 'groups': {}}])
        with self.assertRaisesRegex(ValueError, 'names groups that hold none of its tiles: Tower_Rof'):
            terrain.copied_set(SET, [{**COPY, 'groups': {**COPY['groups'], 'Tower_Rof': 'Flats_Rof'}}])
        bare = SET[:SET.index('[GROUP0]')].replace('[GROUPS]\r\nCount=1', '[GROUPS]\r\nCount=0')  # a set with no groups
        made, _ = terrain.copied_set(bare, [{**COPY, 'groups': {}}]); self.assertEqual(inventory.read_set(made)['groups'], [])
        lowered, _ = terrain.copied_set(SET.replace('TopLeft=Tower\r\nTopRight=Ground', 'TopLeft=tower\r\nTopRight=Ground'), [COPY])  # a corner names its terrain in any case
        self.assertEqual(inventory.read_set(lowered)['tiles'][3]['corners'], ['Tower_2', 'Ground', 'Ground', 'Ground'])
        blank = SET.replace('Columns=1\r\nTile0=2', 'Columns=2\r\nTile0=2\r\nTile1=-1')  # a group with a blank cell is the terrain's still
        self.assertEqual(inventory.read_set(terrain.copied_set(blank, [COPY])[0])['groups'][1], {'name': 'Flats_Roof', 'tiles': [4, -1]})

    def test_the_edge_table_gains_the_source_rows_for_the_copy(self):
        rows = terrain.copied_edge(EDGE, [COPY]).split('\r\n')
        self.assertEqual(rows[-2].split(), ['2', 'Tower_2', '****', 'Tower_2', '0', 'n_t02']); self.assertEqual(len([row for row in rows if row.strip()]), 5)  # the header, three rows
        self.assertEqual(terrain.copied_edge(EDGE.replace('Tower **** Tower', 'TOWER **** tower'), [COPY]).split('\r\n')[-2].split()[1:4], ['Tower_2', '****', 'Tower_2'])  # read in any case

    def test_the_palette_gains_the_copy_s_entries_and_takes_descriptive_names(self):
        made = terrain.palette(PALETTE, [COPY], {'Tower 1': 'Stone Tower'})
        features, terrains = (category['LIST']['value'] for category in made['MAIN']['value'])
        self.assertEqual([(entry['RESREF']['value'], entry['NAME']['value']) for entry in features], [('t_t02', 'Stone Tower, Roof'), ('n_t02', 'Flats, Roof')])
        self.assertEqual([(entry['RESREF']['value'], entry['NAME']['value']) for entry in terrains], [('tower', 'Stone Tower'), ('tower_2', 'Flats')])
        self.assertEqual(PALETTE['MAIN']['value'][1]['LIST']['value'][0]['NAME']['value'], 'Tower 1\r\n')  # the document given is left as it was
        talked = {'__data_type': 'ITP ', 'MAIN': {'type': 'list', 'value': [{'ID': {'type': 'byte', 'value': 0}, 'LIST': {'type': 'list', 'value': [
            {'STRREF': {'type': 'dword', 'value': 63000}, 'RESREF': {'type': 'resref', 'value': 't_t02'}}]}}]}}  # named by the talk table
        copied = terrain.palette(talked, [COPY], {})['MAIN']['value'][0]['LIST']['value'][1]
        self.assertEqual((copied['NAME']['value'], 'STRREF' in copied), ('Flats', False))

    def test_copy_writes_the_models_the_set_the_edge_table_and_the_palette(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary); own = repo / 'srn_t_tst'; (repo / 'srn_t_common').mkdir(); (repo / 'srn_2da').mkdir(); own.mkdir()
            (own / 'tst.set').write_bytes(SET.encode('cp1252')); (repo / 'srn_2da' / 'tst_edge.2da').write_bytes(EDGE.encode('cp1252')); (own / 'tstpalstd.itp').write_bytes(b'ITP ')
            (own / 't_t01.mdl').write_text(MODEL); (own / 't_t01.wok').write_text('node aabb t_t01walk\n'); (own / 't_t02.mdl').write_text(MODEL.replace('t_t01', 't_t02')); (own / 't_t02.wok').write_text('node aabb t_t02walk\n')
            (repo / 'srn_t_other').mkdir(); (repo / 'srn_t_other' / 'ground_x.mdl').write_text(MODEL); (own / 't_a01.mdl').write_text(MODEL.replace('t_t01', 't_a01'))

            def gff(arguments):
                if '-k' in arguments:
                    return json.dumps(PALETTE).encode()
                Path(arguments[-1]).write_text(Path(arguments[1]).read_text(encoding='utf-8')); return b''
            spec = {'tileset': 'tst', 'provenance': 'Towers', 'copies': [COPY]}
            told = terrain.copy(repo, spec, repo / 'out', gff=gff, source='specs/towers.json')
            self.assertEqual(told['Tower_2'], {'models': 2, 'tiles': [3, 4]})
            self.assertEqual(sorted(path.name for path in (repo / 'out').iterdir()), ['made-from.json', 'n_t01.mdl', 'n_t01.wok', 'n_t02.mdl', 'n_t02.wok', 'tst.set', 'tst_edge.2da', 'tstpalstd.itp'])
            self.assertEqual((repo / 'out' / 'n_t01.wok').read_text(), 'node aabb n_t01walk\n')
            record = json.loads((repo / 'out' / 'made-from.json').read_text(encoding='utf-8'))
            self.assertEqual((sorted(record['from']), record['textures']), (['tst.set', 'tst_edge.2da', 'tstpalstd.itp'], ['flat_wall']))
            self.assertEqual([(entry['terrain'], entry['tiles'], entry['models'], entry['source']) for entry in record['catalog']['terrainTiles']], [('Tower_2', [3, 4], ['n_t01', 'n_t02'], 'specs/towers.json')])
            self.assertEqual([(entry['group'], entry['name'], entry['rows'], entry['columns'], entry['tiles'], entry['models']) for entry in record['catalog']['tileGroups']], [(1, 'Flats_Roof', 1, 1, [4], ['n_t02'])])
            (repo / 'out' / 'n_t09.mdl').write_text(MODEL); (repo / 'out' / 'oth.set').write_text('')  # left by an earlier run
            with self.assertRaisesRegex(ValueError, 'files of an earlier run, which apply would install: n_t09.mdl, oth.set'):
                terrain.copy(repo, spec, repo / 'out', gff=gff)
            (repo / 'out' / 'n_t09.mdl').unlink(); (repo / 'out' / 'oth.set').unlink()
            with self.assertRaisesRegex(ValueError, 'broken'):  # a run that fails part way leaves no record of an earlier one
                terrain.copy(repo, spec, repo / 'out', gff=lambda arguments: (_ for _ in ()).throw(ValueError('broken')))
            self.assertFalse((repo / 'out' / 'made-from.json').exists())
            terrain.copy(repo, spec, repo / 'out', gff=gff)
            with self.assertRaisesRegex(ValueError, 'no tile of Tower is t_a01'):  # a refused run leaves the earlier record
                terrain.copy(repo, {**spec, 'copies': [{**COPY, 'models': {**COPY['models'], 't_a01': 'n_a01'}}]}, repo / 'out', gff=gff)
            self.assertTrue((repo / 'out' / 'made-from.json').exists())
            for broken, message in (({**spec, 'provenance': ''}, 'names its section of PROVENANCE.md'), ({**spec, 'copies': [{**COPY, 'terrain': 'Tower 2'}]}, 'at most 16 letters')):
                with self.assertRaisesRegex(ValueError, message):
                    terrain.copy(repo, broken, repo / 'again', gff=gff)
            for broken, message in (({**COPY, 'models': {'t_t01': 'n_t01'}}, 'names no new model for t_t02'),  # each refused before a file is written
                                    ({**COPY, 'models': {**COPY['models'], 't_a01': 'n_a01'}}, 'no tile of Tower is t_a01'),
                                    ({**COPY, 'models': {'t_t01': 'n_t01', 't_t02': 'ground_x'}}, 'A pack holds ground_x already'),
                                    ({**COPY, 'models': {'t_t01': 'n_t01', 't_t02': 'n_t01'}}, 'more than one model the name n_t01'),
                                    ({**COPY, 'models': {'t_t01': 'n_t01', 't_t02': 'n t02'}}, 'n t02: a model is named by a resref'),
                                    ({**COPY, 'textures': {**COPY['textures'], 'Tower_Wal': 'flat_wal'}}, 'renames textures none of its models draws: tower_wal')):
                with self.assertRaisesRegex(ValueError, message):
                    terrain.copy(repo, {**spec, 'copies': [broken]}, repo / 'refused', gff=gff)
                self.assertEqual(list((repo / 'refused').iterdir()), [])
            edged = EDGE + '2  Tower **** Ground 0 t_z01\r\n3  Ground **** Tower 0 tcn01_z15_01\r\n'  # an edge tile of this project's beside the source, and one of the game's
            (repo / 'srn_2da' / 'tst_edge.2da').write_bytes(edged.encode('cp1252')); (own / 't_z01.mdl').write_text(MODEL.replace('t_t01', 't_z01'))
            with self.assertRaisesRegex(ValueError, 'the edge table lays t_z01 beside Tower: the copy names a new model for each'):
                terrain.copy(repo, spec, repo / 'refused', gff=gff)
            with self.assertRaisesRegex(ValueError, 'no edge row of Tower lays t_a01'):
                terrain.copy(repo, {**spec, 'copies': [{**COPY, 'edges': {'t_z01': 'n_z01', 't_a01': 'n_a01'}}]}, repo / 'refused', gff=gff)
            told = terrain.copy(repo, {**spec, 'copies': [{**COPY, 'edges': {'t_z01': 'n_z01'}}]}, repo / 'edged', gff=gff)
            self.assertEqual((told['Tower_2']['edges'], json.loads((repo / 'edged' / 'made-from.json').read_text(encoding='utf-8'))['edges']), (1, ['n_z01']))
            self.assertIn('bitmap flat_wall', (repo / 'edged' / 'n_z01.mdl').read_text()); self.assertFalse((repo / 'edged' / 'n_z01.wok').exists())  # an edge tile with no walkmesh keeps none
            rows = [line.split() for line in (repo / 'edged' / 'tst_edge.2da').read_text(encoding='cp1252').splitlines()[3:] if line.strip()]
            self.assertEqual([row[1:] for row in rows[4:]], [['Tower_2', '****', 'Tower_2', '0', 'n_t02'], ['Tower_2', '****', 'Ground', '0', 'n_z01'], ['Ground', '****', 'Tower_2', '0', 'tcn01_z15_01']])
            (repo / 'srn_2da' / 'tst_edge.2da').write_bytes(EDGE.encode('cp1252')); (own / 't_z01.mdl').unlink()
            (own / 't_t02.wok').unlink()
            with self.assertRaisesRegex(ValueError, 'srn_t_tst has no t_t02.wok'):
                terrain.copy(repo, spec, repo / 'refused', gff=gff)
            self.assertEqual(list((repo / 'refused').iterdir()), [])
            with self.assertRaisesRegex(ValueError, 'A pack holds n_t01 already'):
                (own / 'n_t01.mdl').write_text(MODEL); terrain.copy(repo, spec, repo / 'again', gff=gff)


if __name__ == '__main__':
    unittest.main()
