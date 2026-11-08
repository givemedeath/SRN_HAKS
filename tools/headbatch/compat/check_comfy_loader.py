"""Probe the actual controlled Comfy loader on CPU before spending a GPU attempt.

Run through headbatch env with STARTUP.json and explicit local safetensors files.
The child uses the bound Comfy interpreter. A native loader crash fails the probe.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys


def sha(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def check_model(path, load, torch):
    with path.open("rb") as stream:
        header_size = struct.unpack("<Q", stream.read(8))[0]
        if not 0 < header_size <= 100_000_000:
            raise ValueError(f"{path.name}: invalid header size")
        header = json.loads(stream.read(header_size))
        expected_metadata = header.pop("__metadata__", {})
        tensors, metadata = load(str(path), return_metadata=True)
        if metadata != expected_metadata or tensors.keys() != header.keys():
            raise ValueError(f"{path.name}: tensor names or metadata differ")
        samples = 0
        for name, record in header.items():
            tensor = tensors[name]
            if list(tensor.shape) != record["shape"]:
                raise ValueError(f"{path.name}: {name} shape differs")
            start, end = record["data_offsets"]
            width = min(end - start, 8)
            if not width:
                continue
            data = tensor.reshape(-1).view(torch.uint8)
            if data.numel() != end - start:
                raise ValueError(f"{path.name}: {name} byte length differs")
            for offset in sorted({0, end - start - width}):
                stream.seek(8 + header_size + start + offset)
                if bytes(data[offset:offset + width].tolist()) != stream.read(width):
                    raise ValueError(f"{path.name}: {name} differs at byte {offset}")
                samples += 1
    print(f"{path.name}: {len(tensors)} tensors, {samples} byte samples match", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("startup", type=Path)
    parser.add_argument("models", type=Path, nargs="+")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    config = json.loads(args.startup.read_text(encoding="utf-8-sig"))
    core = Path(config["inventory"]["core"])
    python = config["runtime"]["python"]
    if sha(python["path"]) != python["sha256"]:
        raise ValueError("Bound Comfy interpreter changed")
    if not args.child:
        command = [python["path"], "-I", "-B", "-X", "faulthandler", str(Path(__file__).resolve()),
                   "--child", str(args.startup.resolve()), *(str(p.resolve()) for p in args.models)]
        return subprocess.run(command, cwd=core, env=config["launch"]["environment"]).returncode

    if not sys.flags.isolated or Path(sys.executable).resolve() != Path(python["path"]).resolve():
        raise ValueError("The probe requires the bound isolated interpreter")
    # Comfy reads its flags on import. Preserve loader policy, including disable-mmap.
    sys.argv = [str(core/"main.py"), *config["launch"]["arguments"]]
    sys.path.insert(0, str(core))
    from comfy.options import enable_args_parsing
    enable_args_parsing()
    from comfy.utils import load_torch_file
    import torch

    for path in args.models:
        print(f"Opening {path.name}", flush=True)
        check_model(path, load_torch_file, torch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
