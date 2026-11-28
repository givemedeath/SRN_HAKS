"""Pictures drawn again in code, region by region, where a texture is an atlas too small to redraw (user, 2026-11-26:
Modern Interior's hanging banners "need to be redrawn too"; `tfb01_flood` is 32 pixels).

Each picture is written upright (top row first, as the game shows it) to `<folder>/<name>.png`, with no record: the
folder is a material spec's `--redrawn`, whose pictures without a record are taken as placed by hand. A region is
[left, top, right, bottom] in 0-1 of the picture as the game shows it (v = 1 - top)."""
from pathlib import Path

import numpy as np

from . import material


def _scan(masters, name, width, height, tone, repeat=1):
    """A scan's colour cut to `width` x `height`, its mean colour moved to `tone`."""
    from PIL import Image
    colour = material.master(Path(masters) / name)['colour']
    tiles = np.tile(colour, (repeat, repeat, 1)) if repeat > 1 else colour
    sized = np.asarray(Image.fromarray(np.ascontiguousarray(tiles[..., :3])).resize((width, height), Image.LANCZOS)).astype(np.float64)
    mean = sized.reshape(-1, 3).mean(axis=0)
    return np.clip(sized * (np.asarray(tone, np.float64) / np.maximum(mean, 1)), 0, 255)


def _box(picture, region):
    height, width = picture.shape[:2]; left, top, right, bottom = region
    return slice(round(top * height), round(bottom * height)), slice(round(left * width), round(right * width))


