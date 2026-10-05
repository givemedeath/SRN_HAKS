"""Finite C2 foot-stub field math, with explicit original lower-foot protection.

This module performs RAM calculations only. It cannot authorize a mesh source,
coordinate space, mask, output, native conversion, or a production selection.
"""
import numpy as np


def require(ok, message):
    if not ok:
        raise ValueError(message)


def parameters(start, end, factor):
    values = np.asarray([start, end, factor], dtype=float)
    require(np.isfinite(values).all() and end > start and 0 < factor <= 1,
            'Finite increasing axial support and positive shrink factor <=1 required')
    return float(start), float(end), float(factor)


def profile(z, start, end, factor):
    start, end, factor = parameters(start, end, factor)
    z = np.asarray(z, dtype=float)
    require(np.isfinite(z).all(), 'Finite axial values required')
    u = np.clip((z-start)/(end-start), 0., 1.)
    q = u**3*(10.+u*(-15.+6.*u))
    scale = 1.-(1.-factor)*q
    slope = -(1.-factor)*30.*u*u*(1.-u)*(1.-u)/(end-start)
    scale = np.where(z <= start, 1., np.where(z >= end, factor, scale))
    slope = np.where((z <= start) | (z >= end), 0., slope)
    require(np.isfinite(scale).all() and np.isfinite(slope).all() and (scale > 0).all(),
            'Finite positive field required')
    return scale, slope


def field(points, protected, start, end, factor):
    points, protected = np.asarray(points), np.asarray(protected)
    require(points.ndim == 2 and points.shape[1] == 3 and len(points) > 0 and
            np.issubdtype(points.dtype, np.floating) and np.isfinite(points).all(),
            'Finite nonempty floating attachment-local Nx3 positions required')
    require(protected.dtype == np.dtype(bool) and protected.shape == (len(points),),
            'Explicit complete Boolean original-lower-foot protection required')
    scale, slope = profile(points[:, 2], start, end, factor)
    scale[protected], slope[protected] = 1., 0.
    active = (points[:, 2] > start) & ~protected
    jacobian = np.tile(np.eye(3), (len(points), 1, 1))
    jacobian[:, 0, 0] = jacobian[:, 1, 1] = scale
    jacobian[:, 0, 2] = slope*points[:, 0]
    jacobian[:, 1, 2] = slope*points[:, 1]
    require(np.isfinite(jacobian).all() and (np.linalg.det(jacobian) > 0).all(),
            'Finite strictly positive Jacobian required')
    transformed = points.copy()
    nonidentity = np.any(jacobian != np.eye(3), axis=(1, 2))
    changed = active & nonidentity
    transformed[changed, :2] = (points[changed, :2].astype(float)*scale[changed, None]).astype(points.dtype)
    require(np.isfinite(transformed).all(), 'Transformed position overflow rejected')
    require(transformed[:, 2].tobytes() == points[:, 2].tobytes() and
            transformed[~changed].tobytes() == points[~changed].tobytes(),
            'Axial and computed-identity position bytes must remain exact')
    return transformed, jacobian, active


def transport(points, normals, tangents, protected, start, end, factor):
    points, normals, tangents = map(np.asarray, (points, normals, tangents))
    require(normals.shape == points.shape and tangents.shape == (len(points), 4),
            'Complete matching authored normal/tangent rows required')
    require(all(np.issubdtype(a.dtype, np.floating) and np.isfinite(a).all()
                for a in (normals, tangents)), 'Finite authored floating shading required')
    nmag = np.linalg.norm(normals.astype(float), axis=1)
    tmag = np.linalg.norm(tangents[:, :3].astype(float), axis=1)
    require(np.isfinite(nmag).all() and np.isfinite(tmag).all() and
            (nmag > 0).all() and (tmag > 0).all() and np.isin(tangents[:, 3], [-1, 1]).all(),
            'Finite nonzero authored vectors and exact tangent handedness required')
    q, jacobian, active = field(points, protected, start, end, factor)
    nn, tt = normals.copy(), tangents.copy()
    shaded = active & np.any(jacobian != np.eye(3), axis=(1, 2))
    if shaded.any():
        n = np.linalg.solve(np.swapaxes(jacobian[shaded], 1, 2),
                            normals[shaded].astype(float)[..., None])[..., 0]
        length = np.linalg.norm(n, axis=1)
        require(np.isfinite(length).all() and (length > 0).all(), 'Degenerate normal transport')
        n *= (nmag[shaded]/length)[:, None]
        t = np.einsum('nij,nj->ni', jacobian[shaded], tangents[shaded, :3].astype(float))
        unit = n/nmag[shaded, None]
        t -= np.einsum('ij,ij->i', t, unit)[:, None]*unit
        length = np.linalg.norm(t, axis=1)
        require(np.isfinite(length).all() and (length > 1e-14).all(),
                'Degenerate projected tangent rejected')
        t *= (tmag[shaded]/length)[:, None]
        nn[shaded], tt[shaded, :3] = n.astype(normals.dtype), t.astype(tangents.dtype)
    require(np.isfinite(nn).all() and np.isfinite(tt).all(), 'Shading serialization overflow')
    require(nn[~shaded].tobytes() == normals[~shaded].tobytes() and
            tt[~shaded].tobytes() == tangents[~shaded].tobytes() and
            tt[:, 3].tobytes() == tangents[:, 3].tobytes(), 'Protected shading/W bytes changed')
    return q, nn, tt, jacobian, active
