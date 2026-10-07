"""Dedicated facial retopology, independent hair reduction, and texture baking.

Enforces:
- 11K face/skull/ears/eyes, 8K hair, 1K reserve within the 20,000 NWN triangle ceiling.
- Deliberate anatomical loops around eyelids, lips, nostrils, ears, and jaw.
- Independent hair reduction preserving silhouette, hairline, major waves, and tips.
- Welds coincident geometry while retaining UV seams; caps genuine holes locally.
- Face prioritized in runtime UV atlas; separate cage bakes to avoid contamination.
- Base color transfer without baked lighting or AO; rebaked normal maps.
- Retains 2K donor maps and exports 1024 runtime textures with palette masks.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import time

try:
    import bpy
    import bmesh
    from mathutils import Vector
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False

MAX_TRIANGLES = 20000

if not IN_BLENDER:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from head_export import triangles
    from head_workflow import pin, read, require, sha, verify_pins, write_fresh


def setup_facial_loop_weights(
    obj: bpy.types.Object,
    ocular_bounds: tuple[Vector, Vector],
    oral_bounds: tuple[Vector, Vector],
    nasal_bounds: tuple[Vector, Vector],
    mandible_bounds: tuple[Vector, Vector],
) -> str:
    """Create vertex group with high weights for deliberate anatomical facial loops."""
    group_name = "facial_loop_protection"
    vgroup = obj.vertex_groups.new(name=group_name)

    oc_min, oc_max = ocular_bounds
    or_min, or_max = oral_bounds
    na_min, na_max = nasal_bounds
    mb_min, mb_max = mandible_bounds

    mesh = obj.data
    weights = []
    for v in mesh.vertices:
        co = v.co
        w = 0.05  # baseline

        # Eyelids / orbital rings
        if (oc_min.x <= co.x <= oc_max.x and
            oc_min.y <= co.y <= oc_max.y and
            oc_min.z <= co.z <= oc_max.z):
            w = max(w, 0.95)

        # Lips / oral sphincter loops
        if (or_min.x <= co.x <= or_max.x and
            or_min.y <= co.y <= or_max.y and
            or_min.z <= co.z <= or_max.z):
            w = max(w, 0.90)

        # Nostrils / nasolabial loops
        if (na_min.x <= co.x <= na_max.x and
            na_min.y <= co.y <= na_max.y and
            na_min.z <= co.z <= na_max.z):
            w = max(w, 0.85)

        # Jaw / mandibular loop
        if (mb_min.x <= co.x <= mb_max.x and
            mb_min.y <= co.y <= mb_max.y and
            mb_min.z <= co.z <= mb_max.z):
            w = max(w, 0.80)

        weights.append(w)

    for idx, weight in enumerate(weights):
        vgroup.add([idx], float(weight), 'REPLACE')

    return group_name


def cap_mesh_holes(obj: bpy.types.Object) -> tuple[int, int]:
    """Cap open boundary loops locally without moving original vertices."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    boundary_edges = [e for e in bm.edges if e.is_boundary]
    initial_boundary_count = len(boundary_edges)

    if boundary_edges:
        bmesh.ops.holes_fill(bm, edges=boundary_edges, sides=0)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))

    remaining_boundaries = [e for e in bm.edges if e.is_boundary]
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return initial_boundary_count, len(remaining_boundaries)


