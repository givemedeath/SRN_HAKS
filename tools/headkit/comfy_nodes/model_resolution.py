"""Verify model bytes selected by ComfyUI's own checkpoint-folder resolver."""
import hashlib
import os
from pathlib import Path


# Keep this mapping aligned with the loader nodes used by the frozen graphs.
# The categories are ComfyUI folder_paths namespaces, not local binding labels.
MODEL_FIELDS = {
    ('UNETLoader', 'unet_name'): 'diffusion_models',
    ('CLIPVisionLoader', 'clip_name'): 'clip_vision',
    ('VAELoader', 'vae_name'): 'vae',
    ('LoadMoGeModel', 'model_name'): 'geometry_estimation',
}
MODEL_FIELD_NAMES = frozenset(field for _, field in MODEL_FIELDS)


def _simple_filename(name):
    return (isinstance(name, str) and bool(name) and name not in ('.', '..')
            and not any(character in name for character in ('/', '\\', '\0'))
            and Path(name).name == name)


def model_choices(graph):
    """Return all supported loader category/name pairs actually used by a graph."""
    if not isinstance(graph, dict):
        raise ValueError('Prepared Comfy graph is invalid')
    choices = set()
    for node in graph.values():
        if not isinstance(node, dict) or not isinstance(node.get('inputs', {}), dict):
            raise ValueError('Malformed Comfy graph node')
        class_type = node.get('class_type')
        for field, name in node.get('inputs', {}).items():
            if field not in MODEL_FIELD_NAMES:
                if isinstance(field, str) and (field.endswith('_name') or field in ('ckpt_name', 'checkpoint')):
                    raise ValueError(f'Unsupported Comfy model loader field: {class_type}.{field}')
                continue
            category = MODEL_FIELDS.get((class_type, field))
            if category is None:
                raise ValueError(f'Unsupported Comfy model loader field: {class_type}.{field}')
            if not _simple_filename(name):
                raise ValueError('Comfy checkpoint choice must be a simple filename')
            choices.add((category, name))
    return sorted(choices)


def path_identity(path):
    """Return a stable opaque identity for a fully resolved local path."""
    resolved = Path(path).resolve(strict=True)
    normalized = os.path.normcase(os.path.normpath(str(resolved)))
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def loader_models(graph, bindings, checkpoint_hashes):
    """Freeze the folder category and bound file identity for each graph loader."""
    models = {}
    for category, name in model_choices(graph):
        row = bindings.get(name)
        if not isinstance(row, dict) or not {'path', 'sha256'} <= set(row):
            raise ValueError('Missing checkpoint byte binding: ' + name)
        if row['sha256'] != checkpoint_hashes.get(name):
            raise ValueError('Checkpoint differs from frozen reviewed profile')
        resolved = Path(row['path']).resolve(strict=True)
        if resolved.name != name:
            raise ValueError('Model binding filename differs from loader choice')
        if file_sha256(resolved) != row['sha256']:
            raise ValueError('Stale checkpoint byte binding: ' + name)
        models[(category, name)] = {'category': category, 'name': name,
                                    'pathIdentity': path_identity(resolved), 'sha256': row['sha256']}
    return [models[key] for key in sorted(models)]


def verify_loader_models(expected, folder_paths):
    """Compare frozen bindings with the exact paths ComfyUI loaders resolve."""
    if not isinstance(expected, list):
        raise ValueError('Expected Comfy loader model list')
    resolver = getattr(folder_paths, 'get_full_path_or_raise', None)
    if not callable(resolver):
        raise ValueError('ComfyUI does not expose the loader path resolver required by headkit')
    seen = set()
    for item in expected:
        if not isinstance(item, dict) or set(item) != {'category', 'name', 'pathIdentity', 'sha256'}:
            raise ValueError('Malformed Comfy loader model pin')
        category, name = item['category'], item['name']
        if category not in set(MODEL_FIELDS.values()):
            raise ValueError('Unsupported Comfy model folder category')
        if not _simple_filename(name):
            raise ValueError('Comfy checkpoint choice must be a simple filename')
        key = (category, name)
        if key in seen:
            raise ValueError('Duplicate Comfy loader model pin')
        seen.add(key)
        actual = Path(resolver(category, name)).resolve(strict=True)
        if not actual.is_file():
            raise ValueError('Comfy loader did not resolve a regular checkpoint file')
        if path_identity(actual) != item['pathIdentity']:
            raise ValueError('Comfy loader resolved a different checkpoint path')
        if file_sha256(actual) != item['sha256']:
            raise ValueError('Comfy loader resolved checkpoint bytes differ from the reviewed pin')
    return {'verified': True, 'count': len(expected)}
