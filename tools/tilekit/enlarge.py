"""A texture's picture enlarged by an upscaling model, for the `upscale` route.

A resize makes a small picture bigger and no sharper: a 64-pixel window stays a blur. The model on the shared ComfyUI
(envkit's, `reference.UPSCALER`) doubles a picture and draws its edges clean. A texture whose spec says `doubled`
(1 or 2: the times it is doubled) has the picture the game draws now sent through it, one job at a time as every
submission to the shared server is (headkit.shared_comfy.slot), and kept as `<name>.png` in a folder `material.build`
reads. Only the colour goes: a picture's holes are enlarged by `material.make` as before.

A picture is sent with a margin of itself wrapped round it and the margin is cut off again, so one that tiles still
does."""
import hashlib
import json
import uuid
from pathlib import Path

import numpy as np

from . import material, require

MARGIN = 16  # pixels of the picture wrapped round it on every side while the model has it


def wrapped(picture, margin=MARGIN):
    return np.pad(np.asarray(picture), ((margin, margin), (margin, margin), (0, 0)), mode='wrap')


def enlarge(client, local, bindings_path, repo, spec, folder, *, only=None, deadline=1200, say=print):
    """Every texture of `spec` that asks to be `doubled`, enlarged into `folder` as <name>.png with a record beside it.
    One that is there already, made from the picture the game draws now, is passed over; one made from another is
    refused. Returns {name: 'enlarged' | 'kept'}."""
    from PIL import Image
    from tools.envkit import reference
    from tools.headkit import design
    textures = spec.get('textures'); require(isinstance(textures, dict) and textures, 'A material spec lists its textures')
    chosen = sorted(textures) if only is None else list(only); require(set(chosen) <= set(textures), 'Not in the spec: ' + ', '.join(sorted(set(chosen) - set(textures))))
    folder = Path(folder); work = folder / 'jobs'; work.mkdir(parents=True, exist_ok=True); told = {}
    for name in chosen:
        times = textures[name].get('doubled')
        if times is None:
            continue
        require(times in (1, 2), f'{name}: a texture is doubled once or twice')
        old = np.ascontiguousarray(np.asarray(material.current(repo, name))[..., :3])
        source = hashlib.sha256(repr(old.shape).encode() + old.tobytes()).hexdigest()
        target, record = folder / f'{name}.png', folder / f'{name}.json'
        if target.exists() or record.exists():
            was = json.loads(record.read_text(encoding='utf-8')) if record.is_file() else {}
            require(target.is_file() and was.get('source') == source and was.get('doubled') == times,
                    f'{target} was not made from the {name} the game draws now, doubled {times} times: take it and its record away and enlarge again')
            told[name] = 'kept'; continue
        picture = wrapped(old)
        for step in range(times):
            token = uuid.uuid4().hex; base = f'{name}-{step}-{token[:8]}'; staged = work / f'{base}-in.png'
            Image.fromarray(picture).save(staged)
            graph = reference.enlarge_graph(f'{design.SUBFOLDER}/{token}/reference-0.png', f'{design.SUBFOLDER}/{token}/{base}')
            receipt = {'schemaVersion': 1, 'kind': 'tilekit-enlarged', 'texture': name, 'upscaler': reference.UPSCALER, 'token': token,
                       'outputPrefix': graph['9']['inputs']['filename_prefix'], 'outputs': []}
            design._execute(client, local, bindings_path, graph, receipt, {'reference-0.png': staged}, work, base, 1, None, queue={'deadline': deadline})
            with Image.open(work / f'{base}-b0.png') as made:
                doubled = np.asarray(made.convert('RGB'))
            require(doubled.shape[:2] == (picture.shape[0] * 2, picture.shape[1] * 2), f'{name}: the model gave {doubled.shape[1]}x{doubled.shape[0]}, not the picture doubled')
            picture = doubled
        cut = MARGIN * 2 ** times
        Image.fromarray(picture[cut:-cut, cut:-cut]).save(target)
        record.write_text(json.dumps({'kind': 'tilekit-enlarged', 'texture': name, 'source': source, 'doubled': times, 'upscaler': reference.UPSCALER}, indent=1) + '\n', encoding='utf-8')
        told[name] = 'enlarged'
        if say: say(json.dumps({'texture': name, 'state': 'enlarged', 'size': [picture.shape[1] - 2 * cut, picture.shape[0] - 2 * cut]}), flush=True)
    return told


def picture_of(folder, name, word='doubled', command='enlarge'):
    """The picture of a texture (uint8 RGB array) that `enlarge`, or `redraw`, left in `folder`."""
    from PIL import Image
    path = Path(folder) / f'{name}.png' if folder is not None else None
    made = 'enlarged' if command == 'enlarge' else 'redrawn'
    require(path is not None and path.is_file(), f'{name} is to be {word} and has no {made} picture: run `tilekit {command}` and give its folder as --{made}')
    with Image.open(path) as picture:
        return np.asarray(picture.convert('RGB'))
