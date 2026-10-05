"""C2 attachment-local regional equipment field; no source/model writer.

Source vertex and native shading owner correspondence stay external and explicit.
The field keeps axial coordinates exact and transports authored normal magnitudes.
"""
import numpy as np


def require(value, message):
    if not value:
        raise ValueError(message)


def checked_knots(config):
    require(config.get('schemaVersion') == 1 and config.get('kind') == 'equipment-c2-section-field', 'Unsupported regional field schema')
    require(config.get('axialPolicy') == 'identity' and config.get('statureApplications') == 0, 'Working field must preserve axial positions and apply no stature')
    require(config.get('interpolation', 'quintic-smoothstep-C2-zero-derivatives-at-knots') == 'quintic-smoothstep-C2-zero-derivatives-at-knots' and config.get('outsidePolicy', 'constant-terminal-coefficients') == 'constant-terminal-coefficients', 'Unknown field interpolation or terminal policy')
    rows = config.get('knots', [])
    require(isinstance(rows, list) and len(rows) >= 2, 'At least two explicit section knots required')
    a = np.asarray([[r['z'], *r['scaleXY'], *r['translateXY']] for r in rows], dtype=float)
    require(a.shape == (len(rows), 5) and np.isfinite(a).all(), 'Finite two-axis section coefficients required')
    require((np.diff(a[:, 0]) > 0).all(), 'Section knots must be strictly ordered and distinct')
    require((a[:, 1:3] > 0).all(), 'Regional radial scales must be strictly positive')
    return a


def evaluate(config, positions):
    knots = checked_knots(config)
    p = np.asarray(positions)
    require(p.ndim == 2 and p.shape[1] == 3 and np.issubdtype(p.dtype, np.floating) and np.isfinite(p).all(), 'Finite floating position rows required')
    z = p[:, 2].astype(float)
    i = np.clip(np.searchsorted(knots[:, 0], z, side='right') - 1, 0, len(knots) - 2)
    lo, hi = knots[i], knots[i + 1]
    dz = hi[:, 0] - lo[:, 0]
    u = np.clip((z - lo[:, 0]) / dz, 0., 1.)
    q = u**3 * (10. + u * (-15. + 6. * u))
    dq = 30. * u**2 * (1. - u)**2 / dz
    c = lo[:, 1:] + q[:, None] * (hi[:, 1:] - lo[:, 1:])
    dc = dq[:, None] * (hi[:, 1:] - lo[:, 1:])
    result = p.astype(float, copy=True)
    result[:, :2] = p[:, :2] * c[:, :2] + c[:, 2:]
    # No assignment to axial values: their IEEE value is retained exactly.
    j = np.broadcast_to(np.eye(3), (len(p), 3, 3)).copy()
    j[:, 0, 0], j[:, 1, 1] = c[:, 0], c[:, 1]
    j[:, 0, 2] = dc[:, 0] * p[:, 0] + dc[:, 2]
    j[:, 1, 2] = dc[:, 1] * p[:, 1] + dc[:, 3]
    require(np.isfinite(result).all() and np.isfinite(j).all() and (np.linalg.det(j) > 0).all(), 'Regional field must remain finite and orientation preserving')
    return result, j


def transport_native_normals(normals, native_position_owners, position_jacobians):
    n = np.asarray(normals)
    owners = np.asarray(native_position_owners)
    j = np.asarray(position_jacobians, float)
    require(n.ndim == 2 and n.shape[1] == 3 and np.issubdtype(n.dtype, np.floating) and np.isfinite(n).all(), 'Finite authored native normals required')
    require(owners.shape == (len(n),) and np.issubdtype(owners.dtype, np.integer) and (owners >= 0).all() and (owners < len(j)).all(), 'Every native normal requires one exact in-range source position owner')
    require(j.shape[1:] == (3, 3) and np.isfinite(j).all() and (np.linalg.det(j) > 0).all(), 'Proper invertible native normal owner Jacobians required')
    magnitude = np.linalg.norm(n, axis=1)
    require((magnitude > 0).all(), 'Authored native normals must be nonzero')
    out = n.copy()
    owner_j = j[owners]
    active = np.any(owner_j != np.eye(3), axis=(1, 2))
    if active.any():
        changed = np.linalg.solve(owner_j[active].transpose(0, 2, 1), n[active].astype(float)[..., None])[..., 0]
        length = np.linalg.norm(changed, axis=1)
        require(np.isfinite(changed).all() and (length > 0).all(), 'Invalid transported native normal')
        out[active] = changed * (magnitude[active] / length)[:, None]
    return out

