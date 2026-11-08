"""Create a head folder from a picked design and write its manifest from the design receipt, GPU outputs and overrides.json."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess

from gpu_job import FIELD_NODE, GEOMETRY_NODE, file_from, link_or_copy
import guards
from head_files import sha, write_json
from workspace import PYTHON, RACE_DATA, prefix
import reference_record

FEATURE = re.compile(r'^(Face|Ears|Brows|Horns|Tusks|Beard|Hair|Cyberware|Piercings|Tattoo|Scars): (.*)$', re.M)
SETUP_MARKER = '.setup-incomplete'
PALETTE_ROLES = (('paletteSkin', 'pal-skin01.tga'), ('paletteHair', 'pal-hair01.tga'), ('paletteArmor', 'pal-armor01.tga'), ('paletteArmor2', 'pal-armor02.tga'), ('paletteTattoo', 'pal-tattoo01.tga'))


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
        # Troll/orc tattoo2 is bone; design ink stays on skin (RUNBOOK 219).
        return {'reference': 'head-metal-v1' if race in ('troll', 'orc') else 'head-tattoo1-v1'}
    return {'reference': 'head-metal-v1'}


def link(head, source, name, replaced):
    """The input named for the manifest. The loader checks it against the bytes it finds, so a re-rolled GPU output goes in first; the old file waits in replaced until the manifest passes."""
    target = head/'inputs'/name
    if target.exists() and not os.path.samefile(source, target) and sha(source) != sha(target):
        held = target.with_name(target.name+'.replaced')
        target.replace(held)
        replaced.append((held, target))
    if not target.exists():
        link_or_copy(source, target)
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


def route_declarations(inputs):
    """What the toolkit loader needs stated before this route has produced anything to look at. They declare the route, and nobody has looked at this
    head yet: each is checked at a later visual gate. shellInspection: the shell review of the repair. appearanceField: the bake review. Ownership
    `reviewed`: the ownership review of its rules. placementReviewed: the design pick, and the `setup --approval` a person gave for it."""
    data = {'shellInspection': {'visualReviewed': True, 'confirmedShellDefect': True,
                                'notes': 'Route declaration, reviewed at the repair gate: Pixal raw shell preclustered to 512; the closed shell comes from Alpha Wrap because the raw UDF export is non-manifold.'}}
    if 'field' in inputs and 'raw' in inputs:
        data['appearanceField'] = {
            'decision': 'approved', 'geometryInput': 'raw', 'geometrySha256': inputs['raw']['sha256'], 'fieldSha256': inputs['field']['sha256'],
            'notes': 'Route declaration, reviewed at the bake gate: Pixal appearance field generated in one ComfyUI session from this exact saved shape.'}
    return data


def defaults(name, receipt, inputs, reference):
    race, sex = receipt['race'], receipt['sex']
    declared = route_declarations(inputs)
    data = {
        'schemaVersion': 1, 'id': name, 'profile': 'pixal-single-v1', 'inputs': inputs,
        'features': [dict(name=key, description=value, placementReviewed=True) for key, value in receipt['featureInventory'].items()],
        'approval': {'referenceDesignReviewed': receipt.get('designApproved') is True},
        'matte': {},
        'mesh': {
            'alphaWrap': True, 'offsetRelative': 0.0005, 'triangleBudget': 20000, 'maximumRelativeSurfaceError': 0.004, 'allowDecoderOvershoot': True,
            'maximumSubtexelFraction': 0.005,
            'shellInspection': declared['shellInspection'],
            'uv': {'chartOptions': {'max_cost': 16.0, 'normal_deviation_weight': 0.5, 'max_iterations': 2}},
            'neck': {'taper': {'minScale': 0.5, 'frontStart': -0.078, 'backStart': -0.035, 'axis': [0.0, 0.03]}},
        },
        'ownership': {'mode': 'rules', 'reviewed': True, 'default': 0, 'regions': {}, 'rules': []},
        'tone': {'mode': 'adjust', 'operations': []},
        'palette': {'inputs': {'0': 'paletteSkin', '1': 'paletteHair', '2': 'paletteArmor', '3': 'paletteArmor2', '8': 'paletteTattoo', '9': 'paletteTattoo'},
                    'rows': {'0': 'auto', '1': 'auto', '2': 0, '3': 0, '8': 'auto', '9': 'auto'}, 'shadeOffsets': {},
                    'toneMatch': {'0': {'reference': tone_reference(race, sex), 'rowFrom': 'design'}}},
        'render': {'frontAngleDegrees': -90, 'views': ['front', 'left-profile', 'back', 'right-profile'], 'modes': ['clay', 'color-only', 'ownership'],
                   'mapStages': {'basecolor': 'palette'}, 'ownershipView': True, 'size': 1024, 'diagnostic': True},
        'fit': {'matrixFrom': 'fit', 'align': 'nose', 'excludeLower': 0.25, 'sourceStage': 'unwrap', 'model': receipt['slot'],
                'notes': f'Matrix from the reviewed fit stage: profile-matched scale and nose-tip alignment vs {reference.stem} ({race} {sex} proportion reference); profile matched above the lowest 25% of the reference.'},
    }
    if 'appearanceField' in declared:
        data['approval']['appearanceField'] = declared['appearanceField']
    return data


def tone_every_channel(data, race, sex, name):
    """Hair and accents left on nearest-colour shades read flat in other rows (RUNBOOK 83). palette.toneMatchOff is the reviewed opt-out."""
    used = {str(data['ownership'].get('default', 0))} | {str(rule['channel']) for rule in data['ownership'].get('rules', [])}
    if data['ownership'].get('featureChannels'):
        # Non-iris legacy tattoo1 rules become tattoo2; generated iris texels alone do not (RUNBOOK 243).
        if '8' in used:
            used.add('9')
        used.update(('1', '8'))
    tone = data['palette'].setdefault('toneMatch', {})
    off = set(data['palette'].pop('toneMatchOff', []))
    for channel in sorted(used, key=int):
        if channel in off:
            tone.pop(channel, None)
        else:
            tone.setdefault(channel, channel_reference(race, sex, channel))
    rows = data['palette'].get('rows')
    if data['ownership'].get('mode') == 'rules' and isinstance(rows, dict):
        for channel, row in rows.items():  # no rule, no pixels, and 'auto' cannot rank an empty channel (RUNBOOK 44, 74)
            if row == 'auto' and channel not in used and channel not in tone:
                rows[channel] = 0
    clash = sorted(set(tone) & {key for key, value in data['palette'].get('shadeOffsets', {}).items() if value})
    if clash:
        raise guards.Refused(f'{name}: channels {clash} have both toneMatch and a shade offset; drop the offset (RUNBOOK 83)')


def validate(workspace, path):
    """The toolkit's own loader, in a child process with the bound packages. A misplaced override key otherwise surfaces as a failed launch (RUNBOOK 54)."""
    code = 'import sys; from headkit.common import manifest; manifest(sys.argv[1])'
    done = subprocess.run([PYTHON, '-B', '-c', code, str(path)], env=workspace.python_environment(packages=True, tools=True), capture_output=True, text=True)
    if done.returncode:
        raise guards.Refused(f'{path.parent.name}: manifest refused by the toolkit loader: {done.stderr.strip()[-600:]}')


