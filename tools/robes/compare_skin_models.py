"""Measure structural, attribute, weight and sampled-deformation differences of two models.

Used for the stock Neverblender control and for re-import verification. Vertices
are matched by bind-space position because exporters may reorder or split them.
The report states measurements and, optionally, a tolerance verdict; it never
approves visible deformation.
"""
import argparse
from pathlib import Path

import numpy as np

import lbs
import mdl_ascii
from robe_common import FLAGS, pin, read, require, utc, verify_pins, write_fresh


def nearest(reference, query, cell=1e-3):
    """Index of and distance to the nearest reference point for each query point (grid hash)."""
    reference, query = np.asarray(reference, float), np.asarray(query, float)
    keys = np.floor(reference / cell).astype(np.int64)
    grid = {}
    for index, key in enumerate(map(tuple, keys)):
        grid.setdefault(key, []).append(index)
    offsets = [(x, y, z) for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1)]
    found = np.empty(len(query), dtype=np.int64)
    distance = np.empty(len(query))
    for row, point in enumerate(query):
        base = np.floor(point / cell).astype(np.int64)
        candidates = [i for dx, dy, dz in offsets for i in grid.get((base[0] + dx, base[1] + dy, base[2] + dz), ())]
        if not candidates:
            candidates = range(len(reference))
        candidates = np.fromiter(candidates, dtype=np.int64)
        gaps = np.linalg.norm(reference[candidates] - point, axis=1)
        best = int(np.argmin(gaps))
        found[row], distance[row] = candidates[best], gaps[best]
    return found, distance


def smoothing_edges(left_faces, left_world, right_faces, right_world, digits=4):
    """Shared edges whose smooth/hard state differs; group numbers may be renumbered freely."""
    def states(faces, world):
        edges = {}
        for face in faces:
            for a, b in ((0, 1), (1, 2), (2, 0)):
                key = tuple(sorted((tuple(np.round(world[face[a]], digits)), tuple(np.round(world[face[b]], digits)))))
                edges.setdefault(key, []).append(int(face[3]))
        return {key: bool(groups[0] & groups[1]) for key, groups in edges.items() if len(groups) == 2}
    left, right = states(left_faces, left_world), states(right_faces, right_world)
    return sum(1 for key, smooth in right.items() if key in left and left[key] != smooth)


def corners(node, world):
    faces = np.asarray(node.arrays.get("faces", np.zeros((0, 8))), dtype=np.int64)
    tverts = np.asarray(node.arrays.get("tverts", np.zeros((0, 3))), dtype=float)
    positions = world[faces[:, :3]].reshape(-1, 3) if len(faces) else np.zeros((0, 3))
    uvs = tverts[faces[:, 4:7]].reshape(-1, tverts.shape[1])[:, :2] if len(faces) and len(tverts) else None
    return faces, positions, uvs


