"""Automatic fit measurement for straight bladed weapons: landmarks, grip span, part cuts and shell thinning.

These replace hand-picked grip endpoints, join positions and working-shell preparation. They measure; they do
not approve. The fitted result still needs the hand-fit review on both shipped Human bodies.
"""
import numpy as np
from .straightness import SLICES, _require, _sections, principal_frame

# A dense shell puts hundreds of vertices on each part-cut rim, and every triangle touching a rim is protected
# from reduction: at 200K triangles the rims alone exceeded the 700 to 1,800 triangle part budgets (wave 1).
WORKING_SHELL_TRIANGLES = 40000


def _runs(mask):
    index = np.flatnonzero(mask)
    return [run for run in np.split(index, np.flatnonzero(np.diff(index) > 1) + 1) if len(run)]


def landmarks(positions):
    """Pommel, usable grip, guard and blade along the long axis of a straight weapon.

    Returns the oriented frame (blade toward +long) and fractions of the length measured from the butt:
    pommelEnd, gripStart, gripEnd, bladeStart. `method` is 'cross-guard' when a wide guard separates hilt and
    blade, else 'thin-blade' (a knife: the blade is the long run that is thin in depth, the guard a thicker ring).
    """
    positions = np.asarray(positions, float); mean, axes = principal_frame(positions); q = (positions - mean) @ axes
    centres, mid, extent, wide, _ = _sections(q)
    known = ~np.isnan(extent[:, 0]); depth = np.where(known, extent.min(1), 0)
    guard = max(_runs(wide), key=len) if wide.any() else None
    if guard is not None and 5 < guard[0] and guard[-1] < SLICES - 6:
        method = 'cross-guard'; flip = guard[0] > SLICES - 1 - guard[-1]
    else:
        method = 'thin-blade'; runs = _runs(depth < .5 * np.percentile(depth[known], 75))
        _require(bool(runs), 'Neither a cross-guard nor a thin blade was found'); flip = max(runs, key=len).mean() < SLICES / 2
    if flip: axes = axes * [-1, -1, 1]; q = q * [-1, -1, 1]; centres, mid, extent, wide, _ = _sections(q)
    known = ~np.isnan(extent[:, 0]); width = np.where(known, extent.max(1), 0); depth = np.where(known, extent.min(1), 0)
    if method == 'cross-guard':
        core = np.flatnonzero(np.nan_to_num(extent.max(1)) > 2 * np.nanmedian(extent.max(1))); g0, g1 = int(core[0]), int(core[-1])
    else:
        blade = max(_runs(depth < .5 * np.percentile(depth[known], 75)), key=len); g1 = int(blade[0]) - 1
        handle = np.arange(0, blade[0]); body = np.median(depth[handle[len(handle) // 5: -len(handle) // 5]])
        window = np.arange(max(0, g1 - SLICES // 10), g1 + 1); ring = window[depth[window] > 1.25 * body]
        g0 = int(ring[0]) if len(ring) else g1
    handle = np.arange(0, g0); _require(len(handle) >= 12, 'Handle too short to measure')
    grip_width = np.median(width[handle[len(handle) // 4: -len(handle) // 4]])
    bulge = np.flatnonzero(width[:len(handle) // 2] > 1.1 * grip_width)
    pommel = max(int(bulge[-1]) + 1 if len(bulge) else 0, int(round(.04 * len(handle))))
    marks = {'pommelEnd': pommel / SLICES, 'gripStart': pommel / SLICES, 'gripEnd': g0 / SLICES, 'bladeStart': (g1 + 1) / SLICES}
    return {'method': method, 'landmarks': marks, 'mean': mean, 'axes': axes, 'start': float(q[:, 0].min()),
            'length': float(np.ptp(q[:, 0])), 'centres': centres, 'midline': mid, 'extent': extent}


def grip_start_for_length(marks, grip_length, target_length):
    """Butt-side grip landmark that makes the whole weapon `target_length` once the grip span is scaled to `grip_length`.

    A strict pommel-to-guard span on a design with a short grip overscales the weapon: the wave-1 Sword came out
    1.26 m against a 1.10 m stock longsword and was sent back. Extending the hand span into the pommel lowers the
    scale; the pommel|grip cut still belongs at pommelEnd. The result never leaves [0, pommelEnd]: a design whose
    strict span already gives a shorter weapon keeps its strict span.
    """
    _require(grip_length > 0 and target_length > grip_length, 'Target length must exceed the grip length')
    start = marks['gripEnd'] - grip_length / target_length
    return float(min(marks['pommelEnd'], max(0., start)))


def clear_cut(vertex_y, y, reach=.0003, step=.000005):
    """Move a part cut by at most `reach` metres to the plane farthest from any vertex.

    A cut through source vertices leaves degenerate cap triangles and the part fails its closed-solid check.
    Returns (cut position, clearance to the nearest vertex).
    """
    near = np.sort(np.asarray(vertex_y, float)); near = near[np.abs(near - y) < reach + .0001]
    if not len(near): return float(y), None
    candidates = y + np.arange(-reach, reach + step / 2, step); k = np.searchsorted(near, candidates)
    gap = np.minimum(np.abs(candidates - near[np.clip(k - 1, 0, len(near) - 1)]), np.abs(near[np.clip(k, 0, len(near) - 1)] - candidates))
    best = int(np.argmax(gap - 1e-9 * np.abs(candidates - y)))
    return float(candidates[best]), float(gap[best])


def thin_shell(positions, faces, meshlab, triangles=WORKING_SHELL_TRIANGLES, tolerance=.0025, distances=None):
    """Topology-preserving collapse of a closed working shell; returns (vertices, faces, report).

    The result must stay one closed outward solid of the same genus, within `tolerance` of the longest extent.
    `distances(points, vertices, faces)` may supply exact point-to-surface distances (libigl); without it the
    check falls back to nearest-vertex distance, which only over-reports.
    """
    from .geometry import topology
    p = np.asarray(positions, float); f = np.asarray(faces, np.int32); before = topology(p, f)
    _require(before['closedWound'], 'Closed outward working shell required')
    if len(f) <= triangles: return p.copy(), f.copy(), {'triangles': len(f), 'unchanged': True}
    mesh_set = meshlab.MeshSet(); mesh_set.add_mesh(meshlab.Mesh(p, f))
    mesh_set.meshing_remove_duplicate_vertices()          # GLB transport stores unshared corners; collapse needs connectivity
    mesh_set.meshing_decimation_quadric_edge_collapse(targetfacenum=int(triangles), preservetopology=True, preservenormal=True,
                                                     qualitythr=.5, planarquadric=True)
    mesh_set.meshing_remove_unreferenced_vertices(); current = mesh_set.current_mesh()
    v, t = current.vertex_matrix(), current.face_matrix().astype(np.int32); after = topology(v, t)
    _require(after['closedWound'] and after['totalGenus'] == before['totalGenus'] and after['degenerate'] == 0,
             'Shell thinning broke the closed solid')
    _require(len(t) <= triangles * 1.05, 'Shell thinning stalled above its target')
    if distances is None:
        from scipy.spatial import cKDTree
        worst = max(float(cKDTree(p).query(v)[0].max()), float(cKDTree(v).query(p[::7])[0].max()))
    else: worst = max(float(np.max(distances(v, p, f))), float(np.max(distances(p[::7], v, t))))
    scale = float(np.ptp(p, axis=0).max()); _require(worst <= tolerance * scale, 'Shell thinning moved the surface beyond tolerance')
    return v, t, {'triangles': len(t), 'sourceTriangles': len(f), 'genus': after['totalGenus'], 'maximumDistance': worst,
                  'maximumDistanceFractionOfLength': worst / scale, 'volumeRatio': after['signedVolume'] / before['signedVolume']}
