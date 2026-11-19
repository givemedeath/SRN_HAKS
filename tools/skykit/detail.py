"""Tile detail pass: a land strip redrawn in overlapping close-ups by the local Qwen-Image 2.1 edit profile on the shared
ComfyUI, then blended back into one wrapped strip at about 2.8 times the source size.

The upscaler can only sharpen what the source draws; the land of a generated view is a band a few hundred pixels tall.
Each tile here is that band's full height (plus a strip of key above it) and a width of 1.5 times that, shown to the
model at about 1248 x 832 to redraw with fine detail and the same composition (the panorama's `detail_prompt`). Tiles are tracked art
(`art/<set>/detail/tile_NN.png`, with `detail.json` naming the input they were drawn from); the build blends them:
graded like the input, cut where neighbours agree and blended band by band.

  python -m tools.skykit.detail den [--tiles 0,4] [--seed 51] [--redo]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = 'tools.skykit'

from . import panorama
from .upscale import comfy_url, run_graph

ART = Path(__file__).resolve().parent / 'art'
PAD_TOP = 32       # rows of key laid over the land so the model sees the silhouette against sky
ASPECT = 1.5       # tile width over height, the model's 1248 x 832
OVERLAP = 0.25     # share of a tile its neighbour also covers
SUBFOLDER = 'headkit-design/skykit'
MAX_SHIFT = 32     # texels (at the tiles' scale) a redraw may have drifted; the largest seen is 10


def layout(land):
    """(tile width, tile starts, padded height) of a 1x land strip (rows x columns x 3, key above the land)."""
    height = land.shape[0] + PAD_TOP
    width = int(round(height * ASPECT))
    count = int(np.ceil(land.shape[1] / (width * (1 - OVERLAP))))
    starts = [int(round(i * land.shape[1] / count)) for i in range(count)]
    return width, starts, height


def tile_input(land, key, index):
    width, starts, height = layout(land)
    columns = (starts[index] + np.arange(width)) % land.shape[1]
    pad = np.broadcast_to(np.array(panorama.KEYS[key], np.float32), (PAD_TOP, width, 3))
    return np.concatenate([pad, land[:, columns]], axis=0)


def digest(land):
    return hashlib.sha256(np.ascontiguousarray(land, np.float32).tobytes()).hexdigest()


def generate(land, key, folder, prompt_file, seed, tiles=None, redo=False, url=None):
    """Redraw the tiles of `land` into `folder` (tile_NN.png), skipping those already there unless `redo`."""
    from tools.headkit import design
    folder.mkdir(parents=True, exist_ok=True)
    width, starts, height = layout(land)
    prompt = Path(prompt_file).read_text(encoding='utf-8')
    record = {'inputSha256': digest(land), 'tileWidth': width, 'starts': starts, 'height': height, 'padTop': PAD_TOP,
              'seed': seed, 'profile': 'qwen21-int8-v1', 'promptSha256': hashlib.sha256(prompt.encode()).hexdigest()}
    url = comfy_url(url)
    drawn = set()
    for index in (tiles if tiles is not None else range(len(starts))):
        target = folder / f'tile_{index:02d}.png'
        if target.is_file() and not redo:
            continue
        drawn.add(index)
        name = f'{folder.parent.name}-detail-{index:02d}'
        graph = lambda image, prefix: design.compile_design(prompt, [image], seed + index, 1, prefix, profile='qwen21-int8-v1')
        out = run_graph(url, tile_input(land, key, index), name, graph, timeout=1800, subfolder=SUBFOLDER, output='9')
        Image.fromarray(np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8)).save(target)
        print(f'tile {index:02d} of {len(starts)}: {target.name}', flush=True)
    missing = [i for i in range(len(starts)) if not (folder / f'tile_{i:02d}.png').is_file()]
    if missing:  # the build takes the tiles once detail.json is there: only a complete set gets one
        print(f'{folder}: tiles {missing} still to draw; detail.json not written', flush=True)
        return
    previous = folder / 'detail.json'
    if previous.is_file() and drawn != set(range(len(starts))):
        # tiles kept from an earlier run were drawn from the input that record names: keep it, so a changed strip
        # still shows as stale
        record['inputSha256'] = json.loads(previous.read_text(encoding='utf-8')).get('inputSha256', record['inputSha256'])
    (folder / 'detail.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')


def offset(reference, image):
    """(columns, rows) to roll `image` by so it lines up with `reference` (phase correlation of their luminance)."""
    a = reference @ np.array([0.299, 0.587, 0.114], np.float32)
    b = image @ np.array([0.299, 0.587, 0.114], np.float32)
    spectrum = np.fft.fft2(a - a.mean()) * np.conj(np.fft.fft2(b - b.mean()))
    peak = np.fft.ifft2(spectrum / np.maximum(np.abs(spectrum), 1e-6)).real
    y, x = np.unravel_index(int(peak.argmax()), peak.shape)
    y = y - peak.shape[0] if y > peak.shape[0] // 2 else y
    x = x - peak.shape[1] if x > peak.shape[1] // 2 else x
    return int(x), int(y)


def shifted(image, columns, rows):
    """`image` moved by whole texels, the uncovered edge filled from its nearest row or column."""
    height, width = image.shape[:2]
    ys = np.clip(np.arange(height) - rows, 0, height - 1)
    xs = np.clip(np.arange(width) - columns, 0, width - 1)
    return image[ys][:, xs]


def assemble(land, key, folder):
    """The strip at the tiles' scale, from the tracked tiles in `folder`: (rgb, scale)."""
    record = json.loads((folder / 'detail.json').read_text(encoding='utf-8'))
    width, starts, height = layout(land)
    if [width, starts, height] != [record['tileWidth'], record['starts'], record['height']]:
        raise ValueError(f'{folder}: the land strip changed shape since the tiles were drawn; redraw them')
    missing = [i for i in range(len(starts)) if not (folder / f'tile_{i:02d}.png').is_file()]
    if missing:
        raise FileNotFoundError(f'{folder}: detail tiles {missing} are missing; draw them with python -m tools.skykit.detail')
    if record['inputSha256'] != digest(land):
        print(f'note: {folder.name} tiles were drawn from an earlier version of the strip', flush=True)
    total = land.shape[1]
    scale = 1248.0 / width
    size = (int(round(width * scale)), int(round(height * scale)))
    top = int(round(PAD_TOP * scale))

    def tile(index):
        picture = Image.open(folder / f'tile_{index:02d}.png').convert('RGB').resize(size, Image.LANCZOS)
        drawn = np.asarray(picture, np.float32) / 255
        source = np.asarray(Image.fromarray(np.clip(tile_input(land, key, index) * 255 + 0.5, 0, 255).astype(np.uint8))
                            .resize(size, Image.BICUBIC), np.float32) / 255
        # the model moves its redraw a few texels (up to ten in Denver): put it back over its input, so lines that
        # cross into the next tile meet there
        columns, rows = offset(source, drawn)
        if max(abs(columns), abs(rows)) > MAX_SHIFT:  # an alias of a repeating pattern, not the model's drift
            print(f'note: tile {index:02d} offset ({columns}, {rows}) ignored', flush=True)
            columns = rows = 0
        drawn = shifted(drawn, columns, rows)
        # and drifts the grade a little: hold each tile to its input, row by row
        return panorama.apply_gain(drawn, panorama.row_gain(source, drawn, key), key)[top:]

    place = [int(round(s * scale)) for s in starts]
    strip = tile(0)
    for index in range(1, len(starts)):
        strip = panorama._extend(strip, tile(index), place[index - 1] + size[0] - place[index])
    # the last tile runs past the end onto the first: blend that tail into the start
    end = int(round(total * scale))
    tail = strip[:, end:]
    head = strip[:, :tail.shape[1]]
    path = panorama.seam_path(tail, head).astype(np.float32)[:, None]
    weight = np.clip((np.arange(tail.shape[1], dtype=np.float32)[None, :] - path) / (2 * panorama.SEAM_SOFT) + 0.5, 0, 1)[..., None]
    strip[:, :tail.shape[1]] = panorama.multiband(tail, head, weight.astype(np.float32))
    return np.ascontiguousarray(strip[:, :end]), end / total


def main(argv=None):
    from . import __main__ as build, profiles
    parser = argparse.ArgumentParser(prog='skykit.detail', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('panorama')
    parser.add_argument('--tiles', help='comma-separated tile numbers (default: all missing)')
    parser.add_argument('--seed', type=int, default=51)
    parser.add_argument('--redo', action='store_true')
    args = parser.parse_args(argv)
    spec = profiles.PANORAMAS[args.panorama]
    land = build.assembled_land(args.panorama)
    tiles = [int(t) for t in args.tiles.split(',')] if args.tiles else None
    generate(land, spec['key'], ART / spec['detail'], ART / spec['detail_prompt'], args.seed, tiles, args.redo)


if __name__ == '__main__':
    main()