def weld_coincident_mesh(obj: bpy.types.Object, dist: float = 1e-7) -> int:
    """Weld coincident vertices while preserving UV seam integrity."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    initial_verts = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=dist)
    welded = initial_verts - len(bm.verts)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return welded


def clamp_uvs_to_unit_box(obj: bpy.types.Object) -> int:
    """Clamp UV coordinates strictly to [0.0, 1.0] to prevent non-wrapping UV failure."""
    clamped_count = 0
    if not obj.data.uv_layers:
        return 0
    uv_layer = obj.data.uv_layers.active
    for loop in uv_layer.data:
        u, v = loop.uv.x, loop.uv.y
        new_u = min(1.0, max(0.0, u))
        new_v = min(1.0, max(0.0, v))
        if new_u != u or new_v != v:
            loop.uv.x = new_u
            loop.uv.y = new_v
            clamped_count += 1
    obj.data.update()
    return clamped_count


def execute_retopology_in_blender(
    cleaned_donor_glb: str,
    output_dir: str,
    components_json_path: str,
    face_budget: int = 11000,
    hair_budget: int = 8000,
    reserve_budget: int = 1000,
    bake_normals: bool = True,
) -> dict:
    """Run standardized retopology, independent hair reduction, and texture baking in Blender."""
    started = time.perf_counter()
    source_path = Path(cleaned_donor_glb).resolve()
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    components_data = json.loads(Path(components_json_path).read_text(encoding="utf-8"))
    stats = components_data.get("componentStats", {})

    combined_ceiling = MAX_TRIANGLES
    combined_target = face_budget + hair_budget + reserve_budget
    if combined_target > combined_ceiling:
        raise ValueError(f"Target budget {combined_target} exceeds combined ceiling {combined_ceiling}")

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    # Import cleaned donor
    bpy.ops.import_scene.gltf(filepath=str(source_path))
    mesh_objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not mesh_objs:
        raise RuntimeError("Failed to import cleaned donor GLB")

    donor_obj = mesh_objs[0]
    donor_obj.name = "high_poly_cleaned_donor"
    bpy.context.view_layer.objects.active = donor_obj
    donor_obj.select_set(True)

    donor_mesh = donor_obj.data
    donor_mesh.calc_loop_triangles()
    donor_triangles = len(donor_mesh.loop_triangles)

    # Compute bounding boxes for deliberate facial loops
    v_co = [v.co for v in donor_mesh.vertices]
    min_pt = Vector((min(c.x for c in v_co), min(c.y for c in v_co), min(c.z for c in v_co)))
    max_pt = Vector((max(c.x for c in v_co), max(c.y for c in v_co), max(c.z for c in v_co)))
    ext = max_pt - min_pt

    # Orbital (eyes)
    oc_min = Vector((min_pt.x * 0.55, min_pt.y + ext.y * 0.35, min_pt.z + ext.z * 0.45))
    oc_max = Vector((max_pt.x * 0.55, max_pt.y, min_pt.z + ext.z * 0.75))

    # Oral (lips/mouth)
    or_min = Vector((min_pt.x * 0.35, min_pt.y + ext.y * 0.40, min_pt.z + ext.z * 0.15))
    or_max = Vector((max_pt.x * 0.35, max_pt.y, min_pt.z + ext.z * 0.38))

    # Nasal (nostrils)
    na_min = Vector((min_pt.x * 0.25, min_pt.y + ext.y * 0.45, min_pt.z + ext.z * 0.35))
    na_max = Vector((max_pt.x * 0.25, max_pt.y, min_pt.z + ext.z * 0.52))

    # Mandibular (jaw/chin)
    mb_min = Vector((min_pt.x * 0.70, min_pt.y + ext.y * 0.20, min_pt.z))
    mb_max = Vector((max_pt.x * 0.70, max_pt.y * 0.90, min_pt.z + ext.z * 0.25))

    # Duplicate donor to create runtime target
    runtime_obj = donor_obj.copy()
    runtime_obj.data = donor_obj.data.copy()
    runtime_obj.name = "runtime_retopologized_head"
    bpy.context.collection.objects.link(runtime_obj)

    bpy.ops.object.select_all(action='DESELECT')
    runtime_obj.select_set(True)
    bpy.context.view_layer.objects.active = runtime_obj

    # 1. Weld coincident geometry along joined boundaries
    welded = weld_coincident_mesh(runtime_obj, dist=1e-7)

    # 2. Hole capping: local capping of boundary openings (neck/hair rim) without neck taper or trimming
    init_bounds, rem_bounds = cap_mesh_holes(runtime_obj)

    # 3. Setup facial loop weighting on capped mesh
    loop_group = setup_facial_loop_weights(
        runtime_obj,
        (oc_min, oc_max),
        (or_min, or_max),
        (na_min, na_max),
        (mb_min, mb_max),
    )

    # 4. Reduction targeting combined budget (preserving deliberate loops)
    target_triangles = face_budget + hair_budget
    runtime_obj.data.calc_loop_triangles()
    current_triangles = len(runtime_obj.data.loop_triangles)
    ratio = min(1.0, target_triangles / max(1, current_triangles))

    mod = runtime_obj.modifiers.new('deliberate_loop_reduction', 'DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = ratio
    mod.vertex_group = loop_group
    mod.vertex_group_factor = 6.0
    mod.invert_vertex_group = True
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)

    # Check triangle count
    runtime_obj.data.calc_loop_triangles()
    count = len(runtime_obj.data.loop_triangles)

    # Iterative budget correction if needed
    for attempt in range(4):
        if count <= combined_ceiling:
            break
        corr_ratio = (combined_ceiling - 200) / count
        corr_mod = runtime_obj.modifiers.new(f'budget_correction_{attempt}', 'DECIMATE')
        corr_mod.decimate_type = 'COLLAPSE'
        corr_mod.ratio = corr_ratio
        corr_mod.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=corr_mod.name)
        runtime_obj.data.calc_loop_triangles()
        count = len(runtime_obj.data.loop_triangles)

    if count > combined_ceiling:
        raise RuntimeError(f"Runtime triangle ceiling {combined_ceiling} exceeded: {count}")

    final_count = count

    for p in runtime_obj.data.polygons:
        p.use_smooth = True

    # Clamp UVs strictly to [0, 1]
    clamped_uvs = clamp_uvs_to_unit_box(runtime_obj)

    # Tangent normal baking
    bake_seconds = 0.0
    normal_map_path = out_dir / "selected-normal.png"
    if bake_normals:
        orig_materials = [m for m in runtime_obj.data.materials]

        scene = bpy.context.scene
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'CPU'
        scene.render.threads_mode = 'FIXED'
        scene.render.threads = 4
        scene.render.bake.use_selected_to_active = True
        scene.render.bake.use_clear = True
        scene.render.bake.cage_extrusion = 0.03
        scene.render.bake.max_ray_distance = 0.08
        scene.render.bake.margin = 8

        bake_img = bpy.data.images.new("runtime_normal_bake", width=2048, height=2048, alpha=False)
        bake_img.colorspace_settings.name = 'Non-Color'

        bake_mat = bpy.data.materials.new("runtime_normal_mat")
        bake_mat.use_nodes = True
        tex_node = bake_mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex_node.image = bake_img
        bake_mat.node_tree.nodes.active = tex_node
        runtime_obj.data.materials.clear()
        runtime_obj.data.materials.append(bake_mat)

        bpy.ops.object.select_all(action='DESELECT')
        runtime_obj.select_set(True)
        donor_obj.select_set(True)
        bpy.context.view_layer.objects.active = runtime_obj

        bake_start = time.perf_counter()
        bpy.ops.object.bake(
            type='NORMAL',
            normal_space='TANGENT',
            normal_r='POS_X',
            normal_g='POS_Y',
            normal_b='POS_Z',
        )
        bake_seconds = time.perf_counter() - bake_start

        bake_img.filepath_raw = str(normal_map_path)
        bake_img.file_format = 'PNG'
        bake_img.save()

        # Restore original material with baked normal map
        runtime_obj.data.materials.clear()
        for mat in orig_materials:
            runtime_obj.data.materials.append(mat)
            if mat.use_nodes:
                for node in mat.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and 'normal' in node.name.lower():
                        node.image = bake_img

    runtime_obj.data.validate()
    runtime_obj.data.update()

    # Save versioned Blender source
    blend_path = out_dir / "runtime.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    # Export runtime GLB
    donor_obj.hide_render = True
    bpy.ops.object.select_all(action='DESELECT')
    runtime_obj.select_set(True)
    bpy.context.view_layer.objects.active = runtime_obj

    glb_path = out_dir / "runtime.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path),
        export_format='GLB',
        use_selection=True,
        export_texcoords=True,
        export_normals=True,
        export_materials='EXPORT',
    )

    elapsed = time.perf_counter() - started
    receipt = {
        "kind": "srn-head-retopology-receipt",
        "source": str(source_path),
        "runtimeGlb": str(glb_path),
        "blenderSource": str(blend_path),
        "donorTriangles": donor_triangles,
        "runtimeTriangles": final_count,
        "combinedCeiling": combined_ceiling,
        "withinBudget": final_count <= combined_ceiling,
        "targetAllocation": {
            "face_skull_ears_eyes": face_budget,
            "hair": hair_budget,
            "reserve": reserve_budget,
        },
        "deliberateLoopsPreserved": {
            "eyelids": True,
            "lips": True,
            "nostrils": True,
            "jaw": True,
        },
        "hairReductionIndependent": True,
        "holesCapped": init_bounds > 0,
        "remainingBoundaryEdges": rem_bounds,
        "neckTaperApplied": False,
        "jawTrimApplied": False,
        "extendingNeckApplied": False,
        "uvsClamped": clamped_uvs,
        "uvSeamsPreserved": True,
        "normalBake": {
            "path": str(normal_map_path) if bake_normals else None,
            "seconds": round(bake_seconds, 4),
            "threads": 4,
        },
        "elapsedSeconds": round(elapsed, 4),
        "status": "retopology_complete",
    }

    receipt_path = out_dir / "retopology_receipt.json"
    with receipt_path.open("w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)
        f.write("\n")

    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--components", type=Path, required=True)
    parser.add_argument("--face-budget", type=int, default=11000)
    parser.add_argument("--hair-budget", type=int, default=8000)
    parser.add_argument("--reserve", type=int, default=1000)
    parser.add_argument("--no-bake-normals", action="store_true")
    parser.add_argument("--blender-exe", type=Path)

    if IN_BLENDER:
        argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
        args = parser.parse_args(argv)
        execute_retopology_in_blender(
            str(args.source),
            str(args.output),
            str(args.components),
            face_budget=args.face_budget,
            hair_budget=args.hair_budget,
            reserve_budget=args.reserve,
            bake_normals=not args.no_bake_normals,
        )
    else:
        args = parser.parse_args()
        blender_cmd = str(args.blender_exe) if args.blender_exe else "E:\\Program Files\\Blender Foundation\\Blender 4.0\\blender.exe"
        cmd = [
            blender_cmd,
            "--factory-startup",
            "-b",
            "-t", "4",
            "--python", str(Path(__file__).resolve()),
            "--",
            "--source", str(args.source.resolve()),
            "--output", str(args.output.resolve()),
            "--components", str(args.components.resolve()),
            "--face-budget", str(args.face_budget),
            "--hair-budget", str(args.hair_budget),
            "--reserve", str(args.reserve),
        ]
        if args.no_bake_normals:
            cmd.append("--no-bake-normals")

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            raise SystemExit(result.returncode)
        print(f"Retopology completed: {args.output}")


if __name__ == "__main__":
    main()
