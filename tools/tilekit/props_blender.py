"""Offline renders of the tilekit kit pieces. Run inside Blender:

    blender -b -t 4 --python props_blender.py -- FOLDER

FOLDER holds pieces.json, atlas.png and glow.png (sketch.export). Each piece is shown on a grey wall (a wall piece,
+y out of the wall) or a grey roof (a roof piece), from the front three-quarters and the side by day, and from the
front at night when it has a glowing part. Writes <piece>-<view>.png."""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

GLOWING = {'camera', 'mast', 'cross_sign', 'barrel'}


def material(folder):
    mat = bpy.data.materials.new('kit'); mat.use_nodes = True; nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes['Principled BSDF']
    colour = nodes.new('ShaderNodeTexImage'); colour.image = bpy.data.images.load(str(folder / 'atlas.png'))
    glow = nodes.new('ShaderNodeTexImage'); glow.image = bpy.data.images.load(str(folder / 'glow.png'))
    metal = nodes.new('ShaderNodeTexImage'); metal.image = bpy.data.images.load(str(folder / 'metal.png')); metal.image.colorspace_settings.name = 'Non-Color'
    rough = nodes.new('ShaderNodeTexImage'); rough.image = bpy.data.images.load(str(folder / 'rough.png')); rough.image.colorspace_settings.name = 'Non-Color'
    for image in (colour, glow, metal, rough):
        image.interpolation = 'Closest'
    links.new(colour.outputs['Color'], bsdf.inputs['Base Color']); links.new(metal.outputs['Color'], bsdf.inputs['Metallic'])
    links.new(rough.outputs['Color'], bsdf.inputs['Roughness'])
    links.new(glow.outputs['Color'], bsdf.inputs['Emission Color']); bsdf.inputs['Emission Strength'].default_value = 4.0
    return mat


def eevee(scene):
    for name in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):  # named so to 4.1 and from 5.0, and from 4.2 to 4.5
        try:
            scene.render.engine = name; break
        except TypeError:
            continue
    if hasattr(scene.eevee, 'use_bloom'):  # to 4.1
        scene.eevee.use_bloom = True


def backing(roof):
    mat = bpy.data.materials.new('wall'); mat.use_nodes = True; mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.32, 0.32, 0.31, 1)
    mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9
    mesh = bpy.data.meshes.new('back')
    if roof:
        mesh.from_pydata([(-20, -20, 0), (20, -20, 0), (20, 20, 0), (-20, 20, 0)], [], [(0, 1, 2, 3)])
    else:
        mesh.from_pydata([(-20, -0.002, -20), (20, -0.002, -20), (20, -0.002, 20), (-20, -0.002, 20)], [], [(0, 3, 2, 1)])
    item = bpy.data.objects.new('back', mesh); item.data.materials.append(mat); bpy.context.scene.collection.objects.link(item)


def piece(name, data, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in data['verts']], [], [tuple(f[:3]) for f in data['faces']])
    for polygon in mesh.polygons:
        polygon.use_smooth = True  # shared corners round the light; a face with corners of its own stays flat
    layer = mesh.uv_layers.new()
    for polygon, face in zip(mesh.polygons, data['faces']):
        for loop, corner in zip(polygon.loop_indices, face[3:6]):
            layer.data[loop].uv = data['uvs'][corner]
    item = bpy.data.objects.new(name, mesh); item.data.materials.append(mat); bpy.context.scene.collection.objects.link(item)
    return item


def main(folder):
    folder = Path(folder); pieces = json.loads((folder / 'pieces.json').read_text(encoding='utf-8'))
    for name, data in pieces.items():
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene; eevee(scene); scene.render.resolution_x, scene.render.resolution_y = 800, 600
        scene.view_settings.view_transform = 'Standard'
        world = bpy.data.worlds.new('w'); world.use_nodes = True; scene.world = world; background = world.node_tree.nodes['Background']
        sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); scene.collection.objects.link(sun)
        sun.rotation_euler = (math.radians(55), 0, math.radians(35))
        mat = material(folder); roof = data['roof']; backing(roof); piece(name, data, mat)
        verts = [Vector(v) for v in data['verts']]
        low = Vector(min(v[i] for v in verts) for i in range(3)); high = Vector(max(v[i] for v in verts) for i in range(3))
        centre, size = (low + high) / 2, max((high - low).length, 0.3)
        camera = bpy.data.objects.new('camera', bpy.data.cameras.new('camera')); scene.collection.objects.link(camera); scene.camera = camera
        camera.data.lens = 50; distance = size * 2.1
        views = {'front': (30, 12, 'day'), 'side': (78, 8, 'day')} if not roof else {'front': (30, 25, 'day'), 'side': (120, 35, 'day')}
        if name in GLOWING:
            views['night'] = (views['front'][0], views['front'][1], 'night')
        for view, (azimuth, elevation, light) in views.items():
            a, e = math.radians(azimuth), math.radians(elevation)
            # a wall piece is seen from the street, +y; a roof piece from above, around
            offset = Vector((distance * math.cos(e) * math.sin(a), distance * math.cos(e) * math.cos(a), distance * math.sin(e)))
            camera.location = centre + offset; camera.rotation_euler = (centre - camera.location).to_track_quat('-Z', 'Y').to_euler()
            sun.data.energy = 3.0 if light == 'day' else 0.02
            background.inputs[0].default_value = (0.55, 0.6, 0.68, 1) if light == 'day' else (0.01, 0.012, 0.02, 1)
            background.inputs[1].default_value = 1.0 if light == 'day' else 0.3
            scene.render.filepath = str(folder / f'{name}-{view}.png'); bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    main(*sys.argv[sys.argv.index('--') + 1:])
