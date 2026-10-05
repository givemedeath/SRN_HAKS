"""Pack standalone HAK for Derived Elf Male."""
from __future__ import annotations
import hashlib
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


def main():
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    if not RESOURCES_DIR.exists():
        raise RuntimeError(f"Missing resources dir: {RESOURCES_DIR}")

    files = list(RESOURCES_DIR.iterdir())
    print(f"Packing {len(files)} resources into {HAK_PATH}")

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
