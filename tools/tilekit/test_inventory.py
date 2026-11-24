"""The tileset inventory: what the set and edge table name, surface by texture, copies and other users of a name, and
the walkmesh hashes a restyle must leave alone."""
import contextlib
import hashlib
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path

from . import inventory
from . import __main__ as command


def main(arguments):
    """The command line, with what it prints kept off the test run's own output."""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return command.main(arguments)

SET = '''[GENERAL]
Name=TST01
Default=Ground

[TERRAIN TYPES]
Count=2

[TERRAIN0]
Name=Ground

[TERRAIN1]
Name=Tower

[CROSSER TYPES]
Count=1

[CROSSER0]
Name=Fence

[TILES]
Count=3

[TILE0]
Model=tst01_a01_01
TopLeft=Ground
TopRight=Ground
BottomLeft=Ground
BottomRight=Ground
Top=
Right=Fence
Bottom=
Left=
Doors=0

[TILE1]
Model=TST01_B01_01
TopLeft=Tower
TopRight=Ground
BottomLeft=Ground
BottomRight=Ground
Top=
Right=
Bottom=
Left=
Doors=1

[TILE1DOOR0]
Type=0
X=1.0

[TILE2]
Model=ek_new
TopLeft=Ground
TopRight=Ground
BottomLeft=Ground
BottomRight=Ground
Doors=0

[GROUPS]
Count=1

[GROUP0]
Name=Yard
Rows=1
Columns=2
Tile0=0
Tile1=1
'''.replace('\n', '\r\n')

EDGE = '''2DA V2.0

     Corner1   Edge   Corner2   Height   Model
0    Ground    ****   Ground    0        tst01_a01_01
1    Tower     ****   Tower     0        TST01_Z01_01
2    Tower     ****   ****      0        stock_z02_01
'''


def model(name, nodes):
    """An uncompiled model of `nodes`: (kind, node name, texture, rendered, side) each a square of `side` metres."""
    lines = [f'newmodel {name}', 'classification TILE', f'beginmodelgeom {name}', f'node dummy {name}', '  parent NULL', 'endnode']
    for kind, node, texture, rendered, side in nodes:
        lines += [f'node {kind} {node}', f'  parent {name}', f'  bitmap {texture}', f'  render {int(rendered)}', '  verts 4',
                  '    0.0 0.0 0.0', f'    {side} 0.0 0.0', f'    {side} {side} 0.0', f'    0.0 {side} 0.0', '  faces 2', '    0 1 2 1 0 1 2 0',
                  '    0 2 3 1 0 2 3 0', 'endnode']
    lines += [f'endmodelgeom {name}', f'newanim tiledefault {name}', '  node trimesh ghost', '    parent NULL', '  endnode', f'doneanim tiledefault {name}', f'donemodel {name}']
    return '\n'.join(lines) + '\n'


def tga(width, height):
    return bytes(12) + struct.pack('<HH', width, height) + bytes([24, 0])


class InventoryTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup); self.repo = Path(folder.name)
        own, common, table, other, prop = (self.repo / name for name in ('srn_t_tst01', 'srn_t_common', 'srn_2da', 'srn_t_oth01', 'srn_placeable'))
        for pack in (own, common, table, other, prop):
            pack.mkdir()
        (own / 'tst01.set').write_bytes(SET.encode('cp1252')); (table / 'tst01_edge.2da').write_text(EDGE)
        (own / 'tst01_a01_01.mdl').write_text(model('tst01_a01_01', [('trimesh', 'ground', 'Paving', True, 10.0), ('trimesh', 'hidden', 'secret', False, 10.0),
                                                                    ('aabb', 'walk', 'walk', True, 10.0)]))
        (own / 'tst01_a01_01.wok').write_bytes(b'walkmesh one')
        (common / 'tst01_b01_01.mdl').write_text(model('tst01_b01_01', [('trimesh', 'ground', 'paving', True, 10.0), ('trimesh', 'wall', 'brick', True, 5.0),
                                                                       ('danglymesh', 'flag', 'cloth', True, 1.0), ('trimesh', 'blank', 'NULL', True, 3.0)]))
        (own / 'tst01_z01_01.mdl').write_text(model('tst01_z01_01', [('trimesh', 'wall', 'brick', True, 5.0)]))
        (common / 'EK_New.mdl').write_bytes(b'\0\0\0\0compiled paving'); (common / 'ek_new.wok').write_bytes(b'compiled walk')  # a file in any case is found
        (own / 'tst01_x09_01.mdl').write_text(model('tst01_x09_01', [('trimesh', 'spare', 'brick', True, 2.0)]))  # nothing names this one
        # Copies: paving twice in one pack at two sizes, brick in the door pack only, cloth nowhere (a base-game name).
        (common / 'paving.tga').write_bytes(tga(128, 64)); (common / 'paving.dds').write_bytes(struct.pack('<III', 512, 256, 3) + bytes(8))
        (prop / 'brick.dds').write_bytes(b'DDS ' + struct.pack('<III', 124, 0, 256) + struct.pack('<I', 1024) + bytes(8)); (prop / 'brick.mtr').write_text('texture0 brick\n')
        # Other users: another tileset's tile (compiled, so only its bytes can be read) and two placeables.
        (other / 'oth01.set').write_bytes(b'[TILES]\r\nCount=1\r\n\r\n[TILE0]\r\nModel=oth01_a01_01\r\n')
        (other / 'oth01_a01_01.mdl').write_bytes(b'\0\0\0\0....paving\0\0\0\0brickwork\0')
        (prop / 'plc_one.mdl').write_text('node trimesh a\n  bitmap BRICK\nendnode\n'); (prop / 'plc_two.mdl').write_text('node trimesh a\n  bitmap brick\nendnode\n')

    def test_the_set_and_edge_table_are_read_as_the_game_names_them(self):
        laid = inventory.read_set(SET)
        self.assertEqual((laid['default'], laid['terrains'], laid['crossers']), ('Ground', ['Ground', 'Tower'], ['Fence']))
        self.assertEqual([(tile['number'], tile['model'], tile['doors']) for tile in laid['tiles']], [(0, 'tst01_a01_01', 0), (1, 'tst01_b01_01', 1), (2, 'ek_new', 0)])
        self.assertEqual((laid['tiles'][1]['corners'], laid['tiles'][0]['crossers']), (['Tower', 'Ground', 'Ground', 'Ground'], ['', 'Fence', '', '']))
        self.assertEqual(laid['groups'], [{'name': 'Yard', 'tiles': [0, 1]}])  # a door's section is no tile, Rows and Columns are no tile numbers
        self.assertEqual(inventory.edge_models(EDGE), (['stock_z02_01', 'tst01_a01_01', 'tst01_z01_01'], 3))
        self.assertEqual(inventory.edge_models(EDGE.replace('\n', '\nDEFAULT: ****\n', 1)), inventory.edge_models(EDGE))  # a table that states its default
        with self.assertRaisesRegex(ValueError, 'names no tile'):
            inventory.read_set('[GENERAL]\nName=X\n')
        with self.assertRaisesRegex(ValueError, 'no Model column'):
            inventory.edge_models('2DA V2.0\n\n  Corner1 Edge\n0 a b\n')

    def test_surface_counts_only_rendered_textured_mesh_faces(self):
        told = inventory.surfaces(model('m', [('trimesh', 'a', 'Wall', True, 2.0), ('trimesh', 'b', 'wall', True, 1.0), ('trimesh', 'c', 'off', False, 9.0),
                                              ('aabb', 'd', 'walk', True, 9.0), ('trimesh', 'e', 'NULL', True, 9.0), ('danglymesh', 'f', 'flag', True, 3.0)]))
        self.assertEqual({name: round(area, 6) for name, area in told.items()}, {'wall': 5.0, 'flag': 9.0})  # names fold to lower case; animation nodes add nothing
        self.assertTrue(inventory.compiled(b'\0\0\0\0rest')); self.assertFalse(inventory.compiled(b'# Exported'))

    def test_picture_sizes_come_from_each_header(self):
        self.assertEqual(tuple(inventory.picture_size(self.repo / 'srn_t_common' / 'paving.tga')), (128, 64))
        self.assertEqual(tuple(inventory.picture_size(self.repo / 'srn_t_common' / 'paving.dds')), (512, 256))  # BioWare DDS: width then height
        self.assertEqual(tuple(inventory.picture_size(self.repo / 'srn_placeable' / 'brick.dds')), (1024, 256))  # standard DDS: height then width
        self.assertIsNone(inventory.picture_size(self.repo / 'srn_placeable' / 'brick.mtr'))

    def test_the_inventory_orders_textures_by_surface_and_names_every_copy_and_other_user(self):
        told, walkmesh = inventory.inventory(self.repo, 'tst01')
        self.assertEqual(told['set'], {'terrains': 2, 'crossers': 1, 'tiles': 3, 'models': 3, 'groups': 1})
        self.assertEqual((told['edge'], told['forms']), ({'rows': 3, 'models': 3, 'notInSet': 2}, {'uncompiled': 3, 'compiled': 1, 'absent': 1}))
        self.assertEqual([(one['name'], one['surface'], one['models']) for one in told['textures']], [('paving', 200.0, 2), ('brick', 50.0, 2), ('cloth', 1.0, 1)])
        self.assertEqual((told['surface'], told['coverage']), (251.0, {'50': 1, '80': 2, '90': 2, '95': 2, '99': 2}))
        paving, brick, cloth = told['textures']
        self.assertEqual((paving['share'], paving['cumulative'], brick['cumulative']), (79.681, 79.681, 99.602))
        self.assertEqual(paving['copies'], [{'pack': 'srn_t_common', 'type': 'dds', 'width': 512, 'height': 256}, {'pack': 'srn_t_common', 'type': 'tga', 'width': 128, 'height': 64}])
        self.assertEqual((paving['largest'], brick['largest'], cloth['largest'], cloth['copies']), (512, 1024, None, []))
        self.assertEqual(brick['copies'], [{'pack': 'srn_placeable', 'type': 'dds', 'width': 1024, 'height': 256}, {'pack': 'srn_placeable', 'type': 'mtr'}])
        # The other tileset's compiled tile names paving; "brickwork" in it is another name. The placeables name brick, as does the model nothing names.
        self.assertEqual((paving['otherSets'], paving['otherPacks'], brick['otherSets'], brick['otherPacks']), (['oth01'], {}, [], {'srn_placeable': 2, 'srn_t_tst01': 1}))
        self.assertEqual((paving['terrains'], brick['terrains']), (['Ground', 'Tower'], ['Tower']))  # an edge tile alone gives a texture no terrain
        self.assertEqual(told['models']['tst01_b01_01'], {'pack': 'srn_t_common', 'form': 'uncompiled', 'tiles': [1], 'edge': False})
        self.assertEqual((told['models']['stock_z02_01']['form'], told['models']['ek_new']['form'], told['unnamedModels']), ('absent', 'compiled', ['tst01_x09_01']))
        self.assertEqual(sorted(walkmesh['models']), ['ek_new', 'tst01_a01_01', 'tst01_b01_01', 'tst01_z01_01'])  # an absent model is not held
        self.assertIsNotNone(walkmesh['models']['tst01_a01_01']['aabb']); self.assertIsNone(walkmesh['models']['tst01_b01_01']['aabb'])
        self.assertEqual(walkmesh['models']['ek_new'], {'wok': hashlib.sha256(b'compiled walk').hexdigest(), 'aabb': None})  # a compiled model's walkmesh is its .wok
        rows = inventory.table(told).splitlines()
        self.assertEqual(rows[0].split(',')[:3], ['texture', 'surface_m2', 'share_pct'])
        self.assertEqual(rows[1], 'paving,200.0,79.681,79.681,2,512,srn_t_common:dds:512x256 srn_t_common:tga:128x64,oth01,,Ground Tower')
        with self.assertRaisesRegex(ValueError, 'No set file for nope'):
            inventory.inventory(self.repo, 'nope')

    def test_a_changed_walkmesh_is_told_and_a_restyle_that_changes_none_is_not(self):
        out = self.repo / 'out'; self.assertEqual(main(['inventory', '--tileset', 'TST01', '--out', str(out), '--repo', str(self.repo)]), 0)
        self.assertEqual(sorted(path.name for path in out.iterdir()), ['inventory.json', 'textures.csv', 'walkmesh.json'])
        self.assertEqual(json.loads((out / 'inventory.json').read_text())['tileset'], 'tst01'); self.assertNotIn(b'\r', (out / 'walkmesh.json').read_bytes())
        baseline = ['walkmesh', '--tileset', 'tst01', '--baseline', str(out / 'walkmesh.json'), '--repo', str(self.repo)]
        own = self.repo / 'srn_t_tst01'; path = own / 'tst01_a01_01.mdl'
        path.write_text(path.read_text().replace('bitmap Paving', 'bitmap paving2').replace('  verts 4', '   verts   4', 1))  # a new texture and spacing: no walkmesh change
        (self.repo / 'srn_t_common' / 'tst01_n01_01.mdl').write_text(model('tst01_n01_01', [('aabb', 'walk', 'walk', True, 4.0)]))
        self.assertEqual(main(baseline), 0)
        text = path.read_text(); at = text.index('node aabb'); path.write_text(text[:at] + text[at:].replace('10.0 10.0 0.0', '10.0 9.0 0.0', 1))
        (own / 'tst01_a01_01.wok').write_bytes(b'walkmesh two'); (own / 'tst01_z01_01.mdl').unlink()
        _, now = inventory.inventory(self.repo, 'tst01')
        self.assertEqual(inventory.inventory(self.repo, 'tst01', walkmesh_only=True), (None, now))  # the check reads the tileset's own models alone
        self.assertEqual(inventory.moved(json.loads((out / 'walkmesh.json').read_text()), now),
                         ['tst01_a01_01: wok changed', 'tst01_a01_01: aabb changed', 'tst01_z01_01: gone'])
        self.assertEqual(main(baseline), 1)
        (out / 'other.json').write_text(json.dumps({'schemaVersion': 1, 'tileset': 'oth01', 'models': {}}))
        self.assertEqual(main([*baseline[:4], str(out / 'other.json'), *baseline[5:]]), 2)  # another tileset's baseline is refused, not held against this one
        self.assertEqual(main([*baseline[:4], str(out / 'none.json'), *baseline[5:]]), 2)  # as is one that is not there
        self.assertEqual(main(['walkmesh', '--tileset', 'nope', '--baseline', str(out / 'walkmesh.json'), '--repo', str(self.repo)]), 2)

    def test_a_set_merged_of_this_one_is_no_other(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder); (repo / 'srn_2da').mkdir(); rows = '[TILE0]\nModel=a\n'
            for name in ('x', 'm', 'y'):
                (repo / f'srn_t_{name}').mkdir(); (repo / f'srn_t_{name}' / f'{name}.set').write_text(rows)
            (repo / 'srn_t_x' / 'a.mdl').write_text('newmodel a\n'); merge = repo / 'docs' / 'tilesets' / 'm'; merge.mkdir(parents=True)
            others = lambda tileset: [row[3] for row in inventory.drawn_copies(repo, tileset, None, ('srn_t_x',))]
            self.assertEqual(others('x'), [['m', 'y']])
            (merge / 'merge.json').write_text(json.dumps({'families': [{'set': 'x'}]}))
            self.assertEqual(others('x'), [['y']]); self.assertEqual(others('m'), [['x', 'y']])  # a true other is still one; from the merged set, its families are


if __name__ == '__main__':
    unittest.main()
