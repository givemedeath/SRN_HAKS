"""No floor of the packs `srx01` and `srx02` take tiles from has an edge its neighbours meet in pieces (a T-junction), a
face it holds twice or a face of no area on an edge between two others: the game joins faces edge by edge, so a creature
walks round such a place instead of across it. Nor does a floor end just short of its tile's side, or a tile lack its
`.wok` (reproduced in the client with a Human and a Troll, 2026-11-25)."""
import re
import unittest
from pathlib import Path

import numpy as np

from tools import test_impact
from tools.tilekit import geometry
from tools.tilekit.floors import doubled, pieced, pinched, short

REPO = Path(__file__).resolve().parents[2]
PACKS = ('srn_t_common', 'srn_t_dgt04', 'srn_t_fcx01', 'srn_t_nac01', 'srn_t_srx01', 'srn_t_srx02', 'srn_t_tbx78', 'srn_t_tfb01', 'srn_t_udp1',
         'srn_t_udp2')  # named so the test selector runs this when one changes
# Tiles with a face of no area on an edge between two others, and how many such edges each has. All were walked straight
# across in the client, 2026-11-25, but tfb01_n01_13 and n01_14, whose edge is the top of a 0.9 m wall.
STRAIGHT = {'fcx01_h01_24': 1, 'fcx01_h01_27': 1, 'tfb01_n01_13': 1, 'tfb01_n01_14': 1, 'tfb01_r06_01': 1, 'tfb01_r07_01': 1, 'udp1_c01_07': 1,
            'udp1_c02_07': 1, 'udp1_c03_07': 1, 'udp1_c04_07': 1, 'udp1_c05_07': 1, 'udp1_c06_07': 1}
# Tiles with edges met in pieces that nothing crosses, and how many pairs: the foot of a 78 degree slope, and a tile of no .set.
UNCROSSED = {'nac01_d01_05': 2, 'tfb01_b02_03': 2}


TAIL = (0, 0, 0, 0, 4)
CORNERS = np.array([(0, 0, 0), (2, 0, 0), (1, 0, 0), (1, 2, 0), (1, -2, 0), (3, 0, 0)], dtype=float)