def write_manifest(workspace, name, check=validate, overrides=None):
    """overrides, when given, replace overrides.json once the manifest built from them passes: a refused edit leaves the head as it was.
    The manifest and inputs are pinned by a launch, so the head lock is held from the first read to the replace (RUNBOOK 49, 111)."""
    with guards.head_locks(workspace, [name]):
        return write_locked_manifest(workspace, name, check, overrides)


def write_locked_manifest(workspace, name, check, overrides):
    replaced = []
    try:
        return rewrite_manifest(workspace, name, check, overrides, replaced)
    except Exception:
        for held, target in replaced:
            target.unlink(missing_ok=True)
            held.replace(target)
        raise
    finally:
        for held, _ in replaced:
            held.unlink(missing_ok=True)



def bind_render_device(workspace,data):
    """Bind optional workspace GPU defaults to the same shared GPU lane as generation."""
    configured=workspace.data.get('renderDevice')
    if configured is None or 'render' not in data or 'compute' in data['render']:return
    if not isinstance(configured,dict):raise guards.Refused('renderDevice must be a configuration object')
    from headkit.render_device import settings
    value=dict(configured)
    if value.get('device')=='GPU':
        from shared_tools import tools_root
        from workspace import REPO
        index=value.get('gpuIndex',workspace.data.get('comfy',{}).get('gpuIndex',0))
        if index!=workspace.data.get('comfy',{}).get('gpuIndex',0):raise guards.Refused('Render and ComfyUI must use the same shared GPU index')
        root,_=tools_root(REPO,workspace.data.get('toolsRoot'))
        value.update(gpuIndex=index,gpuLock=str(root/'locks'/f'gpu-{index}'),comfyUrl=workspace.data.get('comfy',{}).get('url'))
    data['render']['compute']=settings({'compute':value})



