"""Exterior-shell audit, precluster, head-local frame and section helpers. Repair and neck shaping live in neck.py, so
tuning them does not change the code that precluster, export and native bind."""
from pathlib import Path
import time
import numpy as np
from .common import require, positive, library, pin, verify, write
from .gltf import mesh, positions, write_mesh
from .intersections import scan


def physical(vertices, faces):
    corners = np.asarray(vertices)[np.asarray(faces)]
    values, inverse = np.unique(corners.reshape(-1, 3), axis=0, return_inverse=True)
    return values, inverse.reshape(-1, 3)


def topology(vertices, faces):
    return _topology(*physical(vertices, faces))


def _topology(vertices, faces):
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    undirected = np.sort(edges, axis=1)
    _, inverse, counts = np.unique(undirected[:, 0]*np.int64(len(vertices))+undirected[:, 1], return_inverse=True, return_counts=True)
    orientation = np.zeros(len(counts), int)
    np.add.at(orientation, inverse, np.where(edges[:, 0] < edges[:, 1], 1, -1))
    corners = vertices[faces].astype(float)
    areas = np.linalg.norm(np.cross(corners[:, 1]-corners[:, 0], corners[:, 2]-corners[:, 0]), axis=1)
    boundary = int(np.count_nonzero(counts == 1)); nonmanifold = int(np.count_nonzero(counts > 2))
    winding = int(np.count_nonzero((counts == 2) & (orientation != 0)))
    # Every vertex link on the supported closed shell must be one simple cycle: each link node of degree two, one component.
    owner = np.concatenate(faces.T); link = np.concatenate([faces[:, [1, 2]], faces[:, [2, 0]], faces[:, [0, 1]]])
    keys, node = np.unique(np.r_[owner, owner]*np.int64(len(vertices))+link.T.reshape(-1), return_inverse=True)
    node = node.reshape(2, -1); count = len(keys); held = keys//len(vertices)
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    labels = connected_components(coo_matrix((np.ones(node.shape[1]), (node[0], node[1])), (count, count)), directed=False)[1]
    cycles = np.bincount(held[np.unique(labels, return_index=True)[1]], minlength=len(vertices))
    bad_links = int(np.count_nonzero((cycles != 1) | (np.bincount(held, np.bincount(node.reshape(-1), minlength=count) != 2, len(vertices)) > 0)))
    zeros = int(np.count_nonzero(areas <= 1e-14))
    return {'triangles': len(faces), 'physicalVertices': len(vertices), 'boundaryEdges': boundary,
            'nonmanifoldEdges': nonmanifold, 'windingConflicts': winding, 'zeroAreaFaces': zeros,
            'invalidVertexLinks': bad_links, 'closed': not (boundary or nonmanifold or winding or zeros or bad_links)}


def audit(path, max_pairs=4000000):
    value = mesh(path); vertices, faces = physical(value['positions'], value['faces'])
    top = _topology(vertices, faces); crossings = scan(vertices, faces, max_pairs=max_pairs)
    return {'source': pin(path), 'topology': top, 'crossings': crossings,
            'passed': top['closed'] and crossings['complete'] and not crossings['pairs'],
            'visualReviewRequired': True}


BLOCK = 1 << 22  # precluster rows per block for the float temporaries


