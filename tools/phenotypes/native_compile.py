"""Validate candidate models with the installed NWN:EE native compiler."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from pipeline import digest, save_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", required=True, type=Path)
    parser.add_argument("--user-directory", required=True, type=Path)
    parser.add_argument("--converted", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=20, help="Per-model compiler deadline in seconds; large diagnostic parts may need longer")
    materials = parser.add_mutually_exclusive_group()
    materials.add_argument("--with-material-resources", dest="with_material_resources", action="store_true", default=True,
                           help="Stage and hash material/texture dependencies for compile-time tangent generation (default)")
    materials.add_argument("--without-material-resources", dest="with_material_resources", action="store_false",
                           help="Explicit diagnostic only: omit compile-time material resources")
    parser.add_argument("--reuse-from",type=Path,help="Reuse verified binaries with identical source and client hashes from another candidate")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    client = args.client.resolve()
    userdir = args.user_directory.resolve()
    converted = args.converted.resolve()
    if userdir == converted.parent.parent / "userdir":
        raise RuntimeError("Compile in a separate staging user directory, not the client-test userdir")
    compiler_output = userdir / "modelcompiler"
    compiler_output.mkdir(parents=True, exist_ok=True)
    override = userdir / "override"
    override.mkdir(exist_ok=True)
    sources = sorted((converted / "ascii").glob("*.mdl"))
    dependencies = sorted(p for p in (converted / "resources").iterdir()
                          if args.with_material_resources and p.suffix.lower() in (".mtr", ".txi", ".tga", ".dds", ".plt"))
    dependency_hashes = {p.name: digest(p) for p in dependencies}
    expected_override = {p.name for p in sources + dependencies}
    extra_override = {p.name for p in override.iterdir()} - expected_override
    if extra_override:
        raise RuntimeError("Unexpected compile override resources: " + str(sorted(extra_override)))
    for path in dependencies:
        shutil.copyfile(path, override / path.name)
    receipt_path = converted / "native-compile.json"
    previous = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    cache = {r["name"]: r for r in previous.get("models", [])}
    client_hash = digest(client)
    if previous.get("clientSha256") != client_hash or previous.get("materialResourceHashes", {}) != dependency_hashes:
        cache = {}
    if args.reuse_from:
        donor=args.reuse_from.resolve()
        donor_receipt=json.loads((donor/"native-compile.json").read_text())
        if (not donor_receipt.get("complete") or donor_receipt.get("clientSha256")!=client_hash
                or donor_receipt.get("materialResourceHashes", {}) != dependency_hashes):
            raise RuntimeError("Compiler cache donor is incomplete or uses a different client")
        for entry in donor_receipt["models"]:
            source=converted/"ascii"/entry["name"]
            binary=donor/"resources"/entry["name"]
            if source.exists() and digest(source)==entry["sourceSha256"]:
                if digest(binary)!=entry["binarySha256"]:
                    raise RuntimeError("Compiler cache donor binary changed: "+entry["name"])
                shutil.copyfile(binary,converted/"resources"/entry["name"])
                cache[entry["name"]]={**entry,"reusedFrom":str(donor)}
    snapshot={}
    for path in sources:
        data=path.read_bytes()
        snapshot[path.name]=hashlib.sha256(data).hexdigest()
        (override/path.name).write_bytes(data)
    receipts = []
    for path in sources:
        if any(digest(p) != dependency_hashes[p.name] or digest(override / p.name) != dependency_hashes[p.name] for p in dependencies):
            raise RuntimeError("Material resource changed during compilation")
        if digest(path)!=snapshot[path.name]:
            raise RuntimeError("Source changed during compilation; finish asset adoption first: "+path.name)
        destination = converted / "resources" / path.name
        cached = cache.get(path.name)
        if (cached and cached["sourceSha256"] == snapshot[path.name] and destination.exists()
                and cached["binarySha256"] == digest(destination)):
            receipts.append(cached)
            continue
        target = compiler_output / path.name
        if target.exists():
            target.unlink()
        started = time.time()
        try:
            result = subprocess.run([str(client), "-userdirectory", str(userdir), "compilemodel", path.stem],
                                    cwd=client.parent, capture_output=True, timeout=args.timeout,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        except subprocess.TimeoutExpired as exc:
            save_json(converted / "native-compile-failure.json", {"model": path.name, "reason": "compilemodel timeout; inspect isolated compiler logs/output before retrying", "timeoutSeconds": args.timeout})
            raise RuntimeError("Native compile did not finish: " + path.name) from exc
        if result.returncode or not target.exists() or target.read_bytes()[:4] != b"\0\0\0\0":
            raise RuntimeError("Native compiler produced no valid binary: " + path.name)
        if digest(path)!=snapshot[path.name] or digest(override/path.name)!=snapshot[path.name]:
            raise RuntimeError("Compiler source or override changed during compilation: "+path.name)
        shutil.copyfile(target, destination)
        receipt = {"name": path.name, "sourceSha256": snapshot[path.name], "binarySha256": digest(destination),
                   "bytes": destination.stat().st_size, "seconds": round(time.time() - started, 2)}
        receipts.append(receipt)
        save_json(receipt_path, {"client": str(client), "clientSha256": client_hash,
                  "materialResourceHashes": dependency_hashes,
                  "models": receipts, "complete": False})
        print(json.dumps({"model": path.name, "completed": len(receipts), "total": len(sources)}), flush=True)
    if any(digest(path)!=snapshot[path.name] for path in sources):
        raise RuntimeError("Source changed before compiler verification completed")
    if any(digest(p) != dependency_hashes[p.name] or digest(override / p.name) != dependency_hashes[p.name] for p in dependencies):
        raise RuntimeError("Material resource changed before compiler verification completed")
    save_json(receipt_path, {"client": str(client), "clientSha256": client_hash,
              "executionMode": "compilemodel", "interactiveClientLaunched": False,
              "materialResourceHashes": dependency_hashes,
              "models": receipts, "complete": len(receipts) == len(sources)})


if __name__ == "__main__":
    main()
