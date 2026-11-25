"""No floor of the packs `srx01` and `srx02` take tiles from has an edge its neighbours meet in pieces (a T-junction), a
face it holds twice or a face of no area on an edge between two others: the game joins faces edge by edge, so a creature
walks round such a place instead of across it. Nor does a floor end just short of its tile's side, or a tile lack its
`.wok` (reproduced in the client with a Human and a Troll, 2026-11-25)."""
import collections
import re
import unittest
from pathlib import Path

import numpy as np

from tools.tilekit import geometry

REPO = Path(__file__).resolve().parents[2]
PACKS = ('srn_t_common', 'srn_t_dgt04', 'srn_t_fcx01', 'srn_t_nac01', 'srn_t_srx01', 'srn_t_tbx78', 'srn_t_tfb01', 'srn_t_udp1',
         'srn_t_udp2')  # named so the test selector runs this when one changes
ON = .04  # how far from an edge, in metres, another still lies along it
SHORT = .3  # an edge met along less than this, in metres, is narrower than a creature's way past it
# Tiles with a face of no area on an edge between two others, and how many such edges each has. All were walked straight
# across in the client, 2026-11-25, but tfb01_n01_13 and n01_14, whose edge is the top of a 0.9 m wall.
STRAIGHT = {'fcx01_h01_24': 1, 'fcx01_h01_27': 1, 'tfb01_n01_13': 1, 'tfb01_n01_14': 1, 'tfb01_r06_01': 1, 'tfb01_r07_01': 1, 'udp1_c01_07': 1,
            'udp1_c02_07': 1, 'udp1_c03_07': 1, 'udp1_c04_07': 1, 'udp1_c05_07': 1, 'udp1_c06_07': 1}
# Tiles with edges met in pieces that nothing crosses, and how many pairs: the foot of a 78 degree slope, and a tile of no .set.
UNCROSSED = {'nac01_d01_05': 2, 'tfb01_b02_03': 2}


def numbered(corners, faces, floor=True):
    """The walked faces (or the others) as corner numbers; corners at one place have one number, and at
    0.01 mm from it another (the game walks round that too)."""
    place = {}; same = [place.setdefault(tuple(corner), index) for index, corner in enumerate(corners)]
    return [[same[index] for index in face[:3]] for face in faces if (face[7] in geometry.WALKABLE) == floor]


def flat(corners, face):
    """Whether a face has no area: it can join its neighbours' edges but has no floor of its own beside them."""
    a, b, c = (corners[index] for index in face)
    return np.linalg.norm(np.cross(b - a, c - a)) <= 1e-4


def edges(corners, faces):
    """{edge: the walked faces that have it}."""
    beside = collections.defaultdict(list)
    for face in numbered(corners, faces):
        for j in range(3):
            beside[frozenset((face[j], face[(j + 1) % 3]))].append(face)
    return beside


def pieced(corners, faces, placed=None):
    """The pairs of unmatched inner edges of the walked `faces` that run along each other: the floor either side meets in
    pieces. `placed` is the corners in the tile, where the node is moved or turned."""
    placed = corners if placed is None else placed
    beside = edges(corners, faces)
    walls = {frozenset((face[j], face[(j + 1) % 3])) for face in numbered(corners, faces, floor=False) for j in range(3)}  # an edge a wall stands on is meant to stop
    single = sorted(tuple(sorted(edge)) for edge, held in beside.items() if len(held) == 1 and len(edge) == 2 and edge not in walls)
    # the tile's side is the neighbour tile's to meet
    single = [(a, b) for a, b in single if not any(abs(placed[a][axis]) > 4.995 and abs(placed[a][axis] - placed[b][axis]) < .005 for axis in (0, 1))]
    if not single:
        return []
    starts, ends = (corners[[edge[side] for edge in single]] for side in (0, 1)); found = []
    for index, (p, q) in enumerate(zip(starts, ends)):
        length = np.linalg.norm(q - p)
        if length < SHORT:
            continue
        along = (q - p) / length; one, two = (starts - p) @ along, (ends - p) @ along
        off = np.maximum(*(np.linalg.norm(ends_ - p - np.outer(share, along), axis=1) for ends_, share in ((starts, one), (ends, two))))
        shared = np.minimum(np.maximum(one, two), length) - np.maximum(np.minimum(one, two), 0)
        met = [other for other in np.nonzero((off < ON) & (shared > ON))[0] if beside[frozenset(single[index])] != beside[frozenset(single[other])]]  # a sliver's own two sides join nothing
        if sum(shared[other] for other in met) > SHORT:
            found += [(single[index], single[other]) for other in met]
    return sorted({tuple(sorted(pair)) for pair in found})


