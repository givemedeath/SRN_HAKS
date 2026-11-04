"""grid.py UV_GLB FIT.json TEX OUT.png: head-local views textured, with bbox-relative (GLB frame, as ownership rules) x/y/z iso-lines every 0.05 (labelled every 0.1). Rows: x lines, y lines, z lines."""
import sys, json
import numpy as np
from PIL import Image, ImageDraw
from headkit.gltf import mesh
from _frame import VIEWS
src, mf, texp, out = sys.argv[1:5]; size = 700
M = np.array(json.load(open(mf))); tex = np.asarray(Image.open(texp).convert('RGB'), float)
m = mesh(src); V = np.asarray(m['positions'], float); F = np.asarray(m['faces']).reshape(-1, 3)
lo, hi = V.min(0), V.max(0); rel = (V-lo)/(hi-lo)
W = np.stack([V[:, 0], -V[:, 2], V[:, 1]], 1) @ M[:3, :3].T + M[:3, 3]
UV = np.asarray(m['uv'], float); UV = UV.reshape(len(F), 3, 2) if UV.ndim == 3 or len(UV) == len(F)*3 else UV[F]
fn = np.cross(W[F[:, 1]]-W[F[:, 0]], W[F[:, 2]]-W[F[:, 0]]); area = np.linalg.norm(fn, axis=1)/2
wl, wh = W.min(0), W.max(0); ctr = (wl+wh)/2; ext = (wh-wl).max()*1.05
k = np.clip(np.ceil(area*(size/ext)**2*4).astype(int), 1, 400); fi = np.repeat(np.arange(len(F)), k)
u = np.random.default_rng(0).random((len(fi), 2)); fl = u.sum(1) > 1; u[fl] = 1-u[fl]; b = np.stack([1-u.sum(1), u[:, 0], u[:, 1]], 1)
P = np.einsum('ij,ijk->ik', b, W[F[fi]]); Rl = np.einsum('ij,ijk->ik', b, rel[F[fi]]); T = np.einsum('ij,ijk->ik', b, UV[fi])
H_, Wd = tex.shape[:2]; col = tex[np.clip((T[:, 1]*H_).astype(int), 0, H_-1), np.clip((T[:, 0]*Wd).astype(int), 0, Wd-1)]
views = []
for v in ('front', 'back', 'left', 'right', 'top'):  # one projection per view; the three rows differ only in their iso-lines
    R = np.array(VIEWS[v], float); S = (P-ctr) @ R.T
    px = ((S[:, 0]/ext+.5)*size).astype(int); py = ((.5-S[:, 1]/ext)*size).astype(int)
    ok = (px >= 0) & (px < size) & (py >= 0) & (py < size); o = np.flatnonzero(ok)[np.argsort(S[ok, 2])]
    base = np.full((size, size, 3), 40.0); base[py[o], px[o]] = col[o]*.75
    views.append((v, py[o], px[o], o, base))
rows = []
for ax in range(3):
    tiles = []
    for v, ys_, xs_, o, base in views:
        img = base.copy(); val = np.full((size, size), -1.0); val[ys_, xs_] = Rl[o, ax]
        for L in np.arange(.05, 1, .05):
            mk = np.abs(val-L) < .0035; c = (255, 40, 40) if round(L*20) % 2 == 0 else (60, 220, 255); img[mk] = c
        im = Image.fromarray(img.astype(np.uint8)); dr = ImageDraw.Draw(im)
        for L in np.arange(.1, 1, .1):
            ys, xs = np.nonzero(np.abs(val-L) < .0035)
            if len(xs) > 20:
                j = np.argsort(xs)[len(xs)//2] if ax != 0 else np.argsort(ys)[len(ys)//2]; dr.text((xs[j]+2, ys[j]-10), f'{L:.1f}', fill=(255, 255, 0))
        dr.text((4, 4), f'{"xyz"[ax]} {v}', fill=(255, 255, 0)); tiles.append(im)
    row = Image.new('RGB', (size*len(tiles), size))
    for j, t in enumerate(tiles): row.paste(t, (j*size, 0))
    rows.append(row)
sheet = Image.new('RGB', (rows[0].width, size*3))
for i, r in enumerate(rows): sheet.paste(r, (0, i*size))
sheet.save(out); print(out)
