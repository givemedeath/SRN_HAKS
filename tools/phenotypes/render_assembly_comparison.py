"""Blender script: Render matched orthographic views comparing Human Master, Stock Dwarf, and Scaled Human.

Uses 4 CPU threads strictly per project rules.
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
from derive_rig import read_mdl_text
from target_contract import PART_JOINTS


def parse_args():
    argv = sys.argv
    if "--" in argv:
        args = argv[argv.index("--") + 1:]
    else:
        args = []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--masters-dir", type=Path, default=Path("output/phenotypes/derived-v1/masters/human-male-v1"))
    parser.add_argument("--stock-dir", type=Path, default=Path("output/phenotypes/derived-v1/stock-cache"))
    parser.add_argument("--output-dir", type=Path, default=Path("output/phenotypes/derived-v1/previews/cp1-assembly-comparison"))
    parser.add_argument("--artifact-dir", type=Path, default=Path("C:/Users/benco/.gemini/antigravity-ide/brain/4adb5468-4771-4ffc-93ea-eda7b809f211"))
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
            parts = s.split()
            if len(parts) >= 3:
                curr_verts.append([float(parts[0]), float(parts[1]), float(parts[2])])
        elif mode == "faces":
            parts = s.split()
            if len(parts) >= 3:
                curr_faces.append([int(parts[0]), int(parts[1]), int(parts[2])])
    if curr_verts:
        offset = len(all_verts)
        all_verts.extend(curr_verts)
        for f in curr_faces:
            all_faces.append([f[0] + offset, f[1] + offset, f[2] + offset])
    return {
        "position": np.array(all_verts, dtype=float),
        "faces": np.array(all_faces, dtype=int) if all_faces else np.zeros((0, 3), dtype=int)
    }


def create_clay_material(name: str, color_rgba: tuple[float, float, float, float], roughness: float = 0.55) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = color_rgba
    bsdf.inputs["Roughness"].default_value = roughness
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.35
    elif "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = 0.35
    out = nodes.new(type="ShaderNodeOutputMaterial")
    mat.node_tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def build_character_mesh(name: str, parts: dict[str, dict], supermodel_text: str, material: bpy.types.Material,
                         scale_factor: float = 1.0, z_ground_offset: float = 0.0,
                         base_pos: Vector = Vector((0, 0, 0))) -> tuple[bpy.types.Object, Vector]:
    skel = nodes(supermodel_text)
    world_xforms = transforms(skel)
    
    combined_verts = []
    combined_faces = []
    
    for part, joint in PART_JOINTS.items():
        if part not in parts:
            continue
        model = parts[part]
        pos = model["position"]
        xform = world_xforms[joint.lower()]
        world_pos = (xform[:3, :3] @ pos.T).T + xform[:3, 3]
        
        scaled_pos = world_pos * scale_factor
        scaled_pos[:, 2] += z_ground_offset
        
        offset = len(combined_verts)
        combined_verts.extend(scaled_pos.tolist())
        for f in model["faces"]:
            combined_faces.append([int(f[0]) + offset, int(f[1]) + offset, int(f[2]) + offset])
            
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(combined_verts, [], combined_faces)
    mesh.update()
    
    for poly in mesh.polygons:
        poly.use_smooth = True
        
    obj = bpy.data.objects.new(name, mesh)
    obj.location = base_pos
    obj.data.materials.append(material)
    bpy.context.collection.objects.link(obj)
    return obj, base_pos


def setup_scene(threads: int = 4):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.render.threads_mode = "FIXED"
    scene.render.threads = min(4, max(1, threads))
    scene.cycles.device = "CPU"
    scene.cycles.samples = 16
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 2048
    scene.render.resolution_y = 1536
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    
    # Clean studio lights
    # Key light: from front-left (+X, +Y, +Z) shining down on the chests/faces
    key_light_data = bpy.data.lights.new(name="KeyLight", type="SUN")
    key_light_data.energy = 2.4
    key_light_data.color = (1.0, 0.98, 0.95)
    key_light = bpy.data.objects.new(name="KeyLight", object_data=key_light_data)
    key_light.rotation_euler = Euler((np.radians(50), np.radians(-15), np.radians(145)), "XYZ")
    bpy.context.collection.objects.link(key_light)
    
    # Fill light: from front-right (-X, +Y, +Z)
    fill_light_data = bpy.data.lights.new(name="FillLight", type="SUN")
    fill_light_data.energy = 1.3
    fill_light_data.color = (0.92, 0.94, 1.0)
    fill_light = bpy.data.objects.new(name="FillLight", object_data=fill_light_data)
    fill_light.rotation_euler = Euler((np.radians(45), np.radians(25), np.radians(-135)), "XYZ")
    bpy.context.collection.objects.link(fill_light)

    # Rim light: from behind (-Y)
    rim_light_data = bpy.data.lights.new(name="RimLight", type="SUN")
    rim_light_data.energy = 1.2
    rim_light_data.color = (1.0, 1.0, 1.0)
    rim_light = bpy.data.objects.new(name="RimLight", object_data=rim_light_data)
    rim_light.rotation_euler = Euler((np.radians(-40), 0, 0), "XYZ")
    bpy.context.collection.objects.link(rim_light)
    
    # World background
    world = bpy.data.worlds.new("StudioWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.07, 0.08, 0.10, 1.0) # premium deep neutral
        bg.inputs["Strength"].default_value = 0.8
    scene.world = world


def render_views(specimens: list[tuple[bpy.types.Object, Vector]], output_dir: Path, artifact_dir: Path):
    target = Vector((0.0, 0.0, 0.95))
    
    views = [
        # In NWN, character faces +Y. So camera at +Y looking toward -Y views the FRONT!
        ("front", Vector((0.0, 8.0, 0.95)), 3.8, False),
        # Camera at -Y looking toward +Y views the REAR!
        ("rear", Vector((0.0, -8.0, 0.95)), 3.8, False),
        # Camera from side (+X): offset specimens along Y so all 3 profiles are visible side-by-side!
        ("side", Vector((8.0, 0.0, 0.95)), 3.8, True),
        # Oblique perspective view from front-right
        ("oblique", Vector((5.5, 5.5, 2.2)), 3.8, False),
        # Top view looking down
        ("top", Vector((0.0, 0.0, 8.0)), 4.0, False),
    ]
    
    cam_data = bpy.data.cameras.new("OrthoCamera")
    cam_data.type = "ORTHO"
    cam_obj = bpy.data.objects.new("OrthoCamera", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj
    
    rendered_files = {}
    
    for name, cam_pos, ortho_scale, is_side in views:
        t0 = time.time()
        
        # Position specimens: in side view, separate along Y so they don't occlude
        for i, (obj, orig_loc) in enumerate(specimens):
            if is_side:
                # Map X shift to Y shift so they appear spaced horizontally in side view
                obj.location = Vector((0.0, orig_loc.x, orig_loc.z))
            else:
                obj.location = orig_loc
                
        bpy.context.view_layer.update()
        
        cam_obj.location = cam_pos
        direction = target - cam_pos
        if name == "top":
            # For top view, align camera up with +Y so front faces up
            cam_obj.rotation_euler = Euler((0, 0, np.radians(-90)), "XYZ")
        else:
            cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
            
        cam_data.ortho_scale = ortho_scale
        
        out_file = output_dir / f"{name}.png"
        bpy.context.scene.render.filepath = str(out_file.resolve())
        bpy.ops.render.render(write_still=True)
        elapsed = time.time() - t0
        print(f"Rendered {name:8s} in {elapsed:.2f}s -> {out_file}")
        
        art_file = artifact_dir / f"cp1_assembly_{name}.png"
        try:
            import shutil
            shutil.copy2(out_file, art_file)
            rendered_files[name] = str(art_file)
        except Exception as e:
            rendered_files[name] = str(out_file)
            
    # Reset locations
    for obj, orig_loc in specimens:
        obj.location = orig_loc
        
    return rendered_files


def create_quadrant_sheet(rendered_files: dict[str, str], output_dir: Path, artifact_dir: Path):
    """Combine Front, Side, Rear, and Oblique into a single high-resolution comparison sheet."""
    try:
        f_img = Image.open(rendered_files["front"])
        s_img = Image.open(rendered_files["side"])
        r_img = Image.open(rendered_files["rear"])
        o_img = Image.open(rendered_files["oblique"])
        
        w, h = f_img.size
        # Half-scale for 2x2 grid
        thumb_w, thumb_h = w // 2, h // 2
        
        grid = Image.new("RGBA", (thumb_w * 2, thumb_h * 2), (18, 20, 26, 255))
        grid.paste(f_img.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS), (0, 0))
        grid.paste(s_img.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS), (thumb_w, 0))
        grid.paste(r_img.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS), (0, thumb_h))
        grid.paste(o_img.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS), (thumb_w, thumb_h))
        
        sheet_out = output_dir / "assembly_comparison_sheet.png"
        grid.save(sheet_out, format="PNG")
        
        art_sheet = artifact_dir / "cp1_assembly_sheet.png"
        grid.save(art_sheet, format="PNG")
        print(f"Created composite comparison sheet -> {art_sheet}")
    except Exception as e:
        print(f"Warning creating comparison sheet: {e}")


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Clean scene
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    
    # 2. Setup scene
    setup_scene(args.threads)
    
    # 3. Load supermodels
    pmh0_text = read_mdl_text((args.masters_dir / "stock" / "pmh0.mdl"))
    pmd0_text = read_mdl_text((args.masters_dir / "stock" / "pmd0.mdl"))
    
    # 4. Load Human Master parts
    master_parts = {}
    ascii_dir = args.masters_dir / "ascii"
    for part in PART_JOINTS:
        if part in ("head", "neck"):
            p = args.masters_dir / "stock" / f"pmh0_{part}001.mdl"
            master_parts[part] = decode_binary_mdl(p, f"pmh0_{part}001g".encode())
        else:
            p = ascii_dir / f"pmh0_{part}001.mdl"
            master_parts[part] = decode_ascii_mdl(p)
            
    # 5. Load Stock Dwarf parts
    dwarf_parts = {}
    for part in PART_JOINTS:
        p = args.stock_dir / f"pmd0_{part}001.mdl"
        dwarf_parts[part] = decode_binary_mdl(p, f"pmd0_{part}001g".encode())
        
    # 6. Materials
    # Warm slate grey for Human master
    mat_human = create_clay_material("Clay_HumanMaster", (0.68, 0.70, 0.73, 1.0))
    # Rich terracotta for Dwarf
    mat_dwarf = create_clay_material("Clay_StockDwarf", (0.84, 0.54, 0.38, 1.0))
    # Soft steel blue for Scaled Human
    mat_scaled = create_clay_material("Clay_ScaledHuman", (0.45, 0.60, 0.74, 1.0))
    
    # 7. Build meshes
    specimens = []
    
    # Specimen 1: Human Male Master (Full Stature 1.934m) at X = +1.35m (Screen Left when viewed from +Y)
    obj_h, loc_h = build_character_mesh("Human_Master", master_parts, pmh0_text, mat_human,
                                         scale_factor=1.0, z_ground_offset=0.0005,
                                         base_pos=Vector((1.35, 0, 0)))
    specimens.append((obj_h, loc_h))
                         
    # Specimen 2: Stock Dwarf Male (Stature 1.486m, ground offset -0.3905m to plant feet) at X = 0.0m (Screen Center)
    obj_d, loc_d = build_character_mesh("Stock_Dwarf", dwarf_parts, pmd0_text, mat_dwarf,
                                         scale_factor=1.0, z_ground_offset=-0.3905,
                                         base_pos=Vector((0.0, 0, 0)))
    specimens.append((obj_d, loc_d))
                         
    # Specimen 3: Scaled Human (Human master scaled 0.686x -> 1.326m) at X = -1.20m (Screen Right when viewed from +Y)
    obj_s, loc_s = build_character_mesh("Scaled_Human_Alias", master_parts, pmh0_text, mat_scaled,
                                         scale_factor=0.685714, z_ground_offset=0.0003,
                                         base_pos=Vector((-1.20, 0, 0)))
    specimens.append((obj_s, loc_s))
                         
    # 8. Render orthographic views
    print(f"Starting orthographic renders with {args.threads} threads...")
    renders = render_views(specimens, args.output_dir, args.artifact_dir)
    
    # 10. Write render manifest
    manifest = {
        "schemaVersion": 1,
        "kind": "phenotype-cp1-previews",
        "threads": args.threads,
        "views": renders,
        "specimens": [
            {"id": "human_master", "label": "Human Male Master", "stature": 1.9339, "xPos": -1.35, "color": "Slate Grey"},
            {"id": "stock_dwarf", "label": "Stock Dwarf Male (pmd0)", "stature": 1.4864, "xPos": 0.0, "color": "Terracotta"},
            {"id": "scaled_human", "label": "Uniform Scaled Human (0.686x)", "stature": 1.3261, "xPos": 1.20, "color": "Steel Blue"}
        ]
    }
    manifest_file = args.output_dir / "preview-manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote preview manifest to {manifest_file}")


if __name__ == "__main__":
    main()
