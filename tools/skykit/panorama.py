"""Land panoramas for the dynamic skies: keyed source views -> one 360-degree strip -> two texture halves and light masks.

A source view is a generated picture whose sky is a flat chroma key (green or magenta). Its land is cut out with a
soft edge, the views are joined round the horizon (a view may be mirrored so a single view still wraps without a
seam), and the strip is resampled into two halves of `HALF` texels, each with a light mask: R marks lit windows and
neon (the shader dims them by day and lets them flicker at night), G marks the red aircraft-warning beacons on tower
tops (the shader blinks them).
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HALF = (8192, 512)  # texels of each half of the strip: 16384 round the horizon (half_size picks the height)
EDGE_ROWS = 20  # rows (at source scale) under a green-keyed silhouette cleared of key tint
KEYS = {'green': (0.0, 1.0, 0.0), 'magenta': (1.0, 0.0, 1.0)}


def load(path):
    return np.asarray(Image.open(path).convert('RGB'), np.float32) / 255


def keyness(rgb, key):
    """How strongly each pixel is the chroma key, 0..1."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    if key == 'green':
        return np.clip(g - np.maximum(r, b), 0, 1)
    if key == 'magenta':
        return np.clip(np.minimum(r, b) - g, 0, 1)
    raise ValueError(f'unknown key {key}')


def cut(rgb, key, scale=1):
    """RGBA of a keyed view: alpha from the key with a soft one-texel edge, key spill removed from the edge colours.

    Everything above the highest land in each column is sky, so specks of key colour inside the land (a green
    window, a magenta sign) stay opaque, and specks of land floating in the sky are dropped."""
    k = keyness(rgb, key)
    alpha = 1 - np.clip((k - 0.18) / 0.32, 0, 1)
    solid = alpha > 0.5
    height = solid.shape[0]
    # the land starts at the first run of four solid rows from the top of each column
    run = solid[:-3] & solid[1:-2] & solid[2:-1] & solid[3:]
    first = np.where(run.any(0), run.argmax(0), height)
    rows = np.arange(height)[:, None]
    alpha = np.where(rows > first[None, :], 1.0, np.where(rows < first[None, :] - 1, 0.0, alpha))
    out = rgb.copy()
    spill = k[..., None] * 1.0
    if key == 'green':
        out[..., 1] = np.minimum(out[..., 1], np.maximum(out[..., 0], out[..., 2]) + (1 - spill[..., 0]) * 0.08)
        # hazy far hills just under the silhouette can come back tinted by the key (green, or cyan once green is held
        # to blue): there, green stays at most a little above red, which keeps snow, violet and orange as they are
        near = (rows >= first[None, :] - 1) & (rows < first[None, :] + EDGE_ROWS * scale)
        out[..., 1] = np.where(near, np.minimum(out[..., 1], out[..., 0] + 0.06), out[..., 1])
    else:
        limit = out[..., 1] + (1 - spill[..., 0]) * 0.08
        out[..., 0] = np.minimum(out[..., 0], np.maximum(limit, out[..., 0] * (1 - spill[..., 0])))
        out[..., 2] = np.minimum(out[..., 2], np.maximum(limit, out[..., 2] * (1 - spill[..., 0])))
    return np.dstack([out, alpha]).astype(np.float32)


def land_rows(rgba, margin=6):
    """(first, last) rows holding land, with a small margin of sky above."""
    rows = np.nonzero(rgba[..., 3].max(1) > 0.02)[0]
    if not len(rows):
        raise ValueError('the view holds no land')
    return max(int(rows[0]) - margin, 0), int(rgba.shape[0])


def strip(views):
    """Join (rgba, mirrored) views left to right into one strip; all views share the land rows of the tallest."""
    tops = [land_rows(rgba)[0] for rgba, _ in views]
    top = min(tops)
    heights = {rgba.shape[0] for rgba, _ in views}
    if len(heights) != 1:
        raise ValueError('views of one strip must share a height')
    parts = [(rgba[:, ::-1] if mirrored else rgba)[top:] for rgba, mirrored in views]
    return np.concatenate(parts, axis=1)


def _blur(channel, radius):
    image = Image.fromarray(np.clip(channel * 255, 0, 255).astype(np.uint8))
    return np.asarray(image.filter(ImageFilter.GaussianBlur(radius)), np.float32) / 255


SHARPEN = (2.0, 70, 2)  # unsharp mask after the upscale: radius (texels), percent, threshold (levels)


