"""Measure a weapon's fit from its closed working shell and write the fresh fitting manifest.

This is the toolkit form of the wave-1 `auto_fit.py` driver. It measures the landmarks along the long axis, the
similarity to the native hand, the two part joins and the thin-section probes; it never approves anything:

- bladed families (swords, knives): pommel | usable grip | guard | blade. One-hand designs are sized from the usable
  grip, extended into the pommel so the whole weapon matches the stock carrier's length; two-hand designs are sized
  uniformly from the approved midpoint grip depth unless an overall length is chosen.
- hafted families (club, axes, polearms): butt | grip | haft | head. The design is scaled uniformly to the stock
  carrier's length (or a chosen one) and the hand sits at the same fraction of the length as on the stock carrier.
  One-hand hafts keep a round handle (usable-length-round); two-hand hafts use the two-hand uniform route.

`measure()` has no side effects (a measure-only pass, and the numbers a fit preview shows); `write()` copies the
inputs into the handoff and writes the manifest. A grip that departs from the approved section needs a review bound
to the fit worker's own measurement digest: run the worker's measure-only pass (`run_itemkit.py measure-fit`) on the
candidate manifest and pass its digest back in `overrides['departureDigest']`.
"""
import hashlib
import json
import shutil
from pathlib import Path
import numpy as np
from tools.headkit.common import ROOT, require
from .autofit import _runs, clear_cut, grip_start_for_length
from .geometry import transform
from .routes import HAFTED_FAMILIES, ROUTES
from . import straightness as st

STANDARD = ROOT/'docs/items/weapon-grip-standard-v1.json'
LANDMARKS = ('pommelEnd', 'gripStart', 'gripEnd', 'bladeStart')
# Processing settings the Vibro Sword needed before it passed (fit-v5, 2026-11-05): plain reduction moved the part joins.
PROCESSING = {'cageExtrusion': .006, 'maxRayDistance': .012, 'uvPackingPaddings': [8, 12, 16], 'constrainedReduction': True,
              'uvCoordinateScale': 1000, 'missCorrection': {'method': 'nearest-finished-donor', 'maximumDistance': .003,
                                                            'minimumNormalAlignment': .5}}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def gltf_to_blender(positions):
    """The fit frame: the glTF importer maps (x, y, z) to (x, -z, y)."""
    g = np.asarray(positions, float); return np.c_[g[:, 0], -g[:, 2], g[:, 1]]


def stock_length(native):
    """Overall length of the stock carrier from its measured part bounds (or the contract's measured span)."""
    if 'stockSpan' in native: return float(native['stockSpan'][1] - native['stockSpan'][0])
    if 'dimensions' not in native: return None
    dims = native['dimensions']; return float(dims['t']['meshes'][0]['bounds'][1][1] - dims['b']['meshes'][0]['bounds'][0][1])


def _frame(b):
    mean, U = st.principal_frame(b); q = (b - mean) @ U
    return mean, U, q


def _oriented(q, U, flip):
    if flip: q = q * [-1, -1, 1]; U = U * [-1, -1, 1]
    if U[2, 1] < 0: q = q * [1, -1, -1]; U = U * [1, -1, -1]         # the width axis follows Blender +Z
    require(abs(np.linalg.det(U) - 1) < 1e-9, 'Right-handed fit frame required')
    return q, U


