"""cutreplay.py HEAD_DIR [KEY=VALUE[,KEY=VALUE] ...] (cut keys, e.g. slope=-0.1,reach=0.08): replay the toolkit's neck_cut (exact code, no Alpha Wrap) on the latest repair attempt's
uncut master for the manifest cut and for each SLOPE, and print pass or the refusal. Several rings need the repair's rewrap and
count as a pass here (the wrapped repair closes them). Read-only; a few seconds per slope instead of an 8-minute repair."""
import glob, json, sys
import headkit.neck as N
from headkit.gltf import mesh
from headbatch.head_files import fit_matrix
head = sys.argv[1]; variants = [{}]+[{k: float(v) for k, v in (kv.split('=') for kv in a.split(','))} for a in sys.argv[2:]]
man = json.load(open(head+'/manifest.json')); fit = fit_matrix(head); body = N.body_neck(head+'/'+man['inputs']['bodyNeck']['path'])
m = mesh(sorted(glob.glob(head+'/run/repair/attempt-*/master-uncut.glb'))[-1]); V, F = N.physical(m['positions'], m['faces'])
for variant in variants:
    policy = json.loads(json.dumps(man['mesh']['neck']))
    policy['cut'].update(variant)
    neck = N.neck_policy(policy, {'matrix': fit, 'reviewed': True}); label = 'manifest cut' if not variant else str(variant)
    try:
        v, f, record = N.neck_cut(V, F, neck, body, rewrap=None)
        problem = N.cut_problem(v, f)  # the master audit's own refusal (troll-male-b attempt 2)
        print(label, 'PASS' if problem is None else f'FAIL ({problem})', 'jaw', record.get('jawLine'), 'rings', record['loops'])
    except ValueError as error:
        if 'only a wrapped repair' in str(error):
            print(label, 'PASS (several rings, rewrap closes them); jaw', N.measured_jaw(N.transform(neck['frame'], V), *body, neck['cut']))
        else:
            print(label, f'FAIL: {error}')
