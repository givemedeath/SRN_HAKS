"""Client metadata for models whose bytes are verified by the owning Comfy server.

This never establishes byte validity itself. Preparation, dispatch and completion
must obtain a fresh server verification using these exact loader/path/hash pins.
"""
from pathlib import Path
from .common import require
from .comfy_nodes.model_resolution import model_choices, path_identity


SERVER_MODEL_VERIFICATION = 'server-owned-v1'


def model_contract(graph, bindings, checkpoints):
    models = []; inputs = []
    for category, name in model_choices(graph):
        row = bindings.get(name)
        require(isinstance(row, dict) and set(row) == {'path', 'sha256'}, 'Missing checkpoint byte binding: '+name)
        require(row['sha256'] == checkpoints.get(name), 'Checkpoint differs from frozen reviewed profile')
        path = Path(row['path']).resolve(strict=True)
        require(path.is_file() and path.name == name, 'Model binding filename differs from loader choice')
        models.append({'category':category, 'name':name, 'pathIdentity':path_identity(path), 'sha256':row['sha256']})
        if row not in inputs: inputs.append(dict(row))
    return models, inputs
