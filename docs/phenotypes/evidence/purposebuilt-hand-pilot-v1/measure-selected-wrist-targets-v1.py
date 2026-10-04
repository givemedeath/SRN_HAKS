"""Read-only selected forearm crown targets in the exact opposite hand frames."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
P = Path(__file__).resolve().parent; R = P.parents[2]
sys.path.insert(0, str(R / 'tools/phenotypes'))
from place_purposebuilt_pelvis import read_glb, raw_corners, require
from retarget import nodes, transforms
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
root = R / 'output/phenotypes/purposebuilt-stock-inputs-v1/stock/ascii/pmh0.mdl'
require(sha(root) == '23fc893a8d18df461052ef978f33b7805da9188546833c0620b3a6014117d45a', 'Stock root changed')
W = transforms(nodes(root.read_text()))
F = R / 'output/phenotypes/purposebuilt-forearm-pilot-v1'
selected = dict(l=(F / 'left-proximal-taper-moderate-v1/tapered-local.glb', '5ca7da7072848fb7bf84d5926d47ada919ce16eb8be7f446768840b96f7b3e32'),
                r=(F / 'right-proximal-taper-moderate-mirror-v1/mirrored-local.glb', 'a1a1d3df83c85b4bf7a06b4fd34f1360ea373869326ee5539fb19942231a9500'))
inputs = {str(root): sha(root), str(Path(__file__)): sha(__file__)}
records = []
for side, (path, digest) in selected.items():
    require(sha(path) == digest, 'Selected forearm differs from measured authority')
    inputs[str(path)] = digest
    d, b = read_glb(path); p, _, _, _ = raw_corners(d, b)
    frame = np.linalg.inv(W[side + 'hand_g']) @ W[side + 'forearm_g']
    p = (np.c_[p.reshape(-1, 3), np.ones(len(p) * 3)] @ frame.T)[:, :3].reshape(-1, 3, 3)
    sections = []
    for z in [-.025, -.015, -.005, 0., .005, .015, .025]:
        rows = []
        for i, j in [(0,1), (1,2), (2,0)]:
            v, q = p[:,i], p[:,j]; dz = q[:,2] - v[:,2]
            take = (np.abs(dz) > 1e-14) & (np.minimum(v[:,2], q[:,2]) <= z) & (np.maximum(v[:,2], q[:,2]) >= z)
            t = (z - v[take,2]) / dz[take]
            rows.extend(v[take,:2] + (q[take,:2] - v[take,:2]) * t[:,None])
        points = np.array(rows)
        sections.append(dict(handLocalZ=z, actualIntersectionCount=len(points),
            boundsXY=([points.min(0).tolist(), points.max(0).tolist()] if len(points) else None),
            centerXY=((points.min(0) + points.max(0)) / 2).tolist() if len(points) else None,
            diametersXYMm=(np.ptp(points, axis=0) * 1000).tolist() if len(points) else None))
    equipment = np.linalg.inv(W[side + 'hand_g']) @ W[side + 'hand']
    records.append(dict(side=side, forearm=str(path), forearmSha256=digest,
        actualForearmToHandBind=frame.tolist(), actualEquipmentInHandBind=equipment.tolist(),
        handWristToGripTranslationMm=(equipment[:3,3] * 1000).tolist(),
        forearmSectionsInHandFrame=sections))
out = P / 'selected-wrist-targets-v1'; require(not out.exists(), 'Fresh output required'); out.mkdir()
for path, digest in inputs.items(): require(sha(path) == digest, 'Frozen source changed')
report = dict(schemaVersion=1, readOnly=True, inputHashes=inputs, records=records,
    scope='Actual selected forearm geometry and stock held roots in each hand attachment frame. No hand source is fitted here. Uniform two-anchor similarity should align measured wrist and actual reconstructed grip center while preserving shaft axis; proper rotation around held axis may be necessary. No per-axis hand scaling or stock controller/height/equipment changes.',
    stockRigUnchanged=True, sourceOrMapsChanged=False, clientTested=False)
path = out / 'measurement.json'; path.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(path=str(path), sha256=sha(path), targets=[dict(side=row['side'], wrist=next(x for x in row['forearmSectionsInHandFrame'] if x['handLocalZ']==0), grip=row['handWristToGripTranslationMm']) for row in records])))
