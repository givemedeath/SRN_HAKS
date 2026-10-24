"""Flux.2 head design proposals through a DIRECT local ComfyUI dispatch.

This route is deliberately unguarded: one POST to the bound local ComfyUI, then /history polling. It has none of the
`comfy.submit` guarantees (shared ledger, generation count, idle-queue check, server runtime identity, verified model
loaders); that guarded route needs the managed srn_headkit adapter, which is still undeployed. Outputs are design
proposals for human review only. Nothing here approves a design or pins it as a manifest reference."""
import json
import re
import shutil
import tempfile
import time
import uuid
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from .common import read, write, require, pin, verify, digest, source_version

TEMPLATES = Path(__file__).parent / 'templates'
SUBFOLDER = 'headkit-design'
NAME = re.compile(r'[a-z0-9][a-z0-9-]{0,63}')
SPEC_KEYS = {'common', 'designs', 'neckInpaint', 'neckEdit'}
SUFFIXES = ('.png', '.jpg', '.jpeg', '.webp')
MAX_BATCH = 8
MAX_REFERENCES = 4
MASK_BLUR = 6
FIXED = {'model': 'flux2_dev_fp8mixed.safetensors', 'turboLora': 'Flux_2-Turbo-LoRA_comfyui.safetensors',
         'steps': 8, 'size': 1024, 'guidance': 4.0, 'sampler': 'euler'}
DISPATCH = ('direct: one unguarded POST to the bound local ComfyUI plus /history polling; no ledger, idle-queue, '
            'runtime-identity or verified-loader checks (the guarded submit route needs the undeployed managed adapter)')


def load_spec(path):
    spec = read(path)
    require(isinstance(spec, dict) and set(spec) <= SPEC_KEYS and isinstance(spec.get('common'), str)
            and spec['common'].strip() and isinstance(spec.get('designs'), dict) and spec['designs'],
            'Design spec needs common text and named designs (keys: ' + ', '.join(sorted(SPEC_KEYS)) + ')')
    for name, text in spec['designs'].items():
        require(NAME.fullmatch(name) is not None and isinstance(text, str) and text.strip(),
                'Design names must be safe IDs with prompt text: ' + name)
    require('neckInpaint' not in spec or (isinstance(spec['neckInpaint'], str) and 'SKIN' in spec['neckInpaint']),
            'neckInpaint needs a SKIN placeholder')
    return spec


def design_prompt(spec, head):
    require(head in spec['designs'], 'Unknown design head: ' + str(head))
    return spec['designs'][head] + '\n' + spec['common']


def inpaint_prompt(spec, skin):
    require(isinstance(spec.get('neckInpaint'), str), 'Spec has no neckInpaint prompt')
    require(isinstance(skin, str) and skin == skin.strip() and 0 < len(skin) <= 80 and '\n' not in skin
            and 'SKIN' not in skin, 'Skin must be one short line of text')
    return spec['neckInpaint'].replace('SKIN', skin)


def _owned(value):
    parts = value.split('/') if isinstance(value, str) else []
    return len(parts) > 1 and parts[0] == SUBFOLDER and all(parts) and '..' not in parts and '\\' not in value and ':' not in value


def _common(graph, prompt, seed, batch, prefix, images):
    require(isinstance(prompt, str) and prompt.strip(), 'Prompt text required')
    require(type(seed) is int and 0 <= seed < 2 ** 64, 'Seed must be an integer from 0 to 2^64-1')
    require(type(batch) is int and 1 <= batch <= MAX_BATCH, f'Batch must be 1..{MAX_BATCH}')
    require(_owned(prefix), 'Isolated output prefix under ' + SUBFOLDER + '/ required')
    require(all(_owned(image) for image in images), 'Stage input images under ' + SUBFOLDER + '/')
    graph['6']['inputs']['text'] = prompt; graph['25']['inputs']['noise_seed'] = seed
    graph['9']['inputs']['filename_prefix'] = prefix