def sharpen(rgb, settings=SHARPEN):
    """An unsharp mask over the upscaled picture: the upscaler keeps edges but softens what lies between them. The
    picture's ends are padded with each other so the wrap stays seamless."""
    pad = 16
    wrapped = np.concatenate([rgb[:, -pad:], rgb, rgb[:, :pad]], axis=1)
    image = Image.fromarray(np.clip(wrapped * 255 + 0.5, 0, 255).astype(np.uint8))
    radius, percent, threshold = settings
    out = np.asarray(image.filter(ImageFilter.UnsharpMask(radius, percent, threshold)), np.float32) / 255
    return out[:, pad:-pad]


def _blur_rows(channel, radius):
    """Mean over `radius` columns either side, along each row only."""
    radius = int(round(radius))
    padded = np.pad(channel, ((0, 0), (radius + 1, radius)), mode='edge')
    sums = np.cumsum(padded, axis=1)
    return (sums[:, 2 * radius + 1:] - sums[:, :-2 * radius - 1]) / (2 * radius + 1)


def lights(rgba, city_from=0.0, scale=1):
    """Light mask of a strip: R lit windows and neon, G red beacons; 0..1, nothing where there is no land.

    Only rows below `city_from` (a share of the strip's height) hold city: above it, sunlit snow and rim light on the
    mountains would read as windows. `scale` is the strip's texels per source pixel; the filters' radii follow it."""
    rgb, alpha = rgba[..., :3], rgba[..., 3]
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    local = _blur(lum, 5 * scale)
    peak = rgb.max(-1)
    sat = (peak - rgb.min(-1)) / np.maximum(peak, 1e-3)
    brighter = np.clip((lum - local - 0.03) / 0.18, 0, 1)
    windows = np.maximum(brighter * np.clip((lum - 0.32) / 0.25, 0, 1),
                         np.clip((peak - 0.7) / 0.2, 0, 1) * np.clip((sat - 0.45) / 0.25, 0, 1))
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    red = np.clip((r - 0.7) / 0.2, 0, 1) * np.clip((r - np.maximum(g, b) - 0.35) / 0.2, 0, 1)
    # a beacon is a small red point: keep red pixels brighter than their red neighbourhood
    beacons = red * np.clip((red - _blur(red, 4 * scale) * 1.5) / 0.3, 0, 1)
    # a red light trail is a line, not a point: drop red that runs on along its row
    beacons *= np.clip((red - _blur_rows(red, 8 * scale) * 1.3) / 0.3, 0, 1)
    beacons = np.maximum(beacons, _blur(beacons, 1.0 * scale) * 1.6).clip(0, 1)
    city = (np.arange(rgb.shape[0]) >= city_from * rgb.shape[0]).astype(np.float32)[:, None]
    mask = np.zeros_like(rgb)
    mask[..., 0] = windows * alpha * city
    mask[..., 1] = beacons * alpha * city
    return mask


def half_size(band):
    """Each half's texels: HALF's width, and the power of two nearest the height that gives the band as many texels
    per degree up as round. Without anisotropic filtering the GPU picks a mip from the denser direction, so a band
    packed denser up than round blurs its detail sideways too."""
    rows = HALF[0] * 2 * (band[1] - band[0]) / 360.0
    return (HALF[0], int(np.clip(2 ** round(np.log2(max(rows, 1.0))), 256, 2048)))


def halves(rgba, mask, size=HALF):
    """Resample the strip to two halves of `size`; returns [(rgba, mask), (rgba, mask)] as float arrays, rows from the
    strip's top. The strip's rows are stretched to the halves' height; the shader maps them to the band's elevations."""
    width, height = size

    def resample(array, mode):
        out = []
        for c in range(array.shape[2]):
            image = Image.fromarray(array[..., c].astype(np.float32), 'F')
            out.append(np.asarray(image.resize((width * 2, height), mode), np.float32))
        return np.dstack(out).clip(0, 1)

    big_rgba = resample(rgba, Image.LANCZOS)
    big_mask = resample(mask, Image.BILINEAR)
    # colour under fully transparent sky follows the nearest land colour so filtering never pulls in key colour
    big_rgba[..., :3] = bleed(big_rgba[..., :3], big_rgba[..., 3])
    return [(big_rgba[:, :width], big_mask[:, :width]), (big_rgba[:, width:], big_mask[:, width:])]


