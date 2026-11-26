"""Computer screens of the 2070s, laid into the pictures of old devices.

The d20 Modern and UDP placeables carry the screenshots of their day: a Windows desktop on the office monitors, a
cartoon on the televisions, a British road map on a terminal (user, 2026-11-25: redraw any computer screen so it matches
the setting). The image model redrawing a device's whole picture draws a device round a dim screen, and given a layout
to follow it copies the layout's bars as text; so a screen's content is drawn alone, from a blank picture (`drawn`), and
laid into the device's picture here (`build`). Screens drawn in code came before and were not good enough (user, 2026-11-25).

A content list (docs/placeables/screen-pictures.json): {pictures: {name: {size, seed, prompt, lift}}, rule: what every
prompt ends with}. `lift`: the model draws interfaces at half brightness, and they are brought up as they are laid.

A screen list (docs/placeables/screens.json) is a material spec whose textures also have `screen`: a list of parts,
each with a `box` [left, top, right, bottom] in shares of the picture and one of
 picture  a content by its name, with `crop` (a box of it) where only some of it is shown
 sign     a word in a panel: {text, colour, on}
 mend     true: the box is filled in from its own edges (a maker's logo taken off a plain surface)
`turn` (quarter turns anticlockwise) is for a screen that lies on its side in the picture. `dim` (0-1) is a worn one's.
`build` lays the parts on the enlarged picture and leaves what `redraw` would leave, so `material --redrawn` takes it."""
import hashlib
import json
from pathlib import Path

import numpy as np

from . import enlarge, material, require

OVER = 3  # a sign is drawn this many times too large, then reduced: smooth edges
BLANK = (7, 11, 18)


def drawn(spec, folder, run, *, only=None, say=print):
    """Every content of the list `spec` drawn into `folder` as <name>.png by `run` (run(seed) gives a `redraw.qwen`).
    One already there from the same words is kept. Returns {name: drawn, kept or failed}."""
    from PIL import Image
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); told = {}
    for name, how in spec['pictures'].items():
        if only is not None and name not in only:
            continue
        target, record = folder / f'{name}.png', folder / f'{name}.json'; made = {'kind': 'tilekit-screen-picture', **how, 'rule': spec['rule']}
        if target.is_file() and record.is_file() and json.loads(record.read_text(encoding='utf-8')) == made:
            told[name] = 'kept'; continue
        work = folder / 'jobs' / name; work.mkdir(parents=True, exist_ok=True)
        for old in work.glob('*'):
            old.unlink()
        Image.new('RGB', tuple(how['size']), BLANK).save(work / 'blank.png')
        try:
            run(how['seed'])(work, how['prompt'] + '\n' + spec['rule'], [work / 'blank.png'])
        except (ValueError, OSError, RuntimeError) as error:
            told[name] = f'failed: {error}'
        else:
            with Image.open(work / 'out.png') as picture:
                picture.convert('RGB').resize(tuple(how['size']), Image.LANCZOS).save(target)
            record.write_text(json.dumps(made, indent=1) + '\n', encoding='utf-8'); told[name] = 'drawn'
        if say: say(json.dumps({name: told[name]}), flush=True)
    return told


def lifted(picture):
    """A content drawn at half brightness (uint8 RGB), at a lit screen's."""
    return np.uint8(np.clip(np.sqrt(np.clip(picture / 255 - 0.02, 0, 1)) * 1.15, 0, 1) * 255 + 0.5)


def content(spec, folder, name):
    """A content of the list `spec` out of the folder `drawn` filled, uint8 RGB."""
    from PIL import Image
    require(name in spec['pictures'], f'No screen content is called {name}'); target, record = Path(folder) / f'{name}.png', Path(folder) / f'{name}.json'
    require(target.is_file() and record.is_file(), f'{name} is not drawn yet: tilekit screens --draw'); was = json.loads(record.read_text(encoding='utf-8'))
    require(all(was.get(key) == value for key, value in spec['pictures'][name].items()) and was.get('rule') == spec['rule'], f'{name} was drawn from other words: draw it again')
    with Image.open(target) as picture:
        made = np.asarray(picture.convert('RGB'))
    return lifted(made) if spec['pictures'][name].get('lift') else made


