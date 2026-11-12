"""Reference images: one clean, isolated view per asset, edited from a concept-sheet crop by the local Qwen 2.1 profile.

A concept sheet packs a building and its props into one picture, each too small and too dressed (captions, wet ground,
neon spill) to hand to a 3D generator. A set file names the crop of each asset; `make` redraws that crop alone on white.
Outputs are proposals for human review: nothing here approves a reference or spends generation credits."""
import hashlib
import json
import re
import time
import uuid
from pathlib import Path

from . import require

PROFILE = 'qwen21-int8-v1'
NAME = re.compile(r'[a-z0-9][a-z0-9-]{0,63}')
KIN = {'type', 'same', 'variant', 'unbranded'}
BRANDING = 'Branding:'
QUEUE_LOOK = 30.0  # seconds between looks at the shared ComfyUI's queue while a run waits for it
CUT_MARGIN = 0.08  # of the longer side: the white set round a piece of a building before it is redrawn
# Type names that turned out to mean a type already in use (review of 2026-11-11). Two names for one kind of prop hide
# its repeats from the register, so a retired name is refused with the name to use.
RETIRED = {'atm': 'pay-kiosk', 'crate-stack': 'pallet-stack', 'cyberware-cabinet': 'storage-cabinet', 'desk-terminal': 'console-desk',
           'drink-case': 'fridge', 'floor-cache': 'floor-hatch', 'folding-table': 'table-and-chairs', 'freezer': 'fridge',
           'goods-rack': 'shelf-unit', 'junction-box': 'power-cabinet', 'ladder-hatch': 'floor-hatch', 'recycle-bin': 'trash-can',
           'secure-door': 'door', 'service-door': 'door', 'stash-cabinet': 'storage-cabinet', 'waiting-seats': 'bench'}
LEAD = {
    'prop': 'Redraw this {subject} as a clean, sharp, high-resolution reference image for 3D modelling. '
            'Keep exactly the same design, colours, proportions, markings and viewing angle.',
    # A prop that serves several locations is drawn on its sheet with one location's mark. "Keep the markings" and a note
    # to leave the logo off pulled against each other, so the unbranded prop has a lead of its own.
    'unbranded': 'Redraw this {subject} as a clean, sharp, high-resolution reference image for 3D modelling. '
                 'Keep exactly the same design, colours, proportions and viewing angle, but leave off every company logo, '
                 'emblem and brand name. Hazard stripes, warning signs and plain labels stay.',
    'building': 'Redraw this {subject} as a clean, sharp, high-resolution reference image for 3D modelling. '
                'Keep exactly the same architecture, colours, proportions, signage and viewing angle. '
                # The props drawn against the walls and the pavement slab under them stay on the building (user,
                # 2026-11-10: the props make dressing areas faster; "we should keep the slab").
                'Keep the pavement slab the building stands on, and the fixtures and street furniture on it, such as '
                'bollards, bins and rubbish bags, exactly where they are. Remove the road beyond the slab, the puddles, '
                'the reflections and the loose litter.',
}
# Left to itself the edit tidies: the first Stuffer Shack pass came back with near-white walls (user, 2026-11-10: "it does
# look too clean"). The wear is part of the design, so every prompt asks for it by name.
WEAR = ('Keep the grime, stains, rust streaks, scratches, worn paint and graffiti exactly as dirty as in the source; '
        'do not clean or repaint anything.')
# Lit parts keep their colour because the emissive texture is taken from it; the spill is removed because a generator
# bakes it into the neighbouring surfaces.
RULES = ('Show the whole object centred with a clear margin on a plain white background. Even, flat, neutral lighting. '
         'Signs, screens and lamps keep their own colours, but nothing glows, blooms or casts coloured light on other '
         'surfaces. No cast shadow, no ground, no people, no captions or text outside the object.')


def prompt(kind, subject, notes='', unbranded=False):
    require(kind in ('prop', 'building'), 'Asset kind must be one of: building, prop')
    require(isinstance(subject, str) and subject.strip() and '\n' not in subject, 'Subject must be one line of text')
    require(isinstance(notes, str), 'Notes must be text')
    require(unbranded is False or unbranded is True and kind == 'prop', 'Only a prop is drawn unbranded')
    lead = LEAD['unbranded' if unbranded else kind]
    return ' '.join(part for part in (lead.format(subject=subject.strip()), WEAR, notes.strip(), RULES) if part)


