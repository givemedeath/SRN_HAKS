"""Pure-numpy outfit fitting: landmarks, proxy-rig pose conversion and lattice clearance.

The generation pose is converted by deforming geometry onto the stock bind
joints; stock bind frames and animations are never changed. Outputs are
measurements and a fitted proposal, not visual approval.
"""
import numpy as np

from mesh_ops import geodesic_labels, slice_loops, smooth_field
from stock_body import closest_on_triangles

PROXY = ["torso", "ua_L", "fa_L", "hand_L", "ua_R", "fa_R", "hand_R",
         "th_L", "sh_L", "ft_L", "th_R", "sh_R", "ft_R"]
SIDES = {"L": -1.0, "R": 1.0}  # NWN left is -X when the model faces +Y


def smoothstep(lo, hi, x):
    t = np.clip((np.asarray(x, float) - lo) / max(hi - lo, 1e-9), 0, 1)
    return t * t * (3 - 2 * t)


def rotate_front(verts, source_front, target_front="+Y"):
    if source_front == target_front:
        return np.array(verts, float)
    if {source_front, target_front} == {"-Y", "+Y"}:
        return np.asarray(verts, float) * np.array([-1.0, -1.0, 1.0])
    raise ValueError("Unsupported front conversion: " + source_front + " -> " + target_front)


def stock_targets(body):
    marks = body.landmarks()
    targets = {k: np.array(v, float) for k, v in marks.items() if isinstance(v, list)}
    pelvis = body.posed_part("pelvis")
    centre = pelvis[np.abs(pelvis[:, 0]) < 0.04]
    chest = body.posed_part("chest")
    targets.update(floor=float(marks["floor"]), crotch=float(centre[:, 2].min()),
                   collarTop=float(targets["neck"][2]), chestY=float(chest[:, 1].mean()))
    for side, part in (("L", "footl"), ("R", "footr")):
        foot = body.posed_part(part)
        targets["toe" + side] = foot[np.argmax(foot[:, 1])]
    return targets


def line_fit(points):
    points = np.asarray(points, float)
    centre = points.mean(0)
    _, _, vt = np.linalg.svd(points - centre)
    return centre, vt[0]


def at_height(centre, direction, z):
    return centre + direction * ((z - centre[2]) / direction[2])


def outfit_landmarks(verts, tris, welded, step=0.005):
    low, high = verts.min(0), verts.max(0)
    height = high[2] - low[2]
    crotch = None
    for z in np.arange(low[2] + 0.30 * height, low[2] + 0.70 * height, step):
        loops = slice_loops(verts, tris, 2, z, welded=welded)
        if any(loop["min"][0] < -0.01 and loop["max"][0] > 0.01 for loop in loops):
            crotch = float(z)
            break
    if crotch is None:
        raise ValueError("Crotch landmark not found: legs never merge")
    legs = {"L": [], "R": []}
    for z in np.linspace(low[2] + 0.12 * height, crotch - 0.04 * height, 12):
        loops = slice_loops(verts, tris, 2, z, welded=welded)
        for side, sign in SIDES.items():
            candidates = [l for l in loops if np.sign(l["center"][0]) == sign]
            if candidates:
                big = max(candidates, key=lambda l: (l["max"][0] - l["min"][0]) * (l["max"][1] - l["min"][1]))
                legs[side].append(big["center"])
    torso_z = crotch + 0.45 * (high[2] - crotch)
    torso = [l for l in slice_loops(verts, tris, 2, torso_z, welded=welded)
             if l["min"][0] < -0.01 and l["max"][0] > 0.01]
    if not torso:
        raise ValueError("Torso cross-section not found")
    torso = max(torso, key=lambda l: l["faces"])
    half_width = float(max(-torso["min"][0], torso["max"][0]))
    marks = {"floor": float(low[2]), "crotch": crotch, "collarTop": float(high[2]), "torsoHalfWidth": half_width,
             "chestY": float(torso["center"][1]), "legs": {}, "arms": {}}
    for side, sign in SIDES.items():
        centre, direction = line_fit(legs[side])
        marks["legs"][side] = {"centre": centre, "direction": direction if direction[2] > 0 else -direction,
                               "samples": len(legs[side])}
        reach = float(np.max(sign * verts[:, 0]))
        centres, radii = [], []
        for c in np.linspace(half_width + 0.03 * height, 0.92 * reach, 14):
            loops = slice_loops(verts, tris, 0, sign * c, welded=welded,
                                select=lambda p: p[:, 2].mean() > crotch)
            if loops:
                top = max(loops, key=lambda l: l["center"][2])
                centres.append(top["center"])
                # Vertical planes cut the angled arm obliquely; the minor principal extent of the
                # section approximates the true sleeve diameter, the major one does not.
                planar = top["points"][:, 1:] - top["points"][:, 1:].mean(0)
                if len(planar) >= 3:
                    _, _, vt = np.linalg.svd(planar, full_matrices=False)
                    minor = planar @ vt[-1]
                    radii.append(float((minor.max() - minor.min()) / 2))
        if len(centres) < 6:
            raise ValueError("Arm centreline not found on side " + side)
        centre, direction = line_fit(centres)
        direction = direction if np.sign(direction[0]) == sign else -direction
        # Two-segment fit: A-posed arms bend at the elbow, so one line biases the shoulder.
        centres = np.asarray(centres)
        best = None
        for split in range(3, len(centres) - 2):
            upper_c, upper_d = line_fit(centres[:split])
            lower_c, lower_d = line_fit(centres[split:])
            residual = sum(np.linalg.norm((p - c) - d * ((p - c) @ d)) ** 2
                           for points, c, d in ((centres[:split], upper_c, upper_d), (centres[split:], lower_c, lower_d))
                           for p in points)
            if best is None or residual < best[0]:
                best = (residual, split, upper_c, upper_d, lower_c, lower_d)
        _, split, upper_c, upper_d, lower_c, lower_d = best
        upper_d = upper_d if np.sign(upper_d[0]) == sign else -upper_d
        lower_d = lower_d if np.sign(lower_d[0]) == sign else -lower_d
        selected = verts[(np.sign(verts[:, 0]) == sign) & (verts[:, 2] > crotch - 0.1 * height)]
        offsets = selected - centre
        radial = np.linalg.norm(offsets - np.outer(offsets @ direction, direction), axis=1)
        reachable = selected[radial < 2.5 * max(radii)]
        fingertip = reachable[np.argmax((reachable - centre) @ direction)]
        marks["arms"][side] = {"centre": centre, "direction": direction, "radius": float(np.percentile(radii, 75)),
                               "fingertip": fingertip, "samples": len(centres), "split": int(split),
                               "centres": centres,
                               "upperCentre": upper_c, "upperDirection": upper_d,
                               "lowerCentre": lower_c, "lowerDirection": lower_d}
    return marks


