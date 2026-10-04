"""Fresh exact-source-UV cap atlas diagnostic; no geometry or native/client edits."""
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct

import numpy as np
from PIL import Image, ImageDraw

from round_generated_waist_cap import append_accessor, embed_image, write_glb


SLOTS = {
    "color": ("pbrMetallicRoughness", "baseColorTexture"),
    "normal": ("normalTexture",),
    "orm": ("pbrMetallicRoughness", "metallicRoughnessTexture"),
    "ao": ("occlusionTexture",),
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    data = path.read_bytes()
    if struct.unpack_from("<4sII", data) != (b"glTF", 2, len(data)):
        raise ValueError("Complete GLB2 required")
    length, kind = struct.unpack_from("<II", data, 12)
    if kind != 0x4e4f534a:
        raise ValueError("Expected JSON chunk")
    doc = json.loads(data[20:20 + length])
    offset = 20 + length
    length, kind = struct.unpack_from("<II", data, offset)
    if kind != 0x004e4942:
        raise ValueError("Embedded binary required")
    return doc, data[offset + 8:offset + 8 + length]


def accessor(doc, binary, index):
    item = doc["accessors"][index]
    view = doc["bufferViews"][item["bufferView"]]
    width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[item["type"]]
    dtype = np.dtype({5121: "u1", 5123: "<u2", 5125: "<u4", 5126: "<f4"}[item["componentType"]])
    if "sparse" in item or item.get("normalized") or view.get("byteStride", width * dtype.itemsize) != width * dtype.itemsize:
        raise ValueError("Packed unnormalized arrays required")
    return np.frombuffer(binary, dtype=dtype, count=item["count"] * width,
        offset=view.get("byteOffset", 0) + item.get("byteOffset", 0)).reshape(-1, width).copy()


def texture_info(material, key):
    value = material
    for field in SLOTS[key]:
        value = value[field]
    if value.get("texCoord", 0) != 0 or "extensions" in value:
        raise ValueError("Untransformed TEXCOORD_0 textures required")
    return value


def image_array(doc, binary, texture):
    record = doc["images"][doc["textures"][texture]["source"]]
    view = doc["bufferViews"][record["bufferView"]]
    payload = binary[view.get("byteOffset", 0):view.get("byteOffset", 0) + view["byteLength"]]
    image = Image.open(io.BytesIO(payload))
    if image.mode not in ("RGB", "RGBA"):
        raise ValueError("Expected RGB/RGBA atlas")
    return np.asarray(image).copy()


def srgb_linear(value):
    return np.where(value <= .04045, value / 12.92, ((value + .055) / 1.055) ** 2.4)


def linear_srgb(value):
    value = np.maximum(value, 0)
    return np.where(value <= .0031308, value * 12.92, 1.055 * value ** (1 / 2.4) - .055)


def bilinear(image, uv):
    height, width = image.shape[:2]
    pixels = np.asarray(uv, float) * [width, height] - .5
    pixels = np.clip(pixels, 0, [width - 1, height - 1])
    low = np.floor(pixels).astype(int)
    high = np.minimum(low + 1, [width - 1, height - 1])
    weight = pixels - low
    a = image[low[:, 1], low[:, 0]].astype(float)
    b = image[low[:, 1], high[:, 0]].astype(float)
    c = image[high[:, 1], low[:, 0]].astype(float)
    d = image[high[:, 1], high[:, 0]].astype(float)
    wx, wy = weight[:, :1], weight[:, 1:]
    return (a * (1 - wx) + b * wx) * (1 - wy) + (c * (1 - wx) + d * wx) * wy


def tile_image(source, key, width, height):
    values = source.astype(float) / 255
    if key == "color":
        values[:, :, :3] = srgb_linear(values[:, :, :3])
    elif key == "normal":
        values[:, :, :3] = values[:, :, :3] * 2 - 1
    result = np.stack([np.asarray(Image.fromarray(values[:, :, k].astype(np.float32)).resize(
        (width, height), Image.Resampling.LANCZOS)) for k in range(values.shape[2])], axis=2)
    # Preserve endpoints on both chart axes: the lower row is the actual seam.
    target_u = np.linspace(0, 1, width)
    target_v = np.linspace(0, 1, height)
    for row, v in ((0, 0), (height - 1, 1)):
        result[row] = bilinear(values, np.column_stack((target_u, np.full(width, v))))
    for column, u in ((0, 0), (width - 1, 1)):
        result[:, column] = bilinear(values, np.column_stack((np.full(height, u), target_v)))
    if key == "color":
        result[:, :, :3] = linear_srgb(result[:, :, :3])
    elif key == "normal":
        xyz = result[:, :, :3]
        xyz /= np.maximum(np.linalg.norm(xyz, axis=2, keepdims=True), 1e-12)
        result[:, :, :3] = xyz * .5 + .5
    return np.clip(np.rint(result * 255), 0, 255).astype(np.uint8)


def transformed_uv(uv, box, size):
    x0, y0, x1, y1 = box
    return ((np.asarray(uv, float) * [x1 - x0 - 1, y1 - y0 - 1] + [x0 + .5, y0 + .5]) / size).astype("<f4")


def summary(values):
    return {"mean": float(np.mean(values)), "p95": float(np.percentile(values, 95)), "max": float(np.max(values))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--allocation", type=Path, required=True, help="Read-only inspector space.json for this exact source")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    if digest(source) != args.source_sha256:
        raise ValueError("Source hash mismatch")
    if args.output.exists():
        raise ValueError("Fresh output required")
    frozen = {str(p.resolve()): digest(p) for p in [source, args.allocation, Path(__file__), Path(__file__).with_name("round_generated_waist_cap.py")]}
    allocation = json.loads(args.allocation.read_text())
    if allocation["sourceSha256"] != args.source_sha256 or allocation["atlasSize"] != 2048:
        raise ValueError("Allocation must inspect this exact 2K source")
    tested = next(t for t in allocation["rectangularTileTests"] if t["width"] == 128 and t["height"] == 64 and t["twoTilesFound"])
    boxes, allocation_padding = tested["guardedPixelBoxes"], tested["padding"]
    padding, filter_halo = 16, 2
    if allocation_padding < padding + filter_halo:
        raise ValueError("16-pixel written guard plus 2-texel source sampling halo required")
    original_doc, original_bin = load(source)
    doc = copy.deepcopy(original_doc)
    primitives = doc["meshes"][0]["primitives"]
    if len(doc["meshes"]) != 1 or len(primitives) != 3:
        raise ValueError("Expected retained skin + outer cap + inner cap")
    if any(p.get("mode", 4) != 4 for p in primitives):
        raise ValueError("Indexed triangle primitives required")
    materials = [doc["materials"][p["material"]] for p in primitives]
    for material in materials:
        if "extensions" in material or "emissiveTexture" in material:
            raise ValueError("Unsupported additional active material textures")
        for key in SLOTS:
            texture_info(material, key)
    mask = Image.new("L", (2048, 2048))
    draw = ImageDraw.Draw(mask)
    source_uv = accessor(doc, original_bin, primitives[0]["attributes"]["TEXCOORD_0"])
    source_faces = accessor(doc, original_bin, primitives[0]["indices"]).reshape(-1, 3)
    corners = source_uv[source_faces]
    upper_samples = np.vstack([source_uv[np.unique(source_faces)], corners.mean(1),
        (corners[:,0] + corners[:,1])/2, (corners[:,1] + corners[:,2])/2, (corners[:,2] + corners[:,0])/2])
    for tri in (source_uv * 2047)[source_faces]:
        draw.polygon([tuple(point) for point in tri], fill=255)
    occupied = np.asarray(mask) != 0
    allowed = np.zeros((2048, 2048), bool)
    for x0, y0, x1, y1 in boxes:
        guard = (x0 - allocation_padding, y0 - allocation_padding, x1 + allocation_padding, y1 + allocation_padding)
        if min(guard) < 0 or max(guard) > 2048:
            raise ValueError("Tile guard outside atlas")
        gx0, gy0, gx1, gy1 = guard
        if occupied[gy0:gy1, gx0:gx1].any() or allowed[gy0:gy1, gx0:gx1].any():
            raise ValueError("Guard overlaps retained source UVs or another cap guard")
        allowed[y0-padding:y1+padding, x0-padding:x1+padding] = True
    args.output.mkdir(parents=True)
    shutil.copy2(source, args.output / "frozen-cap-input.glb")
    shutil.copy2(args.allocation, args.output / "allocation.json")
    for path in [Path(__file__), Path(__file__).with_name("round_generated_waist_cap.py")]:
        shutil.copy2(path, args.output / path.name)
    binary = bytearray(original_bin)
    maps, map_receipts = {}, {}
    for key in SLOTS:
        original_maps = [image_array(original_doc, original_bin, texture_info(mat, key)["index"]) for mat in materials]
        if any(im.shape != original_maps[0].shape or im.shape[:2] != (2048, 2048) for im in original_maps):
            raise ValueError("All inputs for an active channel must share 2K dimensions/components")
        packed = original_maps[0].copy()
        cap_errors = []
        for index, box in enumerate(boxes, 1):
            x0, y0, x1, y1 = box
            tile = tile_image(original_maps[index], key, x1 - x0, y1 - y0)
            packed[y0-padding:y1+padding, x0-padding:x1+padding] = np.pad(tile, ((padding,padding),(padding,padding),(0,0)), mode="edge")
            cap_uv = accessor(original_doc, original_bin, primitives[index]["attributes"]["TEXCOORD_0"])
            faces = accessor(original_doc, original_bin, primitives[index]["indices"]).reshape(-1,3)
            used = np.unique(faces)
            centroids = cap_uv[faces].mean(1)
            samples = np.vstack((cap_uv[used], centroids))
            packed_uv = transformed_uv(samples, box, 2048)
            before = bilinear(original_maps[index], samples) / 255
            after = bilinear(packed, packed_uv) / 255
            color_delta = np.abs(srgb_linear(before[:,:3]) - srgb_linear(after[:,:3])) if key == "color" else np.abs(before[:,:3]-after[:,:3])
            errors = {"samples": len(samples), "samplePolicy": "all used cap vertices and every triangle centroid; clamped glTF bilinear texel-centre coordinates", "componentError": summary(color_delta), "errorSpace": "linear-light RGB" if key == "color" else "normalized map channels"}
            seam = samples[:,1] >= .999999
            if seam.any():
                errors["seamComponentError"] = summary(color_delta[seam])
            if key == "normal":
                a,b = before[:,:3]*2-1, after[:,:3]*2-1
                a /= np.maximum(np.linalg.norm(a,axis=1,keepdims=True),1e-12)
                b /= np.maximum(np.linalg.norm(b,axis=1,keepdims=True),1e-12)
                angles = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i",a,b),-1,1)))
                errors["angularDegrees"] = summary(angles)
                if seam.any(): errors["seamAngularDegrees"] = summary(angles[seam])
            cap_errors.append(errors)
        changed = np.any(packed != original_maps[0], axis=2)
        if (changed & ~allowed).any() or not np.array_equal(packed[occupied], original_maps[0][occupied]):
            raise ValueError("Packing changed protected source atlas pixels")
        upper_difference = np.abs(bilinear(packed, upper_samples) - bilinear(original_maps[0], upper_samples))
        if upper_difference.max() != 0:
            raise ValueError("Packing changed retained source bilinear shading")
        path = args.output / ("common-" + key + ".png")
        Image.fromarray(packed).save(path)
        texture = embed_image(doc, binary, path)
        for material in materials:
            texture_info(material, key)["index"] = texture
        maps[key] = {"path":str(path.resolve()), "sha256":digest(path), "textureIndex":texture}
        map_receipts[key] = {"changedPixels":int(changed.sum()), "sourcePixelsOutsideGuardsExact":True,
                             "occupiedSourcePixelsExact":True, "upperBilinearSamples":len(upper_samples),
                             "upperMaxBilinearChannelError":float(upper_difference.max()), "capSamplingErrors":cap_errors}
    for index, box in enumerate(boxes, 1):
        old_uv = accessor(original_doc, original_bin, primitives[index]["attributes"]["TEXCOORD_0"])
        primitives[index]["attributes"] = dict(primitives[index]["attributes"])
        primitives[index]["attributes"]["TEXCOORD_0"] = append_accessor(doc, binary, transformed_uv(old_uv, box, 2048), "TEXCOORD_0")
    result = args.output / "common-atlas-local.glb"
    write_glb(result, doc, binary)
    final_doc, final_bin = load(result)
    final_primitives = final_doc["meshes"][0]["primitives"]
    proofs = []
    for index,(old,new) in enumerate(zip(original_doc["meshes"][0]["primitives"],final_primitives)):
        if not np.array_equal(accessor(original_doc,original_bin,old["indices"]),accessor(final_doc,final_bin,new["indices"])):
            raise ValueError("Primitive index order changed")
        for semantic in old["attributes"]:
            a,b = accessor(original_doc,original_bin,old["attributes"][semantic]),accessor(final_doc,final_bin,new["attributes"][semantic])
            expected = transformed_uv(a,boxes[index-1],2048) if index and semantic == "TEXCOORD_0" else a
            if not np.array_equal(b,expected):
                raise ValueError("Attribute invariant failed: " + semantic)
        proofs.append({"primitive":index,"triangles":len(accessor(final_doc,final_bin,new["indices"]))/3,
                       "positionsNormalsAndOrderedIndicesExact":True,"upperUVsExact":index == 0,
                       "capUvOnlyPositiveAffineTileTransform":index > 0})
    if final_bin[:len(original_bin)] != original_bin:
        raise ValueError("Original embedded binary prefix changed")
    for path,expected in frozen.items():
        if digest(path) != expected: raise ValueError("Frozen input changed")
    replacement = {"label":"Purpose-built torso common atlas (128x64 cap strips)","prefix":"pmh0","height":1.9339157000000002,
                   "parts":{"chest":str(result.resolve())},"diagnosticOnly":True,"sourceDefectsRemain":True}
    (args.output/"stock-replacement.json").write_text(json.dumps(replacement,indent=2)+"\n")
    receipt = {"phase":"common-cap-atlas-material-diagnostic","frozenInputs":frozen,"sourceSha256":args.source_sha256,
               "outputGlb":str(result.resolve()),"outputSha256":digest(result),"allocation":boxes,"padding":padding,
               "allocationPadding":allocation_padding,"sourceFilterHalo":filter_halo,
               "geometryEdited":False,"sourceUpperUvsEdited":False,"sourceBufferPrefixExact":True,
               "maps":maps,"samplingAndPixelProofs":map_receipts,"serializedAttributeProofs":proofs,
               "normalStrengthReduced":False,"sourceDefectsRemain":True,"productionAccepted":False,
               "nativeCompiled":False,"clientTested":False,"nativeCommonAtlasReviewRequired":True}
    (args.output/"common-atlas.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps({"output":str(result.resolve()),"sha256":digest(result),"geometryEdited":False,"nativeCompiled":False}))


if __name__ == "__main__":
    main()
