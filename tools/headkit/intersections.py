"""Bounded, exact narrow-phase crossing checks from the successful head route."""
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from itertools import chain, islice
import numpy as np

def _cross2(a, b):
    return a[..., 0]*b[..., 1]-a[..., 1]*b[..., 0]

def crossing_pairs(a, b, eps=1e-10):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.shape != b.shape or a.ndim != 3 or a.shape[1:] != (3, 3) or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('finite paired Nx3x3 triangles required')
    if not np.isfinite(eps) or eps <= 0:
        raise ValueError('positive finite epsilon required')
    na = np.cross(a[:, 1]-a[:, 0], a[:, 2]-a[:, 0])
    nb = np.cross(b[:, 1]-b[:, 0], b[:, 2]-b[:, 0])
    la, lb = np.linalg.norm(na, axis=1), np.linalg.norm(nb, axis=1)
    da = np.einsum('nij,nj->ni', b-a[:, :1], na)
    db = np.einsum('nij,nj->ni', a-b[:, :1], nb)
    valid = (la > eps) & (lb > eps)
    separated = (np.all(da > eps, 1) | np.all(da < -eps, 1) |
                 np.all(db > eps, 1) | np.all(db < -eps, 1))
    parallel = np.linalg.norm(np.cross(na, nb), axis=1) <= eps*la*lb
    result = np.zeros(len(a), bool)
    cop = np.flatnonzero(valid & ~separated & parallel & (np.max(np.abs(da), 1) <= eps*la))
    if len(cop):
        axis = np.argmax(np.abs(na[cop]), 1)
        xy = np.asarray([[1, 2], [0, 2], [0, 1]])[axis]
        aa = np.take_along_axis(a[cop], xy[:, None, :], 2)
        bb = np.take_along_axis(b[cop], xy[:, None, :], 2)
        hit = np.zeros(len(cop), bool)
        for i in range(3):
            p, q = aa[:, i], aa[:, (i+1)%3]
            for j in range(3):
                r, s = bb[:, j], bb[:, (j+1)%3]
                o1, o2 = _cross2(q-p, r-p), _cross2(q-p, s-p)
                o3, o4 = _cross2(s-r, p-r), _cross2(s-r, q-r)
                hit |= (o1*o2 < -eps*eps) & (o3*o4 < -eps*eps)
        for points, tri in ((aa.mean(1), bb), (bb.mean(1), aa)):
            signs = np.stack([_cross2(tri[:, (i+1)%3]-tri[:, i], points-tri[:, i]) for i in range(3)], 1)
            hit |= np.all(signs > eps, 1) | np.all(signs < -eps, 1)
        result[cop] = hit
    ids = np.flatnonzero(valid & ~separated & ~parallel)
    if len(ids):
        aa, bb = a[ids], b[ids]
        hit = np.zeros(len(ids), bool)
        for tri, other in ((aa, bb), (bb, aa)):
            e1, e2 = other[:, 1]-other[:, 0], other[:, 2]-other[:, 0]
            for i in range(3):
                start, end = tri[:, i], tri[:, (i+1)%3]
                d = end-start
                h = np.cross(d, e2)
                det = np.einsum('ij,ij->i', e1, h)
                eligible = np.abs(det) > eps
                inv = np.divide(1., det, out=np.zeros_like(det), where=eligible)
                s = start-other[:, 0]
                u = inv*np.einsum('ij,ij->i', s, h)
                q = np.cross(s, e1)
                v = inv*np.einsum('ij,ij->i', d, q)
                t = inv*np.einsum('ij,ij->i', e2, q)
                hit |= eligible & (u >= -eps) & (u <= 1+eps) & (v >= -eps) & (u+v <= 1+eps) & (t > eps) & (t < 1-eps)
        result[ids] = hit
    return result

def _validated_mesh(p, f):
    p, f = np.asarray(p, float), np.asarray(f)
    if p.ndim != 2 or p.shape[1] != 3 or f.ndim != 2 or f.shape[1] != 3 or not len(f) or not np.issubdtype(f.dtype, np.integer) or f.min() < 0 or f.max() >= len(p) or not np.isfinite(p).all():
        raise ValueError('finite mesh with valid triangle indices required')
    return p, f

