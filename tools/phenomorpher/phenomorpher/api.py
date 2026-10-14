"""Stable numerical API. Never writes published body or animation resources."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import numpy as np

from .engine.fit_anatomy_stage1_v15a import fit_stage1
from .engine.morph_anatomy_v15c import fit_stage2, geometry_hash
from .engine.morph_preview_pose_v13 import native_keys_hash
from .engine.check_connector_surfaces_v15 import audit as audit_connectors
from .engine.silhouette_model import assemble, rasterize, measure, cross_section
from .engine.phenomorpher_scene_v15b import read_attributes, export_glb, derived_normals
from .engine.convert_model import convert_text


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def bound(root, row, verified_snapshot=None):
    root = Path(root).resolve()
    path = (root / row['path']).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Source binding escaped root: ' + row['path'])
    actual = digest(path) if verified_snapshot is None else verified_snapshot.get(str(path))
    if actual != row['sha256']:
        raise ValueError('Escaped or stale source binding: ' + row['path'])
    return path


def verify_assets(root, manifest, verified_snapshot=None):
    data = json.loads(Path(manifest).read_text(encoding='utf-8-sig'))
    if data.get('kind') != 'PhenoMorpher-game-ready-bodies' or data.get('schemaVersion') != 1:
        raise ValueError('Supported game-ready body manifest required')
    if not data.get('resources') or not data.get('targets'):
        raise ValueError('Nonempty target and resource inventory required')
    identities = set()
    for row in data['resources']:
        path = bound(root, row, verified_snapshot)
        if path in identities:
            raise ValueError('Duplicate publication resource')
        identities.add(path)
        if path.stat().st_size != row['bytes']:
            raise ValueError('Resource length mismatch')
    return {'version': data['version'], 'targets': len(data['targets']),
            'resources': len(identities), 'verified': True, 'assetApprovalCreated': False}


def fit_candidate(meshes, frames, motion, reference, policy=None):
    """Freeze per-part similarities/chain placement, then recompute broad morphology.

    Native motion inputs must supply all six source-owned clips. Human Fit
    controls automatically take the exact identity path. The caller owns input
    loading and subsequent visual/native/client review; this is an offline proposal.
    """
    meshes = deepcopy(meshes)
    frames = {n: np.asarray(f, dtype=float) for n, f in frames.items()}
    for mesh in meshes:
        mesh['position'] = np.asarray(mesh['position'], dtype=float)
        mesh['faces'] = np.asarray(mesh['faces'], dtype=int)
    before = geometry_hash(meshes)
    keys = native_keys_hash(motion)
    identity = reference.get('slug') in ('human_male_fit', 'human_female_fit')
    first = fit_stage1(meshes, frames, motion, reference, policy, preserve=identity)
    frozen = geometry_hash(first['standingMeshes'])
    second = fit_stage2(first, reference, policy, preserve=identity)
    if geometry_hash(first['standingMeshes']) != frozen or geometry_hash(meshes) != before:
        raise ValueError('Morphing modified its frozen first pass or source')
    if native_keys_hash(motion) != keys:
        raise ValueError('Source animation keys changed')
    second['receipt'].update(toolkit='PhenoMorpher', frozenFirstPassGeometryHash=frozen,
                             sourceAnimationKeysExact=True, assetApprovalCreated=False)
    return first, second


def encode(value):
    if isinstance(value, np.ndarray):
        return {'$array': value.tolist(), 'dtype': value.dtype.str, 'shape': list(value.shape)}
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError('Unsupported recipe value: ' + type(value).__name__)


def array_hook(value):
    if '$array' not in value:
        return value
    dtype = np.dtype(value['dtype'])
    if dtype.hasobject or dtype.kind not in 'biuf' or dtype.itemsize > 8:
        raise ValueError('Numeric recipe arrays only')
    result = np.asarray(value['$array'], dtype=dtype)
    if list(result.shape) != value['shape'] or result.size > 16_000_000 or not np.isfinite(result).all():
        raise ValueError('Invalid or oversized recipe array')
    return result


def load_recipe(path):
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'), object_hook=array_hook)
    if data.get('kind') != 'PhenoMorpher-candidate-inputs' or data.get('schemaVersion') != 1:
        raise ValueError('Versioned candidate input bundle required')
    for clip in data['motion']['clips'].values():
        for node in clip['nodes'].values():
            node['controls'] = {int(k): v for k, v in node['controls'].items()}
    return data


def save_recipe(path, data):
    Path(path).write_text(json.dumps(data, default=encode, allow_nan=False, indent=2) + '\n',
                          encoding='utf-8', newline='\n')


def display_scene(stage, parents, output):
    """Neutral diagnostic GLB; display normals do not modify saved geometry/attributes."""
    meshes = deepcopy(stage['standingMeshes'])
    for mesh in meshes:
        if len(mesh['faces']):
            mesh['normal'] = derived_normals(mesh['position'], mesh['faces'])
    export_glb(meshes, stage['standingFrames'], parents, output)
