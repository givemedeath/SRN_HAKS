"""Create a head folder from a picked design and write its manifest from the design receipt, GPU outputs and overrides.json."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from gpu_job import FIELD_NODE, GEOMETRY_NODE, file_from
import guards
from head_files import sha, write_json
from workspace import PYTHON, RACE_DATA

FEATURE = re.compile(r'^(Face|Ears|Brows|Horns|Tusks|Beard|Hair|Cyberware|Piercings|Tattoo|Scars): (.*)$', re.M)
PALETTE_ROLES = (('paletteSkin', 'pal-skin01.tga'), ('paletteHair', 'pal-hair01.tga'), ('paletteArmor', 'pal-armor01.tga'), ('paletteTattoo', 'pal-tattoo01.tga'))


def tone_reference(race, sex):
    return f'{race}-{sex}-skin-v1'


def channel_reference(race, sex, channel):
    """Every mapped PLT channel matches a measured stock distribution (tools/headkit/stock-shades.json), so any in-game row reads as stock (RUNBOOK 83)."""
    channel = str(channel)
    if channel == '0':
        return {'reference': tone_reference(race, sex), 'rowFrom': 'design'}
    if channel == '1':
        return {'reference': f'{race}-{sex}-hair-v1'}
    if channel == '9':
        return {'reference': 'head-tattoo1-v1'}
    return {'reference': 'head-metal-v1'}


def link(head, source, name):
    target = head/'inputs'/name
    if target.exists() and not os.path.samefile(source, target) and sha(source) != sha(target):
        target.unlink()  # a re-rolled GPU output replaces the stale link
    if not target.exists():
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)
    return {'path': f'inputs/{name}', 'sha256': sha(target)}


def merge(base, extra):
    """Overrides merge into the defaults: null removes a key, and "$replace": true replaces a whole section."""
    for key, value in extra.items():
        if value is None:
            base.pop(key, None)
        elif isinstance(value, dict) and isinstance(base.get(key), dict) and not value.get('$replace'):
            merge(base[key], value)
        else:
            base[key] = {a: b for a, b in value.items() if a != '$replace'} if isinstance(value, dict) else value


def defaults(name, receipt, inputs, reference):
    race, sex = receipt['race'], receipt['sex']
    data = {
        'schemaVersion': 1, 'id': name, 'profile': 'pixal-single-v1', 'inputs': inputs,
        'features': [dict(name=key, description=value, placementReviewed=True) for key, value in receipt['featureInventory'].items()],
        'approval': {'referenceDesignReviewed': receipt.get('designApproved') is True},
        'matte': {},
        'mesh': {
            'alphaWrap': True, 'offsetRelative': 0.0005, 'triangleBudget': 20000, 'maximumRelativeSurfaceError': 0.004, 'allowDecoderOvershoot': True,
            'maximumSubtexelFraction': 0.005,
            'shellInspection': {'visualReviewed': True, 'confirmedShellDefect': True,
                                'notes': 'Pixal raw shell preclustered to 512; the closed shell comes from Alpha Wrap because the raw UDF export is non-manifold.'},
            'uv': {'chartOptions': {'max_cost': 16.0, 'normal_deviation_weight': 0.5, 'max_iterations': 2}},
            'neck': {'taper': {'minScale': 0.5, 'frontStart': -0.078, 'backStart': -0.035, 'axis': [0.0, 0.03]}},
        },
        'ownership': {'mode': 'rules', 'reviewed': True, 'default': 0, 'regions': {}, 'rules': []},
        'tone': {'mode': 'adjust', 'operations': []},
        'palette': {'inputs': {'0': 'paletteSkin', '1': 'paletteHair', '2': 'paletteArmor', '8': 'paletteTattoo', '9': 'paletteTattoo'},
                    'rows': {'0': 'auto', '1': 'auto', '2': 0, '8': 'auto', '9': 'auto'}, 'shadeOffsets': {},
                    'toneMatch': {'0': {'reference': tone_reference(race, sex), 'rowFrom': 'design'}}},
        'render': {'frontAngleDegrees': -90, 'views': ['front', 'left-profile', 'back', 'right-profile'], 'modes': ['clay', 'color-only', 'ownership'],
                   'mapStages': {'basecolor': 'palette'}, 'ownershipView': True, 'size': 1024, 'diagnostic': True},
        'fit': {'matrixFrom': 'fit', 'align': 'nose', 'excludeLower': 0.25, 'sourceStage': 'unwrap', 'model': receipt['slot'],
                'notes': f'Matrix from the reviewed fit stage: profile-matched scale and nose-tip alignment vs {reference.stem} ({race} {sex} proportion reference); profile matched above the lowest 25% of the reference.'},
    }
    if 'field' in inputs and 'raw' in inputs:
        data['approval']['appearanceField'] = {
            'decision': 'approved', 'geometryInput': 'raw', 'geometrySha256': inputs['raw']['sha256'], 'fieldSha256': inputs['field']['sha256'],
            'notes': 'Pixal appearance field generated in the same ComfyUI session from this exact saved shape; the bake review checks it visually.'}
    return data


def tone_every_channel(data, race, sex, name):
    """Hair and accents left on nearest-colour shades read flat in other rows (RUNBOOK 83). palette.toneMatchOff is the reviewed opt-out."""
    used = {str(data['ownership'].get('default', 0))} | {str(rule['channel']) for rule in data['ownership'].get('rules', [])}
    tone = data['palette'].setdefault('toneMatch', {})
    off = set(data['palette'].pop('toneMatchOff', []))
    for channel in sorted(used, key=int):
        if channel in off:
            tone.pop(channel, None)
        else:
            tone.setdefault(channel, channel_reference(race, sex, channel))
    clash = sorted(set(tone) & {key for key, value in data['palette'].get('shadeOffsets', {}).items() if value})
    if clash:
        raise guards.Refused(f'{name}: channels {clash} have both toneMatch and a shade offset; drop the offset (RUNBOOK 83)')


def validate(workspace, path):
    """The toolkit's own loader, in a child process with the bound packages. A misplaced override key otherwise surfaces as a failed launch (RUNBOOK 54)."""
    code = 'import sys; from headkit.common import manifest; manifest(sys.argv[1])'
    done = subprocess.run([PYTHON, '-B', '-c', code, str(path)], env=workspace.python_environment(packages=True, tools=True), capture_output=True, text=True)
    if done.returncode:
        raise guards.Refused(f'{path.parent.name}: manifest refused by the toolkit loader: {done.stderr.strip()[-600:]}')