def banner(width, height, cloth, *, tall=2.44, wide=0.97):
    """A hung cloth banner drawn for a mesh `wide` x `tall` metres whose picture region is `width` x `height` pixels:
    drawn at the cloth's own proportions, then squeezed into the region so the tile stretches it back. A hem stripe
    along its sides and top, and an invented emblem (a hexagon about a crescent: a place to sleep) on dark cloth."""
    from PIL import Image, ImageDraw
    full = max(height, round(width * tall / wide))
    base = Image.fromarray(np.uint8(cloth)).resize((width, full), Image.LANCZOS)
    draw = ImageDraw.Draw(base, 'RGBA'); hem = max(3, width // 40); amber = (196, 140, 58, 255); teal = (72, 190, 196, 255)
    draw.rectangle([0, 0, width, hem * 3], fill=(34, 34, 38, 255))
    for x in (hem, width - 2 * hem):
        draw.rectangle([x, 0, x + hem - 1, full], fill=amber)
    draw.rectangle([0, hem * 3, width, hem * 4], fill=amber)
    middle = (width / 2, full * 0.42); radius = width * 0.30
    corners = [(middle[0] + radius * np.cos(np.pi / 6 + k * np.pi / 3), middle[1] + radius * np.sin(np.pi / 6 + k * np.pi / 3)) for k in range(6)]
    draw.polygon(corners, outline=teal, width=max(4, width // 45))
    moon = radius * 0.55
    draw.ellipse([middle[0] - moon, middle[1] - moon, middle[0] + moon, middle[1] + moon], fill=teal)
    draw.ellipse([middle[0] - moon * 0.55, middle[1] - moon * 1.05, middle[0] + moon * 1.25, middle[1] + moon * 0.75], fill=tuple(int(v) for v in np.asarray(cloth).reshape(-1, 3).mean(0)) + (255,))
    for k in range(3):  # three bars under the emblem, as a hotel's floors
        y = full * 0.62 + k * full * 0.045
        draw.rectangle([width * 0.28, y, width * 0.72, y + full * 0.018], fill=teal if k == 0 else amber)
    return np.asarray(base.resize((width, height), Image.LANCZOS)).astype(np.float64)


def screen(width, height):
    """A small device's face: a dark bezel round a lit display of a few bars and lines (2070s, no real brand)."""
    face = np.full((height, width, 3), 22.0); inset = max(2, min(width, height) // 10)
    face[inset:-inset, inset:-inset] = (18, 52, 70)
    rows = np.arange(height - 2 * inset)[:, None]; columns = np.arange(width - 2 * inset)[None, :]
    lit = face[inset:-inset, inset:-inset]
    for k, share in enumerate((0.7, 0.45, 0.85, 0.3)):
        top = int((0.15 + k * 0.2) * lit.shape[0]); band = (rows >= top) & (rows < top + max(1, lit.shape[0] // 14)) & (columns < share * lit.shape[1])
        lit[np.broadcast_to(band, lit.shape[:2])] = (90, 210, 220) if k % 2 == 0 else (220, 170, 80)
    return face


def flood(masters, size=512):
    """`tfb01_flood`, drawn again: the banner (top), a small device's face and a strip of wood (middle), and the cork
    of the tables and beds below (bottom half), each where the tiles' UVs take it."""
    picture = np.zeros((size, size, 3))
    regions = {'banner': (0.0, 0.0, 1.0, 0.28), 'device': (0.0, 0.28, 0.5, 0.5), 'wood': (0.5, 0.28, 1.0, 0.5), 'cork': (0.0, 0.5, 1.0, 1.0)}
    rows, columns = _box(picture, regions['banner']); h, w = rows.stop - rows.start, columns.stop - columns.start
    cloth = _scan(masters, 'Fabric026', w, round(w * 2.44 / 0.97), (40, 42, 48), repeat=2)
    picture[rows, columns] = banner(w, h, cloth)
    rows, columns = _box(picture, regions['device']); picture[rows, columns] = screen(columns.stop - columns.start, rows.stop - rows.start)
    rows, columns = _box(picture, regions['wood']); picture[rows, columns] = _scan(masters, 'WoodFloor051', columns.stop - columns.start, rows.stop - rows.start, (96, 60, 36))
    rows, columns = _box(picture, regions['cork']); picture[rows, columns] = _scan(masters, 'Fabric026', columns.stop - columns.start, rows.stop - rows.start, (150, 112, 72), repeat=2)
    return np.uint8(np.clip(picture, 0, 255) + 0.5)


def reflection(size=256):
    """srx02's one reflection picture (the set's EnvMap, user 2026-11-27: "Do it"): a lit modern room as a mirror ball
    sees it, in place of the families' crypt, cloud and earth maps. Pale walls round the middle, a ceiling of bright
    light strips above, a darker floor below, the rim dim (what lies behind), softened so no strip reads as a hard
    shape on a polished floor. Upright, top row first."""
    from PIL import Image, ImageFilter
    y, x = (np.mgrid[0:size, 0:size] + 0.5) / size * 2 - 1  # -1..1, y down
    picture = np.empty((size, size, 3)); picture[:] = (150, 148, 142)  # walls: warm pale grey
    ceiling, floor = y < -0.25, y > 0.3
    picture[ceiling] = (176, 176, 172); picture[floor] = (84, 78, 72)
    for row in (-0.85, -0.62, -0.42):  # light strips across the ceiling, wider toward the middle
        reach = 0.75 - abs(row + 0.62) * 0.4
        picture[(abs(y - row) < 0.035) & (abs(x) < reach)] = (252, 250, 240)
    rim = np.clip((np.hypot(x, y) - 0.75) / 0.35, 0, 1)[..., None]
    picture = picture * (1 - 0.65 * rim)
    made = Image.fromarray(np.uint8(np.clip(picture, 0, 255) + 0.5)).filter(ImageFilter.GaussianBlur(size / 96))
    return np.asarray(made)


PICTURES = {'tfb01_flood': flood}
REFLECTIONS = {'srn_t_srx02/srx02__ref01.tga': reflection}  # pack files written as they ship (`reflections`)


def reflections(repo, check=False):
    """Write each drawn reflection picture to its pack file, or with `check` tell those whose file differs. [paths]."""
    from io import BytesIO
    from PIL import Image
    told = []
    for path, made in REFLECTIONS.items():
        out = BytesIO(); Image.fromarray(made()).save(out, format='TGA'); target = Path(repo) / path
        if not target.is_file() or target.read_bytes() != out.getvalue():
            told.append(path)
            if not check:
                target.write_bytes(out.getvalue())
    return told


def write(masters, folder):
    """Write every drawn picture into `folder` (a material spec's --redrawn). [file names]."""
    from PIL import Image
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); told = []
    for name, made in PICTURES.items():
        Image.fromarray(made(masters)).save(folder / f'{name}.png'); told.append(f'{name}.png')
    return told
