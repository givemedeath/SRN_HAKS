"""Freeze an operator-supplied concept image and derive a caption-free Meshy reference.

The original bytes are copied unchanged; the derived reference is a crop only
(no repainting). The receipt records both hashes and the exact crop box.
"""
import argparse
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

from robe_common import FLAGS, fresh_directory, pin, require, utc, write_fresh


def content_rows(image, threshold):
    """Rows containing pixels brighter than the near-black background."""
    values = np.asarray(image.convert("L"), dtype=np.uint8)
    return np.flatnonzero((values > threshold).any(axis=1))


def subject_bottom(image, threshold, minimum_gap):
    """Last row of the subject: the first content row before a background gap of minimum_gap rows."""
    rows = content_rows(image, threshold)
    require(len(rows) > 0, "Reference image has no visible content")
    # Content blocks separated by background gaps; the tallest is the subject (a caption or header is small).
    blocks = np.split(rows, np.flatnonzero(np.diff(rows) >= minimum_gap) + 1)
    subject = max(blocks, key=lambda block: (int(block[-1] - block[0]), -int(block[0])))
    return int(subject[-1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--outfit", required=True)
    parser.add_argument("--threshold", type=int, default=24)
    parser.add_argument("--minimum-gap", type=int, default=12)
    parser.add_argument("--margin", type=int, default=16)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = fresh_directory(args.output)
    original = output / ("original" + args.source.suffix.lower())
    shutil.copyfile(args.source, original)
    source_pin = pin(args.source)
    require(pin(original)["sha256"] == source_pin["sha256"], "Original copy differs from source bytes")
    image = Image.open(original)
    image.load()
    bottom = min(image.height, subject_bottom(image, args.threshold, args.minimum_gap) + 1 + args.margin)
    box = [0, 0, image.width, bottom]
    reference = output / "reference.png"
    image.convert("RGB").crop(box).save(reference, format="PNG", optimize=False)
    report = {"schemaVersion": 1, "kind": "srn-robe-reference", "createdUtc": utc(), "outfit": args.outfit,
              "suppliedSource": source_pin, "original": pin(original), "reference": pin(reference),
              "originalSize": [image.width, image.height], "cropBox": box,
              "derivation": "crop only; removes the caption below the subject; no repainting",
              "settings": {"threshold": args.threshold, "minimumGap": args.minimum_gap, "margin": args.margin},
              **FLAGS}
    print(write_fresh(output / "reference.json", report)["sha256"])


if __name__ == "__main__":
    main()