def validate_source_correspondence(source_positions, source_faces, source_uv, native_positions, native_normals, native_uv, native_faces, position_owners, uv_owners):
    """Validate exhaustive ordered native corner ownership, without reconstructing it.

    ASCII decimal position rounding is diagnosed separately against pinned native
    bytes. UV corner values must retain exact original native float32 values.
    """
    p, f, uv = np.asarray(source_positions), np.asarray(source_faces), np.asarray(source_uv)
    np_, nn, nuv, nf = map(np.asarray, (native_positions, native_normals, native_uv, native_faces))
    po, uo = np.asarray(position_owners), np.asarray(uv_owners)
    require(p.ndim == 2 and p.shape[1] == 3 and len(p) >= 3 and np.isfinite(p).all(), 'Invalid source position table')
    require(f.ndim == 2 and f.shape[1] == 8 and len(f) > 0 and np.issubdtype(f.dtype, np.integer), 'Full ordered source face table required')
    require(uv.ndim == 2 and uv.shape[1] == 3 and np.isfinite(uv).all(), 'Full source UV table required')
    require((f[:, :3] >= 0).all() and (f[:, :3] < len(p)).all() and (f[:, 4:7] >= 0).all() and (f[:, 4:7] < len(uv)).all(), 'Source face owner outside position/UV tables')
    require(np_.ndim == 2 and np_.shape[1] == 3 and len(np_) > 0 and np.isfinite(np_).all(), 'Finite decoded native position table required')
    require(nn.shape == np_.shape and np.isfinite(nn).all() and (np.linalg.norm(nn, axis=1) > 0).all(), 'Finite nonzero decoded native normal owners required')
    require(nuv.shape == (len(np_), 2) and np.isfinite(nuv).all(), 'Decoded native UV owner table required')
    require(nf.shape == (len(f), 3) and np.issubdtype(nf.dtype, np.integer) and (nf >= 0).all() and (nf < len(np_)).all(), 'Ordered native faces required')
    require(po.shape == uo.shape == (len(np_),) and np.issubdtype(po.dtype, np.integer) and np.issubdtype(uo.dtype, np.integer), 'Every native row needs one declared position and UV owner')
    require((po >= 0).all() and (po < len(p)).all() and (uo >= 0).all() and (uo < len(uv)).all(), 'Native owner outside original source table')
    require(np.array_equal(po[nf], f[:, :3]) and np.array_equal(uo[nf], f[:, 4:7]), 'Native corner winding/order or ownership changed')
    require(set(po.tolist()) == set(range(len(p))), 'Missing original source position owner')
    require(np.array_equal(nuv[nf].astype('f4'), uv[f[:, 4:7], :2].astype('f4')), 'Native UV corner precision changed')
    for owner in range(len(p)):
        rows = np_[po == owner]
        require(np.array_equal(rows, np.broadcast_to(rows[0], rows.shape)), 'Ambiguous original native position owner')
    return {'sourcePositionRows': len(p), 'sourceFaces': len(f), 'sourceUVRows': len(uv), 'nativeRows': len(np_), 'orderedCorners': 3*len(f),
            'maximumAsciiNativePositionDifference': float(np.abs(np_ - p[po]).max()), 'orderedFaceAndUvCornerOwnershipExact': True}