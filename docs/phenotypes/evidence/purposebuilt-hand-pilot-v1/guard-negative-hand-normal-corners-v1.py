"""Fresh N-only subset guard; preserve source/v1 and all geometry bytes."""
import argparse
import importlib.util
import json
from pathlib import Path
import numpy as np

P = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('normal_trial', P / 'smooth-reconstructed-hand-normals-v1.py')
helpers = importlib.util.module_from_spec(spec); spec.loader.exec_module(helpers)
sha, require, read_glb, accessor, serialize = helpers.sha, helpers.require, helpers.read_glb, helpers.accessor, helpers.serialize


def arrays(path):
    d, b = read_glb(path); q = d['meshes'][0]['primitives'][0]
    return accessor(d, b, q['attributes']['POSITION']), accessor(d, b, q['indices']).reshape(-1, 3), accessor(d, b, q['attributes']['NORMAL'])


def negatives(v, f, n):
    result = []
    for start in range(0, len(f), 200000):
        faces = f[start:start + 200000]
        p = v[faces].astype(float)
        cross = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
        cross /= np.linalg.norm(cross, axis=1)[:, None]
        dots = np.sum(n[faces].astype(float) * cross[:, None], axis=2)
        fi, ci = np.nonzero(dots < 0)
        result.extend(((start + fi) * 3 + ci).tolist())
    return np.asarray(result, np.int64)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    a = parser.parse_args(); out = a.output.resolve()
    require(out.parent == P.resolve() and not out.exists(), 'Fresh owned output required')
    source = P / 'clean-exterior-512-fairing-v2/faired-exterior-highpoly.glb'
    trial = P / 'clean-exterior-512-normal-polish-v1/normal-polished-highpoly.glb'
    hashes = {str(source): sha(source), str(trial): sha(trial), str(Path(__file__)): sha(__file__)}
    require(hashes[str(source)] == 'feb84aa43e2c7963bf099c3f5b9040f23f2695ae02400405b23bc6303e90a7d6' and
            hashes[str(trial)] == '39b4b3b3a040f5c35cfd465a84631b894fccfc363060c25864b6f2459d5912af', 'Exact unchanged parents required')
    v, f, original_n = arrays(source); tv, tf, candidate_n = arrays(trial)
    require(np.array_equal(v, tv) and np.array_equal(f, tf), 'Parent P/F byte equality required')
    del tv, tf
    original_negative = negatives(v, f, original_n)
    before_negative = negatives(v, f, candidate_n)
    new_negative = np.setdiff1d(before_negative, original_negative)
    vertices = np.unique(f.reshape(-1)[new_negative])
    candidate_n[vertices] = original_n[vertices]
    final_negative = negatives(v, f, candidate_n)
    require(not len(np.setdiff1d(final_negative, original_negative)), 'A newly negative corner remains')
    frozen = v[:, 1] >= v[:, 1].max() - 1 / 512 - 1e-8
    normalized = candidate_n.astype(float)
    lengths = np.linalg.norm(normalized, axis=1); normalized /= lengths[:, None]
    original_unit = original_n.astype(float); original_unit /= np.linalg.norm(original_unit, axis=1)[:, None]
    angles = np.degrees(np.arccos(np.clip(np.sum(normalized * original_unit, axis=1), -1, 1)))
    require(float(angles.max()) <= 35 + 1e-5 and np.array_equal(candidate_n[frozen], original_n[frozen]) and
            float(abs(lengths - 1).max()) < 1e-6, 'Bound/unit/cap gate failed')
    outward = helpers.corner_outwardness(v, f, normalized)
    require(outward['facesAllCornersNegative'] == 0, 'Wholly inward face remains')
    after = helpers.metric(normalized, f, frozen)
    require(after['noncap']['rmsDegrees'] < 5, 'Measured skin RMS target failed')
    parent = json.loads((trial.parent / 'normal-polish.json').read_text())
    out.mkdir(); target = out / 'normal-polished-highpoly.glb'
    serialize(target, v, f, candidate_n)
    nv, nf, nn = arrays(target)
    require(np.array_equal(v, nv) and np.array_equal(f, nf) and np.array_equal(candidate_n, nn), 'Serialized P/F/N transport failed')
    record = dict(parent)
    record.update(output=str(target), outputSha256=sha(target), parentNormalTrial=str(trial),
        parentNormalTrialSha256=hashes[str(trial)], inputHashes=hashes,
        maximumAngleChangeDegrees=float(angles.max()),
        angleChangePercentilesDegrees=dict(zip(['median', 'p95', 'p99'], map(float, np.percentile(angles, [50, 95, 99])))),
        after=after, outwardCornerComparison={'before': parent['outwardCornerComparison']['before'], 'after': outward},
        originalNegativeFaceCornerIds=original_negative.tolist(), parentTrialNegativeFaceCornerIds=before_negative.tolist(),
        correctedNewNegativeCornerIds=new_negative.tolist(), finalNegativeFaceCornerIds=final_negative.tolist(),
        additionalOriginalNormalVertexIds=vertices.tolist(), additionalOriginalNormalVertexCount=len(vertices),
        finalNegativeCornersSubsetOfOriginal=True,
        unrelatedNormalVerticesExactToParentTrial=True,
        normalRefinementPolicy='Restore original v2 N at every newly negative face-corner vertex; preserve parent trial all other N, P/F and cap; no whole-shape rerender authorized/needed for this tiny correction',
        helperSha256=sha(__file__), retainedClayReview=str(P / 'clean-exterior-512-normal-clay-v1/review.json'),
        retainedClayReviewLimit='Four images show immutable v1 N field. Only the listed few vertex normals differ; v2 compact/map review remains required.')
    for path, value in hashes.items():
        require(sha(path) == value, 'Frozen input changed')
    (out / 'normal-polish.json').write_text(json.dumps(record, indent=2) + '\n')
    (out / 'executed-guard.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'outputSha256': record['outputSha256'], 'restoredNVertexCount': len(vertices),
        'originalNegative': original_negative.tolist(), 'parentNegative': before_negative.tolist(),
        'finalNegative': final_negative.tolist(), 'after': after}), flush=True)


if __name__ == '__main__':
    main()
