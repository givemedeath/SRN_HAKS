"""Stock phenotype body reference: rigid *001 parts on their bones, landmarks and chains.

Pure numpy over extracted ASCII. Used for fitting, clearance, weight cages and
penetration diagnostics. Measurements only.
"""
from pathlib import Path

import numpy as np

import mdl_ascii

ATTACH = {"head": "head_g", "neck": "neck_g", "chest": "torso_g", "pelvis": "pelvis_g", "belt": "belt_g",
          "bicepl": "lbicep_g", "bicepr": "rbicep_g", "forel": "lforearm_g", "forer": "rforearm_g",
          "handl": "lhand_g", "handr": "rhand_g", "shol": "lshoulder_g", "shor": "rshoulder_g",
          "legl": "lthigh_g", "legr": "rthigh_g", "shinl": "lshin_g", "shinr": "rshin_g",
          "footl": "lfoot_g", "footr": "rfoot_g"}
CHAINS = {"arm_l": ["lbicep_g", "lforearm_g", "lhand_g"], "arm_r": ["rbicep_g", "rforearm_g", "rhand_g"],
          "leg_l": ["lthigh_g", "lshin_g", "lfoot_g"], "leg_r": ["rthigh_g", "rshin_g", "rfoot_g"]}
SKIN_BONES = ["rootdummy", "torso_g", "pelvis_g", "neck_g", "head_g", "lbicep_g", "lforearm_g", "lhand_g",
              "rbicep_g", "rforearm_g", "rhand_g", "lthigh_g", "lshin_g", "lfoot_g", "rthigh_g", "rshin_g", "rfoot_g"]


class Body:
    def __init__(self, ascii_directory, prefix="pmh0", parts=None):
        self.directory = Path(ascii_directory)
        self.prefix = prefix
        self.model = mdl_ascii.read(self.directory / (prefix + ".mdl"))
        self.bind = mdl_ascii.bind_frames(self.model)
        self.parts = {}
        for part, bone in ATTACH.items():
            if parts is not None and part not in parts:
                continue
            path = self.directory / f"{prefix}_{part}001.mdl"
            if not path.is_file():
                continue
            model = mdl_ascii.read(path)
            local = mdl_ascii.bind_frames(model)
            meshes = [n for n in model.nodes if n.kind in mdl_ascii.MESHES and "faces" in n.arrays]
            verts, faces, offset = [], [], 0
            for node in meshes:
                v = np.asarray(node.arrays["verts"], float)
                verts.append((local[node.key] @ np.c_[v, np.ones(len(v))].T).T[:, :3])
                faces.append(np.asarray(node.arrays["faces"])[:, :3] + offset)
                offset += len(v)
            if verts:
                self.parts[part] = {"bone": bone, "local": np.vstack(verts), "faces": np.vstack(faces)}

    def joint(self, bone):
        return self.bind[bone.lower()][:3, 3].copy()

    def posed(self, frames=None):
        """World vertices/faces of all parts under bone frames (bind when None), with owning bone per face."""
        frames = self.bind if frames is None else frames
        verts, faces, owners, offset = [], [], [], 0
        for part, row in self.parts.items():
            matrix = frames[row["bone"]]
            v = (matrix @ np.c_[row["local"], np.ones(len(row["local"]))].T).T[:, :3]
            verts.append(v)
            faces.append(row["faces"] + offset)
            owners += [row["bone"]] * len(row["faces"])
            offset += len(v)
        return np.vstack(verts), np.vstack(faces), np.array(owners)

    def landmarks(self):
        verts, _, _ = self.posed()
        foot = np.vstack([self.posed_part(p) for p in ("footl", "footr") if p in self.parts])
        marks = {name: self.joint(bone).tolist() for name, bone in
                 [("pelvis", "pelvis_g"), ("neck", "neck_g"), ("head", "head_g"),
                  ("shoulderL", "lbicep_g"), ("shoulderR", "rbicep_g"), ("elbowL", "lforearm_g"),
                  ("elbowR", "rforearm_g"), ("wristL", "lhand_g"), ("wristR", "rhand_g"), ("hipL", "lthigh_g"),
                  ("hipR", "rthigh_g"), ("kneeL", "lshin_g"), ("kneeR", "rshin_g"), ("ankleL", "lfoot_g"),
                  ("ankleR", "rfoot_g")]}
        marks["floor"] = float(foot[:, 2].min())
        marks["top"] = float(verts[:, 2].max())
        for side, part in (("L", "handl"), ("R", "handr")):
            if part in self.parts:
                hand = self.posed_part(part)
                marks["fingertip" + side] = hand[np.argmin(hand[:, 2])].tolist()
        return marks

    def posed_part(self, part, frames=None):
        frames = self.bind if frames is None else frames
        row = self.parts[part]
        return (frames[row["bone"]] @ np.c_[row["local"], np.ones(len(row["local"]))].T).T[:, :3]


def closest_on_triangles(points, verts, faces, chunk=2048):
    """Closest point, distance, face index and signed side (+outside by face normal) for each point."""
    a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    normals = np.cross(b - a, c - a)
    normals /= np.maximum(np.linalg.norm(normals, axis=1), 1e-12)[:, None]
    best_d = np.full(len(points), np.inf)
    best_p = np.zeros((len(points), 3))
    best_f = np.zeros(len(points), dtype=np.int64)
    for start in range(0, len(points), chunk):
        p = points[start:start + chunk][:, None, :]
        ab, ac, ap = b - a, c - a, p - a
        d1, d2 = (ab * ap).sum(-1), (ac * ap).sum(-1)
        bp = p - b
        d3, d4 = (ab * bp).sum(-1), (ac * bp).sum(-1)
        cp = p - c
        d5, d6 = (ab * cp).sum(-1), (ac * cp).sum(-1)
        va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2
        denominator = np.where(np.abs(va + vb + vc) < 1e-20, 1e-20, va + vb + vc)
        v, w = vb / denominator, vc / denominator
        result = a + ab * v[..., None] + ac * w[..., None]
        # Region tests (Ericson): vertex and edge regions override the interior projection.
        cases = [((d1 <= 0) & (d2 <= 0), a + 0 * ap),
                 ((d3 >= 0) & (d4 <= d3), b + 0 * ap),
                 ((d6 >= 0) & (d5 <= d6), c + 0 * ap)]
        vab = (vc <= 0) & (d1 >= 0) & (d3 <= 0)
        cases.append((vab, a + ab * (d1 / np.where(d1 - d3 == 0, 1e-20, d1 - d3))[..., None]))
        vac = (vb <= 0) & (d2 >= 0) & (d6 <= 0)
        cases.append((vac, a + ac * (d2 / np.where(d2 - d6 == 0, 1e-20, d2 - d6))[..., None]))
        vbc = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0)
        tbc = (d4 - d3) / np.where((d4 - d3) + (d5 - d6) == 0, 1e-20, (d4 - d3) + (d5 - d6))
        cases.append((vbc, b + (c - b) * tbc[..., None]))
        for mask, value in reversed(cases):
            result = np.where(mask[..., None], value, result)
        distance = np.linalg.norm(result - p, axis=-1)
        index = distance.argmin(axis=1)
        rows = np.arange(len(index))
        best_d[start:start + chunk] = distance[rows, index]
        best_p[start:start + chunk] = result[rows, index]
        best_f[start:start + chunk] = index
    side = np.sign(((points - best_p) * normals[best_f]).sum(1))
    return best_p, best_d, best_f, side
