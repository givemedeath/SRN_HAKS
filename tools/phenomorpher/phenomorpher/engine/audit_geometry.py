"""Audit replacement body-part surfaces for coincident triangles and roots."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

import numpy as np


def arrays(body, field):
    match = re.search(r"(?m)^\s*" + field + r"\s+(\d+)\s*\n", body)
    if not match:
        return []
    return [[float(v) for v in line.split()] for line in body[match.end():].splitlines()[:int(match[1])]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("converted", type=Path)
    args = parser.parse_args()
    report = json.loads((args.converted / "conversion.json").read_text())
    joints = dict(head="head_g", neck="neck_g", chest="torso_g", pelvis="pelvis_g",
                  bicepl="Lbicep_g", bicepr="Rbicep_g", forel="lforearm_g", forer="rforearm_g",
                  handl="lhand_g", handr="rhand_g", legl="lthigh_g", legr="rthigh_g",
                  shinl="lshin_g", shinr="rshin_g", footl="lfoot_g", footr="rfoot_g")
    surfaces = defaultdict(list)
    entries = []
    for part in report["parts"]:
        model_path = args.converted / "ascii" / (part["model"] + ".mdl")
        text = model_path.read_text()
        node = joints[part["part"]]
        origin = np.array(report["jointWorldNwn"][node])
        triangles = degenerate = 0
        for match in re.finditer(r"(?ms)^node trimesh (\S+)\n(.*?)^endnode", text):
            verts = np.array(arrays(match[2], "verts")) + origin
            for row in arrays(match[2], "faces"):
                coords = verts[np.array(row[:3], dtype=int)]
                if np.linalg.norm(np.cross(coords[1]-coords[0], coords[2]-coords[0])) < 1e-12:
                    degenerate += 1
                key = tuple(sorted(tuple(np.round(v, 6)) for v in coords))
                surfaces[key].append((part["part"], match[1]))
                triangles += 1
        entries.append({"part": part["part"], "triangles": triangles, "degenerate": degenerate,
                        "model":model_path.name,"sourceSha256":hashlib.sha256(model_path.read_bytes()).hexdigest()})
    duplicates = [v for v in surfaces.values() if len(v) > 1]
    result = {"parts": entries, "uniqueTriangles": len(surfaces),
              "coincidentTriangleGroups": len(duplicates), "examples": duplicates[:20]}
    (args.converted / "surface-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
