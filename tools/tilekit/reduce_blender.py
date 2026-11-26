"""Meshes brought down to a number of triangles, their pictures kept in place. Run inside Blender:

    blender -b -t 4 --python reduce_blender.py -- IN.json OUT.json

IN: [{verts, uvs (one for each corner of each face), faces: [[a, b, c]], most}]; OUT the same without `most`."""
import json
import sys

import bmesh
import bpy


def reduced(part):
    mesh = bpy.data.meshes.new('part'); mesh.from_pydata(part['verts'], [], part['faces']); layer = mesh.uv_layers.new(name='uv')
    for loop, uv in zip(layer.data, part['uvs']):
        loop.uv = uv
    work = bmesh.new(); work.from_mesh(mesh); bmesh.ops.remove_doubles(work, verts=work.verts, dist=1e-5); work.to_mesh(mesh); work.free()
    body = bpy.data.objects.new('part', mesh); bpy.context.collection.objects.link(body)
    change = body.modifiers.new('less', 'DECIMATE'); change.ratio = min(1.0, part['most'] / max(1, len(mesh.polygons))); change.use_collapse_triangulate = True
    made = bpy.data.meshes.new_from_object(body.evaluated_get(bpy.context.evaluated_depsgraph_get())); uv = made.uv_layers[0].data
    return {'verts': [list(vertex.co) for vertex in made.vertices], 'faces': [list(face.vertices) for face in made.polygons], 'uvs': [list(uv[loop].uv) for face in made.polygons for loop in face.loop_indices]}


source, target = sys.argv[sys.argv.index('--') + 1:]
with open(source, encoding='utf-8') as file:
    parts = json.load(file)
with open(target, 'w', encoding='utf-8') as file:
    json.dump([reduced(part) for part in parts], file)
