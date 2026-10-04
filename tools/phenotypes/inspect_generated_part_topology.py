"""Read-only linear/vectorized topology and depth-ray diagnosis of generated GLBs.

No geometry, topology, normals or image data is changed. The exact weld used to
interpret glTF UV seams exists only in diagnostic arrays, never in source files.
Supports the isolated single-mesh, identity-node GLBs emitted by this workflow.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import time

import numpy as np


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    data = path.read_bytes()
    magic, version, length = struct.unpack_from("<4sII", data)
    if magic != b"glTF" or version != 2 or length != len(data):
        raise RuntimeError("Expected complete GLB 2 source")
    json_length, kind = struct.unpack_from("<II", data, 12)
    if kind != 0x4E4F534A:
        raise RuntimeError("Expected GLB JSON first")
    document = json.loads(data[20:20 + json_length])
    start = 20 + json_length
    bin_length, bin_kind = struct.unpack_from("<II", data, start)
    if bin_kind != 0x004E4942:
        raise RuntimeError("Expected embedded BIN")
    binary = memoryview(data)[start + 8:start + 8 + bin_length]
    nodes = document.get("nodes", [])
    if (len(nodes) != 1 or nodes[0].get('mesh') != 0
            or set(nodes[0])-{'mesh','name'}
            or ('name' in nodes[0] and not isinstance(nodes[0]['name'],str))
            or len(document["meshes"]) != 1):
        raise RuntimeError("This diagnostic expects one identity-node mesh")
    primitives = document["meshes"][0]["primitives"]
    if len(primitives) != 1 or primitives[0].get("mode", 4) != 4:
        raise RuntimeError("Expected one indexed triangle primitive")
    primitive = primitives[0]

    def accessor(index):
        info = document["accessors"][index]
        view = document["bufferViews"][info["bufferView"]]
        if "sparse" in info or info.get("normalized"):
            raise RuntimeError("Unsupported accessor encoding")
        dtype = {5121: "u1", 5123: "<u2", 5125: "<u4", 5126: "<f4"}[info["componentType"]]
        width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[info["type"]]
        packed = np.dtype(dtype).itemsize * width
        if view.get("byteStride", packed) != packed:
            raise RuntimeError("Unsupported strided source")
        offset = view.get("byteOffset", 0) + info.get("byteOffset", 0)
        return np.frombuffer(binary, dtype=dtype, count=info["count"] * width, offset=offset).reshape(-1, width).copy()

    positions = accessor(primitive["attributes"]["POSITION"])
    triangles = accessor(primitive["indices"]).reshape(-1, 3).astype(np.int64)
    normals = accessor(primitive["attributes"]["NORMAL"]) if "NORMAL" in primitive["attributes"] else None
    return positions, triangles, normals


def canonical_triangle_hash(triangles):
    # Rotate each oriented triangle to its least index and sort triangle rows.
    # Ordering and UV vertex splits are irrelevant; reversed winding is not.
    offsets = np.argmin(triangles, axis=1)
    canonical = np.take_along_axis(triangles, (np.arange(3)[None, :] + offsets[:, None]) % 3, axis=1)
    order = np.lexsort((canonical[:, 2], canonical[:, 1], canonical[:, 0]))
    return hashlib.sha256(canonical[order].astype("<u4").tobytes()).hexdigest()


def inspect(path, ray_samples=None, vertical_samples=None):
    begun = time.time()
    before = digest(path)
    source_positions, source_triangles, source_normals = load(path)
    if not np.isfinite(source_positions).all() or (source_normals is not None and not np.isfinite(source_normals).all()):
        raise RuntimeError('Nonfinite source positions/normals cannot support topology/ray proof')
    positions, inverse = np.unique(source_positions, axis=0, return_inverse=True)
    triangles = inverse[source_triangles]
    positions = positions.astype(np.float64)
    v0, v1, v2 = (positions[triangles[:, index]] for index in range(3))
    cross = np.cross(v1 - v0, v2 - v0)
    areas = np.linalg.norm(cross, axis=1) * .5
    volume_terms = np.einsum("ij,ij->i", v0, cross) / 6
    signed_volume = float(volume_terms.sum(dtype=np.float64))
    vertex_count = len(positions)
    directed = np.concatenate((triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]))
    lows = directed.min(axis=1)
    highs = directed.max(axis=1)
    keys = lows * vertex_count + highs
    unique, edge_inverse, counts = np.unique(keys, return_inverse=True, return_counts=True)
    signs = np.where(directed[:, 0] < directed[:, 1], 1., -1.)
    winding_sums = np.bincount(edge_inverse, weights=signs, minlength=len(unique))
    boundary = unique[counts == 1]
    nonmanifold = unique[counts > 2]
    bad_winding = unique[(counts == 2) & (winding_sums != 0)]
    # The raw decoder master can contain millions of faces. These temporary
    # full edge arrays are no longer needed during union/ray analysis.
    del directed, lows, highs, keys, edge_inverse, signs, winding_sums
    # Bundled workspace Python has NumPy but not SciPy. Union-by-rank with
    # path compression is near-linear in edges and avoids adjacency searches
    # or quadratic triangle matching on the detailed master.
    parents = list(range(vertex_count))
    ranks = [0] * vertex_count

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for encoded in unique:
        first, second = divmod(int(encoded), vertex_count)
        first, second = find(first), find(second)
        if first == second:
            continue
        if ranks[first] < ranks[second]:
            first, second = second, first
        parents[second] = first
        if ranks[first] == ranks[second]:
            ranks[first] += 1
    roots = np.fromiter((find(index) for index in range(vertex_count)), dtype=np.int64, count=vertex_count)
    component_roots, labels = np.unique(roots, return_inverse=True)
    components = len(component_roots)
    bounds_minimum, bounds_maximum = positions.min(axis=0), positions.max(axis=0)
    box_volume = float(np.prod(bounds_maximum - bounds_minimum))
    component_faces = np.bincount(labels[triangles[:, 0]], minlength=components)
    component_volume = np.bincount(labels[triangles[:, 0]], weights=volume_terms, minlength=components)
    component_vertices = np.bincount(labels, minlength=components)
    if ray_samples is None:
        span = bounds_maximum-bounds_minimum
        ray_samples = [(float(bounds_minimum[0]+fx*span[0]), float(bounds_minimum[1]+fy*span[1]))
                       for fy in (.15, .5037, .85) for fx in (.237, .5037, .769)]
        if vertical_samples is None:
            vertical_samples = [(float(bounds_minimum[0]+fx*span[0]), float(bounds_minimum[2]+fz*span[2]))
                                for fz in (.23, .5037, .77) for fx in (.237, .5037, .769)]
    if vertical_samples is None:
        vertical_samples = [(x,z) for x in (0.0037,.035,-.035) for z in (-.10,-.07,-.03,.015,.06)]
    rays = []
    # Generator GLBs are Y-up; ray along Z at X/Y samples. Four alternating
    # intersections with close exterior/interior pairs distinguish a thin
    # hollow surface from an ordinary two-intersection solid at that sample.
    a = v0[:, :2]
    b = v1[:, :2] - a
    c = v2[:, :2] - a
    denominator = b[:, 0] * c[:, 1] - b[:, 1] * c[:, 0]
    valid = np.abs(denominator) > 1e-15
    face_normals = np.divide(cross, (2 * areas)[:, None], out=np.zeros_like(cross), where=areas[:, None] > 0)
    for x, y in ray_samples:
        r = np.asarray([x, y]) - a
        u = np.divide(r[:, 0] * c[:, 1] - r[:, 1] * c[:, 0], denominator,
                      out=np.zeros_like(denominator), where=valid)
        w = np.divide(b[:, 0] * r[:, 1] - b[:, 1] * r[:, 0], denominator,
                      out=np.zeros_like(denominator), where=valid)
        hit = np.flatnonzero(valid & (u >= -1e-9) & (w >= -1e-9) & (u + w <= 1 + 1e-9))
        z = v0[hit, 2] + u[hit] * (v1[hit, 2] - v0[hit, 2]) + w[hit] * (v2[hit, 2] - v0[hit, 2])
        ordering = np.argsort(z)
        unique_hits = []
        for index in ordering:
            if unique_hits and abs(float(z[index]) - unique_hits[-1]["z"]) < 1e-7:
                unique_hits[-1]["triangleCountAtSameHit"] += 1
                continue
            face = int(hit[index])
            vertex_normal = None
            if source_normals is not None:
                normal = ((1 - u[face] - w[face]) * source_normals[source_triangles[face, 0]]
                          + u[face] * source_normals[source_triangles[face, 1]]
                          + w[face] * source_normals[source_triangles[face, 2]])
                norm = np.linalg.norm(normal)
                vertex_normal = (normal / norm).tolist() if norm else normal.tolist()
            unique_hits.append({"z": float(z[index]), "faceIndex": face,
                                "geometricNormal": face_normals[face].tolist(),
                                "interpolatedExportedNormal": vertex_normal,
                                "triangleCountAtSameHit": 1})
        rays.append({"x": x, "y": y, "hits": unique_hits,
                     "consecutiveHitDistances": [h2["z"] - h1["z"] for h1, h2 in zip(unique_hits, unique_hits[1:])]})

    vertical_rays = []
    a = v0[:, [0, 2]]
    b = v1[:, [0, 2]] - a
    c = v2[:, [0, 2]] - a
    denominator = b[:, 0] * c[:, 1] - b[:, 1] * c[:, 0]
    valid = np.abs(denominator) > 1e-15
    for x, z in vertical_samples:
            r = np.asarray([x, z]) - a
            u = np.divide(r[:, 0] * c[:, 1] - r[:, 1] * c[:, 0], denominator,
                          out=np.zeros_like(denominator), where=valid)
            w = np.divide(b[:, 0] * r[:, 1] - b[:, 1] * r[:, 0], denominator,
                          out=np.zeros_like(denominator), where=valid)
            hit = np.flatnonzero(valid & (u >= -1e-9) & (w >= -1e-9) & (u + w <= 1 + 1e-9))
            y = v0[hit, 1] + u[hit] * (v1[hit, 1] - v0[hit, 1]) + w[hit] * (v2[hit, 1] - v0[hit, 1])
            ordering = np.argsort(y)
            hits = []
            for index in ordering:
                if hits and abs(float(y[index]) - hits[-1]["y"]) < 1e-7:
                    continue
                face = int(hit[index])
                hits.append({"y": float(y[index]), "faceIndex": face,
                             "geometricNormal": face_normals[face].tolist()})
            vertical_rays.append({"x": x, "z": z, "hits": hits,
                                  "consecutiveHitDistances": [h2["y"] - h1["y"] for h1, h2 in zip(hits, hits[1:])]})

    def edges_record(encoded):
        return [{"indices": [int(key // vertex_count), int(key % vertex_count)],
                 "positions": positions[[key // vertex_count, key % vertex_count]].tolist()}
                for key in encoded[:100]]

    if digest(path) != before:
        raise RuntimeError("Source bytes changed during read-only inspection")
    return {"path": str(path.resolve()), "sha256": before, "sourceUnchanged": True,
            "sourceVertexCount": len(source_positions), "exactUniquePositionCount": vertex_count,
            "triangleCount": len(triangles), "zeroAreaTriangleCount": int((areas <= 1e-15).sum()),
            "surfaceArea": float(areas.sum()), "signedVolume": signed_volume,
            "axisAlignedBoxVolume": box_volume, "volumeFractionOfAxisAlignedBox": signed_volume / box_volume,
            "bounds": {"minimum": bounds_minimum.tolist(), "maximum": bounds_maximum.tolist()},
            "boundaryEdgeCount": len(boundary), "nonmanifoldEdgeCount": len(nonmanifold),
            "inconsistentWindingManifoldEdgeCount": len(bad_winding),
            "eulerCharacteristic": int(vertex_count - len(unique) + len(triangles)),
            "componentCountByExactCoordinateEdges": components,
            "components": [{"vertices": int(component_vertices[index]), "faces": int(component_faces[index]),
                            "signedVolume": float(component_volume[index])} for index in range(components)],
            "boundaryEdges": edges_record(boundary), "nonmanifoldEdges": edges_record(nonmanifold),
            "windingMismatchEdges": edges_record(bad_winding),
            "exactPositionSha256": hashlib.sha256(positions.astype("<f4").tobytes()).hexdigest(),
            "orientedTrianglesOnExactPositionsSha256": canonical_triangle_hash(triangles),
            "depthRaySections": rays, "verticalNeckWaistRaySections": vertical_rays,
            "elapsedSeconds": time.time() - begun}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-stages", nargs="+",
                        help="Explicit per-source stage labels, e.g. raw-decoder udf-remesh compact-painted textured")
    parser.add_argument("--ray-policy", choices=("legacy-body", "actual-bounds"), default="legacy-body",
                        help="actual-bounds samples each source's own bounds; legacy-body reproduces earlier torso diagnostics")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError("Use a fresh diagnostic output")
    if args.source_stages is not None and len(args.source_stages) != len(args.sources):
        parser.error("Supply exactly one stage label for each source")
    samples = None if args.ray_policy == "actual-bounds" else [(x, y) for y in (-.36, -.22, 0., .20, .36, .435) for x in (0.0037, .10, -.10)]
    results = [inspect(source.resolve(), samples) for source in args.sources]
    for result, stage in zip(results,args.source_stages or ["unspecified"]*len(results)):
        result["sourceStage"] = stage
    output.mkdir(parents=True)
    script = output / Path(__file__).name
    script.write_bytes(Path(__file__).read_bytes())
    receipt = {"schemaVersion": 1, "readOnly": True, "scriptSha256": digest(script),
               "coordinateFrame": "Actual unmodified GLB positions, X horizontal / Y vertical / Z depth.",
               "weldPolicy": "Exact positions in diagnostic arrays only; no source alteration.",
               "sourceStages": args.source_stages or ["unspecified"]*len(results),
               "rayPolicy": args.ray_policy,
               "limitation": "Read-only topology and sampled ray sections; declared stage labels identify lineage, not geometry acceptance. Unspecified stages do not establish remesh causality.",
               "sourceAlterations": False, "clientAccepted": False, "sources": results}
    (output / "topology-and-depth-sections.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps([{key: result[key] for key in ("path", "triangleCount", "boundaryEdgeCount", "nonmanifoldEdgeCount",
                       "inconsistentWindingManifoldEdgeCount", "componentCountByExactCoordinateEdges", "signedVolume",
                       "volumeFractionOfAxisAlignedBox", "eulerCharacteristic", "elapsedSeconds")} for result in results], indent=2), flush=True)


if __name__ == "__main__":
    main()
