"""cutdry.py HEAD_DIR [HEIGHT]: dry-run jaw_line, or the plane at an explicit HEIGHT, and report plane band extents vs the body neck z range."""
import json, sys, glob
import numpy as np
import headkit.neck as N
from _frame import band, head_neck, local_positions
head = sys.argv[1]
man, neck, bv, bf = head_neck(head)
uncut = sorted(glob.glob(head+'/run/repair/attempt-*/master-uncut.glb'))[-1]
L = local_positions(neck, uncut)
cut = neck['cut']; print('local min', L.min(0).round(4), 'max', L.max(0).round(4), 'body z', bv[:, 2].min().round(4), bv[:, 2].max().round(4))
if len(sys.argv) > 2: h = float(sys.argv[2]); jaw = None; cut = dict(cut, height=h)
else:
    jaw = N.measured_jaw(L, bv, bf, cut); print('jaw', jaw)
plane, moving = band(L, cut, jaw, bv, bf); above = L[:, 2]-plane; h = float((plane-cut['slope']*L[:, 1])[0])
ha = np.maximum(L[moving, 2], plane[moving]); print('height', round(h, 4), 'height_at range', ha.min().round(4), ha.max().round(4))
# plane rim z where the plane crosses the surface
near = np.abs(above) < .003; print('rim z range', L[near, 2].min().round(4), L[near, 2].max().round(4), 'rim y range', L[near, 1].min().round(4), L[near, 1].max().round(4))
# Star-shape check of the cut ring (dwarf-female-a repair attempt-02 failed "Cut ring is not star-shaped"): per 10-degree
# bin about the rim centre, the radial spread of near-plane surface points; > 1.5 cm means the plane crosses the surface twice.
ring = L[near][:, :2]; c = ring.mean(0); ang = np.degrees(np.arctan2(*(ring-c).T[::-1])); rad = np.linalg.norm(ring-c, axis=1)
bad = [int(b) for b in range(-180, 180, 10) if ((ang >= b) & (ang < b+10)).sum() > 3 and np.ptp(rad[(ang >= b) & (ang < b+10)]) > .015]
print('ring star-shaped' if not bad else f'RING NOT STAR-SHAPED in bins {bad} (deg about the rim centre)')
