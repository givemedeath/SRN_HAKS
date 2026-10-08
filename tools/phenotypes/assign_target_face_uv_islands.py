"""Give rebuilt faces (cap, pinhole, repair fans) their own UV islands in empty atlas space.

Faces flagged new (face-source -1 from the topology step) are grouped by shared vertices. Each group is
planar-projected (PCA plane), scaled to the median texel density of the surrounding retained skin, and
placed in the first empty atlas rectangle (all primitives share one atlas). Rim vertices are split, so
retained faces keep their exact UVs. Positions, normals and indices of retained faces are unchanged.
"""
import argparse, json, shutil
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

from descendant_mesh_edit import Mesh, Descendant, require, sha, write_receipt


def coverage(uv_tris, size):
    img = Image.new('L', (size, size), 0); d = ImageDraw.Draw(img)
    for tri in uv_tris:
        d.polygon([(float(u) * size, float(v) * size) for u, v in tri], fill=255)
    return np.asarray(img) > 0


def groups_of(F, faces):
    parent = {int(f): int(f) for f in faces}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    owner = {}
    for f in faces:
        for v in F[f]:
            v = int(v)
            if v in owner:
                a, b = find(owner[v]), find(int(f))
                if a != b:
                    parent[a] = b
            else:
                owner[v] = int(f)
    out = {}
    for f in faces:
        out.setdefault(find(int(f)), []).append(int(f))
    return list(out.values())


def find_slot(occupied, w, h, cell=8):
    """Top-left (x, y) in pixels of the first empty w x h rectangle on a coarse grid."""
    H, W = occupied.shape
    gh, gw = H // cell, W // cell
    grid = occupied[:gh * cell, :gw * cell].reshape(gh, cell, gw, cell).any(axis=(1, 3))
    cw, ch = int(np.ceil(w / cell)) + 1, int(np.ceil(h / cell)) + 1
    S = np.pad(grid.astype(int).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    for y in range(1, gh - ch):
        for x in range(1, gw - cw):
            if S[y + ch, x + cw] - S[y, x + cw] - S[y + ch, x] + S[y, x] == 0:
                return x * cell, y * cell
    raise RuntimeError('No empty atlas space for a %dx%d island' % (w, h))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    require(not a.output.exists(), 'Fresh output required')
    cfg = json.loads(a.config.read_text())
    src = Path(cfg['master']); require(sha(src) == cfg['masterSha256'], 'Parent changed')
    fs_path = Path(cfg['faceSource']); require(sha(fs_path) == cfg['faceSourceSha256'], 'Face source changed')
    mesh = Mesh(src); fs = np.load(fs_path)
    require(len(fs) == len(mesh.F), 'Face source length mismatch')
    size = cfg.get('atlasSize', 2048); margin = cfg.get('marginPixels', 12)
    P, N, T = mesh.corners()
    new = np.flatnonzero(fs < 0); old = np.flatnonzero(fs >= 0)
    occupied = coverage(T[old], size)
    occupied = np.asarray(Image.fromarray(occupied.astype(np.uint8) * 255).filter(__import__('PIL.ImageFilter', fromlist=['MaxFilter']).MaxFilter(2 * margin + 1))) > 0
    # texel density of retained skin near the new faces: px per metre
    area3 = 0.5 * np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1)
    e1 = T[:, 1] - T[:, 0]; e2 = T[:, 2] - T[:, 0]
    area2 = 0.5 * np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) * size * size
    cen = P.mean(1)
    desc = Descendant(mesh)
    islands = []
    for group in groups_of(mesh.F, new):
        g = np.asarray(group)
        c = cen[g].mean(0)
        near = old[np.linalg.norm(cen[old] - c, axis=1) < cfg.get('densityRadius', 0.06)]
        density = float(np.sqrt(np.median(area2[near] / np.maximum(area3[near], 1e-12)))) if len(near) else 2000.0
        pts = P[g].reshape(-1, 3)
        mu = pts.mean(0); _, _, vt = np.linalg.svd(pts - mu, full_matrices=False)
        xy = (pts - mu) @ vt[:2].T * density
        lo = xy.min(0); w, h = np.ptp(xy, 0) + 2
        x0, y0 = find_slot(occupied, w + 2 * margin, h + 2 * margin)
        uv = (xy - lo + [x0 + margin, y0 + margin]) / size
        for k, f in enumerate(g):
            desc.corner_uv_override[int(f)] = uv[3 * k:3 * k + 3]
        x1, y1 = int(x0 + w + 2 * margin), int(y0 + h + 2 * margin)
        occupied[y0:y1, x0:x1] = True
        islands.append(dict(faces=len(g), centreLocal=c.tolist(), pxPerMeter=density, rectPx=[int(x0), int(y0), x1, y1]))
    a.output.mkdir(parents=True)
    out = a.output / (cfg.get('name', 'uv-islands') + '-local.glb')
    built = desc.write(out)
    # retained faces keep their UVs exactly (same primitives and face order)
    P2, N2, T2 = built.corners()
    require(len(P2) == len(P), 'Face count changed')
    require(np.abs(T2[old] - T[old]).max() < 1e-7 and np.abs(P2 - P).max() < 1e-6, 'Retained UVs or positions changed')
    np.save(out.with_suffix('.face-source.npy'), fs)
    rec = dict(schemaVersion=1, kind='face-uv-island-descendant', parent={'path': str(src), 'sha256': sha(src)}, faceSource={'path': str(fs_path), 'sha256': sha(fs_path)},
               descendant={'path': str(out), 'sha256': sha(out)}, islands=islands, atlasSize=size, marginPixels=margin, config=cfg, helperSha256=sha(__file__),
               policy='Only UVs of rebuilt faces change (rim vertices split); positions/normals/retained UVs exact; texture for the islands is painted by the material stage.')
    write_receipt(a.output / 'descendant.json', rec)
    shutil.copy2(__file__, a.output / 'executed-helper.py')
    print(json.dumps({'output': str(out), 'islands': islands}))


if __name__ == '__main__':
    main()
