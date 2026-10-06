"""Blender-side import helper shared by the robe drivers (inspection, repair, fit, weights)."""
import bpy

from robe_common import require


def import_single(path):
    """Import a GLB holding exactly one mesh, with its object transform baked into the vertices."""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    meshes = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    require(len(meshes) == 1, "Expected one mesh object in " + str(path))
    obj = meshes[0]
    obj.data.transform(obj.matrix_world)
    obj.matrix_world.identity()
    return obj
