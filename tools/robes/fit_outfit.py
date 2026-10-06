"""Fit a repaired Meshy outfit onto the stock phenotype bind pose (Blender driver).

Orients and scales the outfit from measured landmarks, converts the generation
pose by geodesic-segmented proxy-rig deformation onto the stock bind joints, then
inflates it with a smooth lattice field to a configured clearance outside the
stock body. With fit.space "generation" the clearance pass runs in the outfit's
own generation (A-)pose against the stock body posed into it, so hanging arms
never share lattice cells with the torso, and the result is then converted to
bind. The stock rig is read only. Writes fitted.glb, fit.json and
fit-arrays.npz; approves nothing.
"""
import argparse
import json
from pathlib import Path
import sys

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fit_math
from mesh_ops import neighbours, weld_ids
from robe_common import FLAGS, fresh_directory, pin, read, require, utc, verify_pins, write_fresh
from stock_body import Body

BLENDS = {"shoulder": 0.09, "elbow": 0.05, "wrist": 0.03, "knee": 0.05, "ankle": 0.04, "torsoCoreHalfWidth": 0.10,
          "armSeedFraction": 0.45, "armSeedRadius": 0.15, "labelSmoothing": 6}


def import_single(path):
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    meshes = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    require(len(meshes) == 1, "Expected one mesh object")
    obj = meshes[0]
    obj.data.transform(obj.matrix_world)
    obj.matrix_world.identity()
    return obj


def mesh_arrays(obj):
    mesh = obj.data
    verts = np.empty(len(mesh.vertices) * 3)
    mesh.vertices.foreach_get("co", verts)
    mesh.calc_loop_triangles()
    tris = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int64)
    mesh.loop_triangles.foreach_get("vertices", tris)
    return verts.reshape(-1, 3), tris.reshape(-1, 3)


