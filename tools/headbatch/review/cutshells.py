"""cutshells.py HEAD_DIR UNCUT_GLB OUT_JSON OUT_PNG: reproduce repair's neck cut + rewrap (same Alpha Wrap distances, diagonal of the
precluster source) on the uncut master, list every shell of the re-wrap in head-local coordinates, draw extra shells in red."""
import glob, json, sys
import numpy as np
from PIL import Image, ImageDraw
import headkit.neck as N
from headkit.common import library
from headkit.gltf import mesh
from headkit.mesh import physical, shells
head, uncut, oj, op = sys.argv[1:5]
man = json.load(open(head+'/manifest.json')); b = json.load(open(head+'/bindings.json')); st = json.load(open(head+'/run/state.json'))['stages']
fit = man['fit']['matrix'] if 'matrix' in man['fit'] else json.load(open(st['fit']['path']))['result']['matrix']; pol = man['mesh']  # explicit refit matrix first
src = mesh(sorted(glob.glob(head+'/run/precluster/attempt-*/oriented.glb'))[-1]); sv, _ = physical(src['positions'], src['faces']); diag = float(np.linalg.norm(np.ptp(sv, axis=0)))
ml = library(b, 'pymeshlab'); alpha = pol.get('alphaRelative', .005); offset = pol.get('offsetRelative', .00025)
def wrap(v, f):
    ms = ml.MeshSet(); ms.add_mesh(ml.Mesh(v.astype(float), f.astype(np.int32)))
    ms.generate_alpha_wrap(alpha=ml.PureValue(diag*alpha), offset=ml.PureValue(diag*offset)); c = ms.current_mesh(); c.compact(); return c.vertex_matrix(), c.face_matrix()
neck = N.neck_policy(pol['neck'], {'matrix': fit, 'reviewed': True})
m = mesh(uncut); V, F = physical(m['positions'], m['faces'])
V2, F2, rec = N.neck_cut(V, F, neck, N.body_neck(head+'/'+man['inputs']['bodyNeck']['path']), rewrap=wrap)
print({k: v for k, v in rec.items() if k not in ('profile',)} if isinstance(rec, dict) else rec)
L = N.transform(neck['frame'], V2); lab = shells(V2, F2); c = V2[F2]
area = np.linalg.norm(np.cross(c[:, 1]-c[:, 0], c[:, 2]-c[:, 0]), axis=1)/2; tot = np.bincount(lab, area); keep = int(np.argmax(tot))
out = []
for k in np.argsort(-tot):
    vs = L[np.unique(F2[lab == k])]
    out.append({'shell': int(k), 'kept': k == keep, 'triangles': int((lab == k).sum()), 'areaFraction': round(float(tot[k]/tot.sum()), 6),
                'min': vs.min(0).round(4).tolist(), 'max': vs.max(0).round(4).tolist(), 'centre': vs.mean(0).round(4).tolist()})
    print(out[-1])
json.dump({'cut': {k: v for k, v in rec.items() if isinstance(v, (int, float, str))}, 'shells': out}, open(oj, 'w'), indent=1, default=str)
ROT = {'front': [[-1, 0, 0], [0, 0, 1], [0, 1, 0]], 'back': [[1, 0, 0], [0, 0, 1], [0, -1, 0]], 'left': [[0, 1, 0], [0, 0, 1], [-1, 0, 0]],
       'right': [[0, -1, 0], [0, 0, 1], [1, 0, 0]], 'bottom': [[-1, 0, 0], [0, 1, 0], [0, 0, -1]]}
S = 500; lo, hi = L.min(0), L.max(0); ctr = (lo+hi)/2; ext = (hi-lo).max()*1.1; rng = np.random.default_rng(0)
cc = L[F2]; fa = area/area.sum(); pick = rng.choice(len(F2), 1500000, p=fa); u = rng.random((len(pick), 2)); fl = u.sum(1) > 1; u[fl] = 1-u[fl]
P = cc[pick, 0]+u[:, :1]*(cc[pick, 1]-cc[pick, 0])+u[:, 1:]*(cc[pick, 2]-cc[pick, 0]); red = lab[pick] != keep
n = np.cross(cc[:, 1]-cc[:, 0], cc[:, 2]-cc[:, 0]); n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12); N_ = n[pick]
sheet = Image.new('RGB', (S*len(ROT), S), (40, 40, 40))
for j, (v, R) in enumerate(ROT.items()):
    R = np.array(R, float); Q = (P-ctr) @ R.T; sh = np.clip((N_ @ R.T) @ np.array([-.3, .4, .85]), 0, 1)*200+40
    px = ((Q[:, 0]/ext+.5)*S).astype(int); py = ((.5-Q[:, 1]/ext)*S).astype(int); o = np.argsort(Q[:, 2])
    img = np.full((S, S, 3), 40, np.uint8); col = np.stack([sh]*3, 1).astype(np.uint8); col[red] = (230, 40, 40); img[py[o], px[o]] = col[o]
    im = Image.fromarray(img); ImageDraw.Draw(im).text((4, 4), f'{v} (red = extra shells)', fill=(255, 255, 0)); sheet.paste(im, (j*S, 0))
sheet.save(op); print(op)
