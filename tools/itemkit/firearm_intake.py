"""Reference-only pistol intake; all generation and native gates remain explicit."""
from pathlib import Path
import shutil

from tools.headkit.common import pin, require, write
from .contracts import GENERATION


def intake_pistol(reference, output, design_id):
    out = Path(output).resolve()
    require(not out.exists(), 'Use a fresh intake directory')
    (out/'intake').mkdir(parents=True)
    target = out/'intake/reference-original.png'; shutil.copyfile(reference, target)
    profile = {'schemaVersion': 1, 'kind': 'item-family', 'family': 'firearm-sling',
               'nativePackaging': 'blocked', 'materialRoute': 'diffuse', 'bakeSize': 4096,
               'runtimeTextureSize': 1024, 'firearm': {'subtype': 'pistol'},
               'sourceExport': {'remeshResolution': 768, 'targetFaceCount': 200000, 'signMode': 'udf'},
               'budgets': {'visible': 10000, 'shadow': 500, 'parts': {
                   'b': {'visible': 9992, 'shadow': 500}, 'm': {'visible': 4, 'shadow': 0},
                   't': {'visible': 4, 'shadow': 0}}},
               'allowedAssemblies': [{'b': design_id, 'm': 'hidden-placeholder', 't': 'hidden-placeholder'}],
               'notes': 'Complete pistol occupies bottom. Native packaging requires the separate verified firearm adapter; reference intake grants no fit or client approval.'}
    write(out/'family.json', profile, fresh=True)
    data = {'schemaVersion': 1, 'kind': 'item-asset', 'id': design_id, 'profile': 'pixal-single-v1',
            'generationSettings': dict(GENERATION), 'landmarks': [],
            'materials': [{'name': 'reference appearance pending review', 'region': 'whole pistol'}],
            'familyProfile': {'path': 'family.json', 'sha256': pin(out/'family.json')['sha256']},
            'inputs': {'reference': {'path': 'intake/reference-original.png', 'sha256': pin(target)['sha256']}},
            'features': [{'name': name, 'placementReviewed': False} for name in (
                'complete pistol silhouette and angled grip', 'sights and major controls',
                'trigger and open guard', 'muzzle recesses and magazine base')],
            'openings': [{'name': 'trigger-guard', 'mustRemainOpen': True}],
            'camera': {'reviewed': False, 'fovDegrees': None},
            'approval': {'referenceDesignReviewed': False, 'inputReviewComplete': False},
            'fit': {'reviewed': False},
            'processing': {'openingProbes': [], 'thicknessProbes': [], 'uvMargin': .016,
                           'cageExtrusion': .001, 'maxRayDistance': .003, 'capColour': [.08]*3},
            'clientCoverage': ['human-male', 'human-female'],
            'notes': 'Reference intake only. Review actual openings and materials; bind approved grip measurements. Select and review clay/detail conditioning explicitly before generation.'}
    write(out/'asset.json', data, fresh=True)
    return {'manifest': pin(out/'asset.json'), 'reference': pin(target), 'clayReferenceRequired': False}
