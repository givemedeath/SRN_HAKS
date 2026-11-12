"""Eight orthographic review views of one GLB, and their contact sheet.

    blender -b -P tools/itemkit/preview_views.py -- MODEL.glb OUTPUT_DIR [clay|textured]

Clay views use a grey cavity-shaded workbench; textured views show the model's own colour unlit. Rendering stays at
four threads. `sheet(OUTPUT_DIR)` (plain Python) tiles the eight views with their names into sheet.png.
"""
import sys
from pathlib import Path

VIEWS = {'front': (0, -1, 0), 'back': (0, 1, 0), 'left': (-1, 0, 0), 'right': (1, 0, 0), 'top': (0, 0, 1), 'bottom': (0, 0, -1),
         'oblique-a': (-1, -1, .7), 'oblique-b': (1, 1, .7)}


def render(glb, out, mode='clay'):
    import bpy
    from mathutils import Vector
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()
    bpy.ops.import_scene.gltf(filepath=str(glb))
    objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    points = [o.matrix_world @ Vector(c) for o in objects for c in o.bound_box]
    lo = Vector([min(p[i] for p in points) for i in range(3)]); hi = Vector([max(p[i] for p in points) for i in range(3)])
    centre = (lo + hi) / 2; extent = max(hi - lo)
    print('bounds', tuple(round(x, 3) for x in (hi - lo)), 'tris', sum(len(o.data.polygons) for o in objects))
    scene = bpy.context.scene; scene.render.engine = 'BLENDER_WORKBENCH'; shading = scene.display.shading
    if mode == 'clay':
        shading.light = 'STUDIO'; shading.color_type = 'SINGLE'; shading.single_color = (.62, .62, .62)
        shading.show_cavity = True; shading.cavity_type = 'BOTH'
    else:
        shading.light = 'FLAT'; shading.color_type = 'TEXTURE'; shading.show_cavity = False
    scene.render.resolution_x = scene.render.resolution_y = 900; scene.render.threads_mode = 'FIXED'; scene.render.threads = 4
    scene.render.image_settings.file_format = 'PNG'; scene.view_settings.view_transform = 'Standard'
    scene.world = bpy.data.worlds.new('w'); scene.world.color = (.1, .1, .1)
    camera = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); scene.collection.objects.link(camera); scene.camera = camera
    camera.data.type = 'ORTHO'; camera.data.ortho_scale = (hi - lo).length * 1.05     # a diagonal model fits every view
    for name, direction in VIEWS.items():
        v = Vector(direction).normalized(); camera.location = centre + v * extent * 3
        camera.rotation_euler = (centre - camera.location).to_track_quat('-Z', 'Y' if abs(v.z) < .9 else 'X').to_euler()
        scene.render.filepath = str(out/f'{name}.png'); bpy.ops.render.render(write_still=True)


def sheet(folder, size=480):
    from PIL import Image, ImageDraw
    folder = Path(folder); canvas = Image.new('RGB', (size * 4, size * 2), (20, 20, 20))
    for index, name in enumerate(VIEWS):
        image = Image.open(folder/f'{name}.png').convert('RGB').resize((size, size), Image.LANCZOS)
        ImageDraw.Draw(image).text((8, 8), name, fill=(255, 220, 120)); canvas.paste(image, ((index % 4) * size, (index // 4) * size))
    canvas.save(folder/'sheet.png'); return folder/'sheet.png'


if __name__ == '__main__' and '--' in sys.argv:
    arguments = sys.argv[sys.argv.index('--') + 1:]
    render(arguments[0], arguments[1], arguments[2] if len(arguments) > 2 else 'clay')