def _broad_phase(p, f, eps, chunk, tree_factory, block):
    if tree_factory is None:
        from scipy.spatial import cKDTree
        tree_factory = cKDTree
    p, f = _validated_mesh(p, f)
    if type(chunk) is not int or chunk < 1 or type(block) is not int or block < 1 or not np.isfinite(eps) or eps <= 0:
        raise ValueError('positive chunk, block and epsilon required')
    tri = p[f]
    centers = tri.mean(1)
    radii = np.linalg.norm(tri-centers[:, None], axis=2).max(1)
    if np.any(radii <= 0):
        raise ValueError('zero-radius triangle')
    lo, hi = tri.min(1), tri.max(1)
    bins = np.floor(np.log2(radii)).astype(int)
    guard = 2*np.sqrt(3)*eps + 64*np.finfo(float).eps*max(1., float(np.abs(p).max()))
    step = chunk*max(1, block//chunk)
    def blocks():
        for group in np.unique(bins):
            target_ids = np.flatnonzero(bins == group)
            tree = tree_factory(centers[target_ids])
            maximum = float(radii[target_ids].max())
            yield from ((tree, target_ids, maximum, base, min(base+step, len(f))) for base in range(0, len(f), step))
    def candidates(item, workers=1):
        # One query per block of whole chunks (rows are independent); faces from the group's last target on cannot pair.
        tree, target_ids, maximum, base, end = item
        ids = np.arange(base, min(end, int(target_ids[-1]))); left = right = np.empty(0, np.int64)
        if len(ids):
            query_radius = np.nextafter(radii[ids]+maximum+guard, np.inf)
            neighbors = tree.query_ball_point(centers[ids], query_radius, eps=0., workers=workers)
            counts = np.fromiter(map(len, neighbors), np.int64, len(ids))
            left = np.repeat(ids, counts); right = target_ids[np.fromiter(chain.from_iterable(neighbors), np.int64, int(counts.sum()))]
            keep = left < right
            left, right = left[keep], right[keep]
            keep = np.all(hi[left]+eps >= lo[right], 1) & np.all(hi[right]+eps >= lo[left], 1)
            left, right = left[keep], right[keep]
        return np.stack((left, right), 1), np.searchsorted(left, np.r_[np.arange(base, end, chunk), end])
    return tri, blocks(), candidates

def sphere_aabb_pairs(p, f, *, eps=1e-10, chunk=64, tree_factory=None, block=16384, workers=1):
    _, blocks, candidates = _broad_phase(p, f, eps, chunk, tree_factory, block)
    for item in blocks:
        pairs, bounds = candidates(item, workers)
        yield from (pairs[a:b] for a, b in zip(bounds[:-1], bounds[1:]))

def scan(p, f, *, eps=1e-10, max_pairs=4000000, progress=None, workers=4, block=16384):
    if type(max_pairs) is not int or max_pairs < 0:
        raise ValueError('nonnegative pair cap required')
    if type(workers) is not int or workers < 1:
        raise ValueError('positive worker count required')
    p, f = _validated_mesh(p, f)
    if not np.isfinite(eps) or eps <= 0:
        raise ValueError('positive finite epsilon required')
    tri = p[f]
    area = np.linalg.norm(np.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0]), axis=1)
    if np.any(area <= eps):
        raise ValueError('degenerate triangles prevent strict diagnostic scan')
    begun = time.monotonic()
    tri, blocks, candidates = _broad_phase(p, f, eps, 64, None, block)
    def task(item):
        pairs, bounds = candidates(item)
        return pairs, bounds, crossing_pairs(tri[pairs[:, 0]], tri[pairs[:, 1]], eps) if len(pairs) else np.zeros(0, bool)
    checked, hits, batches, queue = 0, [], 0, deque()
    with ThreadPoolExecutor(workers) as pool:
        # Blocks finish out of order but are consumed in chunk order, so cap, progress and pair order match one chunk at a time.
        fill = lambda: queue.extend(pool.submit(task, item) for item in islice(blocks, 2*workers-len(queue)))
        fill()
        while queue:
            pairs, bounds, hit = queue.popleft().result(); fill()
            sizes = np.diff(bounds); total = checked+np.cumsum(sizes); over = np.flatnonzero(total > max_pairs)
            stop = int(over[0]) if len(over) else len(sizes)
            if progress:
                for k in range(stop):
                    if (batches+k+1) % 50 == 0:
                        progress({'candidatePairs': int(total[k]), 'intersectionPairs': len(hits)+int(np.count_nonzero(hit[:bounds[k+1]])), 'batches': batches+k+1, 'elapsedSeconds': time.monotonic()-begun})
            hits.extend(pairs[:bounds[stop]][hit[:bounds[stop]]].tolist())
            if len(over):
                for future in queue: future.cancel()
                return {'complete': False, 'reason': 'resource-pair-cap', 'pairs': hits,
                        'candidatePairs': int(total[stop]-sizes[stop]), 'nextBatchPairs': int(sizes[stop]), 'limit': max_pairs,
                        'elapsedSeconds': time.monotonic()-begun, 'visualApproval': False}
            checked, batches = int(total[-1]) if len(total) else checked, batches+len(sizes)
    return {'complete': True, 'method': 'log2-binned-enclosing-spheres-exact-expanded-AABB-vectorized-strict-interior',
            'scopeFaces': len(f), 'pairs': hits, 'candidatePairs': checked, 'limit': max_pairs,
            'epsilon': eps, 'elapsedSeconds': time.monotonic()-begun,
            'visualApproval': False, 'geometryAcceptance': False, 'productionAcceptance': False}
