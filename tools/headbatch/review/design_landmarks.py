"""design_landmarks.py OUT_DIR HEAD... [--override JSON] [--no-refine]: OUT_DIR must be absolute: per-head face landmarks for the landmark fit (user 2026-10-28: per-head
landmarks, a pupil/lip detector on the design images with reviewed overlays).
1. Detect on the matted design (run/prepare/*/images/design-rgba.png): pupils = the best left/right pair of dark blobs
   (difference of Gaussians on luminance) at one height in the upper face; lip seam = the darkest row on the face midline between
   0.6 and 1.6 inter-pupil distances below the eyes. --override {"HEAD": {"eyeLeft": [px, py], "eyeRight": ..., "lips": ...}}
   replaces detections (design pixels) after review.
2. Map to the mesh: register the design to the precluster's own front silhouette (headkit palette.register: scale and offset of
   the upper 60% silhouette), turn each design pixel into glTF x/y, take the front-most surface point there, and convert to the
   toolkit head-local frame (unscaled source units, the frame fit.landmarks uses). The nose tip is the most forward point
   within the midline band between the eye line and the lip seam.
3. Review sheet per head: design with the detected marks, and the mesh front view (depth-shaded) with the mapped marks."""
import glob, json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from headkit.palette import register
from headkit.gltf import load, accessor
from headkit.fit import head_local

HEADS = Path.cwd(); SIZE = 1536  # `run_headbatch.py review` runs in the workspace heads folder


def design(head):
    path = sorted(glob.glob(str(HEADS/head/'run/prepare/attempt-*/images/design-rgba.png')))[-1]
    rgba = np.asarray(Image.open(path).convert('RGBA')).astype(float); return rgba[..., :3], rgba[..., 3] > 127, path


def detect(rgb, mask):
    L = rgb @ [.299, .587, .114]; ys, xs = np.nonzero(mask); top, bottom = ys.min(), ys.max(); H = bottom-top
    band = slice(int(top+.28*H), int(top+.62*H)); cols = xs[(ys > top+.3*H) & (ys < top+.6*H)]; mid = float(np.median(cols)); W = float(np.ptp(cols))
    dog = ndimage.gaussian_filter(L, 10)-ndimage.gaussian_filter(L, 2.5); dog[~mask] = -1e9; sub = dog[band]
    peaks = (sub == ndimage.maximum_filter(sub, 21)) & (sub > 5); py, px = np.nonzero(peaks); py = py+band.start; val = dog[py, px]
    left, right = [(x, y, v) for x, y, v in zip(px, py, val) if x < mid], [(x, y, v) for x, y, v in zip(px, py, val) if x > mid]
    best = None
    for xl, yl, vl in left:
        for xr, yr, vr in right:
            sep = xr-xl
            if not (.18*W < sep < .5*W) or abs(yl-yr) > .035*H or abs((xl+xr)/2-mid) > .08*W: continue
            score = vl+vr-3*abs(yl-yr)-2*abs((xl+xr)/2-mid)
            if best is None or score > best[0]: best = (score, (xl, yl), (xr, yr))
    if best is None: return None
    (xl, yl), (xr, yr) = best[1], best[2]; ipd = xr-xl; ey = (yl+yr)/2; cx = (xl+xr)/2
    rows = np.arange(int(ey+.6*ipd), int(ey+1.6*ipd)); Lb = ndimage.gaussian_filter(L, 2)
    profile = Lb[rows][:, int(cx-.3*ipd):int(cx+.3*ipd)].mean(1); lip = int(rows[np.argmin(profile)])
    return {'eyeLeft': [float(xl), float(yl)], 'eyeRight': [float(xr), float(yr)], 'lips': [float(cx), float(lip)]}


