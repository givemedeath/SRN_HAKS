"""The openings of a tileset's tiles: how wide and tall each door hook's doorway is, and which black faces stand for a
doorway or a window.

A hook's doorway is measured by rays against what the tile draws (kit pieces apart): along the door's width both ways,
`ACROSS` metres over the hook, and upward from it. A ray that meets nothing within `FAR` leaves that measure None.
A black opening is an upright face on one of the cell's axes drawn with a named material (`materials`, patterns):
faces whose spans touch along the wall are one opening, a door where it starts within `SILL` metres of the walkable
ground in front of it, else a window."""
import fnmatch
import math
import re
from collections import defaultdict
from pathlib import Path

from . import detail, geometry, inventory, merged

ACROSS, FAR, NEAREST = 1.0, 20.0, 0.02
FOOT = 0.1  # metres over the hook the upward ray starts
SILL, GROUND = 0.4, 3.0  # metres: a door's foot over its ground, and how far about the opening its ground is looked for
SMALLEST, TOUCH, THIN = 0.2, 0.05, 0.05


def cast(triangles, origin, direction, far=FAR):
    """How far from `origin` along `direction` the nearest of `triangles` is met, or None (Moller-Trumbore)."""
    nearest = None; dx, dy, dz = direction
    for (ax, ay, az), (bx, by, bz), (cx, cy, cz) in triangles:
        ux, uy, uz, vx, vy, vz = bx - ax, by - ay, bz - az, cx - ax, cy - ay, cz - az
        px, py, pz = dy * vz - dz * vy, dz * vx - dx * vz, dx * vy - dy * vx; det = ux * px + uy * py + uz * pz
        if abs(det) < 1e-9:
            continue
        sx, sy, sz = origin[0] - ax, origin[1] - ay, origin[2] - az; u = (sx * px + sy * py + sz * pz) / det
        if not 0 <= u <= 1:
            continue
        qx, qy, qz = sy * uz - sz * uy, sz * ux - sx * uz, sx * uy - sy * ux; v = (dx * qx + dy * qy + dz * qz) / det
        if v < 0 or u + v > 1:
            continue
        t = (vx * qx + vy * qy + vz * qz) / det
        if NEAREST < t < far and (nearest is None or t < nearest):
            nearest = t
    return nearest


def hooks(set_text):
    """[(tile number, model, door number, {the hook's keys})] of a set file."""
    sections = inventory.sections(set_text)
    models = {int(name[4:]): keys.get('Model', '').lower() for name, keys in sections if re.fullmatch(r'TILE\d+', name)}
    return [(int(match[1]), models.get(int(match[1]), ''), int(match[2]), keys) for name, keys in sections for match in [re.fullmatch(r'TILE(\d+)DOOR(\d+)', name)] if match]


def measured(triangles, at, turn):
    """{width, height, left, right} of the doorway at a hook."""
    angle = math.radians(turn); along = (math.cos(angle), math.sin(angle), 0.0); middle = (at[0], at[1], at[2] + ACROSS)
    left, right = cast(triangles, middle, along), cast(triangles, middle, tuple(-value for value in along))
    up = cast(triangles, (at[0], at[1], at[2] + FOOT), (0.0, 0.0, 1.0))
    return {'width': round(left + right, 1) if None not in (left, right) else None, 'height': round(up + FOOT, 1) if up is not None else None,
            'left': None if left is None else round(left, 2), 'right': None if right is None else round(right, 2)}


def doorways(set_text, texts, kinds=('0',)):
    """[{tile, model, door, at, turn, width, height, left, right}] of a set's door hooks of `kinds` (Type; 0: a generic
    door), from `texts` {model: uncompiled text}. A model not among them is told with a note instead of measures."""
    found, drawn = [], {}
    for tile, model, door, keys in hooks(set_text):
        if keys.get('Type', '0').strip() not in kinds:
            continue
        said = {'tile': tile, 'model': model, 'door': door, 'at': [float(keys.get(key, 0) or 0) for key in ('X', 'Y', 'Z')], 'turn': float(keys.get('Orientation', 0) or 0)}
        if model not in texts:
            found.append({**said, 'note': 'no uncompiled model'}); continue
        if model not in drawn:
            drawn[model] = geometry.triangles(geometry.parse(texts[model])[2], lambda node: node.rendered and not detail.is_kit(node.name))
        found.append({**said, **measured(drawn[model], said['at'], said['turn'])})
    return found


def black(text, materials):
    """[{material, axis, plane, along, z, ground, kind}] of a model's openings drawn with `materials` (patterns)."""
    _, _, nodes = geometry.parse(text); moves = geometry.placed(nodes); rows = []
    chosen = [node for node in nodes if node.rendered and node.faces and any(fnmatch.fnmatchcase(node.material or '', one.lower()) for one in materials)]
    walk = [((x + 0.5) * geometry.STEP, (y + 0.5) * geometry.STEP, height) for (x, y), heights in geometry.walkable(nodes).items() for height in heights] if chosen else []
    for node in chosen:
        groups = defaultdict(list)
        for face in node.faces:
            if max(face[:3]) >= len(node.verts):
                continue
            points = [moves[id(node)](node.verts[corner]) for corner in face[:3]]
            for axis in (0, 1):
                if max(point[axis] for point in points) - min(point[axis] for point in points) < THIN:
                    groups[axis, round(sum(point[axis] for point in points) / 3, 1)].append(points); break
        for (axis, plane), faces in groups.items():
            along = 1 - axis; clusters = []
            for face in sorted(faces, key=lambda face: min(point[along] for point in face)):  # faces whose spans along the wall touch are one opening
                if clusters and min(point[along] for point in face) <= max(point[along] for point in clusters[-1]) + TOUCH:
                    clusters[-1] += face
                else:
                    clusters.append(list(face))
            for points in clusters:
                low, high = (pick(point[along] for point in points) for pick in (min, max)); bottom, top = (pick(point[2] for point in points) for pick in (min, max))
                if high - low < SMALLEST or top - bottom < SMALLEST:
                    continue
                spot = (plane, (low + high) / 2) if axis == 0 else ((low + high) / 2, plane)
                near = [z for x, y, z in walk if abs(x - spot[0]) < GROUND and abs(y - spot[1]) < GROUND and z <= bottom + 0.5]; ground = max(near, default=None)
                rows.append({'material': node.material, 'axis': 'xy'[axis], 'plane': plane, 'along': [round(low, 2), round(high, 2)], 'z': [round(bottom, 2), round(top, 2)],
                             'ground': None if ground is None else round(ground, 2), 'kind': 'door' if ground is not None and bottom - ground < SILL else 'window'})
    return rows


def openings(repo, tileset, materials=(), kinds=('0',)):
    """{tileset, hooks, black}: the doorways of the tileset's hooks, and the openings drawn with `materials`."""
    repo, tileset = Path(repo), tileset.lower()
    texts = {name: text for name, _, text, _, _ in inventory.drawn_copies(repo, tileset, None, merged.packs(repo, tileset))}
    set_text = (repo / f'srn_t_{tileset}' / f'{tileset}.set').read_bytes().decode('cp1252')
    return {'tileset': tileset, 'hooks': doorways(set_text, texts, kinds), 'black': [{'model': name, **row} for name, text in texts.items() for row in black(text, materials)] if materials else []}
