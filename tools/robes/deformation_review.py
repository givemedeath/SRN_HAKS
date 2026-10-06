"""Sample actual weighted skin deformation of a candidate and a stock donor over the motion matrix.

The candidate and donor skin nodes are linear-blend skinned with bone frames
sampled from the stock animation chain; the stock body parts are posed rigidly
by the same frames. Per sample it measures edge stretch/compression, triangle
collapse and outer-surface body penetration, and saves standing plus the
worst sample per motion family for matched renders. Diagnostics flag problems;
they never approve appearance, and none of this is client evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

import lbs
import mdl_ascii
from robe_common import FLAGS, pin, read, require, sha, utc, verify_pins, write_fresh
from stock_body import Body, closest_on_triangles

FLAG = {"stretch": 1.5, "compression": 0.6, "penetration": 0.02, "collapse": 0.25}
MINIMUM_EDGE, MINIMUM_AREA = 0.003, 4e-6  # sub-millimetre decimation slivers make ratios meaningless


def skin_nodes(rig):
    nodes = []
    for node in rig.model.nodes:
        if node.kind != "skin":
            continue
        weights, bones = mdl_ascii.skin_matrix(node)
        faces = np.asarray(node.arrays["faces"])[:, :3]
        edges = np.unique(np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1), axis=0)
        nodes.append({"node": node, "weights": weights, "bones": bones, "faces": faces, "edges": edges,
                      "rest": lbs.bind_world(rig, node)})
    return nodes


def pose(rig, nodes, frames):
    return [lbs.skin(rig, n["node"], frames, n["weights"], n["bones"]) for n in nodes]


def areas(verts, faces):
    return np.linalg.norm(np.cross(verts[faces[:, 1]] - verts[faces[:, 0]], verts[faces[:, 2]] - verts[faces[:, 0]]), axis=1) / 2


def merged(parts, faces):
    out_v, out_f, offset = [], [], 0
    for verts, f in zip(parts, faces):
        out_v.append(verts)
        out_f.append(f + offset)
        offset += len(verts)
    return np.vstack(out_v), np.vstack(out_f)


def penetration(points, body_verts, body_faces):
    if not len(points):
        return {"inside": 0, "deepest": 0.0, "fraction": 0.0}
    _, gap, _, side = closest_on_triangles(points, body_verts, body_faces)
    signed = side * gap
    return {"inside": int((signed < 0).sum()), "deepest": float(max(0.0, -signed.min())),
            "fraction": float((signed < 0).mean()), "flagged": int((signed < -FLAG["penetration"]).sum())}


def donor_cache_key(donor, body, samples):
    """Identity of the stock-donor baseline: donor and chain bytes, body parts, samples and the computing code."""
    files = sorted({str(donor.path)} | {str(Path(body.directory) / (name + ".mdl")) for name in donor.chain} |
                   {str(Path(body.directory) / f"{body.prefix}_{part}001.mdl") for part in body.parts})
    code = [Path(__file__), Path(lbs.__file__), Path(mdl_ascii.__file__), Path(sys.modules[Body.__module__].__file__)]
    material = {"files": {Path(p).name: sha(p) for p in files}, "code": {p.name: sha(p) for p in code},
                "samples": [[s["clip"], s["time"]] for s in samples], "parts": sorted(body.parts)}
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()


def donor_baseline(donor, donor_nodes, body_rig, body, samples, cache):
    """Posed donor geometry and penetration per sample, reused from `cache` when its key matches."""
    key = donor_cache_key(donor, body, samples)
    stored = Path(cache) / (key + ".npz") if cache else None
    if stored and stored.is_file():
        data = np.load(stored)
        return key, True, list(data["posed"]), data["faces"], json.loads(str(data["penetration"]))
    posed_all, rows = [], []
    for sample in samples:
        posed = np.vstack(pose(donor, donor_nodes, donor.frames(sample["clip"], sample["time"])))
        body_verts, body_faces, _ = body.posed(body_rig.frames(sample["clip"], sample["time"]))
        posed_all.append(posed)
        rows.append(penetration(posed, body_verts, body_faces))
    faces = merged([np.zeros((len(n["rest"]), 3)) for n in donor_nodes], [n["faces"] for n in donor_nodes])[1]
    if stored:
        stored.parent.mkdir(parents=True, exist_ok=True)
        temporary = stored.with_name(key + ".partial.npz")
        np.savez_compressed(temporary, posed=np.stack(posed_all), faces=faces, penetration=json.dumps(rows))
        temporary.replace(stored)
    return key, False, posed_all, faces, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--node-vertices", type=Path, required=True)
    parser.add_argument("--fit-arrays", type=Path, required=True)
    parser.add_argument("--donor", required=True)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--samples-per-clip", type=int, default=5)
    parser.add_argument("--penetration-stride", type=int, default=4)
    parser.add_argument("--donor-cache", type=Path, help="Folder reusing the stock-donor baseline across candidates")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    require(not output.exists(), "Fresh review directory required")
    output.mkdir(parents=True)
    extraction, config = read(args.extraction), read(args.config)
    inputs = [pin(args.candidate), pin(args.node_vertices), pin(args.fit_arrays), pin(args.extraction), pin(args.config)]
    ascii_dir = Path(extraction["asciiDirectory"])
    chain = extraction["bodyChain"]
    candidate = lbs.Rig(args.candidate, [Path(args.candidate).stem.lower(), *chain], ascii_dir)
    donor = lbs.Rig(ascii_dir / (args.donor + ".mdl"), lbs.chain_for(args.extraction, args.donor), ascii_dir)
    body_rig = lbs.Rig(ascii_dir / (chain[0] + ".mdl"), chain, ascii_dir)
    body = Body(ascii_dir, chain[0], parts=config["fit"]["bodyParts"] + ["head"])
    nodes, donor_nodes = skin_nodes(candidate), skin_nodes(donor)
    mapping = np.load(args.node_vertices)
    visible = np.load(args.fit_arrays)["visible"]
    outer = [visible[mapping[n["node"].name]] for n in nodes]
    rest_lengths = [np.linalg.norm(n["rest"][n["edges"][:, 0]] - n["rest"][n["edges"][:, 1]], axis=1) for n in nodes]
    rest_areas = [areas(n["rest"], n["faces"]) for n in nodes]
    samples = lbs.motion_samples(candidate, count=args.samples_per_clip)
    donor_key, donor_reused, donor_posed_all, donor_faces, donor_rows = donor_baseline(
        donor, donor_nodes, body_rig, body, samples, args.donor_cache)
    rows, saved = [], {}
    for index, sample in enumerate(samples):
        frames = candidate.frames(sample["clip"], sample["time"])
        posed = pose(candidate, nodes, frames)
        body_frames = body_rig.frames(sample["clip"], sample["time"])
        body_verts, body_faces, _ = body.posed(body_frames)
        ratios = np.concatenate([(np.linalg.norm(p[n["edges"][:, 0]] - p[n["edges"][:, 1]], axis=1) / np.maximum(r, 1e-9))[r >= MINIMUM_EDGE]
                                 for p, n, r in zip(posed, nodes, rest_lengths)])
        area_ratio = np.concatenate([areas(p, n["faces"]) / np.maximum(a, 1e-12)
                                     for p, n, a in zip(posed, nodes, rest_areas)])
        valid_area = np.concatenate([a >= MINIMUM_AREA for a in rest_areas])
        outer_points = np.vstack([p[o] for p, o in zip(posed, outer)])[::args.penetration_stride]
        row = {**sample, "index": index,
               "stretch": {"maximum": float(ratios.max()), "p999": float(np.percentile(ratios, 99.9)),
                           "flagged": int((ratios > FLAG["stretch"]).sum())},
               "compression": {"minimum": float(ratios.min()), "p001": float(np.percentile(ratios, 0.1)),
                               "flagged": int((ratios < FLAG["compression"]).sum())},
               "collapse": {"flagged": int(((area_ratio < FLAG["collapse"]) & valid_area).sum())},
               "penetration": penetration(outer_points, body_verts, body_faces),
               "donorPenetration": donor_rows[index]}
        rows.append(row)
        candidate_mesh = merged(posed, [n["faces"] for n in nodes])
        saved[index] = (candidate_mesh, (donor_posed_all[index], donor_faces), (body_verts, body_faces))
        if index % 10 == 0:
            print({"sample": index, "of": len(samples), "clip": sample["clip"]}, flush=True)
    families = {}
    for row in rows:
        score = row["penetration"]["deepest"] + max(0.0, row["stretch"]["maximum"] - 1) * 0.05
        best = families.get(row["family"])
        if best is None or score > best[0]:
            families[row["family"]] = (score, row["index"])
    selected = sorted({0, *[index for _, index in families.values()],
                       next((r["index"] for r in rows if r["clip"] == "pause1"), 0)})
    geometry = output / "geometry"
    geometry.mkdir()
    for index in selected:
        (cv, cf), (dv, df), (bv, bf) = saved[index]
        np.savez_compressed(geometry / f"s{index:03d}-candidate.npz", verts=cv, faces=cf)
        np.savez_compressed(geometry / f"s{index:03d}-donor.npz", verts=dv, faces=df)
        np.savez_compressed(geometry / f"s{index:03d}-body.npz", verts=bv, faces=bf)
    verify_pins(inputs)
    worst = {name: {"sample": index, "clip": rows[index]["clip"], "time": rows[index]["time"],
                    "penetrationDeepest": rows[index]["penetration"]["deepest"],
                    "donorPenetrationDeepest": rows[index]["donorPenetration"]["deepest"],
                    "stretchMaximum": rows[index]["stretch"]["maximum"],
                    "compressionMinimum": rows[index]["compression"]["minimum"]}
             for name, (_, index) in families.items()}
    report = {"schemaVersion": 1, "kind": "srn-robe-deformation-review", "createdUtc": utc(), "inputs": inputs,
              "candidate": Path(args.candidate).stem, "donor": args.donor, "bodyChain": chain,
              "donorBaseline": {"key": donor_key, "reusedFromCache": donor_reused,
                                "cache": str(Path(args.donor_cache).resolve()) if args.donor_cache else None},
              "method": "numpy linear blend skinning with rig_pose_audit frames; stock parts posed rigidly",
              "flagThresholds": FLAG, "measuredEdgesAtLeast": MINIMUM_EDGE, "measuredAreasAtLeast": MINIMUM_AREA, "samples": rows, "worstByFamily": worst, "savedSamples": selected,
              "geometry": [pin(p) for p in sorted(geometry.iterdir())], "clientEvidence": False, **FLAGS}
    print(write_fresh(output / "review.json", report)["sha256"])


if __name__ == "__main__":
    main()
