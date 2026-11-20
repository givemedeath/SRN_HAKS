import tempfile
import unittest
from pathlib import Path

from tools.tilekit import crown, geometry, remesh

CORNERS = {'t_edge': ('Ground', 'Tower', 'Ground', 'Tower'),  # the facade on the west
           't_corner': ('Tower', 'Ground', 'Ground', 'Ground'),  # facades on the east and south
           't_inner': ('Tower', 'Tower', 'Ground', 'Tower'),  # the street's corner at the bottom left
           't_middle': ('Tower', 'Tower', 'Tower', 'Tower')}
WALLS = {'w': ((-5, -5), (-5, 5)), 'e': ((5, 5), (5, -5)), 's': ((5, -5), (-5, -5)), 'n': ((-5, 5), (5, 5))}  # each facade, wound to face out


def _model(name, facades, top=12.0, wall=None):
    """A tower tile: the street drawn and walked at 0, its roof at `top` over the whole cell, a wall up to `wall` (the
    roof) on each facade, and a ledge standing 0.5 m out from it at 4 m, as the real towers' do."""
    verts, faces = [(-5, -5, top), (5, -5, top), (5, 5, top), (-5, 5, top)], [(0, 1, 2), (0, 2, 3)]
    for side in facades:
        (x0, y0), (x1, y1) = WALLS[side]; ox, oy = (value * 0.5 for value in crown.FRAME[side][0]); base = len(verts)
        verts += [(x0, y0, 0.0), (x1, y1, 0.0), (x1, y1, wall or top), (x0, y0, wall or top)]; faces += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
        base = len(verts); verts += [(x0, y0, 4.0), (x1, y1, 4.0), (x1 + ox, y1 + oy, 4.0), (x0 + ox, y0 + oy, 4.0)]
        faces += [(base, base + 2, base + 1), (base, base + 3, base + 2)]
    mass = ''.join(f'    {x} {y} {z}\n' for x, y, z in verts); listed = ''.join(f'    {a} {b} {c} 1 0 0 0 1\n' for a, b, c in faces)
    return (f'newmodel {name}\nbeginmodelgeom {name}\nnode dummy {name}\n  parent NULL\nendnode\n'
            f'node trimesh street\n  parent {name}\n  bitmap street_tex\n  verts 4\n    -5 -5 0\n    5 -5 0\n    5 5 0\n    -5 5 0\n'
            '  tverts 1\n    0 0 0\n  faces 2\n    0 1 2 1 0 0 0 1\n    0 2 3 1 0 0 0 1\nendnode\n'
            f'node trimesh mass\n  parent {name}\n  bitmap wall_tex\n  verts {len(verts)}\n{mass}  tverts 1\n    0 0 0\n  faces {len(faces)}\n{listed}endnode\n'
            f'node aabb walk\n  parent {name}\n  verts 4\n    -5 -5 0\n    5 -5 0\n    5 5 0\n    -5 5 0\n  faces 2\n    0 1 2 1 0 0 0 4\n    0 2 3 1 0 0 0 4\n'
            f'  aabb -5 -5 0 5 5 0 -1\n    -5 -5 0 5 5 0 0\n    -5 -5 0 5 5 0 1\nendnode\nendmodelgeom {name}\ndonemodel {name}\n')


def _repo(root):
    own = root / 'srn_t_t'; own.mkdir(); (root / 'srn_t_common').mkdir()
    tiles = ''.join(f'[TILE{number}]\nModel={model}\n' + ''.join(f'{key}={value}\n' for key, value in zip(crown.CORNERS, corners))
                    for number, (model, corners) in enumerate(CORNERS.items()))
    (own / 't.set').write_text(f'[GENERAL]\nName=t\nDefault=Ground\n[TILES]\nCount={len(CORNERS)}\n{tiles}', encoding='cp1252')
    for model, corners in CORNERS.items():
        (own / f'{model}.mdl').write_text(_model(model, crown.facades(corners, 'Tower')), encoding='cp1252')
    return own


