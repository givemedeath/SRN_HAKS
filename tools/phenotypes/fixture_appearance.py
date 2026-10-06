"""Apply a target's approved runtime sizing to its stock appearance row."""
import hashlib
import math
from pathlib import Path


def patch_appearance(path: Path, target: dict) -> str:
    lines = path.read_text(encoding="cp1252").splitlines()
    header = next((i for i, line in enumerate(lines) if "HEIGHT" in line.split() and "WEAPONSCALE" in line.split()), None)
    if header is None:
        raise ValueError(f"Missing appearance scale columns: {path}")
    columns = lines[header].split()
    scaled = ["WEAPONSCALE", "WING_TAIL_SCALE", "HELMET_SCALE_M", "HELMET_SCALE_F", "WALKDIST", "RUNDIST", "CREPERSPACE", "PREFATCKDIST"]
    missing = set(["HEIGHT", *scaled]) - set(columns)
    if missing:
        raise ValueError(f"Missing appearance scale columns: {sorted(missing)}")
    row = str(target["identity"]["appearanceRow"])
    matches = [i for i in range(header + 1, len(lines)) if lines[i].split() and lines[i].split()[0] == row]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one appearance row {row}")
    index = matches[0]
    values = lines[index].split()[1:]
    if len(values) != len(columns):
        raise ValueError(f"Truncated appearance row {row}")
    scale = float(target["rig"]["runtimeScale"])
    height = float(target["heightMeters"])
    if not (math.isfinite(scale) and scale > 0 and math.isfinite(height) and height > 0):
        raise ValueError("Invalid approved runtime scale or height")
    for column in scaled:
        value = float(values[columns.index(column)]) * scale
        if not math.isfinite(value):
            raise ValueError(f"Invalid appearance value: {column}")
        values[columns.index(column)] = format(value, ".15g")
    values[columns.index("HEIGHT")] = format(height, ".15g")
    lines[index] = row + " " + " ".join(values)
    path.write_text("\n".join(lines) + "\n", encoding="cp1252")
    return hashlib.sha256(path.read_bytes()).hexdigest()
