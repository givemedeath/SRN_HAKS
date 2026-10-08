"""LEAN step 3: write the LEAN compiler inputs (basis) in the parent's per-node material layout.

Each parent ASCII model keeps every non-geometry line (node names, hierarchy, transforms, bitmap/materialname); each
trimesh node receives its LEAN arrays (repaired nodes take precedence over reduced ones). Render vertices are written
1:1 as verts, normals and tverts so the native compiler's per-render-vertex tangent generation sees exactly this
vertex set; faces keep the node's dominant parent smoothing group and material id. Every parent material resource the
nodes reference is carried unchanged (hard-linked when possible). The result is compiled once (native_compile.py) to
obtain the compiler tangent basis the LEAN normal maps are then encoded against.

Usage: lean_compose_basis.py --parent <manifest> --reduction <reduction.json> [--reduction ...] [--repair <repair.json>]
       --output <fresh dir>
"""
import argparse
import os
from pathlib import Path
import shutil

import numpy as np

import lean_common as L
from nwn_ascii_trimesh import AsciiModel, fmt

SECTIONS = ('verts', 'normals', 'tverts', 'faces')


def skeleton(lines):
    """ASCII lines with the four geometry sections collapsed to their keyword (non-geometry text identity)."""
    out = []; skip = 0
    for line in lines:
        if skip:
            skip -= 1; continue
        parts = line.split()
        if len(parts) == 2 and parts[0] in SECTIONS and parts[1].isdigit():
            skip = int(parts[1]); out.append(parts[0]); continue
        out.append(line)
    return out


def node_rows(arrays, group, material_id):
    P = arrays['position'].astype(np.float64); N = arrays['normal'].astype(np.float64); U = arrays['uv'].astype(np.float64)
    F = arrays['faces'].astype(np.int64); N = N/np.linalg.norm(N, axis=1)[:, None]
    return {'verts': [' '.join(fmt(x) for x in v) for v in P], 'normals': [' '.join(fmt(x) for x in v) for v in N],
            'tverts': [fmt(t[0])+' '+fmt(t[1])+' 0' for t in U],
            'faces': ['%d %d %d %d %d %d %d %d' % (f[0], f[1], f[2], group, f[0], f[1], f[2], material_id) for f in F]}


def write_part(parent_ascii, nodes, destination):
    """nodes: {node: npz arrays}. Returns per-node triangle/vertex counts after an independent re-read."""
    model = AsciiModel.read(parent_ascii); before = list(model.lines); rows = {}
    L.require({node.name for node in model.trimeshes()} == set(nodes), 'LEAN node inventory differs from the parent model')
    for node in [n.name for n in model.trimeshes()]:
        _, _, _, faces = model.arrays(model.node(node))
        group, material_id = L.mode(faces[:, 3]), L.mode(faces[:, 7])
        for key, values in node_rows(nodes[node], group, material_id).items():
            model.replace_section(model.node(node), key, values)
        rows[node] = {'smoothingGroup': group, 'materialId': material_id}
    L.require(skeleton(before) == skeleton(model.lines), 'Non-geometry ASCII text changed')
    model.write(destination); check = AsciiModel.read(destination)
    for node, arrays in nodes.items():
        V, N, T, F = check.arrays(check.node(node))
        L.require(np.array_equal(V.astype(np.float32), arrays['position'].astype(np.float32)) and
                  np.array_equal(T[:, :2].astype(np.float32), arrays['uv'].astype(np.float32)) and
                  np.array_equal(F[:, :3], arrays['faces'].astype(np.int64)) and np.array_equal(F[:, 4:7], arrays['faces'].astype(np.int64)),
                  'Written LEAN ASCII differs from its arrays: '+node)
        rows[node].update(triangles=int(len(F)), vertices=int(len(V)))
    return rows


def link_or_copy(source, destination):
    try:
        os.link(source, destination); return 'hardlink'
    except OSError:
        shutil.copyfile(source, destination); return 'copy'