def outer_visibility(verts, tris, welded, rays=24, seed=11):
    """Per-vertex flag: some outward-hemisphere ray escapes the outfit (inner layers stay False)."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    unique_ids, first = np.unique(welded, return_index=True)
    points = verts[first]
    faces = welded[tris]
    normals = np.zeros_like(points)
    face_normals = np.cross(points[faces[:, 1]] - points[faces[:, 0]], points[faces[:, 2]] - points[faces[:, 0]])
    for k in range(3):
        np.add.at(normals, faces[:, k], face_normals)
    normals /= np.maximum(np.linalg.norm(normals, axis=1), 1e-12)[:, None]
    tree = BVHTree.FromPolygons([tuple(p) for p in points.tolist()], [tuple(f) for f in faces.tolist()])
    directions = np.random.default_rng(seed).normal(size=(rays, 3))
    directions /= np.linalg.norm(directions, axis=1)[:, None]
    visible = np.zeros(len(points), bool)
    for index, (point, normal) in enumerate(zip(points, normals)):
        origin = Vector(point + normal * 1e-3)
        for direction in directions:
            if direction @ normal <= 0.05:
                continue
            if tree.ray_cast(origin, Vector(direction), 5.0)[0] is None:
                visible[index] = True
                break
    return visible[np.searchsorted(unique_ids, welded)]


def jsonable(value):
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return np.round(value, 6).tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    return value


def describe(matrix):
    linear = matrix[:3, :3]
    u, s, vt = np.linalg.svd(linear)
    rotation = u @ vt
    angle = float(np.degrees(np.arccos(np.clip((np.trace(rotation) - 1) / 2, -1, 1))))
    return {"rotationDegrees": round(angle, 3), "singularValues": np.round(s, 4).tolist(),
            "translation": np.round(matrix[:3, 3], 5).tolist()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--repaired", type=Path, required=True)
    parser.add_argument("--stock-ascii", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    config = read(args.config)
    require(config["kind"] == "srn-robe-outfit-config", "Outfit config required")
    inputs = [pin(args.config), pin(args.repaired)]
    output = fresh_directory(args.output)
    fit = config["fit"]
    blends = {**BLENDS, **fit.get("blends", {})}
    obj = import_single(args.repaired)
    verts, tris = mesh_arrays(obj)
    welded = weld_ids(verts, 1e-6)
    unique_ids, first = np.unique(welded, return_index=True)
    rows, cols = neighbours(tris, len(first), welded)
    oriented = fit_math.rotate_front(verts, config["orientation"]["sourceFront"], config["orientation"]["targetFront"])
    body = Body(args.stock_ascii, config["target"]["prefix"])
    targets = fit_math.stock_targets(body)
    raw_marks = fit_math.outfit_landmarks(oriented, tris, welded)
    scale, offset = fit_math.similarity(raw_marks, targets)
    aligned = scale * oriented + offset
    marks = fit_math.apply_similarity(raw_marks, scale, offset)
    joints = fit_math.outfit_joints(marks, targets, aligned)
    transforms = fit_math.proxy_transforms(joints, targets)
    labels, soft, seed_counts = fit_math.segment_labels(aligned[first], rows, cols, joints, marks, blends)
    corrections = config.get("corrections", {})
    override_counts = []
    if corrections.get("segmentOverrides"):
        labels, soft, override_counts = fit_math.apply_segment_overrides(
            aligned[first], labels, rows, cols, corrections["segmentOverrides"], blends["labelSmoothing"], joints)
    weights = fit_math.proxy_weights(aligned[first], soft, joints, blends)[welded]
    method = fit.get("conversionBlend", "linear")
    posed = fit_math.blend(aligned, weights, transforms, method)
    space = fit.get("space", "bind")
    require(space in ("bind", "generation"), "fit.space must be bind or generation")
    clearance_source = aligned if space == "generation" else posed
    visible = outer_visibility(clearance_source, tris, welded)
    clearance_parts = (fit_math.visible_parts(config["hide"]) if fit.get("clearanceParts") == "visible"
                       else fit["bodyParts"])
    # The garment wraps the neck, not the head: a capped Meshy collar sits inside the head volume
    # and clearing it blew the collar out by up to 27 cm (v5).
    clearance_parts = [p for p in clearance_parts if p not in fit.get("clearanceExclude", [])]
    volume = Body(args.stock_ascii, config["target"]["prefix"], parts=clearance_parts)
    if volume.parts:
        frames = fit_math.generation_pose_frames(volume.bind, transforms) if space == "generation" else None
        body_verts, body_faces, _ = volume.posed(frames)
        inflated, history, signed, initial = fit_math.lattice_inflate(
            clearance_source[first], visible[first], body_verts, body_faces, fit["clearance"], fit["latticeCell"],
            fit["latticeSigma"], fit["latticeIterations"], fit.get("latticeFade", 0.5),
            min_improvement=fit.get("latticeMinImprovement", 0.01))
    else:
        # Nothing visible to clear (e.g. the open-ended neck tube made pushes accumulate): keep Meshy's shape.
        inflated, history = clearance_source[first].copy(), []
        signed = initial = np.full(len(first), np.inf)
    generation = inflated[welded] if space == "generation" else None
    fitted = fit_math.blend(generation, weights, transforms, method) if space == "generation" else inflated[welded]
    separation = fit.get("bindSeparation")
    separation_history = None
    if separation:
        # Move only the listed segments (torso/belt/legs) away from the hanging stock arms in bind;
        # sleeves stay put, so the elbows are not pushed in.
        require(space == "generation", "bindSeparation follows a generation-space fit")
        arms = Body(args.stock_ascii, config["target"]["prefix"], parts=separation["bodyParts"])
        arm_verts, arm_faces, _ = arms.posed()
        movable = np.isin(labels, [fit_math.SEGMENTS.index(s) for s in separation["segments"]])
        bind_visible = outer_visibility(fitted, tris, welded)[first]
        separated, separation_history, _, _ = fit_math.lattice_inflate(
            fitted[first], bind_visible, arm_verts, arm_faces, separation["clearance"], fit["latticeCell"],
            fit["latticeSigma"], separation.get("iterations", 12), fit.get("latticeFade", 0.5),
            min_improvement=fit.get("latticeMinImprovement", 0.01), movable=movable)
        fitted = separated[welded]
    inflated = fitted[first]
    shift_source = clearance_source
    obj.data.vertices.foreach_set("co", fitted.ravel())
    obj.data.update()
    obj.name = config["outfit"] + "_fitted"
    path = output / "fitted.glb"
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True, export_yup=True)
    shift = np.linalg.norm((generation[first] if generation is not None else inflated) - shift_source[first], axis=1)
    outer = visible[first]
    dominant = weights[first].argmax(1)
    regions = {}
    for index, name in enumerate(fit_math.PROXY):
        mask = dominant == index
        if mask.any():
            regions[name] = {"vertices": int(mask.sum()), "outerVertices": int((mask & outer).sum()),
                             "outerInitiallyInside": int(((initial < 0) & mask & outer).sum()),
                             "outerFinalInside": int(((signed < 0) & mask & outer).sum()),
                             "maximumShift": float(shift[mask].max()), "p95Shift": float(np.percentile(shift[mask], 95))}
    np.savez_compressed(output / "fit-arrays.npz", proxyWeights=weights, welded=welded, aligned=aligned, posed=posed,
                        fitted=fitted, tris=tris, visible=visible, segmentLabels=labels[welded],
                        inflation=shift[welded], signedDistance=signed[welded],
                        **({"fittedGeneration": generation,
                            "proxyTransforms": np.stack([transforms[n] for n in fit_math.PROXY])}
                           if generation is not None else {}))
    pose_shift = np.linalg.norm(posed - aligned, axis=1)
    verify_pins(inputs)
    report = {"schemaVersion": 1, "kind": "srn-robe-fit", "createdUtc": utc(), "outfit": config["outfit"],
              "inputs": inputs, "stockAscii": str(Path(args.stock_ascii).resolve()),
              "method": "landmark similarity + geodesic-segmented proxy-rig pose conversion + lattice inflation",
              "orientation": config["orientation"], "uniformScale": scale, "offset": offset,
              "outfitLandmarksRaw": raw_marks, "outfitLandmarksAligned": marks, "outfitJoints": joints,
              "stockTargets": targets, "blends": blends,
              "segments": {"seeds": seed_counts, "manualOverrides": override_counts,
                           "counts": {name: int((labels == i).sum())
                                                            for i, name in enumerate(fit_math.SEGMENTS)}},
              "proxyTransforms": {name: describe(matrix) for name, matrix in transforms.items()},
              "poseConversion": {"maximumShift": float(pose_shift.max()), "p95Shift": float(np.percentile(pose_shift, 95)),
                                 "dominantProxyCounts": {name: int((dominant == i).sum())
                                                         for i, name in enumerate(fit_math.PROXY)}},
              "clearanceSpace": space, "conversionBlend": method, "clearanceParts": sorted(volume.parts), "bindSeparation": {"settings": separation, "history": separation_history},
              "inflation": {"bodyParts": clearance_parts, "distance": fit["clearance"], "cell": fit["latticeCell"],
                            "sigma": fit["latticeSigma"], "history": history, "maximumShift": float(shift.max()),
                            "p95Shift": float(np.percentile(shift, 95)), "outerVertices": int(outer.sum()),
                            "byDominantProxy": regions},
              "fitted": pin(path), "arrays": pin(output / "fit-arrays.npz"),
              "bindFramesChanged": False, "animationsChanged": False, **FLAGS}
    print(json.dumps(write_fresh(output / "fit.json", jsonable(report))))


if __name__ == "__main__":
    main()
