"""Pure-numpy mesh connectivity helpers shared by inspection, fitting and weighting."""
import numpy as np


def weld_ids(verts, tolerance=1e-6):
    """Ids that merge coincident (seam-split) vertices."""
    keys = np.round(np.asarray(verts, float) / tolerance).astype(np.int64)
    _, ids = np.unique(keys, axis=0, return_inverse=True)
    return ids.reshape(-1)


def union_find(count, pairs):
    parent = np.arange(count)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    return np.array([find(x) for x in range(count)])


def islands(verts, tris, tolerance=1e-5):
    """Face island labels over welded connectivity, plus the welded ids."""
    welded = weld_ids(verts, tolerance)
    pairs = np.concatenate([welded[tris[:, [0, 1]]], welded[tris[:, [1, 2]]]])
    roots = union_find(welded.max() + 1, pairs)
    _, labels = np.unique(roots[welded[tris[:, 0]]], return_inverse=True)
    return labels.reshape(-1), welded


def edges(tris, ids=None):
    ids = np.arange(tris.max() + 1) if ids is None else ids
    pairs = np.concatenate([ids[tris[:, [0, 1]]], ids[tris[:, [1, 2]]], ids[tris[:, [2, 0]]]])
    return np.unique(np.sort(pairs, axis=1), axis=0, return_counts=True)


def slice_loops(verts, tris, axis, value, select=None, welded=None):
    """Connected cross-section components where triangles cross a plane (seam-welded connectivity)."""
    side = verts[:, axis] - value
    ids = welded if welded is not None else np.arange(len(verts))
    signs = side[tris]
    crossing = np.flatnonzero((signs.min(axis=1) < 0) & (signs.max(axis=1) > 0))
    if not len(crossing):
        return []
    owner, pairs = {}, []
    for index in crossing:
        a, b, c = tris[index]
        for u, v in ((a, b), (b, c), (c, a)):
            if (side[u] < 0) != (side[v] < 0):
                key = (min(ids[u], ids[v]), max(ids[u], ids[v]))
                if key in owner:
                    pairs.append((owner[key], index))
                else:
                    owner[key] = index
    local = {index: row for row, index in enumerate(crossing)}
    roots = union_find(len(crossing), [(local[a], local[b]) for a, b in pairs])
    rows = []
    for root in np.unique(roots):
        faces = crossing[roots == root]
        points = cut_points(verts, tris[faces], axis, value)
        if select is not None and not select(points):
            continue
        rows.append({"faces": int(len(faces)), "center": points.mean(0), "min": points.min(0), "max": points.max(0),
                     "points": points})
    return sorted(rows, key=lambda row: float(row["center"][0]))


def cut_points(verts, tris, axis, value):
    """Plane intersection points of the crossing edges of the given triangles."""
    points = []
    for tri in tris:
        for u, v in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            a, b = verts[u], verts[v]
            if (a[axis] - value) * (b[axis] - value) < 0:
                t = (value - a[axis]) / (b[axis] - a[axis])
                points.append(a + t * (b - a))
    return np.array(points)


def neighbours(tris, count, ids=None):
    """Symmetric vertex adjacency as (rows, cols) index arrays over welded ids when given."""
    unique, _ = edges(tris, ids)
    rows = np.concatenate([unique[:, 0], unique[:, 1]])
    cols = np.concatenate([unique[:, 1], unique[:, 0]])
    return rows, cols


def geodesic_labels(points, rows, cols, seeds):
    """Multi-source Dijkstra over edge lengths; returns label index per node (-1 unreachable) and distance."""
    import heapq
    order = np.argsort(rows, kind="stable")
    rows, cols = rows[order], cols[order]
    starts = np.searchsorted(rows, np.arange(len(points) + 1))
    lengths = np.linalg.norm(points[rows] - points[cols], axis=1)
    distance = np.full(len(points), np.inf)
    label = np.full(len(points), -1, dtype=np.int64)
    heap = []
    for index, members in enumerate(seeds):
        for node in members:
            if distance[node] > 0:
                distance[node], label[node] = 0.0, index
                heap.append((0.0, int(node)))
    heapq.heapify(heap)
    while heap:
        d, node = heapq.heappop(heap)
        if d > distance[node]:
            continue
        for k in range(starts[node], starts[node + 1]):
            other, step = cols[k], d + lengths[k]
            if step < distance[other]:
                distance[other], label[other] = step, label[node]
                heapq.heappush(heap, (step, int(other)))
    return label, distance


def smooth_field(field, rows, cols, count, iterations, weight=0.5, fixed=None):
    """Laplacian smoothing of a per-vertex field over adjacency; fixed rows keep their values."""
    field = np.array(field, dtype=float)
    degree = np.bincount(rows, minlength=count).astype(float)
    degree[degree == 0] = 1
    for _ in range(iterations):
        total = np.zeros_like(field)
        np.add.at(total, rows, field[cols])
        mean = total / degree[:, None] if field.ndim == 2 else total / degree
        updated = (1 - weight) * field + weight * mean
        if fixed is not None:
            updated[fixed] = field[fixed]
        field = updated
    return field
