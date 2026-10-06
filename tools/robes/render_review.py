"""Render matched orthographic review views of outfit and body geometry (Blender).

A scene spec lists meshes (GLB, posed .npz with verts/faces, or the stock body)
with flat review colours, or several `scenes` of such meshes rendered in one launch.
Every render in a review uses the same cameras, light rig and four-thread engine
settings. Images are review aids, never client evidence.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "phenotypes"))
from pose_preview_render_settings import apply_render_settings
from robe_common import FLAGS, fresh_directory, pin, read, require, utc, write_fresh

VIEWS = {"front": (0.0, 1.0, 0.0), "back": (0.0, -1.0, 0.0), "left": (-1.0, 0.0, 0.0), "right": (1.0, 0.0, 0.0),
         "threequarter": (0.62, 0.78, 0.0), "top": (0.0, 0.05, 1.0)}


def clear():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color[:3], 1.0)
    bsdf.inputs["Roughness"].default_value = 0.7
    if len(color) > 3 and color[3] < 1:
        bsdf.inputs["Alpha"].default_value = color[3]
        mat.blend_method = "BLEND"
    return mat


def from_arrays(name, verts, faces):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(map(float, v)) for v in verts], [], [tuple(map(int, f)) for f in faces])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def load(spec, entry):
    if "glb" in entry:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=entry["glb"])
        objects = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    elif "npz" in entry:
        data = np.load(entry["npz"])
        objects = [from_arrays(entry["name"], data["verts"], data["faces"])]
    else:
        from stock_body import Body
        body = Body(entry["stockBody"]["ascii"], entry["stockBody"].get("prefix", "pmh0"),
                    parts=[p for p in entry["stockBody"].get("parts", [])] or None)
        verts, faces, _ = body.posed()
        objects = [from_arrays(entry["name"], verts, faces)]
    mat = material(entry["name"], entry["color"]) if entry.get("color") else None
    for obj in objects:
        obj.data.transform(obj.matrix_world)
        obj.matrix_world.identity()
        if mat:
            obj.data.materials.clear()
            obj.data.materials.append(mat)
        for polygon in obj.data.polygons:
            polygon.use_smooth = entry.get("smooth", True)
    return objects


def lights():
    for name, direction, energy in (("key", (0.6, 1.0, 1.2), 3.0), ("fill", (-1.0, 0.6, 0.4), 1.2),
                                    ("rim", (0.0, -1.0, 0.8), 1.5)):
        data = bpy.data.lights.new(name, "SUN")
        data.energy = energy
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.rotation_euler = Vector(direction).to_track_quat("Z", "Y").to_euler()
    world = bpy.data.worlds.new("review") if not bpy.context.scene.world else bpy.context.scene.world
    bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.92, 0.92, 0.92, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    spec = read(args.spec)
    output = fresh_directory(args.output)
    clear()
    scene = bpy.context.scene
    settings = apply_render_settings(scene, spec.get("engine", "eevee"))
    scene.render.resolution_x, scene.render.resolution_y = spec.get("resolution", [720, 960])
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scenes = spec.get("scenes") or [{"prefix": spec.get("prefix", "review"), "meshes": spec["meshes"]}]
    require(len({s["prefix"] for s in scenes}) == len(scenes), "Scene prefixes must be unique")
    lights()
    centre = Vector(spec.get("centre", [0.0, 0.0, 0.97]))
    camera_data = bpy.data.cameras.new("review")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = spec.get("cameraScale", 2.2)
    camera = bpy.data.objects.new("review", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    renders, inputs = [], []
    # One launch renders every scene with the same cameras and lights; only meshes are swapped.
    for entry_set in scenes:
        for obj in [o for o in bpy.data.objects if o.type == "MESH"]:
            bpy.data.objects.remove(obj, do_unlink=True)
        for collection in (bpy.data.meshes, bpy.data.materials):
            for item in [i for i in collection if i.users == 0]:
                collection.remove(item)
        for entry in entry_set["meshes"]:
            load(spec, entry)
            inputs += [pin(entry[k]) for k in ("glb", "npz") if k in entry]
        for view in spec.get("views", ["front", "left", "back", "threequarter"]):
            direction = Vector(VIEWS[view]).normalized()
            camera.location = centre + direction * 6.0
            camera.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
            path = output / f"{entry_set['prefix']}-{view}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            require(path.is_file(), "Render missing: " + str(path))
            renders.append({"scene": entry_set["prefix"], "view": view, "image": pin(path),
                            "cameraLocation": list(camera.location), "cameraRotation": list(camera.rotation_euler)})
    report = {"schemaVersion": 1, "kind": "srn-robe-review-render", "createdUtc": utc(), "spec": pin(args.spec),
              "inputs": inputs, "scenes": len(scenes),
              "renderSettings": settings, "cameraScale": camera_data.ortho_scale, "centre": list(centre),
              "renders": renders, "clientEvidence": False, **FLAGS}
    print(json.dumps(write_fresh(output / "render.json", report)))


if __name__ == "__main__":
    main()
