"""Local generation for simple props: one ComfyUI job from a reference image to a textured low-poly GLB.

The shape and texture stages are the head kit's Pixal3D-on-Trellis-2 settings (tools/headkit/templates/geometry.json and
appearance.json), joined in one graph and followed by ComfyUI's own mesh nodes: remesh, decimate to a triangle target,
unwrap, bake colour, metal and roughness from the generated colour field and a normal map from the dense mesh. Nothing
is reviewed between the stages; the result is judged as a whole, like a Meshy prop.

The conditioning wants the subject cut out, so `matte` makes the reference's plain background transparent first."""
import urllib.error
import uuid
from pathlib import Path

from . import fresh, require

SUBFOLDER = 'envkit-local'
MODEL, VISION = 'pixal3d_int8_convrot.safetensors', 'dino_v3_L_naf_fp32.safetensors'
SHAPE_VAE, TEXTURE_VAE = 'trellis_2_shape_vae_bf16.safetensors', 'trellis_2_texture_vae_bf16.safetensors'
MOGE = 'moge_2_vitl_normal_fp16.safetensors'
MAPS = ('base_color', 'metallic', 'roughness', 'normal')
MASTER_TRIANGLES = 200000


def matte(source, target, tolerance=18):
    """Write `source` with its plain background made transparent: everything reachable from the image border through
    pixels within `tolerance` of the corner colour. White inside the object (a label, a recycling mark) is kept."""
    import numpy as np
    from PIL import Image, ImageDraw
    image = Image.open(source).convert('RGB'); width, height = image.size
    key = (255, 0, 255) if image.getpixel((0, 0)) != (255, 0, 255) else (0, 255, 0)
    filled = image.copy()
    for x, y in [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1), (width // 2, 0), (width // 2, height - 1),
                 (0, height // 2), (width - 1, height // 2)]:
        if filled.getpixel((x, y)) != key:
            ImageDraw.floodfill(filled, (x, y), key, thresh=tolerance)
    kept = (np.asarray(filled) != np.array(key, np.uint8)).any(axis=2)
    covered = float(kept.mean())
    require(0.03 < covered < 0.97, f'The matte kept {covered:.0%} of the image; the background is not plain or the subject fills the frame')
    image.putalpha(Image.fromarray(kept.astype(np.uint8) * 255, 'L')); target = Path(target); target.parent.mkdir(parents=True, exist_ok=True); image.save(target)
    return target


def compile_local(image, seed, triangles, prefix, *, texture=2048, shape_resolution=1024):
    """The whole job as an API graph. `image` is a staged RGBA reference; outputs go under `prefix`."""
    require(type(seed) is int and 0 <= seed < 2 ** 63 and type(triangles) is int and 200 <= triangles <= 100000, 'A seed and a triangle target (200-100000) are required')
    link = lambda node, slot=0: [node, slot]
    sampler = lambda model, cond, latent, steps, cfg, scheduler, offset: {'class_type': 'KSampler', 'inputs': {
        'seed': seed + offset, 'steps': steps, 'cfg': cfg, 'sampler_name': 'euler', 'scheduler': scheduler, 'denoise': 1.0, 'model': link(model),
        'positive': link(cond, 0), 'negative': link(cond, 1), 'latent_image': latent}}
    node = lambda kind, **inputs: {'class_type': kind, 'inputs': inputs}
    graph = {
        '1': node('LoadImage', image=image), '2': node('InvertMask', mask=link('1', 1)),
        '3': node('ImageCropToMask', images=link('1'), masks=link('2'), width=1024, height=1024, pad_factor=1.1, grow_mask=0, background='#000000'),
        '10': node('UNETLoader', unet_name=MODEL, weight_dtype='default'), '11': node('CLIPVisionLoader', clip_name=VISION),
        '12': node('VAELoader', vae_name=SHAPE_VAE), '13': node('VAELoader', vae_name=TEXTURE_VAE),
        # The camera's field of view is measured from the image, as the conditioning node asks and the head kit does;
        # a fixed guess bends the proportions of anything not drawn at that angle.
        '4': node('LoadMoGeModel', model_name=MOGE),
        '5': node('MoGeInference', moge_model=link('4'), image=link('3'), resolution_level=9, fov_x_degrees=0, batch_size=1,
                  force_projection=True, apply_mask=True, refine_steps=3),
        '6': node('MoGeGeometryToFOV', moge_geometry=link('5'), axis='horizontal', unit='degrees'),
        '20': node('Pixal3DConditioning', clip_vision_model=link('11'), image=link('3'), camera_angle_x=link('6')),
        # Shape: coarse structure, shape at that structure, then the shape again at the higher resolution.
        '21': node('CFGOverride', cfg=1, start_percent=0.667, end_percent=1, model=link('10')), '22': node('RescaleCFG', multiplier=0.7, model=link('21')),
        '23': node('ModelSamplingSD3', shift=5, model=link('22')), '24': node('EmptyTrellis2LatentStructure', batch_size=1),
        '25': sampler('23', '20', link('24'), 12, 7.5, 'normal', 0),
        '26': node('VaeDecodeStructureTrellis2', resolution='32', samples=link('25'), vae=link('12')),  # a choice, sent as text
        '27': node('Trellis2ShapeStage', positive=link('20', 0), negative=link('20', 1), voxel=link('26')),
        '28': node('CFGOverride', cfg=1, start_percent=0.769, end_percent=1, model=link('10')), '29': node('RescaleCFG', multiplier=0.5, model=link('28')),
        '30': sampler('29', '27', link('27', 2), 20, 12, 'normal', 1),
        '31': node('Trellis2UpsampleStage', target_resolution=shape_resolution, positive=link('27', 0), negative=link('27', 1), shape_latent=link('30'), vae=link('12')),
        '32': sampler('29', '31', link('31', 2), 12, 7.5, 'simple', 2),
        '33': node('VaeDecodeShapeTrellis', samples=link('32'), vae=link('12')),
        # Colour field on that shape.
        '40': node('ModelSamplingSD3', shift=3, model=link('10')),
        '41': node('Trellis2TextureStage', positive=link('20', 0), negative=link('20', 1), shape_latent=link('32')),
        '42': sampler('40', '41', link('41', 2), 12, 1, 'normal', 3),
        '43': node('VaeDecodeTextureTrellis', samples=link('42'), vae=link('13'), shape_subdivides=link('33', 1)),
        # Game mesh: a clean surface, cut to the triangle target, unwrapped, with the maps baked from the dense result.
        # `solid` gives one watertight skin with sharp edges kept. The first trash can used `udf`, which leaves an inner
        # shell behind the outer one; cutting that pair to 3,000 triangles tore it into shards.
        '50': node('RemeshMesh', mesh=link('33'), resolution=512, sign_mode='solid', band=1, project_back=0, fix_poles=False, smooth_iters=0,
                   drop_small_components=0.01, precluster_max_verts=20000000, **{'sign_mode.fill': 20.0, 'sign_mode.qef': True}),
        '51': node('DecimateMesh', mesh=link('50'), target_face_count=triangles, placement_mode='qem',
                   **{'placement_mode.line_quadric_weight': 1.0, 'placement_mode.feature_edge_quadric_weight': 5.0,
                      'placement_mode.feature_edge_min_dihedral_deg': 30.0, 'placement_mode.clamp_v_to_edge': True}),
        '52': node('UnwrapMesh', mesh=link('51'), segmenter='pec', resolution=texture, padding=2, weld_distance=0),
        '53': node('BakeTextureFromVoxel', mesh=link('52'), voxel_colors=link('43'), texture_size=texture, reference_mesh=link('33')),
        '54': node('BakeNormalMapFromMesh', low_poly=link('52'), high_poly=link('33'), resolution=texture, cage_distance=0.05, ignore_backfaces=True),
        '55': node('ApplyTextureToMesh', mesh=link('52'), base_color=link('53', 0), metallic=link('53', 1), roughness=link('53', 2), normal_map=link('54')),
        '56': node('SaveGLB', mesh=link('55'), filename_prefix=prefix + '/model'),
        # The spare: the same skin at a high count, without maps (see the Meshy master rule in meshy.py).
        '57': node('DecimateMesh', mesh=link('50'), target_face_count=MASTER_TRIANGLES, placement_mode='midpoint'),
        '58': node('SaveGLB', mesh=link('57'), filename_prefix=prefix + '/master'),
    }
    for number, (name, source) in enumerate(zip(MAPS, (link('53', 0), link('53', 1), link('53', 2), link('54'))), 60):
        graph[str(number)] = node('SaveImage', images=source, filename_prefix=f'{prefix}/{name}')
    return graph


def make(client, local, name, reference, seed, triangles, output, *, texture=2048, deadline=3600):
    """Run one prop on the bound ComfyUI and copy its model and maps into a fresh `output` folder, named as a Meshy
    download is (`model.glb`, `texture_0_<map>.png`). A busy server is left alone."""
    import json
    import shutil
    from ..headkit import design
    output = Path(output)
    require(not output.exists(), 'Fresh output folder required: ' + str(output))
    queue = client.request('/queue')
    require(not queue.get('queue_running') and not queue.get('queue_pending'), 'ComfyUI is busy; nothing submitted')
    token = uuid.uuid4().hex; prefix = f'{SUBFOLDER}/{token}'
    staged = Path(local['comfyInput']) / SUBFOLDER / token / 'reference.png'
    matte(reference, staged)
    graph = compile_local(f'{SUBFOLDER}/{token}/reference.png', seed, triangles, prefix, texture=texture)
    record = {'asset': name, 'seed': seed, 'triangles': triangles, 'token': token, 'graph': graph}
    try:
        try:
            design.dispatch(client, graph, token, record, deadline=deadline)
        except urllib.error.HTTPError as error:  # the server's reason for refusing a graph is in the response body
            raise ValueError('ComfyUI refused the job: ' + error.read().decode('utf-8', 'replace')[:3000]) from error
        made = Path(local['comfyOutput']) / SUBFOLDER / token
        models = sorted(made.glob('model*.glb'))
        require(len(models) == 1, f'Expected one model, found {len(models)}')
        with fresh(output) as staging:  # a job missing a map leaves no half-filled output folder
            shutil.copyfile(models[0], staging / 'model.glb')
            for master in sorted(made.glob('master*.glb'))[:1]:
                shutil.copyfile(master, staging / 'master.glb')
            for kind in MAPS:
                images = sorted(made.glob(kind + '*.png'))
                require(len(images) == 1, f'Expected one {kind} map, found {len(images)}')
                shutil.copyfile(images[0], staging / f'texture_0_{kind}.png')
        record['state'] = 'complete'
    except Exception as error:
        record.update(state='failed', error=str(error)); raise
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        (output.parent / (output.name + '.json')).write_text(json.dumps(record, indent=1), encoding='utf-8')
    return record
