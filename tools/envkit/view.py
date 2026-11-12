"""Pictures to judge a sheet's work by, made without the game: each reference beside the crop it was drawn from, and
a model seen square on from its sides with a metre grid, to read the boxes of a game set from.

A game set states lit parts, painted and smoothed parts, wire mesh panels, fences, closing faces and a door in metres
on the finished model. `elevations` draws that model as it will ship (turned, hung and retouched as its set says so
far) with a line every half or quarter metre labelled in the model's own x or y and z; with `lit` it shows what the
set's lit boxes light, in its own colour, and dims the rest blue, and counts for each lit part the texels its box
holds and the texels it lights: a box that holds much and lights nothing is on the wrong part of the model. A generated
model that is in no game set yet is drawn as it came back, at a stated height (`raw`). `perspective` draws the model
as it will ship from a stated eye, fence sheets and all, where a square-on view does not show what is wrong: inside a
hole, under an overhang, through a fence; with a `grid` it measures off what it shows, a line a stated distance
apart on the upright plane through what the eye looks at (the Saeder-Krupp yard's fronts were lined up by such a grid
through a long lens, 2026-11-12). `page` puts the pictures of many models on one page, to compare them at a glance.
These were one-off scripts for the Ares Depot (2026-11-11)."""
import math
from pathlib import Path

import numpy as np

from . import convert, glow, require



