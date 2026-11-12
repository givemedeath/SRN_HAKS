"""A model's glow map: which parts of its surface are lit from within, drawn from its own colour.

A generated model comes with colour, relief and shine but no map of what is lit. Its texture is thousands of scattered
islands, so the lit parts cannot be painted on the texture by eye. They are named where they are on the model instead:
boxes in game space (metres, after `convert.fit`), each with an optional colour test. `position_map` gives every texel
its place on the model, `glow` keeps the colour of the texels inside the boxes, and `elevation` draws the model's front
with a metre grid so the boxes can be read off a picture.

The game's own bloom adds no visible spread to a glow map (client check, 2026-11-10: bloom on and off looked the
same), so the light around a sign is drawn: `halo` blurs the model's glow, seen square on from the side it faces,
onto a card that stands just in front of it and is added to the picture behind."""
from typing import NamedTuple

import numpy as np

from . import require


SIDES = ((0.0, 1.0), (1.0, 0.0), (0.0, -1.0), (-1.0, 0.0))  # the ways a card can face: front (+Y), then +X, back, -X


def position_map(points, uvs, faces, size, *, facing=False):
    """((size, size, 3) positions, (size, size) covered): the place on the model each texel shows. Rows run down the
    image as v runs up from 0, the way glTF and the game both read a texture. Each triangle also covers the texels
    just outside its edges, so the gutter the smaller mips blend in is lit like its island. With `facing`, a third
    value: the way each texel's surface faces, as a unit vector."""
    where = np.zeros((size, size, 3)); covered = np.zeros((size, size), bool); toward = np.zeros((size, size, 3))
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
        if facing:
            out = np.cross(points[face[1]] - points[face[0]], points[face[2]] - points[face[0]])
            toward[ys[inside], xs[inside]] = out / max(float(np.linalg.norm(out)), 1e-12)
    return (where, covered, toward) if facing else (where, covered)


def inside(where, covered, box):
    """Which texels show a place within `box`, two corners in metres on the finished model."""
    low, high = (np.asarray(corner, float) for corner in box)
    require(low.shape == high.shape == (3,) and (high > low).all(), 'A box runs from its low corner to its high corner')
    return covered & (where >= low).all(-1) & (where <= high).all(-1)


def wires(where, pitch, wire):
    """Which texels lie on the wires of a chain-link mesh hung upright along X or Y: two sets of wires `wire` metres
    thick, leaning either way, `pitch` metres apart. The pattern is laid by place on the model, so it runs unbroken
    over the islands of the texture and matches on both faces of a panel."""
    require(0 < wire < pitch, 'A wire is thinner than the gap between wires')
    along, up = where[..., 0] + where[..., 1], where[..., 2]
    return (np.mod((along + up) / np.sqrt(2), pitch) < wire) | (np.mod((along - up) / np.sqrt(2), pitch) < wire)


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
        share = inside(where, covered, region['box']) * passing(vivid, region.get('saturation', 0.0)) * passing(brightest, region.get('value', 0.0)) * region.get('gain', 1.0)
        lit = np.maximum(lit, base * share[..., None])
    return np.clip(lit, 0, 1)


