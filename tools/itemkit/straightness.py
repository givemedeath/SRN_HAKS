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
LIMITS = {'bendPctOfLength': 1.5, 'twistDegrees': 12.0, 'guardSkewDegrees': 6.0,
          'guardSectionRatio': 2.5,      # slab or plate guard: wave-1 slabs measured 3.1 and 3.6, bar guards 1.1 to 1.3
          'bladeDepthToWidth': .5,       # wave 1: the Sword at 0.40 was accepted, the Claymore at 0.65 was called too thick
          'splitBladeSlices': 2}         # gross delamination only; a hairline edge split still needs the end-on views
THIN_FACTOR = .5
LONG_FAMILIES =('shortsword', 'longsword', 'greatsword', 'staff')
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
    centres, mid, extent, wide, _ = _sections(p); mid = mid.copy(); mid[wide] = np.nan
    # A slice near either end of a bent thick shaft cuts its end cap obliquely, so its midpoint is off the axis and
    # would hook the centreline. Within about one section width of each end, continue the adjacent interior line.
    step = centres[1] - centres[0]; margin = int(np.ceil(.75 * np.nanmedian(extent.min(1)) / step))    # thin blades bow in depth: little is hidden
    margin = min(max(margin, 2), SLICES // 8); inner = mid.copy(); inner[:margin] = np.nan; inner[-margin:] = np.nan
    known = ~np.isnan(inner[:, 0])
    _require(known.sum() >= SLICES // 4, 'Too few usable cross-sections to measure a centreline')
    line = np.stack([np.interp(centres, centres[known], inner[known, j]) for j in (0, 1)], 1); rows = np.flatnonzero(known)
    for end, near in ((slice(0, rows[0]), rows[:2 * margin]), (slice(rows[-1] + 1, SLICES), rows[-2 * margin:])):
        for j in (0, 1): line[end, j] = np.polyval(np.polyfit(centres[near], inner[near, j], 1), centres[end])
    return centres, line


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


def _fit_ends(p):
    """Flat end caps that are tilted off the long axis, as rows [x_end, y, z, a, b, reach, 0]: the cap is x = x_end + a*dy + b*dz.

    A cap is taken as flat when its outward envelope, sampled over the inner 70% of the section, fits a plane to
    within 2% of the section size; a blade point or a rounded butt does not and is left alone. Tilts under half a
    degree need nothing and tilts over 30 degrees are treated as design, not error (the wave-1 Club pommel was 23).
    """
    centres, mid, extent, _, _ = _sections(p); rows = []
    for sign in (-1, 1):
        zone = slice(0, SLICES // 20) if sign < 0 else slice(SLICES - SLICES // 20, SLICES)
        if np.isnan(extent[zone]).all(): continue
        size = float(np.nanmedian(extent[zone].max(1))); centre = np.nanmedian(mid[zone], axis=0)
        end = p[:, 0].min() if sign < 0 else p[:, 0].max(); near = p[np.abs(p[:, 0] - end) < .35 * size]
        cell = np.floor((near[:, 1:] - centre) / (size / 14)).astype(int); inner = np.hypot(*(cell + .5).T) * size / 14 < .35 * size
        keys, inverse = np.unique(cell[inner], axis=0, return_inverse=True); inverse = inverse.reshape(-1)
        if len(keys) < 24: continue
        outer = np.full(len(keys), -np.inf); np.maximum.at(outer, inverse, sign * near[inner, 0])
        A = np.c_[np.ones(len(keys)), (keys + .5) * size / 14]; fit, *_ = np.linalg.lstsq(A, sign * outer, rcond=None)
        rms = float(np.sqrt(np.mean((A @ fit - sign * outer) ** 2))); tilt = np.degrees(np.arctan(np.hypot(fit[1], fit[2])))
        if rms < .02 * size and .5 < tilt < 30: rows.append([end, centre[0], centre[1], fit[1], fit[2], size, 0.])
    return np.array(rows, float).reshape(-1, 7)


def _apply_ends(p, ends, vectors=None):
    """Shear each tilted flat cap square, fading the correction out over one section size along the shaft."""
    p = p.copy()
    for end, y, z, a, b, reach, _ in ends:
        w = np.clip(1 - np.abs(p[:, 0] - end) / reach, 0, 1); w = w * w * (3 - 2 * w)
        p[:, 0] -= w * (a * (p[:, 1] - y) + b * (p[:, 2] - z))
        if vectors is not None: vectors = np.column_stack([vectors[:, 0], vectors[:, 1] + w * a * vectors[:, 0], vectors[:, 2] + w * b * vectors[:, 0]])
    return p, vectors


def fit_map(positions):
    """Measure the unbend map of a mesh. Returns (map, per-pass midline range in % of length)."""
    positions = np.asarray(positions, float); mean, axes = principal_frame(positions)
    start = (positions - mean) @ axes; p = start; tables = []; history = []
    for _ in range(MAX_PASSES):
        table, deviation = _measure_pass(p); p, _ = _apply_pass(p, table); tables.append(table); history.append(deviation)
        if deviation < CONVERGED_PCT: break
    ends = _fit_ends(p); p, _ = _apply_ends(p, ends)
    shift = float((p[:, 0].max() + p[:, 0].min()) / 2 - (start[:, 0].max() + start[:, 0].min()) / 2)
    return {'mean': mean, 'axes': axes, 'tables': np.array(tables), 'shift': np.array(shift), 'ends': ends}, history


def apply_map(positions, mapping, normals=None):
    """Apply a saved map unchanged. Optional direction vectors (normals) are turned with their cross-section."""
    positions = np.asarray(positions, float); mean, axes = mapping['mean'], mapping['axes']
    _require(positions.ndim == 2 and positions.shape[1] == 3 and np.isfinite(positions).all(), 'Finite positions required')
    p = (positions - mean) @ axes; v = None if normals is None else np.asarray(normals, float) @ axes
    for table in mapping['tables']: p, v = _apply_pass(p, table, v)
    p, v = _apply_ends(p, mapping.get('ends', ()), v)                 # maps saved before end squaring have none
    p[:, 0] -= float(mapping['shift']); moved = p @ axes.T + mean
    if v is None: return moved
    v = v @ axes.T; length = np.linalg.norm(v, axis=1); _require(np.all(length > 0), 'Degenerate normal after straightening')
    return moved, v / length[:, None]


def save_map(path, mapping):
    with Path(path).open('xb') as stream: np.savez(stream, **mapping)


def load_map(path):
    with np.load(path, allow_pickle=False) as archive:
        _require(set(archive.files) - {'ends'} == {'mean', 'axes', 'tables', 'shift'}, 'Unexpected straightening map')
        mapping = {name: archive[name] for name in archive.files}
    _require(mapping['mean'].shape == (3,) and mapping['axes'].shape == (3, 3) and mapping['tables'].ndim == 3
             and mapping['tables'].shape[1:] == (SLICES, 15) and 1 <= len(mapping['tables']) <= MAX_PASSES
             and all(np.isfinite(value).all() for value in mapping.values())
             and mapping.get('ends', np.zeros((0, 7))).shape[1:] == (7,) and len(mapping.get('ends', ())) <= 2, 'Invalid straightening map')
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
    skew = None; guard_section = None; guard = np.flatnonzero(wide)
    # Split blade: a sound blade has two surfaces through its mid-width; a delaminated one shows four or more.
    split = 0; major = int(np.argmax(np.nanmedian(extent[~wide], axis=0))); thin = 1 - major
    for i, rows in enumerate(members):
        if wide[i] or len(rows) < 100 or np.isnan(extent[i, 0]): continue
        core = rows[np.abs(p[rows, 1 + major] - mid[i, major]) < .12 * extent[i, major]]
        if len(core) < 40: continue
        depth = np.sort(p[core, 1 + thin]); gaps = np.diff(depth)
        if (gaps > .12 * extent[i, thin]).sum() >= 3: split += 1
    if len(guard):
        runs = np.split(guard, np.flatnonzero(np.diff(guard) > 1) + 1); run = max(runs, key=len)
        rows = np.concatenate([members[i] for i in run]); body = np.nanmedian(extent[~wide].max(1)) / 2
        centre = np.array([np.interp(centres[run].mean(), centres[~wide], mid[~wide, j]) for j in (0, 1)])
        radial = np.linalg.norm(p[rows, 1:] - centre, axis=1); arms = rows[radial > 1.5 * body]
        if len(arms) >= 200:
            points = p[arms] - p[arms].mean(0); values, vectors = np.linalg.eigh(np.cov(points.T)); arm = vectors[:, -1]
            if np.hypot(arm[1], arm[2]) > .5:                     # a real cross-guard, not a long collar
                skew = float(np.degrees(np.arcsin(min(1., abs(arm[0])))))
                # A bar guard has a compact cross-section; an invented plate or slab is far deeper one way than the other.
                guard_section = float(np.sqrt(values[1] / max(values[0], 1e-18)))
    blade = _blade_slices(wide); ratio = None
    if blade is not None:
        rows = [i for i in blade if not np.isnan(extent[i, 0])]
        if len(rows) >= 20: ratio = float(np.median(extent[rows, thin] / extent[rows, major]))
    return {'bladeDepthToWidth': ratio, 'vertices': int(len(positions)), 'extents': [float(x) for x in extents],
            'aspectRatio': float(length / max(extents[1], 1e-12)),
            'bendPctOfLength': float(history[0]), 'residualBendPctAfterStraightening': float(history[-1]) if len(history) > 1
            else float(history[0]), 'straighteningPasses': len(history),
            'twistDegrees': twist, 'flatSectionsMeasured': len(angles), 'guardSkewDegrees': skew,
            'guardSlices': int(wide.sum()), 'guardSectionRatio': guard_section, 'splitBladeSlices': int(split)}


def _blade_slices(wide):
    """Slice indices of the blade: the longer side of the cross-guard, clear of its blend. None without a guard."""
    guard = np.flatnonzero(wide)
    if not len(guard): return None
    run = max(np.split(guard, np.flatnonzero(np.diff(guard) > 1) + 1), key=len)
    below, above = np.arange(0, run[0]), np.arange(run[-1] + 1, len(wide))
    side = below if len(below) > len(above) else above
    return side[~wide[side]] if len(side) >= 20 else None


def fit_thin(positions, target_ratio=None, factor=None):
    """Measure a depth-only blade thinning map for an already straight mesh (thin after straightening, never before).

    Generation makes blades two to three times too thick for their width. The map scales the blade about its own
    mid-plane so its median depth-to-width ratio meets the target, ramping in over the guard blend so the guard,
    grip and pommel are untouched. Width, length and outline do not change.

    Give either an explicit depth `factor` or a `target_ratio`; with neither the blade is halved. Halving is the
    reviewed default: on the wave-1 Claymore (0.65 as generated) the user rejected a 0.22 target as too thin and
    chose half the original thickness.
    """
    _require(target_ratio is None or factor is None, 'Give a depth factor or a target ratio, not both')
    if target_ratio is None and factor is None: factor = THIN_FACTOR
    _require(factor is None or .2 <= factor <= 1, 'Blade depth factor must lie in [0.2, 1]')
    _require(target_ratio is None or .05 <= target_ratio <= .6, 'Blade depth-to-width target must lie in [0.05, 0.6]')
    positions = np.asarray(positions, float); mean, axes = principal_frame(positions); p = (positions - mean) @ axes
    centres, mid, extent, wide, _ = _sections(p); blade = _blade_slices(wide)
    _require(blade is not None, 'No cross-guard found: the blade cannot be separated from the hilt automatically')
    major = int(np.argmax(np.nanmedian(extent[~wide], axis=0))); thin = 1 - major
    rows = np.array([i for i in blade if not np.isnan(extent[i, 0])]); _require(len(rows) >= 20, 'Too few blade sections')
    current = float(np.median(extent[rows, thin] / extent[rows, major]))
    if factor is None: factor = min(1., target_ratio / current)
    factor = float(factor); target_ratio = current * factor
    gain = np.ones(SLICES); gain[blade] = factor
    # Ramp only across the guard's blend slices next to the blade root; the guard core, grip and pommel keep gain 1.
    guard = np.flatnonzero(wide); run = max(np.split(guard, np.flatnonzero(np.diff(guard) > 1) + 1), key=len)
    ramp = run[-4:] if blade[0] > run[-1] else run[:4][::-1]; t = (np.arange(len(ramp)) + 1) / (len(ramp) + 1)
    gain[ramp] = 1 + (factor - 1) * (3 * t ** 2 - 2 * t ** 3)
    known = ~np.isnan(mid[:, thin]); plane = np.interp(centres, centres[known], mid[known, thin])
    plane = np.convolve(np.pad(plane, 18, mode='edge'), _KERNEL, mode='valid')
    return ({'mean': mean, 'axes': axes, 'table': np.column_stack([centres, plane, gain]), 'axis': np.array(1 + thin)},
            {'bladeDepthToWidthBefore': current, 'target': target_ratio, 'depthFactor': factor})


def apply_thin(positions, mapping, normals=None):
    positions = np.asarray(positions, float); mean, axes = mapping['mean'], mapping['axes']; k = int(mapping['axis'])
    centres, plane, gain = mapping['table'].T; p = (positions - mean) @ axes
    g = np.interp(p[:, 0], centres, gain); c = np.interp(p[:, 0], centres, plane); p[:, k] = c + (p[:, k] - c) * g
    moved = p @ axes.T + mean
    if normals is None: return moved
    v = np.asarray(normals, float) @ axes; v[:, k] /= g; v = v @ axes.T        # inverse-transpose of the depth scale
    return moved, v / np.linalg.norm(v, axis=1)[:, None]


def load_thin(path):
    with np.load(path, allow_pickle=False) as archive:
        _require(set(archive.files) == {'mean', 'axes', 'table', 'axis'}, 'Unexpected thinning map')
        mapping = {name: archive[name] for name in archive.files}
    _require(mapping['mean'].shape == (3,) and mapping['axes'].shape == (3, 3) and mapping['table'].shape == (SLICES, 3)
             and int(mapping['axis']) in (1, 2) and all(np.isfinite(v).all() for v in mapping.values())
             and mapping['table'][:, 2].min() > .1 and mapping['table'][:, 2].max() <= 1 + 1e-9, 'Invalid thinning map')
    return mapping


def thin(source, output, map_path=None, target_ratio=None, factor=None):
    """Write OUTPUT/thinned.glb (+ map and report); triangles, UVs, materials and textures are carried byte for byte."""
    from tools.headkit.common import pin, write
    from tools.headkit.gltf import encode, load, arrays
    source = Path(source); output = Path(output); output.mkdir(parents=True, exist_ok=False)
    source_pin = pin(source); document, binary, primitive, positions, faces, attributes = _glb(source)
    if map_path is None:
        mapping, report = fit_thin(positions, target_ratio, factor); map_path = output / 'thin-map.npz'
        with map_path.open('xb') as stream: np.savez(stream, **mapping)
        mode = 'measured'
    else: mapping, report, mode = load_thin(map_path), None, 'applied'
    normals = attributes.get('NORMAL'); buffer = bytearray(binary)
    if normals is None: moved = apply_thin(positions, mapping)
    else: moved, turned = apply_thin(positions, mapping, normals)
    _replace(document, buffer, primitive['attributes']['POSITION'], moved)
    if normals is not None: _replace(document, buffer, primitive['attributes']['NORMAL'], turned)
    target = output / 'thinned.glb'
    with target.open('xb') as stream: stream.write(encode(document, bytes(buffer)))
    after, after_faces, after_attributes = arrays(*load(target.read_bytes()))
    _require(np.array_equal(after_faces, faces) and all(np.array_equal(after_attributes[name], attributes[name])
             for name in attributes if name not in ('POSITION', 'NORMAL')), 'Thinning changed topology, UVs or other attributes')
    before_metrics, after_metrics = measure(positions), measure(after)
    result = {'source': source_pin, 'output': pin(target), 'map': dict(pin(map_path), mode=mode), 'fit': report,
              'before': before_metrics, 'after': after_metrics, 'assessmentAfter': assess(after_metrics),
              'maximumVertexMove': float(np.linalg.norm(moved - positions, axis=1).max()),
              'outlineExtentsUnchanged': bool(np.allclose(np.sort(before_metrics['extents'])[1:], np.sort(after_metrics['extents'])[1:], rtol=2e-3)),
              'method': 'depth-only scale of the blade about its mid-plane, smooth ramp at the guard; hilt untouched',
              'visualReviewRequired': True}
    write(output / 'thin.json', result, fresh=True); return result


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
    c = commands.add_parser('thin'); c.add_argument('mesh', type=Path); c.add_argument('output', type=Path); c.add_argument('--map', type=Path)
    c.add_argument('--ratio', type=float, help='target blade depth-to-width ratio'); c.add_argument('--factor', type=float, help='explicit depth factor (default 0.5)')
    a = parser.parse_args(argv)
    if a.command == 'thin':
        result = thin(a.mesh, a.output, a.map, a.ratio, a.factor)
        print(json.dumps({k: result[k] for k in ('output', 'map', 'fit', 'maximumVertexMove', 'outlineExtentsUnchanged', 'assessmentAfter')}, indent=2)); return 0
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
