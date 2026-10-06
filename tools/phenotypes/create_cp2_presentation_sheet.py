"""Stitch rendered CP2 views into high-resolution presentation sheets in the artifact directory."""
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
        # Draw label box
        draw.rectangle([x + 16, y + 16, x + 240, y + 52], fill=(20, 24, 34, 210), outline=(70, 80, 105, 255))
        draw.text((x + 28, y + 26), label, fill=(240, 243, 250, 255))

    grid.save(out_path, format="PNG")
    print(f"Created 2x2 grid -> {out_path}")


def make_motion_strip(
    images: list[Path],
    labels: list[str],
    out_path: Path,
    target_width: int = 1920,
):
    imgs = [Image.open(p) for p in images]
    n = len(imgs)
    cell_w = target_width // n
    orig_w, orig_h = imgs[0].size
    cell_h = int(orig_h * (cell_w / orig_w))

    strip = Image.new("RGBA", (cell_w * n, cell_h), (15, 17, 23, 255))
    draw = ImageDraw.Draw(strip)

    for i, (img, label) in enumerate(zip(imgs, labels)):
        resized = img.resize((cell_w, cell_h), Image.Resampling.LANCZOS)
        x = i * cell_w
        strip.paste(resized, (x, 0))
        draw.rectangle([x + 16, 16, x + 240, 52], fill=(20, 24, 34, 210), outline=(70, 80, 105, 255))
        draw.text((x + 28, 26), label, fill=(240, 243, 250, 255))

    strip.save(out_path, format="PNG")
    print(f"Created motion strip -> {out_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--previews-dir",
        type=Path,
        default=Path("output/phenotypes/derived-v1/previews/cp2-review"),
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("C:/Users/benco/.gemini/antigravity-ide/brain/4adb5468-4771-4ffc-93ea-eda7b809f211"),
    )
    args = parser.parse_args()

    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    p_dir = args.previews_dir

    # 1. Standing Clay 2x2
    clay_files = [
        p_dir / "cp2_clay_front.png",
        p_dir / "cp2_clay_side.png",
        p_dir / "cp2_clay_oblique.png",
        p_dir / "cp2_clay_rear.png",
    ]
    clay_labels = [
        "Standing Front (Clay)",
        "Standing Side Profile (Clay)",
        "Standing 3/4 Oblique (Clay)",
        "Standing Rear (Clay)",
    ]
    make_2x2_grid(clay_files, clay_labels, args.artifact_dir / "cp2_standing_clay.png")

    # 2. Standing Unlit 2x2
    unlit_files = [
        p_dir / "cp2_unlit_front.png",
        p_dir / "cp2_unlit_side.png",
        p_dir / "cp2_unlit_oblique.png",
        p_dir / "cp2_unlit_rear.png",
    ]
    unlit_labels = [
        "Silhouette Front (Unlit)",
        "Silhouette Side (Unlit)",
        "Silhouette Oblique (Unlit)",
        "Silhouette Rear (Unlit)",
    ]
    make_2x2_grid(unlit_files, unlit_labels, args.artifact_dir / "cp2_standing_unlit.png")

    # 3. Motion Strip
    pose_files = [
        p_dir / "cp2_pose_combat_ready.png",
        p_dir / "cp2_pose_running_stride.png",
        p_dir / "cp2_pose_deep_crouch.png",
    ]
    pose_labels = [
        "Combat Stance (plreadyr)",
        "Running Stride (run)",
        "Deep Crouch (gutokdf)",
    ]
    make_motion_strip(pose_files, pose_labels, args.artifact_dir / "cp2_motion_poses.png")

    # Copy individual key images to artifact directory
    for f in p_dir.glob("*.png"):
        dest = args.artifact_dir / f.name
        img = Image.open(f)
        img.save(dest, format="PNG")

    print(f"Presentation sheets successfully copied to {args.artifact_dir}")


if __name__ == "__main__":
    main()