def bind_preserved_render(data):
    """Use actual 4K source appearance at 2K and the unchanged PLT decode at 1K."""
    if not data.get('palette',{}).get('preserveStockEncoding') or 'render' not in data:return
    if 'basecolor4k' not in data['inputs']:
        raise guards.Refused('Protected stock rendering needs a bound basecolor4k source; do not upscale the 1K PLT decode')
    render=data['render']
    stages=dict(render.get('mapStages',{}));stages.pop('basecolor',None)
    render['mapStages']=stages
    render['mapInputs']={**render.get('mapInputs',{}),'basecolor':'basecolor4k'}
    render['runtimePalette']=True

def rewrite_manifest(workspace, name, check, overrides, replaced):
    head = workspace.head(name)
    receipt = guards.read(head/'design'/'design-receipt.json')
    stored = head/'overrides.json'
    chosen = overrides if overrides is not None else guards.read(stored) if stored.exists() else {}
    race, sex = receipt['race'], receipt['sex']
    inputs = {'design': link(head, head/'design'/receipt['selectedDesign']['file'], 'design.png', replaced)}
    for role, file in PALETTE_ROLES:
        if not (head/'inputs'/file).is_file():
            raise guards.Refused('Missing palette '+file+'; bind the actual separate palette before regenerating this manifest')
        inputs[role] = {'path': f'inputs/{file}', 'sha256': sha(head/'inputs'/file)}
    gpu = head/'gpu'/'gpu.json'
    if gpu.exists():
        stages = guards.read(gpu)['stages']
        if 'geometry' in stages:
            inputs['raw'] = link(head, file_from(stages['geometry']['files'], GEOMETRY_NODE)['path'], 'raw.glb', replaced)
        if 'appearance' in stages:
            inputs['field'] = link(head, file_from(stages['appearance']['files'], FIELD_NODE)['path'], 'field.npz', replaced)
    reference = workspace.fit_reference(race, sex)
    inputs['fitReference'] = link(head, reference, 'fit-reference-'+reference.name, replaced)
    if race == 'troll' and chosen.get('fit', {}).get('align', 'nose') in ('nose', 'profile'):
        policy = Path(__file__).resolve().parents[2]/'docs/heads/troll-build-allowance-r3.json'
        inputs['nativeSizingPolicy'] = link(head, policy, policy.name, replaced)
    data = defaults(name, receipt, inputs, reference)
    merge(data, chosen)
    bind_render_device(workspace,data)
    if 'nativeSizingPolicy' in inputs:
        data['nativeSizing'] = 'troll-build-allowance-r3'
    tone_every_channel(data, race, sex, name)
    bind_preserved_render(data)
    candidate = head/'manifest.check.json'
    write_json(candidate, data)
    try:
        check(workspace, candidate)
    except Exception:
        candidate.unlink()
        raise
    candidate.replace(head/'manifest.json')
    if overrides is not None:
        write_json(stored, overrides)
    return head/'manifest.json'


