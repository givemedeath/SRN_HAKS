"""Convert preserved Meshy PBR maps to fixed-colour NWN:EE materials plus a skin-only PLT.

Fixed material: diffuse TGA (texture0), tangent normal TGA (texture1) and
roughness TGA (texture3) at the configured atlas size, with explicit Roughness 0
so the map is used. Skin material: a PLT whose every texel is layer 0 (skin)
with shade from base-colour luminance, and an MTR that omits texture0 so the
PLT stays the diffuse source. Source maps are never modified. Approves nothing.
"""
import argparse
import struct
from pathlib import Path

import numpy as np
from PIL import Image

from robe_common import FLAGS, pin, read, require, skin_colour, utc, verify_pins, write_fresh

MTR_PARAMETERS = ["parameter float Roughness 0", "parameter float Specularity 0.04",
                  "parameter float Metallicness 0.001"]


def plt_bytes(shades, layers):
    require(shades.shape == layers.shape and shades.dtype == layers.dtype == np.uint8, "PLT planes must match")
    require(np.all(layers <= 9), "PLT layers must be 0-9")
    height, width = shades.shape
    pixels = np.stack([shades, layers], axis=-1)[::-1].copy()
    return b"PLT V1  " + struct.pack("<IIII", 10, 0, width, height) + pixels.tobytes()


def tga(path, image):
    image.save(path, format="TGA")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--prefix", required=True, help="Material resref prefix, e.g. ww11")
    parser.add_argument("--size", type=int, default=2048)
    parser.add_argument("--flip-normal-green", choices=["true", "false"], required=True)
    parser.add_argument("--skin-shade-range", type=int, nargs=2, default=[60, 230])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inputs = [pin(args.config)]
    config = read(args.config)
    textures = {k: (args.run_root / v).resolve() for k, v in config["source"]["textures"].items()}
    inputs += [pin(p) for p in textures.values()]
    output = Path(args.output).resolve()
    require(not output.exists(), "Fresh material directory required")
    output.mkdir(parents=True)
    size = (args.size, args.size)
    fixed, skin = args.prefix + "a", args.prefix + "s"
    require(len(fixed) + 1 <= 16, "Texture resref too long")
    base = Image.open(textures["baseColor"]).convert("RGB")
    diffuse = base.resize(size, Image.LANCZOS)
    tga(output / (fixed + ".tga"), diffuse)
    normal = np.asarray(Image.open(textures["normal"]).convert("RGB").resize(size, Image.LANCZOS)).copy()
    if args.flip_normal_green == "true":
        normal[:, :, 1] = 255 - normal[:, :, 1]
    tga(output / (fixed + "n.tga"), Image.fromarray(normal))
    roughness = Image.open(textures["roughness"]).convert("L").resize(size, Image.LANCZOS)
    tga(output / (fixed + "r.tga"), Image.merge("RGB", [roughness] * 3))
    (output / (fixed + ".mtr")).write_text("\n".join(["renderhint NormalTangents", f"texture0 {fixed}",
                                                      f"texture1 {fixed}n", *MTR_PARAMETERS, f"texture3 {fixed}r"])
                                           + "\n", encoding="ascii", newline="\n")
    encoded = np.asarray(diffuse, dtype=np.float32) / 255.0  # display-encoded (sRGB) values, as the shade is seen
    luminance = 0.2126 * encoded[:, :, 0] + 0.7152 * encoded[:, :, 1] + 0.0722 * encoded[:, :, 2]
    # Stretch the shade range over the skin-coloured texels only (the rule that marks exposed-skin faces),
    # so cloth, leather and metal elsewhere in the atlas do not compress the skin's contrast.
    skin_texels = skin_colour(encoded.reshape(-1, 3)).reshape(luminance.shape)
    basis = luminance[skin_texels] if skin_texels.sum() >= 1024 else luminance.ravel()
    low, high = np.percentile(basis, [2, 98])
    lo, hi = args.skin_shade_range
    shades = np.clip(lo + (luminance - low) / max(high - low, 1e-6) * (hi - lo), 0, 255).astype(np.uint8)
    layers = np.zeros(shades.shape, dtype=np.uint8)
    (output / (skin + ".plt")).write_bytes(plt_bytes(shades, layers))
    (output / (skin + ".mtr")).write_text("\n".join(["renderhint NormalTangents", f"texture1 {fixed}n",
                                                     *MTR_PARAMETERS, f"texture3 {fixed}r"]) + "\n",
                                          encoding="ascii", newline="\n")
    verify_pins(inputs)
    report = {"schemaVersion": 1, "kind": "srn-robe-materials", "createdUtc": utc(), "inputs": inputs,
              "atlasSize": args.size, "flipNormalGreen": args.flip_normal_green == "true",
              "fixedMaterial": {"mtr": pin(output / (fixed + ".mtr")), "diffuse": pin(output / (fixed + ".tga")),
                                "normal": pin(output / (fixed + "n.tga")), "roughness": pin(output / (fixed + "r.tga"))},
              "skinMaterial": {"mtr": pin(output / (skin + ".mtr")), "plt": pin(output / (skin + ".plt")),
                               "layer": 0, "shadeRange": [lo, hi], "luminancePercentiles": [float(low), float(high)],
                               "percentileTexels": "skin-coloured" if skin_texels.sum() >= 1024 else "whole atlas"},
              "metallic": "constant Metallicness 0.001; the Meshy metallic map is not bound (no standard slot used)",
              "limits": ["Normal-map green orientation needs client confirmation.",
                         "Skin shade is a luminance mapping of the baked albedo; palette response needs client review."],
              **FLAGS}
    print(write_fresh(output / "materials.json", report)["sha256"])


if __name__ == "__main__":
    main()