def contact(run, output, columns=3):
    """One picture of a reference run: each `<asset>-s<seed>-b0.png` of the folder beside `crops/<asset>.png`, the
    crop of the sheet it was drawn from. Returns the number of references shown."""
    from PIL import Image, ImageDraw
    require(type(columns) is int and columns > 0, 'A contact picture has one column at least')
    run = Path(run); crop_width, side, pad, label = 200, 300, 8, 16; cells = []
    for path in sorted(run.glob('*-b0.png')):
        name = path.name.rsplit('-s', 1)[0]
        require((run / 'crops' / f'{name}.png').is_file(), f'{path.name} has no crop beside it: crops/{name}.png is not in {run}')
        cell = Image.new('RGB', (crop_width + side + pad * 3, side + label + pad), (255, 255, 255))
        with Image.open(run / 'crops' / f'{name}.png') as crop, Image.open(path) as drawn:
            crop = crop.convert('RGB'); crop.thumbnail((crop_width, side)); drawn = drawn.convert('RGB'); drawn.thumbnail((side, side))
        cell.paste(crop, (pad, label)); cell.paste(drawn, (crop_width + pad * 2, label))
        ImageDraw.Draw(cell).text((pad, 2), name, fill=(0, 0, 0)); cells.append(cell)
    require(cells, 'No references in ' + str(run))
    rows = -(-len(cells) // columns); width, height = cells[0].size
    page = Image.new('RGB', (width * columns, height * rows), (255, 255, 255))
    for index, cell in enumerate(cells):
        page.paste(cell, (index % columns * width, index // columns * height))
    Path(output).parent.mkdir(parents=True, exist_ok=True); page.save(output)
    return len(cells)


def _drawn(points, uvs, faces, picture, output, name, sides, scale, grid, fine, lit):
    from PIL import Image
    where, covered, toward = glow.position_map(points, uvs, faces, fine, facing=True)
    rgba = np.asarray(picture.convert('RGBA').resize((fine, fine)), float) / 255
    base = rgba[..., :3] * rgba[..., 3:] + np.array([1.0, 0.0, 1.0]) * (1 - rgba[..., 3:])  # what is seen through shows magenta
    report = {'bounds': [points.min(0).round(2).tolist(), points.max(0).round(2).tolist()], 'pictures': []}
    if lit is not None:
        shine = glow.glow(base, where, covered, lit)
        report['litShare'] = round(float((shine.max(-1) > 0.02).sum() / max(covered.sum(), 1)), 3)
        report['litParts'] = [{'part': region.get('part'), 'held': int(glow.inside(where, covered, region['box']).sum()),
                               'lit': int((glow.glow(base, where, covered, [region]).max(-1) > 0.02).sum())} for region in lit]
        base = np.where(shine.max(-1, keepdims=True) > 0.02, np.maximum(shine, 0.1), base * 0.35 * [0.6, 0.7, 1.0])
    extent = float(max(points.max(0) - points.min(0))); pixels = scale or max(int(1400 / extent), 1); output = Path(output); output.mkdir(parents=True, exist_ok=True)
    for side in sides:
        require(side in range(len(glow.SIDES)), 'A side is 0 (front), 1, 2 (back) or 3')
        ahead = np.array([*glow.SIDES[side], 0.0]); facing = covered & ((toward @ ahead) > 0.3)  # only what faces the viewer
        require(facing.any(), f'Nothing of {name} faces side {side}'); path = output / f'{name}-side{side}.png'
        glow.elevation(base, where, facing, side=side, scale=pixels, grid=grid or (0.5 if extent > 1.5 else 0.25)).save(path)
        report['pictures'].append(str(path))
    return report


def elevations(models, root, name, output, *, sides=(0,), scale=None, grid=None, fine=2048, lit=False):
    """Pictures `<name>-side<n>.png` of a game set's model as it will ship, with a grid. `models` is the loaded game
    set and `root` its output root. `lit` shows what its lit boxes light. Returns {bounds, pictures, litShare,
    litParts}, the last two with `lit`: the share of the model's texels that are lit, and for each lit part the texels
    its box holds and the texels it lights."""
    from PIL import Image
    require(name in models, 'No such model in the game set: ' + name); model = models[name]; source = Path(root) / model['source']
    require(not lit or model.get('lit'), name + ' states no lit parts')
    maps = {'base_color': source / 'texture_0_base_color.png'}
    made = convert.shape(source / 'model.glb', maps, height=model['height'], lift=model.get('lift', 0.0), sign_tilt=model.get('signTilt'),
                         **{key: model[key] for key in convert.RETOUCHING if key in model and key != 'fence'})  # a fence's sheets have a picture of their own
    with Image.open(maps['base_color']) as generated:
        picture = made['colour'] or generated.copy()
    return _drawn(made['vertices'], made['uvs'], made['faces'], picture, output, name, sides, scale, grid, fine, model['lit'] if lit else None)


def page(drawn, output, *, columns=2, high=300, widest=2400):
    """One picture of many models: each model's pictures side by side `high` pixels tall (narrower where they would
    be wider than `widest` together) under its name, `columns` models to a row. drawn: [(name, [picture paths])], as
    `elevations`, `raw` and `perspective` report them. Returns the number of models shown."""
    from PIL import Image, ImageDraw
    require(drawn and all(pictures for _, pictures in drawn), 'A page shows one picture at least of each model')
    require(type(columns) is int and columns > 0, 'A page has one column at least')
    label, pad, cells = 16, 10, []
    for name, pictures in drawn:
        shown = []
        for path in pictures:
            with Image.open(path) as picture:
                shown.append(picture.convert('RGB').resize((max(1, round(picture.width * high / picture.height)), high)))
        gaps = pad * (len(shown) - 1); across = sum(one.width for one in shown)
        if across + gaps > widest:
            shrink = max(widest - gaps, len(shown)) / across; shown = [one.resize((max(1, round(one.width * shrink)), max(1, round(high * shrink)))) for one in shown]
        cells.append((name, shown))
    wide = max(sum(one.width for one in shown) + pad * (len(shown) - 1) for _, shown in cells) + 2 * pad; tall = high + label + pad
    sheet = Image.new('RGB', (columns * wide, -(-len(cells) // columns) * tall), (255, 255, 255)); draw = ImageDraw.Draw(sheet)
    for index, (name, shown) in enumerate(cells):
        x, y = index % columns * wide + pad, index // columns * tall
        draw.text((x, y + 2), name, fill=(0, 0, 0))
        for one in shown:
            sheet.paste(one, (x, y + label)); x += one.width + pad
    Path(output).parent.mkdir(parents=True, exist_ok=True); sheet.save(output)
    return len(cells)


def eye(text):
    """label=ex,ey,ez,tx,ty,tz[,fov[,reach]] as (label, eye, target, fov, reach): where the eye is and what it looks at,
    in metres on the finished model, the angle of view in degrees and how far from the target a face is still drawn."""
    label, _, numbers = text.partition('=')
    try:
        values = [float(value) for value in numbers.split(',')]
    except ValueError:
        values = []
    require(label.replace('-', '').isalnum() and 6 <= len(values) <= 8, 'An eye is label=ex,ey,ez,tx,ty,tz[,fov[,reach]]: ' + text)
    fov, reach = (values[6:] + [50.0, 14.0][len(values) - 6:])
    require(values[:3] != values[3:6] and 1 <= fov <= 150 and reach > 0, 'An eye looks at another place than its own, through 1 to 150 degrees: ' + text)
    return label, np.array(values[:3]), np.array(values[3:6]), fov, reach


NEAR = 0.05  # metres in front of the eye at which a face is cut


def _in_front(corners):
    """A triangle cut at the near plane: the triangles of what lies in front of it. `corners` is three rows of (across,
    up, depth, u, v) in the eye's space."""
    kept = []
    for index in range(3):
        here, there = corners[index], corners[(index + 1) % 3]
        if here[2] >= NEAR:
            kept.append(here)
        if (here[2] >= NEAR) != (there[2] >= NEAR):
            kept.append(here + (NEAR - here[2]) / (there[2] - here[2]) * (there - here))
    return [np.array([kept[0], kept[index], kept[index + 1]]) for index in range(1, len(kept) - 1)]


def _measure(picture, at, target, right, focal, grid):
    """Draw on `picture` a line every `grid` metres of the upright plane through `target`, square to a level eye at
    `at`, labelled each whole metre in the model's own x or y (whichever runs more nearly across the picture) and z.
    Returns the pixels to a metre on that plane: what stands nearer the eye is drawn larger, what stands further smaller."""
    from PIL import ImageDraw
    wide, high = picture.size; ppm = focal / float(np.linalg.norm(target - at)); draw = ImageDraw.Draw(picture)
    axis = int(np.argmax(np.abs(right[:2]))); across = float(right[axis])  # metres of that axis to a metre across the picture

    def values(middle, half):
        return [number * grid for number in range(math.ceil((middle - half) / grid - 1e-9), math.floor((middle + half) / grid + 1e-9) + 1)]
    for value in values(float(target[axis]), wide / 2 / ppm * abs(across)):
        place, whole = round(wide / 2 + (value - target[axis]) / across * ppm), abs(value - round(value)) < 1e-6  # on the nearest pixel
        draw.line([(place, 0), (place, high)], fill=(0, 255, 0) if whole else (0, 110, 0))
        if whole:
            draw.text((place + 2, 2), f'{"xy"[axis]}{round(value)}', fill=(0, 255, 0))
    for value in values(float(target[2]), high / 2 / ppm):
        place, whole = round(high / 2 - (value - target[2]) * ppm), abs(value - round(value)) < 1e-6
        draw.line([(0, place), (wide, place)], fill=(0, 255, 0) if whole else (0, 110, 0))
        if whole:
            draw.text((2, place + 2), f'z{round(value)}', fill=(0, 255, 0))
    return ppm


def perspective(models, root, name, output, eyes, *, size=(1280, 800), grid=None):
    """Pictures `<name>-eye-<label>.png` of a game set's model as it will ship (retouched, closed, with its fence
    sheets) from stated eyes (`eye`): its picture alone, nearest face in front, see-through where the picture is, and a
    face seen from behind not drawn, as the game leaves it. A
    face that passes the eye is cut just in front of it. Drawn in software a face at a time, so `reach` keeps a large
    model to what is about the target. A tile group is drawn with the models placed in it (`tiles.parts`). `grid`,
    metres, draws a measuring grid on the upright plane through each eye's target (`_measure`); each eye must then be
    level with its target. Returns {pictures, faces}, the faces drawn for each eye, and with a grid `pixelsPerMetre`
    on each eye's plane."""
    from PIL import Image
    require(name in models, 'No such model in the game set: ' + name); require(eyes, 'Give an eye at least')
    require(grid is None or grid > 0, 'A measuring grid is more than nothing apart')
    level = [label for label, at, target, *_ in eyes if abs(at[2] - target[2]) > 1e-6]
    require(grid is None or not level, 'A measuring grid is drawn for an eye level with its target: give ' + ', '.join(level) + ' its target\'s height')
    meshes = []  # (points, uvs, faces, picture, repeated): each picture with the faces that show it

    shaped = {}  # each model shaped once, however often it is placed

    def add(one, at=(0.0, 0.0, 0.0), turn=0):
        if one not in shaped:
            model = models[one]; source = Path(root) / model['source']; maps = {'base_color': source / 'texture_0_base_color.png'}
            finished = convert.shape(source / 'model.glb', maps, height=model['height'], lift=model.get('lift', 0.0), sign_tilt=model.get('signTilt'),
                                     **{key: model[key] for key in convert.RETOUCHING if key in model})
            with Image.open(maps['base_color']) as generated:
                shaped[one] = (finished, np.asarray((finished['colour'] or generated).convert('RGBA')))
        finished, picture = shaped[one]; made = convert.place(finished, at, turn)
        meshes.append((made['vertices'], made['uvs'], np.asarray(made['faces']), picture, False))
        if made['wire']:  # the fence's sheets show a picture of their own, repeated
            wire = made['wire']; meshes.append((wire['vertices'], wire['uvs'], np.asarray(wire['faces']), np.asarray(wire['image'].convert('RGBA')), True))
    add(name)
    for part in (models[name].get('tiles') or {}).get('parts', []):
        add(part['model'], part['at'], part.get('turn', 0))
    points = np.vstack([mesh[0] for mesh in meshes]); uvs = np.vstack([mesh[1] for mesh in meshes]); starts = np.cumsum([0] + [len(mesh[0]) for mesh in meshes])
    faces = np.vstack([mesh[2] + start for mesh, start in zip(meshes, starts)]); owner = np.concatenate([np.full(len(mesh[2]), index) for index, mesh in enumerate(meshes)])
    wide, high = size; output = Path(output); output.mkdir(parents=True, exist_ok=True); report = {'pictures': [], 'faces': {}}
    for label, at, target, fov, reach in eyes:
        ahead = target - at; ahead = ahead / np.linalg.norm(ahead); right = np.cross(ahead, [0.0, 0.0, 1.0])
        require(np.linalg.norm(right) > 1e-6, f'The eye {label} looks straight up or down: move it a little to the side'); right /= np.linalg.norm(right); up = np.cross(right, ahead)
        rel = points - at; depth = rel @ ahead; focal = high / 2 / np.tan(np.radians(fov) / 2)
        eyed = np.column_stack([rel @ right, rel @ up, depth, uvs])  # each vertex in the eye's space, with its place on the picture
        # The game draws a face from the side its corners run counter-clockwise on, and nothing from behind: so does this. A
        # fence's sheets have a face each way for that reason (`convert.sheets`), and a wall seen from inside is not there.
        corner = points[faces]; front = (np.cross(corner[:, 1] - corner[:, 0], corner[:, 2] - corner[:, 0]) * (at - corner[:, 0])).sum(1) > 0
        shown = (np.linalg.norm(points[faces].mean(1) - target, axis=1) < reach) & (depth[faces] >= NEAR).any(1) & front
        image = np.zeros((high, wide, 3), np.uint8); image[:] = (40, 44, 52); buffer = np.full((high, wide), np.inf)
        for number in np.flatnonzero(shown):
            for corners in _in_front(eyed[faces[number]]):
                away = corners[:, 2]; a, b, c = np.stack([wide / 2 + corners[:, 0] / away * focal, high / 2 - corners[:, 1] / away * focal], 1)
                low = np.maximum(np.floor(np.minimum(np.minimum(a, b), c)).astype(int), 0); top = np.minimum(np.ceil(np.maximum(np.maximum(a, b), c)).astype(int), [wide - 1, high - 1])
                span = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
                if (top < low).any() or abs(span) < 1e-9:
                    continue
                xs, ys = np.meshgrid(np.arange(low[0], top[0] + 1) + 0.5, np.arange(low[1], top[1] + 1) + 0.5)
                second = ((xs - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (ys - a[1])) / span; third = ((b[0] - a[0]) * (ys - a[1]) - (xs - a[0]) * (b[1] - a[1])) / span
                first = 1 - second - third; inside = (first >= 0) & (second >= 0) & (third >= 0)
                if not inside.any():
                    continue
                weight = np.stack([first, second, third], -1)[inside] / away; z = 1 / weight.sum(-1); spot = (weight * z[:, None]) @ corners[:, 3:]  # perspective-correct
                _, _, _, texture, repeated = meshes[owner[number]]
                if repeated:
                    spot = (spot * len(texture)).astype(int) % len(texture); texel = texture[spot[:, 1], spot[:, 0]]
                else:
                    spot = np.clip((spot * [texture.shape[1], texture.shape[0]]).astype(int), 0, [texture.shape[1] - 1, texture.shape[0] - 1]); texel = texture[spot[:, 1], spot[:, 0]]
                py, px = (ys[inside] - 0.5).astype(int), (xs[inside] - 0.5).astype(int); keep = (texel[:, 3] >= 128) & (z < buffer[py, px])
                image[py[keep], px[keep]] = texel[keep, :3]; buffer[py[keep], px[keep]] = z[keep]
        require(np.isfinite(buffer).any(), f'Nothing of {name} is seen from the eye {label}')
        # 2. named apart from the square-on views (`<name>-side<n>.png`), whatever the label
        path = output / f'{name}-eye-{label}.png'; picture = Image.fromarray(image)
        if grid is not None:
            report.setdefault('pixelsPerMetre', {})[label] = round(_measure(picture, at, target, right, focal, grid), 3)
        picture.save(path); report['pictures'].append(str(path)); report['faces'][label] = int(shown.sum())
    return report


def raw(source, height, output, *, name=None, sides=(0,), scale=None, grid=None, fine=2048):
    """Pictures of a generated model as it came back, stood at `height` metres: for a model no game set states yet."""
    from PIL import Image
    source = Path(source); vertices, normals, uvs, faces = convert.read_glb(source / 'model.glb')
    points, _, uvs, _, angles = convert.fit(vertices, normals, uvs, height, faces=faces)
    with Image.open(source / 'texture_0_base_color.png') as generated:
        report = _drawn(points, uvs, faces, generated.copy(), output, name or source.name, sides, scale, grid, fine, None)
    return {**report, 'turnedByDegrees': np.round(angles, 1).tolist()}