def set_components(workspace, name, notes, check=validate):
    """The reviewed shell selection from `review shells`: keep the largest, bound = extra area rounded up + 10 %. The table's count includes the kept shell, and the repair expects the extras (RUNBOOK 93)."""
    head = workspace.head(name)
    table = guards.read(head/'review-evidence'/'shells.json')
    extra, area = len(table['extra']), table['deletedAreaFraction']
    if table['count'] != extra+1:
        raise guards.Refused(f"{name}: the shell table counts {table['count']} with {extra} extra: rerun review shells")
    # Headkit requires a positive area bound. expectedDeleted=0 separately forbids any deletion.
    bound = max(1, math.ceil(area*1.1*1e4))/1e4
    overrides = guards.read(head/'overrides.json')
    overrides.setdefault('mesh', {})['components'] = {'keep': 'largest', 'reviewed': True, 'maximumDeletedAreaFraction': bound, 'expectedDeleted': extra,
                                                      'notes': f'review shells: {extra} extra shells, {area*100:.4f}% of area. {notes}'}
    if extra and all(row.get('insideFraction') == 1.0 for row in table['extra']):
        overrides['mesh']['components']['interiorOnly'] = True
    write_manifest(workspace, name, check, overrides)
    return extra, bound


def set_ownership(workspace, name, rules, check=validate):
    """A reviewed rule set (regions, rules, notes), replacing any earlier one. Coordinates are bbox-relative GLB frame; `review grid` draws the iso-lines."""
    overrides = guards.read(workspace.head(name)/'overrides.json')
    profile = overrides.get('ownership', {})
    features = {key: profile[key] for key in ('featureChannels', 'boneEarGuard', 'hairEarGuard', 'browSeedGuard', 'browSeedGuardPixels', 'lipSkinGuard', 'hairMaskRequiresRule') if key in profile}
    overrides['ownership'] = {'$replace': True, 'mode': 'rules', 'reviewed': True, 'default': 0, **features, **guards.read(rules)}
    return write_manifest(workspace, name, check, overrides)


def revise_clay(workspace, name, design, reference, checked, approval, check=validate):
    return revise_conditioning(workspace, name, design, reference, checked, approval, check=check)


def revise_pair(workspace, name, design, reference, checked, approval, check=validate):
    return revise_conditioning(workspace, name, design, reference, checked, approval, check=check, paired=True)


def revise_conditioning(workspace, name, design, reference, checked, approval, check=validate, paired=False):
    """Select a checked clay for an existing head. Its original conditioning, reviews and GPU ledger stay addressable."""
    from headkit.common import pin, verify, write
    if name not in workspace.head_ids() or reference is None or not approval.strip():
        raise guards.Refused('Revised clay needs the existing slot, reference record and explicit selection')
    head = workspace.head(name)
    with guards.head_locks(workspace, [name]):
        if (head/'gpu/UNRECONCILED').exists():
            raise guards.Refused('Reconcile the pending GPU submission before revising its conditioning')
        ledger = head/'gpu/gpu.json'
        if ledger.exists() and 'geometry' in guards.read(ledger)['stages']:
            raise guards.Refused('A current accepted geometry already exists for the slot')
        record_pin = pin(reference)
        checked_pin = pin(checked)
        record, pair = reference_record.load(reference, name, design)
        measured = guards.read(checked)
        if (not pair or measured.get('head') != name or measured.get('referenceRecord') != record_pin
                or set(measured.get('pair', {}).get('images', {})) != {
                    'geometry-pair.png', 'detail-pair.png', 'common-mask.png', 'alignment-overlay.png'}):
            raise guards.Refused('Run reference-check on this exact revised pair first')
        verify([checked_pin, record_pin, *measured['pair']['images'].values()], fresh=True)
        manifest = guards.read(head/'manifest.json')
        inputs = manifest['inputs']
        if ('clay' not in inputs or 'detail' not in inputs or (not paired and
                (inputs['design']['sha256'] != record['design']['sha256'] or
                 inputs['detail']['sha256'] != record['conditioning']['detail']['sha256']))):
            raise guards.Refused('A clay-only revision must retain the selected design and diffuse input')
        # Content-addressed targets make retries safe and preserve the old prepare and its inputs.
        folder = head/'inputs'/'conditioning'/record_pin['sha256']
        folder.mkdir(parents=True, exist_ok=True)
        target = folder/'clay.png'
        if not target.exists():
            from tempfile import TemporaryDirectory
            with TemporaryDirectory(dir=folder) as scratch:
                copied = Path(scratch)/'clay.png'
                shutil.copyfile(pair['clay'], copied)
                if sha(copied) != record['conditioning']['clay']['sha256']:
                    raise guards.Refused('Revised clay changed during selection')
                copied.replace(target)
        if sha(target) != record['conditioning']['clay']['sha256']:
            raise guards.Refused('Saved revised clay differs from the checked input')
        selected = {'clay': pin(target), 'detail': inputs['detail']}
        if paired:
            # Version every changed image; original inputs, reviews and rejected GPU
            # submissions remain intact. Never reset the slot or its counters.
            for role, source, expected in (
                    ('detail', pair['detail'], record['conditioning']['detail']['sha256']),
                    ('design', Path(design).resolve(), record['design']['sha256'])):
                destination = folder/(role+'.png')
                if not destination.exists():
                    from tempfile import TemporaryDirectory
                    with TemporaryDirectory(dir=folder) as scratch:
                        copied = Path(scratch)/(role+'.png')
                        shutil.copyfile(source, copied)
                        if sha(copied) != expected:
                            raise guards.Refused('Revised '+role+' changed during selection')
                        copied.replace(destination)
                if sha(destination) != expected:
                    raise guards.Refused('Saved revised '+role+' differs from the checked input')
                selected[role] = pin(destination)
        receipt = {'head': name, 'referenceRecord': record_pin, 'pairCheck': checked_pin,
                   **selected, 'approval': approval}
        if paired:
            receipt['originalSelection'] = pin(head/'design/design-receipt.json')
        selection_path = folder/'selection.json'
        if selection_path.exists():
            if guards.read(selection_path) != receipt:
                raise guards.Refused('Existing selection differs for this reference')
        else:
            write(selection_path, receipt, fresh=True)
        overrides = guards.read(head/'overrides.json')
        for role in ('clay', 'detail', 'design') if paired else ('clay',):
            selected_path = Path(selected[role]['path'])
            overrides['inputs'][role] = {'path': selected_path.relative_to(head).as_posix(), 'sha256': selected[role]['sha256']}
        if paired:
            overrides['features'] = [dict(name=key, description=value, placementReviewed=True)
                                     for key, value in record['features'].items()]
        overrides['alignment'] = record['conditioning']['alignment']
        return write_locked_manifest(workspace, name, check, overrides)


