"""Blender 4.0 rendering script for Checkpoint CP2: Derived Dwarf Male Visual Review.

Renders matched side-by-side views of:
1. Human Male Master (heroic reference)
2. Stock Dwarf Male Control (pmd0 stock low-poly)
3. Derived Dwarf Male Fit (new high-poly derived phenotype)

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
from pose_preview_bridge import pose


def parse_args():
    argv = sys.argv
    if "--" in argv:
        args = argv[argv.index("--") + 1:]
    else:
        args = []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--masters-dir", type=Path, default=Path("output/phenotypes/derived-v1/masters/human-male-v1"))
    parser.add_argument("--stock-dir", type=Path, default=Path("output/phenotypes/derived-v1/stock-cache"))
    parser.add_argument("--derived-dir", type=Path, default=Path("output/phenotypes/derived-v1/parts/dwarf-male/ascii"))
    parser.add_argument("--output-dir", type=Path, default=Path("output/phenotypes/derived-v1/previews/cp2-review"))
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
    scene = bpy.context.scene

    # Key light: warm key from +Y, +X, +Z
    key_data = bpy.data.lights.new(name="KeyLight", type="SUN")
    key_data.energy = 2.8
    key_data.color = (1.0, 0.96, 0.92)
    key_obj = bpy.data.objects.new(name="KeyLight", object_data=key_data)
    key_obj.rotation_euler = Euler((np.radians(50), np.radians(-20), np.radians(35)), "XYZ")
    bpy.context.collection.objects.link(key_obj)

    # Fill light: cool fill from +Y, -X, +Z
    fill_data = bpy.data.lights.new(name="FillLight", type="SUN")
    fill_data.energy = 1.4
    fill_data.color = (0.90, 0.94, 1.0)
    fill_obj = bpy.data.objects.new(name="FillLight", object_data=fill_data)
    fill_obj.rotation_euler = Euler((np.radians(45), np.radians(25), np.radians(-135)), "XYZ")
    bpy.context.collection.objects.link(fill_obj)

    # Rim light from behind
    rim_data = bpy.data.lights.new(name="RimLight", type="SUN")
    rim_data.energy = 1.6
    rim_data.color = (1.0, 1.0, 1.0)
    rim_obj = bpy.data.objects.new(name="RimLight", object_data=rim_data)
    rim_obj.rotation_euler = Euler((np.radians(-40), 0, 0), "XYZ")
    bpy.context.collection.objects.link(rim_obj)

    world = bpy.data.worlds.new("StudioWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.06, 0.07, 0.09, 1.0)
        bg.inputs["Strength"].default_value = 0.8
    scene.world = world


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Configure Cycles
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.render.threads_mode = "FIXED"
    scene.render.threads = min(4, args.threads)
    scene.cycles.samples = 64
    scene.cycles.preview_samples = 32
    scene.render.resolution_x = 2400
    scene.render.resolution_y = 1350
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"

    # Clean initial scene
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    setup_lighting()

    # Materials
    clay_human = create_clay_material("ClayHuman", (0.82, 0.78, 0.72))
    clay_stock_dwarf = create_clay_material("ClayStockDwarf", (0.70, 0.73, 0.78))
    clay_derived_dwarf = create_clay_material("ClayDerivedDwarf", (0.90, 0.82, 0.68)) # warm highlight clay

    unlit_human = create_unlit_material("UnlitHuman", (0.85, 0.65, 0.35))      # warm gold
    unlit_stock_dwarf = create_unlit_material("UnlitStockDwarf", (0.35, 0.65, 0.85)) # teal
    unlit_derived_dwarf = create_unlit_material("UnlitDerivedDwarf", (0.92, 0.35, 0.35)) # coral red

    # Load Rig transforms
    pmh0_text = (args.masters_dir / "stock" / "pmh0.mdl").read_text(encoding="cp1252")
    pmd0_text = (args.masters_dir / "stock" / "pmd0.mdl").read_text(encoding="cp1252")

    hm_rig = transforms(nodes(pmh0_text))
    dwarf_rig = transforms(nodes(pmd0_text))

    # Load parts
    master_parts = {}
    stock_dwarf_parts = {}
    derived_dwarf_parts = {}

    for part in PART_JOINTS:
        if part in ("head", "neck"):
            # Stock models
            hm_p = args.masters_dir / "stock" / f"pmh0_{part}001.mdl"
            master_parts[part] = decode_binary_mdl(hm_p, f"pmh0_{part}001g".encode())

            sd_p = args.stock_dir / f"pmd0_{part}001.mdl"
            stock_dwarf_parts[part] = decode_binary_mdl(sd_p, f"pmd0_{part}001g".encode())
            derived_dwarf_parts[part] = stock_dwarf_parts[part]
        else:
            # Body parts
            hm_p = args.masters_dir / "ascii" / f"pmh0_{part}001.mdl"
            master_parts[part] = decode_ascii_mdl(hm_p)

            sd_p = args.stock_dir / f"pmd0_{part}001.mdl"
            stock_dwarf_parts[part] = decode_binary_mdl(sd_p, f"pmd0_{part}001g".encode())

            der_p = args.derived_dir / f"pmd0_{part}001.mdl"
            derived_dwarf_parts[part] = decode_ascii_mdl(der_p)

    # 1. Build Clay Specimens
    obj_hm_clay = build_character_mesh("HumanMaster_Clay", master_parts, hm_rig, clay_human)
    obj_sd_clay = build_character_mesh("StockDwarf_Clay", stock_dwarf_parts, dwarf_rig, clay_stock_dwarf)
    obj_dd_clay = build_character_mesh("DerivedDwarf_Clay", derived_dwarf_parts, dwarf_rig, clay_derived_dwarf)

    # Positions: Human Master at +X=+1.2 (left in front view), Stock Dwarf at X=0, Derived Dwarf at -X=-1.2 (right in front view)
    loc_hm = Vector((1.2, 0.0, 0.0))
    loc_sd = Vector((0.0, 0.0, 0.0))
    loc_dd = Vector((-1.2, 0.0, 0.0))

    obj_hm_clay.location = loc_hm
    obj_sd_clay.location = loc_sd
    obj_dd_clay.location = loc_dd

    # Camera setup
    cam_data = bpy.data.cameras.new("OrthoCam")
    cam_data.type = "ORTHO"
    cam_obj = bpy.data.objects.new("OrthoCam", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    target = Vector((0.0, 0.0, 0.95))

    views = [
        ("front", Vector((0.0, 8.0, 0.95)), 4.0, False),
        ("side", Vector((8.0, 0.0, 0.95)), 4.0, True),
        ("oblique", Vector((5.5, 5.5, 2.2)), 4.0, False),
        ("rear", Vector((0.0, -8.0, 0.95)), 4.0, False),
    ]

    rendered_files = {}

    # Render Clay Pass
    print("--- Rendering Clay Comparison Views ---")
    for view_name, cam_pos, ortho_scale, is_side in views:
        t0 = time.time()
        if is_side:
            obj_hm_clay.location = Vector((0.0, -1.2, 0.0))
            obj_sd_clay.location = Vector((0.0, 0.0, 0.0))
            obj_dd_clay.location = Vector((0.0, 1.2, 0.0))
        else:
            obj_hm_clay.location = loc_hm
            obj_sd_clay.location = loc_sd
            obj_dd_clay.location = loc_dd

        bpy.context.view_layer.update()

        cam_obj.location = cam_pos
        direction = target - cam_pos
        cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        cam_data.ortho_scale = ortho_scale

        out_path = args.output_dir / f"cp2_clay_{view_name}.png"
        scene.render.filepath = str(out_path.resolve())
        bpy.ops.render.render(write_still=True)
        rendered_files[f"clay_{view_name}"] = str(out_path)
        print(f"Rendered clay {view_name} in {time.time()-t0:.2f}s -> {out_path.name}")

    # Switch to Unlit Materials
    print("--- Rendering Unlit Contour Views ---")
    obj_hm_clay.data.materials[0] = unlit_human
    obj_sd_clay.data.materials[0] = unlit_stock_dwarf
    obj_dd_clay.data.materials[0] = unlit_derived_dwarf

    for view_name, cam_pos, ortho_scale, is_side in views:
        t0 = time.time()
        if is_side:
            obj_hm_clay.location = Vector((0.0, -1.2, 0.0))
            obj_sd_clay.location = Vector((0.0, 0.0, 0.0))
            obj_dd_clay.location = Vector((0.0, 1.2, 0.0))
        else:
            obj_hm_clay.location = loc_hm
            obj_sd_clay.location = loc_sd
            obj_dd_clay.location = loc_dd

        bpy.context.view_layer.update()

        cam_obj.location = cam_pos
        direction = target - cam_pos
        cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        cam_data.ortho_scale = ortho_scale

        out_path = args.output_dir / f"cp2_unlit_{view_name}.png"
        scene.render.filepath = str(out_path.resolve())
        bpy.ops.render.render(write_still=True)
        rendered_files[f"unlit_{view_name}"] = str(out_path)
        print(f"Rendered unlit {view_name} in {time.time()-t0:.2f}s -> {out_path.name}")

    # Render Posed Views of Derived Dwarf Male
    print("--- Rendering Dynamic Posed Views ---")
    # Hide HM and Stock Dwarf
    obj_hm_clay.hide_render = True
    obj_sd_clay.hide_render = True
    obj_dd_clay.data.materials[0] = clay_derived_dwarf
    obj_dd_clay.location = Vector((0.0, 0.0, 0.0))

    stock_ascii_dir = Path("output/phenotypes/derived-v1/stock-cache/ascii")
    cam_data.ortho_scale = 2.4
    target_pose = Vector((0.0, 0.0, 0.75))

    motion_poses = [
        ("combat_ready", "plreadyr", 0.5, Vector((2.5, 3.5, 1.4))),
        ("running_stride", "run", 0.3, Vector((3.0, 2.5, 1.3))),
        ("deep_crouch", "gutokdf", 0.5, Vector((2.8, 3.0, 1.2))),
    ]

    for pose_label, clip, t, c_pos in motion_poses:
        t0 = time.time()
        xforms, _ = pose(stock_ascii_dir, "pmd0", clip, t, stock_dir=stock_ascii_dir)

        # Rebuild posed mesh
        bpy.data.objects.remove(obj_dd_clay, do_unlink=True)
        obj_dd_clay = build_character_mesh(f"DerivedDwarf_{pose_label}", derived_dwarf_parts, xforms, clay_derived_dwarf)
        obj_dd_clay.location = Vector((0.0, 0.0, 0.0))

        cam_obj.location = c_pos
        direction = target_pose - c_pos
        cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

        bpy.context.view_layer.update()
        out_path = args.output_dir / f"cp2_pose_{pose_label}.png"
        scene.render.filepath = str(out_path.resolve())
        bpy.ops.render.render(write_still=True)
        rendered_files[f"pose_{pose_label}"] = str(out_path)
        print(f"Rendered pose {pose_label} in {time.time()-t0:.2f}s -> {out_path.name}")

    report_path = args.output_dir / "rendered-files.json"
    report_path.write_text(json.dumps(rendered_files, indent=2) + "\n", encoding="utf-8")
    print(f"All renders complete. Summary written to {report_path}")


if __name__ == "__main__":
    main()
