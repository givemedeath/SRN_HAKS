"""Measure original Human rigid-part overlap in the supermodel bind pose."""
import argparse
import json
from pathlib import Path
import re
from collections import Counter

import numpy as np

from audit_geometry import arrays
from retarget import nodes, transforms

JOINTS = dict(head="head_g", neck="neck_g", chest="torso_g", pelvis="pelvis_g",
              bicepl="Lbicep_g", bicepr="Rbicep_g", forel="lforearm_g", forer="rforearm_g",
              handl="lhand_g", handr="rhand_g", legl="lthigh_g", legr="rthigh_g",
              shinl="lshin_g", shinr="rshin_g", footl="lfoot_g", footr="rfoot_g")
JOINTS = {k: v.lower() for k, v in JOINTS.items()}
PAIRS = [("chest", "neck"), ("neck", "head"), ("chest", "pelvis"),
         ("chest", "bicepl"), ("chest", "bicepr"), ("pelvis", "legl"), ("pelvis", "legr"),
         ("bicepl", "forel"), ("bicepr", "forer"), ("forel", "handl"), ("forer", "handr"),
         ("legl", "shinl"), ("legr", "shinr"), ("shinl", "footl"), ("shinr", "footr")]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("--sex", choices=("m", "f"), default="m")
    args = parser.parse_args()
    prefix = "p" + args.sex + "h0"
    skeleton = nodes((args.baseline / "ascii" / (prefix + ".mdl")).read_text())
    world = transforms(skeleton)
    vertices = {}
    parts = []
    for part, joint in JOINTS.items():
        text = (args.baseline / "ascii" / (prefix + "_" + part + "001.mdl")).read_text()
        coords, edges, offset = [], Counter(), 0
        for match in re.finditer(r"(?ms)^node (?:trimesh|skinmesh|skin|danglymesh) (\S+)\n(.*?)^endnode", text):
            verts = np.array(arrays(match[2], "verts"))
            coords.extend((world[joint] @ np.c_[verts, np.ones(len(verts))].T).T[:, :3])
            for face in arrays(match[2], "faces"):
                ids = [int(v) + offset for v in face[:3]]
                for i in range(3):
                    edges[tuple(sorted((ids[i], ids[(i+1)%3])))] += 1
            offset += len(verts)
        vertices[part] = np.array(coords)
        parts.append({"part": part, "vertices": len(coords), "boundaryEdges": sum(v == 1 for v in edges.values()),
                      "nonmanifoldEdges": sum(v > 2 for v in edges.values())})
    pairs = []
    for parent, child in PAIRS:
        origin = world[JOINTS[child]][:3, 3]
        axis = origin - world[JOINTS[parent]][:3, 3]
        if np.linalg.norm(axis) < 1e-9:
            axis = np.array([0., 0., -1.])
        axis /= np.linalg.norm(axis)
        p = (vertices[parent] - origin) @ axis
        c = (vertices[child] - origin) @ axis
        pairs.append({"parent": parent, "child": child, "axisNwn": axis.tolist(),
                      "parentPastJoint": round(float(p.max()), 6),
                      "childBeforeJoint": round(float(-c.min()), 6),
                      "axialOverlap": round(float(p.max()-c.min()), 6)})
    result = {"skeleton": prefix, "parts": parts, "connections": pairs,
              "note": "Axial interval overlap, not a volumetric intersection or an animation pass."}
    path = args.baseline / (prefix + "-joint-overlap.json")
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
