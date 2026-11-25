"""A texture drawn again by an image generator, on the layout it has.

Enlarging a small old photograph makes it clean and no richer (user, 2026-11-18: upscaling "is not going to cut it").
A window, a shopfront, a sign or a facade is drawn again instead: the generator is shown the picture the game draws
now and asked for the same thing, seen the same way, with every frame and opening where it is, so the new picture
goes on the same model. A lit variant is drawn from its day picture as redrawn, so the pair is one window.

The redraw list (`docs/tilesets/<tileset>/redraw.json`) names each texture's kind and district, and for a lit one the
texture it is `of`. `redraw` leaves `<name>.png` and a record in a folder `material.build` reads for the textures
whose spec says `redrawn`. The generator is whatever `run` is: the command line's is the Codex CLI."""
import hashlib
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from . import material, require

SIDE = 1024  # the longer side of a reference, and of the picture asked for
DISTRICTS = {
    'barrens': 'a neglected, poor district of a 2070s cyberpunk city (Shadowrun Barrens): old late-20th-century construction, grime, rust, peeling paint, improvised repairs',
    'corporate': 'a 2070s cyberpunk megacorporate district (Shadowrun): cool graphite metal, muted blue-grey glass, clean and expensive, only faint rain marks',
    'industrial': 'a working industrial district of a 2070s cyberpunk city (Shadowrun): dark steel, stained cement, warm rust, functional and worn',
    'civic': 'a public building of a 2070s cyberpunk city (Shadowrun): sturdy, institutional, maintained on a small budget, some wear and grime',
    'residential': 'an ordinary residential district of a 2070s cyberpunk city (Shadowrun): a lived-in apartment block, modest upkeep, people\'s own things in the windows',
    'derelict': 'an abandoned district of a 2070s cyberpunk city (Shadowrun Barrens): a gutted, empty building, long left to decay',
    'home': 'the inside of an ordinary apartment in a 2070s cyberpunk city (Shadowrun): lived in, modest, modern materials, clean enough'}
KINDS = {
    'window': 'a window. Daytime, the room behind unlit: dark, slightly reflective glass with some dirt; the frame worn as its district suggests',
    'facade': 'a section of a building facade with its grid of windows. Daytime, glass dark and slightly reflective, no lit windows, no visible interiors',
    'wall': 'a wall surface',
    'shopfront': 'a shop window with its display and lettering. Daytime, the shop unlit inside',
    'sign': 'a sign. Its wording stays the same and stays easy to read, in clean lettering',
    'poster': 'a wall of layered, torn, weathered posters and flyers. Invented bands, events and products only',
    'fixture': 'a piece of building hardware seen straight on (a grille, vent, fan, meter, drain or the like). The same object, in the same place and size',
    'trim': 'a strip or panel of architectural trim. The same mouldings and pattern, in the same places',
    'furniture': 'the front of a piece of built-in furniture seen straight on (a cabinet, a dresser, shelves, a bookcase). The same piece, its doors, drawers, '
                 'shelves, handles and what stands on it in the same places',
    'floor': 'a floor covering seen from straight above',
    'material': 'a plain surface material seen straight on (wood, metal, stone, plaster, cloth)',
    'cloth': 'washing hung out to dry. The same garments in the same places and colours; the plain background around them stays exactly as it is'}
LIT = ('Make its night version: the very same picture, with the frame, mullions, panels, lettering and every mark in the same positions. Only what is behind the glass '
       'or is a lamp or neon tube changes: it is lit from inside, uneven from pane to pane, dirt still visible against the light. Everything that is not glass or a '
       'light stays dark, as at night, a little darker than by day. No glow or bloom spilling over frames.')
