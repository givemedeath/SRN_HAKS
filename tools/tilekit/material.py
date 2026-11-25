"""A restyled texture: its pictures made by one of the routes, and written as one material file with its DDS maps.

A texture keeps its name and its layout; what changes is what is drawn under that name. Three routes make the
pictures (`make`): `master` lays a tiling scan with its own relief and roughness in place of a tiling texture, toned
to the colour the old one had; `layout` keeps the old texture's broad light and dark (its kerbs, lane lines, panel
joints) and takes its fine grain and relief from a scan; `upscale` keeps the old picture, enlarged, with relief
guessed from it. A fourth, composing a facade from its window grid, is the highrise batch's.

`write` stores colour, relief, shine and roughness (and glow, where there is one) as the mipmapped DDS maps envkit's
models use, with the material file that names them, under the texture's own name: the game takes a material named like
a model's bitmap with no model edit (plan, stratum 0). Maps are named after a `stem` of at most 14 characters, the
texture's name where it is that short."""
import functools
import subprocess
from pathlib import Path

import numpy as np

from . import pictures, require

ROUTES = ('master', 'layout', 'upscale')
STEM = 14  # a resref is 16 characters and a map adds two
SIZES = (4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048)  # a block of a compressed map is four pixels
DIELECTRIC = 0.04  # share of light a non-metal reflects head on (envkit's)
MASTER_MAPS = {'colour': 'Color', 'normal': 'NormalGL', 'roughness': 'Roughness', 'metal': 'Metalness'}  # ambientCG's names; +Y up, as the game reads relief


def master(folder):
    """The maps of a tiling scan in `folder` (ambientCG's 1K-JPG layout): {colour, normal: uint8 RGB arrays, roughness,
    metal: 0-1 arrays}. A scan without a metal map is no metal."""
    from PIL import Image
    folder = Path(folder); found = {}
    for key, word in MASTER_MAPS.items():
        paths = sorted(folder.glob(f'*_{word}.jpg')) + sorted(folder.glob(f'*_{word}.png'))
        if paths:
            with Image.open(paths[0]) as picture:
                found[key] = np.asarray(picture.convert('RGB' if key in ('colour', 'normal') else 'L'))
    require({'colour', 'normal', 'roughness'} <= set(found), f'{folder.name} lacks a colour, relief (NormalGL) or roughness map')
    size = found['colour'].shape[:2]; require(all(one.shape[:2] == size for one in found.values()), f'{folder.name}: its maps differ in size')
    found['roughness'] = found['roughness'] / 255.0
    found['metal'] = found['metal'] / 255.0 if 'metal' in found else np.zeros(size)
    return found


def _sized(values, size, *, repeat=1):
    """An array tiled `repeat` times each way and brought to `size` (width, height). A scan that is not the shape of
    the texture is tiled more the short way, so it is not stretched: a 2:1 scan lies twice down a square texture."""
    from PIL import Image
    values = np.asarray(values); height, width = values.shape[:2]; shape = (width / height) / (size[0] / size[1])
    across, down = repeat * max(1, round(1 / shape)), repeat * max(1, round(shape))
    tiled = np.tile(values, (down, across) + (1,) * (values.ndim - 2))
    if values.dtype == np.uint8:
        return np.asarray(Image.fromarray(tiled).resize(size, Image.LANCZOS))
    return np.asarray(Image.fromarray(np.float32(tiled), 'F').resize(size, Image.LANCZOS), np.float64).clip(0, 1)


def _renormal(normal):
    vector = np.asarray(normal, np.float64) / 127.5 - 1; vector /= np.maximum(np.linalg.norm(vector, axis=2, keepdims=True), 1e-6)
    return np.uint8(np.clip(vector * 0.5 + 0.5, 0, 1) * 255 + 0.5)


def _enlarged(old, size):
    from PIL import Image, ImageFilter
    picture = Image.fromarray(np.asarray(old)[..., :3]).resize(size, Image.LANCZOS)
    return np.asarray(picture.filter(ImageFilter.UnsharpMask(radius=1.5, percent=60, threshold=2)) if size[0] > np.asarray(old).shape[1] else picture)


