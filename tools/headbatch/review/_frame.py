"""Shared by the review tools: the view rotations and a head's neck-cut frame."""
import json
import numpy as np
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


def band(local, cut, jaw, bv, bf):
    """(plane height per vertex, vertices the cut draws onto the body neck), as neck_cut measures them: an explicit height wins over the jaw, and skirt hair stays out of the band."""
    plane = (jaw['height']-cut['clearance'] if cut['height'] == 'measured' else cut['height'])+cut['slope']*local[:, 1]
    above = local[:, 2]-plane
    zone = np.zeros(len(local), bool)
    skirt = cut.get('skirt')
    if skirt is not None:
        region = np.flatnonzero((above >= -skirt['depth']) & (above < cut['band']))
        low, high = max(float(bv[:, 2].min())+1e-4, float(local[:, 2].min())), float(bv[:, 2].max())-1e-4
        _, surface, offset = N.body_profile(bv, bf, low, high)(local[region], local[region, 2])
        zone[region] = (np.linalg.norm(offset, axis=1)-surface > skirt['gap']) & (N.face_angle(offset) >= cut['cone'])
    return plane, (above < cut['band']) & ~zone


def local_positions(neck, path):
    """A GLB's physical vertices in the neck-cut frame."""
    m = mesh(path)
    return N.transform(neck['frame'], N.physical(m['positions'], m['faces'])[0])
