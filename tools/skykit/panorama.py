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

HALF = (4096, 512)  # texels of each half of the strip: 8192 round the horizon
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


def cut(rgb, key):
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


def lights(rgba):
    """Light mask of a strip: R lit windows and neon, G red beacons; 0..1, nothing where there is no land."""
    rgb, alpha = rgba[..., :3], rgba[..., 3]
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    local = _blur(lum, 5)
    peak = rgb.max(-1)
    sat = (peak - rgb.min(-1)) / np.maximum(peak, 1e-3)
    brighter = np.clip((lum - local - 0.03) / 0.18, 0, 1)
    windows = np.maximum(brighter * np.clip((lum - 0.32) / 0.25, 0, 1),
                         np.clip((peak - 0.7) / 0.2, 0, 1) * np.clip((sat - 0.45) / 0.25, 0, 1))
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    red = np.clip((r - 0.7) / 0.2, 0, 1) * np.clip((r - np.maximum(g, b) - 0.35) / 0.2, 0, 1)
    # a beacon is a small red point: keep red pixels brighter than their red neighbourhood
    beacons = red * np.clip((red - _blur(red, 4) * 1.5) / 0.3, 0, 1)
    beacons = np.maximum(beacons, _blur(beacons, 1.0) * 1.6).clip(0, 1)
    mask = np.zeros_like(rgb)
    mask[..., 0] = windows * alpha
    mask[..., 1] = beacons * alpha
    return mask


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
