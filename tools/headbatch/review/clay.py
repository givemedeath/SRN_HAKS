"""clay.py OUT.png LABEL=GLB [...] [--views front,left,back,right,top,bottom] [--size N] [--matrix FIT.json] [--zlines z,..]
[--tex IMG] [--lit 0..1] [--two-sided]: orthographic z-buffered renders of GLB meshes in the NWN head frame (GLB->NWN (x,-z,y), then the fit
matrix), one row per mesh, area-weighted surface samples. Clay (lambert) or texture colour (--tex, sampled at UV) with --lit shading.
front: face toward viewer, character right on image left (design convention). left/right: character's left/right side.
--two-sided shades back faces by |N|, which tells inverted precluster normals (harmless, Alpha Wrap rebuilds orientation) from a real extra shell."""
import sys, json
import numpy as np
from PIL import Image, ImageDraw
from headkit.gltf import mesh

args = sys.argv[1:]; out = args.pop(0)
views = ['front', 'left', 'back', 'right']; frame = None; size = 420; matrix = None; zlines = []; tex = None; lit = .35; items = []; two_sided = False
i = 0
while i < len(args):
    a = args[i]
    if a == '--views': views = args[i+1].split(','); i += 2; continue
    if a == '--size': size = int(args[i+1]); i += 2; continue
    if a == '--matrix': matrix = np.array(json.load(open(args[i+1]))); i += 2; continue
    if a == '--zlines': zlines = [float(v) for v in args[i+1].split(',')]; i += 2; continue
    if a == '--tex': tex = np.asarray(Image.open(args[i+1]).convert('RGB'), float); i += 2; continue
    if a == '--two-sided': two_sided = True; i += 1; continue
    if a == '--lit': lit = float(args[i+1]); i += 2; continue
    if a == '--frame': fv = [float(v) for v in args[i+1].split(',')]; frame = (np.array(fv[:3]), fv[3]); i += 2; continue
    label, path = a.split('=', 1); items.append((label, path)); i += 1

ROT = {'front': [[-1, 0, 0], [0, 0, 1], [0, 1, 0]], 'back': [[1, 0, 0], [0, 0, 1], [0, -1, 0]],
       'left': [[0, 1, 0], [0, 0, 1], [-1, 0, 0]], 'right': [[0, -1, 0], [0, 0, 1], [1, 0, 0]],
       'top': [[-1, 0, 0], [0, -1, 0], [0, 0, 1]], 'bottom': [[-1, 0, 0], [0, 1, 0], [0, 0, -1]]}
light = np.array([-.35, .45, .82]); light /= np.linalg.norm(light)
rows = []
for label, path in items:
    m = mesh(path); V = np.asarray(m['positions'], float); F = np.asarray(m['faces']).reshape(-1, 3)
    W = np.stack([V[:, 0], -V[:, 2], V[:, 1]], 1)
    if matrix is not None: W = W @ matrix[:3, :3].T + matrix[:3, 3]
    fn = np.cross(W[F[:, 1]]-W[F[:, 0]], W[F[:, 2]]-W[F[:, 0]]); vn = np.zeros_like(W)
    for k in range(3): np.add.at(vn, F[:, k], fn)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
    lo, hi = W.min(0), W.max(0)
    if frame is None: frame = ((lo+hi)/2, (hi-lo).max()*1.08)
    ctr, ext = frame
    area = np.linalg.norm(fn, axis=1)/2; k = np.clip(np.ceil(area*(size/ext)**2*3).astype(int), 1, 400); fi = np.repeat(np.arange(len(F)), k)
    u = np.random.default_rng(0).random((len(fi), 2)); flip = u.sum(1) > 1; u[flip] = 1-u[flip]
    b = np.stack([1-u.sum(1), u[:, 0], u[:, 1]], 1)
    P = np.einsum('ij,ijk->ik', b, W[F[fi]]); N = np.einsum('ij,ijk->ik', b, vn[F[fi]]); N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
    col = None
    if tex is not None:
        UV = np.asarray(m['uv'], float).reshape(len(F), 3, 2) if np.asarray(m['uv']).ndim == 3 else np.asarray(m['uv'], float)[F]
        T = np.einsum('ij,ijk->ik', b, UV[fi]); H, Wd = tex.shape[:2]
        col = tex[np.clip((T[:, 1]*H).astype(int), 0, H-1), np.clip((T[:, 0]*Wd).astype(int), 0, Wd-1)]
    tiles = []
    for v in views:
        R = np.array(ROT[v], float); S = (P-ctr) @ R.T; Nn = N @ R.T
        if two_sided: Nn = Nn*np.sign(Nn[:, 2:3]+1e-9)
        shade = np.clip(Nn @ light, 0, 1)*.8+.15 if two_sided else np.where(Nn[:, 2] < 0, .12, np.clip(Nn @ light, 0, 1)*.8+.15)
        px = ((S[:, 0]/ext+.5)*size).astype(int); py = ((.5-S[:, 1]/ext)*size).astype(int)
        ok = (px >= 0) & (px < size) & (py >= 0) & (py < size); o = np.flatnonzero(ok)[np.argsort(S[ok, 2])]
        if col is None:
            img = np.full((size, size, 3), 40.0); img[py[o], px[o]] = (shade[o]*235)[:, None]
        else:
            c = col*((1-lit)+lit*np.clip(shade, 0, 1)/.95)[:, None]; img = np.full((size, size, 3), 40.0); img[py[o], px[o]] = c[o]
        im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)); dr = ImageDraw.Draw(im)
        for z in zlines:
            if v in ('top', 'bottom'): continue
            yy = int((.5-(z-ctr[2])/ext)*size); dr.line([(0, yy), (size, yy)], fill=(220, 60, 40)); dr.text((size-60, yy-12), f'z {z:+.3f}', fill=(220, 60, 40))
        dr.text((4, 4), f'{label} {v}', fill=(255, 255, 0)); tiles.append(im)
    row = Image.new('RGB', (size*len(tiles), size))
    for j, t in enumerate(tiles): row.paste(t, (j*size, 0))
    rows.append(row); print(label, path.split('/')[-1], 'faces', len(F), 'bounds', np.round(lo, 4), np.round(hi, 4))
sheet = Image.new('RGB', (max(r.width for r in rows), sum(r.height for r in rows))); y = 0
for r in rows: sheet.paste(r, (0, y)); y += r.height
sheet.save(out); print(out, sheet.size)