class FloorEdges(unittest.TestCase):
    def test_an_edge_met_in_pieces_is_found_and_a_matched_one_is_not(self):
        lower = [(0, 4, 2, *TAIL), (2, 4, 1, *TAIL)]
        self.assertEqual(pieced(CORNERS, [(0, 1, 3, *TAIL), *lower]), [((0, 1), (0, 2)), ((0, 1), (1, 2))])
        self.assertEqual(pieced(CORNERS, [(0, 2, 3, *TAIL), (2, 1, 3, *TAIL), *lower]), [])

    def test_the_tiles_side_is_the_neighbours_to_meet_wherever_the_node_is(self):
        faces = [(0, 1, 3, *TAIL), (0, 4, 2, *TAIL), (2, 4, 1, *TAIL)]; moved = CORNERS + (0, 5, 0)
        self.assertEqual(pieced(moved, faces), [])
        self.assertEqual(len(pieced(moved, faces, CORNERS)), 2)
        self.assertEqual(pieced(CORNERS, faces, moved), [])

    def test_an_edge_met_in_short_pieces_is_found(self):
        self.assertEqual(len(pieced(CORNERS * .25, [(0, 1, 3, *TAIL), (0, 4, 2, *TAIL), (2, 4, 1, *TAIL)])), 2)

    def test_edges_that_only_partly_run_along_each_other_are_found(self):
        self.assertEqual(pieced(CORNERS, [(0, 1, 3, *TAIL), (2, 4, 5, *TAIL)]), [((0, 1), (2, 5))])

    def test_a_sliver_that_joins_one_side_hides_no_miss_on_the_other(self):
        corners = np.array([(0, 0, 0), (2, 0, 0), (1, 2, 0), (1, -1e-5, 0), (0, -8e-6, 0), (2, -8e-6, 0), (1, -2, 0)])
        self.assertEqual(pieced(corners, [(0, 1, 2, *TAIL), (0, 3, 1, *TAIL), (4, 6, 5, *TAIL)]), [((0, 3), (4, 5)), ((1, 3), (4, 5))])

    def test_an_edge_a_wall_stands_on_is_meant_to_stop(self):
        wall = (0, 1, 5, 0, 0, 0, 0, 7)
        self.assertEqual(pieced(CORNERS, [(0, 1, 3, *TAIL), (0, 4, 2, *TAIL), (2, 4, 1, *TAIL), wall]), [])

    def test_a_floor_that_ends_short_of_the_tiles_side_is_found(self):
        side = np.array([(4.99, 0, 0), (4.98, 2, 0), (0, 1, 0)]); reaches = side + (.01, 0, 0); reaches[0, 0] = 4.996; reaches[1, 0] = 5
        self.assertEqual(short(side, [(0, 1, 2, *TAIL)]), [(0, 1)])
        self.assertEqual(short(reaches, [(0, 1, 2, *TAIL)]), [])
        self.assertEqual(short(side, [(0, 1, 2, *TAIL), (0, 1, 2, 0, 0, 0, 0, 7)]), [])  # a wall ends it
        self.assertEqual(short(side - (1, 0, 0), [(0, 1, 2, *TAIL)], side), [(0, 1)])

    def test_every_tile_of_a_set_with_a_walkmesh_has_its_wok(self):
        models, woks = {}, set()  # a set may take its tiles from other packs (srx01, srx02)
        for pack in PACKS:  # a compiled model is read in its source where it has one; the ek_ tiles of common have none
            models.update((path.stem, path) for path in (REPO / pack).glob('*.mdl'))
            models.update((path.stem, path) for path in (REPO / 'sources' / pack).glob('*.mdl'))
            woks.update(path.stem for path in (REPO / pack).glob('*.wok'))
        for pack in PACKS:  # without it creatures walk through the tile's walls (tfb01_l01_09, walked 2026-11-25)
            for path in (REPO / pack).glob('*.set'):
                for name in sorted({name.lower() for name in re.findall(r'(?im)^\s*model\s*=\s*(\S+)', path.read_text(encoding='cp1252'))}):
                    if name in models and name not in woks:
                        data = models[name].read_bytes()  # a compiled model (it starts with four zero bytes) is not read here: it needs its .wok
                        self.assertFalse(data[:4] == bytes(4) or re.search(rb'(?i)\bnode\s+aabb\b', data), f'{path.name}: {name} has a walkmesh and no .wok')

    def test_a_face_held_twice_is_found(self):
        self.assertEqual(doubled(CORNERS, [(0, 1, 3, *TAIL), (1, 3, 0, *TAIL), (0, 4, 1, *TAIL)]), [(0, 1, 3)])

    def test_a_face_of_no_area_between_two_others_is_found(self):
        sides = [(0, 1, 3, *TAIL), (0, 4, 1, *TAIL)]
        for none in ((0, 1, 1), (0, 2, 1)):
            self.assertEqual(pinched(CORNERS, [*sides, (*none, *TAIL)]), [(0, 1)])
        self.assertEqual(pinched(CORNERS, sides), [])
        self.assertEqual(pinched(CORNERS, [(0, 1, 3, *TAIL), (0, 2, 1, *TAIL), (0, 4, 2, *TAIL), (2, 4, 1, *TAIL)]), [])  # it joins the pieces to the edge

    def test_every_pack_with_sources_is_named(self):
        on_disk = {folder.name for folder in (REPO / 'sources').iterdir() if any(folder.glob('*.mdl'))} if (REPO / 'sources').is_dir() else set()
        self.assertEqual((on_disk | test_impact.committed_sources(REPO)) - set(PACKS), set())  # a CI leg checks out only the sources its tests name

    def test_every_floor_is_matched_in_the_sources_and_in_the_woks(self):
        for pack in PACKS:
            models = REPO / 'sources' / pack  # a pack without sources holds its models as text
            for paths in ((models if models.is_dir() else REPO / pack).glob('*.mdl'), (REPO / pack).glob('*.wok')):  # the game walks the .wok; some (ek_) have no source
                checked = 0
                for path in sorted(paths):
                    text = path.read_bytes().decode('cp1252')
                    _, _, nodes = geometry.parse(text if 'beginmodelgeom' in text.lower() else 'beginmodelgeom wok\n' + text)
                    for node in nodes:
                        if node.kind == 'aabb' and node.faces:
                            corners = np.array(node.verts, dtype=float); checked += 1; place = geometry.placed(nodes)[id(node)]
                            with self.subTest(file=path.name):
                                self.assertEqual(doubled(corners, node.faces), [])
                                inside = np.array([place(vertex) for vertex in node.verts])
                                self.assertEqual(len(pieced(corners, node.faces, inside)), UNCROSSED.get(path.stem, 0))
                                self.assertEqual(short(corners, node.faces, inside), [])  # a cut or a new .wok copies the model's
                                self.assertEqual(len(pinched(corners, node.faces)), STRAIGHT.get(path.stem, 0))
                self.assertTrue(checked, f'{pack} has no walkmesh to check')


if __name__ == '__main__':
    unittest.main()
