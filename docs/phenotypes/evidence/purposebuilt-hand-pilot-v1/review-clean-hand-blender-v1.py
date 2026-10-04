"""Bounded EEVEE anatomy-only review; request root GPU slot before execution.

Run in Blender background with --source/--output after `--`. No model or map
export. Actual camera orbit preserves projected X in both polar views.
"""
import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

P = Path(__file__).resolve().parent


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(4 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


args = argparse.ArgumentParser()
args.add_argument('--source', type=Path, required=True)
args.add_argument('--output', type=Path, required=True)
args.add_argument('--size', type=int, default=900)
args.add_argument('--views', nargs='+', choices=['palm', 'opposite-side', 'dorsal', 'thumb-side',
    'wrist-top', 'distal-bottom', 'palm-distal-oblique', 'dorsal-wrist-oblique'])
a = args.parse_args(sys.argv[sys.argv.index('--') + 1:])
source = a.source.resolve(); out = a.output.resolve()
if out.parent != P.resolve() or out.exists():
    raise RuntimeError('Fresh owned output directory required')
before = sha(source)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(source))
mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
if not mesh_objects:
    raise RuntimeError('Actual source mesh not imported')
points = [obj.matrix_world @ Vector(corner) for obj in mesh_objects for corner in obj.bound_box]
lo = Vector(tuple(min(point[i] for point in points) for i in range(3)))
hi = Vector(tuple(max(point[i] for point in points) for i in range(3)))
center = (lo + hi) / 2
span = max(hi - lo) * 1.18
material = bpy.data.materials.new('diagnostic-neutral-clay')
material.use_nodes = True
principled = material.node_tree.nodes.get('Principled BSDF')
principled.inputs['Base Color'].default_value = (.45, .42, .39, 1)
principled.inputs['Roughness'].default_value = .7
for obj in mesh_objects:
    obj.data.materials.clear(); obj.data.materials.append(material)
# Preserve glTF-imported authored normals; no global shade-smooth operation.
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = scene.render.resolution_y = a.size
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.eevee.use_gtao = True
scene.eevee.gtao_distance = span * .12
scene.eevee.gtao_factor = 1.0
scene.eevee.taa_render_samples = 32
world = bpy.data.worlds.new('diagnostic-world'); world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (.085, .085, .085, 1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value = .7
scene.world = world
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'Medium High Contrast'
scene.view_settings.exposure = 0
scene.view_settings.gamma = 1
camera_data = bpy.data.cameras.new('orthographic-camera')
camera_data.type = 'ORTHO'; camera_data.ortho_scale = span
camera = bpy.data.objects.new('orthographic-camera', camera_data)
scene.collection.objects.link(camera); scene.camera = camera
lights = []
for name, energy, size in [('key', 85, span * 1.2), ('fill', 30, span * 1.8)]:
    data = bpy.data.lights.new(name, 'AREA'); data.energy = energy; data.shape = 'DISK'; data.size = size
    obj = bpy.data.objects.new(name, data); scene.collection.objects.link(obj); lights.append(obj)
out.mkdir()
shutil.copy2(__file__, out / 'executed-blender.py')
records = []
for name, azimuth, elevation in [('palm', 0, 0), ('opposite-side', 90, 0),
    ('dorsal', 180, 0), ('thumb-side', 270, 0), ('wrist-top', 0, 90), ('distal-bottom', 0, -90),
    ('palm-distal-oblique', 25, -25), ('dorsal-wrist-oblique', 200, 25)]:
    if a.views and name not in a.views:
        continue
    az, el = map(math.radians, [azimuth, elevation])
    back = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    right = Vector((math.cos(az), math.sin(az), 0))
    up = back.cross(right)
    basis = Matrix((right, up, back)).transposed().to_4x4()
    basis.translation = center + back * span * 3
    camera.matrix_world = basis
    for obj, offset in zip(lights, [back * 2.5 + up * 1.8 - right, back * 1.7 - up + right * 2]):
        obj.location = center + offset * span
        obj.rotation_euler = (center - obj.location).to_track_quat('-Z', 'Y').to_euler()
    path = out / (name + '-clay.png')
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    records.append({'image': str(path), 'sha256': sha(path), 'azimuth': azimuth, 'elevation': elevation,
        'cameraToWorld': [list(row) for row in basis], 'right': list(right), 'up': list(up), 'back': list(back)})
if sha(source) != before:
    raise RuntimeError('Read-only source changed')
(out / 'review.json').write_text(json.dumps({'schemaVersion': 1, 'readOnly': True,
    'source': str(source), 'sourceSha256': before, 'sourceChanged': False,
    'helperSha256': sha(__file__), 'fitOrGeometryEditPerformed': False,
    'meshObjects': [{'name': obj.name, 'vertices': len(obj.data.vertices), 'polygons': len(obj.data.polygons),
        'hasImportedCustomNormals': obj.data.has_custom_normals} for obj in mesh_objects],
    'boundsNwn': [list(lo), list(hi)], 'sharedOrthographicSpan': span,
    'actualCameraConvention': 'right=[cos(az),sin(az),0], up=cross(back,right); both top/bottom project source X right',
    'records': records, 'geometrySelected': False, 'clientAccepted': False,
    'limitations': 'Neutral preview-only clay, renderer AO and lights; source materials/normal atlas and client palette/lighting are not simulated. glTF imported authored normals are preserved; no model or map export.'}, indent=2) + '\n')
print(json.dumps({'output': str(out), 'views': len(records), 'sourceUnchanged': True}))
