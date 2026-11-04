"""jaw.py HEAD_DIR [UNCUT]: dry-run the measured jaw line / cut band of the current toolkit neck cut (read-only)."""
import glob, json, sys
import numpy as np
import headkit.neck as N
from _frame import head_neck, local_positions
head = sys.argv[1]
uncut = sys.argv[2] if len(sys.argv) > 2 else sorted(glob.glob(head+'/run/repair/attempt-*/master-uncut.glb'))[-1]
man, neck, bv, bf = head_neck(head)
L = local_positions(neck, uncut)
cut = dict(neck['cut']); print('cut', {k: v for k, v in cut.items() if k != 'notes'})
print('head local bounds', L.min(0).round(4), L.max(0).round(4), 'body z', bv[:, 2].min().round(4), bv[:, 2].max().round(4))
jaw = N.measured_jaw(L, bv, bf, cut); print('jaw', jaw)
h = jaw['height']-cut['clearance']; plane = h+cut['slope']*L[:, 1]; above = L[:, 2]-plane; mv = above < cut['band']
ha = np.maximum(L[mv, 2], plane[mv]); print('plane h', round(h, 4), 'band height_at', ha.min().round(4), ha.max().round(4))
i = np.argmax(ha); print('highest band vertex', L[mv][i].round(4))
# which features are low: list front features by intercept
low = max(float(L[:, 2].min()), float(bv[:, 2].min())+1e-4); cand = L[(L[:, 2] < 0) & (L[:, 2] > low)]
lk = N.body_profile(bv, bf, low, -1e-4); c, s, o = lk(cand, cand[:, 2]); fr = (o[:, 1] > 0) & (np.linalg.norm(o, axis=1)-s > cut['reach'])
f = cand[fr]; ic = f[:, 2]-cut['slope']*f[:, 1]; order = np.argsort(ic)
print('lowest features (x,y,z,intercept):'); [print(' ', f[k].round(4), round(ic[k], 4)) for k in order[:8]]
zmin = float(sys.argv[3]) if len(sys.argv) > 3 else -0.13
g = fr & (cand[:, 2] > zmin); f = cand[g]; ic = f[:, 2]-cut['slope']*f[:, 1]; order = np.argsort(ic)
print(f'features above z {zmin} (x,y,z,intercept, outside):'); out = (np.linalg.norm(o, axis=1)-s)[g]
[print(' ', f[k].round(4), round(ic[k], 4), round(out[k], 4)) for k in order[:12]]
print('explicit height', round(ic[order[0]]-cut['clearance'], 4))
for zm in (-0.125, -0.12, -0.11):
    g = fr & (cand[:, 2] > zm); f = cand[g]; ic = f[:, 2]-cut['slope']*f[:, 1]; k = np.argmin(ic); print('zmin', zm, 'lowest', f[k].round(4), round(ic[k], 4))
g = fr & (cand[:, 1] > 0.04); f = cand[g]; ic = f[:, 2]-cut['slope']*f[:, 1]; order = np.argsort(ic)
print('forward (y>0.04) features:'); [print(' ', f[k].round(4), round(ic[k], 4)) for k in order[:6]]
# flank profile: max |x| outside per z band
for z0 in np.arange(-0.20, -0.06, 0.01):
    b = fr & (cand[:, 2] > z0) & (cand[:, 2] < z0+0.01)
    print(f'z {z0:+.2f}: front features {b.sum()}', (cand[b][:, :2].round(3)[np.argsort(-cand[b][:, 1])][:2].tolist() if b.any() else ''))
