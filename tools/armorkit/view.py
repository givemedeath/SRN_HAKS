"""Offline views of an outfit's parts, posed by the body's own clips: a look at the cut before the game client.

`load` reads the parts `bake.resplit` made (`armorkit split --output`) or a bake's kept folder; `pose` samples a
clip of the body's animation chain, and `posed` moves each part with its bone, as the game does with a rigid
part; `render` draws parts orthographically with a depth buffer, flat shaded, each part in its own colour and
what the split made in the colour of its kind (`KINDS`); `sheet` lays the views out. `views` does all of it.

A part on the shoulder slot rides on the upper arm's child bone, and a clip that lifts the arm swings it with
the arm: this is how the Site Guard's shoulder pads were seen entering the chest with the arms up before the
client showed them (docs/armorkit/plan.md). A view shows where surfaces are, not how the game shades them:
the client check (`poses`) remains the evidence.
"""
from pathlib import Path

import numpy as np

from . import seams, split
from .registry import require

PALETTE = {'chest': (200, 200, 205), 'pelvis': (150, 150, 200), 'neck': (230, 210, 160), 'belt': (190, 170, 130),
           'bicepl': (220, 140, 120), 'bicepr': (220, 140, 120), 'shol': (120, 210, 210), 'shor': (120, 210, 210),
           'forel': (130, 200, 130), 'forer': (130, 200, 130), 'handl': (230, 210, 120), 'handr': (230, 210, 120),
           'legl': (120, 170, 220), 'legr': (120, 170, 220), 'shinl': (210, 130, 210), 'shinr': (210, 130, 210),
           'footl': (160, 120, 90), 'footr': (160, 120, 90)}
OTHER = (180, 180, 180)  # a part with no colour of its own
SKIN = (110, 100, 95)  # the body's own skin a part holds (`bodyskin.worn`)
KINDS = {split.CLOSING: (250, 200, 0), split.CAP: (250, 90, 20), split.WALL: (160, 0, 160), split.PADDED: (0, 120, 250),
         split.GUSSET: (60, 60, 60)}  # what the split made, by kind; a kept part tells only that a face was added
ADDED = (250, 200, 0)
LEGEND = 'closing yellow, cap orange, wall purple, pad cap blue, gusset dark grey'
DIRECTIONS = {'left': (1.0, 0.0, 0.0), 'right': (-1.0, 0.0, 0.0), 'front': (0.0, -1.0, 0.0), 'back': (0.0, 1.0, 0.0),
              'left front': (0.7, -0.7, 0.0), 'right back': (-0.7, 0.7, 0.0)}  # the way the view looks; the body faces +y, z up
FOCUS = {'shoulders': ('torso_g', 0.25, 0.5), 'hips': ('pelvis_g', 0.0, 0.5)}  # bone, height above it, half the view's width (m)


def load(path):
    """{part: {'v', 'f', 'made', 'pad', 'skin'}} from the .npz `bake.keep_parts` wrote or a folder `bake.store` kept
    parts in. A kept part tells only whether a face was added (`made` is then `split.OWN` or -1) and whether it
    is the body's skin; `skin` is all False where it is not given."""
    path = Path(path)
    if path.is_dir():
        from . import bake
        parts = {}
        for name, part in bake.stored(path).items():
            faces = np.asarray(part['f'], int)
            parts[name] = {'v': np.asarray(part['v'], float), 'f': faces, 'made': np.where(np.asarray(part['added'], bool), -1, split.OWN),
                           'pad': np.asarray(part.get('pad', np.zeros(len(faces), bool)), bool),
                           'skin': np.asarray(part.get('skin', np.zeros(len(faces), bool)), bool)}
        return parts
    with np.load(path, allow_pickle=False) as data:
        from . import bake
        require('kind' in data and str(data['kind']) == bake.WORN_KIND, f'{path} holds no parts `armorkit split` wrote')
        names = sorted({key.split('__')[0] for key in data.files if '__' in key})
        return {name: {'v': np.asarray(data[name + '__v'], float), 'f': np.asarray(data[name + '__f'], int),
                       'made': np.asarray(data[name + '__made'], int), 'pad': np.asarray(data[name + '__pad'], bool),
                       'skin': np.zeros(len(data[name + '__f']), bool)} for name in names}


def pose(body_pack, body, folders, clip, share=0.5):
    """(rest, posed, time) of the bones the parts ride on: the body's rest and the clip `clip` sampled `share` of
    the way through, each a {bone: 4x4} in body space. `folders` hold the animation models the body inherits
    (extracted stock supermodels: game data, kept outside the repository); a clip several models carry plays
    from the nearest, as in the client."""
    from tools.phenomorpher.phenomorpher.engine import anim_library, native_motion
    from . import measure
    require(0.0 <= share <= 1.0, 'A clip is sampled from 0 (its start) to 1 (its end)')
    blob = (Path(body_pack) / (body + '.mdl')).read_bytes()
    models, _, chain = measure.animation_models(body, blob, [body_pack, *folders])
    owners = anim_library.effective(chain, models)
    require(clip in owners, f'{body} has no clip {clip} in its animation chain')
    nodes = measure.ancestors(models[body]['nodes'], set(seams.BONES.values()))
    rest = native_motion.sample(nodes)
    owner = owners[clip]['owner']
    animated = {(body if node == owner else node): keys for node, keys in models[owner]['clips'][clip]['nodes'].items()}
    times = native_motion.sample_times(models[owner]['clips'][clip])
    time = times[min(len(times) - 1, int(round(share * (len(times) - 1))))]
    return rest, native_motion.sample(nodes, animated, time), float(time)