def _references(graph, references):
    # One ReferenceLatent per image, chained onto the guided conditioning, as in the reviewed scratch graph.
    require(len(references) <= MAX_REFERENCES, f'At most {MAX_REFERENCES} reference images')
    cond = ['26', 0]
    for i, ref in enumerate(references):
        a, b, c, d = (str(100 + i * 4 + k) for k in range(4))
        graph[a] = {'class_type': 'LoadImage', 'inputs': {'image': ref}}
        graph[b] = {'class_type': 'ImageScaleToTotalPixels', 'inputs': {'image': [a, 0], 'upscale_method': 'lanczos', 'megapixels': 1.0, 'resolution_steps': 1}}
        graph[c] = {'class_type': 'VAEEncode', 'inputs': {'pixels': [b, 0], 'vae': ['10', 0]}}
        graph[d] = {'class_type': 'ReferenceLatent', 'inputs': {'conditioning': cond, 'latent': [c, 0]}}
        cond = [d, 0]
    graph['22']['inputs']['conditioning'] = cond


def _validated(graph):
    for node in graph.values():
        for key, value in node['inputs'].items():
            if key in ('image', 'images', 'pixels') and node['class_type'] not in ('LoadImage', 'LoadImageMask'):
                require(isinstance(value, list), 'IMAGE socket must reference an image output')
            if isinstance(value, list) and len(value) == 2:
                require(isinstance(value[0], str) and value[0] in graph and type(value[1]) is int, 'Dangling graph link')
    saves = [key for key, node in graph.items() if node['class_type'] == 'SaveImage']
    require(saves == ['9'] and graph['9']['inputs']['images'] == ['8', 0], 'The decoded batch must reach the one SaveImage')
    return graph


def compile_design(prompt, references, seed, batch, prefix):
    """Text plus species reference(s) to a batch of new designs (fixed steps 8, 1024 square, guidance 4.0, turbo LoRA)."""
    graph = read(TEMPLATES / 'flux2-design.json')
    _common(graph, prompt, seed, batch, prefix, references)
    graph['47']['inputs']['batch_size'] = batch; _references(graph, references)
    return _validated(graph)


def compile_inpaint(prompt, design, mask, seed, batch, prefix):
    """Masked resample of an existing design: its own latent under SetLatentNoiseMask, repeated per batch item, and the
    design again as ReferenceLatent. Pixels outside the (blurred) mask keep their latent."""
    graph = read(TEMPLATES / 'flux2-inpaint.json')
    _common(graph, prompt, seed, batch, prefix, [design, mask])
    graph['200']['inputs']['image'] = design; graph['203']['inputs']['image'] = mask
    graph['205']['inputs']['amount'] = batch; _references(graph, [design])
    return _validated(graph)


def dispatch(client, graph, token, record, *, poll=3.0, deadline=2700):
    """POST once and poll /history until the prompt finishes. Never retries or resubmits."""
    response = client.request('/prompt', {'prompt': graph, 'client_id': token})
    require(isinstance(response, dict) and response.get('prompt_id') and not response.get('node_errors'),
            'ComfyUI rejected the design request: ' + json.dumps(response)[:2000])
    record['promptId'] = prompt_id = response['prompt_id']; started = time.monotonic()
    while True:
        entry = client.request('/history/' + prompt_id).get(prompt_id)
        if entry and (entry.get('outputs') or entry.get('status', {}).get('completed') is not None): break
        require(time.monotonic() - started < deadline, f'Design job {prompt_id} unfinished after {deadline}s; it may still be queued')
        time.sleep(poll)
    status = entry.get('status', {})
    require(status.get('status_str') != 'error', 'ComfyUI design job failed: ' + json.dumps(status)[:3000])
    return entry


