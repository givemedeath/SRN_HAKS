"""CPU-only actual hand, selected forearm and held-item silhouette review."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

P = Path(__file__).resolve().parent
R = P.parents[2]
sys.path.insert(0, str(R / 'tools/phenotypes'))
from place_purposebuilt_pelvis import read_glb, raw_corners, require
from retarget import NODE, nodes, transforms
from audit_geometry import arrays
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()

def affine(tri, matrix):
    return (np.c_[tri.reshape(-1, 3), np.ones(len(tri) * 3)] @ matrix.T)[:, :3].reshape(-1, 3, 3)

def mdl(path):
    text = path.read_text()
    worlds = transforms(nodes(text))
    result = []
    for node in NODE.finditer(text.split('endmodelgeom')[0]):
        v = np.array(arrays(node[3], 'verts'))
        if len(v):
            f = np.array(arrays(node[3], 'faces'), int)[:, :3]
            result.extend(affine(v[f], worlds[node[2].lower()]))
    return np.array(result)

def glb(path):
    doc, blob = read_glb(path)
    p, _, _, _ = raw_corners(doc, blob)
    return p

def draw(groups, direction, center, span, output):
    d = np.array(direction, float); d /= np.linalg.norm(d)
    up = np.array([0., 0., 1.]) if abs(d[2]) < .95 else np.array([0., 1., 0.])
    right = np.cross(up, d); right /= np.linalg.norm(right); up = np.cross(d, right)
    key = d + .35 * up - .2 * right; key /= np.linalg.norm(key)
    tri = np.concatenate([g[0] for g in groups])
    colors = np.concatenate([np.tile(c, (len(t), 1)) for t, c in groups])
    q = tri - center
    screen = np.stack([q @ right, -q @ up], axis=2) / span * 900 + 450
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1)[:, None], 1e-20)
    shade = .4 + .6 * np.maximum(0, n @ key)
    image = Image.new('RGB', (900, 900), (27, 27, 27))
    painter = ImageDraw.Draw(image)
    for i in np.argsort(q.mean(1) @ d):
        xy = screen[i]
        if xy[:, 0].max() < 0 or xy[:, 0].min() > 900 or xy[:, 1].max() < 0 or xy[:, 1].min() > 900:
            continue
        painter.polygon([tuple(x) for x in xy], fill=tuple((colors[i] * shade[i]).astype(int)))
    image.save(output)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    parser.add_argument('--forearm-left', type=Path, required=True)
    parser.add_argument('--forearm-right', type=Path, required=True)
    parser.add_argument('--clip', required=True)
    parser.add_argument('--phase', type=float, required=True)
    parser.add_argument('--output', type=Path, required=True)
    a = parser.parse_args()
    out = a.output.resolve(); require(not out.exists(), 'Fresh output required')
    motion = P / 'wrist-motion-dense-v2/measurement.json'
    bank = R / 'output/phenotypes/human-male-complete-goal-v1/stock-grip-inputs-v1/ascii'
    stock = R / 'output/phenotypes/purposebuilt-stock-inputs-v1/stock/ascii'
    case = next(c for c in json.loads(motion.read_text())['cases'] if c['clip'] == a.clip and abs(c.get('fraction', -1) - a.phase) < 1e-12)
    paths = [a.left.resolve(), a.right.resolve(), a.forearm_left.resolve(), a.forearm_right.resolve(),
             motion, stock / 'pmh0_handl001.mdl', stock / 'pmh0_handr001.mdl', Path(__file__),
             *[bank / (name + '.mdl') for name in ['wswls_t_011', 'wswls_m_011', 'wswls_b_011', 'ashsw_011']]]
    inputs = {str(path): sha(path) for path in paths}
    sword = np.concatenate([mdl(bank / (name + '.mdl')) for name in ['wswls_t_011', 'wswls_m_011', 'wswls_b_011']])
    shield = mdl(bank / 'ashsw_011.mdl')
    hands = dict(l=glb(a.left), r=glb(a.right))
    forearms = dict(l=glb(a.forearm_left), r=glb(a.forearm_right))
    out.mkdir()
    records = []
    for h in case['hands']:
        s = h['side']
        # Current hand and forearm GLBs are already in their actual detached part frames.
        fore = affine(forearms[s], np.array(h['forearmToHandLocal']))
        equip = np.array(h['equipmentInHandFrame'])
        for itemname, item in [('sword', sword), ('shield', shield)]:
            posed = affine(item, equip)
            points = hands[s].reshape(-1, 3)
            center = (points.min(0) + points.max(0)) / 2
            span = max(np.ptp(points, axis=0).max() * 1.6, .25)
            for kind in ['candidate', 'stock']:
                hand = hands[s] if kind == 'candidate' else mdl(stock / f'pmh0_hand{s}001.mdl')
                groups = [(fore, [152, 135, 105]), (hand, [214, 214, 214]), (posed, [72, 171, 237])]
                views = [('palm', (1 if s == 'l' else -1, 0, 0)), ('dorsal', (-1 if s == 'l' else 1, 0, 0)), ('thumb-side', (0, 1, 0)), ('distal', (0, 0, -1))]
                for label, direction in views:
                    path = out / f'{s}-{itemname}-{kind}-{label}.png'
                    draw(groups, direction, center, span, path)
                    records.append(dict(side=s, item=itemname, kind=kind, view=label,
                        path=str(path), sha256=sha(path), cameraDirection=direction,
                        centerHandLocal=center.tolist(), orthographicSpanMetres=span))
    for path, digest in inputs.items():
        require(sha(path) == digest, 'Read-only input changed')
    report = dict(schemaVersion=1, readOnly=True, clip=a.clip, phase=a.phase,
        sourceInputsUnchanged=True, equipmentScaleIdentity=True, rigOrAnimationChanged=False,
        inputs=inputs, poseControllerReceipt=case['controllerReceipt'], records=records,
        scope='CPU geometric-face clay and actual item silhouettes, separately on both actual hand frames with selected forearm. Blue is actual stock item, gold current forearm. Front/back painter ordering is diagnostic only; authored skin/maps, native materials and engine playback not simulated. Stock comparator receives exactly the same camera and actual item pose. Sword and shield are alternative attachments, not a claim both are held simultaneously.',
        nativeOrClientAccepted=False)
    (out / 'review.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(output=str(out), images=len(records))))

if __name__ == '__main__':
    main()