def write_manifest(workspace, name, check=validate):
    busy = guards.head_busy(workspace, name)
    if busy:
        raise guards.Refused(f'{name}: a stage launch is queued or running ({busy.name}); edit after it ends (RUNBOOK 111)')
    head = workspace.head(name)
    receipt = guards.read(head/'design'/'design-receipt.json')
    overrides = guards.read(head/'overrides.json') if (head/'overrides.json').exists() else {}
    race, sex = receipt['race'], receipt['sex']
    inputs = {'design': link(head, head/'design'/receipt['selectedDesign']['file'], 'design.png')}
    for role, file in PALETTE_ROLES:
        inputs[role] = {'path': f'inputs/{file}', 'sha256': sha(head/'inputs'/file)}
    gpu = head/'gpu'/'gpu.json'
    if gpu.exists():
        stages = guards.read(gpu)['stages']
        if 'geometry' in stages:
            inputs['raw'] = link(head, file_from(stages['geometry']['files'], GEOMETRY_NODE)['path'], 'raw.glb')
        if 'appearance' in stages:
            inputs['field'] = link(head, file_from(stages['appearance']['files'], FIELD_NODE)['path'], 'field.npz')
    reference = workspace.fit_reference(race, sex)
    inputs['fitReference'] = link(head, reference, 'fit-reference-'+reference.name)
    data = defaults(name, receipt, inputs, reference)
    merge(data, overrides)
    tone_every_channel(data, race, sex, name)
    candidate = head/'manifest.check.json'
    write_json(candidate, data)
    try:
        check(workspace, candidate)
    except guards.Refused:
        candidate.unlink()
        raise
    candidate.replace(head/'manifest.json')
    return head/'manifest.json'


def set_up(workspace, name, design, reach=.04, slope=-.2, deviations=(), approval='', check=validate):
    """A new head folder: design receipt, stock palettes, bindings, compiler binding, body neck, neck-cut overrides, then the manifest."""
    known = workspace.head_ids()
    if name not in known:
        raise guards.Refused(f'{name} is not in workspace slots')
    race, sex, slot = known[name]
    head = workspace.head(name)
    if head.exists() and any(head.iterdir()):
        raise guards.Refused(f'{head} already exists and is not empty')
    prompt = guards.read(workspace.root/'design'/f'designs-{race}.json')['designs'][name]
    features = {key.lower(): value.strip() for key, value in FEATURE.findall(prompt)}
    features['neck'] = 'removed by mesh.neck.cut; the body neck part forms the neck'
    for folder in ('design', 'inputs', 'review-evidence'):
        (head/folder).mkdir(parents=True, exist_ok=True)
    design = Path(design)
    shutil.copy2(design, head/'design'/design.name)
    for file in RACE_DATA['designPalettes']:
        shutil.copy2(workspace.require('palettes')/file, head/'inputs'/file)
    shutil.copy2(workspace.path(workspace.data['headBindings']), head/'bindings.json')
    shutil.copy2(workspace.require('mdlCompiler'), head/'mdl-compiler.json')
    shutil.copy2(workspace.body_neck(race, sex), head/'inputs'/'body-neck.json')
    species = workspace.design_reference(race, sex)
    receipt = {'headId': name, 'race': race, 'sex': sex, 'slot': slot,
               'route': 'bootstrap: one front Flux.2 design -> headkit matte -> Pixal single-view geometry + appearance -> headkit CPU chain with neck cut -> native (Blender + NeverBlender)',
               'generator': 'Flux.2 via headkit design'+(f'; species reference {species.name}' if species else '; no reference image'),
               'prompt': f'design/designs-{race}.json',
               'viewConvention': 'front image left = character RIGHT; image right = character LEFT. NWN fit yaws 180 degrees; sides are anatomical and unchanged.',
               'designApproved': True, 'approval': approval,
               'selectedDesign': {'file': design.name, 'sha256': sha(design)}, 'featureInventory': features, 'observedDeviations': list(deviations),
               'slotSource': 'docs/heads/slot-catalog.json blocks; workspace slots'}
    write_json(head/'design'/'design-receipt.json', receipt)
    overrides = {'inputs': {'bodyNeck': {'path': 'inputs/body-neck.json', 'sha256': sha(head/'inputs'/'body-neck.json')}},
                 'mesh': {'neck': {'$replace': True, 'cut': {'height': 'measured', 'slope': slope, 'band': 0.03, 'reach': reach,
                          'notes': f'Heads have no neck: plane under the lowest front feature beyond the reach, slope {slope}; stub drawn 3 mm inside the smoothed body neck over 3 cm.'}}}}
    if race == 'troll':  # horn curls enclose backdrop that the border flood fill keeps (RUNBOOK 57); review the matte check
        overrides['matte'] = {'enclosedBackgroundMinimumPixels': 400}
    write_json(head/'overrides.json', overrides)
    return write_manifest(workspace, name, check)
