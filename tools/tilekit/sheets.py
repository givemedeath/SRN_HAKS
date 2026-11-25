"""Many small pictures enlarged together: `enlarge` sends one picture a job, and a job waits its turn on the shared
ComfyUI, so a pack's thousand small pictures would hold the queue for hours. Here they are laid on sheets, each with a
margin of itself wrapped round it (`enlarge.wrapped`), a sheet is one job, and each picture is cut out of what comes
back. What it leaves in the folder, a picture and its record, is what `enlarge` leaves, so `material.build` reads either.

The margin is wider than the one a picture has on its own: here a picture's neighbour is another picture, and the
model must not see it."""
import hashlib
import json
import uuid
from pathlib import Path

import numpy as np

from . import enlarge, material, require

SIDE = 1536  # pixels of a sheet's side before it is doubled
MARGIN = 32


def packed(sizes, side=SIDE):
    """Sheets of the pictures `sizes` ({name: (width, height)} with their margins on): [{name: (x, y)}], laid in rows,
    tallest first. A picture larger than a sheet is refused."""
    sheets = []
    for name in sorted(sizes, key=lambda one: (-sizes[one][1], -sizes[one][0], one)):
        width, height = sizes[name]; require(width <= side and height <= side, f'{name} is larger than a sheet')
        for sheet in sheets:
            place = next(((row['x'], row['y'], row) for row in sheet['rows'] if row['x'] + width <= side and height <= row['height']), None)
            if place is None and sheet['next'] + height <= side:
                row = {'x': 0, 'y': sheet['next'], 'height': height}; sheet['rows'].append(row); sheet['next'] += height; place = (0, row['y'], row)
            if place:
                break
        else:
            row = {'x': 0, 'y': 0, 'height': height}; sheet = {'rows': [row], 'next': height, 'at': {}}; sheets.append(sheet); place = (0, 0, row)
        sheet['at'][name] = place[:2]; place[2]['x'] += width
    return [sheet['at'] for sheet in sheets]


def laid(pictures, at, side=SIDE):
    page = np.zeros((side, side, 3), np.uint8)
    for name, (x, y) in at.items():
        height, width = pictures[name].shape[:2]; page[y:y + height, x:x + width] = pictures[name]
    return page


def doubled(pictures, send, *, margin=MARGIN, side=SIDE):
    """Every picture of {name: uint8 RGB array} at twice its size. send(page) gives a page doubled."""
    ringed = {name: enlarge.wrapped(one, margin) for name, one in pictures.items()}; out = {}
    for at in packed({name: one.shape[1::-1] for name, one in ringed.items()}, side):
        page = send(laid(ringed, at, side)); require(page.shape[:2] == (2 * side, 2 * side), 'The model did not give the sheet doubled')
        for name, (x, y) in at.items():
            height, width = pictures[name].shape[:2]; left, top = 2 * (x + margin), 2 * (y + margin)
            out[name] = page[top:top + 2 * height, left:left + 2 * width].copy()
    return out


def run(client, local, bindings_path, repo, spec, folder, *, deadline=7200, say=print, stock=None, group=400):
    """As `enlarge.enlarge`, on sheets. Every group of pictures is finished, and kept, before the next is sent."""
    from PIL import Image
    from tools.envkit import reference
    from tools.headkit import design
    textures = spec['textures']; folder = Path(folder); work = folder / 'jobs'; work.mkdir(parents=True, exist_ok=True); told, todo = {}, {}

    def send(page):
        token = uuid.uuid4().hex; base = f'sheet-{token[:12]}'; staged = work / f'{base}-in.png'; Image.fromarray(page).save(staged)
        graph = reference.enlarge_graph(f'{design.SUBFOLDER}/{token}/reference-0.png', f'{design.SUBFOLDER}/{token}/{base}')
        receipt = {'schemaVersion': 1, 'kind': 'tilekit-enlarged-sheet', 'upscaler': reference.UPSCALER, 'token': token, 'outputPrefix': graph['9']['inputs']['filename_prefix'], 'outputs': []}
        design._execute(client, local, bindings_path, graph, receipt, {'reference-0.png': staged}, work, base, 1, None, queue={'deadline': deadline})
        with Image.open(work / f'{base}-b0.png') as made:
            if say: say(json.dumps({'sheet': base}), flush=True)
            return np.asarray(made.convert('RGB'))

    for name in sorted(textures):
        times = textures[name].get('doubled')
        if times is None:
            continue
        require(times in (1, 2), f'{name}: a texture is doubled once or twice')
        old = np.ascontiguousarray(np.asarray(material.current(repo, textures[name].get('copy', name), stock=stock, **material.of_spec(spec)))[..., :3])
        source = hashlib.sha256(repr(old.shape).encode() + old.tobytes()).hexdigest(); target, record = folder / f'{name}.png', folder / f'{name}.json'
        if target.exists() or record.exists():
            was = json.loads(record.read_text(encoding='utf-8')) if record.is_file() else {}
            require(target.is_file() and was.get('source') == source and was.get('doubled') == times and was.get('upscaler') == reference.UPSCALER,
                    f'{target} was not made from the {name} the game draws now, doubled {times} times by {reference.UPSCALER}: take it and its record away and enlarge again')
            told[name] = 'kept'; continue
        todo[name] = (old, source, times)
    names = sorted(todo, key=lambda one: (todo[one][2], one))
    for start in range(0, len(names), group):
        part = names[start:start + group]; made = doubled({name: todo[name][0] for name in part}, send)
        again = {name: made[name] for name in part if todo[name][2] == 2}
        made.update(doubled(again, send) if again else {})
        for name in part:
            Image.fromarray(made[name]).save(folder / f'{name}.png')
            (folder / f'{name}.json').write_text(json.dumps({'kind': 'tilekit-enlarged', 'texture': name, 'source': todo[name][1], 'doubled': todo[name][2], 'upscaler': reference.UPSCALER}, indent=1) + '\n', encoding='utf-8')
            told[name] = 'enlarged'
        if say: say(json.dumps({'enlarged': start + len(part), 'of': len(names)}), flush=True)
    return told
