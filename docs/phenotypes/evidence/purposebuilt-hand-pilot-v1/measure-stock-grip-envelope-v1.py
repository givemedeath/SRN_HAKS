"""Read-only actual stock mitten/held-shaft finite-pose reference, not a fit mandate."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np

P = Path(__file__).resolve().parent
R = P.parents[2]
sys.path.insert(0, str(R / 'tools/phenotypes'))
from audit_geometry import arrays
from retarget import NODE, nodes, transforms
from place_purposebuilt_pelvis import require

sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
stock = R / 'output/phenotypes/purposebuilt-stock-inputs-v1/stock/ascii'
archive = P / 'wrist-motion-dense-v2/measurement.json'
equipment = P / 'equipment-measurement-v1/measurement.json'
motion = json.loads(archive.read_text())
items = json.loads(equipment.read_text())
inputs = {str(archive): sha(archive), str(equipment): sha(equipment), str(Path(__file__)): sha(__file__)}
for path, digest in motion['inputs'].items():
    require(sha(path) == digest, 'Motion source changed: ' + path)
    inputs[path] = digest
for item in items['models']:
    require(sha(item['path']) == item['sha256'], 'Actual item source changed')
    inputs[item['path']] = item['sha256']
handle = next(x for x in items['models'] if x['model'] == 'wswls_b_011')['parts'][0]['shaft']
center = np.array(handle['lowerCenter'])
axis = np.array(handle['measuredAxis'])
center -= axis * float(center @ axis)

def mesh(path):
    text = path.read_text()
    world = transforms(nodes(text))
    result = []
    for node in NODE.finditer(text.split('endmodelgeom')[0]):
        verts = np.array(arrays(node[3], 'verts'))
        if not len(verts):
            continue
        faces = np.array(arrays(node[3], 'faces'), int)[:, :3]
        v = (np.c_[verts, np.ones(len(verts))] @ world[node[2].lower()].T)[:, :3]
        result.extend(v[faces])
    return np.array(result)

def line_hits(tri, origin, direction):
    # Infinite-line triangle intersections. No source welding or mutation.
    edge1 = tri[:, 1] - tri[:, 0]
    edge2 = tri[:, 2] - tri[:, 0]
    h = np.cross(direction, edge2)
    det = np.einsum('ij,ij->i', edge1, h)
    live = np.abs(det) > 1e-14
    inv = np.zeros(len(tri)); inv[live] = 1 / det[live]
    s = origin - tri[:, 0]
    u = inv * np.einsum('ij,ij->i', s, h)
    q = np.cross(s, edge1)
    v = inv * (q @ direction)
    t = inv * np.einsum('ij,ij->i', edge2, q)
    good = live & (u >= -1e-10) & (v >= -1e-10) & (u + v <= 1 + 1e-10)
    return sorted(set(round(float(x), 12) for x in t[good]))

hands = {}
for side in ['l', 'r']:
    path = stock / f'pmh0_hand{side}001.mdl'
    inputs[str(path)] = sha(path)
    hands[side] = mesh(path)
records = []
for case in motion['cases']:
    if 'hands' not in case:
        continue
    for hand in case['hands']:
        side = hand['side']
        matrix = np.array(hand['equipmentInHandFrame'])
        origin = (matrix @ np.r_[center, 1])[:3]
        direction = matrix[:3, :3] @ axis
        direction /= np.linalg.norm(direction)
        hits = line_hits(hands[side], origin, direction)
        valid = len(hits) % 2 == 0
        intervals = list(zip(hits[::2], hits[1::2])) if valid else []
        shaft_lo, shaft_hi = sorted(float(np.array(handle[key]) @ axis) for key in ['lowerCenter', 'upperCenter'])
        covered = sum(max(0, min(b, shaft_hi) - max(a, shaft_lo)) for a, b in intervals)
        records.append(dict(clip=case['clip'], phase=case['fraction'], side=side,
            actualHeldMatrix=matrix.tolist(), shaftCenterAtItemZeroHandLocal=origin.tolist(),
            shaftDirectionHandLocal=direction.tolist(),
            exactStockHandLineHitsMm=[h * 1000 for h in hits],
            parityUnambiguous=valid, intervalsMm=[[a * 1000, b * 1000] for a, b in intervals],
            actualShaftCenterlineWithinSolidStockMittenMm=covered * 1000,
            heldRotationFromBindDegrees=hand['equipmentRotationDifferenceFromBindDegrees']))
out = P / 'stock-grip-envelope-v1'
require(not out.exists(), 'Fresh output required')
out.mkdir()
summary = dict(schemaVersion=1, readOnly=True, sourceInputsUnchanged=True,
    equipmentScaleIdentity=True, stockRigUnchanged=True, clientTested=False,
    inputs=inputs, stockHandTopology='Closed 16-triangle mitten proxy; naturally lacks anatomical grip opening.',
    scope='Finite exact triangle intersections of actual normal-longsword shaft centerline with stock hand. Internal stock shaft penetration is observed baseline behavior, not a collision-free acceptance requirement for the detailed hand. Actual new hand/thumb/finger contact and right-side mismatch still need independent visual proof.',
    sampledCases=len(records), records=records,
    stockCenterlinePenetrationRangeMm=[min(x['actualShaftCenterlineWithinSolidStockMittenMm'] for x in records), max(x['actualShaftCenterlineWithinSolidStockMittenMm'] for x in records)],
    ambiguousRayCases=sum(not x['parityUnambiguous'] for x in records))
for path, digest in inputs.items():
    require(sha(path) == digest, 'Frozen input changed')
result = out / 'measurement.json'
result.write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(dict(path=str(result), sha256=sha(result), samples=len(records),
    centerlinePenetrationRangeMm=summary['stockCenterlinePenetrationRangeMm'], ambiguous=summary['ambiguousRayCases'])))
