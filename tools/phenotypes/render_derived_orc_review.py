"""Blender 4.0 rendering script for Derived Orc Male Visual Review.

Renders matched side-by-side views of:
1. Human Male Master (heroic reference)
2. Derived Orc Male Fit (broad muscular high-poly derived phenotype on retargeted pmo0 rig)

Produces Clay studio renders, Unlit color/silhouette renders, and dynamic posed views.
Strictly limited to 4 CPU threads.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import struct
import sys
import time

import bpy
from mathutils import Matrix, Vector, Euler
import numpy as np

# Ensure tools directory is in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from retarget import nodes, transforms
from target_contract import PART_JOINTS


def parse_args():
    argv = sys.argv
    if "--" in argv:
        args = argv[argv.index("--") + 1:]
    else:
        args = []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--masters-dir", type=Path, default=Path("output/phenotypes/derived-v1/masters/human-male-v1"))
    parser.add_argument("--derived-dir", type=Path, default=Path("output/phenotypes/derived-v1/parts/orc-male/ascii"))
    parser.add_argument("--rig-file", type=Path, default=Path("output/phenotypes/derived-v1/rigs/orc-male/pmo0.mdl"))
    parser.add_argument("--output-dir", type=Path, default=Path("output/phenotypes/derived-orc-male-v1/review/renders"))
    parser.add_argument("--threads", type=int, default=4)
    return parser.parse_args(args)


def decode_binary_mdl(path: Path | str, node_pattern: bytes) -> dict:
    data = Path(path).read_bytes()
    zero, raw_offset, raw_size = struct.unpack_from("<III", data, 0)
    raw_start = 12 + raw_offset
    idx = data.find(node_pattern)
    if idx < 32:
        raise ValueError(f"Node pattern {node_pattern!r} not found in {path}")
    node = idx - 32
    face_offset, count, capacity = struct.unpack_from("<III", data, node + 0x78)
    vertices, texture_count = struct.unpack_from("<HH", data, node + 0x230)
    offsets = {
        key: struct.unpack_from("<I", data, node + field)[0]
        for key, field in [
            ("position", 0x22c),
            ("uv", 0x234),
            ("normal", 0x244),
        ]
    }
    def floats(key: str, width: int) -> np.ndarray | None:
        off = offsets[key]
        if off == 0xFFFFFFFF or raw_start + off + vertices * width * 4 > len(data):
            return None
        return np.frombuffer(data, "<f4", vertices * width, raw_start + off).reshape(-1, width)

    pos = floats("position", 3)
    norm = floats("normal", 3)
    faces = np.ndarray((count, 3), dtype="<u2", buffer=data, offset=12 + face_offset + 26, strides=(32, 2))
    return {"position": pos, "normal": norm, "faces": faces}


def decode_ascii_mdl(path: Path | str) -> dict:
    text = Path(path).read_text(encoding="cp1252")
    lines = text.splitlines()
    all_verts = []
    all_faces = []
    curr_verts = []
    curr_faces = []
    mode = None
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("node trimesh ") or s.startswith("node dummy ") or s.startswith("endnode"):
            if curr_verts:
                offset = len(all_verts)
                all_verts.extend(curr_verts)
                for f in curr_faces:
                    all_faces.append([f[0] + offset, f[1] + offset, f[2] + offset])
                curr_verts = []
                curr_faces = []
            mode = None
            continue
        if s.startswith("verts "):
            mode = "verts"
            continue
        if s.startswith("faces "):
            mode = "faces"
            continue
        if s.startswith("normals ") or s.startswith("tverts ") or s.startswith("tangents "):
            mode = "other"
            continue
        if mode == "verts":
            parts = [float(v) for v in s.split()]
            if len(parts) >= 3:
                curr_verts.append(parts[:3])
        elif mode == "faces":
            parts = [int(v) for v in s.split()]
            if len(parts) >= 3:
                curr_faces.append(parts[:3])

    if curr_verts:
        offset = len(all_verts)
        all_verts.extend(curr_verts)
        for f in curr_faces:
            all_faces.append([f[0] + offset, f[1] + offset, f[2] + offset])

    return {"position": np.array(all_verts, dtype=float), "faces": np.array(all_faces, dtype=int)}


def build_character_mesh(
    name: str,
    parts_data: dict[str, dict],
    joint_transforms: dict[str, np.ndarray],
    material: bpy.types.Material,
) -> bpy.types.Object:
    all_verts = []
    all_faces = []

    for part, joint in PART_JOINTS.items():
        if part not in parts_data:
            continue
        data = parts_data[part]
        v_local = data["position"]
        f_local = data["faces"]

        if len(v_local) == 0:
            continue

        m = joint_transforms.get(joint.lower())
        if m is None:
            continue

        v_world = v_local @ m[:3, :3].T + m[:3, 3]

        offset = len(all_verts)
        all_verts.extend(v_world.tolist())
        for face in f_local:
            all_faces.append([int(i) + offset for i in face])

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(all_verts, [], all_faces)
    mesh.update()

    for poly in mesh.polygons:
        poly.use_smooth = True

    obj = bpy.data.objects.new(name, mesh)
    if material:
        obj.data.materials.append(material)

    bpy.context.collection.objects.link(obj)
    return obj


def create_clay_material(name: str, base_color: tuple[float, float, float]) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.52
    bsdf.inputs["Specular IOR Level"].default_value = 0.35

    mat.node_tree.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return mat


def create_unlit_material(name: str, color: tuple[float, float, float]) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    emission = nodes.new(type="ShaderNodeEmission")
    emission.inputs["Color"].default_value = (*color, 1.0)
    emission.inputs["Strength"].default_value = 1.0

    mat.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return mat


def setup_lighting():
    # Key light
    key_data = bpy.data.lights.new(name="KeyLight", type="AREA")
    key_data.energy = 380.0
    key_data.size = 2.5
    key_data.color = (1.0, 0.98, 0.95)
    key_obj = bpy.data.objects.new(name="KeyLight", object_data=key_data)
    key_obj.location = (3.5, 4.5, 4.0)
    bpy.context.collection.objects.link(key_obj)

    # Fill light
    fill_data = bpy.data.lights.new(name="FillLight", type="AREA")
    fill_data.energy = 140.0
    fill_data.size = 4.0
    fill_data.color = (0.85, 0.92, 1.0)
    fill_obj = bpy.data.objects.new(name="FillLight", object_data=fill_data)
    fill_obj.location = (-4.0, 3.5, 2.5)
    bpy.context.collection.objects.link(fill_obj)

    # Rim light
    rim_data = bpy.data.lights.new(name="RimLight", type="AREA")
    rim_data.energy = 420.0
    rim_data.size = 3.0
    rim_data.color = (1.0, 1.0, 1.0)
    rim_obj = bpy.data.objects.new(name="RimLight", object_data=rim_data)
    rim_obj.location = (0.0, -4.5, 3.5)
    bpy.context.collection.objects.link(rim_obj)


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Blender scene settings
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.render.threads_mode = "FIXED"
    scene.render.threads = args.threads
    scene.cycles.samples = 64
    scene.render.resolution_x = 2400
    scene.render.resolution_y = 1600

    # Clean initial scene (removes default startup Cube, Camera, Light)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    # Set background color
    scene.world = bpy.data.worlds.new("World")
    scene.world.use_nodes = True
    bg_node = scene.world.node_tree.nodes.get("Background")
    if bg_node:
        bg_node.inputs["Color"].default_value = (0.05, 0.05, 0.07, 1.0)
        bg_node.inputs["Strength"].default_value = 0.65

    # Setup studio lights
    setup_lighting()

    # Materials
    clay_human = create_clay_material("Clay_Human", (0.72, 0.70, 0.68))
    clay_derived_orc = create_clay_material("Clay_DerivedOrc", (0.70, 0.72, 0.68))

    unlit_human = create_unlit_material("Unlit_Human", (0.20, 0.20, 0.20))
    unlit_derived_orc = create_unlit_material("Unlit_DerivedOrc", (0.25, 0.40, 0.20))  # Deep olive green for Orc

    # Rig transforms
    pmh0_text = (args.masters_dir / "stock" / "pmh0.mdl").read_text(encoding="cp1252")
    pmo0_text = args.rig_file.read_text(encoding="cp1252")

    hm_rig = transforms(nodes(pmh0_text))
    orc_rig = transforms(nodes(pmo0_text))

    # Load parts
    master_parts = {}
    derived_orc_parts = {}

    for part in PART_JOINTS:
        if part in ("head", "neck"):
            hm_p = args.masters_dir / "stock" / f"pmh0_{part}001.mdl"
            master_parts[part] = decode_binary_mdl(hm_p, f"pmh0_{part}001g".encode())
            derived_orc_parts[part] = master_parts[part]
        else:
            hm_p = args.masters_dir / "ascii" / f"pmh0_{part}001.mdl"
            master_parts[part] = decode_ascii_mdl(hm_p)

            der_p = args.derived_dir / f"pmo0_{part}001.mdl"
            derived_orc_parts[part] = decode_ascii_mdl(der_p)

    # 1. Build Clay Specimens
    obj_hm_clay = build_character_mesh("HumanMaster_Clay", master_parts, hm_rig, clay_human)
    obj_de_clay = build_character_mesh("DerivedOrc_Clay", derived_orc_parts, orc_rig, clay_derived_orc)

    # Positions: Human Master at +X=+1.0 (camera left), Derived Orc at -X=-1.0 (camera right)
    loc_hm = Vector((1.0, 0.0, 0.0))
    loc_de = Vector((-1.0, 0.0, 0.0))

    obj_hm_clay.location = loc_hm
    obj_de_clay.location = loc_de

    # Camera setup
    cam_data = bpy.data.cameras.new("OrthoCam")
    cam_data.type = "ORTHO"
    cam_obj = bpy.data.objects.new("OrthoCam", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    target = Vector((0.0, 0.0, 1.10))

    views = [
        ("front", Vector((0.0, 9.0, 1.10)), 4.8, False),
        ("side", Vector((9.0, 0.0, 1.10)), 4.8, True),
        ("oblique", Vector((6.5, 6.5, 2.5)), 4.8, False),
        ("rear", Vector((0.0, -9.0, 1.10)), 4.8, False),
    ]

    rendered_files = {}

    # Render Clay Pass
    print("--- Rendering Clay Comparison Views ---")
    for view_name, cam_pos, ortho_scale, is_side in views:
        t0 = time.time()
        if is_side:
            obj_hm_clay.location = Vector((0.0, -1.0, 0.0))
            obj_de_clay.location = Vector((0.0, 1.0, 0.0))
        else:
            obj_hm_clay.location = loc_hm
            obj_de_clay.location = loc_de

        bpy.context.view_layer.update()
        cam_data.ortho_scale = ortho_scale
        cam_obj.location = cam_pos
        direction = target - cam_pos
        cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

        out_path = args.output_dir / f"orc_clay_{view_name}.png"
        scene.render.filepath = str(out_path.resolve())
        bpy.ops.render.render(write_still=True)
        rendered_files[f"clay_{view_name}"] = str(out_path)
        print(f"Rendered clay_{view_name} in {time.time()-t0:.2f}s -> {out_path.name}")

    # 2. Build Unlit Specimens
    print("--- Rendering Unlit Comparison Views ---")
    bpy.data.objects.remove(obj_hm_clay, do_unlink=True)
    bpy.data.objects.remove(obj_de_clay, do_unlink=True)

    obj_hm_unlit = build_character_mesh("HumanMaster_Unlit", master_parts, hm_rig, unlit_human)
    obj_de_unlit = build_character_mesh("DerivedOrc_Unlit", derived_orc_parts, orc_rig, unlit_derived_orc)

    for view_name, cam_pos, ortho_scale, is_side in views:
        t0 = time.time()
        if is_side:
            obj_hm_unlit.location = Vector((0.0, -1.0, 0.0))
            obj_de_unlit.location = Vector((0.0, 1.0, 0.0))
        else:
            obj_hm_unlit.location = loc_hm
            obj_de_unlit.location = loc_de

        bpy.context.view_layer.update()
        cam_data.ortho_scale = ortho_scale
        cam_obj.location = cam_pos
        direction = target - cam_pos
        cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

        out_path = args.output_dir / f"orc_unlit_{view_name}.png"
        scene.render.filepath = str(out_path.resolve())
        bpy.ops.render.render(write_still=True)
        rendered_files[f"unlit_{view_name}"] = str(out_path)
        print(f"Rendered unlit_{view_name} in {time.time()-t0:.2f}s -> {out_path.name}")

    report_path = args.output_dir / "rendered-files.json"
    report_path.write_text(json.dumps(rendered_files, indent=2) + "\n", encoding="utf-8")
    print(f"All renders complete. Summary written to {report_path}")


if __name__ == "__main__":
    main()
