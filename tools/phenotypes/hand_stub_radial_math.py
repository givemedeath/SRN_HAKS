"""Pure coherent wrist-stub C2 radial field math; no file/mesh/rig exporter.

Coordinates are explicitly the frozen hand attachment-local working frame.
This module never authorizes a source, coordinate space, mask or parameter.
"""
import numpy as np


def parameters(start_z, end_z, terminal_factor):
    values = np.asarray([start_z, end_z, terminal_factor], dtype=float)
    if not np.isfinite(values).all() or end_z <= start_z or not 0 < terminal_factor <= 1:
        raise ValueError('Finite increasing band and positive radial shrink factor <=1 required')
    return float(start_z), float(end_z), float(terminal_factor)


def profile(z, start_z, end_z, terminal_factor):
    start_z, end_z, terminal_factor = parameters(start_z, end_z, terminal_factor)
    z = np.asarray(z, dtype=float)
    if not np.isfinite(z).all():
        raise ValueError('Finite attachment-local axial values required')
    u = np.clip((z - start_z) / (end_z - start_z), 0., 1.)
    q = u**3 * (10. - 15. * u + 6. * u**2)
    derivative = 30. * u**2 * (1. - u)**2 / (end_z - start_z)
    scale = 1. + (terminal_factor - 1.) * q
    slope = (terminal_factor - 1.) * derivative
    scale = np.where(z <= start_z, 1., np.where(z >= end_z, terminal_factor, scale))
    slope = np.where((z <= start_z) | (z >= end_z), 0., slope)
    return scale, slope


def field(points, start_z, end_z, terminal_factor):
    points = np.asarray(points)
    if points.ndim != 2 or points.shape[1] != 3 or not np.issubdtype(points.dtype, np.floating) or not np.isfinite(points).all():
        raise ValueError('Finite floating attachment-local Nx3 points required')
    scale, slope = profile(points[:, 2], start_z, end_z, terminal_factor)
    transformed = points.copy()
    active = points[:, 2] > start_z
    transformed[active, :2] = (points[active, :2].astype(float) * scale[active, None]).astype(points.dtype)
    jacobian = np.tile(np.eye(3), (len(points), 1, 1))
    jacobian[:, 0, 0] = jacobian[:, 1, 1] = scale
    jacobian[:, 0, 2] = slope * points[:, 0]
    jacobian[:, 1, 2] = slope * points[:, 1]
    if not (np.linalg.det(jacobian) > 0).all():
        raise ValueError('Positive determinant required')
    return transformed, jacobian, active


def transport(points, normals, tangents, start_z, end_z, terminal_factor):
    """Synthetic/analytical math seam only, not a mesh export or adoption path."""
    points, normals, tangents = map(np.asarray, (points, normals, tangents))
    if normals.shape != points.shape or tangents.shape != (len(points), 4):
        raise ValueError('Matching authored Nx3 normals and Nx4 tangents required')
    if not all(np.issubdtype(x.dtype, np.floating) and np.isfinite(x).all() for x in (normals, tangents)):
        raise ValueError('Finite authored floating shading vectors required')
    nmag, tmag = np.linalg.norm(normals.astype(float), axis=1), np.linalg.norm(tangents[:, :3].astype(float), axis=1)
    if not (nmag > 0).all() or not (tmag > 0).all() or not np.isin(tangents[:, 3], [-1, 1]).all():
        raise ValueError('Nonzero authored vectors and handedness +/-1 required')
    transformed, jacobian, active = field(points, start_z, end_z, terminal_factor)
    out_n, out_t = normals.copy(), tangents.copy()
    shading_active = active & np.any(jacobian != np.eye(3), axis=(1, 2))
    if shading_active.any():
        normal = np.linalg.solve(np.swapaxes(jacobian[shading_active], 1, 2), normals[shading_active].astype(float)[..., None])[..., 0]
        normal *= (nmag[shading_active] / np.linalg.norm(normal, axis=1))[:, None]
        tangent = np.einsum('nij,nj->ni', jacobian[shading_active], tangents[shading_active, :3].astype(float))
        unit_n = normal / nmag[shading_active, None]
        tangent -= np.einsum('ij,ij->i', tangent, unit_n)[:, None] * unit_n
        length = np.linalg.norm(tangent, axis=1)
        if not (length > 1e-14).all():
            raise ValueError('Degenerate transported tangent rejected')
        tangent *= (tmag[shading_active] / length)[:, None]
        out_n[shading_active] = normal.astype(normals.dtype)
        out_t[shading_active, :3] = tangent.astype(tangents.dtype)
    return transformed, out_n, out_t, jacobian, active