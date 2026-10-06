"""Skin-aware ASCII NWN model reader and writer for robe parts.

Parses geometry nodes (dummy, trimesh, danglymesh, skin) with their arrays and
keeps scalar properties in source order. Animation blocks are retained as raw
text for the shared rigid samplers. Reading and writing grant no approval.
"""
import re

import numpy as np

import robe_common  # noqa: F401  (adds tools/phenotypes to sys.path)
from retarget import rotations as rotation

COUNTED = {"verts", "faces", "tverts", "tverts1", "tverts2", "tverts3", "weights", "constraints", "colors",
           "texindices0", "texindices1", "texindices2", "texindices3"}
MESHES = {"trimesh", "danglymesh", "skin"}
CLIP = re.compile(r"(?mis)^newanim\s+(\S+)\s+(\S+)\s*\n(.*?)^doneanim[^\n]*")


class Node:
    def __init__(self, kind, name):
        self.kind, self.name = kind.lower(), name
        self.parent = "NULL"
        self.position = np.zeros(3)
        self.orientation = np.zeros(4)
        self.properties = []
        self.arrays = {}

    @property
    def key(self):
        return self.name.lower()

    def get(self, field, default=None):
        for key, value in self.properties:
            if key.lower() == field:
                return value
        return default

    def set(self, field, value):
        for index, (key, _) in enumerate(self.properties):
            if key.lower() == field:
                self.properties[index] = (key, value)
                return
        self.properties.append((field, value))


class Model:
    def __init__(self, name):
        self.name = name
        self.supermodel = "NULL"
        self.classification = "Character"
        self.animation_scale = "1.0"
        self.header = []
        self.nodes = []
        self.animations = []

    def node(self, name):
        for node in self.nodes:
            if node.key == name.lower():
                return node
        raise KeyError(name)

    def names(self):
        return [node.key for node in self.nodes]


def _numeric(token):
    try:
        float(token)
        return True
    except ValueError:
        return False


def _floats(line):
    return [float(value) for value in line.split()]


def _read_array(lines, index, field, count):
    rows = []
    while len(rows) < count:
        if index >= len(lines):
            raise ValueError("Truncated array: " + field)
        text = lines[index].split("#", 1)[0].strip()
        index += 1
        if text:
            rows.append(text)
    if field == "weights":
        parsed = []
        for row in rows:
            tokens = row.split()
            if len(tokens) % 2:
                raise ValueError("Odd weight row: " + row)
            parsed.append([(tokens[i], float(tokens[i + 1])) for i in range(0, len(tokens), 2)])
        return parsed, index
    if field == "faces":
        return np.array([[int(float(value)) for value in row.split()[:8]] for row in rows], dtype=np.int64), index
    return np.array([_floats(row) for row in rows], dtype=float), index


def parse(text):
    geometry, _, tail = text.partition("endmodelgeom")
    lines = geometry.splitlines()
    model = None
    index = 0
    while index < len(lines):
        raw = lines[index]
        index += 1
        stripped = raw.split("#", 1)[0].strip()
        if not stripped:
            continue
        tokens = stripped.split()
        head = tokens[0].lower()
        if head == "newmodel":
            model = Model(tokens[1])
        elif head == "setsupermodel":
            model.supermodel = tokens[2]
        elif head == "classification":
            model.classification = tokens[1]
        elif head == "setanimationscale":
            model.animation_scale = tokens[1]
        elif head == "beginmodelgeom":
            continue
        elif head == "node":
            node = Node(tokens[1], tokens[2])
            while True:
                if index >= len(lines):
                    raise ValueError("Unterminated node: " + node.name)
                text_line = lines[index].split("#", 1)[0].strip()
                index += 1
                if not text_line:
                    continue
                parts = text_line.split(None, 1)
                field = parts[0].lower()
                if _numeric(field):
                    raise ValueError(f"Unparsed array rows in node {node.name}: an unsupported counted field precedes them")
                value = parts[1].strip() if len(parts) > 1 else ""
                if field == "endnode":
                    break
                if field == "parent":
                    node.parent = value
                elif field == "position":
                    node.position = np.array(_floats(value))
                elif field == "orientation":
                    node.orientation = np.array(_floats(value))
                elif field in COUNTED:
                    count = int(float(value.split()[0]))
                    node.arrays[field], index = _read_array(lines, index, field, count)
                else:
                    node.properties.append((parts[0], value))
            model.nodes.append(node)
    if model is None:
        raise ValueError("No newmodel declaration")
    for match in CLIP.finditer(tail):
        length = re.search(r"(?mi)^\s*length\s+(\S+)", match[3])
        model.animations.append({"name": match[1], "model": match[2], "text": match[0],
                                 "length": float(length[1]) if length else None})
    return model