def short(corners, faces, placed=None):
    """The floor edges along the tile's side, 5 to 50 mm inside it: the neighbour's floor is out of reach there (10 mm on
    fcx01_h01_01 bent the routes; 4 mm on tfb01_a13_02 did not)."""
    placed = corners if placed is None else placed; found = []
    walls = {frozenset((face[j], face[(j + 1) % 3])) for face in numbered(corners, faces, floor=False) for j in range(3)}
    for edge, held in edges(corners, faces).items():
        if len(held) == 1 and len(edge) == 2 and edge not in walls and not flat(corners, held[0]):
            (a, b), (one, two, three) = (placed[list(edge)], placed[held[0]]); up = np.cross(two - one, three - one)
            for axis in (0, 1):
                if abs(up[2]) > .3 * np.linalg.norm(up) and abs(a[axis] - b[axis]) < .02 and abs(a[1 - axis] - b[1 - axis]) > SHORT                         and a[axis] * b[axis] > 0 and 4.95 < min(abs(a[axis]), abs(b[axis])) < 4.995 and max(abs(a[axis]), abs(b[axis])) < 5.002:
                    found.append(tuple(sorted(edge)))
    return sorted(found)


def pinched(corners, faces):
    """The edges between two walked faces on which a face of no area lies too."""
    return sorted(tuple(sorted(edge)) for edge, held in edges(corners, faces).items()
                  if len(edge) == 2 and any(flat(corners, face) for face in held) and sum(not flat(corners, face) for face in held) > 1)


def doubled(corners, faces):
    """The walked faces held more than once."""
    return sorted(face for face, times in collections.Counter(tuple(sorted(face)) for face in numbered(corners, faces)).items() if times > 1)


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
        for pack in PACKS:  # without it creatures walk through the tile's walls (tfb01_l01_09, walked 2026-11-25)
            models = REPO / 'sources' / pack; models = models if models.is_dir() else REPO / pack
            for path in (REPO / pack).glob('*.set'):
                for name in sorted(set(re.findall(r'(?im)^\s*model\s*=\s*(\S+)', path.read_text(encoding='cp1252')))):
                    model = models / f'{name.lower()}.mdl'
                    if model.is_file() and not (REPO / pack / f'{name.lower()}.wok').is_file():
                        self.assertNotIn(b'node aabb', model.read_bytes().lower(), name)

    def test_a_face_held_twice_is_found(self):
        self.assertEqual(doubled(CORNERS, [(0, 1, 3, *TAIL), (1, 3, 0, *TAIL), (0, 4, 1, *TAIL)]), [(0, 1, 3)])

    def test_a_face_of_no_area_between_two_others_is_found(self):
        sides = [(0, 1, 3, *TAIL), (0, 4, 1, *TAIL)]
        for none in ((0, 1, 1), (0, 2, 1)):
            self.assertEqual(pinched(CORNERS, [*sides, (*none, *TAIL)]), [(0, 1)])
        self.assertEqual(pinched(CORNERS, sides), [])
        self.assertEqual(pinched(CORNERS, [(0, 1, 3, *TAIL), (0, 2, 1, *TAIL), (0, 4, 2, *TAIL), (2, 4, 1, *TAIL)]), [])  # it joins the pieces to the edge

    def test_every_pack_with_sources_is_named(self):
        self.assertEqual({folder.name for folder in (REPO / 'sources').iterdir() if any(folder.glob('*.mdl'))} - set(PACKS), set())

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
                                self.assertEqual(short(corners, node.faces, inside) if path.suffix == '.wok' else [], [])
                                self.assertEqual(len(pinched(corners, node.faces)), STRAIGHT.get(path.stem, 0))
                self.assertTrue(checked, f'{pack} has no walkmesh to check')


if __name__ == '__main__':
    unittest.main()
