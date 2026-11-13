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
    for k, box in enumerate(ndimage.find_objects(labels), 1):
        if box is None or k in border: continue
        region = np.pad(labels[box] == k, 1); area = float(region.sum() * RESOLUTION ** 2)   # padded: the EDT sees its edge
        if area < MIN_HOLE_AREA: continue
        depth = ndimage.distance_transform_edt(region); i, j = np.unravel_index(np.argmax(depth), depth.shape)
        i += box[0].start - 1; j += box[1].start - 1
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
    """[{name, start, end}]: a distinct clear hole within tolerance for every reference, each preferring the most clearance.

    The references were all measured on one axis of the reference image, so the whole set is matched from one end of
    the weapon or the other, never each from its own end; when both fit, the closer one wins. References take holes in
    order, most clearance first, backing up when a later one would be left without a hole. A reference with no clear
    hole from either end is refused, as is a set no single end can place."""
    clear = [k for k, hole in enumerate(found) if not hole['hits'] and hole['clearance'] >= MIN_CLEARANCE]
    near = lambda target: sorted((k for k in clear if abs(target - found[k]['fraction']) <= MATCH_TOLERANCE),
                                 key=lambda k: -found[k]['clearance'])
    for name, fraction in references:
        require(near(fraction) or near(1 - fraction), f'No clear through-hole matches {name} (fraction {fraction:.3f}): it closed '
                'or is too narrow; drop it as a real hole with the user, or rebuild the shell')

    def assign(candidates, i=0, used=frozenset()):
        if i == len(candidates): return []
        for k in candidates[i]:
            if k in used: continue
            rest = assign(candidates, i + 1, used | {k})
            if rest is not None: return [k] + rest
        return None
    options = []
    for flip in (False, True):
        targets = [1 - fraction if flip else fraction for _, fraction in references]
        chosen = assign([near(t) for t in targets])
        if chosen is not None: options.append((sum(abs(t - found[k]['fraction']) for t, k in zip(targets, chosen)), chosen))
    require(options, f'No single end of the weapon places all {len(references)} reference openings on distinct clear '
            'through-holes: drop the missing ones with the user, or rebuild the shell')
    chosen = min(options, key=lambda option: option[0])[1]
    return [{'name': name, 'start': found[k]['start'], 'end': found[k]['end']} for (name, _), k in zip(references, chosen)]


def measure(manifest, family, handoff):
    """Every through-hole of the fitted shell and the reference openings' positions, without writing anything."""
    w, f = fitted_shell(manifest, family, handoff); y0, y1 = w[:, 1].min(), w[:, 1].max()
    found = [hole for axis in (0, 2) for hole in holes(w, f, axis)]
    for hole in found: hole['fraction'] = (hole['y'] - y0) / (y1 - y0)
    return {'nativeLength': float(y1 - y0), 'references': reference_fractions(manifest, handoff), 'holes': found}
