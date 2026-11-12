"""The stock tiles of a tileset are read for what the engine wants of a tile."""
import struct
import tempfile
import unittest
from pathlib import Path

from . import study

SET = '''[GENERAL]
Name=tst01

[TILES]
Count=4

[TILE0]
Model=tst01_a01
PathNode=L
Orientation=0
ImageMap2D=MI_a01

[TILE1]
Model=tst01_a02
PathNode=H
Orientation=90
Doors=1

[TILE1DOOR0]
Type=58
X=0.0

[TILE2]
Model=ek_hall_t00
PathNode=A
Orientation=0

[TILE3]
Model=tst01_gone
PathNode=A
Orientation=0

[GROUPS]
Count=0
'''
STONE, WALL = 4, 7


def wok(path, closed):
    """A walkmesh of one tile in four strips or quarters, each walked on unless its number is in `closed`."""
    points = [(x, y, 0.0) for y in (-5, 0, 5) for x in (-5, 0, 5)]
    quads = [(0, 1, 4, 3), (1, 2, 5, 4), (3, 4, 7, 6), (4, 5, 8, 7)]  # south-west, south-east, north-west, north-east
    faces = [(q[a], q[b], q[c], 1, 0, 0, 0, WALL if number in closed else STONE) for number, q in enumerate(quads) for a, b, c in ((0, 1, 2), (0, 2, 3))]
    lines = ['node aabb wm', f'  verts {len(points)}', *('    %s %s %s' % point for point in points), f'  faces {len(faces)}', *('    ' + ' '.join(map(str, face)) for face in faces), 'endnode']
    Path(path).write_text('\n'.join(lines) + '\n', encoding='cp1252')


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup); self.packs = Path(self.folder.name)
        pack, common = self.packs / 'srn_t_tst01', self.packs / 'srn_t_common'; pack.mkdir(); common.mkdir()
        (pack / 'tst01.set').write_bytes(SET.replace('\n', '\r\n').encode('cp1252'))
        wok(pack / 'tst01_a01.wok', closed={0, 2})  # the east half is walked on: north to south
        wok(common / 'tst01_a02.wok', closed={1, 2, 3})  # the south-west quarter alone
        wok(pack / 'ek_hall_t00.wok', closed=set())
        (common / 'mi_a01.tga').write_bytes(bytes(12) + struct.pack('<HHB', 16, 16, 24) + bytes(8))

    def test_a_set_file_is_read_by_tile_with_its_doors(self):
        found = study.records(study.set_text(self.packs, 'tst01'))
        self.assertEqual(sorted(found), [0, 1, 2, 3]); self.assertEqual((found[0]['Model'], found[0]['doors']), ('tst01_a01', []))
        self.assertEqual(found[1]['doors'], [{'Type': '58', 'X': '0.0'}]); self.assertEqual(found[3]['Orientation'], '0')  # the last tile ends at the next section
        with self.assertRaisesRegex(ValueError, 'No such tileset'):
            study.set_text(self.packs, 'tst02')

    def test_a_walkmesh_is_read_as_the_ground_walked_on(self):
        grid = study.walkable(self.packs / 'srn_t_tst01' / 'tst01_a01.wok'); half = study.CELLS // 2
        self.assertTrue(grid[:, half:].all()); self.assertFalse(grid[:, :half].any())
        (self.packs / 'bare.wok').write_text('node trimesh x\nendnode\n', encoding='cp1252')
        with self.assertRaisesRegex(ValueError, 'No walkmesh node'):
            study.walkable(self.packs / 'bare.wok')

    def test_a_node_is_judged_by_its_exits_on_the_ground(self):
        east = study.walkable(self.packs / 'srn_t_tst01' / 'tst01_a01.wok')
        self.assertEqual(study.judge(east, [(2.5, 5, 0), (2.5, -5, 0)]), (2, 2, 1, 1))  # both on the ground and joined, as one region should be
        self.assertEqual(study.judge(east, [(2.5, 5, 0), (2.5, -5, 1)]), (2, 2, 0, 1))  # joined, where the node says they are apart
        self.assertEqual(study.judge(east, [(2.5, 5, 0), (-2.5, -5, 0)]), (1, 2, 0, 0))  # one exit in the wall
        self.assertEqual(study.turned([(0, 5, 0)], 90, 'ccw'), [(-5, 0, 0)]); self.assertEqual(study.turned([(0, 5, 0)], 90, 'cw'), [(5, 0, 0)])
        self.assertEqual(study.turned([(0, 5, 0)], 0, 'cw'), [(0, 5, 0)]); self.assertEqual(study.EXITS['T'], []); self.assertEqual(len(study.EXITS['D']), 8)

    def test_the_table_is_checked_against_the_stock_tiles_each_way_round(self):
        """Tile 1's ground is its south-west quarter and its node H (west and south) is stated turned by 90: turned
        either way one exit leaves that quarter, so neither sense puts both on the ground, and our own tile and the
        tile without a walkmesh are not counted."""
        told = study.path_nodes(self.packs, ['tst01'])
        self.assertEqual(told['ccw']['tiles'], 2); self.assertEqual(sorted(told['ccw']['letters']), ['H', 'L'])
        self.assertEqual(told['ccw']['letters']['L'], {'tiles': 1, 'exitsOnGround': [2, 2], 'pairsRight': [1, 1]})  # a middle exit is found on the ground beside it
        self.assertEqual(told['ccw']['letters']['H']['exitsOnGround'], [1, 2]); self.assertEqual(told['cw']['letters']['H']['exitsOnGround'], [1, 2])
        (self.packs / 'srn_t_tst01' / 'tst01.set').write_bytes(SET.replace('Orientation=90', 'Orientation=0').replace('\n', '\r\n').encode('cp1252'))
        self.assertEqual(study.path_nodes(self.packs, ['tst01'])['ccw']['letters']['H'], {'tiles': 1, 'exitsOnGround': [2, 2], 'pairsRight': [1, 1]})  # as it lies, both are on it
        (self.packs / 'srn_t_tst01' / 'tst01.set').write_bytes(b'[TILE0]\r\nModel=ek_hall_t00\r\nPathNode=A\r\n')
        with self.assertRaisesRegex(ValueError, 'No stock tile'):
            study.path_nodes(self.packs, ['tst01'])

    def test_a_decompiled_tile_tells_its_fade_lights_and_animation(self):
        text = '\n'.join(['newmodel t', 'node dummy t', '  parent NULL', '  position 0 0 0', 'endnode', 'node trimesh roof', '  parent t', '  position 1 2 3', '  tilefade 1', '  bitmap roof01',
                          '  verts 3', '    0 0 0', 'endnode', 'node light tml1', '  parent t', '  position 0 0 5', '  radius 14', '  color 1 1 1', 'endnode', 'newanim day2night t', '  length 1.0'])
        self.assertEqual(study.told(text), ['node dummy t', '    parent NULL', '    position 0 0 0', 'node trimesh roof', '    parent t', '    tilefade 1', '    bitmap roof01',
                                            'node light tml1', '    parent t', '    position 0 0 5', '    radius 14', '    color 1 1 1', '    newanim day2night t', '    length 1.0'])

    def test_tiles_are_decompiled_and_told_with_their_records(self):
        (self.packs / 'srn_t_tst01' / 'tst01_a01.mdl').write_bytes(b'binary')
        import os
        import sys

        def tool(name, code):
            script = self.packs / f'{name}.py'; script.write_text(code, encoding='utf-8'); launcher = self.packs / (f'{name}.cmd' if os.name == 'nt' else f'{name}.sh')
            launcher.write_text(('@"%s" "%s" %%*\n' if launcher.suffix == '.cmd' else '#!/bin/sh\nexec "%s" "%s" "$@"\n') % (sys.executable, script), encoding='utf-8'); launcher.chmod(0o755)
            return launcher

        launcher = tool('tool', 'import sys\nopen(sys.argv[-1], "w").write("node dummy t\\n  parent NULL\\n")\n')
        rows = study.tiles(self.packs, 'tst01', [0, 1], self.packs / 'out', tool=launcher)
        self.assertEqual(rows[0]['record'], {'Model': 'tst01_a01', 'Doors': None, 'MainLight1': None, 'SourceLight1': None, 'AnimLoop1': None, 'PathNode': 'L', 'Orientation': '0', 'ImageMap2D': 'MI_a01'})
        self.assertEqual((rows[0]['lines'], rows[0]['minimap']), (['node dummy t', '    parent NULL'], {'file': 'mi_a01.tga', 'size': [16, 16], 'bits': 24, 'type': 0}))
        self.assertEqual((rows[1]['doors'], rows[1]['error'], 'minimap' in rows[1]), ([{'Type': '58', 'X': '0.0'}], 'model not in the packs', False))
        self.assertTrue((self.packs / 'out' / 'tst01_a01.mdl').is_file())
        for failing in (tool('none', 'import sys\nsys.exit("no such model")\n'), tool('half', 'import sys\nopen(sys.argv[-1], "w").write("node dummy t\\n")\nsys.exit(1)\n')):
            (row,) = study.tiles(self.packs, 'tst01', [0], self.packs / 'out', tool=failing)  # the model the run before left is not this run's
            self.assertNotIn('lines', row); self.assertIn('decompile failed', row['error'])
        with self.assertRaisesRegex(ValueError, 'tst01 has no tile 9'):
            study.tiles(self.packs, 'tst01', [0, 9], self.packs / 'out', tool=launcher)


if __name__ == '__main__':
    unittest.main()