def selected_prompt(workspace, name, race, design, record=None):
    """Resolve generated images against their frozen proposal; external designs retain the manual setup route."""
    folder = workspace.root/'design'
    spec = folder/f'designs-{race}.json'
    if record is not None:
        data, _ = reference_record.load(record, name, design)
        return data['prompt'], {'generator': data['generator'], 'referenceRecord': {'path': str(Path(record).resolve()), 'sha256': sha(record)}}, sha(design)
    if design.parent != (folder/'raw').resolve():
        raise guards.Refused(f'{name}: external designs require --reference-record; the current race prompt is not provenance')

    match = re.fullmatch(r'(.+)-b[0-9]+\.png', design.name)
    if not match:
        raise guards.Refused(f'{name}: expected a generated proposal PNG with its receipt')
    receipt = design.with_name(match[1]+'.json')
    if not receipt.is_file():
        raise guards.Refused(f'{name}: missing proposal receipt {receipt.name}')
    receipt_bytes = receipt.read_bytes()
    data = json.loads(receipt_bytes)
    if data.get('kind') != 'design' or data.get('state') != 'complete' or data.get('head') != name:
        raise guards.Refused(f'{name}: the selected proposal must have a complete design receipt for this head')
    matches = [row for row in data.get('outputs', []) if Path(row['path']).resolve() == design]
    if len(matches) != 1 or sha(design) != matches[0]['sha256']:
        raise guards.Refused(f'{name}: selected image differs from the proposal output')
    spec = Path(data['spec']['path']).resolve()
    if spec.parent != (folder/'launches').resolve() or not spec.is_file():
        raise guards.Refused(f'{name}: the frozen proposal spec is missing from this workspace')
    spec_bytes = spec.read_bytes()
    if hashlib.sha256(spec_bytes).hexdigest() != data['spec']['sha256']:
        raise guards.Refused(f'{name}: frozen proposal spec changed')
    lineage = {'prompt': spec.relative_to(workspace.root).as_posix(), 'promptSha256': data['spec']['sha256'],
               'proposalReceipt': {'path': receipt.relative_to(workspace.root).as_posix(),
                                   'sha256': hashlib.sha256(receipt_bytes).hexdigest()}}
    lineage['designProfile'] = data.get('profile', 'flux2-turbo-v1')
    lineage['generator'] = data.get('settings', {}).get('model', 'Flux.2') + ' via headkit design'
    return json.loads(spec_bytes)['designs'][name], lineage, matches[0]['sha256']