def make(old, how, scan=None, *, enlarged=None):
    """The pictures of a restyled texture: {colour, normal: uint8 RGB arrays, roughness, metal: 0-1 arrays}, at
    how['size'] ([width, height]). old: the texture as the game draws it now (uint8 array). how: {route, size, and by
    route: repeat (times the scan tiles across the texture, default 1), tone (0-1 of the way the scan's mean colour moves
    to the old one's, default 1), grain (how strongly a scan's fine detail is laid on a kept layout, default 1), keep
    (pixels of the old picture, as enlarged, below which its detail is given up to the scan's, default 12), relief
    (pixels of rise guessed relief stands, default 2), roughness (0-1, an upscale's, default 0.8), glow (`glow`),
    turn (the scan a quarter turn anticlockwise, `turned`), wrap ('rows': `pictures.wrapped_rows`), crisp (how many times
    steeper a cut-out's edge is made), plain (`write`)}. An
    old picture with holes in it (an alpha channel in use) gives `alpha` too, and a glow asked for gives `glow`.
    enlarged: the old picture as an upscaling model enlarged it (`enlarge`), which an upscale then starts from."""
    route = how.get('route'); require(route in ROUTES, 'A texture\'s route is one of ' + ', '.join(ROUTES))
    size = tuple(how.get('size', ())); require(len(size) == 2 and all(side in SIZES for side in size), f'A texture\'s size is two of {SIZES}')
    require(route == 'upscale' or scan is not None, f'The {route} route needs a scan')
    require(enlarged is None or route == 'upscale', 'Only an upscale starts from an enlarged picture')
    old = np.asarray(old); source = old[..., :3] if enlarged is None else np.asarray(enlarged)[..., :3]
    if how.get('wrap') == 'rows':  # a facade whose top does not run on into its bottom: see pictures.wrapped_rows
        source = pictures.wrapped_rows(source)
    made = _routed(source, how, route, size, scan)
    if old.shape[2] == 4 and int(old[..., 3].min()) < 250:  # a picture with holes in it keeps them, where it had them
        from PIL import Image
        made['alpha'] = np.asarray(Image.fromarray(old[..., 3]).resize(size, Image.LANCZOS))
        if how.get('crisp'):  # a cut-out's edge (wire, railing, leaf) made sharp again after it was enlarged
            made['alpha'] = np.uint8(np.clip((made['alpha'].astype(np.float64) - 128) * float(how['crisp']) + 128, 0, 255) + 0.5)
    if how.get('glow') is not None:
        made['glow'] = glow(made, how['glow'])
    return made


def glow(made, lit):
    """The glow map of a made texture (uint8 RGB): its own colour where it is lit, black elsewhere. lit: {gain (how
    bright, default 1), tint ([red, green, blue] multipliers), above (0-255: only pixels at least this bright are lit;
    default 0), boxes ([{box: [left, top, right, bottom] in 0-1 of the picture, above: its own}]: lit only inside
    them, a console's indicator lights and not its housing)}. A picture with holes glows only where it is not a hole:
    a facade's lit windows are such a picture."""
    unknown = set(lit) - {'gain', 'tint', 'above', 'boxes'}; require(not unknown, 'A glow has no ' + ', '.join(sorted(unknown)))
    colour = made['colour'].astype(np.float64); tint = np.asarray(lit.get('tint', (1.0, 1.0, 1.0)), np.float64); require(tint.shape == (3,), 'A glow\'s tint is red, green and blue')
    shown = colour.max(axis=2) >= float(lit.get('above', 0))
    if lit.get('boxes') is not None:
        height, width = shown.shape; inside = np.zeros_like(shown)
        for one in lit['boxes']:
            require(set(one) <= {'box', 'above'} and len(one.get('box', ())) == 4 and 0 <= one['box'][0] < one['box'][2] <= 1 and 0 <= one['box'][1] < one['box'][3] <= 1,
                    'A glow\'s box is {box: [left, top, right, bottom] in 0-1, above}')
            left, top, right, bottom = one['box']; rows, columns = slice(round(top * height), round(bottom * height)), slice(round(left * width), round(right * width))
            inside[rows, columns] |= colour[rows, columns].max(axis=2) >= float(one.get('above', lit.get('above', 0)))
        shown = inside
    if 'alpha' in made:
        shown &= made['alpha'] >= 128
    return np.uint8(np.clip(colour * float(lit.get('gain', 1.0)) * tint, 0, 255) * shown[..., None] + 0.5)


def turned(scan):
    """A scan turned a quarter turn anticlockwise, its relief turned with it: ribs that ran across now run up."""
    normal = np.rot90(scan['normal']); leaning = np.dstack([255 - normal[..., 1], normal[..., 0], normal[..., 2]])
    return {**{key: np.rot90(value) for key, value in scan.items()}, 'normal': np.ascontiguousarray(leaning)}