class Crown(unittest.TestCase):
    def test_facades_and_inner_corners_come_from_the_set_s_corners(self):
        self.assertEqual(crown.facades(CORNERS['t_edge'], 'tower'), {'w'})
        self.assertEqual(crown.facades(CORNERS['t_corner'], 'Tower'), {'e', 's'})
        self.assertEqual(crown.inner(CORNERS['t_inner'], 'Tower', set()), {2})
        self.assertEqual(crown.inner(CORNERS['t_corner'], 'Tower', {'e', 's'}), set())  # its street corners are the facades' own

    def test_a_crowned_tower_passes_remesh_where_its_tiles_join_alike(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); _repo(root)
            told = crown.write(root, 't', 'Tower', list(CORNERS), root / 'rebuilt')
            self.assertEqual(told['t_middle'], {'facades': [], 'inner': []}); self.assertFalse((root / 'rebuilt' / 't_middle.mdl').exists())  # nothing to add
            made = remesh.remesh(root, 't', ['t_edge', 't_corner', 't_inner'], root / 'rebuilt', root / 'out', joins='Tower', add=True)
            self.assertGreater(made['t_edge']['faces'][1], made['t_edge']['faces'][0]); self.assertEqual(made['t_edge']['nodes'], [2, 3])  # its own two meshes kept, the crown one more
            text = (root / 'out' / 't_edge.mdl').read_text(encoding='cp1252'); self.assertIn('node trimesh mass', text)
            _, _, nodes = geometry.parse(text)
            self.assertAlmostEqual(max(point[2] for triangle in geometry.triangles(nodes) for point in triangle), 12.0 + crown.SCREEN[1] + crown.POST[1], places=3)  # the screen's posts

    def test_without_joins_a_crown_crossing_the_cell_s_sides_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); _repo(root); crown.write(root, 't', 'Tower', ['t_edge'], root / 'rebuilt')
            with self.assertRaisesRegex(ValueError, 'changes its sides where a neighbour meets them'):
                remesh.remesh(root, 't', ['t_edge'], root / 'rebuilt', root / 'out', add=True)

    def test_a_tile_left_without_its_part_of_the_crown_is_refused(self):  # the inner corner draws the screens' turn
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); _repo(root); crown.write(root, 't', 'Tower', list(CORNERS), root / 'rebuilt')
            with self.assertRaisesRegex(ValueError, "side draws what t_inner's"):
                remesh.remesh(root, 't', ['t_edge', 't_corner'], root / 'rebuilt', root / 'out', joins='Tower', add=True)

    def test_a_facade_may_rise_only_where_it_reaches_its_top(self):
        text = _model('t_edge', {'w'})  # then its north half set back a metre from 6 m up, roof and all: the parapet stands on nothing there
        stepped = text.replace('    -5 5 12.0\n    -5 -5 0.0\n    -5 5 0.0\n    -5 5 12.0', '    -4 5 12.0\n    -5 -5 0.0\n    -5 5 0.0\n    -5 5 6.0')
        self.assertNotEqual(stepped, text)
        made = crown.rebuilt(stepped, 't_edge', CORNERS['t_edge'], 'Tower')
        with self.assertRaisesRegex(ValueError, 'changes its sides where a neighbour meets them: w'):
            remesh.rebuilt(stepped, 't_edge', made, {'w'}, add=True)
        remesh.rebuilt(text, 't_edge', crown.rebuilt(text, 't_edge', CORNERS['t_edge'], 'Tower'), {'w'}, add=True)  # straight up to the roof: it may rise


class Sides(unittest.TestCase):
    def test_a_point_past_a_side_s_ends_is_not_on_that_side(self):
        cornice = [((5.0, -5.4, 10.0), (5.4, -5.4, 10.0), (5.0, -5.1, 10.0))]  # wrapped round the corner, outside the cell
        self.assertFalse({side for side, _, _ in geometry.sides(cornice)} & {'e'})


if __name__ == '__main__':
    unittest.main()