def collect_images(entry, output_root, prefix, batch):
    images = entry.get('outputs', {}).get('9', {}).get('images', [])
    require(len(images) == batch, f'Expected {batch} saved images, got {len(images)}')
    root = Path(output_root).resolve(); owned = (root / prefix).parent; paths = []
    for row in images:
        require(row.get('type') == 'output', 'Only durable output images may be collected')
        path = (root / row.get('subfolder', '') / row['filename']).resolve()
        require(path.is_relative_to(owned), 'Output is outside the owned design prefix')
        require(path.is_file(), 'Comfy output missing: ' + str(path)); paths.append(path)
    return paths


def _bound(local):
    for key in ('comfyInput', 'comfyOutput'):
        require(isinstance(local.get(key), str) and Path(local[key]).is_absolute(), 'Local bindings need absolute ' + key)


def _image(path, suffixes=SUFFIXES):
    path = Path(path)
    require(path.is_file() and path.suffix.lower() in suffixes, 'Image file required: ' + str(path))
    return path


def _execute(client, local, bindings_path, graph, receipt, sources, output, base, batch, runtime):
    """Stage inputs, dispatch, copy outputs; always leave a receipt (complete or failed) once work has started."""
    output = Path(output); started = time.monotonic()
    receipt.update(state='dispatching', comfyEndpoint=client.url, bindings=pin(bindings_path), runtimeIdentity=runtime,
                   codeVersion=source_version(), graph=graph, graphSha256=digest(graph))
    try:
        folder = Path(local['comfyInput']).resolve() / SUBFOLDER / receipt['token']; folder.mkdir(parents=True, exist_ok=False)
        staged = {}
        for name, source in sources.items():
            target = folder / name; shutil.copyfile(source, target)
            row = {'source': pin(source), 'staged': pin(target), 'comfyImage': f'{SUBFOLDER}/{receipt["token"]}/{name}'}
            require(row['source']['sha256'] == row['staged']['sha256'], 'Staged copy differs from its source'); staged[name] = row
        receipt['staged'] = staged; started = time.monotonic()
        entry = dispatch(client, graph, receipt['token'], receipt)
        receipt['elapsedSeconds'] = round(time.monotonic() - started, 1)
        comfy_outputs = [pin(path) for path in collect_images(entry, local['comfyOutput'], receipt['outputPrefix'], batch)]
        outputs = []
        for i, row in enumerate(comfy_outputs):
            target = output / f'{base}-b{i}.png'
            with open(row['path'], 'rb') as source, target.open('xb') as stream: shutil.copyfileobj(source, stream)
            outputs.append(pin(target)); require(outputs[-1]['sha256'] == row['sha256'], 'Copied output differs from Comfy output')
        verify([row[k] for row in staged.values() for k in ('source', 'staged')] + comfy_outputs + outputs)
        receipt.update(state='complete', comfyOutputs=comfy_outputs, outputs=outputs)
    except Exception as exc:
        receipt.update(state='failed', error=str(exc)); receipt.setdefault('elapsedSeconds', round(time.monotonic() - started, 1))
        raise
    finally:
        write(output / f'{base}.json', receipt, fresh=True)
    return {'receipt': str((output / f'{base}.json').resolve()), 'state': receipt['state'], 'promptId': receipt.get('promptId'),
            'outputs': [row['path'] for row in receipt['outputs']], 'elapsedSeconds': receipt['elapsedSeconds'],
            'proposalOnly': True, 'reviewRequired': True}


def _receipt(kind, spec_path, prompt, seed, batch, token, prefix):
    return {'schemaVersion': 1, 'kind': kind, 'dispatch': DISPATCH, 'proposalOnly': True, 'reviewRequired': True,
            'spec': pin(spec_path), 'prompt': prompt, 'seed': seed, 'batch': batch, 'settings': dict(FIXED),
            'token': token, 'outputPrefix': prefix}


def _fresh(output, base):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    require(not (output / f'{base}.json').exists(), 'Receipt already exists; use another seed or output folder')


