"""Inspect a frozen Meshy outfit export for conversion defects (read-only on sources).

Runs in the launcher's isolated Blender. Measures counts against the face budget,
orientation and scale, islands and floating fragments, duplicate faces,
non-manifold and boundary edges, ray-tested hidden faces, leg/arm cross-section
fusion, joint edge density and an exposed-skin texture estimate. Every defect is
classified for repair; nothing is approved.
"""
import argparse
import json
from pathlib import Path
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_io import base_color_image, face_colours, import_single
from mesh_ops import edges, islands, slice_loops
from robe_common import FLAGS, fresh_directory, pin, require, sha, skin_colour, utc, write_fresh

DIRECTIONS = [Vector(v).normalized() for v in
              [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1), (1, 1, 1), (1, 1, -1), (1, -1, 1),
               (1, -1, -1), (-1, 1, 1), (-1, 1, -1), (-1, -1, 1), (-1, -1, -1)]]


def arrays(mesh):
    verts = np.empty(len(mesh.vertices) * 3)
    mesh.vertices.foreach_get("co", verts)
    mesh.calc_loop_triangles()
    tris = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int64)
    mesh.loop_triangles.foreach_get("vertices", tris)
    loops = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int64)
    mesh.loop_triangles.foreach_get("loops", loops)
    return verts.reshape(-1, 3), tris.reshape(-1, 3), loops.reshape(-1, 3)


def boundary_loops(unique, counts, welded_positions):
    boundary = unique[counts == 1]
    adjacency = {}
    for a, b in boundary:
        adjacency.setdefault(a, []).append(b)
        adjacency.setdefault(b, []).append(a)
    seen, loops = set(), []
    for start in adjacency:
        if start in seen:
            continue
        stack, members = [start], []
        while stack:
            v = stack.pop()
            if v in seen:
                continue
            seen.add(v)
            members.append(v)
            stack.extend(adjacency[v])
        points = welded_positions[members]
        loops.append({"vertices": len(members), "center": points.mean(0).round(4).tolist(),
                      "extent": (points.max(0) - points.min(0)).round(4).tolist()})
    return sorted(loops, key=lambda loop: -loop["vertices"])


def sections(verts, tris, axis, value, select=None, welded=None):
    """mesh_ops cross-sections as rounded JSON rows (face count, centre and bounds of the cut points)."""
    return [{"faces": row["faces"], "center": row["center"].round(4).tolist(), "min": row["min"].round(4).tolist(),
             "max": row["max"].round(4).tolist()}
            for row in slice_loops(verts, tris, axis, value, select=select, welded=welded)]


def hidden_faces(obj, verts, tris, sample):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    tree = BVHTree.FromBMesh(bm)
    bm.free()
    centers = verts[tris].mean(axis=1)
    normals = np.cross(verts[tris[:, 1]] - verts[tris[:, 0]], verts[tris[:, 2]] - verts[tris[:, 0]])
    lengths = np.linalg.norm(normals, axis=1)
    normals = normals / np.maximum(lengths, 1e-12)[:, None]
    hidden = []
    for index in sample:
        origin = Vector(centers[index] + normals[index] * 2e-4)
        escaped = False
        for direction in DIRECTIONS:
            if tree.ray_cast(origin, direction, 10.0)[0] is None:
                escaped = True
                break
        if not escaped:
            hidden.append(int(index))
    return hidden