def precluster(source, output, bindings, resolution=512):
    """Bound CPU source size before the 768 UDF remesh; preserve this source separately."""
    require(type(resolution) is int and 64 <= resolution <= 2048, 'Declared precluster resolution required')
    vertices, faces = positions(source); before = len(faces)
    lo = vertices.min(0); size = float(np.max(np.ptp(vertices, axis=0)))
    positive(size, 'mesh extent')
    # One int64 key per cell, axis by axis: cells are 0..resolution, so the packed key sorts exactly like the (x, y, z)
    # rows np.unique(axis=0) sorted, at a fraction of the memory; float temporaries run in blocks (byte-identical output)
    bits = resolution.bit_length(); key = np.zeros(len(vertices), np.int64)
    for axis in range(3):
        key <<= bits; key |= np.floor((vertices[:, axis]-lo[axis]) / size * resolution).astype(np.int64)
    _, groups = np.unique(key, return_inverse=True); del key
    count = int(groups.max())+1; clustered = np.zeros((count, 3), float); np.add.at(clustered, groups, vertices)
    clustered /= np.bincount(groups)[:, None]
    result = groups.astype(np.int32 if count < 2**31 else np.int64)[faces]; del faces
    a, b, c = result[:, 0], result[:, 1], result[:, 2]; result = result[(a != b) & (b != c) & (a != c)]
    require(len(result) > 0, 'Precluster removed all faces')
    # First occurrence of each corner set, in source order (np.unique's stable return_index)
    ordered = np.sort(result, axis=1); order = np.lexsort((ordered[:, 2], ordered[:, 1], ordered[:, 0]))
    ordered = ordered[order]; fresh = np.ones(len(order), bool); fresh[1:] = (ordered[1:] != ordered[:-1]).any(1); del ordered
    result = result[np.sort(order[fresh])]; del order, fresh
    def nonzero(tri):return np.linalg.norm(np.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0]), axis=1) > 0
    result = result[np.concatenate([nonzero(clustered[result[i:i+BLOCK]]) for i in range(0, len(result), BLOCK)])]
    movement = max(float(np.max(np.linalg.norm(clustered[groups[i:i+BLOCK]]-vertices[i:i+BLOCK], axis=1)))
                   for i in range(0, len(vertices), BLOCK))
    diagonal=float(np.linalg.norm(np.ptp(vertices,axis=0)));require(movement/diagonal<=.004,'Precluster assigned-vertex displacement exceeds .4%')
    del groups, vertices
    used,inverse=np.unique(result,return_inverse=True);clustered=clustered[used];result=inverse.reshape(-1,3)
    igl=library(bindings,'igl');result,components=igl.bfs_orient(np.asarray(result,np.int32))
    tri=clustered[result];volumes=np.bincount(components,weights=np.einsum('ij,ij->i',tri[:,0],np.cross(tri[:,1],tri[:,2]))/6)
    del tri;flipped=volumes[components]<0;result[flipped]=result[flipped][:,[0,2,1]]
    write_mesh(output, clustered, result)
    return {'source': pin(source), 'output': pin(output), 'resolution': resolution,
            'maximumAssignedVertexMovementRelativeToDiagonal':movement/diagonal,'notFullHausdorffBound':True,
            'beforeTriangles': before, 'afterTriangles': len(result), 'visualReviewRequired': True}


BASIS = np.array([[1., 0, 0, 0], [0, 0, -1., 0], [0, 1., 0, 0], [0, 0, 0, 1.]])  # GLB -> NWN (x,-z,y)


def checked_fit(matrix):
    matrix = np.asarray(matrix, float)
    require(matrix.shape == (4, 4) and np.isfinite(matrix).all() and np.allclose(matrix[3], [0, 0, 0, 1]), 'Invalid fit transform')
    gram = matrix[:3, :3].T @ matrix[:3, :3]
    require(np.linalg.det(matrix[:3, :3]) > 0 and np.allclose(gram, np.eye(3)*gram[0, 0], atol=1e-8),
            'Fit must be a positive uniform similarity')
    return matrix


def transform(matrix, points):
    return (np.c_[points, np.ones(len(points))] @ np.asarray(matrix).T)[:, :3]


def section(local, faces, z):
    """Horizontal section of a triangle mesh at height z as (n, 2, 2) xy segments."""
    tri = local[faces]; s = tri[:, :, 2]-z; above = s > 0; keep = above.sum(1) % 3 != 0
    tri, s, above = tri[keep], s[keep], above[keep]; points, cuts = [], []
    for a, b in ((0, 1), (1, 2), (2, 0)):
        cut = above[:, a] != above[:, b]; w = np.where(cut, s[:, a]/np.where(cut, s[:, a]-s[:, b], 1), 0)
        points.append(tri[:, a, :2]+w[:, None]*(tri[:, b, :2]-tri[:, a, :2])); cuts.append(cut)
    order = np.argsort(~np.stack(cuts, 1), axis=1, kind='stable')[:, :2]
    return np.take_along_axis(np.stack(points, 1), order[:, :, None], 1)


def enclosed(segments, centre, bins=720):
    """True when the section sweeps every angle around centre: a closed ring, independent of density."""
    if not len(segments): return False
    a = np.arctan2(segments[..., 1]-centre[1], segments[..., 0]-centre[0])
    d = (a[:, 1]-a[:, 0]+np.pi) % (2*np.pi)-np.pi; low = np.where(d >= 0, a[:, 0], a[:, 1])
    start = np.floor((low+np.pi)/(2*np.pi)*bins).astype(int); end = np.floor((low+np.abs(d)+np.pi)/(2*np.pi)*bins).astype(int)
    first = start % bins; last = first+end-start
    marks = np.zeros(2*bins+1, int); np.add.at(marks, first, 1); np.add.at(marks, last+1, -1)
    run = np.cumsum(marks)[:2*bins]
    return bool(np.all(run[:bins]+run[bins:] > 0))


