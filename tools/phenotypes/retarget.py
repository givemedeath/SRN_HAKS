"""Fit NWN skeletons and clone animation chains without changing clip timing."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

import numpy as np

NODE = re.compile(r"(?m)^\s*node\s+(\S+)\s+(\S+)\s*\n(.*?)^\s*endnode", re.S)


def nodes(text):
    result = {}
    for match in NODE.finditer(text.split("endmodelgeom", 1)[0]):
        body = match[3]
        parent = re.search(r"(?m)^\s*parent\s+(\S+)", body)
        position = re.search(r"(?m)^\s*position\s+([^\n]+)", body)
        orientation = re.search(r"(?m)^\s*orientation\s+([^\n]+)", body)
        result[match[2].lower()] = {"name": match[2], "parent": parent[1].lower() if parent else "null",
            "position": np.array([float(x) for x in position[1].split()]) if position else np.zeros(3),
            "orientation": [float(x) for x in orientation[1].split()] if orientation else [0, 0, 0, 0]}
    return result


def rotations(axis_angle):
    axis = np.array(axis_angle[:3], dtype=float)
    angle = axis_angle[3]
    norm = np.linalg.norm(axis)
    if abs(angle) < 1e-10 or norm < 1e-10:
        return np.eye(3)
    axis /= norm
    x, y, z = axis
    cross = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    return np.eye(3) * np.cos(angle) + (1 - np.cos(angle)) * np.outer(axis, axis) + np.sin(angle) * cross


def transforms(skeleton):
    out = {}
    def visit(name):
        if name in out:
            return out[name]
        node = skeleton[name]
        parent = node["parent"]
        matrix = np.eye(4)
        matrix[:3, :3] = rotations(node["orientation"])
        matrix[:3, 3] = node["position"]
        if parent in skeleton:
            matrix = visit(parent) @ matrix
        out[name] = matrix
        return matrix
    for name in skeleton:
        visit(name)
    return out


def geometry(model, skeleton, scale):
    lines = [f"beginmodelgeom {model}"]
    by_name = {data["name"].lower(): data for data in skeleton.values()}
    ordered = []
    visiting = set()
    completed = set()
    def visit(name):
        if name in completed:
            return
        if name in visiting:
            raise RuntimeError("Skeleton parent cycle: " + name)
        visiting.add(name)
        data = by_name[name]
        if data["parent"].lower() in by_name:
            visit(data["parent"].lower())
        ordered.append(data)
        visiting.remove(name)
        completed.add(name)
    for name in by_name:
        visit(name)
    for data in ordered:
        lines += [f"node dummy {data['name']}", f"  parent {data['parent']}",
                  "  position " + " ".join(f"{v:.9g}" for v in data["position"]),
                  "  orientation " + " ".join(f"{v:.9g}" for v in data["orientation"]), "endnode"]
    lines += [f"endmodelgeom {model}"]
    return "\n".join(lines)


def signature(text):
    clips = []
    for match in re.finditer(r"(?mis)^newanim\s+(\S+)\s+\S+\s*\n(.*?)^doneanim[^\n]*", text):
        body = match[2]
        fields = re.findall(r"(?m)^\s*(length|transtime|event)\s+([^\n]+)", body)
        clips.append((match[1], fields))
    return clips


def rotation_signature(text):
    """Freeze stock animation rotations independently of position fitting."""
    result = []
    for clip in re.finditer(r"(?mis)^newanim\s+(\S+)\s+\S+\s*\n(.*?)^doneanim[^\n]*", text):
        for node in NODE.finditer(clip[2]):
            for key in re.finditer(r"(?m)^\s*(orientation(?:bezier)?key)\s+(\d+)\s*\n((?:[ \t]+[\d+\-\.eE]+[^\n]*\n)+)", node[3]):
                rows = [tuple(float(v) for v in line.split()) for line in key[3].splitlines()]
                if len(rows) != int(key[2]):
                    raise RuntimeError("Unexpected rotation controller count")
                result.append((clip[1],node[2].lower(),key[1],rows))
    return result


def main():
    from pipeline import digest, save_json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--converted", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, default=Path("output/phenotypes/baseline"))
    args = parser.parse_args()
    report = json.loads((args.converted / "conversion.json").read_text())
    if not report.get("bindPoseNormalization"):
        raise RuntimeError("Normalize sliced generation geometry and joints to the stock bind pose before animation export")
    prefix = report["modelPrefix"]
    sex, phenotype = prefix[1], prefix[3]
    source_root = f"p{sex}h0"
    source = (args.baseline / "ascii" / (source_root + ".mdl")).read_text(encoding="cp1252")
    skeleton = nodes(source)
    old = {name: {**data, "position": data["position"].copy()} for name, data in skeleton.items()}
    height_scale = report["height"] / report.get("stockReferenceHeight", 2.0)
    targets = {k.lower(): np.array(v) for k, v in report["jointWorldNwn"].items()}
    targets["rootdummy"] = targets["torso_g"]
    targets["belt_g1"] = targets["torso_g"]
    for name, data in skeleton.items():
        data["position"] *= height_scale
        if name == source_root:
            data["name"] = prefix
        if data["parent"] == source_root:
            data["parent"] = prefix
    # Rename the dictionary root as well as its parent references.
    skeleton[prefix] = skeleton.pop(source_root)
    # Set anatomical nodes in parent-before-child order, keeping all auxiliary
    # weapon, robe, cape, emitter, and other attachment nodes in the hierarchy.
    for _ in range(len(skeleton)):
        moved = False
        world = transforms(skeleton)
        for name, target in targets.items():
            if name not in skeleton:
                raise RuntimeError("Missing skeleton attachment: " + name)
            parent = skeleton[name]["parent"]
            parent_world = world.get(parent, np.eye(4))
            local = (np.linalg.inv(parent_world) @ np.r_[target, 1])[:3]
            if np.linalg.norm(local - skeleton[name]["position"]) > 1e-9:
                skeleton[name]["position"] = local
                moved = True
        if not moved:
            break
    world = transforms(skeleton)
    for name, target in targets.items():
        if np.linalg.norm(world[name][:3, 3] - target) > 1e-6:
            raise RuntimeError("Joint fitting did not converge: " + name)
    base_top = ("a_ba" if sex == "m" else "a_fa") + ("2" if phenotype == "2" else "")
    baseline = json.loads((args.baseline / "baseline.json").read_text())
    chain = []
    current = base_top
    while current != "null":
        chain.append(current)
        current = baseline["animations"][current]["supermodel"]
    aliases = {name: f"sr_a{prefix[1:]}_{i}" for i, name in enumerate(chain)}
    output = args.converted / "ascii"
    receipts = []
    for name in chain:
        original = (args.baseline / "ascii" / (name + ".mdl")).read_text(encoding="cp1252")
        alias = aliases[name]
        old_geom = nodes(original)
        fitted = {}
        for key, data in old_geom.items():
            if key in old:
                data = {**skeleton[key], "position": skeleton[key]["position"].copy()}
            else:
                data = {**data, "position": data["position"] * height_scale}
            if key == name:
                data["name"] = alias
            if data["parent"] in (name, prefix):
                data["parent"] = alias
            fitted[key] = data
        parent = aliases.get(baseline["animations"][name]["supermodel"], "NULL")
        header = f"newmodel {alias}\nsetsupermodel {alias} {parent}\nclassification CHARACTER\nsetanimationscale 1\n"
        tail = original.split("endmodelgeom", 1)[1].split("\n", 1)[1]
        # Preserve the original animation controllers and event lines. Adjust
        # position controllers as scaled displacement around the original bind.
        def adjust_node(match):
            node_name = match[2].lower()
            body = match[3]
            old_position = old_geom.get(node_name, old.get(node_name, {})).get("position", np.zeros(3))
            new_position = fitted.get(node_name, {}).get("position", old_position * height_scale)
            delta = new_position - old_position * height_scale
            def keys(block):
                label, count, rows = block[1], int(block[2]), block[3]
                lines = rows.splitlines()
                if len(lines) != count:
                    raise RuntimeError("Unexpected position controller count")
                transformed = []
                for line in lines:
                    values = [float(v) for v in line.split()]
                    if len(values) not in (4, 10):
                        raise RuntimeError("Unexpected position controller arity")
                    values[1:4] = np.array(values[1:4]) * height_scale + delta
                    if len(values) == 10:
                        values[4:] = np.array(values[4:]) * height_scale
                    transformed.append("      " + " ".join(f"{v:.9g}" for v in values))
                return f"    {label} {count}\n" + "\n".join(transformed) + "\n"
            body = re.sub(r"(?m)^\s*(position(?:bezier)?key)\s+(\d+)\s*\n((?:[ \t]+[\d+\-\.eE]+[^\n]*\n)+)", keys, body)
            return f"  node {match[1]} {match[2]}\n{body}  endnode"
        tail = NODE.sub(adjust_node, tail)
        # Model names are separate tokens; replacement does not touch bone names.
        tail = re.sub(r"(?i)\b" + re.escape(name) + r"\b", alias, tail)
        result = header + geometry(alias, fitted, height_scale) + "\n" + tail
        if signature(result) != signature(original):
            raise RuntimeError("Animation names, timing, or events changed")
        if rotation_signature(result) != rotation_signature(original):
            raise RuntimeError("Stock animation rotation controllers changed")
        target_path = output / (alias + ".mdl")
        target_path.write_text(result, encoding="ascii")
        receipts.append({"source": name, "target": alias, "clips": len(signature(result)),
                         "sha256": digest(target_path)})
    root_path = output / (prefix + ".mdl")
    root_path.write_text(f"newmodel {prefix}\nsetsupermodel {prefix} {aliases[base_top]}\n"
                        f"classification CHARACTER\nsetanimationscale 1\n" +
                        geometry(prefix, skeleton, height_scale) + f"\ndonemodel {prefix}\n", encoding="ascii")
    save_json(args.converted / "retarget.json", {"model": prefix, "heightScale": height_scale,
              "animations": receipts, "timingEventsUnchanged": True,
              "rotationControllersUnchanged": True,
              "engineObserved": False, "joints": {k: list(v[:3, 3]) for k, v in world.items()}})
    print(json.dumps({"model": prefix, "animationResources": len(receipts),
                      "clips": sum(r["clips"] for r in receipts), "engineObserved": False}))


if __name__ == "__main__":
    main()
