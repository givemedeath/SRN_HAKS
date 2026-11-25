"""No tile's floor has an edge its neighbours meet in pieces (a T-junction): the game joins faces edge by edge, so a
creature walks round such an edge instead of across it (reproduced in the client with a Human and a Troll, 2026-11-25)."""
import collections
import unittest
from pathlib import Path

import numpy as np

from tools.tilekit import geometry

REPO = Path(__file__).resolve().parents[2]
PACKS = ('srn_t_common', 'srn_t_dgt04', 'srn_t_fcx01', 'srn_t_srx01', 'srn_t_udp1')  # the packs with sources: named so the test selector runs this when one changes
ON = .008  # how far from an edge, in metres, a corner still lies on it
SHORT = .3  # edges shorter than this, in metres, are narrower than a creature's way past them


def pieced(corners, faces):
    """The unmatched inner edges of the walked `faces` that other unmatched edges run along in pieces."""
    place = {}; same = [place.setdefault(tuple(np.round(corner, 3)), index) for index, corner in enumerate(corners)]
    walked = [[same[index] for index in face[:3]] for face in faces if face[7] in geometry.WALKABLE]
    count = collections.Counter(frozenset((face[j], face[(j + 1) % 3])) for face in walked for j in range(3))
    single = {edge for edge, times in count.items() if times == 1 and len(edge) == 2}
    ends = sorted({index for edge in single for index in edge}); at = corners[ends] if ends else corners[:0]; found = []
    for a, b in map(sorted, single):
        p, span = corners[a], corners[b] - corners[a]; length = span @ span
        if length < SHORT * SHORT or any(abs(p[axis]) > 4.995 and abs(span[axis]) < .005 for axis in (0, 1)):  # the tile's side is the neighbour tile's to meet
            continue
        share = (at - p) @ span / length; off = np.linalg.norm(p + np.outer(share, span) - at, axis=1)
        inner = sorted((share[i], ends[i]) for i in np.nonzero((share > .001) & (share < .999) & (off < ON))[0] if ends[i] not in (a, b))
        chain = [a, *(index for _, index in inner), b]
        if inner and all(frozenset(pair) in single for pair in zip(chain, chain[1:])):
            found.append((p.round(2).tolist(), corners[b].round(2).tolist()))
    return found


class FloorEdges(unittest.TestCase):
    def test_an_edge_met_in_pieces_is_found_and_a_matched_one_is_not(self):
        corners = np.array([(0, 0, 0), (2, 0, 0), (1, 0, 0), (1, 2, 0), (1, -2, 0)], dtype=float); tail = (0, 0, 0, 0, 4)
        lower = [(0, 4, 2, *tail), (2, 4, 1, *tail)]
        self.assertEqual(pieced(corners, [(0, 1, 3, *tail), *lower]), [([0, 0, 0], [2, 0, 0])])
        self.assertEqual(pieced(corners, [(0, 2, 3, *tail), (2, 1, 3, *tail), *lower]), [])

    def test_every_tiles_floor_edges_are_matched(self):
        for pack in PACKS:
            for path in sorted((REPO / 'sources' / pack).glob('*.mdl')):
                _, _, nodes = geometry.parse(path.read_bytes().decode('cp1252'))
                for node in nodes:
                    if node.kind == 'aabb' and node.faces:
                        with self.subTest(model=path.name):
                            self.assertEqual(pieced(np.array(node.verts, dtype=float), node.faces), [])


if __name__ == '__main__':
    unittest.main()
