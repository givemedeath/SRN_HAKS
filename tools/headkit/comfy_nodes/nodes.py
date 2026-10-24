"""Standalone ComfyUI adapters used by the portable head toolkit.
Install this folder as custom_nodes/srn_headkit; no generation runs on import.
"""
import hashlib,json,time
from pathlib import Path
import numpy as np
import torch
import folder_paths
import comfy.model_management
from comfy_api.latest import Types
from .transport import write,read,KEYS
from .gltf import load,arrays

def decoded_mesh(data):
    document,binary,primitive=load(data)
    vertices,faces,_=arrays(document,binary,primitive)
    return vertices,faces.astype(np.int64)

def output_path(prefix,suffix):
    folder,name,counter,subfolder,_=folder_paths.get_save_image_path(prefix,folder_paths.get_output_directory())
    path=Path(folder)/f'{name}_{counter:05d}{suffix}'
    if path.exists():raise FileExistsError('Fresh export path required')
    return path,{'filename':path.name,'subfolder':subfolder,'type':'output'}

class HeadkitSaveShapeV1:
    @classmethod
    def INPUT_TYPES(cls):return {'required':{'latent':('LATENT',),'filename_prefix':('STRING',)}}
    RETURN_TYPES=('LATENT',); FUNCTION='save'; CATEGORY='srn/shape-checkpoint'; OUTPUT_NODE=True
    def save(self,latent,filename_prefix):
        if set(latent)!=KEYS:raise ValueError('Unexpected latent fields; preserve before extending transport')
        arrays={k:latent[k].detach().cpu().numpy() for k in ('samples','coords','coord_counts')};meta={k:latent[k] for k in ('coord_resolution','type','model_frame')}
        folder,name,counter,subfolder,_=folder_paths.get_save_image_path(filename_prefix,folder_paths.get_output_directory());path=Path(folder)/f'{name}_{counter:05d}.npz';write(path,arrays,meta)
        again,other=read(path)
        import numpy as np
        if other!=meta or any(not np.array_equal(v,again[k]) for k,v in arrays.items()):raise ValueError('Latent roundtrip mismatch')
        return {'ui':{'files':[{'filename':path.name,'subfolder':subfolder,'type':'output'}]},'result':(latent,)}

def summary(tensor):
    array = tensor.detach().cpu().numpy()
    return {'shape': list(array.shape), 'dtype': str(array.dtype),
            'device': str(tensor.device), 'stride': list(tensor.stride()),
            'sha256': hashlib.sha256(array.tobytes()).hexdigest(),
            'finite': bool(np.isfinite(array).all()),
            'min': float(array.min()), 'max': float(array.max())}

class HeadkitLoadShapeV1:
    """Restore native GPU coordinates; never project a saved shape on CPU implicitly."""
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'path': ('STRING',), 'sha256': ('STRING',)}}
    RETURN_TYPES = ('LATENT',)
    FUNCTION = 'load'
    CATEGORY = 'srn/shape-checkpoint'

    @classmethod
    def IS_CHANGED(cls, path, sha256):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def load(self, path, sha256):
        from .transport import read
        if self.IS_CHANGED(path, sha256) != sha256:
            raise ValueError('Frozen sparse checkpoint hash mismatch')
        arrays, meta = read(path)
        result = {**meta, **{k: torch.from_numpy(v) for k,v in arrays.items()}}
        result['coords'] = result['coords'].to(comfy.model_management.get_torch_device())
        if result['coords'].device.type != 'cuda':
            raise ValueError('This validated Pixal execution profile requires CUDA projection')
        return (result,)

