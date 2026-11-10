"""Long-axis shape checks and deterministic centreline straightening for long thin weapons.

Single-view generation tends to bow or twist a long thin object in depth while its outline stays correct.
`measure` reports centreline bend, blade twist and cross-guard skew so a bent clay is flagged before review.
`fit_map` / `apply_map` unbend a mesh about its smoothed centreline: every cross-section is moved and turned
rigidly, never reshaped. A saved map re-applies unchanged to any mesh in the same frame (the textured donor,
the working shell), which keeps colour baked in the original frame aligned with the straightened geometry.

    python -m tools.itemkit.straightness check MESH.glb [--output REPORT.json] [--family longsword]
    python -m tools.itemkit.straightness straighten MESH.glb OUT_DIR [--map MAP.npz]
"""
import argparse, json, struct, sys
from pathlib import Path
import numpy as np

SLICES = 200
SMOOTHING_SIGMA = 6.0
MAX_PASSES = 4
CONVERGED_PCT = .3
# Advisory review limits. A flagged clay still goes to the user; it is never silently accepted or rejected.
LIMITS = {'bendPctOfLength': 1.5, 'twistDegrees': 12.0, 'guardSkewDegrees': 6.0}
LONG_FAMILIES = ('shortsword', 'longsword', 'greatsword', 'staff')
_KERNEL = np.exp(-.5 * (np.arange(-18, 19) / SMOOTHING_SIGMA) ** 2); _KERNEL /= _KERNEL.sum()


def _require(condition, message):
    if not condition: raise ValueError(message)


def principal_frame(positions):
    """Mean and right-handed axes (columns: long, width, depth) by descending variance."""
    positions = np.asarray(positions, float)
    _require(positions.ndim == 2 and positions.shape[1] == 3 and len(positions) >= 1000 and np.isfinite(positions).all(),
             'Finite mesh with at least 1000 vertices required')
    mean = positions.mean(0); _, axes = np.linalg.eigh(np.cov((positions - mean).T)); axes = axes[:, ::-1].copy()
    if np.linalg.det(axes) < 0: axes[:, 2] *= -1
    return mean, axes


def _sections(p):
    """Per-slice robust midline, extents and the wide-slice (cross-guard) mask along the long axis."""
    t = p[:, 0]; edges = np.linspace(t.min(), t.max(), SLICES + 1)
    index = np.clip(np.digitize(t, edges) - 1, 0, SLICES - 1); order = np.argsort(index, kind='stable')
    bounds = np.searchsorted(index[order], np.arange(SLICES + 1)); centres = (edges[:-1] + edges[1:]) / 2
    mid = np.full((SLICES, 2), np.nan); extent = np.full((SLICES, 2), np.nan); members = []
    for i in range(SLICES):
        rows = order[bounds[i]:bounds[i + 1]]; members.append(rows)
        if len(rows) >= 20:
            low, high = np.percentile(p[rows, 1:], [1, 99], axis=0); mid[i] = (low + high) / 2; extent[i] = high - low
    widest = np.nan_to_num(extent.max(1)); wide = widest > 2 * np.nanmedian(extent.max(1))
    wide = np.convolve(wide, np.ones(9), mode='same') > 0      # guard and its blend into blade and grip
    return centres, mid, extent, wide, members


