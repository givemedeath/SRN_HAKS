"""boundary.py GLB OUT.png: boundary edges of the mesh, grouped into loops by vertex connectivity; report the largest loops'
extent in the viewing frame (x right-left, y face, z up, glTF->(-x,z,y)) and draw them on back/side views."""
import sys, numpy as np
from PIL import Image, ImageDraw
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from headkit.gltf import mesh
from headkit.mesh import physical
m = mesh(sys.argv[1]); V, F = physical(m['positions'], m['faces']); P = np.stack([-V[:, 0], V[:, 2], V[:, 1]], 1)
E = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), 1); u, c = np.unique(E, axis=0, return_counts=True); B = u[c == 1]
print('faces', len(F), 'verts', len(V), 'boundary edges', len(B), 'non-manifold edges', int((c > 2).sum()))
n = len(V); A = coo_matrix((np.ones(len(B)), (B[:, 0], B[:, 1])), shape=(n, n)); k, lab = connected_components(A, directed=False)
bv = np.unique(B); L = lab[bv]; ids, cnt = np.unique(L, return_counts=True); order = np.argsort(-cnt)
lo, hi = P.min(0), P.max(0); rel = lambda q: (q-lo)/(hi-lo)
for i in order[:8]:
    q = P[bv[L == ids[i]]]; r = rel(q); print(f' loop {cnt[i]} verts: rel x {r[:,0].min():.2f}-{r[:,0].max():.2f} y(face) {r[:,1].min():.2f}-{r[:,1].max():.2f} z {r[:,2].min():.2f}-{r[:,2].max():.2f}, span {np.ptp(q,0).round(3)}')
S = 500; img = Image.new('RGB', (S*2, S), (30, 30, 30)); d = ImageDraw.Draw(img); ext = (hi-lo).max()*1.05; c0 = (lo+hi)/2
for j, (a, b) in enumerate(((0, 2), (1, 2))):
    for x, y in zip(((P[::40, a]-c0[a])/ext+.5)*S, (.5-(P[::40, 2]-c0[2])/ext)*S): img.putpixel((j*S+int(np.clip(x, 0, S-1)), int(np.clip(y, 0, S-1))), (110, 110, 110))
    cols = [(255, 60, 60), (255, 200, 0), (60, 200, 255), (80, 255, 80)]
    for t, i in enumerate(order[:4]):
        q = P[bv[L == ids[i]]]
        for x, y in zip(((q[:, a]-c0[a])/ext+.5)*S, (.5-(q[:, 2]-c0[2])/ext)*S): img.putpixel((j*S+int(np.clip(x, 0, S-1)), int(np.clip(y, 0, S-1))), cols[t])
d.text((4, 4), 'back-ish (x,z) | side (y=face right, z): largest boundary loops red/yellow/blue/green', fill='white'); img.save(sys.argv[2])
