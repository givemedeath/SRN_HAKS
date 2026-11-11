"""Review renders of a generated model. Run inside Blender:

    blender -b -t 4 --python tools/envkit/preview_blender.py -- MODEL.glb OUT_DIR

Writes four views (front-left, front-right, rear-left, top) with flat lighting and `stats.json` with the triangle count,
the size in the file's own units and each texture's resolution."""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

VIEWS = {'front-left': (-35, 62), 'front-right': (35, 62), 'rear-left': (-145, 62), 'top': (-20, 18)}  # azimuth, polar


def main(model, output):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(model))
    meshes = [item for item in bpy.context.scene.objects if item.type == 'MESH']
    corners = [item.matrix_world @ Vector(corner) for item in meshes for corner in item.bound_box]
    low = Vector(min(c[i] for c in corners) for i in range(3)); high = Vector(max(c[i] for c in corners) for i in range(3))
    centre, size = (low + high) / 2, high - low
    triangles = sum(sum(len(polygon.vertices) - 2 for polygon in item.data.polygons) for item in meshes)
    textures = {image.name: list(image.size) for image in bpy.data.images if image.size[0]}
    (output / 'stats.json').write_text(json.dumps({'model': str(model), 'triangles': triangles, 'objects': len(meshes),
                                                   'size': [round(v, 4) for v in size], 'materials': len(bpy.data.materials),
                                                   'textures': textures}, indent=1), encoding='utf-8')
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'; scene.render.resolution_x, scene.render.resolution_y = 960, 720
    scene.render.film_transparent = False; scene.view_settings.view_transform = 'Standard'
    world = bpy.data.worlds.new('review'); world.use_nodes = True; scene.world = world
    world.node_tree.nodes['Background'].inputs[0].default_value = (0.82, 0.82, 0.82, 1); world.node_tree.nodes['Background'].inputs[1].default_value = 1.0
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sun.data.energy = 2.0
    sun.rotation_euler = (math.radians(50), 0, math.radians(-30)); scene.collection.objects.link(sun)
    camera = bpy.data.objects.new('camera', bpy.data.cameras.new('camera')); scene.collection.objects.link(camera); scene.camera = camera
    camera.data.lens = 50; distance = max(size) * 2.4
    for name, (azimuth, polar) in VIEWS.items():
        a, p = math.radians(azimuth), math.radians(polar)
        # glTF's front (+Z) arrives in Blender as -Y, so azimuth 0 looks at the front.
        camera.location = centre + Vector((distance * math.sin(p) * math.sin(a), -distance * math.sin(p) * math.cos(a), distance * math.cos(p)))
        camera.rotation_euler = (centre - camera.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = str(output / f'{name}.png'); bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    main(*sys.argv[sys.argv.index('--') + 1:])
