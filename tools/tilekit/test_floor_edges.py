"""No tile's floor has an edge its neighbours meet in pieces (a T-junction) or a face it holds twice: the game joins
faces edge by edge, so a creature walks round such a place instead of across it (reproduced in the client with a Human
and a Troll, 2026-11-25)."""
import collections
import unittest
from pathlib import Path

import numpy as np

from tools.tilekit import geometry

REPO = Path(__file__).resolve().parents[2]
PACKS = ('srn_t_common', 'srn_t_dgt04', 'srn_t_fcx01', 'srn_t_srx01', 'srn_t_udp1')  # the packs with sources: named so the test selector runs this when one changes
ON = .008  # how far from an edge, in metres, another still lies along it
SHORT = .3  # an edge met along less than this, in metres, is narrower than a creature's way past it
# Tiles with corners that miss each other by 1 to 30 mm along an edge, found 2026-11-25; never walked in the client, so not repaired: how many pairs each has.
KNOWN = {'dgt04_e09_33': 1, 'rdt01_e26_01': 1, 'udp1_a01_08': 3, 'udp1_a01_09': 3, 'udp1_a01_13': 2, 'udp1_a01_14': 3, 'udp1_a01_15': 3, 'udp1_a03_12': 1,
         'udp1_a14_14': 2, 'udp1_a14_15': 3, 'udp1_a14_16': 3, 'udp1_a18_10': 1, 'udp1_b06_02': 1}


def walked(corners, faces):
    """The walked faces as corner numbers; corners at one place have one number."""
    place = {}; same = [place.setdefault(tuple(np.round(corner, 3)), index) for index, corner in enumerate(corners)]
    return [[same[index] for index in face[:3]] for face in faces if face[7] in geometry.WALKABLE]


def flat(corners, face):
    """Whether a face has no area: it can join its neighbours' edges but has no floor of its own beside them."""
    a, b, c = (corners[index] for index in face)
    return np.linalg.norm(np.cross(b - a, c - a)) <= 1e-4


def pieced(corners, faces):
    """The pairs of unmatched inner edges of the walked `faces` that run along each other: the floor either side meets in pieces."""
    beside = collections.defaultdict(list)
    for face in walked(corners, faces):
        for j in range(3):
            beside[frozenset((face[j], face[(j + 1) % 3]))].append(face)
    single = sorted(tuple(sorted(edge)) for edge, held in beside.items() if len(held) == 1 and len(edge) == 2 and not flat(corners, held[0]))
    # the tile's side is the neighbour tile's to meet
    single = [(a, b) for a, b in single if not any(abs(corners[a][axis]) > 4.995 and abs(corners[a][axis] - corners[b][axis]) < .005 for axis in (0, 1))]
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
        met = [other for other in np.nonzero((off < ON) & (shared > ON))[0] if other != index]
        if sum(shared[other] for other in met) > SHORT:
            found += [(single[index], single[other]) for other in met]
    return sorted({tuple(sorted(pair)) for pair in found})


def doubled(corners, faces):
    """The walked faces held more than once."""
    return sorted(face for face, times in collections.Counter(tuple(sorted(face)) for face in walked(corners, faces)).items() if times > 1)


TAIL = (0, 0, 0, 0, 4)
CORNERS = np.array([(0, 0, 0), (2, 0, 0), (1, 0, 0), (1, 2, 0), (1, -2, 0), (3, 0, 0)], dtype=float)


class FloorEdges(unittest.TestCase):
    def test_an_edge_met_in_pieces_is_found_and_a_matched_one_is_not(self):
        lower = [(0, 4, 2, *TAIL), (2, 4, 1, *TAIL)]
        self.assertEqual(pieced(CORNERS, [(0, 1, 3, *TAIL), *lower]), [((0, 1), (0, 2)), ((0, 1), (1, 2))])
        self.assertEqual(pieced(CORNERS, [(0, 2, 3, *TAIL), (2, 1, 3, *TAIL), *lower]), [])

    def test_an_edge_met_in_short_pieces_is_found(self):
        self.assertEqual(len(pieced(CORNERS * .25, [(0, 1, 3, *TAIL), (0, 4, 2, *TAIL), (2, 4, 1, *TAIL)])), 2)

    def test_edges_that_only_partly_run_along_each_other_are_found(self):
        self.assertEqual(pieced(CORNERS, [(0, 1, 3, *TAIL), (2, 4, 5, *TAIL)]), [((0, 1), (2, 5))])

    def test_a_face_held_twice_is_found(self):
        self.assertEqual(doubled(CORNERS, [(0, 1, 3, *TAIL), (1, 3, 0, *TAIL), (0, 4, 1, *TAIL)]), [(0, 1, 3)])

    def test_every_tiles_floor_is_matched_in_its_model_and_its_wok(self):
        for pack in PACKS:
            checked = 0
            for source in sorted((REPO / 'sources' / pack).glob('*.mdl')):
                for path in (source, REPO / pack / f'{source.stem}.wok'):  # the game walks the .wok
                    if not path.is_file():
                        continue
                    text = path.read_bytes().decode('cp1252')
                    _, _, nodes = geometry.parse(text if 'beginmodelgeom' in text.lower() else 'beginmodelgeom wok\n' + text)
                    for node in nodes:
                        if node.kind == 'aabb' and node.faces:
                            corners = np.array(node.verts, dtype=float); checked += 1
                            with self.subTest(file=path.name):
                                self.assertEqual(doubled(corners, node.faces), [])
                                found = pieced(corners, node.faces)
                                self.assertEqual(len(found), KNOWN.get(source.stem, 0), f'edges met in pieces (a repaired tile leaves KNOWN): {found}')
            self.assertTrue(checked, f'{pack} has no walkmesh to check')


if __name__ == '__main__':
    unittest.main()
