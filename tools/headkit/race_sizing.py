"""Per-race head size at export (docs/heads/race-head-standard-v1.json, user-approved 2026-11-27).

A profile- or nose-fitted head comes out at the size of the race library before its 1.7.0 review (Elf faces 0.87-0.90 of
Human, Troll males small against the shoulders, Human males at the c8 x1.06). The standard records the reviewed factor per
race and sex, the pivot (head_g, or the head's own chin for Troll males so the jaw keeps its height) and the interpupillary
band of the published library. Export scales once, after the Troll build allowance, then measures the exported face."""
import re
from pathlib import Path
import numpy as np
from .common import pin, read, require

POLICY = 'race-head-standard-v1'
KIND = 'SRN-race-head-standard'
FACTOR_RANGE = (.7, 1.4)
# Barycentres sampled per triangle, so small irises still give enough points.
BARY = np.array([b/np.sum(b) for b in ((1,1,1),(4,1,1),(1,4,1),(1,1,4),(2,2,1),(2,1,2),(1,2,2))],float)


def config(value):
    """Manifest raceSizing: the policy name, or {policy, factor+reason?, outsideBand?} with reviewed overrides."""
    if isinstance(value, str):
        value = {'policy': value}
    require(isinstance(value, dict) and value.get('policy') == POLICY, 'raceSizing names '+POLICY)
    require(set(value) <= {'policy', 'factor', 'reason', 'outsideBand'}, 'Unknown raceSizing key')
    if 'factor' in value:
        f = value['factor']
        require(type(f) in (int, float) and FACTOR_RANGE[0] <= f <= FACTOR_RANGE[1], 'raceSizing.factor outside .7..1.4')
        require(isinstance(value.get('reason'), str) and value['reason'].strip(), 'A reviewed raceSizing.factor needs its reason')
    else:
        require('reason' not in value, 'raceSizing.reason explains a reviewed factor')
    require('outsideBand' not in value or (isinstance(value['outsideBand'], str) and value['outsideBand'].strip()),
            'raceSizing.outsideBand is the reviewed reason, as text')
    return value


def standard(path, model):
    rule = read(path)
    require(rule.get('kind') == KIND and rule.get('id') == POLICY, 'Not the race head standard')
    match = re.fullmatch(r'(p[fm][hedog]0)_head[0-9]{3}', model)
    require(match is not None and match[1] in rule['prefixes'], 'No race head standard row for '+model)
    return rule, rule['prefixes'][match[1]]


def samples(points, uv, layers):
    """Points and their PLT channel over every triangle (NWN UVs: v up, image rows top-down)."""
    h, w = layers.shape
    p = np.einsum('bk,nkd->nbd', BARY, np.asarray(points, float)).reshape(-1, 3)
    c = np.einsum('bk,nkd->nbd', BARY, np.asarray(uv, float)).reshape(-1, 2)
    col = np.clip(c[:, 0]*w, 0, w-1).astype(int); row = np.clip((1-c[:, 1])*h, 0, h-1).astype(int)
    return p, layers[row, col]


def chin(points, samples=200000):
    """Lowest front-midline point (head_g frame, z), whatever its channel: the jaw or beard the chest meets. Area-weighted
    surface samples within 6 mm of the midline; the front is their forward 30% (the 1.7.0 review's measure)."""
    tri = np.asarray(points, float)
    area = np.linalg.norm(np.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0]), axis=1)
    rng = np.random.default_rng(0); pick = rng.choice(len(tri), samples, p=area/area.sum()); u, v = rng.random((2, samples))
    flip = u+v > 1; u[flip], v[flip] = 1-u[flip], 1-v[flip]; t = tri[pick]
    p = np.concatenate([t[:, 0]+u[:, None]*(t[:, 1]-t[:, 0])+v[:, None]*(t[:, 2]-t[:, 0]), tri.reshape(-1, 3)])
    mid = p[np.abs(p[:, 0]) < .006]
    require(len(mid) > 10, 'No midline to find the chin on')
    front = mid[mid[:, 1] >= np.percentile(mid[:, 1], 70)]
    return float(front[:, 2].min())