def bleed(rgb, alpha):
    """Copy each column's top land colour up into its sky, so mip filtering at the silhouette stays land-coloured."""
    out = rgb.copy()
    solid = alpha > 0.5
    first = np.where(solid.any(0), solid.argmax(0), rgb.shape[0] - 1)
    rows = np.arange(rgb.shape[0])[:, None]
    above = rows < first[None, :]
    edge = out[first, np.arange(rgb.shape[1])]
    out[above] = np.broadcast_to(edge[None, :, :], out.shape)[above]
    return out


def band_degrees(strip_rgba, below, stretch):
    """(bottom, top) elevations in degrees of a strip laid round 360 degrees: square texels scaled by `stretch`
    vertically, the strip's bottom `below` degrees under the horizon."""
    height, width = strip_rgba.shape[:2]
    span = height * 360.0 / width * stretch
    return -below, span - below


def roof_degrees(mask, band, share=0.15):
    """Elevation in degrees of the city's rooftops in a strip laid over `band`: the row above which `share` of the
    window light lies. Searchlights rise from there. The band's bottom when the strip holds no city."""
    rows = mask[..., 0].sum(1)
    if rows.sum() <= 1e-6:
        return band[0]
    row = int(np.searchsorted(np.cumsum(rows) / rows.sum(), share))
    return band[1] - (row + 0.5) / len(rows) * (band[1] - band[0])


def tga(array):
    """Uncompressed TGA bytes of float rows (top row first); RGB or RGBA."""
    data = np.clip(np.asarray(array) * 255 + 0.5, 0, 255).astype(np.uint8)
    height, width, channels = data.shape
    header = bytes([0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, width & 255, width >> 8, height & 255, height >> 8, channels * 8,
                    8 if channels == 4 else 0])
    bgr = data[::-1][..., [2, 1, 0, 3][:channels]]  # TGA rows run up from the bottom
    return header + bgr.tobytes()


