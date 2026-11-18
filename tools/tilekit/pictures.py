"""Reading the pictures a pack holds, and the few picture sums a restyle needs.

The game shows a pack's DDS copy of a texture before its TGA (plan, stratum 0), and the packs' DDS copies are BioWare
DDS, which no image library reads: `read` decodes them, so that what a texture looks like "before" is what the game
drew. Everything here is whole-picture arithmetic on arrays; nothing knows about tiles or packs."""
import struct
from pathlib import Path

import numpy as np

from . import require


def _colours(blocks):
    """The sixteen pixels of each DXT colour block: (count, 4, 4, 4) RGBA 0-255, blocks as (count, 8) bytes."""
    c0 = blocks[:, 0].astype(np.uint16) | blocks[:, 1].astype(np.uint16) << 8; c1 = blocks[:, 2].astype(np.uint16) | blocks[:, 3].astype(np.uint16) << 8

    def rgb(c):
        return np.stack([(c >> 11 & 31) * 255 // 31, (c >> 5 & 63) * 255 // 63, (c & 31) * 255 // 31], axis=1).astype(np.int32)
    a, b = rgb(c0), rgb(c1); four = (c0 > c1)[:, None]
    palette = np.stack([a, b, np.where(four, (2 * a + b) // 3, (a + b) // 2), np.where(four, (a + 2 * b) // 3, 0)], axis=1)  # (count, 4, 3)
    alpha = np.full((len(blocks), 4), 255, np.int32); alpha[:, 3] = np.where(four[:, 0], 255, 0)
    bits = blocks[:, 4:8].astype(np.uint32); code = bits[:, 0] | bits[:, 1] << 8 | bits[:, 2] << 16 | bits[:, 3] << 24
    index = (code[:, None] >> (2 * np.arange(16, dtype=np.uint32))[None, :] & 3).astype(np.intp)  # (count, 16), row by row
    rows = np.arange(len(blocks))[:, None]
    return np.concatenate([palette[rows, index], alpha[rows, index][..., None]], axis=2).reshape(len(blocks), 4, 4, 4)


def _alphas(blocks):
    """The sixteen alpha values of each DXT5 alpha block: (count, 4, 4), blocks as (count, 8) bytes."""
    a0, a1 = blocks[:, 0].astype(np.int32), blocks[:, 1].astype(np.int32); eight = (a0 > a1)[:, None]
    steps = np.arange(1, 7)[None, :]
    long = ((7 - steps) * a0[:, None] + steps * a1[:, None]) // 7; short = ((5 - steps) * a0[:, None] + steps * a1[:, None]) // 5
    short[:, 4], short[:, 5] = 0, 255
    palette = np.concatenate([a0[:, None], a1[:, None], np.where(eight, long, short)], axis=1)  # (count, 8)
    code = sum(blocks[:, 2 + byte].astype(np.uint64) << np.uint64(8 * byte) for byte in range(6))
    index = (code[:, None] >> (np.uint64(3) * np.arange(16, dtype=np.uint64))[None, :] & np.uint64(7)).astype(np.intp)
    return palette[np.arange(len(blocks))[:, None], index].reshape(len(blocks), 4, 4)


def decode_dxt(data, width, height, alpha):
    """RGBA pixels (height, width, 4) of one DXT1 (`alpha` false) or DXT5 level, top row first as stored."""
    across, down = -(-width // 4), -(-height // 4); size = 16 if alpha else 8
    require(len(data) >= across * down * size, 'A compressed picture is shorter than its size says')
    blocks = np.frombuffer(data, np.uint8, across * down * size).reshape(across * down, size)
    pixels = _colours(blocks[:, size - 8:])
    if alpha:
        pixels[..., 3] = _alphas(blocks[:, :8])
    whole = pixels.reshape(down, across, 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(down * 4, across * 4, 4)
    return whole[:height, :width].astype(np.uint8)


def read(path):
    """A pack's picture as a PIL image, RGB or RGBA: a TGA or a standard DDS through the image library, a BioWare DDS
    (width, height, channels, size, alpha, then its largest level) decoded here. Top row first, whatever the file."""
    from PIL import Image
    path = Path(path); data = path.read_bytes()
    if path.suffix.lower() == '.dds' and data[:4] != b'DDS ':
        require(len(data) > 20, f'{path.name} is no picture')
        width, height, channels = struct.unpack_from('<III', data, 0)
        require(channels in (3, 4) and 0 < width <= 8192 and 0 < height <= 8192, f'{path.name} is no BioWare DDS')
        # A BioWare DDS holds its bottom row first: against the TGA copy of `sidewalk10` the rows as stored differed by
        # 13 in 255 on average and turned over by 2.5, the compression's own loss (2026-11-18).
        pixels = np.ascontiguousarray(decode_dxt(data[20:], width, height, channels == 4)[::-1])
        return Image.fromarray(pixels, 'RGBA') if channels == 4 else Image.fromarray(pixels[..., :3], 'RGB')
    with Image.open(path) as picture:
        return picture.convert('RGBA' if picture.mode in ('RGBA', 'LA', 'P') and 'A' in picture.convert('RGBA').getbands() and picture.convert('RGBA').getextrema()[3][0] < 255 else 'RGB')


def levels(path):
    """How many levels a standard DDS file states (its mip chain, the largest counted)."""
    data = Path(path).read_bytes()[:32]
    require(data[:4] == b'DDS ' and len(data) == 32, f'{Path(path).name} is no standard DDS')
    return max(struct.unpack_from('<I', data, 28)[0], 1)


def whole_chain(width, height):
    """The levels of a whole mip chain: down to one pixel on the longer side."""
    return max(width, height).bit_length()


def _wrapped_blur(values, radius):
    """A box blur that wraps at the edges, so a tiling picture stays one."""
    if radius < 1:
        return values
    out = values.astype(np.float64)
    for axis in (0, 1):
        total = np.zeros_like(out)
        for shift in range(-radius, radius + 1):
            total += np.roll(out, shift, axis=axis)
        out = total / (2 * radius + 1)
    return out


def relief(height, strength=2.0, *, wrap=True):
    """A normal map (uint8 RGB, +Y up the picture as the game reads one) from a height picture 0-1, lighter being
    higher. `strength` is how many pixels of rise full white stands over black; `wrap` treats the picture as tiling."""
    height = np.asarray(height, np.float64)
    if wrap:
        dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) / 2; dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) / 2
    else:
        dy, dx = np.gradient(height)
    normal = np.dstack([-dx * strength, dy * strength, np.ones_like(height)])  # rows run down the picture: up is -row
    normal /= np.linalg.norm(normal, axis=2, keepdims=True)
    return np.uint8(np.clip(normal * 0.5 + 0.5, 0, 1) * 255 + 0.5)


def height_of(colour, *, detail=2, broad=24):
    """A height picture 0-1 guessed from a colour picture: its brightness with the broad light and shade taken out, so
    that mortar lines and cracks sink and nothing leans with a stain. For a picture that came with no relief of its own."""
    grey = np.asarray(colour, np.float64)[..., :3] @ np.array([0.2126, 0.7152, 0.0722]) / 255
    fine = _wrapped_blur(grey, detail // 2) - _wrapped_blur(grey, broad)
    spread = max(float(np.percentile(np.abs(fine), 99)), 1e-6)
    return np.clip(fine / spread * 0.5 + 0.5, 0, 1)


def toned(colour, like, amount=1.0):
    """`colour` (uint8 RGB array) with its mean colour moved `amount` of the way to that of the picture `like`, its
    light and dark kept: how a master takes the place of a texture without the district changing colour."""
    colour = np.asarray(colour, np.float64)[..., :3]; target = np.asarray(like, np.float64)[..., :3].reshape(-1, 3).mean(axis=0)
    mean = colour.reshape(-1, 3).mean(axis=0)
    scale = 1 + (target / np.maximum(mean, 1) - 1) * amount
    return np.uint8(np.clip(colour * scale, 0, 255) + 0.5)


def graded(colour, grade):
    """`colour` (uint8 RGB array) as a district's grade leaves it. grade: {saturation (1 keeps it, 0 is grey), contrast
    (about the picture's own mean brightness, 1 keeps it), gain (brightness, 1 keeps it), tint ([red, green, blue]
    multipliers), paint (0-1: how far what is painted on the surface, a lane line or a kerb mark, is spared the grade;
    paint is what stands well above the picture's middle brightness or is strongly coloured)}, each optional. Nothing
    here depends on where in the picture a pixel is, so a tiling picture still tiles and no stain is added to read as a
    repeat."""
    unknown = set(grade) - {'saturation', 'contrast', 'gain', 'tint', 'paint'}; require(not unknown, 'A grade has no ' + ', '.join(sorted(unknown)))
    values = np.asarray(colour, np.float64)[..., :3]
    if grade.get('paint'):
        plain = graded(colour, {key: value for key, value in grade.items() if key != 'paint'}).astype(np.float64)
        light = values @ np.array([0.2126, 0.7152, 0.0722]); chroma = values.max(axis=2) - values.min(axis=2)
        painted = np.maximum(np.clip((light - np.median(light) - 25) / 25, 0, 1), np.clip((chroma - 50) / 30, 0, 1))[..., None] * float(grade['paint'])
        return np.uint8(plain * (1 - painted) + values * painted + 0.5)
    grey = (values @ np.array([0.2126, 0.7152, 0.0722]))[..., None]
    values = grey + (values - grey) * float(grade.get('saturation', 1.0))
    middle = float(grey.mean()); values = middle + (values - middle) * float(grade.get('contrast', 1.0))
    tint = np.asarray(grade.get('tint', (1.0, 1.0, 1.0)), np.float64); require(tint.shape == (3,), 'A grade\'s tint is red, green and blue')
    return np.uint8(np.clip(values * float(grade.get('gain', 1.0)) * tint, 0, 255) + 0.5)


def offset_seams(colour):
    """How much a picture jumps where it wraps, against how much it changes from pixel to pixel within: about 1 for a
    picture that tiles, far above for one that does not. Left to right, then top to bottom."""
    grey = np.asarray(colour, np.float64)[..., :3].mean(axis=2)
    within = (np.abs(np.diff(grey, axis=1)).mean() + 1e-6, np.abs(np.diff(grey, axis=0)).mean() + 1e-6)
    return (float(np.abs(grey[:, 0] - grey[:, -1]).mean() / within[0]), float(np.abs(grey[0] - grey[-1]).mean() / within[1]))
