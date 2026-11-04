"""Shared by the review tools: the view rotations and a head's neck-cut frame."""
import json
import headkit.neck as N
from headkit.gltf import mesh
from headbatch.head_files import fit_matrix

VIEWS = {'front': [[-1, 0, 0], [0, 0, 1], [0, 1, 0]], 'back': [[1, 0, 0], [0, 0, 1], [0, -1, 0]],
         'left': [[0, 1, 0], [0, 0, 1], [-1, 0, 0]], 'right': [[0, -1, 0], [0, 0, 1], [1, 0, 0]],
         'top': [[-1, 0, 0], [0, -1, 0], [0, 0, 1]], 'bottom': [[-1, 0, 0], [0, 1, 0], [0, 0, -1]]}


def head_neck(head):
    """(manifest, neck policy on the reviewed fit, body neck vertices, body neck faces)."""
    man = json.load(open(head+'/manifest.json'))
    return (man, N.neck_policy(man['mesh']['neck'], {'matrix': fit_matrix(head), 'reviewed': True}), *N.body_neck(head+'/'+man['inputs']['bodyNeck']['path']))


def local_positions(neck, path):
    """A GLB's physical vertices in the neck-cut frame."""
    m = mesh(path)
    return N.transform(neck['frame'], N.physical(m['positions'], m['faces'])[0])