def shells(vertices, faces):
    """Face labels of the edge-connected shells."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]); n = len(vertices)
    labels = connected_components(coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), (n, n)), directed=False)[1]
    return np.unique(labels[faces[:, 0]], return_inverse=True)[1].reshape(-1)


class ShellReview(ValueError):
    """A refused shell selection that carries the master's shell table, so the refused receipt is the review evidence
    (the runner stores `attempts`) and no further launch is needed to see the shells."""
    def __init__(self, message, table):
        super().__init__(message); self.attempts = {'shells': table}


def select_shells(vertices, faces, selection, inside=None):
    """A master must be one shell. Detached floaters and interior bubbles go only by a reviewed selection that keeps
    the largest-area shell, bounds the deleted area and records every deleted shell. Every refusal carries the shell
    table (triangles, area fraction, centroid and box per extra shell, largest first). With `inside` (winding numbers of
    points against the kept shell: repair passes igl's) each extra shell also records `insideFraction`, and a selection
    with `interiorOnly: true` deletes only shells lying wholly inside the kept shell (Alpha Wrap bubbles under hair):
    nothing visible can go, so a reviewed area bound up to 5% is enough evidence."""
    label = shells(vertices, faces); count = int(label.max())+1
    if selection is None and count == 1:
        return vertices, faces, {'shells': 1, 'deleted': [], 'deletedAreaFraction': 0.0}
    corners = vertices[faces].astype(float)
    area = np.linalg.norm(np.cross(corners[:, 1]-corners[:, 0], corners[:, 2]-corners[:, 0]), axis=1)/2
    totals = np.bincount(label, area, count); keep = int(np.argmax(totals)); fraction = float(1-totals[keep]/totals.sum())
    interior = isinstance(selection, dict) and selection.get('interiorOnly') is True
    def row(k):
        points = vertices[np.unique(faces[label == k])]
        out = {'triangles': int(np.count_nonzero(label == k)), 'areaFraction': float(totals[k]/totals.sum()),
               'centroid': [round(float(c), 5) for c in points.mean(0)],
               'box': [[round(float(c), 5) for c in points.min(0)], [round(float(c), 5) for c in points.max(0)]]}
        if inside is not None:
            try:out['insideFraction'] = float(np.mean(np.abs(np.asarray(inside(np.asarray(vertices, float), faces[label == keep], np.asarray(points, float)))) > .5))
            except Exception:
                if interior:raise  # evidence-only otherwise: a missing library never blocks a refusal from reporting its table
        return out
    deleted = [row(k) for k in np.argsort(-totals) if k != keep]
    def refuse(message):
        summary = '; '.join(f"{r['areaFraction']:.4%} at {r['centroid']}" for r in deleted[:4])
        raise ShellReview(f'{message} (extra shells, largest first: {summary})', {'count': count, 'deletedAreaFraction': fraction, 'extra': deleted})
    if selection is None:
        refuse(f'Master has {count} separate shells; review them and declare mesh.components')
    if not (isinstance(selection, dict) and selection.get('keep') == 'largest' and selection.get('reviewed') is True):
        refuse('Shell selection must be reviewed and keep the largest shell')
    limit = positive(selection.get('maximumDeletedAreaFraction', .01), 'deleted shell area bound')
    require(limit <= .05, 'Deleted shell area bound exceeds supported profile')
    if fraction > limit:refuse(f'Deleted shells cover {fraction:.3%} of the master area, above the reviewed bound')
    expected = selection.get('expectedDeleted')
    if not (expected is None or expected == len(deleted)):refuse(f'{len(deleted)} shells would be deleted; the review expected {expected}')
    if interior:
        require(inside is not None, 'interiorOnly needs the winding-number test (repair supplies it)')
        if any(r['insideFraction'] < 1 for r in deleted):refuse('interiorOnly: a shell to delete is not wholly inside the kept shell')
    deleted = [{k: v for k, v in r.items() if k != 'box'} for r in deleted]  # the success record keeps its earlier shape
    used = np.unique(faces[label == keep]); remap = np.full(len(vertices), -1); remap[used] = np.arange(len(used))
    return vertices[used], remap[faces[label == keep]], {'shells': count, 'deleted': deleted, 'deletedAreaFraction': fraction,
                                                        'keptTriangles': int(np.count_nonzero(label == keep))}

