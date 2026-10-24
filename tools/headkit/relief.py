"""Reviewed relief smoothing on the dense repair master: Taubin (lambda/mu) steps over declared head-local regions, so
Pixal surface crust (buzz cuts, flat-tops, bristles) becomes a clean surface that the texture carries, before QSlim."""
import numpy as np
from scipy.sparse import coo_matrix
from .common import require, positive
from .predicates import Values, when


def neighbours(faces, count):
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]); edges = np.r_[edges, edges[:, ::-1]]
    graph = coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), (count, count)).tocsr(); graph.data[:] = 1
    return graph


def smooth(vertices, faces, ops, local):
    """ops: [{name, where, iterations, lambda?, mu? (default -0.53; 0 = plain Laplacian), feather?, reviewed: true}]; where is a predicate over head-local
    vertex x (character right), y (face forward), z (up) and radius (distance from the z axis), in fitted metres.
    Only selected vertices move; weights ramp over `feather` edge rings from the unselected surface (no step)."""
    require(isinstance(ops, list) and ops, 'Smoothing needs a non-empty list of reviewed regions')
    vertices = np.asarray(vertices, float).copy(); graph = neighbours(faces, len(vertices)); degree = np.asarray(graph.sum(1)).ravel()
    require((degree > 0).all(), 'Smoothing needs every vertex on the surface')
    values = Values({'x': lambda: local[:, 0], 'y': lambda: local[:, 1], 'z': lambda: local[:, 2],
                     'radius': lambda: np.hypot(local[:, 0], local[:, 1])})
    scale = float(np.linalg.norm(local[1]-local[0]))/max(float(np.linalg.norm(vertices[1]-vertices[0])), 1e-30)
    records = []
    for op in ops:
        require(isinstance(op, dict) and op.get('reviewed') is True and isinstance(op.get('name'), str), 'Each smoothing region must be named and reviewed')
        iterations = op.get('iterations'); require(type(iterations) is int and 1 <= iterations <= 100, 'Smoothing iterations must be 1..100')
        lam = positive(op.get('lambda', .5), 'Taubin lambda'); mu = float(op.get('mu', -.53)); feather = op.get('feather', 3)
        # mu 0 is a plain (shrinking) Laplacian: it collapses thin bristle fins that Taubin only translates.
        require(lam < 1 and (mu == 0 or -1 < mu < -lam), 'Taubin needs 0 < lambda < -mu < 1 (or mu 0 for a plain Laplacian)'); require(type(feather) is int and 0 <= feather <= 20, 'Feather must be 0..20 rings')
        selected = when(op['where'], values, {}); require(selected.any(), 'Smoothing region selects no vertices: '+op['name'])
        ring = np.where(selected, feather+1, 0).astype(float); reached = ~selected
        for k in range(1, feather+1):
            grown = (graph @ reached.astype(float) > 0) & ~reached; ring[grown] = k; reached |= grown
        weight = (ring/(feather+1))[:, None]; before = vertices.copy()
        for _ in range(iterations):
            for factor in ((lam, mu) if mu else (lam,)):
                vertices += factor*weight*((graph @ vertices)/degree[:, None]-vertices)
        moved = np.linalg.norm(vertices-before, axis=1)*scale
        records.append({'name': op['name'], 'vertices': int(selected.sum()), 'iterations': iterations, 'lambda': lam, 'mu': mu, 'feather': feather,
                        'maximumDisplacementMetres': float(moved.max()), 'meanDisplacementMetres': float(moved[selected].mean())})
    return vertices, records
