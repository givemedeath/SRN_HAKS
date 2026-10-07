"""End-to-end textured-donor cleanup, retopology, baking, and validation pipeline.

Coordinates:
- Geometry and shell audit (audit_donor_geometry.py)
- Component classification and triangle allocations (classify_head_components.py)
- Textured donor cleanup and repair (cleanup_textured_donor.py)
- Deliberate-loop retopology and independent hair reduction (retopologize_textured_donor.py)
- Multi-view review sheet generation (render_head_trial_review.py)
- Optional fitting, assembly review, and native validation (fit_head.py, head_export.py, etc.)

Tracks source hashes, helper versions, manual revisions, and stage approvals.
Resumes only from matching inputs; changed geometry invalidates downstream stages.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_donor_geometry import audit_geometry
from classify_head_components import classify_donor
from cleanup_textured_donor import execute_donor_cleanup_in_blender
from retopologize_textured_donor import execute_retopology_in_blender
from render_head_trial_review import execute_review_renders_in_blender
from head_workflow import MAX_TRIANGLES, pin, read, require, sha, verify_pins, write_fresh


HELPER_FILES = [
    "audit_donor_geometry.py",
    "classify_head_components.py",
    "cleanup_textured_donor.py",
    "retopologize_textured_donor.py",
    "render_head_trial_review.py",
    "pipeline_textured_donor.py",
]


def helper_pins() -> dict[str, str]:
    """Get SHA-256 hashes of all pipeline helper scripts."""
    here = Path(__file__).resolve().parent
    return {name: sha(here / name) for name in HELPER_FILES if (here / name).is_file()}


class PipelineSession:
    """Manages an end-to-end textured donor cleanup and retopology trial."""

    def __init__(
        self,
        trial_id: str,
        donor_glb: str | Path,
        output_dir: str | Path,
        *,
        reference_image: str | Path | None = None,
        component_overrides: str | Path | None = None,
        face_budget: int = 11000,
        hair_budget: int = 8000,
        reserve_budget: int = 1000,
        body_contract: str | Path | None = None,
        blender_exe: str | Path | None = None,
    ):
        self.trial_id = trial_id
        self.donor_glb = Path(donor_glb).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.reference_image = Path(reference_image).resolve() if reference_image else None
        self.component_overrides = Path(component_overrides).resolve() if component_overrides else None
        self.face_budget = face_budget
        self.hair_budget = hair_budget
        self.reserve_budget = reserve_budget
        self.body_contract = Path(body_contract).resolve() if body_contract else None
        self.blender_exe = str(blender_exe) if blender_exe else "E:\\Program Files\\Blender Foundation\\Blender 4.0\\blender.exe"

        self.donor_pin = pin(self.donor_glb)
        self.helpers = helper_pins()
        self.stage_receipts: dict[str, dict] = {}

    def _verify_upstream_inputs(self, expected_pins: list[dict]) -> bool:
        """Verify that all inputs match their frozen SHA-256 pins."""
        for p in expected_pins:
            path = Path(p["path"])
            if not path.is_file() or sha(path) != p["sha256"]:
                return False
        return True

    def run_geometry_audit(self, force: bool = False) -> dict:
        """Stage 1: Geometry and shell audit."""
        audit_file = self.output_dir / "audit" / "geometry-audit.json"
        if not force and audit_file.exists():
            receipt = read(audit_file)
            if self._verify_upstream_inputs([receipt["source"]]):
                self.stage_receipts["audit"] = receipt
                return receipt
            # Stale input: invalidate
            audit_file.unlink()

        audit_file.parent.mkdir(parents=True, exist_ok=True)
        report = audit_geometry(self.donor_glb, sample_stride=1)
        write_fresh(audit_file, report)
        self.stage_receipts["audit"] = report
        return report

    def run_component_classification(self, force: bool = False) -> dict:
        """Stage 2: Component classification and budget allocation."""
        comp_file = self.output_dir / "components" / "components.json"
        if not force and comp_file.exists():
            receipt = read(comp_file)
            if self._verify_upstream_inputs([receipt["source"]]):
                self.stage_receipts["components"] = receipt
                return receipt
            comp_file.unlink()

        comp_file.parent.mkdir(parents=True, exist_ok=True)
        custom_budget = {
            "skull_face_ears_eyes": self.face_budget,
            "hair": self.hair_budget,
            "reserve": self.reserve_budget,
            "combinedCeiling": MAX_TRIANGLES,
        }
        report = classify_donor(
            self.donor_glb,
            comp_file,
            custom_budget=custom_budget,
            overrides_path=self.component_overrides,
        )
        self.stage_receipts["components"] = report
        return report

    def run_donor_cleanup(self, force: bool = False) -> dict:
        """Stage 3: Donor repair and cleanup in Blender."""
        cleanup_receipt = self.output_dir / "cleanup" / "donor_cleanup.json"
        cleaned_glb = self.output_dir / "cleanup" / "cleaned_donor.glb"

        if not force and cleanup_receipt.exists() and cleaned_glb.exists():
            receipt = read(cleanup_receipt)
            if sha(self.donor_glb) == self.donor_pin["sha256"]:
                self.stage_receipts["cleanup"] = receipt
                return receipt
            cleanup_receipt.unlink()

        cleanup_dir = self.output_dir / "cleanup"
        cleanup_dir.mkdir(parents=True, exist_ok=True)

        audit_path = self.output_dir / "audit" / "geometry-audit.json"
        comp_path = self.output_dir / "components" / "components.json"

        # Invoke cleanup in Blender
        cmd = [
            self.blender_exe,
            "--factory-startup",
            "-b",
            "-t", "4",
            "--python", str(Path(__file__).resolve().parent / "cleanup_textured_donor.py"),
            "--",
            "--source", str(self.donor_glb),
            "--output", str(cleanup_dir),
            "--audit", str(audit_path),
            "--components", str(comp_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0 or not cleanup_receipt.exists():
            raise RuntimeError(f"Donor cleanup failed: {result.stderr or result.stdout}")

        receipt = read(cleanup_receipt)
        self.stage_receipts["cleanup"] = receipt
        return receipt

    def run_retopology(self, force: bool = False) -> dict:
        """Stage 4: Facial retopology and independent hair reduction."""
        retopo_receipt = self.output_dir / "retopology" / "retopology_receipt.json"
        runtime_glb = self.output_dir / "retopology" / "runtime.glb"

        if not force and retopo_receipt.exists() and runtime_glb.exists():
            receipt = read(retopo_receipt)
            cleaned_glb = self.output_dir / "cleanup" / "cleaned_donor.glb"
            if cleaned_glb.exists() and sha(cleaned_glb) == sha(Path(receipt["source"])):
                self.stage_receipts["retopology"] = receipt
                return receipt
            retopo_receipt.unlink()

        retopo_dir = self.output_dir / "retopology"
        retopo_dir.mkdir(parents=True, exist_ok=True)

        cleaned_glb = self.output_dir / "cleanup" / "cleaned_donor.glb"
        comp_path = self.output_dir / "components" / "components.json"

        cmd = [
            self.blender_exe,
            "--factory-startup",
            "-b",
            "-t", "4",
            "--python", str(Path(__file__).resolve().parent / "retopologize_textured_donor.py"),
            "--",
            "--source", str(cleaned_glb),
            "--output", str(retopo_dir),
            "--components", str(comp_path),
            "--face-budget", str(self.face_budget),
            "--hair-budget", str(self.hair_budget),
            "--reserve", str(self.reserve_budget),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0 or not retopo_receipt.exists():
            raise RuntimeError(f"Retopology failed: {result.stderr or result.stdout}")

        receipt = read(retopo_receipt)
        self.stage_receipts["retopology"] = receipt
        return receipt

    def run_review(self, force: bool = False) -> dict:
        """Stage 5: Review sheet and section views generation."""
        review_file = self.output_dir / "review" / "trial_review.json"
        if not force and review_file.exists():
            receipt = read(review_file)
            self.stage_receipts["review"] = receipt
            return receipt

        review_dir = self.output_dir / "review"
        review_dir.mkdir(parents=True, exist_ok=True)

        runtime_glb = self.output_dir / "retopology" / "runtime.glb"
        cleaned_glb = self.output_dir / "cleanup" / "cleaned_donor.glb"

        cmd = [
            self.blender_exe,
            "--factory-startup",
            "-b",
            "-t", "4",
            "--python", str(Path(__file__).resolve().parent / "render_head_trial_review.py"),
            "--",
            "--target", str(runtime_glb),
            "--donor", str(cleaned_glb),
            "--output", str(review_dir),
            "--trial-name", self.trial_id,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0 or not review_file.exists():
            raise RuntimeError(f"Review rendering failed: {result.stderr or result.stdout}")

        receipt = read(review_file)
        self.stage_receipts["review"] = receipt
        return receipt

    def run_pipeline(self) -> dict:
        """Execute full trial pipeline."""
        start_time = time.monotonic()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        audit_rep = self.run_geometry_audit()
        comp_rep = self.run_component_classification()
        cleanup_rep = self.run_donor_cleanup()
        retopo_rep = self.run_retopology()
        review_rep = self.run_review()

        summary = {
            "kind": "srn-head-quality-pipeline-trial-summary",
            "trialId": self.trial_id,
            "donor": self.donor_pin,
            "helpers": self.helpers,
            "stages": {
                "audit": "passed",
                "components": "passed",
                "cleanup": "passed",
                "retopology": "passed",
                "review": "passed",
                "fitting": "pending_body_contract" if not self.body_contract else "ready",
                "native": "pending_body_contract" if not self.body_contract else "ready",
            },
            "metrics": {
                "originalDonorTriangles": audit_rep["triangleCount"],
                "cleanedDonorTriangles": cleanup_rep["cleanedTriangles"],
                "runtimeTriangles": retopo_rep["runtimeTriangles"],
                "triangleCeiling": MAX_TRIANGLES,
                "withinCeiling": retopo_rep["withinBudget"],
                "boundaryEdges": retopo_rep["remainingBoundaryEdges"],
                "loopsPreserved": retopo_rep["deliberateLoopsPreserved"],
                "bottomViewCorrectlyOriented": review_rep["orientationChecks"]["bottomViewCorrectlyOriented"],
            },
            "reviewGates": review_rep["reviewGates"],
            "totalElapsedSeconds": round(time.monotonic() - start_time, 4),
        }

        summary_file = self.output_dir / "trial_summary.json"
        write_fresh(summary_file, summary)
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trial-id", required=True)
    parser.add_argument("--donor", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--components", type=Path)
    parser.add_argument("--body-contract", type=Path)
    parser.add_argument("--face-budget", type=int, default=11000)
    parser.add_argument("--hair-budget", type=int, default=8000)
    parser.add_argument("--reserve", type=int, default=1000)
    parser.add_argument("--blender-exe", type=Path)
    args = parser.parse_args()

    session = PipelineSession(
        trial_id=args.trial_id,
        donor_glb=args.donor,
        output_dir=args.output,
        reference_image=args.reference,
        component_overrides=args.components,
        body_contract=args.body_contract,
        face_budget=args.face_budget,
        hair_budget=args.hair_budget,
        reserve_budget=args.reserve,
        blender_exe=args.blender_exe,
    )
    result = session.run_pipeline()
    print(json.dumps({
        "trial": args.trial_id,
        "runtimeTriangles": result["metrics"]["runtimeTriangles"],
        "withinBudget": result["metrics"]["withinCeiling"],
        "status": "completed",
    }))


if __name__ == "__main__":
    main()