def similarity(marks, targets):
    """Uniform scale about the floor from crotch and collar heights, then centring."""
    o = np.array([marks["crotch"] - marks["floor"], marks["collarTop"] - marks["floor"]])
    s = np.array([targets["crotch"] - targets["floor"], targets["collarTop"] - targets["floor"]])
    scale = float(o @ s / (o @ o))
    offset = np.array([0.0, targets["chestY"] - scale * marks["chestY"], targets["floor"] - scale * marks["floor"]])
    centre_x = np.mean([marks["legs"]["L"]["centre"][0], marks["legs"]["R"]["centre"][0]])
    offset[0] = -scale * centre_x
    return scale, offset


def apply_similarity(marks, scale, offset):
    point = lambda p: scale * np.asarray(p, float) + offset
    out = {k: (scale * v + offset[2] if k in ("floor", "crotch", "collarTop") else v) for k, v in marks.items()
           if not isinstance(v, dict)}
    out["torsoHalfWidth"] = scale * marks["torsoHalfWidth"]
    out["chestY"] = scale * marks["chestY"] + offset[1]
    out["legs"] = {s: {**v, "centre": point(v["centre"])} for s, v in marks["legs"].items()}
    out["arms"] = {s: {**v, "centre": point(v["centre"]), "fingertip": point(v["fingertip"]),
                       "upperCentre": point(v["upperCentre"]), "lowerCentre": point(v["lowerCentre"]),
                       "centres": point(v["centres"]),
                       "radius": scale * v["radius"]} for s, v in marks["arms"].items()}
    return out


