"""fitcheck.py HEAD_DIR OUT.png OUT_MATRIX.json: read-only nose-tip placement (unwindowed toolkit nose_tip, profile scale)
drawn like the fit overlay, both placements side by side (profile left pair, nose right pair)."""
import glob, sys, json, numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from headkit.fit import *
from headkit.gltf import mesh
from headbatch.head_files import read
H, out, mout = sys.argv[1:4]
value = mesh(sorted(glob.glob(H+'/run/precluster/attempt-*/oriented.glb'))[-1]); local = head_local(surface_samples(value['positions'][value['faces']], 1000000))
target = ascii_surface(H+'/'+read(H+'/manifest.json')['inputs']['fitReference']['path'])  # a head can hold older references beside the bound one
r = match(local, target, exclude_lower=.25); s = r['scale']; prof = np.array(r['translation'])
tn = nose_tip(target, .001, .0005); sn = nose_tip(local, .001/s, .0005/s); t = tn-s*sn
print('scale', s, 'profile', prof.round(5), 'target nose', tn.round(5), 'source nose', sn.round(5), 'nose translation', t.round(5), 'shift', round(float(np.linalg.norm(t-prof)), 4))
M = np.eye(4); M[:3, :3] = np.diag([-s, -s, s]); M[:3, 3] = t; json.dump(M.tolist(), open(mout, 'w'))
size = 700; pad = max(.32, float(np.abs(target).max())*1.15); canvas = np.zeros((size, size*4, 3), np.uint8)
for j, tr in enumerate((prof, t)):
    fitted = local*s+tr
    for axes, offset in (((0, 2), 0), ((1, 2), size)):
        masks = []
        for points in (fitted, target):
            x = ((points[:, axes[0]]/pad*.5+.5)*size).astype(int); y = ((.5-points[:, axes[1]]/pad*.5)*size).astype(int)
            ok = (x >= 0) & (x < size) & (y >= 0) & (y < size); mask = np.zeros((size, size), bool); mask[y[ok], x[ok]] = True
            masks.append(ndimage.binary_closing(mask, iterations=2))
        o = j*2*size+offset; view = canvas[:, o:o+size]; view[masks[0]] = (255, 140, 60)
        view[masks[1] & ~ndimage.binary_erosion(masks[1], iterations=2)] = (70, 160, 255)
im = Image.fromarray(canvas); d = ImageDraw.Draw(im)
for z, c in ((tn[2], (0, 255, 0)), (-0.09, (200, 200, 200))):
    y = int((.5-z/pad*.5)*size); d.line((0, y, size*4, y), fill=c)
d.text((10, 10), f'PROFILE placement tz {prof[2]:+.4f}', fill='white'); d.text((2*size+10, 10), f'NOSE-TIP placement t ({t[1]:+.4f}, {t[2]:+.4f}), shift {np.linalg.norm(t-prof)*100:.1f} cm', fill='white')
d.text((10, 26), 'green: reference nose-tip height; grey: z -0.09; orange = this head, blue = fit reference', fill='white'); im.save(out)
