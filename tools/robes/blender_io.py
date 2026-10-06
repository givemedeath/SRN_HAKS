"""Blender-side import and base-colour sampling shared by the robe drivers (inspection, repair, fit, weights)."""
import bpy
import numpy as np

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


def base_color_image(obj):
    """The first image linked to a Principled BSDF base colour on the object, or None."""
    for slot in obj.material_slots:
        material = slot.material
        if material and material.use_nodes:
            for node in material.node_tree.nodes:
                if node.type == "BSDF_PRINCIPLED" and node.inputs["Base Color"].is_linked:
                    image = getattr(node.inputs["Base Color"].links[0].from_node, "image", None)
                    if image is not None:
                        return image
    return None


def face_colours(obj, loops, image):
    """Base-colour RGB (0-1, as stored) at each triangle's UV centroid; loops are (faces, 3) loop indices."""
    width, height = image.size
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    pixels = pixels.reshape(height, width, 4)[:, :, :3]
    uv = np.empty(len(obj.data.loops) * 2)
    obj.data.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)[loops].mean(axis=1)
    x = np.clip((uv[:, 0] % 1.0) * (width - 1), 0, width - 1).astype(int)
    y = np.clip((uv[:, 1] % 1.0) * (height - 1), 0, height - 1).astype(int)
    return pixels[y, x]