class HeadkitDecodeShapeV1:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'latent': ('LATENT',), 'vae': ('VAE',),
            'chunk_budget_mb': ('INT', {'default': 512, 'min': 0, 'max': 512}),
            'filename_prefix': ('STRING',)}}
    RETURN_TYPES = ('MESH', 'SHAPE_SUBDIVIDES')
    FUNCTION = 'decode'
    CATEGORY = 'srn/diagnostics'
    OUTPUT_NODE = True

    def decode(self, latent, vae, chunk_budget_mb, filename_prefix):
        from comfy_extras.nodes_trellis2 import VaeDecodeShapeTrellis
        from comfy.ldm.trellis2 import flexgemm
        original = flexgemm.get_recommended_chunk_mem
        budgets = []
        def budget(*args, **kwargs):
            value = chunk_budget_mb / 1024 if chunk_budget_mb else original(*args, **kwargs)
            budgets.append(value)
            return value
        before = {k: summary(latent[k]) for k in ('samples','coords','coord_counts')}
        begun = time.monotonic()
        try:
            flexgemm.get_recommended_chunk_mem = budget
            result = VaeDecodeShapeTrellis.execute(latent, vae).result
        finally:
            flexgemm.get_recommended_chunk_mem = original
        after = {k: summary(latent[k]) for k in before}
        if before != after:
            raise ValueError('Decode changed the frozen latent')
        report = {'kind': 'audited-saved-shape-decode', 'latent': before,
            'chunkBudgetMb': chunk_budget_mb, 'actualChunkBudgetsGiB': budgets,
            'vaeDtype': str(vae.vae_dtype), 'matmulTf32': torch.backends.cuda.matmul.allow_tf32,
            'cudnnTf32': torch.backends.cudnn.allow_tf32, 'elapsedSeconds': time.monotonic()-begun,
            'latentUnchanged': True, 'diffusionSampling': False}
        folder, name, counter, subfolder, _ = folder_paths.get_save_image_path(filename_prefix,folder_paths.get_output_directory())
        path = Path(folder)/f'{name}_{counter:05d}.json'
        with path.open('x',encoding='utf-8') as f: json.dump(report,f,indent=2)
        return {'ui': {'files': [{'filename':path.name,'subfolder':subfolder,'type':'output'}]}, 'result': result}

class HeadkitSaveFieldV1:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'voxel': ('VOXEL',), 'filename_prefix': ('STRING',)}}
    RETURN_TYPES = ('VOXEL',)
    FUNCTION = 'save'
    CATEGORY = 'srn/trellis-review'
    OUTPUT_NODE = True

    def save(self, voxel, filename_prefix):
        coords = voxel.data.detach().cpu().numpy()
        attrs = voxel.voxel_colors.detach().cpu().numpy()
        if attrs.ndim != 2 or attrs.shape[-1] != 6 or len(attrs) != len(coords):
            raise ValueError('Require complete six-channel Trellis.2 appearance')
        if not np.isfinite(attrs).all() or not np.isfinite(coords).all():
            raise ValueError('Nonfinite generated field')
        path, row = output_path(filename_prefix, '.npz')
        with path.open('xb') as stream:
            np.savez(stream, coords=coords, attrs=attrs, resolution=int(voxel.resolution))
        return {'ui': {'files': [row]}, 'result': (voxel,)}

class HeadkitLoadMeshV1:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'path': ('STRING',), 'sha256': ('STRING',)}}
    RETURN_TYPES = ('MESH',)
    FUNCTION = 'load'
    CATEGORY = 'srn/trellis-review'

    def load(self, path, sha256):
        payload = Path(path).read_bytes()
        if hashlib.sha256(payload).hexdigest() != sha256: raise ValueError('Mesh hash changed')
        vertices, faces = decoded_mesh(payload)
        return (Types.MESH(torch.from_numpy(vertices).unsqueeze(0), torch.from_numpy(faces).unsqueeze(0)),)

NODE_CLASS_MAPPINGS={c.__name__:c for c in (HeadkitSaveShapeV1,HeadkitLoadShapeV1,HeadkitDecodeShapeV1,HeadkitSaveFieldV1,HeadkitLoadMeshV1)}
