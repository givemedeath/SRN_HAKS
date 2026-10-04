"""Explicit stock Human limb ownership and recursive native receipt contracts."""
import json
from pathlib import Path

from stage_stock_part import require, sha

ATTACHMENTS = {'legl': 'lthigh_g', 'legr': 'rthigh_g', 'shinl': 'lshin_g', 'shinr': 'rshin_g',
               'footl': 'lfoot_g', 'footr': 'rfoot_g', 'bicepl': 'lbicep_g', 'bicepr': 'rbicep_g',
               'forel': 'lforearm_g', 'forer': 'rforearm_g', 'handl': 'lhand_g', 'handr': 'rhand_g'}
OPPOSITE = {'legl': 'legr', 'legr': 'legl', 'shinl': 'shinr', 'shinr': 'shinl',
            'footl': 'footr', 'footr': 'footl', 'bicepl': 'bicepr', 'bicepr': 'bicepl',
            'forel': 'forer', 'forer': 'forel', 'handl': 'handr', 'handr': 'handl'}
PAIRS = (('legl', 'legr'), ('shinl', 'shinr'), ('footl', 'footr'),
         ('bicepl', 'bicepr'), ('forel', 'forer'), ('handl', 'handr'))
FAMILIES = tuple(family for left, right in PAIRS for family in ({left}, {left, right}))
BASE_PARTS = {'chest', 'pelvis'}
DEFAULT_PRESERVED_PARTS = 'chest,pelvis'  # Historical thigh CLI compatibility only.


def parse_preserved_parts(value=DEFAULT_PRESERVED_PARTS):
    parts = value.split(',')
    require(len(parts) == len(set(parts)) and BASE_PARTS <= set(parts)
            and set(parts) <= BASE_PARTS | set(ATTACHMENTS), 'Invalid/duplicate/undeclared preserved parts')
    for left, right in PAIRS:
        require((left in parts) == (right in parts), 'Preserved limb family must be an accepted complete pair')
    require('shinl' not in parts or {'legl', 'legr'} <= set(parts), 'Preserved shins require accepted thighs')
    require('footl' not in parts or {'legl', 'legr', 'shinl', 'shinr'} <= set(parts),
            'Preserved feet require accepted thigh and shin pairs')
    require('forel' not in parts or {'bicepl', 'bicepr'} <= set(parts),
            'Preserved forearms require accepted upper-arm pair')
    require('handl' not in parts or {'bicepl', 'bicepr', 'forel', 'forer'} <= set(parts),
            'Preserved hands require accepted upper-arm and forearm pairs')
    return {'pmh0_' + part + '001.mdl' for part in parts}


def validate_new_parts(parts, preserved):
    require(len(parts) == len(set(parts)) and set(parts) in FAMILIES,
            'Expected first left donor, or left and right of one limb family together')
    require(not {'pmh0_' + part + '001.mdl' for part in parts} & preserved,
            'New replacements overlap explicitly preserved parts')
    if 'shinl' in parts:
        require({'pmh0_legl001.mdl', 'pmh0_legr001.mdl'} <= preserved,
                'Shin continuation requires explicit preserved accepted thigh pair')
    if 'footl' in parts:
        require({'pmh0_' + p + '001.mdl' for p in ('legl', 'legr', 'shinl', 'shinr')} <= preserved,
                'Foot continuation requires explicit preserved accepted thigh and shin pairs')
    if 'forel' in parts:
        require({'pmh0_bicepl001.mdl', 'pmh0_bicepr001.mdl'} <= preserved,
                'Forearm continuation requires explicit preserved accepted upper-arm pair')
    if 'handl' in parts:
        require({'pmh0_' + p + '001.mdl' for p in ('bicepl', 'bicepr', 'forel', 'forer')} <= preserved,
                'Hand continuation requires explicit preserved accepted upper-arm and forearm pairs')


def validate_mirror_association(donor, source_joint, target_joint):
    part = donor.get('part', donor.get('configuration', {}).get('part'))
    require(part in ATTACHMENTS and source_joint == ATTACHMENTS[part]
            and target_joint == ATTACHMENTS[OPPOSITE[part]], 'Mirror crosses limb family or donor joint')
    require(donor.get('joint', donor.get('configuration', {}).get('joint')) == source_joint,
            'Mirror source joint differs from fitted donor')


def validate_receipt_lineage(native, require_composition=True, seen=None):
    """Verify nested actual compile unions; allow both old and new provenance forms."""
    seen = set() if seen is None else seen
    require(len(seen) < 32, 'Excessive/cyclic native receipt lineage')
    composition = native.get('composition', {})
    require(not (composition.get('sourceReceipts') and composition.get('perModelReceipts')),
            'Ambiguous native composition provenance')
    sources = composition.get('sourceReceipts')
    if sources is None:
        origins = composition.get('perModelReceipts')
        if origins is None:
            require(not require_composition, 'Native donor lacks independent composition provenance')
            return
        require(set(origins) == {row['name'] for row in native['models']},
                'Legacy accepted provenance model keys differ')
        sources = list(origins.values())
    require(isinstance(sources, list) and len(sources) >= 2, 'Composition lacks independent compile units')
    models = {row['name']: row for row in native['models']}
    require(len(models) == len(native['models']), 'Duplicate combined model entries')
    found = set(); dependencies = {}
    for origin in sources:
        path = Path(origin['path']).resolve()
        require(path not in seen and sha(path) == origin['sha256'], 'Independent source compile receipt changed/cyclic')
        original = json.loads(path.read_text())
        require(original.get('complete') is True and original.get('clientSha256') == native['clientSha256'],
                'Independent compiler receipt incomplete/different client')
        names = [row['name'] for row in original['models']]
        require(len(names) == len(set(names)) and set(names) == set(origin['models'])
                and len(origin['models']) == len(set(origin['models'])) and not found & set(names),
                'Independent model ownership overlaps/differs')
        require(origin.get('materialResourceHashes') == original.get('materialResourceHashes'),
                'Independent source material provenance differs')
        for row in original['models']:
            require(models.get(row['name']) == row, 'Combined model differs from actual independent compilation')
        require(not dependencies.keys() & original['materialResourceHashes'].keys(),
                'Independent material ownership overlaps')
        dependencies.update(original['materialResourceHashes']); found.update(names)
        validate_receipt_lineage(original, False, seen | {path})
    require(found == set(models) and dependencies == native['materialResourceHashes'],
            'Independent source compile union differs from candidate')