def compare_mesh(left_rig, right_rig, left, right, samples, index_tolerance=1e-4):
    lw, rw = lbs.bind_world(left_rig, left), lbs.bind_world(right_rig, right)
    lf, lc, lu = corners(left, lw)
    rf, rc, ru = corners(right, rw)
    # Coincident double-sided vertices make position matching ambiguous; keep index identity
    # whenever the exporter preserved vertex and face order.
    ordered = (len(lw) == len(rw) and len(lf) == len(rf) and np.array_equal(lf[:, :3], rf[:, :3])
               and float(np.abs(lw - rw).max(initial=0.0)) <= index_tolerance)
    if ordered:
        match, gap = np.arange(len(rw)), np.linalg.norm(lw - rw, axis=1)
        back_gap = gap
    else:
        match, gap = nearest(lw, rw)
        back, back_gap = nearest(rw, lw)
    row = {"node": left.name, "kinds": [left.kind, right.kind], "vertices": [len(lw), len(rw)],
           "faces": [len(lf), len(rf)], "mapping": "index" if ordered else "nearest-position",
           "maximumPositionError": float(max(gap.max(), back_gap.max())) if len(gap) else 0.0,
           "bitmap": [left.get("bitmap"), right.get("bitmap")], "uvPresent": [lu is not None, ru is not None]}
    if len(lc) and len(rc):
        left_tri, right_tri = lc.reshape(-1, 3, 3), rc.reshape(-1, 3, 3)
        if ordered:
            face_match = np.arange(len(right_tri))
            face_gap = np.linalg.norm(left_tri.mean(axis=1) - right_tri.mean(axis=1), axis=1)
        else:
            face_match, face_gap = nearest(left_tri.mean(axis=1), right_tri.mean(axis=1))
        paired = left_tri[face_match]
        # Winding-preserving cyclic alignment; coincident corners are disambiguated by UV.
        rotations = np.array([[0, 1, 2], [1, 2, 0], [2, 0, 1]])
        position_error = np.stack([np.linalg.norm(paired[:, r] - right_tri, axis=2).max(axis=1) for r in rotations], 1)
        uv_error = np.zeros_like(position_error)
        if lu is not None and ru is not None:
            left_uv, right_uv = lu.reshape(-1, 3, 2)[face_match], ru.reshape(-1, 3, 2)
            uv_error = np.stack([np.abs(left_uv[:, r] - right_uv).max(axis=(1, 2)) for r in rotations], 1)
        best = np.array([min(range(3), key=lambda k: (round(position_error[f, k], 7), uv_error[f, k]))
                         for f in range(len(right_tri))])
        chosen = np.arange(len(right_tri))
        row["maximumFaceCentroidError"] = float(face_gap.max())
        # Exported-to-reference pairing is many-to-one; also require every reference face to be covered,
        # so a duplicated triangle cannot hide an omitted one.
        _, coverage_gap = (np.arange(len(left_tri)), face_gap) if ordered else \
            nearest(right_tri.mean(axis=1), left_tri.mean(axis=1))
        row["maximumReferenceFaceGap"] = float(coverage_gap.max())
        row["maximumCornerPositionError"] = float(position_error[chosen, best].max())
        if lu is not None and ru is not None:
            row["maximumUvError"] = float(uv_error[chosen, best].max())
        area = np.linalg.norm(np.cross(left_tri[:, 1] - left_tri[:, 0], left_tri[:, 2] - left_tri[:, 0]), axis=1) / 2
        row["degenerateReferenceFaces"] = int(np.sum(area < 1e-12))
        row["smoothingEdgeMismatches"] = smoothing_edges(lf, lw, rf, rw)
        # The per-face surface-material column only matters for walkmeshes; render meshes ignore it.
        row["surfaceMaterialIdMismatches"] = int(np.sum(lf[face_match, 7] != rf[:, 7]))
    if left.kind == "skin" and right.kind == "skin":
        lW, lb = mdl_ascii.skin_matrix(left)
        rW, rb = mdl_ascii.skin_matrix(right)
        bones = sorted(set(lb) | set(rb))
        lW, _ = mdl_ascii.skin_matrix(left, bones)
        rW, _ = mdl_ascii.skin_matrix(right, bones)
        delta = np.abs(lW[match] - rW)
        row.update(bones=[lb, rb], maximumWeightError=float(delta.max()),
                   influenceChanges=int(np.sum((lW[match] > 0).sum(1) != (rW > 0).sum(1))),
                   rightMaximumSumDeviation=float(np.abs(rW.sum(1) - 1).max()))
        worst = {"error": 0.0}
        for sample in samples:
            lframes = left_rig.frames(sample["clip"], sample["time"])
            rframes = right_rig.frames(sample["clip"], sample["time"])
            error = np.linalg.norm(lbs.skin(left_rig, left, lframes, lW, bones)[match]
                                   - lbs.skin(right_rig, right, rframes, rW, bones), axis=1).max()
            if error > worst["error"]:
                worst = {"error": float(error), **sample}
        row["sampledDeformation"] = {"samples": len(samples), "maximumDisplacementError": worst["error"],
                                     "worstSample": worst}
    return row


def compare(left_path, right_path, left_chain, right_chain, ascii_directory, motion_count=9):
    left_rig = lbs.Rig(left_path, left_chain, ascii_directory)
    right_rig = lbs.Rig(right_path, right_chain, ascii_directory)
    lm, rm = left_rig.model, right_rig.model
    lnodes, rnodes = {n.key: n for n in lm.nodes}, {n.key: n for n in rm.nodes}
    shared = [k for k in lnodes if k in rnodes]
    frames = []
    for key in shared:
        a, b = left_rig.bind[key], right_rig.bind[key]
        frames.append({"node": key, "translation": float(np.abs(a[:3, 3] - b[:3, 3]).max()),
                       "rotation": float(np.abs(a[:3, :3] - b[:3, :3]).max())})
    samples = lbs.motion_samples(left_rig, count=motion_count)
    meshes = [compare_mesh(left_rig, right_rig, lnodes[k], rnodes[k], samples) for k in shared
              if lnodes[k].kind in mdl_ascii.MESHES and lnodes[k].get("render", "1") != "0"]
    return {"header": {"supermodel": [lm.supermodel, rm.supermodel],
                       "classification": [lm.classification, rm.classification],
                       "animationScale": [lm.animation_scale, rm.animation_scale],
                       "localAnimations": [len(lm.animations), len(rm.animations)]},
            "missingNodes": sorted(set(lnodes) - set(rnodes)), "addedNodes": sorted(set(rnodes) - set(lnodes)),
            "kindChanges": [k for k in shared if lnodes[k].kind != rnodes[k].kind],
            "parentChanges": [k for k in shared if lnodes[k].parent.lower() != rnodes[k].parent.lower()],
            "maximumBindTranslationError": max(f["translation"] for f in frames),
            "maximumBindRotationError": max(f["rotation"] for f in frames),
            "bindFrames": frames, "meshes": meshes, "modelSources": left_rig.sources + right_rig.sources}


