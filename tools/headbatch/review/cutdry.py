"""cutdry HEAD [HEIGHT] [--attempt attempt-NN]: check the cut band before repair, or replay a saved uncut master."""
import argparse
from pathlib import Path
import re
import tempfile
from unittest.mock import patch

import numpy as np

import headkit.neck as N
from headkit.common import pin, verify, write
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


def verified_cut_positions(head, neck, label):
    """Keep the real cut and its audit without starting reduction or recording a repair stage."""
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', label):
        raise ValueError('Use a new diagnostic folder name')
    head = head.resolve()
    manifest = pin(head/'manifest.json')
    runner = Runner(head/'manifest.json', head/'bindings.json', head/'run')
    fit = runner.state['stages']['fit']
    precluster = runner.state['stages']['precluster']
    inputs = [manifest, pin(head/'bindings.json'), fit, precluster, pin(runner.input('bodyNeck'))]
    folder = head/'review-evidence'/label
    folder.mkdir(parents=True, exist_ok=False)
    full_audit, production_cut = N.audit, N.neck_cut
    last_cut = {}

    def capture_cut(vertices, faces, policy, body, rewrap=None):
        result = production_cut(vertices, faces, policy, body, rewrap=rewrap)
        last_cut.clear()
        last_cut.update(result[2])
        return result

    def capture_audit(path, *args, **kwargs):
        report = full_audit(path, *args, **kwargs)
        if Path(path) != folder/'master.glb':
            return report
        verify(inputs, fresh=True)
        write(folder/'master-audit.json', report, fresh=True)
        if not report['passed']:
            raise ValueError(f'Cut master failed audit: {folder}')
        if not last_cut:
            raise ValueError('Expected the production neck cut before the master audit')
        write(folder/'cut-evidence.json', {
            'fit': fit, 'inputs': inputs, 'cut': last_cut, 'audit': pin(folder/'master-audit.json'),
            'uncut': pin(folder/'master-uncut.glb'), 'master': pin(path),
        }, fresh=True)
        raise MasterReady()

    with patch.object(N,'neck_cut',side_effect=capture_cut), patch.object(N,'audit',side_effect=capture_audit):
        try:
            runner._execute('repair', folder)
        except MasterReady:
            print('Verified cut master', folder/'cut-evidence.json', 'closure', last_cut['closure'], 'loops', last_cut['loops'])
            return local_positions(neck, folder/'master-uncut.glb')
    raise ValueError('Diagnostic did not reach the cut-master audit')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("head", type=Path)
    parser.add_argument("height", type=float, nargs="?")
    parser.add_argument("--attempt", help="replay this saved repair master instead of building from current inputs")
    parser.add_argument("--verify-cut", metavar="NEW_FOLDER",
                        help="run through the production cut and master audit, save both meshes under review-evidence")
    args = parser.parse_args()
    if args.verify_cut and (args.attempt or args.height is not None):
        parser.error("--verify-cut uses the current manifest and approved fit")
    from headkit.common import read
    if read(args.head/'manifest.json')['mesh'].get('neck') is None:
        if args.verify_cut or args.attempt or args.height is not None:
            parser.error('A cut-specific replay or height requires a configured neck cut')
        from _frame import report_uncut_jaw
        report_uncut_jaw(args.head)
        return
    _, neck, bv, bf = head_neck(str(args.head))
    positions = (verified_cut_positions(args.head, neck, args.verify_cut) if args.verify_cut
                 else dry_positions(args.head, neck, args.attempt))
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