def read(path):
    with open(path, encoding="cp1252") as stream:
        return parse(stream.read())


def _number(value):
    text = f"{float(value):.9g}"
    return "0.0" if text in ("-0", "0") else text


def _array_lines(field, values, decimals):
    if field == "weights":
        fmt = "{:." + str(decimals) + "f}"
        return ["  ".join(f"{bone} {fmt.format(weight)}" for bone, weight in row) for row in values]
    if field == "faces":
        return [" ".join(str(int(value)) for value in row) for row in values]
    return [" ".join(_number(value) for value in row) for row in values]


def dumps(model, *, weight_decimals=6, animations=True):
    out = ["#MAXMODEL ASCII", f"newmodel {model.name}", f"setsupermodel {model.name} {model.supermodel}",
           f"classification {model.classification}", f"setanimationscale {model.animation_scale}",
           f"beginmodelgeom {model.name}"]
    for node in model.nodes:
        out.append(f"node {node.kind} {node.name}")
        out.append(f"  parent {node.parent}")
        if node.kind != "dummy" or np.any(node.position) or np.any(node.orientation):
            out.append("  position " + " ".join(_number(v) for v in node.position))
            out.append("  orientation " + " ".join(_number(v) for v in node.orientation))
        for key, value in node.properties:
            out.append(f"  {key} {value}".rstrip())
        for field in ("verts", "faces", "tverts", "tverts1", "tverts2", "tverts3", "colors", "constraints",
                      "weights", "texindices0", "texindices1", "texindices2", "texindices3"):
            if field in node.arrays:
                values = node.arrays[field]
                out.append(f"  {field} {len(values)}")
                out.extend("    " + line for line in _array_lines(field, values, weight_decimals))
        out.append("endnode")
    out.append(f"endmodelgeom {model.name}")
    if animations:
        out.extend(animation["text"] for animation in model.animations)
    out.append(f"donemodel {model.name}")
    return "\n".join(out) + "\n"


def write(path, model, **options):
    with open(path, "x", encoding="cp1252", newline="\n") as stream:
        stream.write(dumps(model, **options))


def bind_frames(model, base=None):
    """World bind matrices for every node; base supplies inherited parents by name."""
    table = {node.key: node for node in model.nodes}
    inherited = {} if base is None else base
    output, visiting = {}, set()

    def visit(name):
        if name in output:
            return output[name]
        if name not in table:
            if name in inherited:
                return inherited[name]
            raise ValueError("Unresolved bind parent: " + name)
        if name in visiting:
            raise ValueError("Bind hierarchy cycle: " + name)
        visiting.add(name)
        node = table[name]
        local = np.eye(4)
        local[:3, :3] = rotation(node.orientation)
        local[:3, 3] = node.position
        parent = node.parent.lower()
        matrix = local if parent == "null" else visit(parent) @ local
        visiting.discard(name)
        output[name] = matrix
        return matrix

    for name in table:
        visit(name)
    return output


def skin_matrix(node, bones=None):
    """Dense weights for a skin node, columns ordered by first appearance unless bones given."""
    from robe_weights import from_pairs
    rows = node.arrays.get("weights")
    if rows is None:
        raise ValueError("Node has no weights: " + node.name)
    if bones is None:
        seen = []
        for row in rows:
            for bone, _ in row:
                if bone.lower() not in seen:
                    seen.append(bone.lower())
        bones = seen
    return from_pairs([[(bone.lower(), weight) for bone, weight in row] for row in rows], bones)