def save_png(array, path):
    data = np.clip(np.asarray(array) * 255 + 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(data, 'RGBA' if data.shape[2] == 4 else 'RGB').save(Path(path))


# Joins: neighbouring views are drawn apart, so their ends do not meet. A join picture is redrawn (by the same image
# model) from `join_input`: the last JOIN_KEEP columns of the left view, a blend of the two across JOIN_GAP columns,
# and the first JOIN_KEEP columns of the right view. `assemble` keeps the redrawn middle and feathers it into both views.
VIEW = (1248, 832)       # every view is resized to this before joining
JOIN_KEEP, JOIN_GAP, JOIN_FEATHER = 500, 248, 64
JOIN_TRIM = 100          # columns of a join's kept ends that are trusted to the views rather than to the redraw
# A panorama's joins are drawn for one layout and assembled with it: (keep, gap, feather, trim).
LAYOUT = (JOIN_KEEP, JOIN_GAP, JOIN_FEATHER, JOIN_TRIM)
WIDE = (400, 448, 128, 150)  # a wider repainted middle and longer blends, for views that differ more


def view_rgb(path):
    """A source view as float RGB at VIEW size."""
    return np.asarray(Image.open(path).convert('RGB').resize(VIEW, Image.LANCZOS), np.float32) / 255


def join_input(left, right, layout=LAYOUT):
    """The picture a join is redrawn from: left's end, a crossfade, right's start (float RGB, VIEW size)."""
    keep, gap_width = layout[0], layout[1]
    a, b = left[:, -keep:], right[:, :keep]
    t = np.linspace(0, 1, gap_width, dtype=np.float32)[None, :, None]
    gap = a[:, -1:] * (1 - t) + b[:, :1] * t
    return np.concatenate([a, gap, b], axis=1)


SEAM_MARGIN, SEAM_SOFT = 64, 5.0  # columns kept clear of an overlap's ends; half-width of the blend along a cut
SEAM_LEVELS = 7  # pyramid levels of the blend: fine detail switches at the cut, broad colour over up to 2**7 times wider


def _resize(array, size, mode):
    return np.dstack([np.asarray(Image.fromarray(array[..., c], 'F').resize(size, mode), np.float32) for c in range(array.shape[2])])


def multiband(a, b, weight, levels=SEAM_LEVELS):
    """Blend a into b by `weight` (0 keeps a, 1 takes b) band by band (Burt and Adelson): each Laplacian band is mixed
    by the mask blurred to its own scale, so a difference of colour is spread wide while edges stay sharp."""
    ga, gb, gw = [a], [b], [weight]
    for _ in range(levels):
        h, w = ga[-1].shape[:2]
        size = (max(1, w // 2), max(1, h // 2))
        ga.append(_resize(ga[-1], size, Image.BOX)); gb.append(_resize(gb[-1], size, Image.BOX)); gw.append(_resize(gw[-1], size, Image.BOX))
    out = ga[-1] * (1 - gw[-1]) + gb[-1] * gw[-1]
    for level in range(levels - 1, -1, -1):
        h, w = ga[level].shape[:2]
        up = lambda x: _resize(x, (w, h), Image.BILINEAR)
        band_a = ga[level] - up(ga[level + 1]); band_b = gb[level] - up(gb[level + 1])
        out = up(out) + band_a * (1 - gw[level]) + band_b * gw[level]
    return np.clip(out, 0, 1)


def seam_path(a, b, margin=SEAM_MARGIN):
    """The column, row by row, where two overlapping pictures of the same columns agree best: a minimum-cost path from
    top to bottom that moves at most one column a row (image quilting), kept `margin` columns from either end."""
    cost = ((a - b) ** 2).sum(-1)
    cost = (cost + np.roll(cost, 1, 0) + np.roll(cost, -1, 0)) / 3  # a little vertical smoothing
    width = cost.shape[1]
    big = np.float32(1e9)
    cost[:, :margin] = big; cost[:, width - margin:] = big
    total = cost.copy(); back = np.zeros(cost.shape, np.int32)
    for row in range(1, cost.shape[0]):
        prev = total[row - 1]
        left = np.concatenate([[big], prev[:-1]]); right = np.concatenate([prev[1:], [big]])
        stack = np.stack([left, prev, right]); pick = stack.argmin(0)
        total[row] += stack[pick, np.arange(width)]; back[row] = pick - 1
    path = np.zeros(cost.shape[0], np.int32); path[-1] = int(total[-1].argmin())
    for row in range(cost.shape[0] - 1, 0, -1):
        path[row - 1] = path[row] + back[row, path[row]]
    return path


GRADE_ROWS = 24.0  # vertical smoothing (rows) of the grade measured in an overlap


def row_gain(reference, image, key):
    """Per-row, per-channel gain that grades `image` like `reference` where both show the same land (an overlap):
    the redraw model drifts the grade of the part it was told to keep, which shows as a jump at the cut."""
    land = ((keyness(reference, key) < 0.1) & (keyness(image, key) < 0.1)).astype(np.float32)[..., None]
    profile = lambda picture: (picture * land).sum(1)
    count = land.sum(1)
    rows = np.arange(len(count), dtype=np.float32)
    kernel = np.exp(-0.5 * ((rows[:, None] - rows[None, :]) / GRADE_ROWS) ** 2)
    smooth = lambda values: kernel @ values
    weight = smooth(count)
    a = smooth(profile(reference)) / np.maximum(weight, 1e-6)
    b = smooth(profile(image)) / np.maximum(weight, 1e-6)
    gain = np.clip((a + 0.02) / (b + 0.02), 0.6, 1.6)
    trust = np.clip(weight / (weight.max() * 0.05 + 1e-6), 0, 1)  # rows with almost no land keep their colours
    return 1 + (gain - 1) * trust


def apply_gain(image, gain, key):
    """`image` with a gain (rows x 3, or rows x columns x 3) on its land; the chroma key stays the key."""
    land = 1 - np.clip(keyness(image, key) * 3, 0, 1)[..., None]
    gain = gain[:, None, :] if gain.ndim == 2 else gain
    return np.clip(image * (1 + (gain - 1) * land), 0, 1).astype(np.float32)


def _place_join(canvas, start, join, left, right, keep, gap, key=None):
    """Lay a redrawn join into `canvas` from column `start` (wrapping round): it takes over from `left` and hands back
    to `right` along the seam paths through its two overlaps, blended band by band."""
    span, total = join.shape[1], canvas.shape[1]
    if key:  # grade the join like the left view at its left end and like the right view at its right end
        g0 = row_gain(left[:, -keep:], join[:, :keep], key)
        g1 = row_gain(right[:, :keep], join[:, keep + gap:], key)
        t = np.clip((np.arange(span, dtype=np.float32) - keep / 2) / (span - keep), 0, 1)[None, :, None]
        join = apply_gain(join, g0[:, None, :] * (1 - t) + g1[:, None, :] * t, key)
    columns = np.arange(span, dtype=np.float32)[None, :]
    enter = seam_path(left[:, -keep:], join[:, :keep]).astype(np.float32)[:, None]
    leave = (keep + gap + seam_path(join[:, keep + gap:], right[:, :keep])).astype(np.float32)[:, None]
    weight = (np.clip((columns - enter) / (2 * SEAM_SOFT) + 0.5, 0, 1) * np.clip((leave - columns) / (2 * SEAM_SOFT) + 0.5, 0, 1))[..., None]
    place = (start + np.arange(span)) % total
    canvas[:, place] = multiband(canvas[:, place], join, weight.astype(np.float32))


def assemble(views, joins, layout=LAYOUT, key=None):
    """One wrapped strip from views [v0..vn-1] and joins [j01, j12, .., j(n-1)0] (float RGB, VIEW size).

    Join column c < keep is the left view's column W - keep + c; column c >= keep + gap is the right view's column
    c - keep - gap. Views are laid every W + gap columns; each join covers its gap and overlaps both neighbours by
    `keep` columns, and within each overlap the strip switches from view to join (and back) along `seam_path`, so a
    repaint that drifted from the view it was meant to keep meets it where they agree, not at a fixed column."""
    height, width = views[0].shape[:2]
    keep, gap = layout[0], layout[1]
    step = width + gap
    canvas = np.zeros((height, step * len(views), 3), np.float32)
    for index, view in enumerate(views):
        canvas[:, index * step:index * step + width] = view
    for index, join in enumerate(joins):
        _place_join(canvas, index * step + width - keep, join, views[index], views[(index + 1) % len(views)], keep, gap, key)
    return canvas


# Chains: a panorama grown to the right from one start view. Each extension is redrawn from `extend_input` (the
# strip's last JOIN_KEEP columns, then a blurred placeholder), so it continues the strip at the strip's own scale and
# horizon; a closing join (from `join_input(strip, strip)`) then wraps the end back to the start.
def extend_input(strip, key, keep=JOIN_KEEP):
    """The VIEW-sized picture an extension is redrawn from: the strip's last `keep` columns, then a blurred mirror of
    them as a placeholder for the new land, with the sky above it the flat key."""
    width = VIEW[0]
    tail = strip[:, -keep:]
    rough = np.concatenate([tail[:, ::-1], tail] * 2, axis=1)[:, :width - keep]
    sky = keyness(rough, key) > 0.3
    fill = np.dstack([_blur(rough[..., c], 8) for c in range(3)])
    fill[sky] = KEYS[key]
    return np.concatenate([tail, fill], axis=1).astype(np.float32)


def _extend(strip, extension, keep, key=None):
    if key:  # grade the whole redraw like the strip it continues
        extension = apply_gain(extension, row_gain(strip[:, -keep:], extension[:, :keep], key), key)
    width = extension.shape[1]
    path = seam_path(strip[:, -keep:], extension[:, :keep]).astype(np.float32)[:, None]
    weight = np.clip((np.arange(width, dtype=np.float32)[None, :] - path) / (2 * SEAM_SOFT) + 0.5, 0, 1)[..., None]
    old = np.concatenate([strip[:, -keep:], extension[:, keep:]], axis=1)
    return np.concatenate([strip[:, :-keep], multiband(old, extension, weight.astype(np.float32))], axis=1)


def chain(start, extensions, close=None, keep=JOIN_KEEP, gap=JOIN_GAP, key=None):
    """One strip from a start view and its extensions (float RGB, VIEW size), wrapped by the closing join if given."""
    strip = start
    for extension in extensions:
        strip = _extend(strip, extension, keep, key)
    if close is None:
        return strip
    canvas = np.zeros((strip.shape[0], strip.shape[1] + gap, 3), np.float32)
    canvas[:, :strip.shape[1]] = strip
    _place_join(canvas, strip.shape[1] - keep, close, strip, strip, keep, gap, key)
    return canvas


def match_colours(image, reference, key, strength=0.75):
    """Shift `image`'s land colours toward `reference`'s (per-channel mean and spread of the land, sky key left alone):
    views drawn by different models then share one grade."""
    def land(rgb):
        return keyness(rgb, key) < 0.1
    src, ref = image[land(image)], reference[land(reference)]
    mean_s, std_s = src.mean(0), src.std(0) + 1e-4
    mean_r, std_r = ref.mean(0), ref.std(0) + 1e-4
    graded = (image - mean_s) / std_s * std_r + mean_r
    out = image + (graded - image) * strength
    mask = land(image)[..., None]
    return np.where(mask, np.clip(out, 0, 1), image).astype(np.float32)
