"""The faults of a tile's floor that bend or stop a creature's route (walked in the client with a Human and a Troll,
2026-11-25): an edge its neighbours meet in pieces (a T-junction, or corners that miss each other), a face held twice, a
face of no area on an edge between two others, and a floor that ends just short of its tile's side. The game joins
walked faces edge by edge, so a creature walks round such a place instead of across it. `test_floor_edges` holds the
packs to them; `walk` sends walkers across what they find."""
import collections

import numpy as np

from . import geometry

ON = .04  # how far from an edge, in metres, another still lies along it
SHORT = .3  # an edge met along less than this, in metres, is narrower than a creature's way past it


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
                along = abs(a[axis] - b[axis]) < .02 and abs(a[1 - axis] - b[1 - axis]) > SHORT and a[axis] * b[axis] > 0
                inside = 4.95 < min(abs(a[axis]), abs(b[axis])) < 4.995 and max(abs(a[axis]), abs(b[axis])) < 5.002
                if abs(up[2]) > .3 * np.linalg.norm(up) and along and inside:
                    found.append(tuple(sorted(edge)))
    return sorted(found)


def pinched(corners, faces):
    """The edges between two walked faces on which a face of no area lies too."""
    return sorted(tuple(sorted(edge)) for edge, held in edges(corners, faces).items()
                  if len(edge) == 2 and any(flat(corners, face) for face in held) and sum(not flat(corners, face) for face in held) > 1)


def doubled(corners, faces):
    """The walked faces held more than once."""
    return sorted(face for face, times in collections.Counter(tuple(sorted(face)) for face in numbered(corners, faces)).items() if times > 1)
