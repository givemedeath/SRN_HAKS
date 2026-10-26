"""Exterior-shell audit, precluster, head-local frame and section helpers. Repair and neck shaping live in neck.py, so
tuning them does not change the code that precluster, export and native bind."""
from pathlib import Path
import time
import numpy as np
from .common import require, positive, library, pin, verify, write
from .gltf import mesh, write_mesh
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


def precluster(source, output, bindings, resolution=512):
    """Bound CPU source size before the 768 UDF remesh; preserve this source separately."""
    require(type(resolution) is int and 64 <= resolution <= 2048, 'Declared precluster resolution required')
    original = mesh(source); vertices, faces = original['positions'],original['faces']
    lo = vertices.min(0); size = float(np.max(np.ptp(vertices, axis=0)))
    positive(size, 'mesh extent')
    cells = np.floor((vertices-lo) / size * resolution).astype(np.int64)
    _, groups = np.unique(cells, axis=0, return_inverse=True)
    clustered = np.zeros((groups.max()+1, 3), float); np.add.at(clustered, groups, vertices)
    clustered /= np.bincount(groups)[:, None]; result = groups[faces]
    keep = np.all(np.diff(np.sort(result, axis=1), axis=1) != 0, axis=1); result = result[keep]
    require(len(result) > 0, 'Precluster removed all faces')
    _,first=np.unique(np.sort(result,axis=1),axis=0,return_index=True);result=result[np.sort(first)]
    tri=clustered[result];result=result[np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)>0]
    movement=float(np.max(np.linalg.norm(clustered[groups]-vertices,axis=1)))
    diagonal=float(np.linalg.norm(np.ptp(vertices,axis=0)));require(movement/diagonal<=.004,'Precluster assigned-vertex displacement exceeds .4%')
    used,inverse=np.unique(result,return_inverse=True);clustered=clustered[used];result=inverse.reshape(-1,3)
    igl=library(bindings,'igl');result,components=igl.bfs_orient(np.asarray(result,np.int32))
    tri=clustered[result];volumes=np.bincount(components,weights=np.einsum('ij,ij->i',tri[:,0],np.cross(tri[:,1],tri[:,2]))/6)
    flipped=volumes[components]<0;result[flipped]=result[flipped][:,[0,2,1]]
    write_mesh(output, clustered, result)
    return {'source': pin(source), 'output': pin(output), 'resolution': resolution,
            'maximumAssignedVertexMovementRelativeToDiagonal':movement/diagonal,'notFullHausdorffBound':True,
            'beforeTriangles': len(faces), 'afterTriangles': len(result), 'visualReviewRequired': True}


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


def select_shells(vertices, faces, selection):
    """A master must be one shell. Detached floaters and interior bubbles go only by a reviewed selection that keeps
    the largest-area shell, bounds the deleted area and records every deleted shell."""
    label = shells(vertices, faces); count = int(label.max())+1
    if selection is None:
        require(count == 1, f'Master has {count} separate shells; review them and declare mesh.components')
        return vertices, faces, {'shells': 1, 'deleted': [], 'deletedAreaFraction': 0.0}
    require(isinstance(selection, dict) and selection.get('keep') == 'largest' and selection.get('reviewed') is True,
            'Shell selection must be reviewed and keep the largest shell')
    limit = positive(selection.get('maximumDeletedAreaFraction', .01), 'deleted shell area bound')
    require(limit <= .05, 'Deleted shell area bound exceeds supported profile')
    corners = vertices[faces].astype(float)
    area = np.linalg.norm(np.cross(corners[:, 1]-corners[:, 0], corners[:, 2]-corners[:, 0]), axis=1)/2
    totals = np.bincount(label, area, count); keep = int(np.argmax(totals)); fraction = float(1-totals[keep]/totals.sum())
    deleted = [{'triangles': int(np.count_nonzero(label == k)), 'areaFraction': float(totals[k]/totals.sum()),
                'centroid': [round(float(c), 5) for c in vertices[np.unique(faces[label == k])].mean(0)]}
               for k in np.argsort(-totals) if k != keep]
    require(fraction <= limit, f'Deleted shells cover {fraction:.3%} of the master area, above the reviewed bound')
    expected = selection.get('expectedDeleted')
    require(expected is None or expected == len(deleted), f'{len(deleted)} shells would be deleted; the review expected {expected}')
    used = np.unique(faces[label == keep]); remap = np.full(len(vertices), -1); remap[used] = np.arange(len(used))
    return vertices[used], remap[faces[label == keep]], {'shells': count, 'deleted': deleted, 'deletedAreaFraction': fraction,
                                                        'keptTriangles': int(np.count_nonzero(label == keep))}

