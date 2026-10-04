"""Read-only actual wrist sections and source grip-axis anchors; no fitting."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np

P = Path(__file__).resolve().parent
R = P.parents[2]
sys.path.insert(0, str(R / 'tools/phenotypes'))
from place_purposebuilt_pelvis import read_glb, accessor, require


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(4 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def section(v, f, raw_y):
    low = np.full(2, np.inf); high = np.full(2, -np.inf); count = 0
    for start in range(0, len(f), 150000):
        t = v[f[start:start + 150000]].astype(float)
        for i, j in [(0, 1), (1, 2), (2, 0)]:
            first, second = t[:, i], t[:, j]
            delta = second[:, 1] - first[:, 1]
            ok = (abs(delta) > 1e-14) & (np.minimum(first[:, 1], second[:, 1]) <= raw_y) & (np.maximum(first[:, 1], second[:, 1]) >= raw_y)
            factor = (raw_y - first[ok, 1]) / delta[ok]
            hits = first[ok][:, [0, 2]] + (second[ok][:, [0, 2]] - first[ok][:, [0, 2]]) * factor[:, None]
            if len(hits):
                low = np.minimum(low, hits.min(0)); high = np.maximum(high, hits.max(0)); count += len(hits)
    require(count > 0, 'Actual section is empty')
    nw_low = np.array([low[0], -high[1]])
    nw_high = np.array([high[0], -low[1]])
    return {'planeNwnZ': raw_y, 'actualSegmentEndpointSamples': count,
            'boundsNwnXY': [nw_low.tolist(), nw_high.tolist()],
            'centerNwnXYZ': [*((nw_low + nw_high) / 2).tolist(), raw_y],
            'diametersNwnXY': (nw_high - nw_low).tolist()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    a = parser.parse_args(); source = a.source.resolve(); out = a.output.resolve()
    require(out.parent == P.resolve() and not out.exists(), 'Fresh owned output required')
    targets = P / 'selected-wrist-targets-v1/measurement.json'
    stock = P / 'stock-measurement-v1/measurement.json'
    hashes = {str(x): sha(x) for x in [source, targets, stock, Path(__file__)]}
    require(hashes[str(source)] == 'feb84aa43e2c7963bf099c3f5b9040f23f2695ae02400405b23bc6303e90a7d6', 'Exact faired-v2 P candidate required')
    doc, blob = read_glb(source); q = doc['meshes'][0]['primitives'][0]
    v = accessor(doc, blob, q['attributes']['POSITION'])
    f = accessor(doc, blob, q['indices']).reshape(-1, 3)
    require(doc['nodes'] == [{'mesh': 0, 'name': 'bounded-faired-exterior'}], 'Original identity frame required')
    del doc, blob
    records = [section(v, f, z) for z in [.20, .25, .30, .35, .38, .40, .42, .44, .45, .453]]
    target_data = json.loads(targets.read_text())
    left = target_data['records'][0]
    wrist = next(s for s in left['forearmSectionsInHandFrame'] if abs(s['handLocalZ']) < 1e-8)
    dimensions = np.asarray(wrist['diametersXYMm']) / 1000
    target_center = np.array([*wrist['centerXY'], 0.])
    held = np.array(left['actualEquipmentInHandBind'])[:3, 3]
    # A channel line is axial along source X; its arbitrary X origin is not a
    # longitudinal anchor. Use perpendicular distance and keep that free axis.
    core = np.array([0., -.05, -.175])
    target_radial = (held - target_center)[[0, 2]]
    for row in records:
        source_radial = (core - np.array(row['centerNwnXYZ']))[[1, 2]]
        row['sourceWristToCorePerpendicularDistance'] = float(np.linalg.norm(source_radial))
        row['scaleForExactWristToGripDistance'] = float(np.linalg.norm(target_radial) / np.linalg.norm(source_radial))
        # Explicit reflection then Rz(+90) maps source transverse widths to the
        # stock left axes; this is only a dimensional diagnostic, not a fit.
        projected = np.asarray(row['diametersNwnXY'])[::-1]
        row['leastSquaresScaleForWristWidthsOnly'] = float(np.dot(projected, dimensions) / np.dot(projected, projected))
        row['wristWidthsAtGripDistanceScaleMm'] = (projected * row['scaleForExactWristToGripDistance'] * 1000).tolist()
    conversion = np.array([[1., 0., 0.], [0., 0., -1.], [0., 1., 0.]])
    nwn = v @ conversion.T
    report = {'schemaVersion': 1, 'readOnly': True, 'fitOrSourceEditPerformed': False,
        'source': str(source), 'sourceSha256': hashes[str(source)], 'inputHashes': hashes,
        'positionArraySha256': hashlib.sha256(v.astype('<f4').tobytes()).hexdigest(),
        'frameConversionRawGltfToNwn': conversion.tolist(), 'sourceBoundsNwn': [nwn.min(0).tolist(), nwn.max(0).tolist()],
        'sourceCoreGripLineNwn': {'origin': core.tolist(), 'direction': [1., 0., 0.], 'axisOriginXIsFree': True},
        'targetLeftWristCenterHandLocal': target_center.tolist(), 'targetLeftWristDiametersMm': (dimensions * 1000).tolist(),
        'targetActualHeldRootHandLocal': held.tolist(), 'targetActualShaftDirectionHandLocalBind': [0., 1., 0.],
        'targetWristToGripPerpendicularDistance': float(np.linalg.norm(target_radial)), 'actualSections': records,
        'limits': 'Section AABB widths and one exact clear core line are measured fit inputs. Scale diagnostics do not select a landmark, rotation, placement or adoption. Confirm visible hand anatomy and actual compact stage; do not use total donor AABB as fitting authority.'}
    for path, value in hashes.items():
        require(sha(path) == value, 'Frozen read-only input changed')
    out.mkdir(); (out / 'measurement.json').write_text(json.dumps(report, indent=2) + '\n')
    (out / 'executed-measurement.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'output': str(out), 'sections': [{k: row[k] for k in ['planeNwnZ', 'diametersNwnXY', 'scaleForExactWristToGripDistance', 'wristWidthsAtGripDistanceScaleMm']} for row in records]}), flush=True)


if __name__ == '__main__':
    main()