def sign(text, width, height, colour, on):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('RGB', (width * OVER, height * OVER), tuple(on)); pen = ImageDraw.Draw(image); lines = text.split('\n'); size = int(height * OVER * 0.7 / len(lines))
    while size > 4:
        font = ImageFont.load_default(size); wide = max(pen.textbbox((0, 0), line, font=font, stroke_width=size // 24)[2] for line in lines)
        if wide <= width * OVER * 0.9:
            break
        size -= 1
    for index, line in enumerate(lines):
        pen.text((width * OVER / 2, height * OVER * (index + 0.5) / len(lines)), line, font=font, fill=tuple(colour), anchor='mm', stroke_width=size // 24, stroke_fill=tuple(colour))
    return np.asarray(image.resize((width, height), Image.LANCZOS))


def mended(picture, box):
    """The pixel box (left, top, right, bottom) filled from the picture just outside it, each edge fading into the next."""
    left, top, right, bottom = box; high, wide = picture.shape[:2]; picture = picture.astype(float); side = lambda a, limit: min(max(a, 0), limit - 1)
    band = 3; row = lambda y: np.mean([picture[side(y + k, high), left:right] for k in range(band)], axis=0); column = lambda x: np.mean([picture[top:bottom, side(x + k, wide)] for k in range(band)], axis=0)
    above, below, west, east = row(top - band), row(bottom), column(left - band), column(right); rows, columns = bottom - top, right - left
    v, u = ((np.arange(rows) + 0.5) / rows)[:, None, None], ((np.arange(columns) + 0.5) / columns)[None, :, None]
    clear = np.array([top >= band, bottom + band <= high, left >= band, right + band <= wide], float)  # a side on the picture's edge has nothing outside it but the box
    require(clear.any(), 'A box to mend covers the whole picture')
    near = np.stack([np.broadcast_to(one, (rows, columns, 1)) for one in (1 / v, 1 / (1 - v), 1 / u, 1 / (1 - u))]) ** 2 * clear[:, None, None, None]
    parts = [np.broadcast_to(above[None], (rows, columns, 3)), np.broadcast_to(below[None], (rows, columns, 3)), np.broadcast_to(west[:, None], (rows, columns, 3)), np.broadcast_to(east[:, None], (rows, columns, 3))]
    return np.uint8(np.clip(sum(n * p for n, p in zip(near, parts)) / near.sum(0), 0, 255) + 0.5)


def laid(picture, parts, name='a picture', of=None):
    """`picture` (uint8 RGB) with the `parts` of a screen list laid on it. of(name) gives a content."""
    from PIL import Image
    picture = np.array(picture[..., :3]); high, wide = picture.shape[:2]
    for part in parts:
        box = part.get('box', ()); require(len(box) == 4 and 0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1, f'{name}: a part has a box [left, top, right, bottom] in shares of the picture')
        left, top, right, bottom = round(box[0] * wide), round(box[1] * high), round(box[2] * wide), round(box[3] * high); size = (right - left, bottom - top); require(min(size) > 0, f'{name}: a part covers no pixel')
        require(sum(key in part for key in ('picture', 'sign', 'mend')) == 1, f'{name}: a part is one of picture, sign and mend')
        if part.get('mend'):
            made = mended(picture, (left, top, right, bottom))
        else:
            quarter = int(part.get('turn', 0)) % 4; shape = size[::-1] if quarter % 2 else size
            if 'picture' in part:
                whole = of(part['picture']); crop = part.get('crop', (0, 0, 1, 1)); rows, columns = whole.shape[:2]; require(len(crop) == 4 and 0 <= crop[0] < crop[2] <= 1 and 0 <= crop[1] < crop[3] <= 1, f'{name}: a crop is a box of the content')
                made = np.asarray(Image.fromarray(whole[round(crop[1] * rows):round(crop[3] * rows), round(crop[0] * columns):round(crop[2] * columns)]).resize(shape, Image.LANCZOS))
            else:
                made = sign(part['sign']['text'], *shape, part['sign']['colour'], part['sign']['on'])
            made = np.rot90(made, quarter)
        picture[top:bottom, left:right] = np.uint8(made * (1 - float(part.get('dim', 0))) + 0.5)
    return picture


def build(spec, repo, folder, *, enlarged=None, redrawn=None, only=None, stock=None, of=None):
    """Every texture of the screen list `spec` made into `folder` as <name>.png with the record `material.build` checks.
    It starts from the picture `redraw` left in `redrawn` where the texture says `over`: 'redrawn', else from the
    enlarged one where it is `doubled`, else from the picture as it is. of(name) gives a content (`content`). Returns {name: parts laid}."""
    from PIL import Image
    textures = spec['textures']; chosen = sorted(textures) if only is None else list(only); folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); told = {}
    for name in chosen:
        how = textures[name]; require(how.get('screen'), f'{name} has no parts (`screen`)')
        old = np.ascontiguousarray(np.asarray(material.current(repo, name, stock=stock, **material.of_spec(spec)))[..., :3])
        base = enlarge.picture_of(redrawn, name, 'redrawn', 'redraw') if how.get('over') == 'redrawn' else enlarge.picture_of(enlarged, name) if how.get('doubled') else old
        whole = np.asarray(Image.fromarray(base).resize(tuple(how['size']), Image.LANCZOS)); Image.fromarray(laid(whole, how['screen'], name, of)).save(folder / f'{name}.png')
        (folder / f'{name}.json').write_text(json.dumps({'kind': 'tilekit-screen', 'texture': name, 'source': hashlib.sha256(repr(old.shape).encode() + old.tobytes()).hexdigest(), 'screen': how['screen'], 'contents': {part['picture']: hashlib.sha256(of(part['picture']).tobytes()).hexdigest() for part in how['screen'] if 'picture' in part}}, indent=1) + '\n', encoding='utf-8')
        told[name] = len(how['screen'])
    return told