def bladed_landmarks(q, U, overrides):
    N = st.SLICES; centres, mid, extent, wide, _ = st._sections(q)
    known = ~np.isnan(extent[:, 0]); depth = np.where(known, extent.min(1), 0)
    guard = max(_runs(wide), key=len) if wide.any() else None
    if guard is not None and 5 < guard[0] and guard[-1] < N - 6:
        flip = guard[0] > N - 1 - guard[-1]; method = 'cross-guard'          # more length below the guard: blade at the low end
    elif 'bladeAtLowEnd' in overrides:
        require(all(k in overrides for k in LANDMARKS), 'override-ends needs every landmark')
        flip = bool(overrides['bladeAtLowEnd']); method = 'override-ends'
    else:
        thin = depth < .5 * np.percentile(depth[known], 75); flip = max(_runs(thin), key=len).mean() < N / 2; method = 'thin-blade'
    q, U = _oriented(q, U, flip); centres, mid, extent, wide, _ = st._sections(q)
    known = ~np.isnan(extent[:, 0]); width = np.where(known, extent.max(1), 0); depth = np.where(known, extent.min(1), 0)
    if method == 'cross-guard':
        core = np.nan_to_num(extent.max(1)) > 2 * np.nanmedian(extent.max(1)); g0, g1 = np.flatnonzero(core)[[0, -1]]
    elif method == 'override-ends':
        g0 = int(overrides['gripEnd'] * N); g1 = int(overrides['bladeStart'] * N) - 1
    else:
        thin = depth < .5 * np.percentile(depth[known], 75); blade = max(_runs(thin), key=len); handle = np.arange(0, blade[0])
        body = np.median(depth[handle[len(handle) // 5: -len(handle) // 5]])     # a guard ring is thicker than the handle
        g1 = blade[0] - 1; window = np.arange(max(0, g1 - N // 10), g1 + 1); ring = window[depth[window] > 1.25 * body]
        g0 = int(ring[0]) if len(ring) else g1
    handle = np.arange(0, g0); require(len(handle) >= 12, 'Handle too short to measure')
    gw = np.median(width[handle[len(handle) // 4: -len(handle) // 4]])
    bulge = np.flatnonzero(width[:len(handle) // 2] > 1.1 * gw)                # pommel: the last clearly wider butt slice
    p1 = max(int(bulge[-1]) + 1 if len(bulge) else 0, int(round(.04 * len(handle))))
    marks = {'pommelEnd': p1 / N, 'gripStart': p1 / N, 'gripEnd': float(g0 / N), 'bladeStart': float((g1 + 1) / N)}
    return method, q, U, marks


def hafted_landmarks(q, U, overrides):
    """Butt | grip | haft | head of a club, axe or polearm. The head is the end with the widest sections."""
    N = st.SLICES; centres, mid, extent, wide, _ = st._sections(q)
    width = np.nan_to_num(extent.max(1)); quarter = N // 4
    flip = bool(overrides['headAtLowEnd']) if 'headAtLowEnd' in overrides else \
        np.percentile(width[:quarter], 90) > np.percentile(width[-quarter:], 90)
    q, U = _oriented(q, U, flip); centres, mid, extent, wide, _ = st._sections(q); width = np.nan_to_num(extent.max(1))
    shaft = float(np.median(width[int(.2 * N):int(.6 * N)])); require(shaft > 0, 'No haft section found')
    head = np.flatnonzero(width > 1.6 * shaft); head = head[head > N // 2]
    head_start = int(head[0]) if len(head) else int(.6 * N)                  # a club thickens gradually: 60% by default
    bulge = np.flatnonzero(width[:N // 6] > 1.25 * shaft)                       # a butt knob or cap wider than the haft
    butt = int(bulge[-1]) + 1 if len(bulge) else 0
    marks = {'pommelEnd': butt / N, 'gripStart': butt / N, 'gripEnd': head_start / N, 'bladeStart': head_start / N}
    return 'hafted-head' if len(head) else 'hafted-taper', q, U, marks


def measure(manifest, family, working, overrides=None, standard=None, *, profile_dir=None):
    """Every fit number for one design, without writing anything.

    `working` is the closed working shell (glTF positions and faces). Returns a dict with the landmarks, the
    similarity `matrix`, `gripEndpoints`, `joinY`, `thicknessProbes`, the grip report and the native length.
    """
    from .grip import GripDeparture, calibration, one_hand_round, two_hand_uniform
    overrides = dict(overrides or {}); standard = standard or json.loads(STANDARD.read_text(encoding='utf-8'))
    name = family['family']; route = ROUTES[name]; native = family['native']
    origin = np.array(native['gripOrigin'], float); grip_length = float(native['gripLength'])
    b = gltf_to_blender(working['positions']); faces = np.asarray(working['faces'])
    mean, U, q = _frame(b); N = st.SLICES; L = float(np.ptp(q[:, 0]))
    hafted = name in HAFTED_FAMILIES
    method, q, U, marks = (hafted_landmarks if hafted else bladed_landmarks)(q, U, overrides)
    centres, mid, extent, wide, _ = st._sections(q); t0 = float(q[:, 0].min()); known = ~np.isnan(extent[:, 0])
    auto = dict(marks); two_hand = route.hold == 'two'
    target = float(overrides['targetLength']) if 'targetLength' in overrides else stock_length(native)
    require(target or (two_hand and not hafted), 'The contract has no measured stock length: give targetLength')
    if hafted:
        # Scale to the overall length, then put the hand at the stock carrier's own fraction of its length.
        s = target / L
        lo = native['stockSpan'][0] if 'stockSpan' in native else native['dimensions']['b']['meshes'][0]['bounds'][0][1]
        centre_fraction = float(overrides.get('gripCentre', (origin[1] - lo) / stock_length(native)))
        half = grip_length / (s * L) / 2
        centre_fraction = min(max(centre_fraction, marks['pommelEnd'] + half), marks['bladeStart'] - half) \
            if marks['bladeStart'] - marks['pommelEnd'] > 2 * half else (marks['pommelEnd'] + marks['bladeStart']) / 2
        marks.update(gripStart=centre_fraction - half, gripEnd=centre_fraction + half)
    elif not two_hand and overrides.get('sizeToLength', True):
        marks['gripStart'] = grip_start_for_length({**marks, **{k: float(v) for k, v in overrides.items() if k in marks}},
                                                   grip_length, target)
    marks.update({k: float(v) for k, v in overrides.items() if k in LANDMARKS})
    at = lambda f: t0 + f * L
    grip = (centres >= at(marks['gripStart'])) & (centres <= at(marks['gripEnd'])) & known
    require(grip.any(), 'No surface in the measured grip span')
    centre = np.median(mid[grip], axis=0)
    src = lambda f, c=centre: mean + U @ np.array([at(f), c[0], c[1]])
    A, B = src(marks['gripStart']), src(marks['gripEnd']); usable = float(np.linalg.norm(B - A))
    s = grip_length / usable if not hafted else s
    Rn = np.array([np.cross(U[:, 0], U[:, 1]), U[:, 0], U[:, 1]]); require(abs(np.linalg.det(Rn) - 1) < 1e-9, 'Rotation required')
    rule_length = None
    if two_hand and not hafted:
        from .grip import section_dimensions
        centre_src = (A + B) / 2; R4 = np.eye(4); R4[:3, :3] = Rn
        s = standard['targetMidpointSection']['depth'] / section_dimensions(transform(b, R4), faces, float((Rn @ centre_src)[1]))[0]
        rule_length = float(L * s)
        if 'targetLength' in overrides: s = float(overrides['targetLength']) / L
        half = grip_length / s / 2; A, B = centre_src - U[:, 0] * half, centre_src + U[:, 0] * half
    M = np.eye(4); M[:3, :3] = s * Rn; M[:3, 3] = origin - s * Rn @ ((A + B) / 2)
    authority, departure, report = None, None, None
    chosen_length = hafted or 'targetLength' in overrides
    review = lambda: ({'decision': 'approved', 'measurementDigest': overrides['departureDigest'], 'notes': departure_notes,
                       **({'depthDepartureApproved': True} if two_hand and chosen_length else {})}
                      if overrides.get('departureDigest') else ({'depthDepartureApproved': True} if two_hand and chosen_length else None))
    departure_notes = ''
    raised = False
    try:
        if two_hand:
            authority = 'midpoint-depth-two-hand'; F, report = two_hand_uniform(b, faces, M, [A, B], origin, standard, review())
        elif hafted or overrides.get('uniform'):
            authority = 'usable-length-round'; F, report = one_hand_round(b, faces, M, origin, standard, review())
        else:
            F, report = calibration(b, faces, M, origin, standard)
    except GripDeparture as exc:
        report = exc.report; F = np.array(report.get('fitMatrix', M.tolist())); raised = True
    pending = raised          # a departure the fit worker will refuse until a review binds its own measurement digest
    fb = transform(b, F)
    joins = [float(transform(src(max(marks['gripStart'], marks['pommelEnd']) - .0015 / (s * L))[None], F)[0, 1]),
             float(transform(src(marks['gripEnd'] + .0015 / (s * L))[None], F)[0, 1])]
    nudge = overrides.get('joinNudge', [0, 0]); require(len(nudge) == 2 and max(map(abs, nudge)) <= .0005, 'Join nudge too large')
    cleared = [clear_cut(fb[:, 1], y) for y in joins]
    joins = [cleared[0][0] + nudge[0], cleared[1][0] + nudge[1]]
    require(joins[0] < joins[1], 'Part joins out of order')
    probes = []
    for k, f in enumerate((.15, .4, .65, .85)):
        fs = marks['bladeStart'] + f * (1 - marks['bladeStart']); ts = at(fs); j = int(np.clip((ts - t0) / L * N, 0, N - 1))
        c = mid[j]; half_width = np.nanmax(extent[j]) / 2
        cand = np.flatnonzero((np.abs(q[:, 0] - ts) < .004 * L) & (np.abs(q[:, 1] - c[0]) < .12 * half_width))
        require(len(cand) > 10, f'No surface for the thickness probe at {f}')
        lo_i = cand[np.argmin(q[cand, 2])]
        near = cand[(np.abs(q[cand, 0] - q[lo_i, 0]) < .003 * L) & (np.abs(q[cand, 1] - q[lo_i, 1]) < .003 * L)]
        hi_i = near[np.argmax(q[near, 2])]
        if q[hi_i, 2] - q[lo_i, 2] < .2 * np.nanmin(extent[j]):          # sparse thick shaft: nearest vertex on the far side
            top = cand[q[cand, 2] > c[1]]; hi_i = top[np.argmin(np.hypot(q[top, 0] - q[lo_i, 0], q[top, 1] - q[lo_i, 1]))]
        pts = [b[lo_i].tolist(), b[hi_i].tolist()]; fit = transform(np.array(pts), F); t = float(np.linalg.norm(fit[1] - fit[0]))
        require(t > .0008, f'Section thinner than 0.8 mm at station {k}')
        probes.append({'name': f'blade-section-{k}', 'sourcePoints': pts, 'points': fit.tolist(), 'measuredThickness': t,
                       'minimum': t / 2, 'maximumSampleError': .0025})
    return {'family': name, 'method': method, 'automaticLandmarks': auto, 'overrides': overrides, 'landmarks': marks,
            'gripEndpoints': [A.tolist(), B.tolist()], 'matrix': M.tolist(), 'fitMatrix': np.asarray(F).tolist(), 'scale': float(s),
            'usableSourceLength': usable, 'joinY': joins, 'joinClearance': [c[1] for c in cleared], 'thicknessProbes': probes,
            'sizingAuthority': authority, 'gripReport': report, 'departurePending': bool(pending),
            'nativeLength': float(np.ptp(fb[:, 1])), 'stockLength': stock_length(native), 'targetLength': target,
            'depthRuleLength': rule_length, 'fittedBounds': [fb.min(0).round(4).tolist(), fb.max(0).round(4).tolist()]}


def write(handoff, design, src, dst, working_path, donor_path, overrides=None, *, notes_authority=None):
    """Measure and write `<design>.<dst>.asset.json` with the working shell and textured donor copied into the handoff.

    The textured donor and working mesh approvals are not written here: they record a person's review of those exact
    files. A grip departure is bound only when `overrides['departureDigest']` carries the fit worker's measurement.
    """
    from tools.headkit.gltf import mesh
    handoff = Path(handoff); m = json.loads((handoff/f'{design}.{src}.asset.json').read_text(encoding='utf-8'))
    family = json.loads((handoff/m['familyProfile']['path']).read_text(encoding='utf-8'))
    out = handoff/f'{design}.{dst}.asset.json'; require(not out.exists(), 'Manifest exists: '+out.name)
    data = measure(m, family, mesh(working_path), overrides)
    gen = handoff/'generated'/design/dst; gen.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(donor_path, gen/'textured-donor.glb'); shutil.copyfile(working_path, gen/'working-shell.glb')
    if not (handoff/'weapon-grip-standard-v1.json').exists(): shutil.copyfile(STANDARD, handoff/'weapon-grip-standard-v1.json')
    record = {k: v for k, v in data.items() if k not in ('gripReport',)}
    record.update(working=sha(working_path), donor=sha(donor_path))
    (gen/'fit-data.json').write_text(json.dumps(record, indent=1), encoding='utf-8')
    rel = lambda p: {'path': p.relative_to(handoff).as_posix(), 'sha256': sha(p)}
    inputs = m['inputs']; inputs['texturedDonor'] = rel(gen/'textured-donor.glb'); inputs['workingMesh'] = rel(gen/'working-shell.glb')
    inputs['gripStandard'] = rel(handoff/'weapon-grip-standard-v1.json'); inputs.pop('exportSource', None); m['approval'].pop('exportGeometry', None)
    marks = json.dumps(data['landmarks']); over = json.dumps(overrides or {})
    m['fit'] = {'gripEndpoints': data['gripEndpoints'], 'matrix': data['matrix'], 'reviewed': True, 'sourceSha256': inputs['texturedDonor']['sha256'],
                'notes': f"Automatic fit ({data['method']}, tools/itemkit/fit_manifest.py): long axis to native +Y, scale {data['scale']:.5f}, "
                         f"native length {data['nativeLength']:.3f} m (stock carrier {data['stockLength'] or 0:.3f} m). "
                         f"Landmarks {marks}; overrides {over}."}
    if data['sizingAuthority']: m['fit']['sizingAuthority'] = data['sizingAuthority']
    report = data['gripReport'] or {}
    if overrides and overrides.get('departureDigest'):
        d = report.get('midpointRelativeDifferences', {})
        m['fit']['gripDeparture'] = {'decision': 'approved', 'measurementDigest': overrides['departureDigest'],
                                     'notes': (f"{notes_authority or overrides.get('uniformAuthority') or 'Automatic fit'}. Measured by the fit worker: "
                                               f"against the approved midpoint section this grip is {d.get('depth', 0) * 100:+.1f}% in depth and "
                                               f"{d.get('visibleFaceWidth', 0) * 100:+.1f}% in face width. Bound so the fit can run; the visual "
                                               "hand-fit review on both Human bodies is still required.")}
        if data['sizingAuthority'] == 'midpoint-depth-two-hand' and (ROUTES[family['family']].shape == 'hafted' or 'targetLength' in overrides):
            m['fit']['gripDeparture']['depthDepartureApproved'] = True
    m['processing'].update({'joinY': data['joinY'], 'thicknessProbes': data['thicknessProbes'], **PROCESSING})
    out.write_text(json.dumps(m, indent=2), encoding='utf-8')
    return out, data
