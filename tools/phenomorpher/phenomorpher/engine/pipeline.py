"""Extracted measurement utilities; no generation service or legacy stature defaults."""
import hashlib
import json
from pathlib import Path
import numpy as np


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def detect_view_spans(image):
    """Read-only view detection shared by generation and measurement reviews."""
    if image.size != (1916, 821):
        raise ValueError(f"Review unfamiliar sheet dimensions: {image.size}")
    arr = np.array(image.convert("RGB")).copy()
    rgb = arr.astype(np.int16)
    cyan = (rgb[:, :, 1] > rgb[:, :, 0] + 5) & (rgb[:, :, 2] > rgb[:, :, 0] + 5)
    arr[cyan] = 0
    profile = (arr[70:755].max(axis=2) > 20).sum(axis=0) > 8
    starts = np.flatnonzero(profile & ~np.r_[False, profile[:-1]])
    ends = np.flatnonzero(profile & ~np.r_[profile[1:], False]) + 1
    spans = []
    for start, end in zip(starts, ends):
        if spans and start - spans[-1][1] < 25:
            spans[-1][1] = int(end)
        else:
            spans.append([int(start), int(end)])
    spans = [s for s in spans if s[1] - s[0] > 60]
    if len(spans) != 4:
        raise ValueError(f"Review ambiguous view spans: {spans}")
    return spans
