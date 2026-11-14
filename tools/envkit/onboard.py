"""Bringing a concept sheet into the kit: its set file, checked against the sheet and against the sheets before it.

A sheet packs a building and its props into one picture. `propose` finds what is drawn on it and numbers a box round
each; a spec names those boxes (`write_sets`); `crops_page` and `overlay` show the boxes against the sheet, to catch a
name on the wrong crop and a prop left without a box; `audit` checks every set mechanically; `type_page` and
`same_pages` put the props of a type, and each reused prop and the prop it reuses, side by side to judge which are
alike; and `revise` applies the decisions of such a review to the set files. Whatever is written is a set file as
`reference.load_set` reads it, in the one-asset-per-line layout of the sets (`layout`), and is accepted only when
`reference.register` accepts the whole folder with it.

These were one-off scripts when the 55 FRFZ sheets were onboarded (2026-11-11)."""
import collections
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

from . import reference, require

ORDER = ('kind', 'type', 'same', 'variant', 'unbranded', 'drawn', 'subject', 'box', 'cut', 'turn', 'notes')
# The names a sheet's own lettering uses: outside a sign, a prop that needs one is a branding variant (`reference.register`).
BRANDS = ('Ares|Mitsuhama|Renraku|Saeder|Shiawase|Evo|Wuxing|Horizon|NeoNET|DocWagon|Aztechnology|Lone Star|Knight Errant|PCC|ZDF|'
          'Council|UCAS|CAS|Sioux|Spiritech|Apex|Hargreaves|NABS|Ghostwalker|GridGuide|Denver Water|RTG|Chavez|Eagle|Mesametric|'
          'Warpdrive|Eclipse|Focused|Aurora Village|Ghost Riders|Koshari|Draco|The Hub|Penrose|UD|Centennial|2072|Chop Shop|'
          'Coffin Hotel|Stuffer|Casquilho|Denver FRFZ|T-Bird|DW|GG')
SIGNS = {'storefront-sign', 'pylon-sign', 'banner-set', 'neon-sign', 'billboard', 'schedule-board', 'graffiti-wall'}
MADE, REUSED, BUILDING = (255, 0, 255), (0, 170, 0), (0, 200, 255)


def layout(sheet, assets):
    """The text of a set file: the sheet, then one asset to a line with its keys in `ORDER`."""
    lines = [f'    {json.dumps(name)}: {json.dumps({**{key: asset[key] for key in ORDER if key in asset}, **{key: value for key, value in asset.items() if key not in ORDER}}, ensure_ascii=False)}'
             for name, asset in assets.items()]
    return ('{\n  "sheet": {\n    "file": ' + json.dumps(sheet['file']) + ',\n    "sha256": ' + json.dumps(sheet['sha256'])
            + ',\n    "size": ' + json.dumps(sheet['size']) + '\n  },\n  "assets": {\n' + ',\n'.join(lines) + '\n  }\n}\n')


def concept_sets(sets):
    """{name: set} of the concept sets in a folder; the game sets and plans that share it are passed over."""
    found = {}
    for path in sorted(Path(sets).glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data, dict) and 'sheet' in data:
            found[path.stem] = data
    return found


def _accepted(sets, texts):
    """Write set files, but only where the folder with them in it is one `reference.register` accepts."""
    sets = Path(sets)
    with tempfile.TemporaryDirectory() as scratch:
        trial = Path(scratch)
        for path in sets.glob('*.json'):
            shutil.copyfile(path, trial / path.name)
        for name, text in texts.items():
            (trial / f'{name}.json').write_bytes(text.encode('utf-8'))
        reference.register(trial)  # reads every set, and refuses a type shared without saying same or variant
    for name, text in texts.items():
        (sets / f'{name}.json').write_bytes(text.encode('utf-8'))


def _open(sheets, sheet):
    from PIL import Image
    with Image.open(reference.resolve_sheet(sheets, sheet)) as image:  # by name, and only at the hash the set records: its boxes are on that drawing
        return image.convert('RGB')