def _routed(old, how, route, size, scan):
    if scan is not None and how.get('turn'):
        scan = turned(scan)
    if route == 'master':
        repeat = int(how.get('repeat', 1)); require(1 <= repeat <= 8, 'A scan tiles one to eight times across a texture')
        colour = pictures.toned(_sized(scan['colour'], size, repeat=repeat), old, float(how.get('tone', 1.0)))
        return {'colour': colour, 'normal': _renormal(_sized(scan['normal'], size, repeat=repeat)),
                'roughness': _sized(scan['roughness'], size, repeat=repeat), 'metal': _sized(scan['metal'], size, repeat=repeat)}
    large = _enlarged(old, size)
    if route == 'upscale':
        flat = np.full(size[::-1], float(how.get('roughness', 0.8)))
        return {'colour': large, 'normal': pictures.relief(pictures.height_of(large), float(how.get('relief', 2.0))), 'roughness': flat, 'metal': np.zeros(size[::-1])}
    repeat = int(how.get('repeat', 1)); keep = int(how.get('keep', 12)); grain = float(how.get('grain', 1.0))
    fine = _sized(scan['colour'], size, repeat=repeat).astype(np.float64)
    broad = np.dstack([pictures._wrapped_blur(large[..., channel], keep) for channel in range(3)])
    detail = fine - np.dstack([pictures._wrapped_blur(fine[..., channel], keep) for channel in range(3)])
    colour = np.uint8(np.clip(broad + detail * grain, 0, 255) + 0.5)
    # The layout's own edges (a kerb, a joint) are relief too: guessed from the kept picture and laid over the scan's.
    edges = pictures.relief(pictures.height_of(broad, detail=2, broad=keep * 2), float(how.get('relief', 2.0))).astype(np.float64) - np.array([127.5, 127.5, 255.0])
    normal = _renormal(np.clip(_sized(scan['normal'], size, repeat=repeat).astype(np.float64) + edges, 0, 255))
    return {'colour': colour, 'normal': normal, 'roughness': _sized(scan['roughness'], size, repeat=repeat), 'metal': _sized(scan['metal'], size, repeat=repeat)}


def shine(colour, metal):
    """Head-on reflectance 0-1: a non-metal's small fixed share, a metal's own brightness (envkit's rule)."""
    luminance = np.asarray(colour, np.float64)[..., :3] @ np.array([0.2126, 0.7152, 0.0722]) / 255
    return np.clip(DIELECTRIC + (luminance - DIELECTRIC) * metal, 0, 1)


def material_text(stem, glow=False):
    lines = ['renderhint NormalAndSpecMapped', '', f'texture0 {stem}', f'texture1 {stem}_n', f'texture2 {stem}_s', f'texture3 {stem}_r', 'texture4 null',
             f'texture5 {stem}_i' if glow else 'texture5 null']
    return '\n'.join(lines) + '\n'


def stem_of(name, how):
    stem = how.get('stem', name); require(len(stem) <= STEM and stem == stem.lower() and stem.replace('_', '').isalnum(),
                                          f'{name}: its maps need a `stem` of at most {STEM} lowercase characters')
    return stem


