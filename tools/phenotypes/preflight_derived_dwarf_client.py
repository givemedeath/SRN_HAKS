"""Preflight verification for derived Dwarf Male client testing."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
STAGE = REPO / "output/phenotypes/derived-dwarf-male-v1/test-stage"
CLIENT = Path(r"C:\Program Files (x86)\GOG Galaxy\Games\Neverwinter Nights Enhanced Edition\bin\win32\nwmain.exe")


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(cond: bool, msg: str):
    if not cond:
        raise ValueError(msg)


def run_preflight(stage_dir: Path = STAGE, client_path: Path = CLIENT, output_receipt: Path | None = None, race: str = "dwarf", prefix: str = "pmd0") -> dict:
    stage_dir = stage_dir.resolve()
    userdir = stage_dir / "userdir"
    receipt_path = stage_dir / "test-module/receipt.json"

    require(userdir.exists(), f"Missing userdir: {userdir}")
    require(receipt_path.exists(), f"Missing build receipt: {receipt_path}")

    build_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    # Verify HAK and MOD files
    hak_path = userdir / "hak/srn_pheno_test.hak"
    mod_path = userdir / "modules/srn_pheno_test.mod"

    require(hak_path.exists(), f"Missing HAK: {hak_path}")
    require(mod_path.exists(), f"Missing Module: {mod_path}")

    hak_sha = sha256_file(hak_path)
    mod_sha = sha256_file(mod_path)

    require(hak_sha == build_receipt["hakSha256"], "HAK SHA256 mismatch vs build receipt")
    require(mod_sha == build_receipt["moduleSha256"], "MOD SHA256 mismatch vs build receipt")

    # Verify override is empty
    override_dir = userdir / "override"
    require(override_dir.is_dir(), "Userdir override must exist as directory")
    override_files = list(override_dir.iterdir())
    require(len(override_files) == 0, f"Userdir override must be completely empty: {override_files}")

    # Verify client hash vs compiler client
    client_sha = sha256_file(client_path)
    compile_receipt = stage_dir / f"{race}_male_fit/converted/native-compile.json"
    require(compile_receipt.exists(), f"Missing {race} candidate native compile receipt")
    compile_data = json.loads(compile_receipt.read_text(encoding="utf-8"))
    require(client_sha == compile_data["clientSha256"], "Client executable hash differs from native compiler")

    # Verify HAK inventory via direct archive parsing
    hak_data = hak_path.read_bytes()
    require(len(hak_data) >= 160 and hak_data[:4] in (b"HAK ", b"MOD ", b"ERF "), "Invalid HAK header")
    import struct
    entry_count = struct.unpack_from("<I", hak_data, 16)[0]
    keys_offset, _ = struct.unpack_from("<II", hak_data, 24)
    type_map = {2002: "mdl", 6: "plt", 2017: "2da", 3: "tga", 2072: "mtr", 2010: "ini", 2005: "nss", 2006: "ncs", 2013: "set"}
    hak_entries = []
    for index in range(entry_count):
        raw_name, rid, res_type = struct.unpack_from("<16sIH", hak_data, keys_offset + 24 * index)
        name = raw_name.split(b"\x00")[0].decode("ascii", errors="replace").lower()
        ext = type_map.get(res_type, f"res{res_type}")
        hak_entries.append(f"{name}.{ext}")

    # Verify candidate parts are packed
    for part in ["bicepl", "bicepr", "chest", "footl", "footr", "forel", "forer", "handl", "handr", "legl", "legr", "pelvis", "shinl", "shinr"]:
        require(f"{prefix}_{part}001.mdl" in hak_entries, f"Missing {prefix}_{part}001.mdl in HAK")
        require(f"{prefix}_{part}001.plt" in hak_entries, f"Missing {prefix}_{part}001.plt in HAK")
        require(f"{prefix}_{part}001.mtr" in hak_entries, f"Missing {prefix}_{part}001.mtr in HAK")

    # Verify stock comparator parts if present in build receipt
    specimens = build_receipt.get("specimens", [])
    if "stock_dwarf_male_fit" in specimens:
        for part in ["bicepl", "bicepr", "chest", "footl", "footr", "forel", "forer", "handl", "handr", "head", "neck", "legl", "legr", "pelvis", "shinl", "shinr", "belt", "shol", "shor"]:
            require(f"pmz0_{part}001.mdl" in hak_entries, f"Missing pmz0_{part}001.mdl in HAK")
            require(f"pmz0_{part}001.plt" in hak_entries, f"Missing pmz0_{part}001.plt in HAK")
        require("pmz0.mdl" in hak_entries, "Missing pmz0.mdl supermodel in HAK")

    require("appearance.2da" in hak_entries, "Missing fixture appearance.2da in HAK")

    result = {
        "schemaVersion": 1,
        "kind": "derived-phenotype-client-preflight",
        "target": f"{race}-male-stock-family",
        "pass": True,
        "specimens": specimens,
        "stage": str(stage_dir),
        "userDirectory": str(userdir),
        "hak": str(hak_path),
        "hakSha256": hak_sha,
        "module": str(mod_path),
        "moduleSha256": mod_sha,
        "totalHakEntries": len(hak_entries),
        "client": str(client_path),
        "clientSha256": client_sha,
        "overrideEmpty": True,
        "clientLaunched": False,
        "preflightAuthorization": "READY_FOR_USER_CONFIRMATION"
    }

    if output_receipt:
        output_receipt.parent.mkdir(parents=True, exist_ok=True)
        output_receipt.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"Wrote preflight receipt to {output_receipt}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preflight verification for derived phenotype client testing")
    parser.add_argument("--race", default="dwarf", help="Target race (default: dwarf)")
    parser.add_argument("--prefix", default=None, help="Model prefix (default: pmd0 for dwarf, pmg0 for troll)")
    parser.add_argument("--stage", default=None, type=Path, help="Stage dir")
    parser.add_argument("--client", default=None, type=Path, help="Client executable path")
    parser.add_argument("--output-receipt", default=None, type=Path, help="Output receipt path")
    args = parser.parse_args()

    race = args.race
    default_prefixes = {"dwarf": "pmd0", "troll": "pmg0", "elf": "pme0", "orc": "pmo0"}
    prefix = args.prefix or default_prefixes.get(race, "pmd0")
    stage = args.stage or (REPO / f"output/phenotypes/derived-{race}-male-v1/test-stage")
    from run_derived_dwarf_client_test import resolve_client
    client = resolve_client(args.client)

    res = run_preflight(stage_dir=stage, client_path=client, output_receipt=receipt, race=race, prefix=prefix)
    print(f"Preflight passed: {res['pass']}, HAK entries: {res['totalHakEntries']}")