def verdict(report, tolerances):
    failures = []
    if report["missingNodes"] or report["addedNodes"] or report["kindChanges"] or report["parentChanges"]:
        failures.append("structure")
    if report["header"]["supermodel"][0].lower() != report["header"]["supermodel"][1].lower():
        failures.append("supermodel")
    if report["maximumBindTranslationError"] > tolerances["bindTranslation"] or \
            report["maximumBindRotationError"] > tolerances["bindRotation"]:
        failures.append("bind frames")
    for mesh in report["meshes"]:
        checks = [("maximumPositionError", "position"), ("maximumUvError", "uv"),
                  ("maximumWeightError", "weight")]
        for field, key in checks:
            if field in mesh and mesh[field] > tolerances[key]:
                failures.append(f"{mesh['node']}: {key}")
        if mesh.get("faces", [0, 0])[0] != mesh.get("faces", [0, 0])[1]:
            failures.append(f"{mesh['node']}: face count")
        if mesh.get("smoothingEdgeMismatches", 0) > tolerances.get("smoothingEdges", 0):
            failures.append(f"{mesh['node']}: smoothing edges")
        if mesh.get("maximumFaceCentroidError", 0) > tolerances["position"] or \
                mesh.get("maximumReferenceFaceGap", 0) > tolerances["position"] or \
                mesh.get("maximumCornerPositionError", 0) > tolerances["position"]:
            failures.append(f"{mesh['node']}: face pairing")
        if len(set(mesh.get("uvPresent", [True, True]))) > 1:
            failures.append(f"{mesh['node']}: UV presence")
        if str(mesh["bitmap"][0]).lower() != str(mesh["bitmap"][1]).lower():
            failures.append(f"{mesh['node']}: bitmap")
        deformation = mesh.get("sampledDeformation")
        if deformation and deformation["maximumDisplacementError"] > tolerances["deformation"]:
            failures.append(f"{mesh['node']}: deformation")
        if mesh.get("rightMaximumSumDeviation", 0) > tolerances["weightSum"]:
            failures.append(f"{mesh['node']}: weight sum")
    return {"pass": not failures, "failures": failures, "tolerances": tolerances}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", type=Path, required=True, help="Reference ASCII model")
    parser.add_argument("--right", type=Path, required=True, help="Compared ASCII model")
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--chain-model", required=True, help="Stock model whose supermodel chain both use")
    parser.add_argument("--tolerances", type=Path)
    parser.add_argument("--motion-count", type=int, default=9)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    extraction = read(args.extraction)
    inputs = [pin(args.left), pin(args.right), pin(args.extraction)]
    if args.tolerances:
        inputs.append(pin(args.tolerances))
    chain = lbs.chain_for(args.extraction, args.chain_model)
    # A stock robe's chain starts with itself; a candidate inherits from the body model directly.
    tail = chain if args.chain_model.lower() == extraction["prefix"] else chain[1:]
    left_chain = [Path(args.left).stem.lower(), *tail]
    right_chain = [Path(args.right).stem.lower(), *tail]
    report = compare(args.left, args.right, left_chain, right_chain, extraction["asciiDirectory"], args.motion_count)
    for source in report.pop("modelSources"):  # both rigs read the same stock chain; pin each file once
        if source["path"] not in {i["path"] for i in inputs}:
            inputs.append(source)
    if args.tolerances:
        tolerance_file = read(args.tolerances)
        require(tolerance_file["kind"] == "srn-robe-control-tolerances", "Frozen control tolerances required")
        report["verdict"] = verdict(report, tolerance_file["tolerances"])
    verify_pins(inputs)
    print(write_fresh(args.output, {"schemaVersion": 1, "kind": "srn-robe-model-comparison", "createdUtc": utc(),
                                    "inputs": inputs, **report, **FLAGS})["sha256"])


if __name__ == "__main__":
    main()