def face(points, uv, layers):
    """Iris centres (tattoo1) and chin under the face (lowest front-midline skin). None when the irises are not found."""
    p, channel = samples(points, uv, layers)
    iris, skin = p[channel == 8], p[channel == 0]
    midline = skin[np.abs(skin[:, 0]) < .01]
    if not len(iris) or not len(midline):
        return None
    nose = midline[:, 1].max()
    iris = iris[(iris[:, 1] > nose-.06) & (np.abs(iris[:, 0]) > .012) & (np.abs(iris[:, 0]) < .12)]
    for _ in range(2):
        if len(iris):
            centre = np.median(iris[:, 1:], 0); iris = iris[np.linalg.norm(iris[:, 1:]-centre, axis=1) < .04]
    if (iris[:, 0] > 0).sum() < 3 or (iris[:, 0] < 0).sum() < 3:
        return None
    left, right = np.median(iris[iris[:, 0] > 0], 0), np.median(iris[iris[:, 0] < 0], 0); eye = (left+right)/2
    front = skin[(np.abs(skin[:, 0]) < .012) & (skin[:, 1] > eye[1]-.05)]
    result = {'interpupillary': float(left[0]-right[0]), 'eyeHeight': float(eye[2])}
    if len(front):
        result['eyeToChin'] = float(eye[2]-front[:, 2].min())
    return result


def factor(row, override, align, reference, prefix):
    if 'factor' in override:
        return float(override['factor']), 'reviewed override: '+override['reason']
    if align == 'landmarks':
        return 1.0, 'landmark fit keeps its reviewed scale'
    frame = row['fitFrame']
    if frame is None:  # Trolls: the build allowance has already accepted (or refused) the reference frame
        return float(row['exportScale']), 'Troll frame accepted by the build allowance'
    stem = Path(reference).stem
    require(stem == frame or stem.endswith('-'+frame), f'Fit reference {stem} is not the {prefix} frame {frame}: '
            'verify its scale against the race library and set raceSizing.factor with a reason')
    return float(row['exportScale']), 'compact reference frame '+frame


def apply(policy_path, override, model, align, reference, points, matrix, uv, layers):
    """(points, matrix, record): the export scaled about the standard's pivot and its face measured against the band."""
    override = config(override); rule, row = standard(policy_path, model)
    prefix = model[:4]; scale, basis = factor(row, override, align, reference, prefix)
    points = np.asarray(points, float); matrix = np.asarray(matrix, float).copy()
    pivot = np.array([0., 0., chin(points) if row['pivot'] == 'chin' and scale != 1 else 0.])
    points = pivot + (points-pivot)*scale
    move = np.eye(4); move[:3, :3] *= scale; move[:3, 3] = (1-scale)*pivot; matrix = move @ matrix
    measured = face(points, uv, layers); band = row.get('interpupillary'); check = rule['faceCheck']
    record = {'policy': pin(policy_path), 'scale': scale, 'basis': basis, 'pivot': pivot.tolist(),
              'pivotRule': row['pivot'], 'face': measured, 'band': band}
    if band is None:
        record['faceCheck'] = 'no band for this race: judge the face size by eye against the library'
    elif measured is None:
        record['faceCheck'] = 'irises not found on tattoo1: judge the face size by eye against the library'
    else:
        deviation = measured['interpupillary']/band['medianMeters']-1; suggested = scale*band['medianMeters']/measured['interpupillary']
        record.update(deviation=round(deviation, 4), suggestedScale=round(suggested, 4))
        if abs(deviation) > check['refuseFraction']:
            require('outsideBand' in override, f'{model}: eye spacing {measured["interpupillary"]*100:.2f} cm is {deviation:+.0%} from the '
                    f'{prefix} library median {band["medianMeters"]*100:.2f} cm; review the size (a scale of {suggested:.3f} reaches the '
                    'median) and set raceSizing.factor, or raceSizing.outsideBand with the reason')
            record['faceCheck'] = 'outside the refusal band, accepted on review: '+override['outsideBand']
        elif abs(deviation) > check['reviewFraction']:
            record['faceCheck'] = 'review: compare the face size with the race library side by side'
        else:
            record['faceCheck'] = 'within the library band'
    return points, matrix, record