def _midline(p):
    centres, mid, _, wide, _ = _sections(p); mid = mid.copy(); mid[wide] = np.nan; known = ~np.isnan(mid[:, 0])
    _require(known.sum() >= SLICES // 4, 'Too few usable cross-sections to measure a centreline')
    return centres, np.stack([np.interp(centres, centres[known], mid[known, j]) for j in (0, 1)], 1)


def _measure_pass(p):
    centres, mid = _midline(p)
    smooth = np.stack([np.convolve(np.pad(mid[:, j], 18, mode='edge'), _KERNEL, mode='valid') for j in (0, 1)], 1)
    curve = np.column_stack([centres, smooth]); slope = np.gradient(curve, centres, axis=0)
    speed = np.linalg.norm(slope, axis=1); tangent = slope / speed[:, None]
    arc = np.concatenate([[0], np.cumsum((speed[:-1] + speed[1:]) / 2 * np.diff(centres))]) + centres[0]
    normal = np.zeros_like(tangent); a = np.array([0., 1., 0.])
    for i in range(SLICES):                                       # rotation-minimising frame along the centreline
        a = a - (a @ tangent[i]) * tangent[i]; a /= np.linalg.norm(a); normal[i] = a
    table = np.column_stack([centres, curve, tangent, normal, np.cross(tangent, normal), speed, arc])
    return table, float(100 * np.ptp(mid, axis=0).max() / np.ptp(p[:, 0]))


def _apply_pass(p, table, vectors=None):
    centres, curve, tangent, n1, n2 = table[:, 0], table[:, 1:4], table[:, 4:7], table[:, 7:10], table[:, 10:13]
    speed, arc = table[:, 13], table[:, 14]
    at = lambda rows, t: np.stack([np.interp(t, centres, rows[:, j]) for j in range(3)], 1)
    t = p[:, 0]; t = t + ((p - at(curve, t)) * at(tangent, t)).sum(1) / np.interp(t, centres, speed)   # foot of the normal
    offset = p - at(curve, t); tt, a1, a2 = at(tangent, t), at(n1, t), at(n2, t)
    moved = np.column_stack([np.interp(t, centres, arc) + (offset * tt).sum(1), (offset * a1).sum(1), (offset * a2).sum(1)])
    if vectors is not None:
        vectors = np.column_stack([(vectors * tt).sum(1), (vectors * a1).sum(1), (vectors * a2).sum(1)])
    return moved, vectors


def fit_map(positions):
    """Measure the unbend map of a mesh. Returns (map, per-pass midline range in % of length)."""
    positions = np.asarray(positions, float); mean, axes = principal_frame(positions)
    start = (positions - mean) @ axes; p = start; tables = []; history = []
    for _ in range(MAX_PASSES):
        table, deviation = _measure_pass(p); p, _ = _apply_pass(p, table); tables.append(table); history.append(deviation)
        if deviation < CONVERGED_PCT: break
    shift = float((p[:, 0].max() + p[:, 0].min()) / 2 - (start[:, 0].max() + start[:, 0].min()) / 2)
    return {'mean': mean, 'axes': axes, 'tables': np.array(tables), 'shift': np.array(shift)}, history


def apply_map(positions, mapping, normals=None):
    """Apply a saved map unchanged. Optional direction vectors (normals) are turned with their cross-section."""
    positions = np.asarray(positions, float); mean, axes = mapping['mean'], mapping['axes']
    _require(positions.ndim == 2 and positions.shape[1] == 3 and np.isfinite(positions).all(), 'Finite positions required')
    p = (positions - mean) @ axes; v = None if normals is None else np.asarray(normals, float) @ axes
    for table in mapping['tables']: p, v = _apply_pass(p, table, v)
    p[:, 0] -= float(mapping['shift']); moved = p @ axes.T + mean
    if v is None: return moved
    v = v @ axes.T; length = np.linalg.norm(v, axis=1); _require(np.all(length > 0), 'Degenerate normal after straightening')
    return moved, v / length[:, None]


def save_map(path, mapping):
    with Path(path).open('xb') as stream: np.savez(stream, **mapping)


def load_map(path):
    with np.load(path, allow_pickle=False) as archive:
        _require(set(archive.files) == {'mean', 'axes', 'tables', 'shift'}, 'Unexpected straightening map')
        mapping = {name: archive[name] for name in archive.files}
    _require(mapping['mean'].shape == (3,) and mapping['axes'].shape == (3, 3) and mapping['tables'].ndim == 3
             and mapping['tables'].shape[1:] == (SLICES, 15) and 1 <= len(mapping['tables']) <= MAX_PASSES
             and all(np.isfinite(value).all() for value in mapping.values()), 'Invalid straightening map')
    return mapping


def measure(positions):
    """Centreline bend, blade twist and guard skew of a long thin mesh, measured about its own unbent frame."""
    positions = np.asarray(positions, float); mapping, history = fit_map(positions)
    mean, axes = mapping['mean'], mapping['axes']; start = (positions - mean) @ axes
    extents = np.ptp(start, axis=0); length = float(extents[0])
    p = start
    for table in mapping['tables']: p, _ = _apply_pass(p, table)
    centres, mid, extent, wide, members = _sections(p)
    # Twist: direction of each flat cross-section's broad axis, followed along the unbent length.
    angles = []; where = []
    for i, rows in enumerate(members):
        if wide[i] or len(rows) < 50: continue
        section = p[rows, 1:] - p[rows, 1:].mean(0); values, vectors = np.linalg.eigh(np.cov(section.T))
        if values[1] < 3 * max(values[0], 1e-18): continue          # a near-round section has no broad axis to follow
        angles.append(np.arctan2(vectors[1, 1], vectors[0, 1])); where.append(i)
    twist = None
    if len(angles) >= 20:
        doubled = np.unwrap(2 * np.array(angles)) / 2             # a broad axis has no sign: unwrap modulo 180 degrees
        doubled = np.convolve(doubled, np.ones(5) / 5, mode='valid')
        twist = float(np.degrees(np.ptp(doubled)))
    # Guard skew: the wide run's own long direction against the plane square to the weapon axis.
    skew = None; guard = np.flatnonzero(wide)
    if len(guard):
        runs = np.split(guard, np.flatnonzero(np.diff(guard) > 1) + 1); run = max(runs, key=len)
        rows = np.concatenate([members[i] for i in run]); body = np.nanmedian(extent[~wide].max(1)) / 2
        centre = np.array([np.interp(centres[run].mean(), centres[~wide], mid[~wide, j]) for j in (0, 1)])
        radial = np.linalg.norm(p[rows, 1:] - centre, axis=1); arms = rows[radial > 1.5 * body]
        if len(arms) >= 200:
            points = p[arms] - p[arms].mean(0); _, vectors = np.linalg.eigh(np.cov(points.T)); arm = vectors[:, -1]
            if np.hypot(arm[1], arm[2]) > .5:                     # a real cross-guard, not a long collar
                skew = float(np.degrees(np.arcsin(min(1., abs(arm[0])))))
    return {'vertices': int(len(positions)), 'extents': [float(x) for x in extents],
            'aspectRatio': float(length / max(extents[1], 1e-12)),
            'bendPctOfLength': float(history[0]), 'residualBendPctAfterStraightening': float(history[-1]) if len(history) > 1
            else float(history[0]), 'straighteningPasses': len(history),
            'twistDegrees': twist, 'flatSectionsMeasured': len(angles), 'guardSkewDegrees': skew,
            'guardSlices': int(wide.sum())}


def assess(metrics, limits=None):
    """Advisory flags against the review limits; an unmeasurable quantity is reported, not flagged."""
    limits = dict(LIMITS, **(limits or {})); flags = []
    for name, limit in limits.items():
        value = metrics.get(name)
        if value is not None and value > limit: flags.append({'metric': name, 'value': value, 'limit': limit})
    return {'limits': limits, 'flags': flags, 'straight': not flags,
            'unmeasured': [name for name in limits if metrics.get(name) is None]}


def _glb(path):
    from tools.headkit.gltf import load, arrays
    document, binary, primitive = load(Path(path).read_bytes()); positions, faces, attributes = arrays(document, binary, primitive)
    return document, binary, primitive, positions, faces, attributes


def _replace(document, buffer, index, values):
    """Overwrite one float32 accessor in place, honouring its stride, and refresh its bounds."""
    accessor = document['accessors'][index]; view = document['bufferViews'][accessor['bufferView']]
    width = values.shape[1]; stride = view.get('byteStride', 4 * width)
    start = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
    target = np.ndarray((accessor['count'], width), dtype='<f4', buffer=buffer, offset=start, strides=(stride, 4))
    target[:] = values.astype('<f4')
    if 'min' in accessor: accessor['min'] = target.min(0).tolist()
    if 'max' in accessor: accessor['max'] = target.max(0).tolist()


def straighten(source, output, map_path=None):
    """Write OUTPUT/straightened.glb (+ map and report). Indices, UVs, materials and textures are carried byte for byte."""
    from tools.headkit.common import pin, write
    from tools.headkit.gltf import encode, load, arrays
    source = Path(source); output = Path(output); output.mkdir(parents=True, exist_ok=False)
    source_pin = pin(source); document, binary, primitive, positions, faces, attributes = _glb(source)
    if map_path is None:
        mapping, history = fit_map(positions); map_path = output / 'straighten-map.npz'; save_map(map_path, mapping); mode = 'measured'
    else:
        mapping, history, mode = load_map(map_path), None, 'applied'
    normals = attributes.get('NORMAL'); buffer = bytearray(binary)
    if normals is None: moved = apply_map(positions, mapping)
    else: moved, turned = apply_map(positions, mapping, normals)
    _replace(document, buffer, primitive['attributes']['POSITION'], moved)
    if normals is not None: _replace(document, buffer, primitive['attributes']['NORMAL'], turned)
    target = output / 'straightened.glb'
    with target.open('xb') as stream: stream.write(encode(document, bytes(buffer)))
    check, check_binary, check_primitive = load(target.read_bytes()); after, after_faces, after_attributes = arrays(check, check_binary, check_primitive)
    _require(np.array_equal(after_faces, faces) and all(np.array_equal(after_attributes[name], attributes[name])
             for name in attributes if name not in ('POSITION', 'NORMAL')), 'Straightening changed topology, UVs or other attributes')
    corners = moved[faces]; area = np.linalg.norm(np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), axis=1)
    before = positions[faces].astype(float); before_area = np.linalg.norm(np.cross(before[:, 1] - before[:, 0], before[:, 2] - before[:, 0]), axis=1)
    result = {'source': source_pin, 'output': pin(target), 'map': dict(pin(map_path), mode=mode),
              'before': measure(positions), 'after': measure(after), 'passMidlineRangePct': history,
              'maximumVertexMove': float(np.linalg.norm(moved - positions, axis=1).max()),
              'surfaceAreaRatio': float(area.sum() / before_area.sum()),
              'trianglesUnchanged': True, 'attributesOtherThanPositionAndNormalExact': True,
              'method': 'two-axis centreline unbend, rotation-minimising frame, guard slices excluded; cross-sections rigid',
              'visualReviewRequired': True}
    result['assessmentAfter'] = assess(result['after'])
    write(output / 'straighten.json', result, fresh=True); return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0]); commands = parser.add_subparsers(dest='command', required=True)
    c = commands.add_parser('check'); c.add_argument('mesh', type=Path); c.add_argument('--output', type=Path); c.add_argument('--family')
    c = commands.add_parser('straighten'); c.add_argument('mesh', type=Path); c.add_argument('output', type=Path); c.add_argument('--map', type=Path)
    a = parser.parse_args(argv)
    if a.command == 'check':
        from tools.headkit.gltf import positions as read_positions
        metrics = measure(read_positions(a.mesh)[0]); result = {'mesh': str(a.mesh), 'metrics': metrics, 'assessment': assess(metrics)}
        if a.family is not None: result['family'] = a.family; result['longFamily'] = a.family in LONG_FAMILIES
        if a.output is not None:
            with a.output.open('x', encoding='utf-8') as stream: json.dump(result, stream, indent=2)
        print(json.dumps(result, indent=2)); return 0
    result = straighten(a.mesh, a.output, a.map)
    print(json.dumps({k: result[k] for k in ('output', 'map', 'maximumVertexMove', 'surfaceAreaRatio', 'assessmentAfter')}, indent=2)); return 0


if __name__ == '__main__':
    sys.exit(main())