def write(name, made, folder, crunch, *, stem=None, glow=None, compress=None, plain=False):
    """Write a texture's material file and maps into `folder`: <stem>.dds (colour), _n (relief, half size as envkit's),
    _s (shine), _r (roughness), _i (glow, where the texture was made with one or one is given), and <name>.mtr. Every map must come out with
    its whole mip chain: one written with its largest level alone drew black in the game (plan, stratum 0). Returns the
    file names written. plain: the picture alone, under the texture's own name, with no maps and no material file, for a
    texture whose look the game makes from its TXI (water) and that a material would take over."""
    from concurrent.futures import ThreadPoolExecutor
    from PIL import Image
    if compress is None:
        from tools.envkit import convert
        compress = convert._compress
    stem = stem or name; require(len(stem) <= STEM and len(name) <= 16, f'{name}: a map\'s stem is at most {STEM} characters and a texture\'s name 16')
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); height, width = made['colour'].shape[:2]
    half = (max(width // 2, 64), max(height // 2, 64))
    channel = lambda values: Image.fromarray(np.repeat(np.uint8(np.clip(values, 0, 1) * 255 + 0.5)[..., None], 4, axis=2), 'RGBA')
    shown = Image.fromarray(np.dstack([made['colour'], made['alpha']]), 'RGBA') if 'alpha' in made else Image.fromarray(made['colour'], 'RGB')
    glow = made.get('glow') if glow is None else glow
    wanted = [(shown, f'{stem}.dds', '-DXT5' if 'alpha' in made else '-DXT1', (width, height), False),
              (Image.fromarray(made['normal'], 'RGB'), f'{stem}_n.dds', '-DXN', half, True),
              (channel(shine(made['colour'], made['metal'])), f'{stem}_s.dds', '-DXT5A', half, True), (channel(made['roughness']), f'{stem}_r.dds', '-DXT5A', half, True)]
    if plain:
        require(stem == name and glow is None, f'{name}: a plain texture has no stem of its own and no glow'); wanted = wanted[:1]
    if glow is not None:
        wanted.append((Image.fromarray(np.asarray(glow)[..., :3], 'RGB'), f'{stem}_i.dds', '-DXT1', half, False))
    # The game takes the first row of a DDS for the bottom of the picture, as it does a BioWare DDS's: written top row
    # first, a facade's lit windows came out upside down (pilot, 2026-11-18; no brick or asphalt showed it). So every
    # map is stored turned over. Its relief needs no other change: turned back by the game, it is the same picture.
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda one: compress(one[0].transpose(Image.FLIP_TOP_BOTTOM), folder / one[1], one[2], one[3], crunch, data=one[4]), wanted))
    for _, file, _, size, _ in wanted:
        require(pictures.levels(folder / file) >= pictures.whole_chain(*size) - 2, f'{file} was written without its mip chain')
    if plain:
        return [one[1] for one in wanted]
    (folder / f'{name}.mtr').write_text(material_text(stem, glow is not None), encoding='ascii', newline='\n')
    return [one[1] for one in wanted] + [f'{name}.mtr']


@functools.lru_cache(maxsize=None)
def _tree(repo, before, pack):
    """{lower-case file name: file name} of what a pack held at commit `before`."""
    listed = subprocess.run(['git', '-C', str(repo), 'ls-tree', '--name-only', before, '--', f'{pack}/'], capture_output=True, text=True)
    require(listed.returncode == 0, f'git cannot list {pack} at {before}: ' + listed.stderr.strip()[-300:])
    return {name.lower(): name for name in (line.rsplit('/', 1)[-1] for line in listed.stdout.splitlines())}


def current(repo, name, packs=('srn_t_common', 'srn_t_dgt04', 'srn_door', 'srn_placeable'), stock=None, before=None):
    """The picture of a texture as the tileset had it before its restyle: its DDS copy before its TGA, in the first of
    `packs` to hold one, else in `stock`, a folder of the base game's own pictures read out of the install (a base-game
    texture). before: the commit whose packs hold the originals (a spec's `before`); once a restyle is in the packs
    their files are its own maps, so a restyled name is refused there: one with a material file, or a standard DDS (the
    D20 originals are all BioWare DDS; a plain restyle such as the water has no material). A texture added to a pack
    after `before` is read from the pack as it is."""
    repo = Path(repo)
    for pack in packs if before is not None else ():
        tree = _tree(str(repo), before, pack); late = f'{name} is restyled already at {before} ({pack}): a spec\'s `before` is a commit whose packs hold the originals'
        require(f'{name}.mtr'.lower() not in tree, late)  # the same rule as the packs' own copies below
        for kind in ('dds', 'tga'):
            file = tree.get(f'{name}.{kind}'.lower())  # as the pack spelled it
            if file:
                shown = subprocess.run(['git', '-C', str(repo), 'show', f'{before}:{pack}/{file}'], capture_output=True)
                require(shown.returncode == 0, f'git cannot read {pack}/{file} at {before}')
                require(kind != 'dds' or shown.stdout[:4] != b'DDS ', late)
                return pictures.read(file, shown.stdout)
    restyled = [pack for pack in packs if (repo / pack / f'{name}.mtr').is_file()]
    for pack in packs if not restyled else ():
        for kind in ('dds', 'tga'):
            path = repo / pack / f'{name}.{kind}'
            if path.is_file():
                if kind == 'dds' and path.read_bytes()[:4] == b'DDS ':
                    restyled.append(pack); continue
                return pictures.read(path)
    for kind in ('dds', 'tga'):  # a base-game texture: its original is the game's own, whatever restyle a pack holds
        if stock and (Path(stock) / f'{name}.{kind}').is_file():
            return pictures.read(Path(stock) / f'{name}.{kind}')
    require(not restyled, f'{name} is restyled already ({", ".join(restyled)}): its old picture is read from the spec\'s `before` commit')
    raise ValueError(f'No pack holds a picture of {name}' + ('' if stock else ' (a base-game texture needs --stock)'))


