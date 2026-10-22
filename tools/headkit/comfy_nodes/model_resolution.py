"""Verify model bytes selected by ComfyUI's own checkpoint-folder resolver."""
import hashlib
import os
from pathlib import Path


# Keep this mapping aligned with the loader nodes used by the frozen graphs.
# The categories are ComfyUI folder_paths namespaces, not local binding labels.
STANDARD_MODEL_FIELDS = {
    ('UNETLoader', 'unet_name'): 'diffusion_models',
    ('CLIPVisionLoader', 'clip_name'): 'clip_vision',
    ('VAELoader', 'vae_name'): 'vae',
    ('LoadMoGeModel', 'model_name'): 'geometry_estimation',
}
VERIFIED_LOADER_TYPES = {
    original: 'HeadkitVerified' + original + 'V1'
    for original in {class_type for class_type, _ in STANDARD_MODEL_FIELDS}
}
VERIFIED_MODEL_FIELDS = {
    (verified, field): category
    for (original, field), category in STANDARD_MODEL_FIELDS.items()
    for verified in (VERIFIED_LOADER_TYPES[original],)
}
MODEL_FIELDS = {**STANDARD_MODEL_FIELDS, **VERIFIED_MODEL_FIELDS}
MODEL_FIELD_NAMES = frozenset(field for _, field in MODEL_FIELDS)
MODEL_PIN_FIELDS = ('headkit_model_sha256', 'headkit_model_path_identity')
# These selectors contain the word "name" but select algorithms, not model files.
NON_FILE_NAME_FIELDS = frozenset({'sampler_name'})


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
                if isinstance(field, str) and field not in NON_FILE_NAME_FIELDS and \
                        (field.endswith('_name') or field in ('ckpt_name', 'checkpoint')):
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


def bind_loader_models(graph, models):
    """Replace standard loaders with hash-keyed adapters and pin their inputs."""
    if not isinstance(graph, dict) or not isinstance(models, list):
        raise ValueError('Comfy graph and loader model pins are required')
    by_choice = {(item.get('category'), item.get('name')): item for item in models
                 if isinstance(item, dict)}
    result = {node_id: {**node, 'inputs': dict(node.get('inputs', {}))}
              for node_id, node in graph.items()}
    for node in result.values():
        class_type, inputs = node['class_type'], node['inputs']
        for field, name in list(inputs.items()):
            category = STANDARD_MODEL_FIELDS.get((class_type, field))
            if category is None:
                continue
            pin = by_choice.get((category, name))
            if pin is None:
                raise ValueError('Comfy loader has no reviewed model pin')
            if any(key in inputs for key in MODEL_PIN_FIELDS):
                raise ValueError('Comfy loader already contains headkit model pin inputs')
            inputs['headkit_model_sha256'] = pin['sha256']
            inputs['headkit_model_path_identity'] = pin['pathIdentity']
            node['class_type'] = VERIFIED_LOADER_TYPES[class_type]
    validate_bound_loader_nodes(result, models)
    return result


def validate_bound_loader_nodes(graph, expected):
    """Require every graph model choice to use its exact hash-keyed loader."""
    if not isinstance(graph, dict) or not isinstance(expected, list):
        raise ValueError('Comfy graph and loader model pins are required')
    pins = {(item.get('category'), item.get('name')): item for item in expected
            if isinstance(item, dict)}
    seen = set()
    for node in graph.values():
        class_type, inputs = node.get('class_type'), node.get('inputs', {})
        for field, name in inputs.items():
            category = MODEL_FIELDS.get((class_type, field))
            if category is None:
                continue
            choice = (category, name)
            if class_type not in VERIFIED_LOADER_TYPES.values():
                raise ValueError('Comfy model loader is missing its hash-keyed headkit adapter')
            pin = pins.get(choice)
            if pin is None or inputs.get('headkit_model_sha256') != pin.get('sha256') or \
                    inputs.get('headkit_model_path_identity') != pin.get('pathIdentity'):
                raise ValueError('Comfy model loader inputs differ from the reviewed path and byte pins')
            seen.add(choice)
    if seen != set(pins):
        raise ValueError('Comfy graph model choices do not exactly match the reviewed pins')
    return True


def verify_model_file(category, name, path_identity_value, sha256, folder_paths):
    """Resolve and verify one model immediately before a headkit loader reads it."""
    if category not in set(MODEL_FIELDS.values()) or not _simple_filename(name):
        raise ValueError('Unsupported Comfy model folder choice')
    resolver = getattr(folder_paths, 'get_full_path_or_raise', None)
    if not callable(resolver):
        raise ValueError('ComfyUI does not expose the required model path resolver')
    actual = Path(resolver(category, name)).resolve(strict=True)
    if not actual.is_file() or actual.name != name:
        raise ValueError('Comfy loader did not resolve the reviewed model file')
    if path_identity(actual) != path_identity_value:
        raise ValueError('Comfy loader resolved a different model path')
    if file_sha256(actual) != sha256:
        raise ValueError('Comfy loader resolved model bytes different from the reviewed pin')
    return actual


def verify_loader_models(expected, folder_paths, graph=None):
    """Compare frozen bindings with the exact paths ComfyUI loaders resolve."""
    if not isinstance(expected, list) or not all(
            isinstance(item, dict) and set(item) == {'category', 'name', 'pathIdentity', 'sha256'}
            for item in expected):
        raise ValueError('Expected complete Comfy loader model pins')
    if graph is not None:
        if model_choices(graph) != sorted((item.get('category'), item.get('name')) for item in expected):
            raise ValueError('Comfy graph model choices differ from the reviewed pins')
        validate_bound_loader_nodes(graph, expected)
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
        verify_model_file(category, name, item['pathIdentity'], item['sha256'], folder_paths)
    return {'verified': True, 'count': len(expected)}
