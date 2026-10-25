"""Open-occiput check on a raw Pixal shape, before the appearance pass and the CPU chain.

Single-view Pixal shapes sometimes leave the back of the skull open: sparse hair cards over no skull, so the back view
shows the inside of the face shell (troll batch v2: two seeds of one slicked-back-hair design, one more on a reseedable
shape). Precluster and the repair wrap cannot fix that, and an agent finds it only after a long precluster, so check the
raw GLB first. Read-only; no stage depends on it.

Method: face area per 2.5% height band (glTF y up) in the central back third (|x - centre| < width/6, z behind the
centre by more than a quarter of the depth). OPEN when two or more adjacent bands between 35% and 80% of the height
hold less than 5% of the median non-empty band area. Validated on troll batch v2: both open shapes flagged, every closed
shape passed (a stubble or bald scalp gives a low floor, not a gap).
"""
import itertools

import numpy as np

from .gltf import mesh

BANDS, LOW, HIGH, FLOOR = 40, 14, 32, .05


def back_coverage(path):
    """Per-band back face area (m^2) and the verdict for a GLB."""
    m = mesh(path); vertices = np.asarray(m['positions'], float); faces = np.asarray(m['faces']).reshape(-1, 3)
    lo, hi = vertices.min(0), vertices.max(0); centre = (lo+hi)/2; extent = hi-lo; corners = vertices[faces]
    centroids = corners.mean(1); area = np.linalg.norm(np.cross(corners[:, 1]-corners[:, 0], corners[:, 2]-corners[:, 0]), axis=1)/2
    back = (np.abs(centroids[:, 0]-centre[0]) < extent[0]/6) & (centroids[:, 2] < centre[2]-.25*extent[2])
    height = (centroids[:, 1]-lo[1])/extent[1]
    bands = np.array([area[back & (height >= b/BANDS) & (height < (b+1)/BANDS)].sum() for b in range(BANDS)])
    filled = bands[bands > 0]; floor = FLOOR*float(np.median(filled)) if len(filled) else 0.0
    low = [b for b in range(LOW, HIGH) if bands[b] < floor]
    run = max((sum(1 for _ in group) for adjacent, group in itertools.groupby(np.diff(low) == 1) if adjacent), default=0)+1 if low else 0
    return {'open': run >= 2, 'lowBands': [round(b/BANDS, 3) for b in low], 'floorSquareCm': round(floor*1e4, 2),
            'bandSquareCm': [round(float(v)*1e4, 2) for v in bands]}