def generate(client, local, bindings_path, spec_path, head, seed, batch, references, output, *, runtime=None):
    """`design`: N candidates for one spec head, conditioned on the species reference image(s)."""
    _bound(local); spec = load_spec(spec_path); prompt = design_prompt(spec, head)
    references = [_image(path) for path in references]
    base = f'{head}-s{seed}'; _fresh(output, base); token = uuid.uuid4().hex
    names = {f'reference-{i}{path.suffix.lower()}': path for i, path in enumerate(references)}
    graph = compile_design(prompt, [f'{SUBFOLDER}/{token}/{name}' for name in names], seed, batch, f'{SUBFOLDER}/{token}/{base}')
    receipt = _receipt('design', spec_path, prompt, seed, batch, token, graph['9']['inputs']['filename_prefix'])
    receipt.update(head=head, references=[f'{SUBFOLDER}/{token}/{name}' for name in names])
    return _execute(client, local, bindings_path, graph, receipt, names, output, base, batch, runtime)


def waist(alpha):
    """Matte rows: (top, bottom, neck waist) where the waist is the narrowest silhouette row 62-97% down the subject."""
    rows = np.flatnonzero(alpha.any(1)); require(rows.size, 'Matte found no subject')
    top, bottom = int(rows.min()), int(rows.max()); height = bottom - top
    widths = np.array([np.ptp(np.flatnonzero(row)) if row.any() else 0 for row in alpha])
    lo, hi = int(top + .62 * height), int(top + .97 * height); require(hi > lo, 'Subject is too small to locate a neck')
    return top, bottom, lo + int(np.argmin(widths[lo:hi]))


