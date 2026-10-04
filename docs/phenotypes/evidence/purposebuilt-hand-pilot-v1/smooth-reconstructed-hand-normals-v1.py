"""Bounded normal-field-only trial on the new, unselected 12-pair hand exterior."""
import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

P = Path(__file__).resolve().parent
R = P.parents[2]
sys.path.insert(0, str(R / 'tools/phenotypes'))
from place_purposebuilt_pelvis import read_glb, accessor, require
_spec = importlib.util.spec_from_file_location('bounded_fairing', P / 'fair-reconstructed-hand-v1.py')
_fairing = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fairing)
serialize = _fairing.serialize


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(4 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def metric(n, f, frozen):
    reports = {key: {'count': 0, 'total': 0., 'squared': 0., 'maximum': 0.,
                     'above10': 0, 'above20': 0} for key in ['all', 'noncap']}
    for start in range(0, len(f), 200000):
        faces = f[start:start + 200000]
        for i, j in [(0, 1), (1, 2), (2, 0)]:
            angles = np.degrees(np.arccos(np.clip(np.sum(n[faces[:, i]] * n[faces[:, j]], axis=1), -1, 1)))
            for key, mask in [('all', np.ones(len(faces), bool)),
                              ('noncap', ~(frozen[faces[:, i]] | frozen[faces[:, j]]))]:
                values = angles[mask]; row = reports[key]
                row['count'] += len(values)
                row['total'] += float(values.sum())
                row['squared'] += float(np.square(values).sum())
                row['maximum'] = max(row['maximum'], float(values.max(initial=0)))
                row['above10'] += int((values > 10).sum())
                row['above20'] += int((values > 20).sum())
    return {key: {'directedFaceEdgeSamples': row['count'],
                  'meanDegrees': row['total'] / row['count'],
                  'rmsDegrees': (row['squared'] / row['count']) ** .5,
                  'maximumDegrees': row['maximum'],
                  'edgesAbove10Degrees': row['above10'],
                  'edgesAbove20Degrees': row['above20']} for key, row in reports.items()}


def neighbour_mean(n, f, degree):
    result = np.zeros_like(n, dtype=np.float64)
    for axis in range(3):
        for i, j, k in [(0, 1, 2), (1, 2, 0), (2, 0, 1)]:
            result[:, axis] += np.bincount(f[:, i], weights=n[f[:, j], axis] + n[f[:, k], axis], minlength=len(n))
    return result / degree[:, None]


def spherical_clamp(original, proposed, max_angle):
    dot = np.clip(np.sum(original * proposed, axis=1), -1, 1)
    angles = np.arccos(dot)
    over = angles > max_angle
    if np.any(over):
        tangent = proposed[over] - dot[over, None] * original[over]
        length = np.linalg.norm(tangent, axis=1)
        require((length > 1e-12).all(), 'Antipodal normal update rejected')
        proposed[over] = np.cos(max_angle) * original[over] + np.sin(max_angle) * tangent / length[:, None]
    return proposed, int(over.sum())


def corner_outwardness(v, f, n, return_bad=False):
    negative = all_negative = count = 0
    smallest = 1.
    bad_faces = []
    for start in range(0, len(f), 200000):
        faces = f[start:start + 200000]
        points = v[faces].astype(float)
        face_normals = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
        face_normals /= np.linalg.norm(face_normals, axis=1)[:, None]
        dots = np.sum(n[faces] * face_normals[:, None, :], axis=2)
        negative += int((dots < 0).sum()); all_negative += int((dots.max(1) < 0).sum())
        if return_bad:
            bad_faces.extend((start + np.flatnonzero(dots.max(1) < 0)).tolist())
        count += dots.size; smallest = min(smallest, float(dots.min()))
    record = {'corners': count, 'negativeFaceNormalCorners': negative,
            'facesAllCornersNegative': all_negative, 'minimumFaceNormalDot': smallest}
    return (record, np.asarray(bad_faces, np.int64)) if return_bad else record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    a = parser.parse_args()
    source = a.source.resolve(); out = a.output.resolve()
    require(out.parent == P.resolve() and not out.exists(), 'Fresh owned output directory required')
    source_sha = sha(source)
    require(source_sha == 'feb84aa43e2c7963bf099c3f5b9040f23f2695ae02400405b23bc6303e90a7d6', 'Exact new 12-pair unselected geometry required')
    doc, blob = read_glb(source); primitive = doc['meshes'][0]['primitives'][0]
    v = accessor(doc, blob, primitive['attributes']['POSITION'])
    f = accessor(doc, blob, primitive['indices']).reshape(-1, 3).astype(np.int64)
    original_n = accessor(doc, blob, primitive['attributes']['NORMAL'])
    require(not doc.get('images') and not doc.get('materials') and set(primitive['attributes']) == {'POSITION', 'NORMAL'}, 'Untextured P/N source required')
    del doc, blob
    original = original_n.astype(float)
    lengths = np.linalg.norm(original, axis=1)
    require(np.isfinite(original).all() and (lengths > 1e-12).all(), 'Finite nonzero input normals required')
    original /= lengths[:, None]
    frozen = v[:, 1] >= v[:, 1].max() - 1 / 512 - 1e-8
    degree = np.zeros(len(v), np.float64)
    for corner in range(3):
        degree += 2 * np.bincount(f[:, corner], minlength=len(v))
    require((degree > 0).all(), 'Unused vertex rejected')
    current = original.copy()
    before = metric(current, f, frozen)
    before_outward = corner_outwardness(v, f, current)
    require(before_outward['facesAllCornersNegative'] == 0, 'Original area-weighted field has inward faces')
    history = []
    # Surface-adjacency lowpass, normalized each step. It never edits geometry.
    # Bound from the original field, not from the previous smoothed step.
    for step in range(1, 25):
        proposed = .5 * current + .5 * neighbour_mean(current, f, degree)
        norm = np.linalg.norm(proposed, axis=1)
        require((norm > 1e-12).all(), 'Zero smoothed normal rejected')
        proposed /= norm[:, None]
        proposed, clamped = spherical_clamp(original, proposed, np.radians(35))
        proposed[frozen] = original[frozen]
        current = proposed
        if step % 4 == 0:
            measured = metric(current, f, frozen)
            angles = np.degrees(np.arccos(np.clip(np.sum(current * original, axis=1), -1, 1)))
            history.append({'steps': step, 'adjacentNormalVariation': measured,
                            'maximumAngleChangeDegrees': float(angles.max()),
                            'p95AngleChangeDegrees': float(np.percentile(angles, 95)),
                            'clampedVerticesAtLastStep': clamped})
            print(json.dumps(history[-1]), flush=True)
            if measured['noncap']['rmsDegrees'] < 4.8:
                break
    # Concave geometry may contain a tiny face whose three interpolated normals
    # all face away after lowpass. Restore its actual original vertex normals,
    # with a fixed point check on neighbouring faces; never weaken outwardness.
    outward_guards = np.zeros(len(v), bool)
    outward_history = []
    for guard_step in range(12):
        measured, bad_faces = corner_outwardness(v, f, current, return_bad=True)
        outward_history.append({'iteration': guard_step, **measured})
        print(json.dumps({'outwardGuard': outward_history[-1]}), flush=True)
        if not len(bad_faces):
            break
        outward_guards[f[bad_faces].ravel()] = True
        current[outward_guards] = original[outward_guards]
    require(not len(bad_faces), 'Original-normal vertex guard did not converge')
    final_n = current.astype(np.float32)
    final_n[frozen] = original_n[frozen]
    final_n[outward_guards] = original_n[outward_guards]
    final_length = np.linalg.norm(final_n.astype(float), axis=1)
    normalized = final_n.astype(float) / final_length[:, None]
    angle_change = np.degrees(np.arccos(np.clip(np.sum(normalized * original, axis=1), -1, 1)))
    require(np.isfinite(final_n).all() and float(abs(final_length - 1).max()) < 1e-6 and
            float(angle_change.max()) <= 35 + 1e-5 and np.array_equal(final_n[frozen], original_n[frozen]),
            'Normal unit/nonzero/angle/cap gate failed')
    after = metric(normalized, f, frozen)
    after_outward = corner_outwardness(v, f, normalized)
    require(after_outward['facesAllCornersNegative'] == 0, 'Inward-facing authored-normal face rejected')
    out.mkdir()
    target = out / 'normal-polished-highpoly.glb'
    serialize(target, v, f, final_n)
    d, b = read_glb(target); q = d['meshes'][0]['primitives'][0]
    require(np.array_equal(accessor(d, b, q['attributes']['POSITION']), v) and
            np.array_equal(accessor(d, b, q['indices']).reshape(-1, 3), f) and
            np.array_equal(accessor(d, b, q['attributes']['NORMAL']), final_n), 'Serialized exact P/F/N transport failed')
    require(sha(source) == source_sha, 'Source changed')
    record = {'schemaVersion': 1, 'newUnselectedCandidateOnly': True, 'source': str(source), 'sourceSha256': source_sha,
        'output': str(target), 'outputSha256': sha(target), 'sourceChanged': False,
        'vertices': len(v), 'faces': len(f), 'positionsByteExact': True, 'faceIndicesByteExact': True,
        'positionArraySha256': hashlib.sha256(v.astype('<f4').tobytes()).hexdigest(),
        'faceArraySha256': hashlib.sha256(f.astype('<u4').tobytes()).hexdigest(),
        'normalFieldChangedOnly': True, 'normalAtlasOrStrengthChanged': False, 'mapsOrUvsExist': False,
        'algorithm': 'Half self + half equal-edge neighbour mean on actual manifold; normalize; spherical clamp to 35 degrees from v2; cap band exact',
        'steps': step, 'maximumAllowedChangeDegrees': 35., 'maximumAngleChangeDegrees': float(angle_change.max()),
        'angleChangePercentilesDegrees': dict(zip(['median', 'p95', 'p99'], map(float, np.percentile(angle_change, [50, 95, 99])))),
        'normalUnitMaximumError': float(abs(final_length - 1).max()), 'capNormalVerticesFrozen': int(frozen.sum()),
        'outwardNormalVerticesRestoredToOriginal': int(outward_guards.sum()), 'outwardGuardHistory': outward_history,
        'capNormalsExact': True, 'geometryGripGuardsExactByPositionTransport': True,
        'before': before, 'after': after, 'history': history, 'outwardCornerComparison': {'before': before_outward, 'after': after_outward},
        'helperSha256': sha(__file__), 'selected': False, 'clientAccepted': False,
        'limits': 'Noncap RMS covers all surface-adjacency samples with neither endpoint in the protected wrist cap band, including anatomical curvature and grip. It is not a pure noise spectrum or a final bake/client proof.'}
    (out / 'normal-polish.json').write_text(json.dumps(record, indent=2) + '\n')
    (out / 'executed-normal-polish.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'outputSha256': record['outputSha256'], 'steps': step,
                      'maxAngle': record['maximumAngleChangeDegrees'], 'after': after}), flush=True)


if __name__ == '__main__':
    main()
