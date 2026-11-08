"""shells.py HEAD_DIR [--interior]: read-only reproduction of the head's repair up to the shell selection, with the pipeline
toolkit's ShellReview table: every extra shell's triangles, area fraction, centroid and box (repair frame). Writes nothing
into the run. Record the selection with `run_headbatch.py components`, which reads review-evidence/shells.json: the printed
count includes the kept shell, so it is not expectedDeleted (RUNBOOK 93)."""
import json, sys, tempfile
from pathlib import Path
head = Path(next(a for a in sys.argv[1:] if not a.startswith('--')))
from headkit import neck, mesh as meshmod
from headkit.common import read
from headbatch.head_files import fit_matrix
from _frame import band
man = json.load(open(head/'manifest.json')); st = read(head/'run/state.json')['stages']; b = read(head/'bindings.json')
source = read(st['precluster']['path'])['result']['output']
fit = dict(man['fit'], matrix=fit_matrix(head), reviewed=True); fit.pop('matrixFrom', None)
policy = dict(man['mesh']); policy.pop('components', None)  # force the refusal so the full table is reported
inspection = dict(policy.get('shellInspection', {}), sourceSha256=source['sha256'])
body = head/man['inputs']['bodyNeck']['path'] if (policy.get('neck') or {}).get('cut') else None
captured = {}
original = meshmod.select_shells
class Selected(Exception): pass
def capture(vertices, faces, selection, inside=None):
    # Stop as soon as the selection passes: the diagnostic needs nothing after it, and the reduction's spawned worker would
    # re-run this unguarded script (elf-male-b crashed that way after 6 min, RUNBOOK 56).
    captured.update(vertices=vertices, faces=faces); result = original(vertices, faces, selection, inside); raise Selected(result)
neck.select_shells = meshmod.select_shells = capture
with tempfile.TemporaryDirectory() as tmp:
    try:
        neck.repair(source['path'], Path(tmp)/'final.glb', b, policy, inspection, fit=fit, body=body)
    except Selected:
        (head/'review-evidence').mkdir(exist_ok=True)
        table = {'count': 1, 'deletedAreaFraction': 0.0, 'extra': []}
        (head/'review-evidence'/'shells.json').write_text(json.dumps(table, indent=1))
        print('single shell: keep it, no extras to delete')
    except meshmod.ShellReview as error:
        import numpy as np
        table = error.attempts['shells']; print('shells', table['count'], 'including the kept one; extra area %.4f%%' % (100*table['deletedAreaFraction']))
        V, F = np.asarray(captured['vertices'], float), np.asarray(captured['faces']); label = meshmod.shells(V, F)
        corners = V[F]; area = np.linalg.norm(np.cross(corners[:, 1]-corners[:, 0], corners[:, 2]-corners[:, 0]), axis=1)/2
        keep = int(np.argmax(np.bincount(label, area))); main = F[label == keep]
        from headkit.common import library; igl = library(b, "igl")
        for k, row in zip([k for k in np.argsort(-np.bincount(label, area)) if k != keep], table['extra']):
            if 'insideFraction' not in row:
                points = V[np.unique(F[label == k])]
                winding = igl.fast_winding_number(V, main.astype(np.int64, copy=False), points)
                row['insideFraction'] = float(np.mean(np.abs(winding) > .5))
            print(' ', row['triangles'], 'tri', '%.4f%%' % (100*row['areaFraction']), 'inside %.0f%%' % (100*row['insideFraction']), 'centroid', row['centroid'])
        (head/'review-evidence').mkdir(exist_ok=True); (head/'review-evidence'/'shells.json').write_text(json.dumps(table, indent=1))
        # shells.png: face centroids projected on the three axis planes of the repair frame, kept shell grey (nearer = lighter),
        # extra shells red and enlarged, so a visible floater (stud, ring) is told from an interior bubble at a glance.
        from PIL import Image, ImageDraw
        C = V[F].mean(1); lo, hi = C.min(0), C.max(0); span = (hi-lo).max()*1.05; size = 520; tiles = []
        for a, b, d in ((0, 1, 2), (0, 2, 1), (2, 1, 0)):
            im = Image.new('RGB', (size, size), (30, 30, 30)); px = im.load(); o = np.argsort(C[:, d])
            u = ((C[o, a]-(lo[a]+hi[a])/2)/span+.5)*size; w = (.5-(C[o, b]-(lo[b]+hi[b])/2)/span)*size
            shade = (60+150*(C[o, d]-lo[d])/max(hi[d]-lo[d], 1e-9)).astype(int)
            for x, y, s in zip(u.astype(int), w.astype(int), shade):
                if 0 <= x < size and 0 <= y < size: px[x, y] = (s, s, s)
            draw = ImageDraw.Draw(im)
            for k in [k for k in range(label.max()+1) if k != keep]:
                for c in C[label == k]:
                    x = ((c[a]-(lo[a]+hi[a])/2)/span+.5)*size; y = (.5-(c[b]-(lo[b]+hi[b])/2)/span)*size; draw.ellipse([x-3, y-3, x+3, y+3], fill=(255, 40, 40))
            draw.text((4, 4), f'axes {"xyz"[a]} right, {"xyz"[b]} up, depth {"xyz"[d]}', fill=(255, 255, 0)); tiles.append(im)
        sheet = Image.new('RGB', (size*3, size)); [sheet.paste(t, (i*size, 0)) for i, t in enumerate(tiles)]; sheet.save(head/'review-evidence'/'shells.png')
        if '--interior' in sys.argv:  # would the toolkit's interiorOnly selection accept this master?
            win = lambda vv, ff, pts: igl.fast_winding_number(np.asarray(vv, float), np.asarray(ff, np.int64), np.asarray(pts, float))
            try:
                _, kept, record = original(V, F, {'keep': 'largest', 'reviewed': True, 'interiorOnly': True, 'maximumDeletedAreaFraction': .05}, win)
                print('interiorOnly accepts:', len(record['deleted']), 'shells deleted,', '%.4f%%' % (100*record['deletedAreaFraction']), len(kept), 'faces kept')
            except meshmod.ShellReview as refusal: print('interiorOnly refuses:', refusal)

# Neck-cut band vs the body neck (human-female-b repair attempt-01 failed "Body neck must span the cut band" after 8 min):
# the selection sees the wrapped, uncut master, so the measured jaw line and band can be checked here before any repair launch.
if body is not None and captured:
    import numpy as np
    V = np.asarray(captured['vertices'], float); cut_policy = neck.neck_policy(man['mesh']['neck'], {'matrix': fit['matrix'], 'reviewed': True})
    bv, bf = neck.body_neck(str(body)); L = neck.transform(cut_policy['frame'], V); cut = cut_policy['cut']
    jaw = neck.measured_jaw(L, bv, bf, cut); plane, moving = band(L, cut, jaw, bv, bf)
    top = np.maximum(L[moving, 2], plane[moving]).max(); high = bv[:, 2].max()
    print('neck cut: slope', cut['slope'], 'band top %.4f' % top, 'body neck top %.4f' % high, 'OK' if top < high else 'FAIL: lower the slope magnitude (the band at the nape is above the body neck)')