def carve_guide(image, top, keep, stump):
    """Carve guide (troll-male-04 v6): a row cut leaves ghost fringes or flared wings where a wide bust is removed, so the
    neck is carved instead. The guide keeps the design above `top` and inside the jaw `keep` polygon, keeps the design's own
    neck skin only inside a stump outline (cx, wTop, wBottom, ySide, yBottom: straight sides from `top` to ySide, a rounded
    closed bottom to yBottom) and fills the rest with the corner backdrop. The mask (255 = resample) is everything outside
    the keep region, so Flux re-renders the carved stump as closed skin. Returns (guide RGB image, mask uint8, backdrop)."""
    rgb = np.asarray(image.convert('RGB')); height, width = rgb.shape[:2]
    cx, wt, wb, ys, yb = (float(v) for v in stump)
    require(len(keep) >= 3 and all(0 <= x < width and 0 <= y < height for x, y in keep), 'Keep polygon needs 3+ points inside the image')
    require(0 < top < ys < yb <= height and wt > 0 and wb > 0 and 0 < cx < width, 'Stump must run from top to ySide to yBottom inside the image')
    corners = np.concatenate([rgb[-height // 16:, :width // 16].reshape(-1, 3), rgb[-height // 16:, -width // 16:].reshape(-1, 3)])
    backdrop = tuple(int(v) for v in np.median(corners, 0))
    outline = Image.new('L', image.size, 0); draw = ImageDraw.Draw(outline); r, ry = wb / 2, yb - ys
    draw.polygon([(cx - wt / 2, top), (cx + wt / 2, top), (cx + r, ys)]
                 + [(cx + r * np.cos(t), ys + ry * np.sin(t)) for t in np.linspace(0, np.pi, 40)] + [(cx - r, ys)], fill=255)
    kept = Image.new('L', image.size, 0); dk = ImageDraw.Draw(kept)
    dk.rectangle((0, 0, width, top), fill=255); dk.polygon([tuple(p) for p in keep], fill=255)
    guide = Image.new('RGB', image.size, backdrop); source = image.convert('RGB')
    guide.paste(source, (0, 0), outline.filter(ImageFilter.GaussianBlur(1.5))); guide.paste(source, (0, 0), kept)
    return guide, np.where(np.asarray(kept) > 127, 0, 255).astype(np.uint8), backdrop


def inpaint(client, local, bindings_path, spec_path, design, skin, seed, batch, output, *, cut=None, lift=24, name=None, runtime=None,
            carve=None):
    """`design-inpaint`: resample only the rows below a cut row of a reviewed design (its neck); the head stays. With
    `carve` ({top, keep, stump}, see carve_guide) the staged image is the carve guide and only the keep region stays."""
    from .images import matte
    _bound(local); spec = load_spec(spec_path); prompt = inpaint_prompt(spec, skin); design = _image(design, ('.png',))
    name = design.stem if name is None else name
    require(NAME.fullmatch(name) is not None, 'Pass --name: the design file stem is not a safe ID')
    require(type(lift) is int and 0 <= lift <= 256, 'Lift must be 0..256 rows')
    base = f'{name}-inpaint-s{seed}'; _fresh(output, base)
    with tempfile.TemporaryDirectory() as folder:
        evidence = matte(design, {}, Path(folder) / 'matte')
        with Image.open(Path(folder) / 'matte' / 'design-rgba.png') as image: alpha = np.asarray(image.getchannel('A')) > 127
    top, bottom, waist_row = waist(alpha)
    if carve is not None:
        require(cut is None and isinstance(carve, dict) and set(carve) == {'top', 'keep', 'stump'}, 'Carve declares top, keep and stump (no --cut)')
        require(type(carve['top']) is int and top + (bottom - top) / 2 < carve['top'] <= bottom,
                f"Carve top {carve['top']} must lie below the top half of the matte (rows {top}..{bottom}) and inside the subject")
        with Image.open(design) as image: guide, carved, backdrop = carve_guide(image, carve['top'], carve['keep'], carve['stump'])
        Path(output).mkdir(parents=True, exist_ok=True); guide_path = Path(output) / f'{base}-guide.png'
        with guide_path.open('xb') as stream: guide.save(stream, format='PNG')
    cut_row = (carve['top'] if carve is not None else waist_row - lift) if cut is None else cut
    require(type(cut_row) is int and top + (bottom - top) / 2 < cut_row <= bottom,
            f'Cut row {cut_row} must lie below the top half of the matte (rows {top}..{bottom}) and inside the subject')
    token = uuid.uuid4().hex
    graph = compile_inpaint(prompt, f'{SUBFOLDER}/{token}/design.png', f'{SUBFOLDER}/{token}/mask.png', seed, batch,
                            f'{SUBFOLDER}/{token}/{base}')
    mask = carved if carve is not None else np.zeros(alpha.shape, np.uint8)
    if carve is None: mask[cut_row:] = 255
    mask_path = Path(output) / f'{base}-mask.png'
    with mask_path.open('xb') as stream: Image.fromarray(mask).filter(ImageFilter.GaussianBlur(MASK_BLUR)).save(stream, format='PNG')
    receipt = _receipt('design-inpaint', spec_path, prompt, seed, batch, token, graph['9']['inputs']['filename_prefix'])
    receipt.update(name=name, skin=skin, design=pin(design),
                   matte={key: evidence[key] for key in ('backdrop', 'foregroundFraction', 'marginPixels')} | {'topRow': top, 'bottomRow': bottom},
                   waistRow=waist_row, cutRow=cut_row,
                   cutSource='carve' if carve is not None else 'explicit' if cut is not None else 'waist-minus-lift',
                   lift=None if cut is not None or carve is not None else lift,
                   mask={**pin(mask_path), 'cutRow': cut_row, 'blurRadius': MASK_BLUR, 'size': [alpha.shape[1], alpha.shape[0]],
                         'rule': 'outside the carve keep region (rows above top + jaw polygon) is 255 before blur' if carve is not None
                                 else 'rows at and below cutRow are 255 before blur; everything above is kept'})
    if carve is not None: receipt.update(carve={**carve, 'backdrop': list(backdrop)}, guide=pin(guide_path))
    staged = guide_path if carve is not None else design
    return _execute(client, local, bindings_path, graph, receipt, {'design.png': staged, 'mask.png': mask_path}, output, base, batch, runtime)
