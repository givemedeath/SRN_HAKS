"""Head-local body neck reference for mesh.neck.cut: the body's neck part placed in the head part's frame.

The head and neck parts attach to the skeleton's head_g and neck_g nodes, so inv(head_g) @ neck_g carries the neck
part into the head frame (NWN: face +y, up +z). Inputs are ASCII models (decompile binaries first); the reference
pins them and records the transform, so a cut is bound to exactly the body it was reviewed against."""
import argparse
import math
from pathlib import Path
import numpy as np
from .common import require, pin, write

KIND = 'srn-head-body-neck'
MESHES = ('trimesh', 'danglymesh', 'skin')


def _nodes(text):
    """name -> (type, parent, position, orientation axis-angle) for every node of an ASCII model."""
    nodes = {}; current = None
    for line in text.splitlines():
        t = line.split()
        if not t: continue
        key = t[0].lower()
        if key == 'node' and len(t) >= 3:
            current = {'type': t[1].lower(), 'parent': None, 'position': np.zeros(3), 'orientation': np.array([0., 0., 1., 0.])}
            nodes[t[2].lower()] = current
        elif key == 'endnode': current = None
        elif current is not None and key == 'parent' and len(t) == 2: current['parent'] = None if t[1].upper() == 'NULL' else t[1].lower()
        elif current is not None and key == 'position' and len(t) == 4: current['position'] = np.array(list(map(float, t[1:])))
        elif current is not None and key == 'orientation' and len(t) == 5: current['orientation'] = np.array(list(map(float, t[1:])))
    return nodes


def _local(node):
    x, y, z, angle = node['orientation']; axis = np.array([x, y, z]); length = np.linalg.norm(axis); matrix = np.eye(4)
    if length > 1e-12 and abs(angle) > 1e-12:
        x, y, z = axis/length; c, s = math.cos(angle), math.sin(angle); C = 1-c
        matrix[:3, :3] = [[c+x*x*C, x*y*C-z*s, x*z*C+y*s], [y*x*C+z*s, c+y*y*C, y*z*C-x*s], [z*x*C-y*s, z*y*C+x*s, c+z*z*C]]
    matrix[:3, 3] = node['position']; return matrix


def world(nodes, name):
    """World matrix of a node: parents' local transforms composed down to it."""
    chain = []; seen = set()
    while name is not None:
        require(name in nodes and name not in seen, 'Skeleton node chain is broken at '+str(name))
        seen.add(name); chain.append(nodes[name]); name = nodes[name]['parent']
    matrix = np.eye(4)
    for node in reversed(chain): matrix = matrix@_local(node)
    return matrix


def mesh_parts(text):
    """(vertices, faces) of every mesh node in a rigid part model, each node's own transform applied."""
    nodes = _nodes(text); lines = text.splitlines(); vertices = []; faces = []; name = None; kind = None; i = 0
    while i < len(lines):
        t = lines[i].split(); key = t[0].lower() if t else ''
        if key == 'node' and len(t) >= 3: kind, name = t[1].lower(), t[2].lower()
        elif key == 'verts' and kind in MESHES:
            n = int(t[1]); local = np.array([list(map(float, lines[i+1+j].split()[:3])) for j in range(n)])
            matrix = world(nodes, name); base = sum(len(v) for v in vertices)
            vertices.append(local@matrix[:3, :3].T+matrix[:3, 3]); i += n
        elif key == 'faces' and kind in MESHES:
            n = int(t[1]); faces.append(np.array([list(map(int, lines[i+1+j].split()[:3])) for j in range(n)])+base); i += n
        i += 1
    require(vertices and faces, 'Neck model has no mesh')
    return np.concatenate(vertices), np.concatenate(faces)


def build(skeleton, neck, output, body=''):
    """Write the head-local neck reference; the neck part's own root offset is part of its model and stays."""
    bones = _nodes(Path(skeleton).read_text(encoding='cp1252'))
    for name in ('head_g', 'neck_g'): require(name in bones, 'Skeleton lacks '+name)
    to_head = np.linalg.inv(world(bones, 'head_g'))@world(bones, 'neck_g')
    vertices, faces = mesh_parts(Path(neck).read_text(encoding='cp1252'))
    vertices = vertices@to_head[:3, :3].T+to_head[:3, 3]
    require(len(faces) >= 4 and vertices[:, 2].min() < 0, 'Body neck must reach below the head joint')
    document = {'kind': KIND, 'frame': 'head_g local (NWN: face +y, up +z) = inv(head_g) @ neck_g of the body skeleton',
                'body': body, 'sources': {'skeleton': pin(skeleton), 'neck': pin(neck)}, 'neckToHead': to_head.round(9).tolist(),
                'vertices': vertices.round(7).tolist(), 'faces': faces.tolist()}
    write(output, document, fresh=True); return document


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--skeleton', type=Path, required=True, help='ASCII skeleton (e.g. decompiled pfg0.mdl)')
    p.add_argument('--neck', type=Path, required=True, help='ASCII neck part (e.g. decompiled pfg0_neck001.mdl)')
    p.add_argument('--body', default='', help='free-text body identity recorded in the reference')
    p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    d = build(a.skeleton, a.neck, a.output, a.body); print(a.output, len(d['vertices']), 'vertices')