def set_up(workspace, name, design, reach=.04, slope=-.2, deviations=(), approval='', check=validate, reference=None, quality_profile=None, no_neck_cut=False):
    """A new head folder: design receipt, stock palettes, bindings, compiler binding, body neck, neck-cut overrides, then the manifest.
    A marker stands until the manifest passes, so a failed setup can be run again once its cause is fixed."""
    known = workspace.head_ids()
    if name not in known:
        raise guards.Refused(f'{name} is not in workspace slots')
    race, sex, slot = known[name]
    head = workspace.head(name)
    marker = head/SETUP_MARKER
    if head.exists() and any(head.iterdir()) and not marker.exists():
        raise guards.Refused(f'{head} already exists and is not empty')
    if not approval.strip():
        raise guards.Refused(f'{name}: --approval must say who picked the design and on what basis')
    design = Path(design).resolve()
    prompt, lineage, expected_image = selected_prompt(workspace, name, race, design, reference)
    record, pair = reference_record.load(reference, name, design) if reference else (None, {})
    if workspace.data.get('requirePairedReferences') is True and not pair:
        raise guards.Refused('This workspace requires a reviewed clay/detail reference pair before setup')
    quality_profile = quality_profile or workspace.data.get('headQualityProfile', 'face-v1' if race == 'troll' else None)
    if quality_profile not in (None, 'face-v1'):
        raise guards.Refused('Unknown head quality profile: '+str(quality_profile))
    if quality_profile=='face-v1' and race=='troll':
        checks=(record or {}).get('conditioning',{}).get('alignment',{}).get('featureChecks')
        if checks!={'horns':2,'tusks':2,'neck':'none','hairBelowJaw':True}:
            raise guards.Refused('Troll face-v1 requires measured horn/tusk roots and tips, jaw landmarks and explicit no-neck featureChecks')
        # Validation remains in the bound prepare child; no anatomy is approved here.
    features = {key.lower(): value.strip() for key, value in FEATURE.findall(prompt)}
    if record:
        features = dict(record['features'])
    features['neck'] = ('preserve the jaw-terminated head; the body part forms the neck' if no_neck_cut else
                        'removed by mesh.neck.cut; the body neck part forms the neck')
    for folder in ('design', 'inputs', 'review-evidence'):
        (head/folder).mkdir(parents=True, exist_ok=True)
    marker.touch()
    saved = Path(shutil.copy2(design, head/'design'/design.name))
    image_sha = sha(saved)
    if expected_image is not None and image_sha != expected_image:
        raise guards.Refused(f'{name}: proposal image changed during setup')
    for file in RACE_DATA['designPalettes']:
        shutil.copy2(workspace.require('palettes')/file, head/'inputs'/file)
    shutil.copy2(workspace.path(workspace.data['headBindings']), head/'bindings.json')
    shutil.copy2(workspace.require('mdlCompiler'), head/'mdl-compiler.json')
    shutil.copy2(workspace.body_neck(race, sex), head/'inputs'/'body-neck.json')
    species = workspace.design_reference(race, sex)
    receipt = {'headId': name, 'race': race, 'sex': sex, 'slot': slot,
               'route': 'bootstrap: one front design -> headkit matte -> Pixal single-view geometry + appearance -> headkit CPU chain with neck cut -> native (Blender + NeverBlender)',
               'generator': 'Flux.2 via headkit design'+(f'; species reference {species.name}' if species else '; no reference image'),
               **lineage,
               'viewConvention': 'front image left = character RIGHT; image right = character LEFT. NWN fit yaws 180 degrees; sides are anatomical and unchanged.',
               'designApproved': True, 'approval': approval,
               'selectedDesign': {'file': design.name, 'sha256': image_sha}, 'featureInventory': features, 'observedDeviations': list(deviations),
               'slotSource': 'docs/heads/slot-catalog.json blocks; workspace slots'}
    write_json(head/'design'/'design-receipt.json', receipt)
    # Keep replacement directives until write_manifest merges this layer into defaults (RUNBOOK 245).
    overrides = face_quality_profile() if quality_profile else {}
    if race == 'troll' and quality_profile:
        overrides['ownership']['boneEarGuard'] = True
    overrides['inputs'] = {'bodyNeck': {'path': 'inputs/body-neck.json', 'sha256': sha(head/'inputs'/'body-neck.json')}}
    body_prefix = prefix(race, sex)
    torso = workspace.data.get('bodyTorsoReferences', {}).get(body_prefix)
    if torso:
        source = workspace.path(torso)
        if not source.is_file() or source.stem[:4] != body_prefix:
            raise guards.Refused('Body torso reference must exist and match '+body_prefix)
        target = head/'inputs'/source.name
        shutil.copy2(source, target)
        overrides['inputs']['bodyTorso'] = {'path': 'inputs/'+target.name, 'sha256': sha(target)}
    overrides.setdefault('mesh', {})['neck'] = None if no_neck_cut else {'$replace': True, 'cut': {
        'height': 'measured', 'slope': slope, 'band': 0.03, 'reach': reach,
        'notes': f'Heads have no neck: plane under the lowest front feature beyond the reach, slope {slope}; stub drawn 3 mm inside the smoothed body neck over 3 cm.'}}
    if record:
        shutil.copy2(reference, head/'design'/'reference-record.json')
        receipt['sourceReferenceRecord'] = receipt['referenceRecord']
        receipt['referenceRecord'] = {'path': 'design/reference-record.json', 'sha256': sha(head/'design'/'reference-record.json')}
        if pair:
            receipt['route'] = 'paired: clay geometry + diffuse detail; shared crop and FOV; saved-shape appearance'
            for role, source in pair.items():
                target = head/'inputs'/f'{role}.png'
                shutil.copy2(source, target)
                overrides['inputs'][role] = {'path': f'inputs/{role}.png', 'sha256': sha(target)}
            overrides['alignment'] = record['conditioning']['alignment']
        write_json(head/'design'/'design-receipt.json', receipt)
    if quality_profile:
        body = workspace.data.get('bodySkinReferences', {}).get(f'{race}-{sex}')
        if not body or not workspace.path(body).is_file():
            raise guards.Refused('face-v1 needs workspace bodySkinReferences for '+race+'-'+sex)
        target = head/'inputs'/'body-skin.plt'
        shutil.copy2(workspace.path(body), target)
        overrides['inputs']['bodySkin'] = {'path': 'inputs/body-skin.plt', 'sha256': sha(target)}
    if race == 'troll':  # horn curls enclose backdrop that the border flood fill keeps (RUNBOOK 57); review the matte check
        overrides['matte'] = {'enclosedBackgroundMinimumPixels': 400}
    write_json(head/'overrides.json', overrides)
    manifest = write_manifest(workspace, name, check)
    marker.unlink()
    return manifest