def elevation(base, where, covered, *, side=0, scale=60, grid=1.0):
    """A picture of the model seen square on from one of its sides (`SIDES`: 0 the front, looking along -Y), `scale`
    pixels to the metre, with the ground at the bottom and a line every `grid` metres labelled in the model's own
    x or y and z, so a lit part's box can be read off it. What is nearest the viewer is drawn last."""
    from PIL import Image, ImageDraw
    ahead_x, ahead_y = SIDES[side]; spots, colours = where[covered], base[covered]
    across, depth = spots[:, 0] * ahead_y - spots[:, 1] * ahead_x, spots[:, 0] * ahead_x + spots[:, 1] * ahead_y  # the viewer's left is positive
    order = np.argsort(depth); across, height, colours = across[order], spots[order, 2], colours[order]
    low, high, floor, top = across.min(), across.max(), height.min(), height.max()
    wide, tall = int(np.ceil((high - low) * scale)) + 1, int(np.ceil((top - floor) * scale)) + 1
    picture = np.zeros((tall, wide, 3))
    picture[tall - 1 - ((height - floor) * scale).astype(int), ((high - across) * scale).astype(int)] = colours
    image = Image.fromarray((picture * 255).astype(np.uint8)); draw = ImageDraw.Draw(image)
    # The line across the picture is x seen from front or back and y seen from either side; its sign follows the side.
    letter, sign = ('x', ahead_y) if ahead_y else ('y', -ahead_x)
    for value in np.arange(np.ceil(low / grid) * grid, high, grid):
        column = int((high - value) * scale); draw.line([(column, 0), (column, tall)], fill=(0, 255, 0))
        draw.text((column + 2, 2), f'{letter}{value * sign:g}', fill=(0, 255, 0))
    for z in np.arange(np.ceil(floor / grid) * grid, top, grid):
        row = tall - 1 - int((z - floor) * scale); draw.line([(0, row), (wide, row)], fill=(0, 255, 0)); draw.text((2, row + 2), f'z{z:g}', fill=(0, 255, 0))
    return image


class Halo(NamedTuple):
    """What `halo` makes: the one picture its cards share, the cards, and each card's light. Read by name: the three are
    told apart by nothing else."""
    image: object
    cards: list
    light: list


