"""slopescan.py HEAD_DIR SLOPE...: shells.py's neck-cut band check (RUNBOOK 76/human-female-b) for several slopes on the precluster
mesh (no wrap, seconds instead of minutes). The wrapped master sits ~1-2 mm outside it, so compare against the slope the shells
diagnostic measured on the wrap. Prints jaw point, band top and body neck top per slope."""
import json, sys, glob
import numpy as np
import headkit.neck as N
from headkit.gltf import mesh
head = sys.argv[1]; man = json.load(open(head+'/manifest.json')); st = json.load(open(head+'/run/state.json'))['stages']
fit = man['fit']['matrix'] if 'matrix' in man['fit'] else json.load(open(st['fit']['path']))['result']['matrix']  # explicit refit matrix first
m = mesh(sorted(glob.glob(head+'/run/precluster/attempt-*/oriented.glb'))[-1]); V, F = N.physical(m['positions'], m['faces'])
args = sys.argv[2:]; reach = float(args[args.index('--reach')+1]) if '--reach' in args else None; args = [a for i, a in enumerate(args) if a != '--reach' and (i == 0 or args[i-1] != '--reach')]
for s in map(float, args):
    neck = dict(man['mesh']['neck']); neck['cut'] = dict(neck['cut'], slope=s, **({'reach': reach} if reach else {}))
    pol = N.neck_policy(neck, {'matrix': fit, 'reviewed': True}); bv, bf = N.body_neck(head+'/'+man['inputs']['bodyNeck']['path'])
    L = N.transform(pol['frame'], V); cut = pol['cut']; jaw = N.jaw_line(L, bv, bf, cut['reach'], cut['slope'], cut['searchBottom'], cut.get('cone'))  # skirt heads search the front cone only, as repair does
    h = jaw['height']-cut['clearance']; plane = h+s*L[:, 1]; band = L[(L[:, 2]-plane) < cut['band']]
    top = np.maximum(band[:, 2], h+s*band[:, 1]).max()
    print(f'slope {s:+.2f} jaw z {jaw["point"][2]:+.4f} y {jaw["point"][1]:+.4f} band top {top:.4f} body neck top {bv[:, 2].max():.4f}', 'OK' if top < bv[:, 2].max() else 'FAIL')