def skin_estimate(obj, loops, image):
    if image is None or not obj.data.uv_layers:
        return None
    rgb = face_colours(obj, loops, image)
    return skin_colour(rgb), rgb


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--face-budget", type=int, default=100000)
    parser.add_argument("--hidden-sample", type=int, default=20000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    source = args.source.resolve()
    require(sha(source) == args.source_sha256, "Frozen source changed")
    output = fresh_directory(args.output)
    obj = import_single(source)
    verts, tris, loops = arrays(obj.data)
    low, high = verts.min(0), verts.max(0)
    size = high - low
    face_island, welded = islands(verts, tris)
    island_faces = np.bincount(face_island)
    main_island = int(np.argmax(island_faces))
    welded_positions = np.zeros((welded.max() + 1, 3))
    welded_positions[welded] = verts
    unique, counts = edges(tris, welded)
    # Islands: distance from each island to the main island surface (floating fragments).
    main_faces = tris[face_island == main_island]
    tree = BVHTree.FromPolygons([tuple(map(float, v)) for v in verts], [tuple(map(int, f)) for f in main_faces])
    island_rows = []
    for label in np.argsort(-island_faces):
        if label == main_island:
            continue
        faces = tris[face_island == label]
        points = verts[np.unique(faces)]
        step = max(1, len(points) // 200)
        gap = min(tree.find_nearest(Vector(p))[3] for p in points[::step])
        island_rows.append({"island": int(label), "faces": int(island_faces[label]),
                            "center": points.mean(0).round(4).tolist(),
                            "extent": (points.max(0) - points.min(0)).round(4).tolist(),
                            "distanceToMain": round(float(gap), 5)})
    # Rotate each triangle to start at its lowest vertex but keep its winding: a reversed copy is the
    # back of double-sided cloth (repair_source.remove_duplicates keeps it), not a duplicate.
    corners = welded[tris]
    start = corners.argmin(axis=1)[:, None]
    keys = np.take_along_axis(corners, (start + np.arange(3)) % 3, axis=1)
    _, duplicate_counts = np.unique(keys, axis=0, return_counts=True)
    rng = np.random.default_rng(1234)
    sample = rng.choice(len(tris), size=min(args.hidden_sample, len(tris)), replace=False)
    hidden = hidden_faces(obj, verts, tris, sample)
    # Orientation: Z up after glTF import. Front is the side toward which the boot toes extend.
    feet = verts[verts[:, 2] < low[2] + 0.06 * size[2]]
    ankles = verts[(verts[:, 2] > low[2] + 0.08 * size[2]) & (verts[:, 2] < low[2] + 0.14 * size[2])]
    forward = float(np.median(feet[:, 1]) - np.median(ankles[:, 1])) if len(feet) and len(ankles) else 0.0
    height = float(size[2])
    legs = {f"{fraction:.2f}": sections(verts, tris, 2, low[2] + fraction * height, welded=welded)
            for fraction in (0.20, 0.30, 0.40, 0.45)}
    arms = {}
    for sign, label in ((1, "left+x"), (-1, "right-x")):
        for fraction in (0.55, 0.70, 0.85):
            plane = sign * fraction * (high[0] if sign > 0 else -low[0])
            arms[f"{label}@{fraction:.2f}"] = sections(verts, tris, 0, plane,
                                                          select=lambda p: p[:, 2].mean() > low[2] + 0.55 * height,
                                                          welded=welded)
    lengths = np.linalg.norm(welded_positions[unique[:, 0]] - welded_positions[unique[:, 1]], axis=1)
    estimate = skin_estimate(obj, loops, base_color_image(obj))
    skin = None
    if estimate is not None:
        mask, rgb = estimate
        centers = verts[tris].mean(1)
        skin = {"faces": int(mask.sum()), "fraction": round(float(mask.mean()), 4),
                "heightBands": {f"{b:.1f}": int(mask[(centers[:, 2] >= low[2] + b * height) &
                                                     (centers[:, 2] < low[2] + (b + 0.1) * height)].sum())
                                for b in np.arange(0, 1.0, 0.1)},
                "method": "base-colour hue/saturation rule at face UV centroids; estimate only"}
        np.save(output / "skin-mask.npy", mask)
    floating = [row for row in island_rows if row["distanceToMain"] > 0.01]
    defects = []
    if len(tris) > args.face_budget:
        defects.append({"defect": "face budget exceeded", "measured": len(tris), "limit": args.face_budget,
                        "class": "auto-repairable", "repair": "UV-preserving collapse decimation to the budget"})
    if floating:
        defects.append({"defect": "floating fragments", "count": len(floating), "class": "auto-repairable",
                        "repair": "delete islands farther than 1 cm from the main surface"})
    if int((duplicate_counts > 1).sum()):
        defects.append({"defect": "duplicate faces", "count": int((duplicate_counts > 1).sum()),
                        "class": "auto-repairable", "repair": "remove duplicates"})
    if int((counts > 2).sum()):
        defects.append({"defect": "non-manifold edges", "count": int((counts > 2).sum()), "class": "manual-review"})
    hidden_fraction = len(hidden) / max(1, len(sample))
    if hidden_fraction > 0.01:
        defects.append({"defect": "hidden internal faces", "sampledFraction": round(hidden_fraction, 4),
                        "class": "auto-repairable", "repair": "delete faces with no unoccluded ray",
                        "appliedInAutomaticPass": False,
                        "reason": "rest-pose occlusion does not prove faces stay hidden in motion"})
    require(sha(source) == args.source_sha256, "Frozen source changed during inspection")
    report = {"schemaVersion": 1, "kind": "srn-robe-source-inspection", "createdUtc": utc(), "source": pin(source),
              "blenderVersion": bpy.app.version_string, "importer": "io_scene_gltf2 (Blender bundled)",
              "counts": {"vertices": len(verts), "triangles": len(tris), "faceBudget": args.face_budget,
                         "materials": [s.material.name for s in obj.material_slots if s.material],
                         "uvLayers": [u.name for u in obj.data.uv_layers]},
              "bounds": {"min": low.round(5).tolist(), "max": high.round(5).tolist(), "size": size.round(5).tolist()},
              "orientation": {"up": "+Z (glTF Y-up converted)", "bootToeOffsetY": round(forward, 4),
                              "front": "-Y" if forward < 0 else "+Y", "armsAlong": "X"},
              "islands": {"count": int(len(island_faces)), "mainFaces": int(island_faces[main_island]),
                          "others": island_rows[:200], "floating": floating},
              "duplicateFaces": int((duplicate_counts > 1).sum()),
              "edges": {"boundary": int((counts == 1).sum()), "manifold": int((counts == 2).sum()),
                        "nonManifold": int((counts > 2).sum()),
                        "medianLength": float(np.median(lengths)), "p95Length": float(np.percentile(lengths, 95))},
              "boundaryLoops": boundary_loops(unique, counts, welded_positions)[:40],
              "hiddenFaces": {"sampled": int(len(sample)), "hidden": len(hidden), "fraction": round(hidden_fraction, 4)},
              "crossSections": {"legsHorizontal": legs, "armsVertical": arms},
              "exposedSkinEstimate": skin, "defects": defects, **FLAGS}
    np.save(output / "hidden-sample.npy", np.array(hidden, dtype=np.int64))
    print(json.dumps(write_fresh(output / "inspection.json", report)))


if __name__ == "__main__":
    main()
