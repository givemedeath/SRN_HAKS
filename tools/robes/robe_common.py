"""Shared hashing, pinning and fresh-write helpers for the Meshy robe trial.

These helpers make no paid requests and grant no visual, native, client or
production approval. Every robe receipt states those flags explicitly.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1]
REPO = TOOLS.parent
for entry in (TOOLS, TOOLS / "phenotypes"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

FLAGS = {"referenceApproved": False, "nativeValidated": False, "clientValidated": False,
         "productionAccepted": False, "gameClientTesting": False}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def pin(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha(path)}


def read_pinned(path):
    """Read a file once; return its bytes and the pin of exactly those bytes (no read/hash gap)."""
    path = Path(path).resolve()
    data = path.read_bytes()
    return data, {"path": str(path), "sha256": hashlib.sha256(data).hexdigest()}


def skin_colour(rgb):
    """Exposed-skin colour rule on (n, 3) base-colour values in 0-1 (display-encoded): warm, moderately saturated."""
    import numpy as np
    rgb = np.asarray(rgb, dtype=float)
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    saturation = (rgb.max(1) - rgb.min(1)) / np.maximum(rgb.max(1), 1e-6)
    return (r > g) & (g > b) & (saturation > 0.18) & (saturation < 0.75) & (rgb.max(1) > 0.08) & ((r - b) > 0.05)


def verify_pins(pins):
    for item in pins:
        require(Path(item["path"]).is_file(), "Pinned input missing: " + item["path"])
        require(sha(item["path"]) == item["sha256"], "Pinned input changed: " + item["path"])


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_fresh(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")
    return pin(path)


def fresh_directory(path):
    path = Path(path).resolve()
    require(not path.exists(), "Fresh output directory required: " + str(path))
    path.mkdir(parents=True)
    return path


def utc():
    return datetime.now(timezone.utc).isoformat()