def _fitted(image, wide, high, enlarge=False):
    """The image scaled to lie within `wide` by `high`: made smaller to fit and, with `enlarge`, larger to fill."""
    scale = min(wide / image.width, high / image.height); scale = scale if enlarge else min(scale, 1.0)
    return image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))))


def propose(sheet, output, split=None):
    """Boxes round the things drawn on a sheet's light background, drawn numbered on `output`: T1.. for what lies above
    `split` (the building views, shown at half size) and P1.. for the prop set below it. `split` defaults to the bottom
    of the lowest wide or tall panel. Caption lettering is thin strokes and is passed over. Returns {size, split,
    boxes}: a proposal to name in a spec, where a box that cut a prop in two or took two for one is put right."""
    import numpy as np
    from PIL import Image, ImageDraw
    from scipy import ndimage
    with Image.open(sheet) as opened:
        image = opened.convert('RGB')
    pixels = np.asarray(image).astype(int); height, width = pixels.shape[:2]
    light = pixels.min(-1) > 200; require(light.any(), 'The sheet has no light background to find its drawings on: ' + str(sheet))
    paper = np.median(pixels[light], axis=0); ink = np.abs(pixels - paper).max(-1) > 28
    solid = ndimage.binary_opening(ink, np.ones((5, 5), bool))  # thin caption strokes go; drawn objects stay
    letters, _ = ndimage.label(solid)
    for index, found in enumerate(ndimage.find_objects(letters), 1):  # what is left of bold caption letters
        if found[0].stop - found[0].start < 20 and found[1].stop - found[1].start < 60:
            solid[found][letters[found] == index] = False
    labels, _ = ndimage.label(ndimage.binary_dilation(solid, np.ones((9, 9), bool))); boxes = []
    for index, found in enumerate(ndimage.find_objects(labels), 1):
        rows, columns = found; part = solid[found] & (labels[found] == index)
        if rows.stop - rows.start < 40 or columns.stop - columns.start < 40 or part.sum() < 1500:
            continue
        ys, xs = np.nonzero(part)
        boxes.append([columns.start + int(xs.min()), rows.start + int(ys.min()), columns.start + int(xs.max()) + 1, rows.start + int(ys.max()) + 1])
    joined = True
    while joined:  # the opening can split one object: boxes that overlap are one
        joined = False
        for a in range(len(boxes)):
            for b in range(a + 1, len(boxes)):
                p, q = boxes[a], boxes[b]
                if p[0] < q[2] and q[0] < p[2] and p[1] < q[3] and q[1] < p[3]:
                    boxes[a] = [min(p[0], q[0]), min(p[1], q[1]), max(p[2], q[2]), max(p[3], q[3])]; del boxes[b]; joined = True
                    break
            if joined:
                break
    margin = 4; boxes = [[max(0, b[0] - margin), max(0, b[1] - margin), min(width, b[2] + margin), min(height, b[3] + margin)] for b in boxes]
    if split is None:
        split = max([b[3] for b in boxes if b[2] - b[0] > 330 or b[3] - b[1] > 200], default=0)
    require(type(split) is int and 0 <= split <= height, 'The split is a row of the sheet')
    upper = sorted((b for b in boxes if b[1] < split), key=lambda b: (b[0] > width * 0.45, b[1]))
    lower = sorted((b for b in boxes if b[1] >= split), key=lambda b: (round((b[1] - split) / 110), b[0]))
    draw = ImageDraw.Draw(image); named = {}
    for letter, group in (('T', upper), ('P', lower)):
        for number, box in enumerate(group, 1):
            named[f'{letter}{number}'] = box; big = letter == 'T'
            draw.rectangle(box, outline=MADE, width=3 if big else 2)
            draw.rectangle([box[0], box[1], box[0] + (48 if big else 26), box[1] + (30 if big else 15)], fill=MADE)
            draw.text((box[0] + 3, box[1] + 2), f'{letter}{number}', fill=(255, 255, 255), font_size=24 if big else 11)
    page = Image.new('RGB', (width, split // 2 + height - split), (255, 255, 255))
    if split >= 2:
        page.paste(image.crop((0, 0, width, split)).resize((max(1, width // 2), split // 2)), (0, 0))
    page.paste(image.crop((0, split, width, height)), (0, split // 2))
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True); page.save(output)
    return {'size': [width, height], 'split': split, 'boxes': named}


def _relation(row, text, where):
    """`=set/asset` (the same as that prop), `~what differs` (a variant) or `~!what differs` (a variant drawn unbranded)."""
    require(text[:1] in ('=', '~') and text.lstrip('=~!').strip(), 'A relation is =set/asset or ~what differs: ' + where)
    if text.startswith('='):
        row['same'] = text[1:].strip()
    else:
        row['variant'] = text.lstrip('~!').strip()
        if text.startswith('~!'):
            row['unbranded'] = True


def _box(text, where):
    require(re.fullmatch(r'\d+( \d+){3}', ' '.join(text.split())) is not None, 'A box is x0 y0 x1 y1: ' + where)
    return [int(value) for value in text.split()]


def write_sets(spec, sheets, sets):
    """Write the set files a spec states, and refuse them where the folder with them is not one the kit accepts.

    A block starts `@ set-name NN`, NN being the number the sheet's file name starts with (`NN_*.png`). Each further
    line is `name | type | relation | subject | x0 y0 x1 y1 [| notes]`: type is B for a building view; relation is
    empty for the original of its type, or `=set/asset`, `~what differs` or `~!what differs` (`_relation`). A set that
    is there already is not written over: it is changed with `revise`. Returns {set: assets}."""
    from PIL import Image
    spec, sheets, sets = Path(spec), Path(sheets), Path(sets); blocks, current = {}, None
    for line in spec.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('@'):
            words = line.split(); require(len(words) == 3 and words[1] not in blocks, 'A block starts `@ set-name NN`, once for a set: ' + line)
            current = blocks[words[1]] = {'number': words[2], 'rows': []}
            continue
        parts = [part.strip() for part in line.split('|')]
        require(current is not None and len(parts) in (5, 6), 'A line is name | type | relation | subject | box [| notes], under its block: ' + line)
        current['rows'].append(parts)
    require(blocks, 'The spec states no set: ' + str(spec)); texts = {}
    taken = {data['sheet'].get('file'): name for name, data in concept_sets(sets).items() if isinstance(data['sheet'], dict)}
    for name, block in blocks.items():
        require(reference.NAME.fullmatch(name) is not None and not (sets / f'{name}.json').exists(), f'{name} is no new set name: an existing set is changed with revise')
        found = sorted(sheets.glob(block['number'] + '_*.png')); require(len(found) == 1, f'{name}: one sheet starts {block["number"]}_ and {len(found)} were found in {sheets}')
        require(found[0].name not in taken, f'{name}: {found[0].name} is the sheet of {taken.get(found[0].name)} already, and a sheet has one set'); taken[found[0].name] = name
        with Image.open(found[0]) as image:
            size = list(image.size)
        assets = {}
        for parts in block['rows']:
            asset, kind, relation, subject, box = parts[:5]; where = f'{name}/{asset}'
            require(asset not in assets, 'An asset is stated once: ' + where); row = {'kind': 'building' if kind == 'B' else 'prop'}
            if kind != 'B':
                row['type'] = kind
                if relation:
                    _relation(row, relation, where)
            else:
                require(not relation, 'A building view has no relation: ' + where)
            row['subject'] = subject; row['box'] = _box(box, where)
            if len(parts) == 6:
                row['notes'] = parts[5]
            assets[asset] = row
        texts[name] = layout({'file': found[0].name, 'sha256': hashlib.sha256(found[0].read_bytes()).hexdigest(), 'size': size}, assets)
    _accepted(sets, texts)
    return {name: len(block['rows']) for name, block in blocks.items()}


def revise(decisions, sets):
    """Apply the decisions of a review to the set files; nothing is written unless the folder is accepted with all of them.

        set/asset | action [| action ...]     the actions in order:
            =set/asset           the same as that prop
            ~text                a variant, with this line of what differs
            ~!text               a variant drawn unbranded
            ^                    the original of its type
            !                    drawn unbranded
            type name            another type
            box x0 y0 x1 y1      another crop box
        + set/asset | type | relation | subject | x0 y0 x1 y1     a prop the set missed (relation as in a spec)
        * old-type > new-type    a type renamed in every set

    Returns the sets that changed."""
    sets = Path(sets); todo, added, renames = {}, {}, {}
    for line in Path(decisions).read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('*'):
            names = [part.strip() for part in line[1:].split('>')]; require(len(names) == 2 and all(names), 'A rename is * old-type > new-type: ' + line)
            renames[names[0]] = names[1]
            continue
        parts = [part.strip() for part in line.split('|')]; key = parts[0].lstrip('+').strip()
        require(re.fullmatch(f'{reference.NAME.pattern}/{reference.NAME.pattern}', key) is not None, 'A decision starts with set/asset: ' + line)
        if parts[0].startswith('+'):
            require(len(parts) == 5 and key not in added, 'A prop is added once, as + set/asset | type | relation | subject | box: ' + line)
            row = {'kind': 'prop', 'type': parts[1]}
            if parts[2]:
                _relation(row, parts[2], key)
            added[key] = {**row, 'subject': parts[3], 'box': _box(parts[4], key)}
            continue
        require(key not in todo and len(parts) > 1 and all(parts[1:]), 'An asset is decided once, with an action at least: ' + line); todo[key] = parts[1:]
    found = concept_sets(sets); texts, done = {}, set()
    for name, data in found.items():
        assets = data['assets']
        for key, row in added.items():
            if key.split('/')[0] == name:
                require(key.split('/')[1] not in assets, 'The set has it already: ' + key); assets[key.split('/')[1]] = row; done.add(key)
        for asset_name, asset in assets.items():
            key = f'{name}/{asset_name}'
            if asset.get('type') in renames:
                asset['type'] = renames[asset['type']]
            for action in todo.get(key, []):
                done.add(key); require(asset['kind'] == 'prop' or action.startswith('box '), 'A building view has its box alone to change: ' + key)
                if action.startswith('box '):
                    asset['box'] = _box(action[4:], key)
                elif action.startswith('type '):
                    require(len(action.split()) == 2, 'A type is one word: ' + key); asset['type'] = action.split()[1]
                elif action == '^':
                    asset.pop('same', None); asset.pop('variant', None)
                elif action == '!':
                    asset['unbranded'] = True
                else:
                    require(action[:1] in ('=', '~'), f'No such action as `{action}` (=set/asset, ~text, ~!text, ^, !, type name, box x0 y0 x1 y1): {key}')
                    asset.pop('same', None); asset.pop('variant', None)
                    if action.startswith('=') or action.lstrip('~').startswith(reference.BRANDING):  # neither is drawn unbranded
                        asset.pop('unbranded', None)
                    _relation(asset, action, key)
            if 'same' in asset:
                asset.pop('unbranded', None)
        text = layout(data['sheet'], assets)
        if text.encode('utf-8') != (sets / f'{name}.json').read_bytes():
            texts[name] = text
    missing = sorted((set(todo) | set(added)) - done); require(not missing, 'No such asset, or no such set to add to: ' + ', '.join(missing))
    _accepted(sets, texts)
    return sorted(texts)


def crops_page(set_path, sheets, output):
    """One picture of every crop of a set, each under its asset name: is each name on the crop it means?"""
    from PIL import Image, ImageDraw
    data = reference.load_set(set_path); sheet = _open(sheets, data['sheet']); cells = []
    for name, asset in data['assets'].items():
        limit = 300 if asset['kind'] == 'building' else 150; cells.append((name, _fitted(sheet.crop(tuple(asset['box'])), limit, limit)))
    width, x, y, row, places = 1400, 4, 4, 0, []
    for name, crop in cells:
        wide = max(crop.width, 7 * len(name)) + 8
        if x + wide > width:
            x, y, row = 4, y + row + 18, 0
        places.append((name, crop, x, y)); x += wide; row = max(row, crop.height)
    page = Image.new('RGB', (width, y + row + 18), (255, 255, 255)); draw = ImageDraw.Draw(page)
    for name, crop, x, y in places:
        page.paste(crop, (x, y)); draw.rectangle([x, y, x + crop.width - 1, y + crop.height - 1], outline=MADE); draw.text((x, y + crop.height + 2), name, fill=(0, 0, 0))
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True); page.save(output)
    return len(cells)


def overlay(sets, sheets, prefix):
    """Every sheet with its boxes drawn on it, four sheets to a page `<prefix>-NN.png`, to spot a prop without a box.
    Magenta: a prop that is made. Green: a prop that reuses another. Cyan: a building view. Returns the pages."""
    from PIL import Image, ImageDraw
    cells, pages = [], []
    for name, data in concept_sets(sets).items():
        image = _open(sheets, data['sheet']); scale = 760 / image.width; image = image.resize((760, int(image.height * scale))); draw = ImageDraw.Draw(image)
        for asset in data['assets'].values():
            colour = BUILDING if asset['kind'] == 'building' else REUSED if 'same' in asset else MADE
            draw.rectangle([int(value * scale) for value in asset['box']], outline=colour, width=2)
        title = f'{data["sheet"]["file"][:2]} {name}'; draw.rectangle([0, 0, 7 * len(title) + 8, 14], fill=(255, 255, 0)); draw.text((3, 2), title, fill=(0, 0, 0))
        cells.append((data['sheet']['file'], image))
    require(cells, 'No concept sets in ' + str(sets)); cells.sort(key=lambda cell: cell[0]); Path(prefix).parent.mkdir(parents=True, exist_ok=True)
    for start in range(0, len(cells), 4):
        group = [image for _, image in cells[start:start + 4]]; high = max(image.height for image in group)
        page = Image.new('RGB', (1520, high * ((len(group) + 1) // 2)), (255, 255, 255))
        for index, image in enumerate(group):
            page.paste(image, (760 * (index % 2), high * (index // 2)))
        pages.append(f'{prefix}-{start // 4 + 1:02d}.png'); page.save(pages[-1])
    return pages


def audit(sets, sheets):
    """What a reading of the sets would not catch, as {finding: [rows]}: a set the kit would refuse (told, and not
    audited further), a sheet that is missing, changed or in two sets, a sheet without a set, a key stated twice, a
    tiny box, prop boxes that overlap by more than a tenth of the smaller (told `noted` where either says so in its
    notes), text that is untidy or not in the form of the rest, a brand word in a prop that is neither a sign nor a
    branding variant, and the types only one prop has."""
    from PIL import Image
    sets, sheets = Path(sets), Path(sheets); out = collections.defaultdict(list); seen, props, refused = collections.defaultdict(list), {}, set()
    brand = re.compile(r'\b(' + BRANDS + r')\b')

    def pairs(items):
        keys = [key for key, _ in items]; twice.update(key for key in keys if keys.count(key) > 1)
        return dict(items)

    for path in sorted(sets.glob('*.json')):
        twice = set(); data = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs)
        if not isinstance(data, dict) or 'sheet' not in data:
            continue
        out['key stated twice'] += [f'{path.stem}: {key}' for key in sorted(twice)]
        try:  # what follows reads a set as the kit does: one it would refuse is told, and the rest are still audited
            reference.load_set(path)
        except (ValueError, KeyError, TypeError) as error:
            out['set refused'].append(f'{path.stem}: {error!r}' if not isinstance(error, ValueError) else f'{path.stem}: {error}')
            if isinstance(data['sheet'], dict) and isinstance(data['sheet'].get('file'), str):
                refused.add(data['sheet']['file'])  # its sheet has a set, such as it is
            continue
        name, sheet = path.stem, data['sheet']; seen[sheet['file']].append(name); file = sheets / sheet['file']
        if not file.is_file():
            out['sheet missing'].append(name)
        else:
            if hashlib.sha256(file.read_bytes()).hexdigest() != sheet['sha256']:
                out['sheet differs from the set'].append(name)
            with Image.open(file) as image:
                if list(image.size) != sheet['size']:
                    out['size differs'].append(f'{name} {list(image.size)} {sheet["size"]}')
        assets = data['assets']; boxes = []
        if 'building-hero' not in assets:
            out['no building-hero'].append(name)
        for key, asset in assets.items():
            x0, y0, x1, y1 = asset['box']
            if min(x1 - x0, y1 - y0) < 30:
                out['tiny box'].append(f'{name}/{key} {x1 - x0}x{y1 - y0}')
            if asset['kind'] == 'prop':
                boxes.append((key, asset['box'])); props[f'{name}/{key}'] = asset
            text = [('subject', asset['subject'])] + [(field, asset[field]) for field in ('variant', 'notes') if field in asset]
            for field, value in text:
                if value != value.strip() or '  ' in value or not value.isascii():
                    out['untidy text'].append(f'{name}/{key} {field}: {value!r}')
                if field != 'subject' and not value.rstrip().endswith('.'):
                    out['no full stop'].append(f'{name}/{key} {field}: {value}')
                if field == 'subject' and value and (value.endswith('.') or value[0].isupper() and not brand.match(value)):
                    out['subject form'].append(f'{name}/{key}: {value}')
            if asset['kind'] == 'prop' and asset['type'] not in SIGNS and not asset.get('variant', '').startswith(reference.BRANDING):
                out['brand word in an unbranded prop'] += [f'{name}/{key} [{asset["type"]}] {field}: {value}' for field, value in text if field != 'notes' and brand.search(value)]
            if 'same' in asset and 'notes' in asset:
                out['same with notes'].append(f'{name}/{key}: {asset["notes"]}')
            if key == 'building-hero' and 'notes' not in asset:
                out['hero without notes'].append(name)
        for index, (first, a) in enumerate(boxes):
            for second, b in boxes[index + 1:]:
                wide, high = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
                small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
                if wide > 0 and high > 0 and wide * high / small > 0.10:
                    noted = 'noted' if 'notes' in assets[first] or 'notes' in assets[second] else 'NO NOTE'
                    out['prop boxes overlap'].append(f'{name}: {first} / {second} {round(100 * wide * high / small)}% {noted}')
    out['sheet in two sets'] += [f'{file}: {", ".join(names)}' for file, names in seen.items() if len(names) > 1]
    out['sheets without a set'] += sorted(path.name for path in sheets.glob('*.png') if path.name not in seen and path.name not in refused)
    types = collections.Counter(asset['type'] for asset in props.values()); out['types of one prop'] += sorted(kind for kind, count in types.items() if count == 1)
    return {'sets': sum(len(names) for names in seen.values()), 'props': len(props), 'findings': {title: rows for title, rows in out.items() if rows}}


def type_page(sets, sheets, output, types):
    """One picture of every made prop of some types, each under set/asset and its state (O original, V variant, B
    branding variant), to judge which are alike. A prop that is the `same` as another is not drawn."""
    from PIL import Image, ImageDraw
    found = concept_sets(sets); cells, images = [], {}; require(types, 'Name a type at least')
    for kind in types:
        cells.append((f'## {kind}', None)); before = len(cells)
        for name, data in found.items():
            for asset_name, asset in data['assets'].items():
                if asset.get('type') != kind or 'same' in asset:
                    continue
                if name not in images:
                    images[name] = _open(sheets, data['sheet'])
                state = 'B' if asset.get('variant', '').startswith(reference.BRANDING) else 'V' if 'variant' in asset else 'O'
                cells.append((f'{name[:16]}/{asset_name[:16]} {state}', _fitted(images[name].crop(tuple(asset['box'])), 1400, 130, enlarge=True)))  # one height to compare at, but never off the page
        require(len(cells) > before, 'No made prop is of type ' + kind)
    width, x, y, places = 1500, 4, 4, []
    for label, crop in cells:
        if crop is None:
            y += 150 if x > 4 else 0; places.append((label, None, 4, y)); x, y = 4, y + 16
            continue
        wide = max(crop.width, 6 * len(label)) + 8
        if x + wide > width:
            x, y = 4, y + 150
        places.append((label, crop, x, y)); x += wide
    page = Image.new('RGB', (width, y + 150), (255, 255, 255)); draw = ImageDraw.Draw(page)
    for label, crop, x, y in places:
        if crop is None:
            draw.text((x, y), label, fill=(200, 0, 0)); continue
        page.paste(crop, (x, y)); draw.text((x, y + 132), label, fill=(0, 0, 0))
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True); page.save(output)
    return sum(crop is not None for _, crop in cells)


ROW = 8  # crops to a row of the reuse pages


def reuse_rows(target, reuses):
    """The rows of the reuse pages for one made prop: each starts with it, then as many of the props that reuse it as
    the row has room for. A row that runs on starts with it again, so that what is judged is beside what it is judged
    against, whichever page it lands on (Codex on PR #127, 2026-11-12: the shipped sets have two props reused eight
    times and more)."""
    return [[target, *reuses[start:start + ROW - 1]] for start in range(0, len(reuses), ROW - 1)]


def same_pages(sets, sheets, prefix, only=()):
    """Each reused prop beside the prop it reuses, to judge that they are alike: a row starts with the made prop (red
    frame) and goes on with props that say they are the same, as many rows as they fill (`reuse_rows`). `only` limits the rows to props of those sets, made or
    reusing. Pages `<prefix>-NN.png`. Returns {targets, reuses, pages}."""
    from PIL import Image, ImageDraw
    props, images = {}, {}
    for name, data in concept_sets(sets).items():
        props.update({f'{name}/{asset_name}': (name, data['sheet'], asset) for asset_name, asset in data['assets'].items() if asset['kind'] == 'prop'})

    def crop(key):
        name, sheet, asset = props[key]
        if name not in images:
            images[name] = _open(sheets, sheet)
        return _fitted(images[name].crop(tuple(asset['box'])), 170, 100)

    groups = collections.defaultdict(list)
    for key, (_, _, asset) in props.items():
        if 'same' in asset:
            require(asset['same'] in props, f'{key} is the same as {asset["same"]}, which no set has'); groups[asset['same']].append(key)
    if only:
        groups = {target: keys for target, keys in groups.items() if {key.split('/')[0] for key in [target, *keys]} & set(only)}
    require(groups, 'No prop reuses another' + (' in ' + ', '.join(only) if only else '')); rows, pages = [], []
    for target in sorted(groups, key=lambda key: (props[key][2]['type'], key)):
        rows += [(target, keys) for keys in reuse_rows(target, groups[target])]
    Path(prefix).parent.mkdir(parents=True, exist_ok=True)
    for start in range(0, len(rows), 11):
        page = rows[start:start + 11]; sheet = Image.new('RGB', (1500, 124 * len(page)), (255, 255, 255)); draw = ImageDraw.Draw(sheet)
        for y, (target, keys) in enumerate(page):
            for x, key in enumerate(keys):
                cut = crop(key); left, top = 4 + x * 186, 2 + y * 124; sheet.paste(cut, (left, top))
                if key == target:
                    draw.rectangle([left, top, left + cut.width, top + cut.height], outline=(255, 0, 0), width=2)
                draw.text((left, top + 104), key.split('/')[0][:14] + '/' + key.split('/')[1][:13], fill=(0, 0, 0))
        pages.append(f'{prefix}-{start // 11 + 1:02d}.png'); sheet.save(pages[-1])
    return {'targets': len(groups), 'reuses': sum(len(keys) for keys in groups.values()), 'pages': pages}
