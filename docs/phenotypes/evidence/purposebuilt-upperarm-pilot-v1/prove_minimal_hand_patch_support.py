"""Independent read-only support proof for the selected two-cell diagnostic grid."""
from pathlib import Path
import hashlib
import importlib.util
import json
import math
import shutil
import struct
import sys

import numpy as np

PILOT = Path(__file__).resolve().parent
ROOT = PILOT.parents[2]
OP = PILOT / 'hand-leak-independent-v1/localized-512-mincut-v2'
OUT = PILOT / 'hand-leak-independent-v1/final-grid-support-proof-v1'
LOADER = ROOT / 'tools/phenotypes/inspect_generated_part_topology.py'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise RuntimeError(message)


def decode_independent(path):
    data = path.read_bytes()
    magic, version, length = struct.unpack_from('<4sII', data)
    require((magic, version, length) == (b'glTF', 2, len(data)), 'Invalid source envelope')
    offset = 12
    chunks = []
    while offset < len(data):
        size, kind = struct.unpack_from('<II', data, offset)
        chunks.append((kind, memoryview(data)[offset+8:offset+8+size]))
        offset += size+8
    require(len(chunks) == 2 and chunks[0][0] == 0x4e4f534a and chunks[1][0] == 0x004e4942,
            'Expected exact JSON/BIN source')
    doc = json.loads(bytes(chunks[0][1]))
    require(len(doc['nodes']) == 1 and doc['nodes'][0].get('mesh') == 0
            and not set(doc['nodes'][0])-{'mesh', 'name'}, 'Source transform must be identity')
    primitive = doc['meshes'][0]['primitives'][0]

    def attribute(index, width):
        row = doc['accessors'][index]
        view = doc['bufferViews'][row['bufferView']]
        dtype = {5126:'<f4', 5125:'<u4', 5123:'<u2'}[row['componentType']]
        require(not row.get('normalized') and not row.get('sparse'), 'Unsupported accessor')
        step = np.dtype(dtype).itemsize*width
        require(view.get('byteStride', step) == step, 'Unsupported source stride')
        first = view.get('byteOffset', 0)+row.get('byteOffset', 0)
        raw = chunks[1][1][first:first+row['count']*step]
        return np.frombuffer(raw, dtype=dtype).reshape(row['count'], width).copy()

    p = attribute(primitive['attributes']['POSITION'], 3)
    f = attribute(primitive['indices'], 1).reshape(-1, 3).astype(np.int64)
    return p, f


def exact_distance(points, triangles):
    """Alternative plane half-space inclusion and clamped segment distance."""
    a, b, c = (triangles[:, i] for i in range(3))
    ab, bc, ca = b-a, c-b, a-c
    normal = np.cross(ab, c-a)
    nn = np.sum(normal*normal, axis=1)
    distances = []
    for point in points:
        dot = np.sum((point-a)*normal, axis=1)
        foot = point-(dot/np.maximum(nn, 1e-30))[:, None]*normal
        inside = (np.sum(np.cross(ab, foot-a)*normal, axis=1) >= 0)
        inside &= np.sum(np.cross(bc, foot-b)*normal, axis=1) >= 0
        inside &= np.sum(np.cross(ca, foot-c)*normal, axis=1) >= 0
        inside &= nn > 1e-25
        d2 = np.where(inside, dot*dot/np.maximum(nn, 1e-30), np.inf)
        for first, edge in [(a, ab), (b, bc), (c, ca)]:
            t = np.clip(np.sum((point-first)*edge, axis=1)/np.maximum(np.sum(edge*edge, axis=1), 1e-30), 0, 1)
            delta = point-(first+t[:, None]*edge)
            d2 = np.minimum(d2, np.sum(delta*delta, axis=1))
        index = int(np.argmin(d2))
        distances.append({'distance':float(np.sqrt(d2[index])), 'sourceFace':index})
    return distances


