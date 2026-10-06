"""Target matrix query, validation, and policy enforcement for derived humanoid phenotypes."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

DEFAULT_MATRIX_PATH = Path(__file__).resolve().parent / "configurations" / "derived" / "target-matrix.json"


def load_matrix(path: Path | str | None = None) -> dict:
    matrix_path = Path(path).resolve() if path else DEFAULT_MATRIX_PATH
    if not matrix_path.is_file():
        raise FileNotFoundError(f"Derived target matrix not found: {matrix_path}")
    data = json.loads(matrix_path.read_text(encoding="utf-8"))
    if data.get("schemaVersion") != 1 or data.get("kind") != "phenotype-derived-matrix":
        raise ValueError(f"Invalid derived target matrix schema in {matrix_path}")
    return data


def get_target(matrix: dict, target_id: str) -> dict:
    targets = matrix.get("targets", {})
    if target_id not in targets:
        raise KeyError(f"Unknown target '{target_id}'. Available targets: {list(targets.keys())}")
    return targets[target_id]


def get_pilot_target(matrix: dict) -> dict:
    pilot_id = matrix.get("pilotTarget")
    if not pilot_id:
        raise ValueError("Matrix does not specify a pilotTarget")
    return get_target(matrix, pilot_id)


def evaluate_target_eligibility(matrix: dict, target_id: str) -> tuple[bool, str]:
    target = get_target(matrix, target_id)
    status = target.get("status")
    
    if status == "pilot-accepted":
        return True, "Pilot validated and accepted"

    if status in ("in-progress-pilot", "in-progress", "active"):
        return True, "Active target ready for derivation"
    
    if status == "pending-equipment-validation":
        return True, "Derivation/review allowed; production acceptance pending equipment geometry and client gates"

    if status == "blocked-on-source":
        blocker = target.get("blocker", "Blocked on source master")
        return False, f"BLOCKED: {blocker}"
    
    if status == "shares-human-body":
        note = target.get("note", "Shares stock Human body")
        return False, f"INELIGIBLE FOR DERIVATION: {note}"
    
    if status == "out-of-scope":
        return False, "OUT OF SCOPE: Halfling is excluded per project specification"
    
    if status == "pending-pilot-validation":
        pilot_id = matrix.get("pilotTarget")
        return False, f"PENDING: Pilot target '{pilot_id}' must pass validation and acceptance gates before expanding to '{target_id}'"
    
    return False, f"Unknown status: {status}"


def require_eligible_target(matrix: dict, target_id: str) -> dict:
    eligible, reason = evaluate_target_eligibility(matrix, target_id)
    if not eligible:
        raise RuntimeError(f"Target '{target_id}' cannot proceed: {reason}")
    return get_target(matrix, target_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX_PATH, help="Path to target-matrix.json")
    parser.add_argument("--list", action="store_true", help="List all targets in matrix with status")
    parser.add_argument("--pilot", action="store_true", help="Show pilot target details")
    parser.add_argument("--target", type=str, help="Check eligibility for a specific target")
    args = parser.parse_args()

    matrix = load_matrix(args.matrix)

    if args.list:
        print(f"Pilot Target: {matrix.get('pilotTarget')}")
        print("Targets:")
        for tid, t in matrix.get("targets", {}).items():
            eligible, reason = evaluate_target_eligibility(matrix, tid)
            flag = "[READY]" if eligible else "[BLOCKED/PENDING]"
            print(f"  {flag} {tid:20s} status={t.get('status')} ({reason})")
        return

    if args.pilot:
        pilot = get_pilot_target(matrix)
        print(json.dumps(pilot, indent=2))
        return

    if args.target:
        eligible, reason = evaluate_target_eligibility(matrix, args.target)
        status_str = "ELIGIBLE" if eligible else "INELIGIBLE"
        print(f"Target '{args.target}': {status_str} - {reason}")
        if not eligible:
            sys.exit(1)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
