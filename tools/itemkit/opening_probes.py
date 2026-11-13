"""Measured probes for a fit manifest's reviewed openings: the through-holes of the fitted working shell.

    python -m tools.itemkit.drive opening-probes ID FIT_SUFFIX [--write NEW_SUFFIX]

A reference opening (`openings`, measured on the reviewed image) is kept only when `processing.openingProbes` holds a
segment through it that crosses no surface. This places the working shell exactly as the fit stage will (similarity
and the measured grip correction), projects it along each transverse axis onto a 0.5 mm grid, and takes the
background regions the silhouette encloses as through-holes. Each hole's deepest point gives a probe along the view
axis. Holes are matched to the reference openings by their position along the weapon's long axis, measured from either
end, within 3% of the length; a hole needs 1.5 mm of clearance, since a narrower gap closes in reduction (the wave-3
Vibro Knife's 2 mm lanyard hole closed in every reduced shell, 2026-11-13).
"""
import json
from pathlib import Path

import numpy as np

from tools.headkit.common import require

RESOLUTION = .0005          # projection grid, metres
MIN_HOLE_AREA = 8e-6        # holes under 8 mm^2 are ignored
MIN_CLEARANCE = .0015       # a narrower hole closes in reduction
MATCH_TOLERANCE = .03       # of the length, between a reference opening and a hole


def fitted_shell(manifest, family, handoff):
    """(vertices, faces) of the working shell placed as the fit stage places it (blender_worker.grip_fit)."""
    from tools.headkit.gltf import arrays, load
    from . import grip
    from .fit_manifest import gltf_to_blender
    handoff = Path(handoff); fit = manifest['fit']
    v, f, _ = arrays(*load((handoff/manifest['inputs']['workingMesh']['path']).read_bytes()))
    b = gltf_to_blender(v); f = np.asarray(f); M = np.asarray(fit['matrix'], float); origin = family['native']['gripOrigin']
    if 'gripStandard' in manifest['inputs']:
        standard = json.loads((handoff/manifest['inputs']['gripStandard']['path']).read_text(encoding='utf-8'))
        authority, review = fit.get('sizingAuthority'), fit.get('gripDeparture')
        if authority is None: M, _ = grip.calibration(b, f, M, origin, standard)
        elif authority == 'midpoint-depth-two-hand': M, _ = grip.two_hand_uniform(b, f, M, fit['gripEndpoints'], origin, standard, review)
        elif authority == 'usable-length-round': M, _ = grip.one_hand_round(b, f, M, origin, standard, review)
        elif authority == 'midpoint-depth-uniform':
            M, _ = grip.transverse_uniform(b, f, M, origin, standard, review, fit.get('sectionBasis', 'depth'))
        else: raise ValueError(f'Sizing authority {authority} is not placed here')
    M = np.asarray(M, float)
    return b @ M[:3, :3].T + M[:3, 3], f


def holes(vertices, faces, axis):
    """Through-holes seen along `axis` (0 = x, 2 = z): area, clearance, long-axis position and a probe segment."""
    from PIL import Image, ImageDraw
    from scipy import ndimage
    from .geometry import segment_hits
    other = 2 if axis == 0 else 0
    u, v = vertices[:, 1], vertices[:, other]; lo = np.array([u.min(), v.min()]) - .005
    size = np.ceil((np.array([u.max(), v.max()]) + .005 - lo) / RESOLUTION).astype(int)
    image = Image.new('1', tuple(size), 0); draw = ImageDraw.Draw(image)
    pu = (u - lo[0]) / RESOLUTION; pv = (v - lo[1]) / RESOLUTION
    for a, b, c in faces: draw.polygon([(pu[a], pv[a]), (pu[b], pv[b]), (pu[c], pv[c])], fill=1)
    covered = np.array(image, bool).T                                                  # [u, v]
    labels, count = ndimage.label(~covered)
    border = set(np.unique(np.r_[labels[0], labels[-1], labels[:, 0], labels[:, -1]]).tolist())
    found = []
    for k in range(1, count + 1):
        if k in border: continue
        region = labels == k; area = float(region.sum() * RESOLUTION ** 2)
        if area < MIN_HOLE_AREA: continue
        depth = ndimage.distance_transform_edt(region); i, j = np.unravel_index(np.argmax(depth), depth.shape)
        start = np.zeros(3); start[1] = lo[0] + (i + .5) * RESOLUTION; start[other] = lo[1] + (j + .5) * RESOLUTION
        end = start.copy(); start[axis] = vertices[:, axis].min() - .01; end[axis] = vertices[:, axis].max() + .01
        found.append({'axis': 'xyz'[axis], 'area': area, 'clearance': float(depth.max() * RESOLUTION), 'y': float(start[1]),
                      'start': start.tolist(), 'end': end.tolist(), 'hits': int(segment_hits(vertices, faces, start.tolist(), end.tolist()))})
    return found


def reference_fractions(manifest, handoff):
    """[(name, fraction)]: each reviewed opening's position along the long axis of the reference foreground mask."""
    from PIL import Image
    mask = np.array(Image.open(Path(handoff)/manifest['inputs']['geometryForegroundMask']['path']).convert('L')) > 127
    ys, xs = np.nonzero(mask); points = np.c_[xs, ys].astype(float); centre = points.mean(0)
    axis = np.linalg.svd(points - centre, full_matrices=False)[2][0]; t = (points - centre) @ axis; lo, hi = t.min(), t.max()
    rows = []
    for opening in manifest['openings']:
        x0, y0, x1, y1 = opening['referenceBounds']
        rows.append((opening['name'], float(((np.array([(x0 + x1) / 2, (y0 + y1) / 2]) - centre) @ axis - lo) / (hi - lo))))
    return rows


def match(references, found):
    """[{name, start, end}]: for each reference, the clear unused hole within tolerance with the most clearance.

    The reference may be measured from either end of the weapon. A reference with no clear hole is refused."""
    probes, used = [], set()
    for name, fraction in references:
        best = None
        for flip in (False, True):
            target = 1 - fraction if flip else fraction
            for k, hole in enumerate(found):
                if k in used or hole['hits'] or hole['clearance'] < MIN_CLEARANCE: continue
                if abs(target - hole['fraction']) <= MATCH_TOLERANCE and (best is None or hole['clearance'] > best[0]): best = (hole['clearance'], k)
        require(best is not None, f'No clear through-hole matches {name} (fraction {fraction:.3f}): it closed or is too narrow; '
                'drop it as a real hole with the user, or rebuild the shell')
        used.add(best[1]); probes.append({'name': name, 'start': found[best[1]]['start'], 'end': found[best[1]]['end']})
    return probes


def measure(manifest, family, handoff):
    """Every through-hole of the fitted shell and the reference openings' positions, without writing anything."""
    w, f = fitted_shell(manifest, family, handoff); y0, y1 = w[:, 1].min(), w[:, 1].max()
    found = [hole for axis in (0, 2) for hole in holes(w, f, axis)]
    for hole in found: hole['fraction'] = (hole['y'] - y0) / (y1 - y0)
    return {'nativeLength': float(y1 - y0), 'references': reference_fractions(manifest, handoff), 'holes': found}