def face_quality_profile():
    """Explicit opt-in for new heads; no existing manifest is silently migrated."""
    return {'mesh': {'uv': {'faceDensity': 3, 'refinePacking': True}}, 'faceMasks': {},
            'ownership': {'featureChannels': True, 'hairEarGuard': True, 'browSeedGuard': True, 'browSeedGuardPixels': 8, 'lipSkinGuard': True},
            'tone': {'faceTreatment': {'delight': .8, 'smooth': .7, 'lipDark': .5, 'socket': .3,
                     'irisRim': .45, 'lidLine': .6, 'browEdge': .95, 'scalpDelight': 0, 'browSkinRefill': 0}},
            'quality': {}, 'palette': {'nativeMaterial': 'stock-organic-head-v1', 'fullShadeRange': True, 'stretchShadingOnly': True, 'matchBodySkin': True, 'skinShadeContrast': 'auto', 'repairSkinSeams': True, 'repairFeatureHighlights': True},
            'render': {'$replace': True, 'frontAngleDegrees': -90,
                       'sizes': [2048, 1024], 'modes': ['clay','color-only','material-lit'],
                       'mapStages': {'basecolor': 'tone'}, 'runtimePalette': True,
                       'materialConstants': {'roughness': .8, 'metallic': 0, 'opacity': 1}}}
