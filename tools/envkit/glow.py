"""A model's glow map: which parts of its surface are lit from within, drawn from its own colour.

A generated model comes with colour, relief and shine but no map of what is lit. Its texture is thousands of scattered
islands, so the lit parts cannot be painted on the texture by eye. They are named where they are on the model instead:
boxes in game space (metres, after `convert.fit`), each with an optional colour test. `position_map` gives every texel
its place on the model, `glow` keeps the colour of the texels inside the boxes, and `elevation` draws the model's front
with a metre grid so the boxes can be read off a picture.

The game's own bloom adds no visible spread to a glow map (client check, 2026-11-10: bloom on and off looked the
same), so the light around a sign is drawn: `halo` blurs the model's glow, seen from the front, onto a card that stands
just in front of it and is added to the picture behind."""
import numpy as np

from . import require


def position_map(points, uvs, faces, size):
    """((size, size, 3) positions, (size, size) covered): the place on the model each texel shows. Rows run down the
    image as v runs up from 0, the way glTF and the game both read a texture. Each triangle also covers the texels
    just outside its edges, so the gutter the smaller mips blend in is lit like its island."""
    where = np.zeros((size, size, 3)); covered = np.zeros((size, size), bool)
    pixel = np.asarray(uvs, float) * size - 0.5
    for face in np.asarray(faces):
        a, b, c = pixel[face]
        low = np.maximum(np.floor(np.minimum(np.minimum(a, b), c)).astype(int) - 1, 0)
        high = np.minimum(np.ceil(np.maximum(np.maximum(a, b), c)).astype(int) + 1, size - 1)
        if (high < low).any():
            continue
        span = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
        if abs(span) < 1e-12:
            continue
        xs, ys = np.meshgrid(np.arange(low[0], high[0] + 1), np.arange(low[1], high[1] + 1))
        second = ((xs - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (ys - a[1])) / span
        third = ((b[0] - a[0]) * (ys - a[1]) - (xs - a[0]) * (b[1] - a[1])) / span
        weights = np.stack([1 - second - third, second, third], -1)
        margin = 1.0 / max(float(np.sqrt(abs(span))), 1.0)  # about one texel, in the triangle's own measure
        inside = (weights >= -margin).all(-1) & ~(covered[ys, xs] & (weights < 0).any(-1))  # a gutter never overwrites an island
        nearest = np.clip(weights[inside], 0, 1); nearest /= nearest.sum(-1, keepdims=True)  # a gutter texel shows the edge beside it
        where[ys[inside], xs[inside]] = nearest @ points[face]
        covered[ys[inside], xs[inside]] = True
    return where, covered


def glow(base, where, covered, regions):
    """The glow map, 0-1, the shape of `base` (0-1 colour at the position map's size).

    regions: [{box: [[x, y, z], [x, y, z]], gain, saturation, value}]. A texel inside a box, at least as vivid as
    `saturation` and as bright as `value` (both 0-1, default 0), glows with its own colour times `gain` (default 1).
    The two tests fade in over a band around their thresholds: a hard cut left ragged, blocky patches in the shop
    windows seen close (client check, 2026-11-10)."""
    require(base.shape[:2] == covered.shape, 'The colour and the position map must be the same size')
    brightest, dullest = base.max(-1), base.min(-1)
    vivid = (brightest - dullest) / np.maximum(brightest, 1e-6); lit = np.zeros_like(base)
    passing = lambda values, floor: 1.0 if floor <= 0 else np.clip((values - floor + 0.05) / 0.15, 0, 1)
    for region in regions:
        low, high = (np.asarray(corner, float) for corner in region['box'])
        require((high > low).all(), 'A glow box runs from its low corner to its high corner')
        inside = covered & (where >= low).all(-1) & (where <= high).all(-1)
        share = inside * passing(vivid, region.get('saturation', 0.0)) * passing(brightest, region.get('value', 0.0)) * region.get('gain', 1.0)
        lit = np.maximum(lit, base * share[..., None])
    return np.clip(lit, 0, 1)


def elevation(base, where, covered, *, scale=60, grid=1.0):
    """A picture of the model from the front (looking along -Y), `scale` pixels to the metre, with a line every `grid`
    metres and the ground at the bottom: x runs left to right from the model's low x, z bottom to top."""
    from PIL import Image, ImageDraw
    spots, colours = where[covered], base[covered]
    order = np.argsort(spots[:, 1]); spots, colours = spots[order], colours[order]  # the front is drawn last
    low, high = spots.min(0), spots.max(0)
    wide, tall = int(np.ceil((high[0] - low[0]) * scale)) + 1, int(np.ceil((high[2] - low[2]) * scale)) + 1
    picture = np.zeros((tall, wide, 3))
    picture[tall - 1 - ((spots[:, 2] - low[2]) * scale).astype(int), ((high[0] - spots[:, 0]) * scale).astype(int)] = colours
    image = Image.fromarray((picture * 255).astype(np.uint8)); draw = ImageDraw.Draw(image)
    # Seen from the front the model's +x is on the left, so the labels count down across the picture.
    for x in np.arange(np.ceil(low[0] / grid) * grid, high[0], grid):
        column = int((high[0] - x) * scale); draw.line([(column, 0), (column, tall)], fill=(0, 255, 0)); draw.text((column + 2, 2), f'x{x:g}', fill=(0, 255, 0))
    for z in np.arange(np.ceil(low[2] / grid) * grid, high[2], grid):
        row = tall - 1 - int((z - low[2]) * scale); draw.line([(0, row), (wide, row)], fill=(0, 255, 0)); draw.text((2, row + 2), f'z{z:g}', fill=(0, 255, 0))
    return image


def halo(lit, where, covered, *, reach=0.35, strength=0.6, core=0.6, scale=24, apart=0.25):
    """(image, cards) of the cards that carry the spread of the model's glow, or None where nothing glows.

    The glow seen from the front is blurred over `reach` metres and dimmed to `strength`. Over the lit parts
    themselves it is held back by `core`, or a sign's lettering washes out to white. Lit parts more than `apart`
    metres apart in depth get a card each, 4 cm in front of their own foremost texel: one card at the depth of a sign
    that stands out from the wall drew the door's glow over a person standing at the door (client check, 2026-11-10).
    Each card reaches past its glow on every side. The cards share one picture, stacked top to bottom; a card is its
    four places, each with the texture corner it shows: bottom left, bottom right, top right, top left as seen from
    the front. Only light that faces front is served: the cards are flat."""
    from PIL import Image, ImageFilter
    require(reach > 0 and 0 < strength <= 1 and 0 <= core <= 1, 'A halo needs a reach in metres, a strength up to 1 and a core of 0 to 1')
    shining = covered & (lit.max(-1) > 0)
    if not shining.any():
        return None
    spots, colours = where[shining], lit[shining]; pad = 2 * reach
    order = np.argsort(spots[:, 1]); spots, colours = spots[order], colours[order]
    layers = np.split(np.arange(len(spots)), np.flatnonzero(np.diff(spots[:, 1]) > apart) + 1)
    pictures, frames = [], []
    for layer in layers:
        low, high = spots[layer].min(0) - pad, spots[layer].max(0) + pad
        wide, tall = int(np.ceil((high[0] - low[0]) * scale)), int(np.ceil((high[2] - low[2]) * scale))
        picture = np.zeros((tall, wide, 3))
        rows = np.clip(((high[2] - spots[layer, 2]) * scale).astype(int), 0, tall - 1)
        columns = np.clip(((high[0] - spots[layer, 0]) * scale).astype(int), 0, wide - 1)
        np.maximum.at(picture, (rows, columns), colours[layer])
        sharp = Image.fromarray((picture * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))  # close the gaps between texels
        source = np.asarray(sharp.filter(ImageFilter.GaussianBlur(1)), float).max(-1, keepdims=True) / 255
        spread = np.asarray(sharp.filter(ImageFilter.GaussianBlur(reach * scale / 2)), float) * strength * (1 - core * source)
        pictures.append(spread.round().astype(np.uint8)); frames.append((low, high, float(spots[layer, 1].max()) + 0.04))
    sheet = np.zeros((sum(len(picture) for picture in pictures), max(picture.shape[1] for picture in pictures), 3), np.uint8)
    cards, top = [], 0
    for picture, (low, high, front) in zip(pictures, frames):
        tall, wide = picture.shape[:2]; sheet[top:top + tall, :wide] = picture
        left, right, upper, lower = 0.0, wide / sheet.shape[1], top / len(sheet), (top + tall) / len(sheet)
        cards.append([((high[0], front, low[2]), (left, lower)), ((low[0], front, low[2]), (right, lower)),
                      ((low[0], front, high[2]), (right, upper)), ((high[0], front, high[2]), (left, upper))])
        top += tall
    return Image.fromarray(sheet), cards