def load_set(path):
    """A set is one concept sheet (file name and SHA-256, never a machine path) and the crop box of each asset on it."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    require(isinstance(data, dict) and set(data) == {'sheet', 'assets'}, 'A set has exactly sheet and assets')
    sheet = data['sheet']
    require(isinstance(sheet, dict) and set(sheet) == {'file', 'sha256', 'size'} and Path(sheet['file']).name == sheet['file']
            and re.fullmatch(r'[0-9a-f]{64}', str(sheet['sha256'])) is not None, 'Sheet needs a bare file name, sha256 and size')
    width, height = sheet['size']
    require(isinstance(data['assets'], dict) and data['assets'], 'A set needs assets')
    for name, asset in data['assets'].items():
        require(NAME.fullmatch(name) is not None, 'Asset names must be safe IDs: ' + name)
        require(isinstance(asset, dict) and {'kind', 'subject', 'box'} <= set(asset) <= {'kind', 'subject', 'box', 'notes', 'cut', *KIN},
                'Asset needs kind, subject and box: ' + name)
        require(asset['kind'] == 'prop' or not KIN & set(asset), 'Only props have a type: ' + name)
        if 'cut' in asset:  # a piece of a building, drawn from its whole view's chosen reference (`cut_box`)
            cut = asset['cut']; whole = data['assets'].get(cut['from']) if isinstance(cut, dict) and isinstance(cut.get('from'), str) else None
            require(asset['kind'] == 'building' and isinstance(cut, dict) and set(cut) == {'from', 'box'} and whole is not None
                    and whole['kind'] == 'building' and 'cut' not in whole, 'A cut is a building view drawn from another, whole, view of the set: ' + name)
            require(isinstance(cut['box'], list) and len(cut['box']) == 4 and all(type(v) is int for v in cut['box'])
                    and 0 <= cut['box'][0] < cut['box'][2] and 0 <= cut['box'][1] < cut['box'][3], 'A cut states its box in pixels of that view\'s reference: ' + name)
        prompt(asset['kind'], asset['subject'], asset.get('notes', ''), asset.get('unbranded', False))
        if asset['kind'] == 'prop':
            require(NAME.fullmatch(str(asset.get('type'))) is not None, 'A prop needs a type: ' + name)
            require(asset['type'] not in RETIRED, f'Type {asset["type"]} is now {RETIRED.get(asset["type"])}: {name}')
            require(not {'same', 'variant'} <= set(asset), 'A prop is the same as another or a variant, not both: ' + name)
            require('same' not in asset or re.fullmatch(f'{NAME.pattern}/{NAME.pattern}', str(asset['same'])) is not None,
                    'same names another prop as set/asset: ' + name)
            require('variant' not in asset or isinstance(asset['variant'], str) and asset['variant'].strip()
                    and '\n' not in asset['variant'], 'variant says in one line what differs: ' + name)
            require('unbranded' not in asset or 'same' not in asset and not str(asset.get('variant', '')).startswith(BRANDING),
                    'unbranded is for a prop that is made and does not carry its location\'s branding: ' + name)
        box = asset['box']
        require(isinstance(box, list) and len(box) == 4 and all(type(v) is int for v in box)
                and 0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height, 'Crop box is outside the sheet: ' + name)
    return data


def register(folder):
    """Every prop of every concept set in a folder, by type, so that a sheet's props are checked against the sheets before
    it. The sheets repeat themselves (most draw a camera, a fence, crates, a rooftop unit), so one prop of a type is its
    original and every other one says which it is: `same` (the named prop serves and nothing is made) or `variant` (a
    design of its own, with what differs). A type shared without saying so is refused.

    Branding (user, 2026-11-11): a prop that needs its location's name, emblem or livery is a variant even where the object
    is otherwise the same, and its line starts `Branding:`. That is for signs, banners, reception desks, guard booths,
    vehicle gates and cases, "not every possible logo or text that showed up": kiosks, lockers, fences, rooftop units,
    barriers and other utility gear are one prop for every location, drawn `unbranded` where the sheet shows a mark.
    Adobe-patterned and scrap-built pieces stay variants of their own as a regional style."""
    props = {}
    for path in sorted(Path(folder).glob('*.json')):
        if 'sheet' in json.loads(path.read_text(encoding='utf-8')):  # game sets share the folder
            props.update({f'{path.stem}/{name}': asset for name, asset in load_set(path)['assets'].items() if asset['kind'] == 'prop'})
    types = {}
    for key, asset in props.items():
        role = 'same' if 'same' in asset else 'variant' if 'variant' in asset else 'original'
        types.setdefault(asset['type'], {'original': [], 'variant': [], 'same': []})[role].append(key)
    for kind, rows in types.items():
        require(len(rows['original']) == 1, f'Type {kind} needs one original; the others say same or variant: '
                + ', '.join(rows['original'] or rows['variant'] + rows['same']))
        for key in rows['same']:
            target = props.get(props[key]['same'])
            require(target is not None and target['type'] == kind and 'same' not in target,
                    f'{key} is the same as {props[key]["same"]}, which is not a made prop of type {kind}')
    return {'types': dict(sorted(types.items())), 'make': sum(len(r['original']) + len(r['variant']) for r in types.values()),
            'reuse': sum(len(r['same']) for r in types.values())}


def resolve_sheet(sheets, sheet):
    """The sheet as bytes on this machine: found by name in the given folder and accepted only at the recorded hash."""
    path = Path(sheets) / sheet['file']
    require(path.is_file(), 'Concept sheet not found: ' + str(path))
    require(hashlib.sha256(path.read_bytes()).hexdigest() == sheet['sha256'], 'Concept sheet differs from the set: ' + path.name)
    return path


def crop(sheet_path, box, output):
    from PIL import Image
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(sheet_path) as image:
        require(box[2] <= image.width and box[3] <= image.height, f'The box {box} runs off {Path(sheet_path).name} ({image.width} x {image.height})')
        image.convert('RGB').crop(tuple(box)).save(output)
    return output


def source(data, name, sheet, selected, output):
    """The picture an asset is redrawn from, written to `output`: its box on the sheet, or for a cut (a piece of a
    building too large for one generator texture, user 2026-11-12) its box on the chosen reference of the whole view,
    so that the pieces keep the one drawing's proportions and colours between them."""
    asset = data['assets'][name]
    if 'cut' not in asset:
        return crop(sheet, asset['box'], output)
    from PIL import Image
    from .sheet import image
    output = crop(image(selected, asset['cut']['from']), asset['cut']['box'], output)
    # Set on white with a margin all round: a wall running off the picture was redrawn running off it, where the cut was
    # to be closed (two of the yard's six pieces on their first seed, 2026-11-12).
    with Image.open(output) as piece:
        margin = round(max(piece.size) * CUT_MARGIN); framed = Image.new('RGB', (piece.width + 2 * margin, piece.height + 2 * margin), 'white')
        framed.paste(piece, (margin, margin))
    framed.save(output)
    return output