def positions(head):
    """Triangle centroids and unit normals of the precluster (written as explicit corners, so corners come in face order)."""
    document, binary, primitive = load(sorted((HEADS/head/'run/precluster').glob('attempt-*/oriented.glb'))[-1].read_bytes())
    p = accessor(document, binary, primitive['attributes']['POSITION']).astype(np.float32); del binary
    t = p[:len(p)//3*3].reshape(-1, 3, 3); n = np.cross(t[:, 1]-t[:, 0], t[:, 2]-t[:, 0]); n /= np.linalg.norm(n, axis=1, keepdims=True)+1e-12
    return np.c_[t.mean(1), n].astype(float)


def front(p, size=SIZE):
    """Front (+z glTF) view: silhouette mask, z-buffer, and Lambert shade from the frontmost triangle's normal per pixel."""
    xyz, nrm = p[:, :3], p[:, 3:]; lo, hi = xyz.min(0), xyz.max(0); span = max(hi[0]-lo[0], hi[1]-lo[1])*1.02; c = (lo+hi)/2
    x = np.clip(((xyz[:, 0]-c[0])/span*size+size/2).astype(int), 0, size-1); y = np.clip(((c[1]-xyz[:, 1])/span*size+size/2).astype(int), 0, size-1)
    pix = y*size+x; order = np.lexsort((-xyz[:, 2], pix)); first = np.r_[True, np.diff(pix[order]) != 0]; win = order[first]
    depth = np.full(size*size, -np.inf); depth[pix[win]] = xyz[win, 2]; light = np.array([-.35, .45, .82]); light /= np.linalg.norm(light)
    shade = np.zeros(size*size); shade[pix[win]] = np.clip(np.abs(nrm[win]) @ np.abs(light)*0+np.clip(nrm[win] @ light, 0, 1), 0, 1)
    m = np.isfinite(depth).reshape(size, size); m = ndimage.binary_fill_holes(ndimage.binary_closing(m, iterations=2))
    img = ((shade.reshape(size, size)*235+20)*np.isfinite(depth).reshape(size, size)).astype(np.uint8); holes = (img == 0) & m
    global LAST_SHADE; LAST_SHADE = np.where(holes, ndimage.grey_dilation(img, size=3), img).astype(np.uint8)
    return m, depth.reshape(size, size), span, c


def to_mesh(pt, scale, ox, oy, p, span, c):
    fx, fy = (pt[0]-ox)/scale, (pt[1]-oy)/scale; gx = (fx-SIZE/2)*span/SIZE+c[0]; gy = c[1]-(fy-SIZE/2)*span/SIZE
    near = (np.abs(p[:, 0]-gx) < .003*span) & (np.abs(p[:, 1]-gy) < .003*span)
    gz = float(p[near, 2].max()) if near.any() else float('nan'); return np.array([gx, gy, gz]), (fx, fy)


def shaded(depth):
    """The Lambert shade front() computed for this depth map (frontmost triangle normals)."""
    return LAST_SHADE


def refine(front_marks, depth, r=25):
    """Pupils: the front-most point of the smoothed depth within r px (the eyeball apex), kept only when it is an interior
    maximum. Lip seam: the depth minimum on its column within r px between the lips, kept only when interior."""
    ok = np.isfinite(depth); idx = ndimage.distance_transform_edt(~ok, return_distances=False, return_indices=True)
    z = ndimage.gaussian_filter(np.where(ok, depth, 0)[tuple(idx)], 2.0); out = {}
    for name, (x, y) in front_marks.items():
        x, y = int(round(x)), int(round(y))
        if name.startswith('eye'):
            win = z[y-r:y+r+1, x-r:x+r+1]; yy, xx = np.mgrid[-r:r+1, -r:r+1]; win = np.where(xx**2+yy**2 <= r*r, win, -np.inf)
            j, i = np.unravel_index(np.argmax(win), win.shape); interior = r*.15 < np.hypot(i-r, j-r) < r*.85 or np.hypot(i-r, j-r) <= r*.15
            out[name] = [x+i-r, y+j-r] if interior and np.hypot(i-r, j-r) < r*.85 else [x, y]
        else:
            col = z[y-r:y+r+1, x-3:x+4].mean(1); j = int(np.argmin(col)); out[name] = [x, y+j-r] if 2 < j < 2*r-2 else [x, y]
    return out


def sheet(rgb, marks, depth, fmarks, out, title):
    d = Image.fromarray(rgb.astype(np.uint8)); dd = ImageDraw.Draw(d)
    f = Image.fromarray(shaded(depth)).convert('RGB'); fd = ImageDraw.Draw(f)
    for (name, (x, y)), (_, (u, v)) in zip(marks.items(), fmarks.items()):
        col = (255, 60, 60) if name != 'lips' else (60, 200, 255)
        for draw, a, b in ((dd, x, y), (fd, u, v)): draw.ellipse((a-6, b-6, a+6, b+6), outline=col, width=2); draw.line((a-14, b, a+14, b), fill=col); draw.line((a, b-14, a, b+14), fill=col)
    out_img = Image.new('RGB', (2048, 1024+24), (0, 0, 0)); out_img.paste(d.resize((1024, 1024)), (0, 24)); out_img.paste(f.resize((1024, 1024)), (1024, 24))
    ImageDraw.Draw(out_img).text((6, 4), title, fill='white'); out_img.save(out)


if __name__ == '__main__':
    args = sys.argv[1:]; out = Path(args[0])
    if not out.is_absolute():  # this runs in the heads folder but `landmarks` resolves against the workspace, so a relative path would leave the jaw guard off
        sys.exit(f'OUT_DIR must be absolute: {out}')
    out.mkdir(parents=True, exist_ok=True)
    override = json.loads(Path(args[args.index('--override')+1]).read_text()) if '--override' in args else {}
    heads = [a for a in args[1:] if not a.startswith('--') and not a.endswith('.json')]
    result = json.loads((out/'landmarks.json').read_text()) if (out/'landmarks.json').exists() else {}
    for head in heads:
        rgb, mask, path = design(head); marks = override.get(head) or detect(rgb, mask)
        if marks is None:  # on disk at once: the old marks must not stand in for a failed refresh
            result[head] = {'error': 'no pupil pair detected'}; print(head, 'no pupil pair'); (out/'landmarks.json').write_text(json.dumps(result, indent=1)); continue
        p = positions(head); fm, depth, span, c = front(p); scale, ox, oy = register(mask, fm)
        if 'front' in marks:  # reviewed on the mesh view: coarse marks refined on the surface, then expressed as design pixels
            refined = marks['front'] if '--no-refine' in args else refine(marks['front'], depth); marks = {k: [v[0]*scale+ox, v[1]*scale+oy] for k, v in refined.items()}
        mesh_pts, fmarks = {}, {}
        for name, pt in marks.items(): mesh_pts[name], fmarks[name] = to_mesh(pt, scale, ox, oy, p, span, c)
        local = {k: head_local(v[None])[0] for k, v in mesh_pts.items()}; P = head_local(p[:, :3])
        ez, lz = (local['eyeLeft'][2]+local['eyeRight'][2])/2, local['lips'][2]; band = (np.abs(P[:, 0]) < .02*span) & (P[:, 2] < ez) & (P[:, 2] > lz)
        local['noseTip'] = P[band][np.argmax(P[band][:, 1])]
        result[head] = {'design': path, 'designPixels': marks, 'registration': [round(float(scale), 4), round(float(ox), 1), round(float(oy), 1)],
                        'source': {k: [round(float(x), 5) for x in v] for k, v in local.items()}, 'overridden': head in override}
        sheet(rgb, marks, depth, fmarks, out/f'lm-{head}.png', f'{head}: design (left) and mesh front view (right); red pupils, blue lip seam' + (' [override]' if head in override else ''))
        print(head, 'ok', {k: [round(v[0]), round(v[1])] for k, v in marks.items()}, flush=True)
        (out/'landmarks.json').write_text(json.dumps(result, indent=1))
