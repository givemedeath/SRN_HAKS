"""Read-only collected compact P/F/UV and actual final authored shading basis."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np

P = Path(__file__).resolve().parent; R = P.parents[2]
sys.path.insert(0, str(R / 'tools/phenotypes'))
from place_purposebuilt_pelvis import read_glb, accessor, require


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    d, b = read_glb(path); q = d['meshes'][0]['primitives'][0]
    require(d['nodes'] == [{'mesh': 0}] and len(d['meshes']) == len(d['meshes'][0]['primitives']) == 1, 'Actual identity source required')
    values = {key: accessor(d, b, i) for key, i in q['attributes'].items()}
    values['faces'] = accessor(d, b, q['indices']).reshape(-1, 3)
    return values


def fallback_normals(v, f):
    inv_tol = np.float32(1 / (max(float(np.ptp(v, axis=0).max()), 1e-9) * 1e-5))
    keys = np.round((v - v.min(0)) * inv_tol).astype(np.int64)
    _, group = np.unique(keys, axis=0, return_inverse=True)
    tri = v[f]; face_n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    acc = np.zeros((int(group.max()) + 1, 3), np.float32)
    for i in range(3):
        np.add.at(acc, group[f[:, i]], face_n)
    result = acc[group]; result /= np.maximum(np.linalg.norm(result, axis=1, keepdims=True), 1e-6)
    return result


def angle(a, b):
    a = a.astype(float); b = b.astype(float)
    a /= np.linalg.norm(a, axis=1, keepdims=True); b /= np.linalg.norm(b, axis=1, keepdims=True)
    values = np.degrees(np.arccos(np.clip(np.sum(a * b, axis=1), -1, 1)))
    return {'maximumDegrees': float(values.max()), 'p99Degrees': float(np.percentile(values, 99)),
            'meanDegrees': float(values.mean())}


def main():
    out = P / 'clean-output-basis-v1'; require(not out.exists(), 'Fresh owned output required')
    job_root = R / 'output/phenotypes/human-male-complete-goal-v1/clean-hand-retexture-v2'
    generation = job_root / 'generation.json'; job = json.loads(generation.read_text())
    paths = [job_root / 'generated' / name for name in ['uv-master_00001.glb', 'textured_00001.glb']]
    hashes = {str(path): sha(path) for path in [generation, *paths, Path(__file__)]}
    require(job['state'] == 'success' and job['promptId'] == '3565bc47-42b7-4e91-a4ce-9c9e164058f3', 'Actual collected final job required')
    for path in paths:
        require(any(Path(o['localPath']).resolve() == path.resolve() and o['sha256'] == sha(path) for o in job['outputs']), 'Actual saved master association failed')
    uv, final = map(load, paths)
    require(np.array_equal(uv['POSITION'], final['POSITION']) and np.array_equal(uv['faces'], final['faces']), 'Compact P/F changed during material application')
    delta = abs(uv['TEXCOORD_0'] - final['TEXCOORD_0'])
    require(float(delta.max()) < 1e-6, 'Material stage substantially changed UVs')
    n, t = final['NORMAL'], final['TANGENT']
    require(np.isfinite(n).all() and np.isfinite(t).all() and np.isfinite(final['TEXCOORD_0']).all(), 'Nonfinite basis/UV rejected')
    nl, tl = np.linalg.norm(n.astype(float), axis=1), np.linalg.norm(t[:, :3].astype(float), axis=1)
    require(nl.min() > .99 and tl.min() > .99 and np.all(abs(t[:, 3]) == 1), 'Invalid authored basis or tangent signs')
    fallback = fallback_normals(final['POSITION'], final['faces'])
    record = {'schemaVersion': 1, 'readOnly': True, 'inputHashes': hashes, 'jobPromptId': job['promptId'],
        'actualCompactVertices': len(final['POSITION']), 'actualCompactFaces': len(final['faces']),
        'positionsFloat32ByteExact': True, 'faceIndicesByteExact': True, 'identitySourceFrames': True,
        'uvMasterHasAuthoredNormals': 'NORMAL' in uv, 'uvMasterHasTangents': 'TANGENT' in uv,
        'finalUvMaximumComponentDifference': float(delta.max()), 'changedUvComponents': int((delta != 0).sum()),
        'normalLengthMinMax': [float(nl.min()), float(nl.max())], 'tangentLengthMinMax': [float(tl.min()), float(tl.max())],
        'maximumAbsNormalTangentDot': float(abs(np.sum(n.astype(float) * t[:, :3], axis=1)).max()),
        'tangentSignsAllUnit': True, 'installedFallbackVsActualNormals': angle(fallback, n),
        'sourceGeometryOrMapsChanged': False, 'acceptedNeighboursChanged': False,
        'limits': 'UV-save intentionally has no N/T. Actual final N/T and unchanged compact geometry are measured. FP32 fallback reconstruction uses installed weld/area weighting, with a different accumulation order from GPU. Native serialized P/N/UV/T and final palette/roughness remain root gates. Tiny compact crossing and pinched-link exceptions are documented separately, not hidden by this basis check.'}
    for path, value in hashes.items():
        require(sha(path) == value, 'Read-only input changed')
    out.mkdir(); (out / 'measurement.json').write_text(json.dumps(record, indent=2) + '\n')
    (out / 'executed-audit.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
