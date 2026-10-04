"""Brief actual textured wrist/hand review; root grants the local GPU slot."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Matrix, Vector
import numpy as np

P = Path(__file__).resolve().parent
R = P.parents[2]
sys.path.insert(0, str(R / 'tools/phenotypes'))
from retarget import nodes, transforms


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    a = parser.parse_args(sys.argv[sys.argv.index('--') + 1:]); out = a.output.resolve()
    if out.parent != P.resolve() or out.exists():
        raise RuntimeError('Fresh owned output required')
    inputs = {'l': P / 'left-uniform-stock-v1/placed-local.glb',
              'r': P / 'right-uniform-stock-mirror-v1/mirrored-local.glb'}
    fore = R / 'output/phenotypes/purposebuilt-forearm-pilot-v1'
    neighbours = {'l': fore / 'left-proximal-taper-moderate-v1/tapered-local.glb',
                  'r': fore / 'right-proximal-taper-moderate-mirror-v1/mirrored-local.glb'}
    stock = R / 'output/phenotypes/purposebuilt-stock-inputs-v1/stock/ascii/pmh0.mdl'
    world = transforms(nodes(stock.read_text()))
    hashes = {str(p): sha(p) for p in [*inputs.values(), *neighbours.values(), stock, Path(__file__)]}
    out.mkdir(); records = []
    for side in ['l', 'r']:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(inputs[side]))
        hands = [o for o in bpy.context.scene.objects if o.type == 'MESH']
        hand_points = [o.matrix_world @ Vector(c) for o in hands for c in o.bound_box]
        center = Vector(tuple((min(p[i] for p in hand_points) + max(p[i] for p in hand_points)) / 2 for i in range(3)))
        span = .245
        before = set(bpy.context.scene.objects)
        bpy.ops.import_scene.gltf(filepath=str(neighbours[side]))
        fore_matrix = Matrix((np.linalg.inv(world[side + 'hand_g']) @ world[side + 'forearm_g']).tolist())
        fore_objects = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o not in before]
        for obj in fore_objects:
            obj.matrix_world = fore_matrix @ obj.matrix_world
        scene = bpy.context.scene; scene.render.engine = 'BLENDER_EEVEE'
        scene.render.resolution_x = scene.render.resolution_y = 850
        scene.render.resolution_percentage = 100; scene.render.image_settings.file_format = 'PNG'
        scene.eevee.taa_render_samples = 32; scene.eevee.use_gtao = True
        scene.eevee.gtao_distance = .03; scene.eevee.gtao_factor = 1.
        scene.view_settings.view_transform = 'Standard'; scene.view_settings.look = 'Medium High Contrast'
        background = bpy.data.worlds.new('neutral-review-background'); background.use_nodes = True
        background.node_tree.nodes['Background'].inputs['Color'].default_value = (.075, .075, .075, 1)
        background.node_tree.nodes['Background'].inputs['Strength'].default_value = .65; scene.world = background
        camera_data = bpy.data.cameras.new('orthographic-camera'); camera_data.type = 'ORTHO'; camera_data.ortho_scale = span
        camera = bpy.data.objects.new('orthographic-camera', camera_data); scene.collection.objects.link(camera); scene.camera = camera
        lights = []
        for label, energy, size in [('key', 5., .28), ('fill', 2., .38)]:
            data = bpy.data.lights.new(label, 'AREA'); data.energy = energy; data.shape = 'DISK'; data.size = size
            light = bpy.data.objects.new(label, data); scene.collection.objects.link(light); lights.append(light)
        for label, direction in [('palm', (1 if side == 'l' else -1, 0., 0.)),
                                 ('oblique', (1 if side == 'l' else -1, .65, -.30))]:
            back = Vector(direction).normalized(); right = Vector((0., 0., 1.)).cross(back).normalized(); up = back.cross(right)
            basis = Matrix((right, up, back)).transposed().to_4x4(); basis.translation = center + back * .75; camera.matrix_world = basis
            for light, offset in zip(lights, [back * .45 + up * .25 - right * .16, back * .35 - up * .1 + right * .25]):
                light.location = center + offset; light.rotation_euler = (center - light.location).to_track_quat('-Z', 'Y').to_euler()
            image = out / f'{side}-{label}.png'; scene.render.filepath = str(image); bpy.ops.render.render(write_still=True)
            records.append({'side': side, 'view': label, 'image': str(image), 'sha256': sha(image),
                'cameraToHandLocal': [list(row) for row in basis], 'forearmToHandBind': [list(row) for row in fore_matrix],
                'handImportedCustomNormals': [o.data.has_custom_normals for o in hands]})
    for path, value in hashes.items():
        if sha(path) != value:
            raise RuntimeError('Read-only source changed')
    result = {'schemaVersion': 1, 'readOnly': True, 'inputs': hashes, 'records': records,
        'sourceGeometryOrMapsChanged': False, 'rigChanged': False, 'clientAccepted': False,
        'limits': 'Actual generated GLB maps and selected forearm raw GLB materials, EEVEE neutral lights/AO. Root native palette calibration and embedded-AO/roughness repair are not simulated; skin colour mismatch here is not final native evidence. No model export. Stock bind wrist assembly only; CPU weapon and dense controller checks complement this view.'}
    (out / 'review.json').write_text(json.dumps(result, indent=2) + '\n')
    (out / 'executed-blender.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'output': str(out), 'views': len(records)}), flush=True)


if __name__ == '__main__':
    main()