RULES = ('Hard requirements:\n- Exactly straight-on orthographic view: no perspective, no tilt, no vignette.\n'
         '- Every frame, mullion, opening, panel, band and block of lettering stays in the same position and proportion as in the reference, so the picture can replace '
         'it on the same 3D model. The subject fills the picture edge to edge exactly as the reference does: no added wall, border, margin or background.\n'
         '- Any area that is pure black in the reference stays pure black.\n'
         '- Flat, even, overcast lighting with no cast shadows, as for a game albedo texture. Wear is mild and evenly spread: no single large crack, stain, tape or '
         'graffiti that would be recognised when the picture repeats along a building.\n'
         '- No real brand names, logos or trademarks, no people.\n')


KEEP_BLACK = '- Any area that is pure black in the reference stays pure black.'
GLAZED = ('- The openings, pure black or dark in the reference, are window glass: draw them as glass in every opening, none left black or empty, '
          'with only the room behind seen faintly through it.')
GLASS = (34, 42, 52)  # a glazed texture's black openings are filled with this before the reference goes to the generator
MOSTLY_BLACK = 0.5  # a window texture more pure black than this says what its openings are (`glazed` or `opening`: 'door')


BLANK = (60, 110, 170)  # what a `blank` box of a reference is filled with; the note says what is drawn there instead


def banded(old):
    """Every row of `old` its own mean colour: a wall's bands at their heights with the pattern on them gone. Shown the
    old wallpaper, a generator asked for plain plaster draws the wallpaper again (2026-11-24)."""
    rows = np.asarray(old)[..., :3].astype(np.float64).mean(axis=1, keepdims=True)
    return np.uint8(np.broadcast_to(rows, np.asarray(old)[..., :3].shape) + 0.5)


def blanked(picture, boxes):
    """`picture` (an RGB array) with each box [left, top, right, bottom], in shares of its width and height, filled with
    `BLANK`, or with the colour given as a fifth value: what stood there (a portrait, an old print) is not copied."""
    shown = np.asarray(picture)[..., :3].copy(); height, width = shown.shape[:2]
    for box in boxes:
        require(len(box) in (4, 5) and 0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1, 'A blank box is [left, top, right, bottom] in shares of the picture')
        shown[round(box[1] * height):round(box[3] * height), round(box[0] * width):round(box[2] * width)] = box[4] if len(box) == 5 else BLANK
    return shown


def unfilled(picture, boxes, near=30.0):
    """The blank boxes of a drawn picture that are still `BLANK`: the generator copied the fill (2026-11-24)."""
    values = np.asarray(picture)[..., :3].astype(np.float64); height, width = values.shape[:2]; left = []
    for box in boxes:
        part = values[round(box[1] * height):round(box[3] * height), round(box[0] * width):round(box[2] * width)].reshape(-1, 3)
        if len(box) == 4 and np.abs(np.median(part, axis=0) - BLANK).mean() < near and part.std(axis=0).mean() < near:
            left.append(box)
    return left


def _broad(values, axis, radius):
    """`values` smoothed along one axis, mirrored at its ends (a wrapping blur would average the very step sought)."""
    for _ in range(3):
        size = values.shape[axis]; place = np.abs(np.arange(-radius - 1, size + radius)); place = np.where(place >= size, 2 * size - 2 - place, place)
        total = np.cumsum(np.take(values, place, axis=axis), axis=axis); wide = 2 * radius + 1
        values = (np.take(total, np.arange(wide, wide + size), axis=axis) - np.take(total, np.arange(size), axis=axis)) / wide
    return values


