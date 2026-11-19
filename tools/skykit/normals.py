"""Surface normals of a land strip, from MoGe-2 on the shared ComfyUI (its HTTP API only), cached by content.

The strip is cut into overlapping tiles of about 60 degrees round the horizon, each with a matching field of view and
sky laid above it, and the tiles' normal maps are blended back into one wrapped strip. Normals are in the viewer's
frame at each column: x to the right, y up, z toward the viewer. The shader relights the land with them.
"""
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image

from .panorama import to_u8
from .upscale import comfy_url, run_graph

MODEL = 'moge_2_vitl_normal_fp16.safetensors'
TILE = (1536, 1024)  # texels of a tile: its width sets its field of view
STEP = 1122           # columns between tiles: neighbours overlap by a quarter
SKY = (0.04, 0.05, 0.12)


def _graph(fov):
    def nodes(image, prefix):
        return {
            '1': {'class_type': 'LoadImage', 'inputs': {'image': image}},
            '2': {'class_type': 'LoadMoGeModel', 'inputs': {'model_name': MODEL}},
            '3': {'class_type': 'MoGeInference', 'inputs': {'moge_model': ['2', 0], 'image': ['1', 0], 'resolution_level': 9,
                                                            'fov_x_degrees': fov, 'batch_size': 1, 'force_projection': True,
                                                            'apply_mask': False, 'refine_steps': 0}},
            '4': {'class_type': 'MoGeRender', 'inputs': {'moge_geometry': ['3', 0], 'output': 'normal_opengl'}},
            'out': {'class_type': 'SaveImage', 'inputs': {'images': ['4', 0], 'filename_prefix': prefix}},
        }
    return nodes


def key(strip):
    """The cache name's hash: the strip and everything that shapes the normals from it (model, tiling, sky fill)."""
    settings = f'{MODEL}|tile={TILE}|step={STEP}|sky={SKY}'
    return hashlib.sha256(np.ascontiguousarray(strip, np.float32).tobytes() + settings.encode()).hexdigest()[:16]


def normals(strip, folder, url=None):
    """(rows x columns x 3) unit normals of the land in `strip` (RGBA, wrapped), and the cache file."""
    folder = Path(folder)
    target = folder / f'normals-{key(strip)}.png'
    if not target.is_file():
        url = comfy_url(url)
        height, width = strip.shape[:2]
        rgb = np.where(strip[..., 3:] > 0.5, strip[..., :3], np.array(SKY, np.float32))
        pad = max(TILE[1] - height, 0)
        fov = 360.0 * TILE[0] / width
        total = np.zeros((height, width, 3), np.float32)
        weight = np.zeros((1, width, 1), np.float32)
        ramp = (np.minimum(np.arange(TILE[0]), TILE[0] - 1 - np.arange(TILE[0])) + 1.0).astype(np.float32)[None, :, None]
        for index in range(-(-width // STEP)):
            columns = (index * STEP + np.arange(TILE[0])) % width
            tile = np.concatenate([np.broadcast_to(np.array(SKY, np.float32), (pad, TILE[0], 3)), rgb[:, columns]], axis=0)
            out = run_graph(url, tile, f'{folder.name}-normals-{index}', _graph(fov))
            if out.shape[:2] != tile.shape[:2]:
                out = np.asarray(Image.fromarray(to_u8(out)).resize(tile.shape[1::-1], Image.BILINEAR),
                                 np.float32) / 255
            np.add.at(total, (slice(None), columns), (out[pad:] * 2 - 1) * ramp)
            np.add.at(weight, (slice(None), columns), ramp)
        field = total / np.maximum(weight, 1e-6)
        field /= np.maximum(np.linalg.norm(field, axis=-1, keepdims=True), 1e-6)
        folder.mkdir(parents=True, exist_ok=True)
        Image.fromarray(to_u8(field * 0.5 + 0.5)).save(target)
    field = np.asarray(Image.open(target).convert('RGB'), np.float32) / 255 * 2 - 1
    return field, target