def posed(parts, rest, moved):
    """The parts moved as their bones moved from `rest` to `moved` (`pose`): each part rigidly with its bone
    (`seams.BONES`), a part with no bone there left where it is."""
    out = {}
    for name, part in parts.items():
        bone = seams.BONES.get(name)
        if bone in rest and bone in moved:
            turn = np.asarray(moved[bone], float) @ np.linalg.inv(np.asarray(rest[bone], float))
            part = {**part, 'v': np.asarray(part['v'], float) @ turn[:3, :3].T + turn[:3, 3]}
        out[name] = part
    return out


def colours(name, part):
    """Per face of a part: its colour, what the split made in the colour of its kind and the body's skin in `SKIN`."""
    made = np.asarray(part.get('made', np.zeros(len(part['f']), int)), int)
    tint = np.tile(np.array(PALETTE.get(name, OTHER), float), (len(made), 1))
    for kind, colour in KINDS.items():
        tint[made == kind] = colour
    tint[made == -1] = ADDED
    tint[np.asarray(part.get('skin', np.zeros(len(made), bool)), bool)] = SKIN
    return tint


def render(parts, direction, centre, extent, size=520, up=(0.0, 0.0, 1.0)):
    """An orthographic view of `parts` looking along `direction`, `extent` metres either side of `centre`: an
    RGB array, white where nothing is. Faces are lit flat from over the viewer's shoulder, both sides alike."""
    d = seams.unit(np.asarray(direction, float))
    right = seams.unit(np.cross(d, np.asarray(up, float)))
    upward = np.cross(right, d)
    light = seams.unit(-d + 0.4 * upward + 0.3 * right)
    image = np.full((size, size, 3), 255, np.uint8)
    depth = np.full((size, size), np.inf)
    scale = size / (2 * extent)
    for name, part in parts.items():
        v = np.asarray(part['v'], float)
        f = np.asarray(part['f'], int)
        if not len(f):
            continue
        relative = v - np.asarray(centre, float)
        x, y, z = relative @ right * scale + size / 2, size / 2 - relative @ upward * scale, relative @ d
        corners = v[f]
        normal = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
        normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-12)
        shaded = np.clip(colours(name, part) * (0.35 + 0.65 * np.abs(normal @ light))[:, None], 0, 255).astype(np.uint8)
        for k, (a, b, c) in enumerate(f):
            xs, ys = np.array([x[a], x[b], x[c]]), np.array([y[a], y[b], y[c]])
            x0, x1 = max(int(np.floor(xs.min())), 0), min(int(np.ceil(xs.max())), size - 1)
            y0, y1 = max(int(np.floor(ys.min())), 0), min(int(np.ceil(ys.max())), size - 1)
            den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
            if x0 > x1 or y0 > y1 or abs(den) < 1e-12:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            l0 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / den
            l1 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / den
            l2 = 1 - l0 - l1
            inside = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
            nearer = l0 * z[a] + l1 * z[b] + l2 * z[c]
            region = depth[y0:y1 + 1, x0:x1 + 1]
            better = inside & (nearer < region)
            region[better] = nearer[better]
            image[y0:y1 + 1, x0:x1 + 1][better] = shaded[k]
    return image


def framed(parts, bones, focus):
    """(centre, extent) of a view: a `FOCUS` preset about its bone, or `body` for everything the parts hold."""
    if focus == 'body':
        points = np.concatenate([np.asarray(part['v'], float) for part in parts.values()])
        low, high = points.min(axis=0), points.max(axis=0)
        return (low + high) / 2, 0.55 * float((high - low).max())
    require(focus in FOCUS, f'A view is framed on one of {sorted(FOCUS) + ["body"]}')
    bone, above, extent = FOCUS[focus]
    return np.asarray(bones[bone], float)[:3, 3] + np.array([0.0, 0.0, above]), extent


def sheet(images, columns, path, labels=(), legend=LEGEND):
    """The images in rows of `columns`, each labelled, and the legend of the kinds' colours under them."""
    from PIL import Image, ImageDraw
    height, width = images[0].shape[:2]
    rows = (len(images) + columns - 1) // columns
    out = Image.new('RGB', (width * columns, height * rows + 24), 'white')
    draw = ImageDraw.Draw(out)
    for k, image in enumerate(images):
        out.paste(Image.fromarray(image), ((k % columns) * width, (k // columns) * height))
        if k < len(labels):
            draw.text(((k % columns) * width + 6, (k // columns) * height + 4), labels[k], fill='black')
    draw.text((6, height * rows + 6), legend, fill='black')
    out.save(path)
    return Path(path)


def views(parts_path, output, body_pack, body='pmh0', folders=(), clip=None, share=0.5, focus='shoulders', directions=tuple(DIRECTIONS), size=520):
    """Render the parts at `parts_path` (`load`) from each of `directions`, at rest or posed by `clip` (`pose`),
    framed on `focus` (`framed`), into the sheet `output`: a record of what was drawn."""
    from . import measure
    require(all(name in DIRECTIONS for name in directions), f'Views look from {sorted(DIRECTIONS)}')
    parts = load(parts_path)
    bones = {} if focus == 'body' else measure.body(body_pack, body)[0]  # only a preset frames on a bone
    time = None
    if clip is not None:
        rest, moved, time = pose(body_pack, body, folders, clip, share)
        parts, bones = posed(parts, rest, moved), {**bones, **moved}
    centre, extent = framed(parts, bones, focus)
    images = [render(parts, DIRECTIONS[name], centre, extent, size) for name in directions]
    title = 'rest' if clip is None else f'{clip} at {time:.2f} s'
    sheet(images, min(3, len(images)), output, [f'{title}: {name}' for name in directions])
    return {'output': str(output), 'parts': len(parts), 'clip': clip, 'time': time, 'focus': focus, 'views': list(directions)}