def main():
    require(not OUT.exists(), 'Fresh proof destination required')
    receipt_path = OP/'closure.json'
    receipt = json.loads(receipt_path.read_text())
    for path, pin in receipt['frozenInputs'].items():
        require(sha(path) == pin, 'Actual executed operation input changed')
    source = next(Path(path) for path in receipt['frozenInputs'] if path.endswith('shape-master_00001.glb'))
    grid_path = Path(receipt['grid']['path'])
    require(sha(grid_path) == receipt['grid']['sha256'], 'Selected grid changed')
    paths = [receipt_path, grid_path, OP/'patch-cells.npz', LOADER, source, Path(__file__),
             PILOT/'minimize_cached_hand_closure.py', PILOT/'close_cached_hand_leak.py',
             PILOT/'analyze_cached_hand_leak.py']
    pins = {str(path):sha(path) for path in paths}
    p, f = decode_independent(source)
    spec = importlib.util.spec_from_file_location('support_loader', LOADER)
    loader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader)
    lp, lf, _ = loader.load(source)
    require(np.array_equal(p, lp) and np.array_equal(f, lf), 'Independent decode differs from support helper')
    fixture = np.array([[[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]]])
    example = exact_distance(np.array([[.2,.2,1.],[2.,0.,0.],[-1.,-1.,0.]]), fixture)
    require(np.allclose([x['distance'] for x in example], [1.,1.,math.sqrt(2)], atol=1e-14),
            'Analytic triangle distance cases failed')
    with np.load(OP/'patch-cells.npz') as patch:
        indices = patch['indices'].copy()
        origin = patch['origin'].copy()
        pitch = float(patch['pitch'])
    centres = origin+(indices+.5)*pitch
    corners = np.unique(np.array([origin+(idx+np.array(bits))*pitch
                                  for idx in indices for bits in np.ndindex((2,2,2))]), axis=0)
    triangles = p[f].astype(float)
    centre_rows = exact_distance(centres, triangles)
    corner_rows = exact_distance(corners, triangles)
    old_centres = receipt['patchCentreSourceRecords']
    old_corners = receipt['patchCornerSourceRecords']
    require(np.allclose([row['distance'] for row in centre_rows],
                        [row['distanceSourceCoordinates'] for row in old_centres], atol=1e-15, rtol=0),
            'Independent centre support discrepancy')
    require(np.allclose([row['distance'] for row in corner_rows],
                        [row['distanceSourceCoordinates'] for row in old_corners], atol=1e-15, rtol=0),
            'Independent corner support discrepancy')
    max_centre = max(row['distance'] for row in centre_rows)
    max_corner = max(row['distance'] for row in corner_rows)
    half_diagonal = math.sqrt(3)*pitch/2
    whole_patch_bound = max_centre+half_diagonal
    require(whole_patch_bound < math.sqrt(3)*pitch,
            'Patch cell support exceeds conservative SAT512 whole-cell bound')
    OUT.mkdir()
    for path in paths:
        if path.suffix == '.py':
            shutil.copy2(path, OUT/path.name)
    report = {
        'schemaVersion':1, 'readOnly':True, 'originalInputsModified':False,
        'sourceAdopted':False, 'gpuUsed':False, 'clientControlled':False,
        'frozenInputs':pins,
        'historicalOperationLoaderPinNote':
            'The original mincut receipt pins its directly called support helpers but omits their imported GLB loader. '
            'This later independent proof archives the actual loader, verifies identity-transform position/index '
            'decoding with a separate parser and reproduces all recorded distances; it does not rewrite historical provenance.',
        'runtime':{'pythonExecutable':sys.executable, 'pythonVersion':sys.version, 'numpyVersion':np.__version__},
        'sourceVertices':len(p), 'sourceTriangles':len(f), 'independentDecodeArraysExact':True,
        'analyticDistanceSelfTestsPassed':True, 'patchCells':len(indices),
        'allRecordedDistancesIndependentlyReproducedAt1eMinus15':True,
        'maximumCentreSourceDistance':max_centre, 'maximumCornerSourceDistance':max_corner,
        'pitchSourceCoordinates':pitch, 'cellHalfDiagonal':half_diagonal,
        'allPointsInPatchCellsSourceDistanceBound':whole_patch_bound,
        'wholeCellProof':'Distance to a fixed source triangle set is 1-Lipschitz; every point in each cell is at '
                         'most half a cell diagonal from its independently measured centre.',
        'conservativeSAT512WholeCellSourceSupportBound':math.sqrt(3)*pitch,
        'notClaimed':'This bound applies to the two added complete cells, not every interpolated extracted '
                     'surface vertex, topology, anatomy or final fit. Independent actual extracted surface gates remain required.',
        'centreRecords':[{'index':idx.tolist(), **row} for idx,row in zip(indices,centre_rows)],
        'cornerRecords':[{'point':point.tolist(), **row} for point,row in zip(corners,corner_rows)]
    }
    for path, pin in pins.items():
        require(sha(path) == pin, 'Proof changed immutable input')
    target = OUT/'proof.json'
    target.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'proof':str(target), 'sha256':sha(target), 'wholePatchCellBound':whole_patch_bound,
                      'SAT512WholeCellBound':math.sqrt(3)*pitch}))


if __name__ == '__main__':
    main()
