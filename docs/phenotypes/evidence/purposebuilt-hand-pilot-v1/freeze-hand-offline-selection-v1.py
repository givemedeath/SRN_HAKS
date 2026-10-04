"""Freeze the practical hand pair for root native/body integration, not client acceptance."""
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent; R = P.parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    out = P / 'selected-offline-v1'
    if out.exists():
        raise RuntimeError('Fresh selection output required')
    left = P / 'left-uniform-stock-v1/placed-local.glb'
    right = P / 'right-uniform-stock-mirror-v1/mirrored-local.glb'
    if sha(left) != 'a65969da012dc41661747f76e2585286e2e4f3cfad9fffcd852948694ea4fc0d' or sha(right) != '58d803f87abaac491be54201aba9daced6b08096898af61aefade314327c5fc1':
        raise RuntimeError('Actual selected pair changed')
    fore = R / 'output/phenotypes/purposebuilt-forearm-pilot-v1/hand-shell-diagnosis-v1'
    evidence = [P / path for path in ['left-uniform-stock-v1/placement.json',
        'right-uniform-stock-mirror-v1/mirror.json', 'left-stage-prepared-v1/map-extraction.json',
        'right-stage-prepared-v1/map-extraction.json', 'clean-compact-topology-v1/index.json',
        'clean-output-basis-v1/measurement.json', 'fitted-texture-wrist-review-v1/review.json',
        'equipment-max-wrist-review-v1/review.json', 'equipment-max-held-review-v1/review.json',
        'clean-exterior-512-normal-polish-v2/normal-polish.json']]
    evidence.append(fore / 'final-hand-pair-wrist-local-intervals-v1.json')
    seams = json.loads(evidence[-1].read_text())
    if seams['stockComparableRays'] != 4374 or seams['newWristGapsOverStockPlus1mm'] or seams['excludedRays']:
        raise RuntimeError('Actual practical wrist evidence failed')
    job = R / 'output/phenotypes/human-male-complete-goal-v1/clean-hand-retexture-v2/generation.json'
    record = {'schemaVersion': 1, 'status': 'practical-offline-geometry-pair-ready-for-root-native-integration',
        'scope': 'Latest user direction: wrap the hands up soon; they do not need to be perfect. No further fine cosmetic source trials.',
        'parts': [{'part': part, 'model': f'pmh0_{part}001', 'source': str(source.resolve()), 'sha256': sha(source)}
                  for part, source in [('handl', left), ('handr', right)]],
        'finalGeneration': {'path': str(job), 'sha256': sha(job), 'promptId': '3565bc47-42b7-4e91-a4ce-9c9e164058f3'},
        'uniformScale': .16561695430321036, 'sourceWristAnchorNwnZ': .39,
        'properHeldShaftRotationDegrees': 19.326583956217448,
        'canonicalSourceChiralityReflectionExplicit': True, 'oppositeSideExactDetachedStockFrameMirror': True,
        'stockRigAnimationsAttachmentsAndHeightChanged': False, 'equipmentScaling': 'stock-identity',
        'mapAndUvBytesChangedByFittingOrMirror': False, 'authoredNormalAndTangentMagnitudePreserved': True,
        'tangentHandednessFlipsPerReflection': True, 'normalMapStrength': 1,
        'stageConfigurations': [str(P / side / 'stage-config.json') for side in ['left-stage-prepared-v1', 'right-stage-prepared-v1']],
        'evidence': [{'path': str(path.resolve()), 'sha256': sha(path)} for path in evidence],
        'practicalMovingWrist': {'cases': 243, 'comparableRays': 4374, 'excludedRays': 0,
            'newGaps': 0, 'minimumOccupiedOverlapMetres': seams['minimumWristOverlapMetres']},
        'visualReviewScope': 'Six bind CPU views, four actual-texture wrist views, and representative candidate/stock weapon and shield views at maximum sampled wrist/held rotations. 32 captures per selected pose exist; only representative views were spot-reviewed.',
        'disclosedLimits': ['Fresh49,990-face compact has eight tiny crossing pairs (maximum about0.624mm at actual scale) and one pinched vertex link introduced by QEM; retained under the coordinator’s measured micro-imperfection decision and latest user scope. Edge boundary/nonmanifold/winding and degeneracy counts are zero; do not claim all vertex links/intersections are clean.',
            'Selected forearm end shows through the front wrist crown, especially in extreme poses. No empty wrist opening on sampled contact rays; the visible cap patch remains for whole-body/client assessment.',
            'At maximum sampled73-degree held-dummy rotation, shaft sweeps diagonally through the left palm in the unchanged stock animation; the stock mitten also penetrates. No collision-free item claim.',
            'RawGLB hand is red/glossy relative to raw forearm. Root owns native palette/AO/roughness calibration, preserving source geometry and normal basis.',
            'Finite CPU/controller samples and EEVEE previews do not replace native or actual client lighting, motion, stability and performance checks.'],
        'nativeCompiledByWorker': False, 'clientTested': False, 'productionWholeBodyAccepted': False,
        'remainingRootWork': ['Calibrate new hand effective skin/roughness against selected forearms without repeating AO',
            'Independent native P/N/UV/T/sign proofs', 'Cumulative full-body offline assembly and package inventory',
            'Authorized whole-body actual client tests and animation reference sheet'],
        'helperSha256': sha(__file__)}
    out.mkdir(); (out / 'selection.json').write_text(json.dumps(record, indent=2) + '\n')
    (out / 'executed-freezer.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'selection': str(out / 'selection.json'), 'sha256': sha(out / 'selection.json')}), flush=True)


if __name__ == '__main__':
    main()
