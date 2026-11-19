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
    'civic': 'a public building of a 2070s cyberpunk city (Shadowrun): sturdy, institutional, maintained on a small budget, some wear and grime'}
KINDS = {
    'window': 'a window. Daytime, the room behind unlit: dark, slightly reflective glass with some dirt; the frame worn as its district suggests',
    'facade': 'a section of a building facade with its grid of windows. Daytime, glass dark and slightly reflective, no lit windows, no visible interiors',
    'wall': 'a wall surface',
    'shopfront': 'a shop window with its display and lettering. Daytime, the shop unlit inside',
    'sign': 'a sign. Its wording stays the same and stays easy to read, in clean lettering',
    'poster': 'a wall of layered, torn, weathered posters and flyers. Invented bands, events and products only'}
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


def prompt(name, how, size, tiles=False, tool=True):
    """What the generator is asked for one texture. how: {kind, district, note (optional), of (a lit variant's day
    texture), light (a lit variant's light, optional)}. size: the (width, height) the picture is saved at. tool: the
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
        lines += [f'The attached {"ref.png" if tool else "image"} is an old low-quality game texture of {KINDS[how["kind"]]}. Redraw it as a new, detailed, '
                  f'photographic-quality texture of the same thing for {DISTRICTS[how["district"]]}.']
    if how.get('note'):
        lines.append(how['note'])
    lines += ['', RULES.rstrip()]
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


def _sha(picture):
    picture = np.ascontiguousarray(picture); return hashlib.sha256(repr(picture.shape).encode() + picture.tobytes()).hexdigest()


def alike(old, new, side=256):
    """How well a redrawn picture's edges sit on the old one's: the correlation of their edge strengths, about 0.5 or
    more for a layout that was kept, near 0 for one that moved. A lit picture against a dim one scores lower."""
    from PIL import Image
    shrunk = lambda picture: np.asarray(Image.fromarray(np.asarray(picture)[..., :3]).convert('L').resize((side, side), Image.LANCZOS), np.float64)
    edges = lambda grey: (np.abs(np.diff(grey, axis=1))[:-1] + np.abs(np.diff(grey, axis=0))[:, :-1]).ravel()
    first, second = edges(shrunk(old)), edges(shrunk(new))
    return 0.0 if first.std() == 0 or second.std() == 0 else float(np.corrcoef(first, second)[0, 1])


def composed(day, old_day, old_lit, enlarged=None):
    """The lit variant of a redrawn day picture, made with no generator: its glass lit where the old night texture is
    lit, in that texture's colours, with the day picture's own detail (a curtain, a blind, dirt) showing against the
    light; everything else as by day, darker. day: the redrawn day picture (PIL image). old_day, old_lit: the
    textures the game draws now (uint8 arrays; a lit one's alpha limits what is lit). enlarged: the old lit picture
    as the upscaling model enlarged it, for cleaner colours. Lit is what the old night texture shows well brighter
    than the old day one, or outright bright (a neon tube is as bright by day in the old pictures)."""
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
    light = new @ weights; inside = mask[..., 0] > 0.5
    low, high = np.percentile(light[inside], [5, 95]) if inside.sum() > 50 else (0.0, 255.0)
    detail = np.clip((light - low) / max(high - low, 1.0), 0, 1)[..., None]
    return Image.fromarray(np.uint8(np.clip(new * 0.6 * (1 - mask) + colour * (0.7 + 0.5 * detail) * mask, 0, 255) + 0.5))


def redraw(spec, repo, folder, run, *, only=None, enlarged=None, workers=3, say=print):
    """Every texture of a redraw list drawn again into `folder` as <name>.png with a record beside it, the day
    pictures first and then the lit ones from them, `workers` at a time. One that is there already is passed over. A
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
        how = textures[name]; target = folder / f'{name}.png'
        if target.is_file():
            return 'kept'
        old = np.asarray(material.current(repo, name))[..., :3]; height, width = old.shape[:2]
        size = (SIDE, max(64, round(SIDE * height / width / 64) * 64)) if width >= height else (max(64, round(SIDE * width / height / 64) * 64), SIDE)
        better = Path(enlarged) / f'{name}.png' if enlarged else None
        if how.get('compose'):
            require(how.get('of'), 'only a lit variant is composed: it names the day texture it is `of`')
            day = folder / f'{how["of"]}.png'; require(day.is_file(), f'its day picture {how["of"]} was not redrawn')
            with Image.open(day) as shown:
                picture = composed(shown, np.asarray(material.current(repo, how['of'])), np.asarray(material.current(repo, name)),
                                   np.asarray(Image.open(better).convert('RGB')) if better is not None and better.is_file() else None).resize(size, Image.LANCZOS)
            picture.save(target)
            (folder / f'{name}.json').write_text(json.dumps({'kind': 'tilekit-composed', 'texture': name, 'source': _sha(old), 'of': how['of'], 'size': list(size)}, indent=1) + '\n', encoding='utf-8')
            return 'composed'
        work = folder / 'jobs' / name
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True); images = [work / 'ref.png']
        reference = Image.open(better).convert('RGB') if better is not None and better.is_file() else Image.fromarray(old)
        reference.resize(size, Image.LANCZOS).save(work / 'ref.png')
        if how.get('of'):
            day = folder / f'{how["of"]}.png'; require(day.is_file(), f'its day picture {how["of"]} was not redrawn')
            Image.open(day).convert('RGB').resize(size, Image.LANCZOS).save(work / 'day.png'); images.insert(0, work / 'day.png')
        text = prompt(name, how, size, tiles=bool(how.get('tiles')), tool=getattr(run, 'tool', True)); (work / 'prompt.txt').write_text(text, encoding='utf-8')
        run(work, text, images)
        require((work / 'out.png').is_file(), 'the generator left no out.png')
        with Image.open(work / 'out.png') as made:
            picture = made.convert('RGB').resize(size, Image.LANCZOS)
        picture.save(target)
        (folder / f'{name}.json').write_text(json.dumps({'kind': 'tilekit-redrawn', 'texture': name, 'source': _sha(old), 'prompt': text, 'size': list(size),
                                                         'alike': round(alike(old, picture), 2)}, indent=1) + '\n', encoding='utf-8')
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
