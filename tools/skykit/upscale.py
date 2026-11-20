"""2x upscale of an assembled panorama with RealESRGAN on the shared ComfyUI (its HTTP API only), cached by content.

The picture is padded with its own other end before upscaling so the wrap round the horizon stays seamless, and the
result is kept under output/skykit/<key>/ named by a hash of the input and the model: a rebuild of unchanged art needs
no GPU. Set SRN_COMFY_URL to reach a ComfyUI other than http://127.0.0.1:8188.
"""
import hashlib
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import numpy as np
from PIL import Image

from .panorama import to_u8

MODEL = 'RealESRGAN_x2plus.pth'
SCALE = 2
PAD = 64  # columns of the other end laid either side, so the upscaler sees across the wrap


def _png(array):
    data = to_u8(array)
    buffer = io.BytesIO()
    Image.fromarray(data, 'RGB').save(buffer, 'PNG')
    return buffer.getvalue()


def _request(url, data=None, headers=None):
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers or {}), timeout=60) as reply:
        return reply.read()


def _upload(url, name, payload, subfolder='skykit'):
    boundary = uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\n'
            f'Content-Type: image/png\r\n\r\n').encode() + payload + (
            f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="subfolder"\r\n\r\n{subfolder}'
            f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n--{boundary}--\r\n').encode()
    reply = json.loads(_request(url + '/upload/image', body, {'Content-Type': f'multipart/form-data; boundary={boundary}'}))
    return f"{reply['subfolder']}/{reply['name']}" if reply.get('subfolder') else reply['name']


def run_graph(url, picture, name, nodes, timeout=900, subfolder='skykit', output='out'):
    """Upload `picture` into `subfolder`, queue the graph `nodes(image, prefix)` and return the image its `output` node
    saved."""
    image = _upload(url, f'{name}.png', _png(picture), subfolder)
    graph = nodes(image, f'{subfolder}/{name}')
    prompt = json.loads(_request(url + '/prompt', json.dumps({'prompt': graph, 'client_id': uuid.uuid4().hex}).encode(),
                                 {'Content-Type': 'application/json'}))['prompt_id']
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            history = json.loads(_request(f'{url}/history/{prompt}')).get(prompt)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            # a busy ComfyUI can miss a poll; the job runs on, so keep asking until the deadline
            print(f'note: ComfyUI history poll for {name} failed ({error}); retrying', flush=True)
            time.sleep(5)
            continue
        if history and history.get('status', {}).get('completed'):
            images = history.get('outputs', {}).get(output, {}).get('images')
            if not images:
                raise RuntimeError(f'ComfyUI job {name} finished but its node {output!r} saved no image')
            saved = images[0]
            query = urllib.parse.urlencode({'filename': saved['filename'], 'subfolder': saved['subfolder'], 'type': saved['type']})
            return np.asarray(Image.open(io.BytesIO(_request(f'{url}/view?{query}'))).convert('RGB'), np.float32) / 255
        if history and history.get('status', {}).get('status_str') == 'error':
            raise RuntimeError(f'ComfyUI job {name} failed: {history["status"]}')
        time.sleep(2)
    raise TimeoutError(f'ComfyUI job {prompt} did not finish in {timeout} s')


def comfy_url(url=None):
    return (url or os.environ.get('SRN_COMFY_URL') or 'http://127.0.0.1:8188').rstrip('/')


def _upscale_graph(image, prefix):
    return {
        '1': {'class_type': 'LoadImage', 'inputs': {'image': image}},
        '2': {'class_type': 'UpscaleModelLoader', 'inputs': {'model_name': MODEL}},
        '3': {'class_type': 'ImageUpscaleWithModel', 'inputs': {'upscale_model': ['2', 0], 'image': ['1', 0]}},
        'out': {'class_type': 'SaveImage', 'inputs': {'images': ['3', 0], 'filename_prefix': prefix}},
    }


def key(array):
    """The cache name's hash: the input and everything that shapes the result from it (model and wrap padding)."""
    return hashlib.sha256(np.ascontiguousarray(array, np.float32).tobytes() + f'{MODEL}|pad={PAD}'.encode()).hexdigest()[:16]


def upscale(array, folder, url=None):
    """`array` (float RGB rows of a wrapped strip) at SCALE times its size: from the cache, or from ComfyUI."""
    folder = Path(folder)
    target = folder / f'x{SCALE}-{key(array)}.png'
    if not target.is_file():
        url = comfy_url(url)
        padded = np.concatenate([array[:, -PAD:], array, array[:, :PAD]], axis=1)
        out = run_graph(url, padded, f'{folder.name}-{target.stem}', _upscale_graph)
        if out.shape[:2] != (padded.shape[0] * SCALE, padded.shape[1] * SCALE):
            raise RuntimeError(f'upscaled to {out.shape[:2]}, expected {SCALE} times {padded.shape[:2]}')
        folder.mkdir(parents=True, exist_ok=True)
        Image.fromarray(to_u8(out[:, PAD * SCALE:-PAD * SCALE])).save(target)
    return np.asarray(Image.open(target).convert('RGB'), np.float32) / 255, target
