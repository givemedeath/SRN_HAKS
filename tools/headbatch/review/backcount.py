"""backcount.py GLB: per height band, vertex count and back-most y (rel) of vertices within the central x band; shows where the back of the skull is missing."""
import sys, numpy as np
from headkit.gltf import mesh
p = np.asarray(mesh(sys.argv[1])['positions'], float); P = np.stack([-p[:, 0], p[:, 2], p[:, 1]], 1); lo, hi = P.min(0), P.max(0); R = (P-lo)/(hi-lo)
for z in np.arange(.30, .90, .025):
    s = (R[:, 2] >= z) & (R[:, 2] < z+.025) & (np.abs(R[:, 0]-.5) < .12)
    print(f'z {z:.3f}  central verts {s.sum():7d}  back-most y {R[s,1].min() if s.any() else float("nan"):.3f}  front-most y {R[s,1].max() if s.any() else float("nan"):.3f}  verts y<0.35: {(s & (R[:,1]<.35)).sum()}')
print('height m', (hi-lo).round(3))