def halo(lit, where, covered, *, toward=None, reach=0.35, strength=0.6, core=0.6, scale=24, apart=0.25, least=0.05, clear=0.3):
    """The cards that carry the spread of the model's glow, a `Halo` (image, cards, light), or None where nothing glows.

    The glow seen square on is blurred over `reach` metres and dimmed to `strength`. Over the lit parts themselves it
    is held back by `core`, or a sign's lettering washes out to white. Lit parts more than `apart` metres apart in
    depth get a card each, 4 cm in front of their own foremost texel: one card at the depth of a sign that stands out
    from the wall drew the door's glow over a person standing at the door (client check, 2026-11-10). Each card
    reaches past its glow on every side. The cards share one picture, stacked top to bottom; a card is its four
    places, each with the texture corner it shows: bottom left, bottom right, top right, top left as seen from in
    front of it. light: for each card the lit parts it spreads, before any blur, as the square metres of them that
    each pixel of the card's picture holds; rows from the card's top, columns from its left. A tile cuts a card by it
    where the top of a building can be hidden (`tile.model_text`).

    `toward` (`position_map` with `facing`) says which way each texel's surface faces. With it a texel's light goes to
    a card on the upright side it faces most nearly (`SIDES`), so a sign on a side wall spreads from that wall. Three
    kinds of light then get no card: light that faces up or down; a patch of less than `least` square metres (the end
    of a sign box, the side of a window recess); and light the model itself hides, with more of the model standing
    over `clear` metres in front of most of it (the back of a sign box, inside the wall it hangs on). Patches whose
    cards would not touch get a card each. Without `toward` everything is taken to face front and nothing is left
    out. The cards are flat either way."""
    from PIL import Image, ImageFilter
    require(reach > 0 and 0 < strength <= 1 and 0 <= core <= 1, 'A halo needs a reach in metres, a strength up to 1 and a core of 0 to 1')
    shining = covered & (lit.max(-1) > 0)
    if not shining.any():
        return None
    pad = 2 * reach; pictures, frames, light = [], [], []
    if toward is not None:  # the upright side each texel faces most nearly, or none where it faces up or down
        along = np.stack([toward[..., 0] * x + toward[..., 1] * y for x, y in SIDES], -1)
        faced = np.where(along.max(-1) > 0.5, along.argmax(-1), -1)
    for side, (ahead_x, ahead_y) in enumerate(SIDES):
        # In the card's own frame: across (the viewer's left is positive), depth towards the viewer, height.
        frame = lambda places: np.stack([places[:, 0] * ahead_y - places[:, 1] * ahead_x, places[:, 0] * ahead_x + places[:, 1] * ahead_y, places[:, 2]], 1)
        mine = shining & (faced == side) if toward is not None else shining if side == 0 else np.zeros_like(shining)
        if not mine.any():
            continue
        spots = frame(where[mine]); colours = lit[mine]; order = np.argsort(spots[:, 1]); spots, colours = spots[order], colours[order]
        if toward is not None:  # how far out the model reaches at each spot of this view, to tell what it hides
            whole = frame(where[covered]); base = whole.min(0); span = np.ceil((whole.max(0) - base) * scale).astype(int) + 1
            pixel = lambda places: (np.clip(((places[:, 2] - base[2]) * scale).astype(int), 0, span[2] - 1), np.clip(((places[:, 0] - base[0]) * scale).astype(int), 0, span[0] - 1))
            outermost = np.full((span[2], span[0]), -np.inf); np.maximum.at(outermost, pixel(whole), whole[:, 1])
        for layer in np.split(np.arange(len(spots)), np.flatnonzero(np.diff(spots[:, 1]) > apart) + 1):
            layer = layer[np.argsort(spots[layer, 0])]
            for patch in np.split(layer, np.flatnonzero(np.diff(spots[layer, 0]) > 2 * pad) + 1) if toward is not None else [layer]:
                low, high = spots[patch].min(0) - pad, spots[patch].max(0) + pad
                wide, tall = int(np.ceil((high[0] - low[0]) * scale)), int(np.ceil((high[2] - low[2]) * scale))
                picture = np.zeros((tall, wide, 3))
                rows = np.clip(((high[2] - spots[patch, 2]) * scale).astype(int), 0, tall - 1)
                columns = np.clip(((high[0] - spots[patch, 0]) * scale).astype(int), 0, wide - 1)
                np.maximum.at(picture, (rows, columns), colours[patch])
                if toward is not None:
                    hidden = outermost[pixel(spots[patch])] > spots[patch, 1].max() + clear
                    if (picture.max(-1) > 0).sum() < least * scale ** 2 or hidden.mean() > 0.5:
                        continue
                sharp = Image.fromarray((picture * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))  # close the gaps between texels
                source = np.asarray(sharp.filter(ImageFilter.GaussianBlur(1)), float).max(-1, keepdims=True) / 255
                spread = np.asarray(sharp.filter(ImageFilter.GaussianBlur(reach * scale / 2)), float) * strength * (1 - core * source)
                pictures.append(spread.round().astype(np.uint8)); frames.append((low, high, float(spots[patch, 1].max()) + 0.04, (ahead_x, ahead_y)))
                light.append((np.asarray(sharp).max(-1) > 0) / scale ** 2)
    if not pictures:
        return None
    sheet = np.zeros((sum(len(picture) for picture in pictures), max(picture.shape[1] for picture in pictures), 3), np.uint8)
    cards, top = [], 0
    for picture, (low, high, front, (ahead_x, ahead_y)) in zip(pictures, frames):
        tall, wide = picture.shape[:2]; sheet[top:top + tall, :wide] = picture
        left, right, upper, lower = 0.0, wide / sheet.shape[1], top / len(sheet), (top + tall) / len(sheet)
        place = lambda across, height: (float(across * ahead_y + front * ahead_x), float(front * ahead_y - across * ahead_x), float(height))
        cards.append([(place(high[0], low[2]), (left, lower)), (place(low[0], low[2]), (right, lower)),
                      (place(low[0], high[2]), (right, upper)), (place(high[0], high[2]), (left, upper))])
        top += tall
    return Halo(Image.fromarray(sheet), cards, light)


def card_normal(card):
    """The way a halo card faces, from its corners."""
    first, second, third = (np.array(place, float) for place, _ in card[:3]); out = np.cross(second - first, third - first)
    return out / np.linalg.norm(out)
