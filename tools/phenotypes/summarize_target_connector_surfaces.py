"""Derive immutable face-level review from pinned connector samples; no repair."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from connector_surface_math import closest_points_on_triangles
from place_purposebuilt_pelvis import raw_corners, read_glb


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit_path, output = args.audit.resolve(), args.output.resolve()
    require(not output.exists(), 'Fresh immutable interpretation output required')
    receipt = json.loads(audit_path.read_text())
    require(receipt['kind'] == 'target-connector-actual-surface-audit', 'Explicit surface audit required')
    require(receipt['target']['coordinateSpace'] == 'working' and receipt['statureApplications'] == 0,
            'Unscaled working-space connector audit required')
    require(all(receipt[key] is False for key in ['geometryOrMaterialsChanged', 'selectionOrLedgerChanged',
                                                'rigPilotAccepted', 'productionAccepted', 'clientAccepted']),
            'This review does not infer or revise acceptance')
    pins = dict(receipt['frozenInputs'])
    pins[str(audit_path)] = sha(audit_path)
    for path, pin in pins.items():
        require(sha(path) == pin, 'Frozen audit input differs: ' + path)
    archive_path = Path(receipt['sampleArchive']['path'])
    require(sha(archive_path) == receipt['sampleArchive']['sha256'], 'Sample archive differs')
    exposure_rows, exposed = [], []
    with np.load(archive_path, allow_pickle=False) as samples:
        for row in receipt['measurements']:
            if 'chest_terminal_cap' not in row['zone']:
                continue
            key = row['state'] + '_' + row['zone']
            bind_key = 'bind_' + row['zone']
            faces = samples[key + '_faceIds']
            require(np.array_equal(faces, samples[bind_key + '_faceIds']), 'Pose face selection changed')
            repeated_faces = np.repeat(faces, row['surfaceCoverage']['samplesPerFace'])
            weights = samples[key + '_sampleWeights']
            for view in ['front', 'left', 'right']:
                mask = samples[key + '_visible_' + view]
                measured = row['surfaceCoverage']['surfaceExposureViews'][view]
                require(int(mask.sum()) == measured['geometricallyUnoccludedSamples'], 'Sample count differs')
                area = float(weights[mask].sum())
                require(area == measured['sampleWeightedAreaSquareMetres'], 'Quadrature area differs')
                visible_faces = sorted(set(repeated_faces[mask].tolist()))
                item = {'state': row['state'], 'zone': row['zone'], 'view': view,
                        'unoccludedSamples': int(mask.sum()), 'quadratureAreaSquareMillimetres': area * 1e6,
                        'currentSerializedCandidateFaceIds': visible_faces}
                exposure_rows.append(item)
                if mask.any():
                    points = samples[key + '_samplePoints'][mask]
                    bind_points = samples[bind_key + '_samplePoints'][mask]
                    item['poseSampleBoundsMetres'] = [points.min(axis=0).tolist(), points.max(axis=0).tolist()]
                    item['bindSampleBoundsMetres'] = [bind_points.min(axis=0).tolist(), bind_points.max(axis=0).tolist()]
                    per_face = []
                    for face in visible_faces:
                        selected = mask & (repeated_faces == face)
                        per_face.append({'faceId': face, 'unoccludedSamples': int(selected.sum()),
                                         'quadratureAreaSquareMillimetres': float(weights[selected].sum() * 1e6)})
                    item['perFace'] = per_face
                    item['poseSamplePointsMetres'] = points.tolist()
                    item['bindSamplePointsMetres'] = bind_points.tolist()
                    pose_row = next(value for value in receipt['poses'] if value['state'] == row['state'])
                    pose_path = Path(pose_row['comparison'])
                    require(sha(pose_path) == pose_row['comparisonSha256'], 'Pose receipt differs')
                    pose = json.loads(pose_path.read_text())
                    specimen = next(value for value in pose['specimens'] if value.get('target'))
                    selected = next(value for value in specimen['targetPartReceipts'] if value['part'] == row['adjacent'])
                    candidate = Path(selected['candidate'])
                    require(str(candidate) in pins and sha(candidate) == selected['candidateSha256'], 'Adjacent candidate differs')
                    doc, binary = read_glb(candidate)
                    triangles = raw_corners(doc, binary)[0]
                    frame = np.asarray(specimen['jointWorldMatrices'][selected['joint']])
                    triangles = triangles @ frame[:3, :3].T + frame[:3, 3]
                    chest_frame = np.asarray(specimen['jointWorldMatrices']['torso_g'])
                    distances, directions, closest_rows = [], [], []
                    indices = np.flatnonzero(mask)
                    for index, point in zip(indices, points):
                        closest = closest_points_on_triangles(point, triangles)
                        all_distances = np.linalg.norm(closest - point, axis=1)
                        adjacent_face = int(all_distances.argmin())
                        location, distance = closest[adjacent_face], float(all_distances[adjacent_face])
                        archived_distance = float(samples[key + '_nearestDistances'][index])
                        require(abs(distance - archived_distance) <= 2e-5, 'Exhaustive nearest triangle disagrees with BVH distance')
                        delta = location - point
                        unit = delta / distance if distance else np.zeros(3)
                        local_unit = chest_frame[:3, :3].T @ unit
                        closest_rows.append({'sampleIndex': int(index), 'chestFaceId': int(repeated_faces[index]),
                                             'adjacentArmFaceId': adjacent_face, 'poseSamplePointMetres': point.tolist(),
                                             'closestActualArmPointMetres': location.tolist(), 'distanceMillimetres': distance * 1e3,
                                             'towardClosestArmDeltaWorldMetres': delta.tolist(),
                                             'towardClosestArmUnitWorld': unit.tolist(),
                                             'towardClosestArmUnitChestAttachmentLocal': local_unit.tolist(),
                                             'archivedBvhNearestDistanceMillimetres': archived_distance * 1e3})
                        distances.append(distance * 1e3)
                        directions.append(unit)
                    direction_array = np.asarray(directions)
                    item['closestActualArmDistancesMillimetres'] = {'minimum': min(distances), 'median': float(np.median(distances)),
                                                                  'maximum': max(distances)}
                    item['towardClosestArmUnitWorldComponentRanges'] = [direction_array.min(axis=0).tolist(), direction_array.max(axis=0).tolist()]
                    item['closestActualArmSamples'] = closest_rows
                    item['closestPointMeaning'] = 'Exhaustive comparison against all current posed arm triangles. Unsigned closest-point vectors are diagnostic directions, not a prescribed repair or certified inside/outside sign.'
                    exposed.append(item)
    topology_limits = {}
    for name, row in receipt['partTopologies'].items():
        if receipt['closedVolumeClassificationAvailable'][name]:
            continue
        edge_records = []
        for edge in row['nonmanifoldEdgeRecords']:
            positions = np.asarray(edge['positions'])
            edge_records.append({'incidentFaces': edge['incidentFaces'],
                                 'edgeLengthMillimetres': float(np.linalg.norm(positions[1] - positions[0]) * 1e3),
                                 'attachmentLocalPositionsMetres': edge['positions']})
        topology_limits[name] = {'closedVolumeClassificationAvailable': False,
                                'boundaryEdges': row['boundaryEdges'],
                                'nonmanifoldEdges': row['nonmanifoldEdges'],
                                'nonmanifoldVertexLinks': row['nonmanifoldVertexLinks'],
                                'nonmanifoldEdgeRecords': edge_records}
    neck_caps = [{'state': row['state'], 'zone': row['zone'],
                  'actualTriangleContactPairs': row['surfaceIntersections']['actualTriangleContactPairs'],
                  'sampledUnoccludedByView': {
                      view: values['geometricallyUnoccludedSamples']
                      for view, values in row['surfaceCoverage']['surfaceExposureViews'].items()}}
                 for row in receipt['measurements'] if row['zone'].startswith('neck_')]
    shoulders = [{'state': row['state'], 'zone': row['zone'],
                  'actualTriangleContactPairs': row['surfaceIntersections']['actualTriangleContactPairs'],
                  'intersectionCurveLengthMillimetres': row['surfaceIntersections']['distinctSegmentLengthSumMetres'] * 1e3}
                 for row in receipt['measurements'] if row['zone'].endswith('arm_proximal_cap')]
    report = {'schemaVersion': 1, 'kind': 'target-connector-surface-interpretation',
              'createdUtc': datetime.now(timezone.utc).isoformat(), 'target': receipt['target'],
              'statureApplications': 0, 'audit': str(audit_path), 'auditSha256': pins[str(audit_path)],
              'chestTerminalCapExposure': exposure_rows, 'exposedCandidateRegions': exposed,
              'neckCaps': neck_caps, 'shoulderContacts': shoulders, 'topologyClassificationLimits': topology_limits,
              'findings': [
                  'Closed stock neck has no open rim boundary; approved collar shape remains protected.',
                  'Lower neck cap intersects chest in all three sampled states. Neither neck cap has sampled exposure from front/left/right.',
                  'Stock head is open; zero upper-neck/head surface intersection does not demonstrate a disconnected neck through its open socket.',
                  'Both arm proximal connector regions intersect chest in all sampled states; these required overlaps do not measure penetration volume or independently prove a defect.',
                  'Only the left chest terminal cap in CONJURE1 .25s has sampled geometric exposure among the declared caps and three views.',
                  'Tiny exact-position-weld arm nonmanifold edges prevent certified inside/outside volume classification; actual triangle contacts and ray visibility remain measured.'
              ],
              'userAestheticApprovals': ['Collar-like neck rim is fine', 'Chest and upper arms look good'],
              'rigOrBindChangeRequiredByThisEvidence': False,
              'boundedFollowup': {
                  'adopted': False,
                  'smallestDemonstratedReviewRegion': 'Current serialized chest face IDs in exposedCandidateRegions, plus their edge-connected terminal-cap neighbors only after ownership review.',
                  'compatibleRepairPolicy': 'Review the casting-only exposed terminal patch in a matched material view. If unintended, prepare a separate bounded terminal-cap descendant and motion proof before selection; measure required direction against actual arm surfaces. These samples do not authorize trimming or prescribe displacement.',
                  'protected': receipt['repairRecommendations']['protectedGeometry'],
                  'cosmeticNeckRimRepairRecommended': False,
                  'wholeChestOrArmFitChangeRecommended': False,
                  'actualRepairSelected': False,
              },
              'limitations': receipt['limitations'] + [
                  'Exposure face IDs index the final current serialized chest candidate, not a newly inferred donor face map.',
                  'Four quadrature samples per triangle can miss smaller patches; measured area is an estimate, not an exact clipped polygon area.',
                  'No repair displacement is inferred because arm closed-volume classification is unavailable; closest-point diagnostic vectors do not certify volume sign or a safe displacement.',
                  'Nonmanifold edge length alone does not prove visible damage or identify whether coincident source geometry or serialized precision produced it.'
              ],
              'geometryOrMaterialsChanged': False, 'selectionOrLedgerChanged': False,
              'rigPilotAccepted': False, 'productionAccepted': False, 'clientAccepted': False,
              'frozenInputs': pins}
    for path, pin in pins.items():
        require(sha(path) == pin, 'Frozen input changed during interpretation: ' + path)
    output.mkdir(parents=True)
    helper = output / Path(__file__).name
    shutil.copyfile(__file__, helper)
    report['helperSnapshot'] = {'path': str(helper), 'sha256': sha(helper)}
    closure = {}
    for name in ['connector_surface_math.py', 'place_purposebuilt_pelvis.py', 'mirror_stock_limb_part.py', 'retarget.py',
                 'effective_body_contract.py']:
        source = Path(__file__).with_name(name)
        copied = output / name
        shutil.copyfile(source, copied)
        closure[str(source)] = {'snapshot': str(copied), 'sha256': sha(copied)}
    report['helperClosure'] = closure
    json_path = output / 'connector-review.json'
    json_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    patch = exposed[0] if len(exposed) == 1 else None
    summary = (
        '# Read-only connector surface review\n\n'
        'The user-approved neck collar is protected. The fixed stock neck is closed, and its lower cap intersects the chest in bind, PAUSE2 0.5 s and CONJURE1 0.25 s. '
        'Neither neck cap has sampled exposure from front, left or right. The stock head is open, so its upper connection cannot be certified using closed-volume parity.\n\n'
        'Both arm connector regions intersect the chest in all three states. '
        'The declared chest terminal caps have no sampled exposure in bind or PAUSE2. '
    )
    if patch:
        summary += ('Casting exposes ' + str(patch['unoccludedSamples']) + ' samples on the left chest terminal cap from the left side, '
                    'with quadrature area ' + format(patch['quadratureAreaSquareMillimetres'], '.6f') + ' mm². '
                    'Current serialized chest face IDs: ' + ', '.join(map(str, patch['currentSerializedCandidateFaceIds'])) + '.\n\n')
        distances = patch['closestActualArmDistancesMillimetres']
        summary += ('Exhaustive closest actual arm-triangle distances for those samples are '
                    + format(distances['minimum'], '.6f') + '–' + format(distances['maximum'], '.6f') + ' mm (median '
                    + format(distances['median'], '.6f') + ' mm). Per-sample closest points and world/chest-local directions are in the JSON. '
                    'They are unsigned diagnostic vectors, not an authorized displacement.\n\n')
    summary += (
        'The smallest demonstrated follow-up is this terminal patch and reviewed connected neighbors. '
        'No trim, displacement, fit change or repair has been selected. Preserve the accepted collar/chest shape, arms and existing material attributes.\n\n'
        'Each serialized arm has three tiny exact-position-weld nonmanifold edges; inside/outside classification therefore remains unavailable. '
        'Actual triangle contacts and directional occlusion are separate measurements. These anomalies are not independently demonstrated visible defects. '
        'Finite surface quadrature and three sampled states do not establish full motion or client acceptance.\n\n'
        'All geometry/material modification, selection and acceptance flags remain false. The JSON pins the audit, sample archive, input assets and helper snapshot.\n'
    )
    (output / 'connector-review.md').write_text(summary, encoding='utf-8')
    print(json.dumps({'receipt': str(json_path), 'sha256': sha(json_path),
                      'exposedRegions': len(exposed), 'geometryOrMaterialsChanged': False}))


if __name__ == '__main__':
    main()