def of_spec(spec):
    """What `current` takes from a material spec: `before`, and `packs` where the spec names its own (a tileset whose
    textures are not in the city set's packs: the first pack named that holds a texture gives its picture)."""
    return {'before': spec.get('before'), **({'packs': tuple(spec['packs'])} if spec.get('packs') else {})}


def _derived(folder, name, old, *, doubled=None):
    """Refuse a picture `redraw` or `enlarge` left in `folder` whose record says it was made from another original
    than `old` (the picture the spec starts from), another day picture (a lit one), or another enlargement; one with
    no record was placed by hand and is taken as it is, as those commands keep it."""
    import hashlib
    import json
    record = Path(folder) / f'{name}.json'
    if not record.is_file():
        return
    was = json.loads(record.read_text(encoding='utf-8-sig')); old = np.ascontiguousarray(np.asarray(old)[..., :3])
    again = f'{name}: its picture in {folder} was made from'
    require(was.get('source') in (None, hashlib.sha256(repr(old.shape).encode() + old.tobytes()).hexdigest()), f'{again} another picture than the one the spec starts from: make it again')
    day = Path(folder) / f'{was["of"]}.png' if was.get('of') else None
    require(day is None or 'day' not in was or (day.is_file() and hashlib.sha256(day.read_bytes()).hexdigest() == was['day']), f'{again} another {was.get("of")} day picture: make it again')
    if doubled is not None:
        from tools.envkit import reference
        require(was.get('doubled') in (None, doubled) and was.get('upscaler') in (None, reference.UPSCALER), f'{again} another enlargement than {doubled} times by {reference.UPSCALER}: enlarge it again')


def build(spec, repo, masters, folder, crunch, *, only=None, compress=None, enlarged=None, redrawn=None, stock=None):
    """Make and write every texture of a material spec ({before (the commit whose packs hold the original pictures,
    `current`), grades: {name: grade}, textures: {name: how}}; how['copy'] names the texture a new one (a copied
    terrain's) starts from; how['master']
    names a scan's folder in `masters`, how['grade'] one of the spec's grades, `pictures.graded`) into `folder`. A
    texture that is `doubled` starts from its picture in `enlarged`, the folder `enlarge.enlarge` filled, and one that
    is `redrawn` from its picture in `redrawn`, the folder `redraw.redraw` filled.
    Returns {name: {route, size, grade, files}}."""
    from . import enlarge
    textures = spec.get('textures'); require(isinstance(textures, dict) and textures, 'A material spec lists its textures')
    chosen = sorted(textures) if only is None else list(only); require(set(chosen) <= set(textures), 'Not in the spec: ' + ', '.join(sorted(set(chosen) - set(textures))))
    scans, told, grades = {}, {}, spec.get('grades', {})
    for name in chosen:
        how = textures[name]; scan = None
        if how.get('master'):
            if how['master'] not in scans:
                scans[how['master']] = master(Path(masters) / how['master'])
            scan = scans[how['master']]
        picture = (enlarge.picture_of(redrawn, name, 'redrawn', 'redraw') if how.get('redrawn') else
                   enlarge.picture_of(enlarged, name) if how.get('doubled') else None)
        old = np.asarray(current(repo, how.get('copy', name), stock=stock, **of_spec(spec)))  # a copy starts from its source's picture
        if picture is not None:  # made from that picture, as its record says
            _derived(redrawn if how.get('redrawn') else enlarged, name, old, doubled=None if how.get('redrawn') else how['doubled'])
        made = make(old, how, scan, enlarged=picture)
        if how.get('stain'):  # grime over the whole texture, before the district's grade; see pictures.stained
            require(0 < float(how['stain']) <= 1, f'{name}: a stain is between 0 and 1')
            made = pictures.stained(made, name, float(how['stain']))
        if how.get('grade'):  # the district's look, laid on whatever route made the picture
            require(how['grade'] in grades, f'{name}: the spec has no grade {how["grade"]}')
            made['colour'] = pictures.graded(made['colour'], grades[how['grade']])
        if how.get('glow') is not None and (how.get('stain') or how.get('grade')):  # a glow is of the picture as stained and graded
            made['glow'] = glow(made, how['glow'])
        told[name] = {'route': how['route'], 'size': list(how['size']), **({'grade': how['grade']} if how.get('grade') else {}), 'files': write(name, made, folder, crunch, stem=stem_of(name, how), compress=compress, plain=bool(how.get('plain')))}
    return told
