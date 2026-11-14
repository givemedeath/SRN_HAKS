"""A part over its triangle budget, brought under it by taking vertices out of its surface one at a time.

Each step takes one vertex out by folding it into a neighbour that stays where it is (a half-edge collapse): no
vertex that is kept moves, so whatever a kept vertex carries (the columns the split gave it, its place on a
joint's end) is unchanged, and every face that is kept is the face it was with one corner moved to a
neighbour. The vertex whose loss changes the surface least goes first, as the sum of its squared distances
from the planes of the faces round both vertices measures it (Garland and Heckbert's quadrics). A step that
would fold a face over, leave one with no area, part the surface or join two faces that only touched there is
not taken; nor is one that moves the surface more than `SHIFT` from where the lost vertex was.

A part's rim, where its surface ends, may lose points too when `lines` is given, and so may a line of points
on a cut inside the surface (where a cap meets the part on a joint's plane): a point is folded into one of the
two beside it on its rim or its line, where the edge left runs within `RIM_SHIFT` of it and of every point that
edge has lost before, and only into a
neighbour that lies on every cut it lay on, as the point beyond does. A rim or an end on a joint's plane then
stays on the plane, and a corner where it turns from one cut onto another stays. A part cut from a dense mesh,
its closings and caps built on it, was otherwise left with every point of its rims and ends (Facility
Security from 200,000 faces, 2026-11-13)."""
import heapq

import numpy as np

from .registry import require

SHIFT = 0.004  # metres: a vertex is taken out only where the faces it leaves lie this near it
FOLD = 0.2  # a face a step changes may turn this far at most: the cosine between its normals before and after
THIN = 1e-10  # square metres: a face a step leaves smaller than this has no area to speak of
RIM_SHIFT = 0.002  # metres: a point of a rim is taken out only where the rim left runs this near it


def _planes(points, faces):
    """Per face: its unit normal, its plane's offset and its area."""
    a, b, c = (points[faces[:, i]] for i in range(3))
    cross = np.cross(b - a, c - a)
    area = np.linalg.norm(cross, axis=1) / 2
    normal = cross / np.maximum(2 * area, 1e-30)[:, None]
    return normal, -(normal * a).sum(axis=1), area


