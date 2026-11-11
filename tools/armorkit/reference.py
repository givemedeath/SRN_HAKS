"""A reference image for a generated outfit, made on the local image engine from the outfit's brief.

The prompt is never handed in: it is the brief's (`brief.seal`), so the kind of every material is on record
before an image exists, and each image that comes back is registered with the brief it was made from
(`brief.register`). One job at a time, on headkit's reviewed design graph; nothing leaves this machine.
"""
import json
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from tools.headkit import comfy, design

from . import brief
from .registry import require

URL = 'http://127.0.0.1:8188'
STAGED = 'headkit-design/armorkit-ref'  # where the engine keeps the images a job is given and the ones it makes


def upload(url, path, name):
    """Hand the engine an image to work from; returns the name it knows it by."""
    boundary = uuid.uuid4().hex
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"\r\n\r\n{value}\r\n'.encode()
             for field, value in (('subfolder', STAGED), ('type', 'input'), ('overwrite', 'true'))]
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\nContent-Type: image/png\r\n\r\n'.encode()
                 + Path(path).read_bytes() + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    request = urllib.request.Request(url + '/upload/image', data=b''.join(parts), headers={'Content-Type': 'multipart/form-data; boundary=' + boundary})
    with urllib.request.urlopen(request, timeout=120) as response:
        answer = json.loads(response.read())
    return (answer.get('subfolder', '') + '/' + answer['name']).lstrip('/')


def fetch(url, row):
    """The bytes of an image the engine made (`row` as its history names it)."""
    query = urllib.parse.urlencode({'filename': row['filename'], 'subfolder': row.get('subfolder', ''), 'type': row.get('type', 'output')})
    with urllib.request.urlopen(url + '/view?' + query, timeout=120) as response:
        return response.read()


def generate(brief_path, folder, seed, batch=1, references=(), url=URL, profile=design.DEFAULT_PROFILE, deadline=1800):
    """Make reference images from a brief: the paths of the images, in a new run folder under `folder`.

    `folder` is sealed with the brief first, which writes the prompt there; a brief that does not hold, or one
    whose materials are drawn too alike, is refused before the engine is asked for anything. `references` are
    earlier images the engine is to work from. The run folder gets the prompt as sent, the images and a record
    of the job, and the images are registered in the folder's seal."""
    require(isinstance(seed, int) and isinstance(batch, int) and batch >= 1, 'A seed and a number of images are whole numbers')
    references = [Path(path).resolve() for path in references]
    require(all(path.is_file() for path in references), 'A reference is an image file')
    folder = Path(folder).resolve()
    text = brief.seal(brief.load(brief_path), folder)
    run = folder / f'run-{len(list(folder.glob("run-*"))) + 1}'
    run.mkdir()
    token = 'armorkit-' + uuid.uuid4().hex[:10]
    client = comfy.Client(url)
    staged = [upload(url, path, f'{token}-{index}{path.suffix.lower()}') for index, path in enumerate(references)]
    graph = design.compile_design(text, staged, seed, batch, f'{STAGED}/{token}', profile=profile)
    record = {'token': token, 'model': brief.sealed(folder)[0]['model'], 'seed': seed, 'batch': batch,
              'references': [path.name for path in references], 'staged': staged, 'profile': profile}
    (run / 'prompt.txt').write_text(text + '\n', encoding='utf-8', newline='\n')
    started = time.time()
    entry = design.dispatch(client, graph, token, record, deadline=deadline)
    record['seconds'] = round(time.time() - started, 1)
    images = []
    for index, row in enumerate(entry.get('outputs', {}).get('9', {}).get('images', [])):
        images.append(run / f'image-{index}.png')
        images[-1].write_bytes(fetch(url, row))
    record['images'] = len(images)
    (run / 'record.json').write_text(json.dumps(record, indent=1) + '\n', encoding='utf-8', newline='\n')
    brief.register(folder, *images)
    return images
