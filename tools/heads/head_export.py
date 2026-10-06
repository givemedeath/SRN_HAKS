"""Dedicated rigid-head GLB/PLT/NWN exporter, independent of body staging."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import re

import numpy as np

from head_workflow import MAX_TRIANGLES, TEXTURE_SIZE, fit_similarity, model_name, pin, read, require, sha, validate_target, verify_pins, write_fresh

BASIS = np.array([[1., 0, 0, 0], [0, 0, -1., 0], [0, 1., 0, 0], [0, 0, 0, 1.]])
COMPONENTS = {5121: np.dtype("u1"), 5123: np.dtype("<u2"), 5125: np.dtype("<u4"), 5126: np.dtype("<f4")}
WIDTHS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def load_glb(path):
    data = Path(path).read_bytes()
    require(len(data) >= 20, "Truncated GLB")
    magic, version, length = struct.unpack_from("<III", data)
    require(magic == 0x46546C67 and version == 2 and length == len(data), "Invalid GLB header")
    chunks, offset = {}, 12
    while offset < len(data):
        require(offset + 8 <= len(data), "Truncated chunk header")
        size, kind = struct.unpack_from("<II", data, offset)
        offset += 8
        require(offset + size <= len(data) and kind not in chunks, "Invalid or duplicate GLB chunk")
        chunks[kind] = data[offset:offset+size]
        offset += size
    require(0x4E4F534A in chunks and 0x004E4942 in chunks, "Embedded JSON/BIN required")
    document = json.loads(chunks[0x4E4F534A].decode("utf-8"))
    require(not document.get("skins") and not document.get("animations"), "Rigid unrigged donor required")
    buffers = document["buffers"]
    require(len(buffers) == 1 and "uri" not in buffers[0] and
            buffers[0]["byteLength"] <= len(chunks[0x004E4942]), "External or truncated buffers rejected")
    return document, chunks[0x004E4942]


def accessor(document, binary, index):
    item = document["accessors"][index]
    require("sparse" not in item and not item.get("normalized") and item["count"] > 0,
            "Unsupported sparse/normalized/empty accessor")
    dtype = COMPONENTS[item["componentType"]]
    width = WIDTHS[item["type"]]
    view = document["bufferViews"][item["bufferView"]]
    require(view.get("buffer", 0) == 0, "External buffer view")
    offset = view.get("byteOffset", 0) + item.get("byteOffset", 0)
    stride = view.get("byteStride", dtype.itemsize * width)
    end = offset + (item["count"] - 1) * stride + dtype.itemsize * width
    require(stride >= dtype.itemsize * width and end <= view.get("byteOffset", 0) + view["byteLength"]
            and end <= document["buffers"][0]["byteLength"] and end <= len(binary), "Accessor escapes buffer")
    result = np.ndarray((item["count"], width), dtype=dtype, buffer=binary,
                        offset=offset, strides=(stride, dtype.itemsize)).copy()
    require(np.isfinite(result).all(), "Non-finite mesh attribute")
    return result


def node_matrix(node):
    if "matrix" in node:
        require(not any(key in node for key in ("translation", "rotation", "scale")), "Matrix/TRS conflict")
        matrix = np.asarray(node["matrix"], dtype=float).reshape(4, 4, order="F")
    else:
        x, y, z, w = node.get("rotation", [0, 0, 0, 1])
        require(abs(x*x+y*y+z*z+w*w-1) < 1e-5, "Invalid node quaternion")
        rotation = np.array([
            [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
            [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
            [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)],
        ])
        matrix = np.eye(4)
        matrix[:3, :3] = rotation @ np.diag(node.get("scale", [1, 1, 1]))
        matrix[:3, 3] = node.get("translation", [0, 0, 0])
    require(np.isfinite(matrix).all() and np.allclose(matrix[3], [0, 0, 0, 1]), "Invalid node matrix")
    gram = matrix[:3, :3].T @ matrix[:3, :3]
    require(np.linalg.det(matrix[:3, :3]) > 0 and np.allclose(gram, np.eye(3)*gram[0, 0], atol=1e-7),
            "Node reflection/stretch rejected")
    return matrix


def triangles(path, local_transform, *, maximum=MAX_TRIANGLES, require_uv=True):
    document, binary = load_glb(path)
    parts, visited = [], set()
    roots = document["scenes"][document.get("scene", 0)]["nodes"]
    transform = np.asarray(local_transform, dtype=float)
    require(transform.shape == (4, 4) and np.isfinite(transform).all()
            and np.allclose(transform[3], [0, 0, 0, 1]), "Invalid selected local transform")
    gram = transform[:3, :3].T @ transform[:3, :3]
    require(np.linalg.det(transform[:3, :3]) > 0
            and np.allclose(gram, np.eye(3)*gram[0, 0], atol=1e-7), "Selected transform stretches or reflects")

    def visit(index, parent):
        require(index not in visited, "GLB cycle or multiply-parented mesh")
        visited.add(index)
        node = document["nodes"][index]
        require("skin" not in node, "Skinned head donor rejected")
        world = parent @ node_matrix(node)
        if "mesh" in node:
            matrix = transform @ BASIS @ world
            scale = np.linalg.norm(matrix[:3, 0])
            for primitive in document["meshes"][node["mesh"]]["primitives"]:
                require(primitive.get("mode", 4) == 4 and not primitive.get("targets")
                        and not primitive.get("extensions"), "Only plain triangle primitives supported")
                attrs = primitive["attributes"]
                require({"POSITION", "NORMAL"} <= set(attrs), "P/N attributes required")
                require(not require_uv or "TEXCOORD_0" in attrs, "UV attribute required")
                p, n = [accessor(document, binary, attrs[key]) for key in ("POSITION", "NORMAL")]
                uv = accessor(document, binary, attrs["TEXCOORD_0"]) if "TEXCOORD_0" in attrs else np.zeros((len(p), 2))
                require(p.shape == n.shape and p.shape[1] == 3 and uv.shape == (len(p), 2), "Attribute shape mismatch")
                indices = (accessor(document, binary, primitive["indices"]).ravel() if "indices" in primitive
                           else np.arange(len(p)))
                require(np.issubdtype(indices.dtype, np.integer) and len(indices) % 3 == 0
                        and indices.min() >= 0 and indices.max() < len(p), "Invalid triangle indices")
                faces = indices.reshape(-1, 3)
                points = (np.c_[p, np.ones(len(p))] @ matrix.T)[:, :3]
                normals = n @ (matrix[:3, :3] / scale).T
                require(np.allclose(np.linalg.norm(normals, axis=1), 1, atol=2e-3), "Invalid authored normals")
                require(np.all((uv >= 0) & (uv <= 1)), "Head atlas must use non-wrapping UVs")
                # glTF images use top-left UV coordinates; NWN uses bottom-left.
                tex = np.c_[uv[:, 0], 1 - uv[:, 1]]
                parts.append((points[faces], normals[faces], tex[faces]))
        for child in node.get("children", []):
            visit(child, world)

    for root in roots:
        visit(root, np.eye(4))
    require(bool(parts), "No visible head triangles")
    p, n, uv = [np.concatenate([part[index] for part in parts]) for index in range(3)]
    require(0 < len(p) <= maximum, "Head triangle budget exceeded")
    require(np.all(np.linalg.norm(np.cross(p[:, 1]-p[:, 0], p[:, 2]-p[:, 0]), axis=1) > 1e-14),
            "Degenerate runtime triangles")
    return p, n, uv


def plt_bytes(shades, layers):
    require(shades.shape == layers.shape == (TEXTURE_SIZE, TEXTURE_SIZE), "Runtime palette must be 1024 square")
    require(shades.dtype == layers.dtype == np.uint8 and np.all(np.isin(layers, [0, 1])),
            "Explicit skin layer0 / hair layer1 masks required")
    pixels = np.stack([shades, layers], axis=-1)[::-1].copy()
    return b"PLT V1  " + struct.pack("<IIII", 10, 0, TEXTURE_SIZE, TEXTURE_SIZE) + pixels.tobytes()


def ascii_model(model, points, normals, uv, groups):
    lines = [f"newmodel {model}", f"setsupermodel {model} NULL", "classification CHARACTER",
             "setanimationscale 1", f"beginmodelgeom {model}", f"node dummy {model}",
             "  parent NULL", "endnode"]
    assigned = []
    for number, group in enumerate(groups):
        ids = np.asarray(group["triangles"])
        require(np.issubdtype(ids.dtype, np.integer), "Material face IDs must be integers")
        require(ids.ndim == 1 and len(ids) > 0 and np.all(ids >= 0) and np.all(ids < len(points)),
                "Invalid material face selection")
        assigned.extend(ids.tolist())
        material = model if group["kind"] == "palette" else model + group["suffix"]
        require(re.fullmatch(r"[a-z0-9_]{1,14}", material) and group["kind"] in ("palette", "fixed"),
                "Invalid material group or dependency resref")
        p, n, tex = points[ids].reshape(-1, 3), normals[ids].reshape(-1, 3), uv[ids].reshape(-1, 2)
        lines += [f"node trimesh {model}p{number}", f"  parent {model}", "  position 0 0 0",
                  "  orientation 0 0 0 0", "  ambient 1 1 1", "  diffuse 1 1 1",
                  "  specular 0 0 0", "  shininess 0", f"  bitmap {material}",
                  f"  materialname {material}", "  render 1", "  shadow 1"]
        for label, values in (("verts", p), ("normals", n), ("tverts", np.c_[tex, np.zeros(len(tex))])):
            lines.append(f"  {label} {len(values)}")
            lines.extend("    " + " ".join(format(float(v), ".17g") for v in row) for row in values)
        lines.append(f"  faces {len(ids)}")
        for face in range(len(ids)):
            a, b, c = face*3, face*3+1, face*3+2
            lines.append(f"    {a} {b} {c} 1 {a} {b} {c} 1")
        lines.append("endnode")
    require(len(groups) <= 3 and sorted(assigned) == list(range(len(points))),
            "Every triangle must belong to exactly one of at most three material groups")
    require(sum(group["kind"] == "palette" for group in groups) == 1, "Exactly one palette group required")
    materials = [model if g["kind"] == "palette" else model+g["suffix"] for g in groups]
    require(len(set(materials)) == len(materials), "Duplicate material group name")
    lines += [f"endmodelgeom {model}", f"donemodel {model}"]
    return "\n".join(lines) + "\n"


def export(config_path, output):
    from PIL import Image
    config = read(config_path)
    require(config["kind"] == "srn-head-export", "Explicit head export configuration required")
    verify_pins(config["inputs"])
    target = validate_target(read(config["target"]["path"]))
    verify_pins([config["target"], config["source"], config["fit"]])
    fit = read(config["fit"]["path"])
    require(fit["source"] == config["source"] and fit["target"] == config["target"], "Fit belongs to another donor/body")
    if config.get('geometryPolicy')=='neckless-cap-only':
        verify_pins([config['neckCorrection']]);closure=read(config['neckCorrection']['path'])
        require(closure['kind']=='srn-head-cap-only-closure' and closure['output']==config['source']
                and closure['passed'] is True and closure['originalSurfacePreserved'] is True
                and closure['trimApplied'] is False and closure['taperApplied'] is False,
                'Neckless export requires a matching cap-only proof')
    measured = fit_similarity(fit["sourceLandmarks"], fit["targetLandmarks"], target["landmarkTolerance"])
    require(np.allclose(fit["localMatrix"], measured["matrix"], atol=1e-9), "Export fit differs from measured landmarks")
    model = model_name(target["prefix"], config["slot"])
    require(config["normalStrength"] == 1, "Selected normal strength must remain one")
    points, normals, uv = triangles(config["source"]["path"], fit["localMatrix"])
    bounds = np.array([points.min((0, 1)), points.max((0, 1))])
    envelope = np.asarray(target["cranialEnvelope"])
    inside=((points>=envelope[0])&(points<=envelope[1])).all(2)
    if not inside.all() and 'neckConnectorEnvelope' in target:
        verify_pins([config['neckCorrection']]);correction=read(config['neckCorrection']['path'])
        require(correction['output']==config['source'] and correction.get('taperDepthMetres',0)>0,
                'Neck allowance requires the exact separately versioned taper')
        connector=np.asarray(target['neckConnectorEnvelope'])
        authorized=np.zeros(len(points),dtype=bool);authorized[correction['connectorFaceIds']]=True
        inside|=authorized[:,None]&((points>=connector[0])&(points<=connector[1])).all(2)
    require(inside.all(),"Head silhouette exceeds approved target envelope")
    with Image.open(config['shades']) as value:
        require(value.mode=='L','Explicit byte shade mask required'); shades=np.asarray(value)
    with Image.open(config['layers']) as value:
        require(value.mode=='L','Explicit byte layer mask required'); layers=np.asarray(value)
    payload = plt_bytes(shades, layers)
    text = ascii_model(model, points, normals, uv, config["groups"])
    consumed = [config["shades"], config["layers"]]
    consumed += [group[key] for group in config["groups"] for key in ("normal", "roughness", "color") if key in group]
    declared = {Path(item["path"]).resolve() for item in config["inputs"]}
    require({Path(p).resolve() for p in consumed} <= declared, "Material input omitted from frozen declaration")
    maps = {}
    for number, group in enumerate(config["groups"]):
        metallic = group.get("metallicness", 0)
        require(type(metallic) in (int, float) and 0 <= metallic <= 1, "Explicit metallicness required")
        for key in (["color"] if group["kind"] == "fixed" else []) + ["normal", "roughness"]:
            with Image.open(group[key]) as original:
                require(original.size == (TEXTURE_SIZE, TEXTURE_SIZE), "Explicit runtime-size maps required")
                maps[number, key] = original.convert("RGB")
    verify_pins(config["inputs"])
    destination = Path(output)
    require(not destination.exists(), "Fresh export directory required")
    resources = destination / "resources"
    resources.mkdir(parents=True)
    (destination / "ascii").mkdir()
    (destination / "ascii" / (model+".mdl")).write_text(text, encoding="ascii")
    (resources / (model+".plt")).write_bytes(payload)
    for number, group in enumerate(config["groups"]):
        material = model if group["kind"] == "palette" else model + group["suffix"]
        if group["kind"] == "fixed":
            color = maps[number, "color"]
            color.save(resources / (material+".tga"))
        for name, key in (("n", "normal"), ("r", "roughness")):
            image = maps[number, key]
            require(len(material+name) <= 16, "Material dependency resref too long")
            image.save(resources / (material+name+".tga"))
        metallic = group.get("metallicness", 0)
        require(type(metallic) in (int, float) and 0 <= metallic <= 1, "Explicit metallicness required")
        mtr = ("renderhint NormalTangents\n" + f"texture1 {material}n\ntexture3 {material}r\n"
               + f"parameter float Roughness 0\nparameter float Metallicness {metallic}\n")
        (resources / (material+".mtr")).write_text(mtr, encoding="ascii")
    verify_pins(config["inputs"])
    write_fresh(destination / "export.json", {
        "kind": "srn-head-export-result", "configuration": pin(config_path), "source": config["source"],
        "target": config["target"], "fit": config["fit"], "triangles": len(points),
        "localBounds": bounds.tolist(), "textureSize": TEXTURE_SIZE,
        "paletteLayers": sorted(int(value) for value in np.unique(layers)),
        "resources": [pin(path) for path in sorted(resources.iterdir())],
        "ascii": pin(destination / "ascii" / (model+".mdl")),
        "nativeValidated": False, "clientValidated": False, "productionAccepted": False,
    })
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({"export": str(export(args.config, args.output))}))