def wait_for_queue(client, limit, *, sleep=time.sleep, clock=time.monotonic):
    """Wait up to `limit` seconds for the shared ComfyUI's queue to empty, looking every QUEUE_LOOK seconds; returns
    whether it did. Another job may still come in before ours: `make` looks again and refuses then. The Saeder-Krupp
    yard's references were made one asset at a time so, while other kits used the same queue (2026-11-12)."""
    deadline = clock() + limit
    while True:
        queue = client.request('/queue')
        if not queue.get('queue_running') and not queue.get('queue_pending'):
            return True
        if clock() >= deadline:
            return False
        sleep(min(QUEUE_LOOK, max(deadline - clock(), 0.0)))


def make(client, local, bindings_path, name, text, reference, seed, output, *, batch=1, deadline=2400):
    """One edit job on the bound local ComfyUI. Submission waits in headkit.shared_comfy.slot for the GPU lease and an
    idle queue, so another session's job finishes first and is left alone."""
    from tools.headkit import design
    require(NAME.fullmatch(name) is not None, 'Asset names must be safe IDs: ' + str(name))
    reference = Path(reference); token = uuid.uuid4().hex; base = f'{name}-s{seed}'
    staged = 'reference-0' + reference.suffix.lower()
    require(not (Path(output) / f'{base}.json').exists(), 'Receipt already exists; use another seed or output folder')
    Path(output).mkdir(parents=True, exist_ok=True)
    graph = design.compile_design(text, [f'{design.SUBFOLDER}/{token}/{staged}'], seed, batch,
                                  f'{design.SUBFOLDER}/{token}/{base}', profile=PROFILE)
    receipt = {'schemaVersion': 1, 'kind': 'envkit-reference', 'proposalOnly': True, 'reviewRequired': True, 'asset': name,
               'prompt': text, 'seed': seed, 'batch': batch, 'profile': PROFILE, 'settings': dict(design.PROFILES[PROFILE]),
               'token': token, 'outputPrefix': graph['9']['inputs']['filename_prefix']}
    return design._execute(client, local, bindings_path, graph, receipt, {staged: reference}, output, base, batch, None,
                           queue={'deadline': deadline})
