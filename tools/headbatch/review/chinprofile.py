"""chinprofile.py HEAD_DIR [STEP] [--source]: front profile of the latest repair attempt's uncut master in the neck-cut frame: per height band
the front-most y near the midline (|x| < 3 cm) and the body neck's front radius there. The chin is where the front edge steps
back toward the neck; set mesh.neck.cut.searchBottom just under it when the measured jaw line lands on the generated neck."""
import glob, json, sys
import numpy as np
import headkit.neck as N
from headkit.gltf import mesh
args = [a for a in sys.argv[1:] if not a.startswith('--')]; head = args[0]; step = float(args[1]) if len(args) > 1 else .01
# --source: the repair input (same physical frame), so the chin and jaw line are known before the first repair
precluster = '--source' in sys.argv
man = json.load(open(head+'/manifest.json')); st = json.load(open(head+'/run/state.json'))['stages']
fit = man['fit']['matrix'] if 'matrix' in man['fit'] else json.load(open(st['fit']['path']))['result']['matrix']  # explicit refit matrix first
neck = N.neck_policy(man['mesh']['neck'], {'matrix': fit, 'reviewed': True}); bv, bf = N.body_neck(head+'/'+man['inputs']['bodyNeck']['path'])
m = mesh(sorted(glob.glob(head+('/run/precluster/attempt-*/oriented.glb' if precluster else '/run/repair/attempt-*/master-uncut.glb')))[-1]); V, F = N.physical(m['positions'], m['faces'])
L = N.transform(neck['frame'], V); mid = np.abs(L[:, 0]) < .03; bmid = np.abs(bv[:, 0]) < .03
print('body neck z', bv[:, 2].min().round(3), bv[:, 2].max().round(3))
for z in np.arange(L[:, 2].min(), min(L[:, 2].max(), .06), step):
    band = mid & (L[:, 2] >= z) & (L[:, 2] < z+step); bband = bmid & (bv[:, 2] >= z-.01) & (bv[:, 2] < z+step+.01)
    if band.any(): print(f'z {z:+.3f} front y {L[band, 1].max():+.3f}', f'body front {bv[bband, 1].max():+.3f}' if bband.any() else '')
cut = neck['cut']; jaw = N.jaw_line(L, bv, bf, cut['reach'], cut['slope'], cut['searchBottom'])
floor = jaw['point'][2]-L[:, 2].min() < .01  # a hand-set searchBottom just under the chin is meant to hold the jaw line
print('jaw', jaw, 'ON THE NECK BOTTOM / SEARCH FLOOR: set searchBottom just under the chin' if floor else 'OK')
