"""Assemble labelled review renders into a contact sheet PNG with a hash receipt."""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

from robe_common import FLAGS, pin, read, require, utc, write_fresh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", type=Path, required=True,
                        help="JSON: {title, rows: [{label, images: [paths]}], cell: [w, h]}")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    layout = read(args.layout)
    require(not args.output.exists(), "Fresh contact sheet required")
    cell_w, cell_h = layout.get("cell", [240, 320])
    label_w, title_h = 190, 34
    columns = max(len(row["images"]) for row in layout["rows"])
    sheet = Image.new("RGB", (label_w + columns * cell_w, title_h + len(layout["rows"]) * cell_h), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    draw.text((8, 10), layout["title"], fill=(0, 0, 0))
    inputs = []
    for r, row in enumerate(layout["rows"]):
        y = title_h + r * cell_h
        draw.text((8, y + cell_h // 2 - 12), row["label"], fill=(0, 0, 0))
        for c, path in enumerate(row["images"]):
            image = Image.open(path).convert("RGB")
            image.thumbnail((cell_w, cell_h))
            sheet.paste(image, (label_w + c * cell_w, y))
            inputs.append(pin(path))
        if "note" in row:
            draw.text((8, y + cell_h // 2 + 6), row["note"], fill=(90, 90, 90))
    for c, heading in enumerate(layout.get("columns", [])):
        draw.text((label_w + c * cell_w + 6, title_h - 14), heading, fill=(60, 60, 60))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(json.dumps(write_fresh(args.output.with_suffix(".json"), {"kind": "srn-robe-contact-sheet",
                     "createdUtc": utc(), "layout": pin(args.layout), "inputs": inputs, "sheet": pin(args.output),
                     "clientEvidence": False, **FLAGS})))


if __name__ == "__main__":
    main()
