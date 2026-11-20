import tempfile
import unittest
from pathlib import Path

from tools.tilekit import count, inventory, remesh

TILE = """newmodel t_a01
beginmodelgeom t_a01
node dummy t_a01
  parent NULL
endnode
node trimesh street
  parent t_a01
  bitmap street_tex
  verts 4
    -5 -5 0
    5 -5 0
    5 5 0
    -5 5 0
  tverts 1
    0 0 0
  faces 2
    0 1 2 1 0 0 0 1
    0 2 3 1 0 0 0 1
endnode
node trimesh wall
  parent t_a01
  bitmap wall_tex
  verts 4
    -5 4 0
    5 4 0
    5 4 {top}
    -5 4 {top}
  tverts 1
    0 0 0
  faces 2
    0 1 2 1 0 0 0 1
    0 2 3 1 0 0 0 1
endnode
node light t_a01ml1
  parent {lamp}
  radius 7.0
endnode
node aabb walk
  parent t_a01
  verts 4
    -5 -5 0
    5 -5 0
    5 3.5 0
    -5 3.5 0
  faces 2
    0 1 2 1 0 0 0 4
    0 2 3 1 0 0 0 4
  aabb -5 -5 0 5 3.5 0 -1
    -5 -5 0 5 3.5 0 0
    -5 -5 0 5 3.5 0 1
endnode
endmodelgeom t_a01
donemodel t_a01
"""
SET = "[GENERAL]\nName=t\n[TILES]\nCount=1\n[TILE0]\nModel=t_a01\n"


def _repo(root, **tile):
    own = root / 'srn_t_t'; own.mkdir(); (root / 'srn_t_common').mkdir(); (root / 'rebuilt').mkdir()
    (own / 't.set').write_text(SET, encoding='cp1252')
    (own / 't_a01.mdl').write_text(TILE.format(**{'top': 12, 'lamp': 't_a01', **tile}), encoding='cp1252')
    return own


class Remesh(unittest.TestCase):
    def _run(self, root, rebuilt):
        (root / 'rebuilt' / 't_a01.mdl').write_text(rebuilt, encoding='cp1252')
        return remesh.remesh(root, 't', ['t_a01'], root / 'rebuilt', root / 'out')

    def test_a_new_roof_block_replaces_the_meshes_and_keeps_walkmesh_and_lamp(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); own = _repo(root)
            block = 'node trimesh block\n  parent t_a01\n  bitmap street_tex\n  verts 3\n    -2 4 12\n    2 4 12\n    0 4 15\n  faces 1\n    0 1 2 1 0 0 0 1\nendnode\n'
            rebuilt = TILE.format(top=12, lamp='t_a01').replace('wall_tex', 'street_tex').replace('node light', block + 'node light')
            told = self._run(root, rebuilt)  # one look: merged into one node; the block is above head height and off the sides
            self.assertEqual(told['t_a01'], {'faces': [4, 5], 'nodes': [2, 1]})
            made = (root / 'out' / 't_a01.mdl').read_text(encoding='cp1252')
            self.assertIn('node trimesh t_a01_rm00', made); self.assertIn('node light t_a01ml1', made); self.assertNotIn('node trimesh wall', made)
            self.assertEqual(inventory.walk_hash(made), inventory.walk_hash((own / 't_a01.mdl').read_text(encoding='cp1252')))
            self.assertEqual(count.of(made), {'faces': 5, 'nodes': 1, 'materials': 1})

    def test_a_taller_wall_at_the_cell_s_side_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); _repo(root)
            with self.assertRaisesRegex(ValueError, 'changes its sides where a neighbour meets them'):
                self._run(root, TILE.format(top=16, lamp='t_a01'))

    def test_a_rebuild_that_moves_the_wall_at_street_level_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); _repo(root)
            with self.assertRaisesRegex(ValueError, 'changes the shape below'):
                self._run(root, TILE.format(top=12, lamp='t_a01').replace('-5 4 0\n    5 4 0', '-5 2 0\n    5 2 0'))

    def test_a_rebuild_without_the_floor_over_walkable_ground_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); _repo(root)
            rebuilt = TILE.format(top=12, lamp='t_a01').replace('bitmap street_tex', 'bitmap street_tex\n  render 0')
            with self.assertRaisesRegex(ValueError, 'draws no floor'):
                self._run(root, rebuilt)

    def test_a_rebuild_that_overhangs_further_than_the_original_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); _repo(root)
            with self.assertRaisesRegex(ValueError, 'reaches past its cell further'):
                self._run(root, TILE.format(top=12, lamp='t_a01').replace('5 4 {top}'.format(top=12), '5.6 4 12'))

    def test_a_lamp_hanging_from_a_replaced_mesh_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); _repo(root, lamp='wall')
            with self.assertRaisesRegex(ValueError, 'hang from meshes the rebuild replaces'):
                self._run(root, TILE.format(top=16, lamp='t_a01'))


class Count(unittest.TestCase):
    def test_a_tile_over_budget_is_listed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); _repo(root)
            told = count.count(root, 't', budget={'nodes': 1, 'faces': 10})
            self.assertEqual(told['tiles']['t_a01'], {'faces': 4, 'nodes': 2, 'materials': 2})
            self.assertEqual(told['over'], {'t_a01': ['nodes 2 > 1']})
            with self.assertRaisesRegex(ValueError, 'A budget is any of'):
                count.count(root, 't', budget={'draws': 1})


if __name__ == '__main__':
    unittest.main()
