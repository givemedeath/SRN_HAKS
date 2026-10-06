"""Stitch rendered Orc Male review views into presentation sheets in the artifact directory."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def make_2x2_grid(
    images: list[Path],
    labels: list[str],
    out_path: Path,
    target_width: int = 1920,
):
    imgs = [Image.open(p) for p in images]
    orig_w, orig_h = imgs[0].size
    cell_w = target_width // 2
    cell_h = int(orig_h * (cell_w / orig_w))

    grid = Image.new("RGBA", (cell_w * 2, cell_h * 2), (15, 17, 23, 255))
    draw = ImageDraw.Draw(grid)

    positions = [(0, 0), (cell_w, 0), (0, cell_h), (cell_w, cell_h)]

    for img, label, (x, y) in zip(imgs, labels, positions):
        resized = img.resize((cell_w, cell_h), Image.Resampling.LANCZOS)
        grid.paste(resized, (x, y))
        draw.rectangle([x + 16, y + 16, x + 340, y + 52], fill=(20, 24, 34, 210), outline=(70, 80, 105, 255))
        draw.text((x + 28, y + 26), label, fill=(240, 243, 250, 255))

    grid.save(out_path, format="PNG")
    print(f"Created 2x2 grid -> {out_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--renders-dir",
        type=Path,
        default=Path("output/phenotypes/derived-orc-male-v1/review/renders"),
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("C:/Users/benco/.gemini/antigravity-ide/brain/4adb5468-4771-4ffc-93ea-eda7b809f211"),
    )
    args = parser.parse_args()

    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    r_dir = args.renders_dir

    # 1. Standing Clay 2x2
    clay_files = [
        r_dir / "orc_clay_front.png",
        r_dir / "orc_clay_side.png",
        r_dir / "orc_clay_oblique.png",
        r_dir / "orc_clay_rear.png",
    ]
    clay_labels = [
        "Human Master vs Derived Orc (Front Clay)",
        "Human Master vs Derived Orc (Side Clay)",
        "Human Master vs Derived Orc (Oblique Clay)",
        "Human Master vs Derived Orc (Rear Clay)",
    ]
    make_2x2_grid(clay_files, clay_labels, args.artifact_dir / "orc_standing_clay.png")

    # 2. Standing Unlit 2x2
    unlit_files = [
        r_dir / "orc_unlit_front.png",
        r_dir / "orc_unlit_side.png",
        r_dir / "orc_unlit_oblique.png",
        r_dir / "orc_unlit_rear.png",
    ]
    unlit_labels = [
        "Human Master vs Derived Orc (Front Unlit)",
        "Human Master vs Derived Orc (Side Unlit)",
        "Human Master vs Derived Orc (Oblique Unlit)",
        "Human Master vs Derived Orc (Rear Unlit)",
    ]
    make_2x2_grid(unlit_files, unlit_labels, args.artifact_dir / "orc_standing_unlit.png")


if __name__ == "__main__":
    main()