def levelled(picture, way):
    """`picture` (an RGB image) with its broad light and shade taken out, so that it meets itself where it repeats: a
    generator shades a plain wall darker at one side, which showed as a step in tone from panel to panel (2026-11-24).
    way: 'across' (each row to its own mean: a wall, its bands kept) or 'both' (a plain material)."""
    from PIL import Image
    require(way in ('across', 'both'), 'A texture is levelled across or both')
    values = np.asarray(picture.convert('RGB')).astype(np.float64); radius = max(1, max(values.shape[:2]) // 16)
    broad = _broad(values, 1, radius)
    if way == 'both':
        broad = _broad(broad, 0, radius); mean = values.mean(axis=(0, 1), keepdims=True)
    else:
        broad = _broad(broad, 0, max(1, radius // 16)); mean = broad.mean(axis=1, keepdims=True)
    return Image.fromarray(np.uint8(np.clip(values * mean / np.maximum(broad, 1.0), 0, 255) + 0.5))


def mostly_black(old, below=8):
    """The share of a picture that is pure black (each channel under `below`)."""
    return float((np.asarray(old)[..., :3].max(axis=2) < below).mean())


def glass_filled(old, below=8):
    """`old` with its pure-black openings filled with `GLASS`, as a glazed texture's reference."""
    shown = np.asarray(old)[..., :3].copy(); shown[shown.max(axis=2) < below] = GLASS
    return shown


def prompt(name, how, size, tiles=False, tool=True):
    """What the generator is asked for one texture. how: {kind, district, note (optional), of (a lit variant's day
    texture), light (a lit variant's light, optional), words (new lettering for a sign, optional)}. size: the (width, height) the picture is saved at. tool: the
    generator is an agent told to use its image tool and save the file; without it the text is the edit itself, and
    the pictures are spoken of in the order they are given."""
    require(how.get('district') in DISTRICTS, f'{name}: a redraw\'s district is one of ' + ', '.join(DISTRICTS))
    require(how.get('kind') in KINDS, f'{name}: a redraw\'s kind is one of ' + ', '.join(KINDS))
    lines = [f'Use your built-in image generation tool to make one image, then save it in the current working directory as out.png, resized (not cropped) to exactly '
             f'{size[0]}x{size[1]} pixels. Generate at the closest shape the tool offers. Do nothing else.', ''] if tool else []
    day, old = ('day.png', 'ref.png') if tool else ('The first image', 'The second image')
    if how.get('of'):
        lines += [f'Two images are attached. {day} is a game texture, by day. {old} is the old low-quality night version of the same texture, which shows which '
                  f'parts are lit. {LIT}', f'The light is {how.get("light", "warm and dim")}. The setting is {DISTRICTS[how["district"]]}.']
    else:
        what = KINDS[how['kind']]
        if how.get('words'):  # new wording: the kind's "wording stays the same" would win over a note asking for it
            what = what.split('. ')[0] + f'. Every word of the old lettering is replaced: the new lettering reads exactly {how["words"]}, in the same places, sizes and style'
        lines += [f'The attached {"ref.png" if tool else "image"} is an old low-quality game texture of {what}. Redraw it as a new, detailed, '
                  f'photographic-quality texture of the same thing for {DISTRICTS[how["district"]]}.']
    if how.get('note'):
        lines.append(how['note'])
    rules = RULES.rstrip()
    if how.get('glazed'):  # the black is a window's empty opening, not a door's: it is drawn as glass
        rules = rules.replace(KEEP_BLACK, GLAZED)
    if how.get('opening') == 'none':  # its dark parts are drawn, not openings
        rules = rules.replace(KEEP_BLACK + '\n', '')
    lines += ['', rules]
    if tiles:
        lines.append('- It must tile seamlessly: what leaves the right edge continues at the left edge, and the top continues at the bottom.')
    return '\n'.join(lines) + '\n'


def codex(executable):
    """A `run` that asks the Codex CLI: run(folder, text, images) leaves out.png in `folder`."""
    import subprocess

    def run(folder, text, images):
        command = [str(executable), 'exec', '--skip-git-repo-check', '-s', 'workspace-write', '-C', str(folder)]
        for image in images:
            command += ['-i', str(image)]
        done = subprocess.run(command + ['-o', str(Path(folder) / 'last.txt')], input=text, text=True, encoding='utf-8', capture_output=True, timeout=1500)
        require(done.returncode == 0, f'The generator failed in {folder}: ' + (done.stderr or done.stdout)[-600:])
    return run


def qwen(client, local, bindings, *, seed=1, deadline=2400):
    """A `run` that asks the local Qwen edit model on the shared ComfyUI (envkit's reference profile), one job at a
    time through headkit.shared_comfy.slot: run(folder, text, images) leaves out.png in `folder`. The model draws a
    square, so the pictures go in squared and what comes back is brought to the texture's shape by `redraw`."""
    import uuid
    from PIL import Image
    from tools.envkit import reference
    from tools.headkit import design

    def run(folder, text, images):
        folder = Path(folder); token = uuid.uuid4().hex; base = f'{folder.name}-s{seed}'; sources = {}
        for index, image in enumerate(images):
            squared = folder / f'squared-{index}.png'
            with Image.open(image) as picture:
                picture.convert('RGB').resize((SIDE, SIDE), Image.LANCZOS).save(squared)
            sources[f'reference-{index}.png'] = squared
        graph = design.compile_design(text, [f'{design.SUBFOLDER}/{token}/{name}' for name in sources], seed, 1, f'{design.SUBFOLDER}/{token}/{base}', profile=reference.PROFILE)
        receipt = {'schemaVersion': 1, 'kind': 'tilekit-redrawn', 'texture': folder.name, 'prompt': text, 'seed': seed, 'profile': reference.PROFILE, 'token': token,
                   'outputPrefix': graph['9']['inputs']['filename_prefix'], 'outputs': []}
        design._execute(client, local, bindings, graph, receipt, sources, folder, base, 1, None, queue={'deadline': deadline})
        shutil.copyfile(folder / f'{base}-b0.png', folder / 'out.png')
    run.tool = False  # the text is the edit itself
    return run


def _opened(path):
    """A picture file as an RGB image read into memory, the file closed again (an open one cannot be moved on Windows)."""
    from PIL import Image
    with Image.open(path) as picture:
        return picture.convert('RGB')


def _sha(picture):
    picture = np.ascontiguousarray(picture); return hashlib.sha256(repr(picture.shape).encode() + picture.tobytes()).hexdigest()


def _file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def alike(old, new, side=256):
    """How well a redrawn picture's edges sit on the old one's: the correlation of their edge strengths, about 0.5 or
    more for a layout that was kept, near 0 for one that moved. A lit picture against a dim one scores lower."""
    from PIL import Image
    shrunk = lambda picture: np.asarray(Image.fromarray(np.asarray(picture)[..., :3]).convert('L').resize((side, side), Image.LANCZOS), np.float64)
    edges = lambda grey: (np.abs(np.diff(grey, axis=1))[:-1] + np.abs(np.diff(grey, axis=0))[:, :-1]).ravel()
    first, second = edges(shrunk(old)), edges(shrunk(new))
    return 0.0 if first.std() == 0 or second.std() == 0 else float(np.corrcoef(first, second)[0, 1])


def black_kept(old, picture, *, below=8):
    """`picture` with every area that is pure black in `old` (each channel under `below`) black again: such an area is
    a door or opening a model is hooked up to, whatever the generator drew there. Specks of black are left to it."""
    from PIL import Image, ImageFilter
    dark = Image.fromarray(np.uint8((np.asarray(old)[..., :3].max(axis=2) < below) * 255)).filter(ImageFilter.MinFilter(3))
    mask = np.asarray(dark.resize(picture.size, Image.NEAREST)) > 127
    if not mask.any():
        return picture
    shown = np.asarray(picture.convert('RGB')).copy(); shown[mask] = 0
    return Image.fromarray(shown)


def _blobs(lit):
    """{label: cells} of the 4-connected True regions of a small boolean grid, labelled in reading order."""
    labels = np.zeros(lit.shape, int); count = 0
    for start in zip(*np.nonzero(lit)):
        if labels[start]:
            continue
        count += 1; labels[start] = count; stack = [start]
        while stack:
            row, column = stack.pop()
            for near in ((row + 1, column), (row - 1, column), (row, column + 1), (row, column - 1)):
                if 0 <= near[0] < lit.shape[0] and 0 <= near[1] < lit.shape[1] and lit[near] and not labels[near]:
                    labels[near] = count; stack.append(near)
    return labels, count


def kept_lights(mask, dark, share, seed=0):
    """Where a share of the lit windows of `mask` (H, W, 1, 0 to 1) are lit instead: the panes lit near one another
    make one window, at least one window is kept, picked by `seed`, and each kept window is lit over its whole box
    where `dark` (H, W, 0 to 1: how dark the day picture is) says it is open or a gap, not over its frame or the boards
    across it. A derelict tower shows two or three squatters' windows, not an office's lit grid."""
    from PIL import Image, ImageFilter
    height, width = mask.shape[:2]; step = max(1, min(height, width) // 128)
    small = np.asarray(Image.fromarray(np.uint8(mask[..., 0] * 255 + 0.5)).resize((max(1, width // step), max(1, height // step)), Image.BOX)) > 127
    near = np.asarray(Image.fromarray(np.uint8(small * 255)).filter(ImageFilter.MaxFilter(5))) > 127  # a window's panes, split by its mullions, as one
    labels, count = _blobs(near)
    if not count:
        return mask
    chosen = np.random.default_rng(seed).choice(np.arange(1, count + 1), size=min(count, max(1, round(share * count))), replace=False)
    lit = np.zeros((height, width))
    for label in chosen:
        rows, columns = np.nonzero(labels == label)
        lit[rows.min() * step:(rows.max() + 1) * step, columns.min() * step:(columns.max() + 1) * step] = 1.0
    soft = max(1, width // 256)
    return (np.asarray(Image.fromarray(np.uint8(lit * dark * 255 + 0.5)).filter(ImageFilter.GaussianBlur(soft)), np.float64) / 255)[..., None]


def composed(day, old_day, old_lit, enlarged=None, keep=None):
    """The lit variant of a redrawn day picture, made with no generator: its glass lit where the old night texture is
    lit, in that texture's colours, with the day picture's own detail (a curtain, a blind, dirt) showing against the
    light; everything else as by day, darker. day: the redrawn day picture (PIL image). old_day, old_lit: the
    textures the game draws now (uint8 arrays; a lit one's alpha limits what is lit). enlarged: the old lit picture
    as the upscaling model enlarged it, for cleaner colours. Lit is what the old night texture shows well brighter
    than the old day one, or outright bright (a neon tube is as bright by day in the old pictures). keep: {share,
    colour, seed} leaves only that share of the lit windows (`kept_lights`), lit in `colour` where it is given."""
    from PIL import Image, ImageFilter
    weights = np.array([0.2126, 0.7152, 0.0722]); size = day.size
    sized = lambda picture: np.asarray(Image.fromarray(np.ascontiguousarray(np.asarray(picture)[..., :3])).resize(size, Image.LANCZOS), np.float64)
    new, before, night = np.asarray(day.convert('RGB'), np.float64), sized(old_day), sized(old_lit if enlarged is None else enlarged)
    brightest = night.max(axis=2)
    mask = np.maximum(np.clip((night @ weights - before @ weights - 12) / 36, 0, 1) * np.clip((brightest - 60) / 60, 0, 1), np.clip((brightest - 140) / 50, 0, 1))
    if np.asarray(old_lit).shape[2] == 4:
        mask *= np.asarray(Image.fromarray(np.ascontiguousarray(np.asarray(old_lit)[..., 3])).resize(size, Image.LANCZOS), np.float64) / 255
    soft = max(1, size[0] // 256)
    mask = np.asarray(Image.fromarray(np.uint8(mask * 255 + 0.5)).filter(ImageFilter.GaussianBlur(soft)), np.float64)[..., None] / 255
    colour = np.asarray(Image.fromarray(np.uint8(night + 0.5)).filter(ImageFilter.GaussianBlur(soft * 2)), np.float64)
    if keep:
        mask = kept_lights(mask, np.clip((60 - new @ weights) / 40, 0, 1), keep.get('share', 1.0), keep.get('seed', 0))
        if keep.get('colour'):  # the old light's brightness, in the colour asked for
            colour = (colour @ weights)[..., None] / 255 * np.array(keep['colour'], np.float64) * 1.4
    light = new @ weights; inside = mask[..., 0] > 0.5
    low, high = np.percentile(light[inside], [5, 95]) if inside.sum() > 50 else (0.0, 255.0)
    detail = np.clip((light - low) / max(high - low, 1.0), 0, 1)[..., None]
    return Image.fromarray(np.uint8(np.clip(new * 0.6 * (1 - mask) + colour * (0.7 + 0.5 * detail) * mask, 0, 255) + 0.5))


def redraw(spec, repo, folder, run, *, only=None, enlarged=None, workers=3, say=print, stock=None):
    """Every texture of a redraw list drawn again into `folder` as <name>.png with a record beside it, the day
    pictures first and then the lit ones from them, `workers` at a time. One that is there already is passed over where
    its record says it was made from the picture the game draws now (a lit one also from its day picture as it is), and
    refused where its record says otherwise; one with no record was placed by hand and is kept. A
    lit one whose entry says `compose` is not drawn: it is `composed` from its day picture and the old textures.
    enlarged: the folder of `enlarge`, whose cleaner picture is the reference where it has one. Returns
    {name: 'redrawn' | 'composed' | 'kept' | 'failed: ...'}; a failure stops nothing else."""
    from PIL import Image
    textures = spec.get('textures'); require(isinstance(textures, dict) and textures, 'A redraw list lists its textures')
    chosen = sorted(textures) if only is None else list(only); require(set(chosen) <= set(textures), 'Not in the list: ' + ', '.join(sorted(set(chosen) - set(textures))))
    for name in chosen:
        of = textures[name].get('of'); require(of is None or of in textures, f'{name}: it is of {of}, which the list lacks')
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); told = {}

    def one(name):
        how = textures[name]; target = folder / f'{name}.png'; record = folder / f'{name}.json'
        source = lambda texture: textures.get(texture, {}).get('copy', texture)  # a copied terrain's texture is drawn from its source's picture
        original = lambda: np.asarray(material.current(repo, source(name), stock=stock, **material.of_spec(spec)))
        day = folder / f'{how["of"]}.png' if how.get('of') else None  # a lit variant's day picture, as redrawn
        if how.get('kind') == 'window' and not how.get('of') and not how.get('glazed') and how.get('opening') != 'door':
            share = mostly_black(original())  # empty black windows went unnoticed in release 1 (2026-11-20): each is said
            require(share <= MOSTLY_BLACK, f'{name} is {share:.0%} pure black: say whether its openings are window glass ("glazed": true, drawn as glass) '
                    'or a door opening a model is hooked up to ("opening": "door", kept black)')
        if target.is_file():  # kept where it was made from the picture the game draws now, a lit one from its day picture as it is; one with no record was placed by hand
            was = json.loads(record.read_text(encoding='utf-8')) if record.is_file() else {}
            require('source' not in was or was['source'] == _sha(original()[..., :3]), f'{target} was not made from the {name} the game draws now: take it and its record away and draw it again')
            require(not how.get('glazed') or was.get('glazed') or 'source' not in was, f'{target} was drawn with its openings black: take it and its record away and draw it again glazed')
            require(day is None or 'day' not in was or (day.is_file() and was['day'] == _file_sha(day)),
                    f'{target} was made from another {how.get("of")} day picture: take it and its record away and draw it again')
            require(not how.get('compose') or 'source' not in was or (was.get('keep') or None) == (how.get('keep') or None),
                    f'{target} was composed with other lights kept: take it and its record away and compose it again')
            return 'kept'
        whole = original(); old = whole[..., :3]; height, width = old.shape[:2]
        size = (SIDE, max(64, round(SIDE * height / width / 64) * 64)) if width >= height else (max(64, round(SIDE * width / height / 64) * 64), SIDE)
        better = Path(enlarged) / f'{name}.png' if enlarged else None
        if how.get('compose'):
            require(how.get('of'), 'only a lit variant is composed: it names the day texture it is `of`')
            require(day.is_file(), f'its day picture {how["of"]} was not redrawn')
            cleaner = _opened(better) if better is not None and better.is_file() else None
            with Image.open(day) as shown:
                picture = composed(shown, np.asarray(material.current(repo, source(how['of']), stock=stock, **material.of_spec(spec))), whole,
                                   None if cleaner is None else np.asarray(cleaner), keep=how.get('keep')).resize(size, Image.LANCZOS)
            picture.save(target)
            record.write_text(json.dumps({'kind': 'tilekit-composed', 'texture': name, 'source': _sha(old), 'of': how['of'], 'day': _file_sha(day), 'size': list(size),
                                          **({'keep': how['keep']} if how.get('keep') else {})}, indent=1) + '\n', encoding='utf-8')
            return 'composed'
        work = folder / 'jobs' / name
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True); images = [work / 'ref.png']
        reference = _opened(better) if better is not None and better.is_file() else Image.fromarray(old)
        if how.get('glazed'):
            reference = Image.fromarray(glass_filled(np.asarray(reference.convert('RGB'))))
        if how.get('bands'):
            reference = Image.fromarray(banded(np.asarray(reference.convert('RGB'))))
        if how.get('blank'):
            reference = Image.fromarray(blanked(np.asarray(reference.convert('RGB')), how['blank']))
        reference.resize(size, Image.LANCZOS).save(work / 'ref.png')
        if day is not None:
            require(day.is_file(), f'its day picture {how["of"]} was not redrawn')
            _opened(day).resize(size, Image.LANCZOS).save(work / 'day.png'); images.insert(0, work / 'day.png')
        text = prompt(name, how, size, tiles=bool(how.get('tiles')), tool=getattr(run, 'tool', True)); (work / 'prompt.txt').write_text(text, encoding='utf-8')
        run(work, text, images)
        require((work / 'out.png').is_file(), 'the generator left no out.png')
        with Image.open(work / 'out.png') as made:
            picture = made.convert('RGB').resize(size, Image.LANCZOS)
        require(not unfilled(np.asarray(picture), how.get('blank', ())), 'the generator left a blank box as it was: give the box the colour of what belongs there')
        if how.get('level'):
            picture = levelled(picture, how['level'])
        if not how.get('glazed') and how.get('opening') != 'none':
            picture = black_kept(old, picture)  # a generator paints over black openings (doors are hooked up there), by day or night: they are put back
        picture.save(target)
        record.write_text(json.dumps({'kind': 'tilekit-redrawn', 'texture': name, 'source': _sha(old), 'prompt': text, 'size': list(size),
                                      **({'of': how['of'], 'day': _file_sha(day)} if day is not None else {}),
                                      **({'glazed': True} if how.get('glazed') else {}), 'alike': round(alike(old, picture), 2)}, indent=1) + '\n', encoding='utf-8')
        return 'redrawn'

    def safe(name):
        try:
            state = one(name)
        except Exception as error:  # one texture's failure is said and the rest go on
            state = f'failed: {error}'
        if say: say(json.dumps({'texture': name, 'state': state}), flush=True)
        return name, state
    for group in ([name for name in chosen if not textures[name].get('of')], [name for name in chosen if textures[name].get('of')]):
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            told.update(pool.map(safe, group))
    return told
