"""Pictures to judge a sheet's work by, made without the game: each reference beside the crop it was drawn from, and
a model seen square on from its sides with a metre grid, to read the boxes of a game set from.

A game set states lit parts, painted and smoothed parts, wire mesh panels, fences, closing faces and a door in metres
on the finished model. `elevations` draws that model as it will ship (turned, hung and retouched as its set says so
far) with a line every half or quarter metre labelled in the model's own x or y and z; with `lit` it shows what the
set's lit boxes light, in its own colour, and dims the rest blue. A generated model that is in no game set yet is
drawn as it came back, at a stated height (`raw`). These were one-off scripts for the Ares Depot (2026-11-11)."""
from pathlib import Path

import numpy as np

from . import convert, glow, require



def contact(run, output, columns=3):
    """One picture of a reference run: each `<asset>-s<seed>-b0.png` of the folder beside `crops/<asset>.png`, the
    crop of the sheet it was drawn from. Returns the number of references shown."""
    from PIL import Image, ImageDraw
    run = Path(run); crop_width, side, pad, label = 200, 300, 8, 16; cells = []
    for path in sorted(run.glob('*-b0.png')):
        name = path.name.rsplit('-s', 1)[0]
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
    set and `root` its output root. `lit` shows what its lit boxes light. Returns {bounds, pictures, litShare}."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    require(name in models, 'No such model in the game set: ' + name); model = models[name]; source = Path(root) / model['source']
    require(not lit or model.get('lit'), name + ' states no lit parts')
    maps = {'base_color': source / 'texture_0_base_color.png'}
    made = convert.shape(source / 'model.glb', maps, height=model['height'], lift=model.get('lift', 0.0), sign_tilt=model.get('signTilt'),
                         **{key: model[key] for key in convert.RETOUCHING if key in model and key != 'fence'})  # a fence's sheets have a picture of their own
    with Image.open(maps['base_color']) as generated:
        picture = made['colour'] or generated.copy()
    return _drawn(made['vertices'], made['uvs'], made['faces'], picture, output, name, sides, scale, grid, fine, model['lit'] if lit else None)


def raw(source, height, output, *, name=None, sides=(0,), scale=None, grid=None, fine=2048):
    """Pictures of a generated model as it came back, stood at `height` metres: for a model no game set states yet."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    source = Path(source); vertices, normals, uvs, faces = convert.read_glb(source / 'model.glb')
    points, _, uvs, _, angles = convert.fit(vertices, normals, uvs, height, faces=faces)
    with Image.open(source / 'texture_0_base_color.png') as generated:
        report = _drawn(points, uvs, faces, generated.copy(), output, name or source.name, sides, scale, grid, fine, None)
    return {**report, 'turnedByDegrees': np.round(angles, 1).tolist()}
