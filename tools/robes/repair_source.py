"""Apply the configured automatic repairs to a frozen Meshy export (Blender).

Repairs are recorded as interventions with counts; the source file is never
modified. Output is a repaired GLB plus repair.json. Approves nothing.
"""
import argparse
import json
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_io import import_single
from robe_common import FLAGS, fresh_directory, pin, read_pinned, require, sha, utc, verify_pins, write_fresh


def weld(obj, distance=1e-6):
    """Merge seam-split coincident vertices; per-loop UVs keep the texture layout."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    before = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=distance)
    after = len(bm.verts)
    bm.to_mesh(obj.data)
    bm.free()
    return before - after


def triangles(obj):
    obj.data.calc_loop_triangles()
    return len(obj.data.loop_triangles)


def remove_duplicates(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    seen, doomed = set(), []
    for face in bm.faces:
        # Same vertices in the same winding: a reversed face is the back of double-sided cloth, not a copy.
        ring = [v.index for v in face.verts]
        start = ring.index(min(ring))
        key = tuple(ring[start:] + ring[:start])
        if key in seen:
            doomed.append(face)
        seen.add(key)
    bmesh.ops.delete(bm, geom=doomed, context="FACES")
    bm.to_mesh(obj.data)
    bm.free()
    return len(doomed)


def remove_floating(obj, distance):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    islands, seen = [], set()
    for face in bm.faces:
        if face.index in seen:
            continue
        stack, members = [face], []
        while stack:
            current = stack.pop()
            if current.index in seen:
                continue
            seen.add(current.index)
            members.append(current)
            for edge in current.edges:
                stack.extend(f for f in edge.link_faces if f.index not in seen)
        islands.append(members)
    islands.sort(key=len, reverse=True)
    main = islands[0]
    tree = BVHTree.FromPolygons([v.co.copy() for v in bm.verts], [[v.index for v in f.verts] for f in main])
    doomed = []
    for island in islands[1:]:
        points = {v for f in island for v in f.verts}
        gap = min(tree.find_nearest(v.co)[3] for v in points)
        if gap > distance:
            doomed.extend(island)
    removed = len(doomed)
    bmesh.ops.delete(bm, geom=doomed, context="FACES")
    bm.to_mesh(obj.data)
    bm.free()
    return removed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    config_bytes, config_pin = read_pinned(args.config)
    config = json.loads(config_bytes.decode("utf-8-sig"))
    require(config["kind"] == "srn-robe-outfit-config", "Outfit config required")
    source = (args.run_root / config["source"]["working"]).resolve()
    source_pin = pin(source)
    output = fresh_directory(args.output)
    obj = import_single(source)
    before = triangles(obj)
    interventions = [{"step": "weld seam-split coincident vertices (1e-6 m)", "automatic": True,
                      "verticesMerged": weld(obj)}]
    options = config["repair"]
    if options.get("removeDuplicateFaces"):
        count = remove_duplicates(obj)
        interventions.append({"step": "remove duplicate faces", "faces": count, "automatic": True})
    if options.get("removeFloatingFartherThan") is not None:
        count = remove_floating(obj, options["removeFloatingFartherThan"])
        interventions.append({"step": "remove floating islands", "faces": count, "automatic": True,
                              "threshold": options["removeFloatingFartherThan"]})
    require(not options.get("removeHiddenFaces"), "Hidden-face deletion is not part of the automatic pass")
    current = triangles(obj)
    if options.get("decimateToBudget") and current > config["faceBudget"]:
        target = int(config["faceBudget"] * options.get("budgetMargin", 0.995))
        modifier = obj.modifiers.new("budget", "DECIMATE")
        modifier.decimate_type = "COLLAPSE"
        ratio = target / current
        modifier.ratio = ratio
        modifier.use_collapse_triangulate = True
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier="budget")
        interventions.append({"step": "UV-preserving collapse decimation to face budget", "automatic": True,
                              "trianglesBefore": current, "trianglesAfter": triangles(obj), "ratio": ratio})
    final = triangles(obj)
    require(final <= config["faceBudget"], "Face budget still exceeded after repair")
    target_path = output / "repaired.glb"
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(target_path), export_format="GLB", use_selection=True,
                              export_apply=True, export_yup=True)
    require(sha(source) == source_pin["sha256"], "Source changed during repair")
    verify_pins([config_pin])
    report = {"schemaVersion": 1, "kind": "srn-robe-source-repair", "createdUtc": utc(), "outfit": config["outfit"],
              "config": config_pin, "source": source_pin, "repaired": pin(target_path),
              "trianglesBefore": before, "trianglesAfter": final, "faceBudget": config["faceBudget"],
              "interventions": interventions, "manualInterventions": [], **FLAGS}
    print(json.dumps(write_fresh(output / "repair.json", report)))


if __name__ == "__main__":
    main()