def outfit_joints(marks, targets, verts):
    joints = {}
    ratio = (marks["crotch"] - marks["floor"]) / (targets["crotch"] - targets["floor"])
    for side in SIDES:
        leg = marks["legs"][side]
        ankle_z = marks["floor"] + ratio * (targets["ankle" + side][2] - targets["floor"])
        hip_z = marks["crotch"] + ratio * (targets["hip" + side][2] - targets["crotch"])
        hip = at_height(leg["centre"], leg["direction"], hip_z)
        ankle = at_height(leg["centre"], leg["direction"], ankle_z)
        fraction = (targets["knee" + side][2] - targets["ankle" + side][2]) / \
            (targets["hip" + side][2] - targets["ankle" + side][2])
        sign = SIDES[side]
        foot = verts[(np.sign(verts[:, 0]) == sign) & (verts[:, 2] < ankle_z)]
        joints.update({"hip" + side: hip, "knee" + side: ankle + fraction * (hip - ankle), "ankle" + side: ankle,
                       "toe" + side: foot[np.argmax(foot[:, 1])] if len(foot) else ankle + [0, 0.15, 0]})
        arm = marks["arms"][side]
        uc, ud, lc, ld = arm["upperCentre"], arm["upperDirection"], arm["lowerCentre"], arm["lowerDirection"]
        stock_shoulder = np.array(targets["shoulder" + side], float)
        # Sleeve root: the upper-arm centreline point nearest the stock shoulder (the rest of the
        # offset is absorbed by the shoulder blend). Elbow: closest approach of the two segments.
        shoulder = uc + ud * ((stock_shoulder - uc) @ ud)
        hand_length = np.linalg.norm(targets["fingertip" + side] - targets["wrist" + side])
        wrist = arm["fingertip"] - hand_length * ld
        # Elbow at the stock upper/lower length ratio along the measured centreline polyline;
        # intersecting two near-parallel segment lines is ill-conditioned for a straight A-pose arm.
        upper = np.linalg.norm(targets["elbow" + side] - targets["shoulder" + side])
        lower = np.linalg.norm(targets["wrist" + side] - targets["elbow" + side])
        path = [shoulder] + [p for p in arm["centres"] if (p - shoulder) @ ld > 0 and (wrist - p) @ ld > 0] + [wrist]
        path = np.asarray(path)
        lengths = np.r_[0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
        goal = upper / (upper + lower) * lengths[-1]
        segment = min(int(np.searchsorted(lengths, goal)), len(path) - 1)
        fraction = (goal - lengths[segment - 1]) / max(lengths[segment] - lengths[segment - 1], 1e-9)
        elbow = path[segment - 1] + fraction * (path[segment] - path[segment - 1])
        joints.update({"shoulder" + side: shoulder, "elbow" + side: elbow, "wrist" + side: wrist,
                       "fingertip" + side: arm["fingertip"],
                       "shoulderOffsetFromStock" + side: float(np.linalg.norm(shoulder - stock_shoulder))})
    return joints


def rotation_between(a, b):
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    axis = np.cross(a, b)
    s, c = np.linalg.norm(axis), float(np.clip(a @ b, -1, 1))
    if s < 1e-12:
        return np.eye(3)
    k = axis / s
    cross = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + s * cross + (1 - c) * cross @ cross


def segment_transform(source_start, source_end, target_start, target_end, stretch=True):
    direction = source_end - source_start
    length = np.linalg.norm(direction)
    unit = direction / length
    scale = np.linalg.norm(target_end - target_start) / length if stretch else 1.0
    stretch_matrix = np.eye(3) + (scale - 1) * np.outer(unit, unit)
    linear = rotation_between(direction, target_end - target_start) @ stretch_matrix
    matrix = np.eye(4)
    matrix[:3, :3] = linear
    matrix[:3, 3] = target_start - linear @ source_start
    return matrix


def proxy_transforms(joints, targets):
    t = {"torso": np.eye(4)}
    for side in SIDES:
        t["ua_" + side] = segment_transform(joints["shoulder" + side], joints["elbow" + side],
                                            targets["shoulder" + side], targets["elbow" + side])
        t["fa_" + side] = segment_transform(joints["elbow" + side], joints["wrist" + side],
                                            targets["elbow" + side], targets["wrist" + side])
        t["hand_" + side] = segment_transform(joints["wrist" + side], joints["fingertip" + side],
                                              targets["wrist" + side], targets["fingertip" + side], stretch=False)
        t["th_" + side] = segment_transform(joints["hip" + side], joints["knee" + side],
                                            targets["hip" + side], targets["knee" + side])
        t["sh_" + side] = segment_transform(joints["knee" + side], joints["ankle" + side],
                                            targets["knee" + side], targets["ankle" + side])
        t["ft_" + side] = segment_transform(joints["ankle" + side], joints["toe" + side],
                                            targets["ankle" + side], targets["toe" + side], stretch=False)
    return t


SEGMENTS = ["torso", "arm_L", "arm_R", "leg_L", "leg_R"]


def segment_labels(points, rows, cols, joints, marks, blends):
    """Geodesic segmentation of welded points into torso / arms / legs, softened over the mesh."""
    seeds = [np.flatnonzero((np.abs(points[:, 0]) < blends["torsoCoreHalfWidth"])
                            & (points[:, 2] > marks["crotch"] + 0.12) & (points[:, 2] < marks["collarTop"] - 0.12))]
    for side, sign in SIDES.items():
        shoulder, tip = joints["shoulder" + side], joints["fingertip" + side]
        axis = (tip - shoulder) / np.linalg.norm(tip - shoulder)
        offsets = points - shoulder
        along = offsets @ axis
        radial = np.linalg.norm(offsets - np.outer(along, axis), axis=1)
        seeds.append(np.flatnonzero((along > blends["armSeedFraction"] * np.linalg.norm(tip - shoulder))
                                    & (radial < blends["armSeedRadius"]) & (np.sign(points[:, 0]) == sign)))
    for side, sign in SIDES.items():
        seeds.append(np.flatnonzero((points[:, 2] < joints["knee" + side][2]) & (np.sign(points[:, 0]) == sign)))
    labels, _ = geodesic_labels(points, rows, cols, seeds)
    labels[labels < 0] = 0
    soft = np.eye(len(SEGMENTS))[labels]
    soft = smooth_field(soft, rows, cols, len(points), blends["labelSmoothing"])
    return labels, soft / soft.sum(1, keepdims=True), {name: int(len(s)) for name, s in zip(SEGMENTS, seeds)}


def apply_segment_overrides(points, labels, rows, cols, overrides, smoothing, joints):
    """Recorded manual relabelling in aligned space; returns new labels, soft labels and per-rule counts."""
    labels = labels.copy()
    counts = []
    for rule in overrides:
        source, target = SEGMENTS.index(rule["from"]), SEGMENTS.index(rule["to"])
        mask = labels == source
        if "minArmRadial" in rule:
            side = rule["minArmRadial"]["side"]
            shoulder, tip = joints["shoulder" + side], joints["fingertip" + side]
            axis = (tip - shoulder) / np.linalg.norm(tip - shoulder)
            offsets = points - shoulder
            radial = np.linalg.norm(offsets - np.outer(offsets @ axis, axis), axis=1)
            mask &= radial > rule["minArmRadial"]["value"]
        if "maxZ" in rule:
            mask &= points[:, 2] < rule["maxZ"]
        if "maxAbsX" in rule:
            mask &= np.abs(points[:, 0]) < rule["maxAbsX"]
        labels[mask] = target
        counts.append({**rule, "vertices": int(mask.sum())})
    soft = smooth_field(np.eye(len(SEGMENTS))[labels], rows, cols, len(points), smoothing)
    return labels, soft / soft.sum(1, keepdims=True), counts


def proxy_weights(points, soft, joints, blends):
    """Proxy-rig weights on welded points: segment membership times along-limb splits."""
    n = len(points)
    w = {name: np.zeros(n) for name in PROXY}
    for side in SIDES:
        shoulder, wrist, tip = joints["shoulder" + side], joints["wrist" + side], joints["fingertip" + side]
        axis = (tip - shoulder) / np.linalg.norm(tip - shoulder)
        along = (points - shoulder) @ axis
        member = soft[:, SEGMENTS.index("arm_" + side)] * smoothstep(-blends["shoulder"], blends["shoulder"], along)
        elbow_at, wrist_at = (joints["elbow" + side] - shoulder) @ axis, (wrist - shoulder) @ axis
        lower = smoothstep(elbow_at - blends["elbow"], elbow_at + blends["elbow"], along)
        hand = smoothstep(wrist_at - blends["wrist"], wrist_at + blends["wrist"], along)
        w["ua_" + side] = member * (1 - lower)
        w["fa_" + side] = member * lower * (1 - hand)
        w["hand_" + side] = member * hand
        leg = soft[:, SEGMENTS.index("leg_" + side)]
        z = points[:, 2]
        knee, ankle = joints["knee" + side][2], joints["ankle" + side][2]
        shin = 1 - smoothstep(knee - blends["knee"], knee + blends["knee"], z)
        foot = 1 - smoothstep(ankle - blends["ankle"], ankle + blends["ankle"], z)
        w["th_" + side] = leg * (1 - shin)
        w["sh_" + side] = leg * shin * (1 - foot)
        w["ft_" + side] = leg * foot
    stacked = np.stack([w[name] for name in PROXY], axis=1)
    stacked[:, 0] = np.clip(1 - stacked[:, 1:].sum(1), 0, None)
    return stacked / stacked.sum(1, keepdims=True)


def blend(verts, weights, transforms):
    homogeneous = np.c_[verts, np.ones(len(verts))]
    out = np.zeros((len(verts), 3))
    for column, name in enumerate(PROXY):
        if np.any(weights[:, column]):
            out += weights[:, column, None] * (homogeneous @ transforms[name].T)[:, :3]
    return out


def _gaussian_blur(grid, sigma_cells):
    radius = int(np.ceil(3 * sigma_cells))
    kernel = np.exp(-0.5 * (np.arange(-radius, radius + 1) / sigma_cells) ** 2)
    kernel /= kernel.sum()
    for axis in range(3):
        padded = np.pad(grid, [(radius, radius) if a == axis else (0, 0) for a in range(grid.ndim)])
        out = np.zeros_like(grid)
        for offset, weight in enumerate(kernel):
            index = [slice(None)] * grid.ndim
            index[axis] = slice(offset, offset + grid.shape[axis])
            out += weight * padded[tuple(index)]
        grid = out
    return grid


def _trilinear(grid, coords):
    base = np.floor(coords).astype(int)
    frac = coords - base
    out = np.zeros((len(coords),) + grid.shape[3:])
    for corner in range(8):
        offset = np.array([(corner >> k) & 1 for k in range(3)])
        index = np.clip(base + offset, 0, np.array(grid.shape[:3]) - 1)
        weight = np.prod(np.where(offset, frac, 1 - frac), axis=1)
        out += weight.reshape((-1,) + (1,) * (grid.ndim - 3)) * grid[index[:, 0], index[:, 1], index[:, 2]]
    return out


def lattice_inflate(points, outer, body_verts, body_faces, distance, cell=0.02, sigma=0.04, iterations=12,
                    fade=0.5, reach=0.2, min_improvement=0.01, patience=2):
    """Smooth spatial inflation: splat clearance pushes into a voxel lattice, blur, sample at every point.

    Every layer inside a cell moves together, so garment layers keep their order and detail.
    Stops early once patience consecutive passes each remove less than min_improvement
    of the remaining clearance deficit (the field has plateaued).
    """
    low = points.min(0) - 6 * cell
    shape = tuple(np.ceil((points.max(0) - low) / cell).astype(int) + 7)
    current = points.copy()
    history = []
    initial = None
    near = np.ones(len(points), bool)
    stalled = 0
    for _ in range(iterations):
        closest = current.copy()
        gap, side = np.full(len(points), np.inf), np.ones(len(points))
        closest[near], gap[near], _, side[near] = closest_on_triangles(current[near], body_verts, body_faces)
        signed = side * gap
        if initial is None:
            initial = signed.copy()
            near = signed < distance + reach  # points farther than the total possible travel never violate
        need = np.where(outer, np.clip(distance - signed, 0, None), 0.0)
        history.append({"violations": int((need > 1e-4).sum()), "maximumNeeded": float(need.max()),
                        "deficit": float(need.sum()), "inside": int(((signed < 0) & outer).sum())})
        if history[-1]["violations"] == 0:
            break
        if len(history) > 1:
            before = history[-2]["deficit"]
            stalled = stalled + 1 if before - history[-1]["deficit"] < min_improvement * before else 0
            if stalled >= patience:
                history[-1]["stoppedEarly"] = True
                break
        direction = np.where((side >= 0)[:, None], current - closest, closest - current)
        direction /= np.maximum(np.linalg.norm(direction, axis=1), 1e-12)[:, None]
        active = need > 1e-4
        coords = (current[active] - low) / cell
        cells = np.clip(np.round(coords).astype(int), 0, np.array(shape) - 1)
        push = np.zeros(shape + (3,))
        count = np.zeros(shape)
        np.add.at(push, (cells[:, 0], cells[:, 1], cells[:, 2]), direction[active] * need[active, None])
        np.add.at(count, (cells[:, 0], cells[:, 1], cells[:, 2]), 1.0)
        blurred_push = np.stack([_gaussian_blur(push[..., k], sigma / cell) for k in range(3)], axis=-1)
        blurred_count = _gaussian_blur(count, sigma / cell)
        field = blurred_push / np.maximum(blurred_count, 1e-9)[..., None]
        field *= (blurred_count / (blurred_count + fade))[..., None]
        current = current + _trilinear(field, (current - low) / cell)
    gap, side = np.full(len(points), np.inf), np.ones(len(points))
    _, gap[near], _, side[near] = closest_on_triangles(current[near], body_verts, body_faces)
    signed = side * gap
    history.append({"violations": int(((signed < distance - 1e-4) & outer).sum()),
                    "inside": int(((signed < 0) & outer).sum()), "hiddenInside": int(((signed < 0) & ~outer).sum()),
                    "maximumNeeded": float(np.where(outer, np.clip(distance - signed, 0, None), 0).max()),
                    "final": True})
    return current, history, signed, initial
