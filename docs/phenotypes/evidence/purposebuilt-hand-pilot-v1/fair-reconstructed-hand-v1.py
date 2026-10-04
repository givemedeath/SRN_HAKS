"""Bounded fairing of NEW reconstructed hand only; fixed faces/cap/grip guards."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np

P = Path(__file__).resolve().parent
R = P.parents[2]
sys.path.insert(0, str(R / 'tools/phenotypes'))
from place_purposebuilt_pelvis import read_glb, accessor, write_glb, require

SOURCE_SHA = 'd955864c9184a210d0ad9997006576bcb3e6adcdc8b4ecfc46dce410e15c4c9b'
PITCH = 1 / 512
CORES = np.array([[-.175, .05], [-.19, .05], [-.175, .035], [-.16, .035]], float)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(4 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def projected_clearance(v, f, witness):
    """Distance from an infinite X line to each exact triangular surface."""
    distances = np.empty(len(f), np.float64)
    for start in range(0, len(f), 200000):
        stop = min(start + 200000, len(f))
        t = v[f[start:stop]][:, :, 1:3].astype(float) - witness
        best = np.full(len(t), np.inf)
        crosses = []
        for i, j in [(0, 1), (1, 2), (2, 0)]:
            a, edge = t[:, i], t[:, j] - t[:, i]
            factor = np.clip(-np.sum(a * edge, axis=1) / np.maximum(np.sum(edge * edge, axis=1), 1e-30), 0, 1)
            best = np.minimum(best, np.linalg.norm(a + factor[:, None] * edge, axis=1))
            crosses.append(edge[:, 0] * -a[:, 1] - edge[:, 1] * -a[:, 0])
        crosses = np.stack(crosses, axis=1)
        area2 = (t[:, 1, 0] - t[:, 0, 0]) * (t[:, 2, 1] - t[:, 0, 1]) - (t[:, 1, 1] - t[:, 0, 1]) * (t[:, 2, 0] - t[:, 0, 0])
        inside = ((crosses.min(1) >= 0) | (crosses.max(1) <= 0)) & (abs(area2) > 1e-20)
        best[inside] = 0
        distances[start:stop] = best
    return distances


def laplacian(v, f, degree):
    accum = np.zeros_like(v, dtype=np.float64)
    for axis in range(3):
        for i, j, k in [(0, 1, 2), (1, 2, 0), (2, 0, 1)]:
            accum[:, axis] += np.bincount(f[:, i], weights=v[f[:, j], axis] + v[f[:, k], axis], minlength=len(v))
    return accum / degree[:, None] - v


def surface_stats(original, candidate, f):
    normals = np.zeros_like(candidate, dtype=np.float64)
    original_volume = candidate_volume = 0.
    flipped = degenerate = 0
    minimum_dot = np.inf
    for start in range(0, len(f), 200000):
        faces = f[start:start + 200000]
        old, new = original[faces].astype(float), candidate[faces].astype(float)
        old_cross = np.cross(old[:, 1] - old[:, 0], old[:, 2] - old[:, 0])
        new_cross = np.cross(new[:, 1] - new[:, 0], new[:, 2] - new[:, 0])
        dot = np.sum(old_cross * new_cross, axis=1)
        minimum_dot = min(minimum_dot, float(dot.min()))
        flipped += int((dot <= 0).sum())
        degenerate += int((np.linalg.norm(new_cross, axis=1) <= 1e-15).sum())
        original_volume += float(np.sum(old[:, 0] * old_cross) / 6)
        candidate_volume += float(np.sum(new[:, 0] * new_cross) / 6)
        for corner in range(3):
            np.add.at(normals, faces[:, corner], new_cross)
    lengths = np.linalg.norm(normals, axis=1)
    require((lengths > 1e-15).all(), 'New zero authored normal rejected')
    normals = (normals / lengths[:, None]).astype(np.float32)
    return normals, {'originalSignedVolume': original_volume, 'candidateSignedVolume': candidate_volume,
        'volumeRatio': candidate_volume / original_volume, 'faceFlips': flipped,
        'degenerateFaces': degenerate, 'minimumOldNewCrossDot': minimum_dot,
        'normalPolicy': 'Fresh unit area-weighted normals on new candidate; no selected/parent normals overwritten'}


def serialize(path, v, f, n):
    arrays = [v.astype('<f4'), f.astype('<u4').ravel(), n.astype('<f4')]
    blocks = [a.tobytes() for a in arrays]
    offsets = np.cumsum([0] + [len(block) for block in blocks[:-1]])
    doc = {'asset': {'version': '2.0', 'generator': 'SRN bounded reconstructed-hand fairing'},
        'buffers': [{'byteLength': sum(map(len, blocks))}],
        'bufferViews': [{'buffer': 0, 'byteOffset': int(offset), 'byteLength': len(block)} for offset, block in zip(offsets, blocks)],
        'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': len(v), 'type': 'VEC3', 'min': v.min(0).tolist(), 'max': v.max(0).tolist()},
            {'bufferView': 1, 'componentType': 5125, 'count': f.size, 'type': 'SCALAR'},
            {'bufferView': 2, 'componentType': 5126, 'count': len(n), 'type': 'VEC3'}],
        'meshes': [{'primitives': [{'attributes': {'POSITION': 0, 'NORMAL': 2}, 'indices': 1, 'mode': 4}]}],
        'nodes': [{'mesh': 0, 'name': 'bounded-faired-exterior'}], 'scenes': [{'nodes': [0]}], 'scene': 0}
    write_glb(path, doc, b''.join(blocks))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--reconstruction', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pairs', type=int, default=3)
    a = parser.parse_args()
    require(1 <= a.pairs <= 24, 'Explicit bounded Taubin pair count required')
    source = a.source.resolve(); out = a.output.resolve()
    require(out.parent == P.resolve() and not out.exists(), 'Fresh owned output directory required')
    require(sha(source) == SOURCE_SHA, 'Only the exact new MT candidate is authorized')
    receipt = json.loads(a.reconstruction.read_text())
    require(receipt['outputSha256'] == SOURCE_SHA and receipt['pitchSourceCoordinates'] == PITCH and
        receipt['sourceModified'] is False and receipt['topology']['boundaryEdges'] == 0 and
        receipt['topology']['nonmanifoldEdges'] == 0, 'Actual closed new-reconstruction receipt required')
    doc, binary = read_glb(source)
    require(doc['nodes'] == [{'mesh': 0, 'name': 'filled-exterior'}] and not doc.get('materials') and not doc.get('images'),
        'Original identity-frame, untextured reconstruction required')
    prim = doc['meshes'][0]['primitives'][0]
    v = accessor(doc, binary, prim['attributes']['POSITION'])
    f = accessor(doc, binary, prim['indices']).reshape(-1, 3).astype(np.int64)
    del doc, binary
    frozen = v[:, 1] >= v[:, 1].max() - PITCH - 1e-8
    cap_frozen_count = int(frozen.sum())
    guard_reports = []
    for witness in CORES:
        distances = projected_clearance(v, f, witness)
        minimum = float(distances.min()); require(minimum > 0, 'Source core grip line is not clear')
        near = distances <= minimum + 2 * PITCH
        frozen[f[near].ravel()] = True
        guard_reports.append({'lineOriginRawGltf': [0., *witness.tolist()],
            'sourceMinimumClearance': minimum, 'protectedFaceCount': int(near.sum()),
            'guardBandSourceUnits': 2 * PITCH})
        print(json.dumps({'gripGuard': guard_reports[-1]}), flush=True)
        del distances
    degree = np.zeros(len(v), np.float64)
    for corner in range(3):
        degree += 2 * np.bincount(f[:, corner], minlength=len(v))
    require((degree > 0).all(), 'Unused source vertex rejected')
    current = v.astype(float)
    history = []
    # Leave room for FLOAT32 serialization error while staying below one pitch.
    clamp = PITCH - 1e-7
    for pair in range(a.pairs):
        for label, factor in [('lambda', .5), ('mu', -.53)]:
            current += factor * laplacian(current, f, degree)
            displacement = current - v
            lengths = np.linalg.norm(displacement, axis=1)
            scale = np.minimum(1, clamp / np.maximum(lengths, 1e-30))
            current = v + displacement * scale[:, None]
            current[frozen] = v[frozen]
            history.append({'pair': pair + 1, 'step': label, 'factor': factor,
                'maximumDisplacementSourceUnits': float(np.linalg.norm(current - v, axis=1).max()),
                'clampedVertices': int((lengths > clamp).sum())})
            print(json.dumps(history[-1]), flush=True)
    candidate = current.astype(np.float32)
    del current
    displacement = np.linalg.norm(candidate.astype(float) - v, axis=1)
    require(float(displacement.max()) <= PITCH and np.array_equal(candidate[frozen], v[frozen]),
        'Exact cap/grip guard or displacement bound failed')
    normals, integrity = surface_stats(v, candidate, f)
    require(integrity['faceFlips'] == integrity['degenerateFaces'] == 0 and
        0.995 <= integrity['volumeRatio'] <= 1.005, 'Fairing flip/degeneracy/volume gate failed')
    for witness, record in zip(CORES, guard_reports):
        distances = projected_clearance(candidate, f, witness)
        record['candidateMinimumClearance'] = float(distances.min())
        require(abs(record['candidateMinimumClearance'] - record['sourceMinimumClearance']) <= 1e-10,
            'Exact protected core clearance changed')
        del distances
    out.mkdir()
    path = out / 'faired-exterior-highpoly.glb'
    serialize(path, candidate, f, normals)
    nd, nb = read_glb(path); primitive = nd['meshes'][0]['primitives'][0]
    read_f = accessor(nd, nb, primitive['indices']).reshape(-1, 3)
    read_v = accessor(nd, nb, primitive['attributes']['POSITION'])
    read_n = accessor(nd, nb, primitive['attributes']['NORMAL'])
    require(np.array_equal(read_f, f) and np.array_equal(read_v, candidate) and np.array_equal(read_n, normals),
        'Serialized candidate P/F/N differs from measured arrays')
    require(sha(source) == SOURCE_SHA, 'Immutable MT source changed')
    np.savez_compressed(out / 'protected-vertices.npz', frozen=np.packbits(frozen), vertexCount=np.array([len(v)]))
    result = {'schemaVersion': 1, 'newUnselectedCandidateOnly': True,
        'source': str(source), 'sourceSha256': SOURCE_SHA, 'sourceChanged': False,
        'reconstruction': str(a.reconstruction.resolve()), 'reconstructionSha256': sha(a.reconstruction),
        'output': str(path), 'outputSha256': sha(path), 'geometryFrame': 'Original raw glTF, identity node',
        'positionsChanged': int(np.any(candidate != v, axis=1).sum()), 'vertices': len(v), 'faces': len(f),
        'faceIndicesExact': True, 'sourceFaceIndicesSha256': hashlib.sha256(f.astype('<u4').tobytes()).hexdigest(),
        'maximumDisplacementSourceUnits': float(displacement.max()),
        'displacementPercentiles': dict(zip(['median', 'p95', 'p99'], map(float, np.percentile(displacement, [50, 95, 99])))),
        'sourcePitch': PITCH, 'maximumAllowedDisplacementSourceUnits': PITCH,
        'capAxisRawGltf': 'Y', 'capPlane': float(v[:, 1].max()), 'capPlaneAndOnePitchBandVerticesFrozen': cap_frozen_count,
        'protectedVertexCount': int(frozen.sum()), 'protectedVerticesExact': True,
        'protectedVertexArchiveSha256': sha(out / 'protected-vertices.npz'), 'gripGuards': guard_reports,
        'taubinHistory': history, 'integrity': integrity,
        'sourceBoundsRawGltf': [v.min(0).tolist(), v.max(0).tolist()],
        'candidateBoundsRawGltf': [candidate.min(0).tolist(), candidate.max(0).tolist()],
        'uvsOrMapsExist': False, 'acceptedGeometryOrMaterialsChanged': False,
        'helperSha256': sha(__file__), 'selected': False, 'clientAccepted': False,
        'remainingGates': ['Independent source-envelope/sections/wrist/grip proof',
            'Representative clay ridge-removal review', 'Fresh compact topology/bakes and stock fitting']}
    (out / 'fairing.json').write_text(json.dumps(result, indent=2) + '\n')
    (out / 'executed-fairing.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({key: result[key] for key in ['output', 'outputSha256', 'positionsChanged',
        'maximumDisplacementSourceUnits', 'integrity']}), flush=True)


if __name__ == '__main__':
    main()