def reduce(vertices, faces, target, locked=None, lines=None):
    """(kept, faces, which): `vertices` and `faces` with vertices taken out until `target` faces or fewer are
    left, or no step more may be taken. `kept` indexes the vertices given that are left, in order; `faces` are
    the faces left, numbered into `kept`; `which[i]` is the face given that face i is, one of its corners
    perhaps moved. A vertex `locked` flags stays, and so does every vertex on an edge more than two faces have.
    So does every vertex on an edge only one face has (an end, a hole), unless `lines` gives, per vertex, a bit
    for each cut it lies on (0 for none): a rim's points may then be taken out along the rim (above)."""
    points, faces = np.asarray(vertices, float), np.asarray(faces, int)
    require(points.ndim == 2 and points.shape[1] == 3 and faces.ndim == 2 and faces.shape[1] == 3, 'Vertices are points and faces triangles')
    require(target >= 0, 'A face budget is zero or more')
    stays = np.zeros(len(points), bool) if locked is None else np.array(locked, bool)
    require(stays.shape == (len(points),), 'One lock flag per vertex')
    edges = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    unique, count = np.unique(edges, axis=0, return_counts=True)
    rim = np.zeros(len(points), bool)
    if lines is None:
        stays[unique[count != 2].ravel()] = True  # an end, a hole or a fin stays as it is
    else:
        lines = np.asarray(lines, np.int64)
        require(lines.shape == (len(points),), 'One set of cuts per vertex')
        stays[unique[count > 2].ravel()] = True  # a fin stays as it is
        rim[unique[count == 1].ravel()] = True
    normal, offset, area = _planes(points, faces)
    plane = np.concatenate([normal, offset[:, None]], axis=1)
    quadric = np.zeros((len(points), 4, 4))
    for corner in range(3):
        np.add.at(quadric, faces[:, corner], area[:, None, None] * plane[:, :, None] * plane[:, None, :])
    corners = faces.tolist()
    alive = np.ones(len(faces), bool)
    around = [set() for _ in points]
    for index, face in enumerate(corners):
        for vertex in face:
            around[vertex].add(index)
    gone = np.zeros(len(points), bool)
    stamp = np.zeros(len(points), int)
    heap = []

    def neighbours(vertex):
        return {other for index in around[vertex] for other in corners[index] if other != vertex}

    def along_rim(vertex):
        """The points beside `vertex` on its rim: those it shares an edge with that one face alone has."""
        uses = {}
        for index in around[vertex]:
            for other in corners[index]:
                if other != vertex:
                    uses[other] = uses.get(other, 0) + 1
        return [other for other, number in uses.items() if number == 1]

    run_of = {}  # a rim's or line's edge -> the points it lost there, folded into it one by one

    def edge(a, b):
        return (a, b) if a < b else (b, a)

    def straight(source, sink):
        """Where its rim or its line may lose `source` into `sink`: None if it may not, else the edge left there
        (sink, beyond), or () where it lies on its cuts all round. They are beside each other on it, what is left
        runs within `RIM_SHIFT` of the point and of every point the two edges lost before, and both ends of that
        lie on every cut the point lay on. Bounding the last point alone let a run of folds sag the edge past
        `RIM_SHIFT` (CI, 2026-11-14)."""
        if lines[source] & ~lines[sink]:
            return None
        if rim[source]:
            beside = along_rim(source)
        else:  # along its line: the edges where the surface leaves the cuts it lies on (a lid's rim, where a cap meets the part)
            off = lambda index: any(lines[corner] & lines[source] != lines[source] for corner in corners[index])
            beside = [other for other in neighbours(source) if lines[other] & lines[source] == lines[source]
                      and any(off(index) for index in around[source] if other in corners[index])]
            if not beside:
                return ()  # all round it lies on its cuts (a lid on a joint's plane): it stays on them wherever it goes
        if len(beside) != 2 or sink not in beside:
            return None
        beyond = beside[0] if beside[1] == sink else beside[1]
        if lines[source] & ~(lines[sink] & lines[beyond]):
            return None
        lost = points[[source, *run_of.get(edge(sink, source), ()), *run_of.get(edge(source, beyond), ())]]
        run = points[beyond] - points[sink]
        share = np.clip((lost - points[sink]) @ run / max(float(run @ run), 1e-24), 0.0, 1.0)
        far = np.linalg.norm(points[sink] + share[:, None] * run - lost, axis=1).max()
        return (sink, beyond) if float(far) <= RIM_SHIFT else None

    def offer(source, sink):
        if stays[source] or gone[source] or gone[sink]:
            return
        at = np.append(points[sink], 1.0)
        heapq.heappush(heap, (float(at @ (quadric[source] + quadric[sink]) @ at), stamp[source], stamp[sink], source, sink))

    for a, b in unique[count <= 2].tolist():  # a rim's edges too: its points stay but where `lines` lets them go
        offer(a, b)
        offer(b, a)
    left = int(alive.sum())
    while left > target and heap:
        _, mark_source, mark_sink, source, sink = heapq.heappop(heap)
        if gone[source] or gone[sink] or stamp[source] != mark_source or stamp[sink] != mark_sink:
            continue
        shared = [index for index in around[source] if sink in corners[index]]
        on_line = rim[source] or (lines is not None and lines[source] != 0)
        left_edge = straight(source, sink) if on_line else ()
        if len(shared) != (1 if rim[source] else 2) or left_edge is None:
            continue  # a point of a rim or a cut goes only along it
        opposite = {vertex for index in shared for vertex in corners[index]} - {source, sink}
        if neighbours(source) & neighbours(sink) != opposite:
            continue  # folding them would join two faces that only touch at a vertex there
        moved = [index for index in around[source] if index not in shared]
        good = True
        for index in moved:
            before = points[corners[index]]
            after = np.array([points[sink] if vertex == source else points[vertex] for vertex in corners[index]])
            was = np.cross(before[1] - before[0], before[2] - before[0])
            now = np.cross(after[1] - after[0], after[2] - after[0])
            size = np.linalg.norm(now)
            if size / 2 < THIN or now @ was < FOLD * size * np.linalg.norm(was) or abs((points[source] - after[0]) @ now) > SHIFT * size:
                good = False
                break
        if not good:
            continue
        for index in shared:
            alive[index] = False
            for vertex in corners[index]:
                around[vertex].discard(index)
        for index in moved:
            corners[index] = [sink if vertex == source else vertex for vertex in corners[index]]
            around[sink].add(index)
        if left_edge:
            _, beyond = left_edge
            run_of[edge(sink, beyond)] = [*run_of.pop(edge(sink, beyond), ()), source,
                                          *run_of.pop(edge(sink, source), ()), *run_of.pop(edge(source, beyond), ())]
        around[source] = set()
        gone[source] = True
        quadric[sink] += quadric[source]
        left -= len(shared)
        stamp[sink] += 1  # every step into or out of it costs anew
        for vertex in neighbours(sink):  # and a step here refused before may be taken now
            for other in neighbours(vertex):
                offer(vertex, other)
                offer(other, vertex)
    which = np.flatnonzero(alive)
    kept = np.flatnonzero(~gone)
    number = np.full(len(points), -1)
    number[kept] = np.arange(len(kept))
    return kept, number[np.array([corners[index] for index in which], int).reshape(-1, 3)], which
