"""cutdry HEAD [HEIGHT] [--attempt attempt-NN]: check the cut band before repair, or replay a saved uncut master."""
import argparse
from pathlib import Path
import re
import tempfile
from unittest.mock import patch

import numpy as np

import headkit.neck as N
from headkit.common import pin
from headkit.runner import Runner
from _frame import band, head_neck, local_positions


class MasterReady(Exception):
    """Stop the isolated diagnostic after the real repair code has written its uncut master."""


def dry_positions(head, neck, attempt):
    if attempt is not None:
        if not re.fullmatch(r"attempt-[0-9]+", attempt):
            raise ValueError("Expected an attempt directory such as attempt-01")
        master = head / "run" / "repair" / attempt / "master-uncut.glb"
        if not master.is_file():
            raise ValueError(f"No saved uncut master in {attempt}")
        print("Replay", attempt, pin(master)["sha256"], "with current cut settings")
        return local_positions(neck, master)

    runner = Runner(head / "manifest.json", head / "bindings.json", head / "run")
    if not runner.data.get("mesh", {}).get("neck", {}).get("cut"):
        raise ValueError("The manifest must configure mesh.neck.cut")
    with tempfile.TemporaryDirectory() as scratch:
        folder = Path(scratch)
        # Use the same verified source, fit, shell policy and smoothing as repair.
        # Stop before cutting, reduction or any run-stage bookkeeping.
        with patch.object(N, "neck_cut", side_effect=MasterReady):
            try:
                runner._execute("repair", folder)
            except MasterReady:
                master = folder / "master-uncut.glb"
                print("Dry run", "manifest", pin(head / "manifest.json")["sha256"],
                      "uncut master", pin(master)["sha256"])
                for stage in ("precluster", "fit"):
                    if stage in runner.state["stages"]:
                        print(stage, runner.state["stages"][stage])
                return local_positions(neck, master)
        raise ValueError("Diagnostic did not reach the configured neck cut")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("head", type=Path)
    parser.add_argument("height", type=float, nargs="?")
    parser.add_argument("--attempt", help="replay this saved repair master instead of building from current inputs")
    args = parser.parse_args()
    _, neck, bv, bf = head_neck(str(args.head))
    positions = dry_positions(args.head, neck, args.attempt)
    cut = neck["cut"]
    print("local min", positions.min(0).round(4), "max", positions.max(0).round(4),
          "body z", round(bv[:, 2].min(), 4), round(bv[:, 2].max(), 4))
    jaw = None
    if args.height is not None:
        cut = dict(cut, height=args.height)
    elif cut["height"] == "measured":
        jaw = N.measured_jaw(positions, bv, bf, cut)
        print("jaw", jaw)
    plane, moving = band(positions, cut, jaw, bv, bf)
    if not moving.any():
        raise ValueError("No master vertices in the proposed cut band")
    heights = np.maximum(positions[moving, 2], plane[moving])
    height = (plane - cut["slope"] * positions[:, 1])[0]
    print("height", round(height, 4), "height_at range", round(heights.min(), 4), round(heights.max(), 4))

    rim = positions[np.abs(positions[:, 2] - plane) < .003]
    if len(rim) < 3:
        raise ValueError("Too few master vertices near the proposed cut plane to inspect its rim")
    print("rim z range", round(rim[:, 2].min(), 4), round(rim[:, 2].max(), 4),
          "rim y range", round(rim[:, 1].min(), 4), round(rim[:, 1].max(), 4))
    offsets = rim[:, :2] - rim[:, :2].mean(0)
    angles = np.degrees(np.arctan2(offsets[:, 1], offsets[:, 0]))
    radii = np.linalg.norm(offsets, axis=1)
    wide_bins = []
    for lower in range(-180, 180, 10):
        samples = radii[(angles >= lower) & (angles < lower + 10)]
        if len(samples) > 3 and np.ptp(samples) > .015:
            wide_bins.append(lower)
    if wide_bins:
        print(f"RING NOT STAR-SHAPED in bins {wide_bins} (deg about the rim centre)")
    else:
        print("No wide radial bins in the sampled rim; topology still requires the cut or rewrap.")


if __name__ == "__main__":
    main()
