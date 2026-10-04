"""Prepare strict stock-wrist/held-shaft similarity configurations; no mesh edits."""
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
from place_purposebuilt_pelvis import read_glb, raw_corners, accessor, BASIS, require
from retarget import nodes, transforms
spec = importlib.util.spec_from_file_location('hand_placement', P / 'place-hand-v1.py')
hand = importlib.util.module_from_spec(spec); spec.loader.exec_module(hand)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(4 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    for key in ['source', 'output']:
        parser.add_argument('--' + key, type=Path, required=True)
    evidence = parser.add_mutually_exclusive_group(required=True)
    evidence.add_argument('--generation', type=Path)
    evidence.add_argument('--pending-observation', type=Path)
    args = parser.parse_args(); out = args.output.resolve()
    require(out.parent == P.resolve() and not out.exists(), 'Fresh owned output required')
    source = args.source.resolve(); generation = (args.generation or args.pending_observation).resolve()
    job = json.loads(generation.read_text())
    require(job.get('promptId') == '3565bc47-42b7-4e91-a4ce-9c9e164058f3', 'Only the current gated-exterior fresh compact job is a fitting source')
    pending = args.pending_observation is not None
    if pending:
        require(job.get('kind') == 'pending-actual-server-uv-observation' and job['finalJobCollectionRequired'] is True and
                job['selected'] is False and Path(job['target']).resolve() == source and job['sha256'] == sha(source), 'Exact pending actual observation required')
    else:
        require(job.get('state') == 'success' and any(Path(o.get('localPath', '')).resolve() == source and
                o.get('sha256') == sha(source) for o in job['outputs']), 'Actual collected source receipt required')
    root = R / 'output/phenotypes/purposebuilt-stock-inputs-v1/stock/ascii/pmh0.mdl'
    stock = P / 'stock-measurement-v1/measurement.json'; wrist_targets = P / 'selected-wrist-targets-v1/measurement.json'
    require(sha(root) == '23fc893a8d18df461052ef978f33b7805da9188546833c0620b3a6014117d45a', 'Exact stock rig required')
    measured = json.loads(wrist_targets.read_text()); target = measured['records'][0]
    wrist = next(row for row in target['forearmSectionsInHandFrame'] if abs(row['handLocalZ']) < 1e-8)
    wrist_center = np.array([*wrist['centerXY'], 0.])
    held = np.array(target['actualEquipmentInHandBind'])[:3, 3]
    world = transforms(nodes(root.read_text()))
    require(np.array_equal(np.linalg.inv(world['lhand_g']) @ world['lhand'], np.array(target['actualEquipmentInHandBind'])), 'Actual held frame differs from target receipt')
    doc, blob = read_glb(source)
    if pending:
        require(doc['nodes'] == [{'mesh': 0}] and len(doc['meshes']) == 1 and len(doc['meshes'][0]['primitives']) == 1,
                'Exact identity-node pending UV-save source required')
        primitive = doc['meshes'][0]['primitives'][0]
        positions = accessor(doc, blob, primitive['attributes']['POSITION']).astype(float)
        indices = accessor(doc, blob, primitive['indices']).reshape(-1, 3).astype(int)
        p = positions[indices] @ BASIS.T
    else:
        p, _, _, _ = raw_corners(doc, blob, allow_wrapper=True)
    core = np.array([0., -.05, -.175])
    reflection = np.diag([-1., 1., 1.])
    rz90 = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
    hypotheses = []
    out.mkdir()
    for z in [.38, .39, .40, .41, .42]:
        source_section = hand.section(p, z)
        source_anchor = np.array([*source_section['centerXY'], z])
        before = rz90 @ reflection @ (core - source_anchor)
        desired = held - wrist_center
        scale = float(np.linalg.norm(desired[[0, 2]]) / np.linalg.norm(before[[0, 2]]))
        angle = np.arctan2(desired[0], desired[2]) - np.arctan2(before[0], before[2])
        angle = float((angle + np.pi) % (2 * np.pi) - np.pi)
        c, s = np.cos(angle), np.sin(angle)
        ry = np.array([[c, 0., s], [0., 1., 0.], [-s, 0., c]])
        rotation = ry @ rz90; orthogonal = rotation @ reflection
        candidate = (p - source_anchor) @ (orthogonal * scale).T + wrist_center
        candidate_section = hand.section(candidate, 0.)
        section_width = np.diff(np.array(candidate_section['boundsXY']), axis=0)[0] * 1000
        target_width = np.array(wrist['diametersXYMm'])
        center_delta = np.array(candidate_section['centerXY']) - wrist_center[:2]
        width_relative = (section_width - target_width) / target_width
        score = float(np.sum(width_relative ** 2) + np.sum((center_delta / .03) ** 2))
        channel_origin = scale * orthogonal @ (core - source_anchor) + wrist_center
        channel_direction = orthogonal @ np.array([1., 0., 0.])
        shaft_error = float(np.linalg.norm((held - channel_origin)[[0, 2]]))
        require(shaft_error < 1e-10 and abs(np.linalg.det(rotation) - 1) < 1e-10 and
                np.array_equal(channel_direction, np.array([0., -1., 0.])), 'Strict shaft similarity derivation failed')
        cfg = {'schemaVersion': 1, 'sourceSha256': sha(source), 'generationSha256': sha(generation),
            'jobPromptId': job['promptId'], 'stockRootSha256': sha(root), 'stockMeasurementSha256': sha(stock),
            'uniformScale': scale, 'properRotationMatrixNwn': rotation.tolist(),
            'sourceAnchorNwn': source_anchor.tolist(), 'targetAnchorHandLocal': wrist_center.tolist(),
            'reflectSourceAnatomyX': True,
            'reflectionEvidence': 'Measured source palm -Y, thumb -X and distal -Z differ in chirality from actual stock left palm +X, thumb +Y, distal -Z; explicit source X reflection reverses winding and tangent W, followed by a proper Rz(+90) and shaft-axis rotation. No stock rig or animation is mirrored.',
            'orientationEvidence': 'Actual stock longsword handle axis is +Y in the identity held frame. The preserved source C grip opening runs along source X; Rz(+90) after explicit X reflection maps this to -Y, and a proper rotation about that shaft aligns the measured wrist-to-grip perpendicular vector. Exact stock lhand_g/lhand matrices remain unchanged.',
            'label': f'Strict uniform stock wrist and held-shaft fit, crown plane {z:+.3f} source units'}
        if pending:
            cfg['orientationEvidence'] = 'UNCONFIRMED final job association: proposed fit only. ' + cfg['orientationEvidence']
        filename = f'fit-z{int(round(z * 1000)):03d}.json'
        (out / filename).write_text(json.dumps(cfg, indent=2) + '\n')
        hypotheses.append({'sourceWristPlaneNwnZ': z, 'sourceSection': source_section,
            'config': str(out / filename), 'configSha256': sha(out / filename),
            'uniformScale': scale, 'additionalShaftAxisRotationDegrees': np.degrees(angle),
            'actualCandidateWristSection': candidate_section, 'actualCandidateWristWidthsMm': section_width.tolist(),
            'candidateSectionCenterDeltaMm': (center_delta * 1000).tolist(), 'widthRelativeError': width_relative.tolist(),
            'dimensionalScore': score, 'channelAxisDirectionHandLocal': channel_direction.tolist(),
            'channelToActualShaftPerpendicularErrorMetres': shaft_error,
            'boundsHandLocal': [candidate.min((0, 1)).tolist(), candidate.max((0, 1)).tolist()]})
    selected = min(hypotheses, key=lambda row: row['dimensionalScore'])
    report = {'schemaVersion': 1, 'readOnly': True, 'geometryOrRigChanged': False, 'source': str(source),
        'sourceSha256': sha(source), 'generation': str(generation), 'generationSha256': sha(generation),
        'jobPromptId': job['promptId'], 'inputHashes': {str(x): sha(x) for x in [source, generation, root, stock, wrist_targets, Path(__file__)]},
        'wristAndEquipmentTargets': str(wrist_targets), 'sourceCoreGripLineNwn': core.tolist(),
        'hypotheses': hypotheses, 'recommendedConfiguration': selected['config'],
        'recommendationOnly': True, 'pendingObservationOnly': pending,
        'limits': 'Positive uniform similarities only; exact source C-axis evidence and measured serialized donor wrist sections. Does not change P/N/UV/maps. Pending-observation configurations cannot pass placement. The score only chooses a first dimensional trial; actual both-side item wrapping, visible anatomy and moving wrist overlap still require checks.'}
    (out / 'measurement.json').write_text(json.dumps(report, indent=2) + '\n')
    (out / 'executed-preparation.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'recommended': selected['config'], 'scale': selected['uniformScale'],
        'rotation': selected['additionalShaftAxisRotationDegrees'],
        'wristWidths': selected['actualCandidateWristWidthsMm'],
        'hypotheses': [{k: row[k] for k in ['sourceWristPlaneNwnZ', 'dimensionalScore', 'actualCandidateWristWidthsMm']} for row in hypotheses]}), flush=True)


if __name__ == '__main__':
    main()
