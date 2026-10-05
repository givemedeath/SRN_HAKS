"""Pack standalone HAK for Derived Elf Male."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from shared_tools import resolve_tool

RESOURCES_DIR = REPO / "output/phenotypes/derived-elf-male-v1/candidate/converted/resources"
PACKAGE_DIR = REPO / "output/phenotypes/derived-elf-male-v1/package"
HAK_PATH = PACKAGE_DIR / "srn_derived_elf_test.hak"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_resources(resources_dir: Path) -> list[Path]:
    """Validate resource inventory, completeness, and binary hashes against native-compile.json."""
    stage_dir = resources_dir.parent
    receipt_file = stage_dir / "native-compile.json"
    if not receipt_file.is_file():
        raise RuntimeError(f"Missing compiler receipt: {receipt_file}")

    compile_data = json.loads(receipt_file.read_text(encoding="utf-8"))
    if not compile_data.get("complete", False):
        raise RuntimeError(f"Incomplete compiler receipt in {receipt_file}")

    models = compile_data.get("models", [])
    if not models:
        raise RuntimeError(f"No models declared in {receipt_file}")

    expected_resources: dict[str, str] = {}
    for m in models:
        name = m.get("name")
        sha = m.get("binarySha256")
        if not name or not sha:
            raise RuntimeError(f"Invalid model entry in compiler receipt: {m}")
        expected_resources[name] = sha

    materials = compile_data.get("materialResourceHashes", {})
    for mat_name, mat_sha in materials.items():
        expected_resources[mat_name] = mat_sha

    actual_files = {p.name: p for p in resources_dir.iterdir() if p.is_file()}

    missing = set(expected_resources) - set(actual_files)
    if missing:
        raise RuntimeError(f"Missing expected compiled resources: {sorted(missing)}")

    stale = set(actual_files) - set(expected_resources)
    if stale:
        raise RuntimeError(f"Stale or undeclared resources in directory: {sorted(stale)}")

    for name, expected_sha in expected_resources.items():
        actual_sha = sha256_file(actual_files[name])
        if actual_sha != expected_sha:
            raise RuntimeError(
                f"Binary SHA256 mismatch for {name}: expected {expected_sha}, got {actual_sha}"
            )

    return [actual_files[name] for name in sorted(expected_resources)]


def main():
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    if not RESOURCES_DIR.exists():
        raise RuntimeError(f"Missing resources dir: {RESOURCES_DIR}")

    validated_files = validate_resources(RESOURCES_DIR)
    print(f"Validated {len(validated_files)} resources against native-compile.json")
    print(f"Packing {len(validated_files)} resources into {HAK_PATH}")

    erf_tool = resolve_tool("erf", repo=REPO)["path"]
    cmd = [
        str(erf_tool),
        "-c",
        "-f", str(HAK_PATH),
        "-e", "HAK",
        str(RESOURCES_DIR)
    ]
    subprocess.run(cmd, check=True)

    sha = sha256_file(HAK_PATH)
    size = HAK_PATH.stat().st_size
    print(f"Built standalone Elf HAK: {HAK_PATH}")
    print(f"Size: {size} bytes, SHA256: {sha}")


if __name__ == "__main__":
    main()