def compose(parent_path, reduction_paths, output, repair_path=None):
    frozen = L.Frozen(); manifest = L.read_json(frozen.take(parent_path))
    L.require(manifest.get('kind') == 'lean-parent-representation', 'LEAN parent representation required')
    lean = {}; reductions = []
    for path in reduction_paths:
        receipt = L.read_json(frozen.take(path)); L.require(receipt.get('kind') == 'lean-part-reduction', 'LEAN reduction receipt required')
        L.require(receipt['parent']['sha256'] == L.sha(parent_path), 'Reduction descends from a different parent representation')
        for part, row in receipt['parts'].items():
            for node, entry in row['nodes'].items():
                L.require(node not in lean, 'Node reduced twice: '+node); lean[node] = ('reduction', entry['arrays'])
        reductions.append({**L.pin(path), 'parts': sorted(receipt['parts'])})
    repaired = []
    if repair_path is not None:
        repair = L.read_json(frozen.take(repair_path)); L.require(repair.get('kind') == 'lean-border-repair', 'LEAN repair receipt required')
        for node, entry in repair['nodes'].items():
            L.require(node in lean and lean[node][1] == entry['input'], 'Repair applies to a different LEAN node: '+node)
            lean[node] = ('repair', entry['arrays']); repaired.append(node)
    output = L.fresh(output); (output/'ascii').mkdir(); (output/'resources').mkdir()
    parts = {}; resources = {}
    for part in L.PARTS:
        row = manifest['parts'][part]; model = row['model']
        nodes = {}
        for mesh in row['meshes']:
            L.require(mesh['mesh'] in lean, 'Missing LEAN node: '+mesh['mesh'])
            nodes[mesh['mesh']] = np.load(frozen.pinned(lean[mesh['mesh']][1]))
            for key in ('mtr', 'normal', 'roughness', 'plt', 'garmentColor'):
                value = mesh.get(key)
                if isinstance(value, dict):
                    source = frozen.pinned(value); name = source.name.lower()
                    L.require(resources.get(name, value['sha256']) == value['sha256'], 'Conflicting parent resource: '+name)
                    resources[name] = value['sha256']
                    if not (output/'resources'/name).exists(): link_or_copy(source, output/'resources'/name)
        parent_ascii = frozen.pinned(row['ascii'])
        counts = write_part(parent_ascii, nodes, output/'ascii'/(model+'.mdl'))
        parts[part] = {'model': model, 'ascii': L.pin(output/'ascii'/(model+'.mdl')), 'parentAscii': row['ascii'],
                       'nodes': {node: {**counts[node], 'source': lean[node][0], 'arrays': lean[node][1]} for node in counts},
                       'triangles': sum(value['triangles'] for value in counts.values())}
    for name, digest in resources.items():
        L.require(L.sha(output/'resources'/name) == digest, 'Carried parent resource differs: '+name)
    receipt = {'schemaVersion': 1, 'kind': 'lean-basis-composition', 'sex': manifest['sex'], 'prefix': manifest['prefix'],
               'parent': L.pin(parent_path), 'reductions': reductions, 'repair': L.pin(repair_path) if repair_path else None,
               'repairedNodes': sorted(repaired), 'parts': parts, 'resourceHashes': dict(sorted(resources.items())),
               'materialLayout': 'parent-per-node (pre-atlas)', 'nativeCompiled': False,
               'frozenInputs': {**frozen.verify(), **L.helper_pins('lean_compose_basis.py', 'nwn_ascii_trimesh.py')},
               'selected': False, 'clientAccepted': False, 'productionAccepted': False}
    return L.save_json(output/'basis.json', receipt)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path, required=True); parser.add_argument('--reduction', type=Path, action='append', required=True)
    parser.add_argument('--repair', type=Path); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); print(compose(args.parent, args.reduction, args.output, args.repair))
