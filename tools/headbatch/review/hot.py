"""hot.py HEAD_DIR ATTEMPT OUT_PNG: master->final and final->master distances (relative to master diagonal), stats, clusters
of master vertices >0.4% in head-local coordinates, and a four-view point plot of hot vertices on the master."""
import json, sys
import numpy as np
from PIL import Image, ImageDraw
from headkit.common import library
from headkit.gltf import mesh
from headbatch.head_files import fit_matrix
from headkit.mesh import physical
from headkit.neck import BASIS, transform
head, att, out = sys.argv[1:4]
b = json.load(open(head+'/bindings.json')); igl = library(b, 'igl')
R = f'{head}/run/repair/attempt-{att}/'
A = mesh(R+'master.glb'); a, af = physical(A['positions'], A['faces']); C = mesh(R+'final.glb'); c, cf = physical(C['positions'], C['faces'])
diag = float(np.linalg.norm(np.ptp(a, axis=0)))
d1 = np.sqrt(igl.point_mesh_squared_distance(a.astype(float), c.astype(float), cf.astype(np.int32))[0])/diag
d2 = np.sqrt(igl.point_mesh_squared_distance(c.astype(float), a.astype(float), af.astype(np.int32))[0])/diag
print('diag', round(diag, 4), 'master->final max %.4f%% p99 %.4f%% p99.9 %.4f%%' % (d1.max()*100, np.percentile(d1, 99)*100, np.percentile(d1, 99.9)*100),
      'final->master max %.4f%%' % (d2.max()*100), 'master verts', len(a))
for t in (.003, .004, .006, .008, .01): print(f' >{t*100:.1f}%: {(d1 > t).sum()}')
M = np.array(fit_matrix(head)); L = transform(M @ BASIS, a)
hot = np.flatnonzero(d1 > .004)
# cluster hot by 1 cm grid connectivity (simple greedy)
left = list(hot[np.argsort(-d1[hot])]); used = set(); cl = []
for i in left:
    if i in used: continue
    m = [j for j in hot if j not in used and np.linalg.norm(L[j]-L[i]) < .012]; used.update(m); cl.append((i, m))
for i, m in cl[:20]: print(f' cluster at {np.round(L[i], 3).tolist()} max {d1[i]*100:.3f}% n {len(m)}')
size = 520; Rs = {'front': [[-1, 0, 0], [0, 0, 1], [0, 1, 0]], 'left': [[0, 1, 0], [0, 0, 1], [-1, 0, 0]], 'back': [[1, 0, 0], [0, 0, 1], [0, -1, 0]], 'right': [[0, -1, 0], [0, 0, 1], [1, 0, 0]]}
lo, hi = L.min(0), L.max(0); ctr = (lo+hi)/2; ext = (hi-lo).max()*1.05; tiles = []
for v, Rm in Rs.items():
    Rm = np.array(Rm, float); S = (L-ctr) @ Rm.T; px = ((S[:, 0]/ext+.5)*size).astype(int); py = ((.5-S[:, 1]/ext)*size).astype(int)
    img = Image.new('RGB', (size, size), (40, 40, 40)); dr = ImageDraw.Draw(img)
    for x, y in zip(px[::3], py[::3]): img.putpixel((min(max(x, 0), size-1), min(max(y, 0), size-1)), (150, 150, 150))
    for j in hot:
        col = (255, 40, 40) if d1[j] > .008 else (255, 200, 0); dr.ellipse([px[j]-3, py[j]-3, px[j]+3, py[j]+3], fill=col)
    dr.text((4, 4), f'{v}: master verts >0.4% (yellow) >0.8% (red)', fill='white'); tiles.append(img)
sheet = Image.new('RGB', (size*4, size))
for k, t in enumerate(tiles): sheet.paste(t, (k*size, 0))
sheet.save(out); print(out)
