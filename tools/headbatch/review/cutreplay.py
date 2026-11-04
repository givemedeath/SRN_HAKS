"""cutreplay.py HEAD_DIR [KEY=VALUE[,KEY=VALUE] ...] (cut keys, e.g. slope=-0.1,reach=0.08): replay the toolkit's neck_cut (exact code, no Alpha Wrap) on the latest repair attempt's
uncut master for the manifest cut and for each SLOPE, and print pass or the refusal. Several rings need the repair's rewrap and
count as a pass here (the wrapped repair closes them). Read-only; a few seconds per slope instead of an 8-minute repair."""
import glob, json, sys
import numpy as np
from headkit.intersections import scan
import headkit.neck as N
from headkit.gltf import mesh
head = sys.argv[1]; variants = [{}]+[{k: float(v) for k, v in (kv.split('=') for kv in a.split(','))} for a in sys.argv[2:]]
man = json.load(open(head+'/manifest.json')); st = json.load(open(head+'/run/state.json'))['stages']
fit = man['fit']['matrix'] if 'matrix' in man['fit'] else json.load(open(st['fit']['path']))['result']['matrix']; body = N.body_neck(head+'/'+man['inputs']['bodyNeck']['path'])
m = mesh(sorted(glob.glob(head+'/run/repair/attempt-*/master-uncut.glb'))[-1]); V, F = N.physical(m['positions'], m['faces'])
for variant in variants:
    policy = json.loads(json.dumps(man['mesh']['neck']))
    policy['cut'].update(variant)
    neck = N.neck_policy(policy, {'matrix': fit, 'reviewed': True}); label = 'manifest cut' if not variant else str(variant)
    try:
        v, f, record = N.neck_cut(V, F, neck, body, rewrap=None)
        try: crossings = len(scan(np.asarray(v, float), np.asarray(f))['pairs'])  # the master audit's strict scan (troll-male-b attempt 2)
        except ValueError as error: crossings = 'scan refused: '+str(error)
        print(label, 'PASS' if crossings == 0 else 'FAIL (crossings)', 'crossings', crossings, 'jaw', record.get('jawLine'), 'rings', record['loops'])
    except ValueError as error:
        print(label, 'PASS (several rings, rewrap closes them); jaw', N.jaw_line(N.transform(neck['frame'], V), *body, neck['cut']['reach'], neck['cut']['slope'], neck['cut']['searchBottom']) if 'only a wrapped repair' in str(error) else f'FAIL: {error}')
