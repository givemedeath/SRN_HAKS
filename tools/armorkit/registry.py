"""The part registry: what each armorkit part is, validated, and the names derived from it.

The registry is the source of truth for part numbers. Parts tables, model names and the file handed to
SR_NWN are all derived from it (docs/armorkit/plan.md, "Part rules" and "Handoff to SR_NWN").
"""
import json
import re
from pathlib import Path

KIND = 'srn-armorkit-registry'
RACES = {'h': 'Human', 'd': 'Dwarf', 'e': 'Elf', 'o': 'Orc', 'g': 'Troll'}
PHENOTYPES = {0: 'Fit', 2: 'Large'}
BODIES = tuple(f'p{gender}{race}{phenotype}' for gender in 'mf' for race in RACES for phenotype in PHENOTYPES)

# slot: parts table, model tokens (left then right for paired slots), item appearance fields in the same order.
# The fields are the word fields the client reads for numbers above 255 (spikes.md, section 1), names
# truncated to 16 characters as the game writes them; `models` are ITEM_APPR_ARMOR_MODEL_* indices.
SLOTS = {
    'neck': {'table': 'parts_neck', 'tokens': ('neck',), 'fields': ('xArmorPart_Neck',), 'models': (9,)},
    'chest': {'table': 'parts_chest', 'tokens': ('chest',), 'fields': ('xArmorPart_Torso',), 'models': (7,)},
    'belt': {'table': 'parts_belt', 'tokens': ('belt',), 'fields': ('xArmorPart_Belt',), 'models': (8,)},
    'pelvis': {'table': 'parts_pelvis', 'tokens': ('pelvis',), 'fields': ('xArmorPart_Pelvi',), 'models': (6,)},
    'robe': {'table': 'parts_robe', 'tokens': ('robe',), 'fields': ('xArmorPart_Robe',), 'models': (18,)},
    'shoulder': {'table': 'parts_shoulder', 'tokens': ('shol', 'shor'),
                 'fields': ('xArmorPart_LShou', 'xArmorPart_RShou'), 'models': (15, 14)},
    'bicep': {'table': 'parts_bicep', 'tokens': ('bicepl', 'bicepr'),
              'fields': ('xArmorPart_LBice', 'xArmorPart_RBice'), 'models': (13, 12)},
    'forearm': {'table': 'parts_forearm', 'tokens': ('forel', 'forer'),
                'fields': ('xArmorPart_LFArm', 'xArmorPart_RFArm'), 'models': (11, 10)},
    'hand': {'table': 'parts_hand', 'tokens': ('handl', 'handr'),
             'fields': ('xArmorPart_LHand', 'xArmorPart_RHand'), 'models': (17, 16)},
    'thigh': {'table': 'parts_legs', 'tokens': ('legl', 'legr'),
              'fields': ('xArmorPart_LThig', 'xArmorPart_RThig'), 'models': (4, 5)},
    'shin': {'table': 'parts_shin', 'tokens': ('shinl', 'shinr'),
             'fields': ('xArmorPart_LShin', 'xArmorPart_RShin'), 'models': (3, 2)},
    'foot': {'table': 'parts_foot', 'tokens': ('footl', 'footr'),
             'fields': ('xArmorPart_LFoot', 'xArmorPart_RFoot'), 'models': (1, 0)},
}
TABLES = tuple(sorted({row['table'] for row in SLOTS.values()}))

# The joints each fitted slot ends on. Accessory slots (neck, belt, shoulder, robe) may declare a subset.
JOINTS = ('neck', 'shoulder', 'elbow', 'wrist', 'waist', 'hip', 'knee', 'ankle')
SLOT_JOINTS = {'chest': ('neck', 'shoulder', 'waist'), 'pelvis': ('waist', 'hip'), 'bicep': ('shoulder', 'elbow'),
               'forearm': ('elbow', 'wrist'), 'hand': ('wrist',), 'thigh': ('hip', 'knee'), 'shin': ('knee', 'ankle'),
               'foot': ('ankle',), 'neck': ('neck',), 'belt': ('waist',), 'shoulder': ('shoulder',), 'robe': ()}
FITTED = ('chest', 'pelvis', 'bicep', 'forearm', 'hand', 'thigh', 'shin', 'foot')
TIERS = (0, 1, 2, 3)  # skin-tight, cloth, padded or armored, heavy
MESHES = {'rigid': FITTED + ('belt', 'shoulder', 'neck'), 'dangly': ('belt',), 'skinned': ('belt', 'neck', 'robe')}
CHANNELS = ('cloth1', 'cloth2', 'leather1', 'leather2', 'metal1', 'metal2', 'skin')
NECK_CATEGORIES = ('headgear', 'back', 'neckwear', 'torso')
# Where a part may show a logo. A logo is one cell of a shared strip, read through a shared material and
# picked per wearer (plan.md, revision "logos use the shader value"). The material and the logo cells are
# Phase 1 work, so nothing about them is derived here yet.
BADGE_POSITIONS = {'shoulder': ('left', 'right'), 'neck': ('lanyard',)}
ROBE_HIDES = ('FOOTR', 'FOOTL', 'SHINR', 'SHINL', 'LEGR', 'LEGL', 'PELVIS', 'CHEST', 'BELT', 'NECK', 'FORER',
              'FOREL', 'BICEPR', 'BICEPL', 'SHOR', 'SHOL', 'HANDR', 'HANDL', 'HEAD')

# Stock tables hold rows 0-200 (parts_robe 0-38) and stock models run to 255; 256-299 stay empty as a buffer.
FIRST_NUMBER = 300
FIELD_LIMIT = 65535  # the item field is a word; names stay within 16 characters up to 99999
# Numbers by digit (plan.md, revision "part numbers by digit"): 300-999 are test parts and never published,
# 1000-2999 are standalone pieces, and each family has one thousand. In a family thousand the hundreds digit
# is a group, the tens digit a set and the units digit a variant. Runner and role sets come last so that they
# can grow into the numbers from 10000, which stay closed until that is decided.
TEST, STANDALONE = 'test', 'standalone'
FAMILY_BLOCKS = ('civilian', 'workwear', 'corporate', 'security', 'gang', 'heavy', 'runner')
BLOCKS = ((300, 999, TEST), (1000, 2999, STANDALONE)) + tuple(
    (3000 + 1000 * index, 3999 + 1000 * index, family) for index, family in enumerate(FAMILY_BLOCKS))
LAST_NUMBER = BLOCKS[-1][1]
FAMILIES = ('accessory',) + FAMILY_BLOCKS
# Standalone neck parts are numbered by their category, the only label a number list shows.
NECK_BANDS = {'headgear': (1000, 1499), 'back': (1500, 1999), 'neckwear': (2000, 2499), 'torso': (2500, 2999)}

PART_KEYS = {'slot', 'number', 'set', 'group', 'families', 'genderedCut', 'tiers', 'neckCategory', 'coverage',
             'channels', 'badge', 'bodies', 'mesh', 'sides', 'hide'}
REQUIRED = PART_KEYS - {'set', 'group', 'neckCategory', 'sides', 'hide'}
TAG = re.compile(r'[a-z0-9][a-z0-9-]{0,31}')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def block(number):
    """The block a number belongs to: `test`, `standalone` or the family of its thousand."""
    for first, last, name in BLOCKS:
        if first <= number <= last:
            return name
    raise ValueError(f'Part number {number} is outside every block')


def model_name(body, token, number):
    """`p<m|f><race><phenotype>_<slot><number>`: three digits below 1000, the plain number above."""
    name = f'{body}_{token}{number:03d}'
    require(body in BODIES and len(name) <= 16, 'Model name exceeds 16 characters or names no SRN body: ' + name)
    return name


def tokens(part):
    row = SLOTS[part['slot']]
    sides = part.get('sides')
    return tuple(token for token in row['tokens'] if sides is None or token[-1] in sides)


def model_names(part):
    """{body: [model resref, ...]} for the bodies the part exists on."""
    return {body: [model_name(body, token, part['number']) for token in tokens(part)] for body in part['bodies']}


def texture_names(part):
    """The tint texture of each Human Fit model per gender present.

    Race versions keep these names in their meshes. A model that names its own, missing texture falls back
    to them across race (spikes.md, section 11); across gender or build that fallback is not proven."""
    genders = sorted({body[1] for body in part['bodies']})
    return [model_name(f'p{gender}h0', token, part['number']) for gender in genders for token in tokens(part)]


def _unique(values, allowed, label, *, empty=False):
    require(isinstance(values, list) and (empty or values) and all(isinstance(value, str) for value in values)
            and len(set(values)) == len(values) and all(value in allowed for value in values),
            f'{label} must be a list of distinct values from {list(allowed)}')


def validate_part(part, *, publish=False):
    require(isinstance(part, dict) and REQUIRED <= set(part) <= PART_KEYS,
            'Part keys must be ' + ', '.join(sorted(REQUIRED)) + ' plus optional set, group, neckCategory, sides, hide')
    slot, number = part['slot'], part['number']
    require(isinstance(slot, str) and slot in SLOTS, f'Unknown slot {slot!r}')
    label = f'{slot} {number}'
    require(type(number) is int and FIRST_NUMBER <= number,
            f'{label}: numbers start at {FIRST_NUMBER}; stock rows, stock models and the 256-299 buffer are never reused')
    require(number <= LAST_NUMBER,
            f'{label}: numbers from {LAST_NUMBER + 1} are kept for more runner and role sets and are not open yet')
    _unique(part['families'], FAMILIES, label + ': families')
    name = block(number)
    in_family = name in FAMILY_BLOCKS
    require(not in_family or name in part['families'], f'{label}: numbers in this block belong to the {name} family')
    require(not publish or name != TEST, f'{label}: numbers 300-999 are test parts and are never published')
    for key in ('set', 'group'):
        require(key not in part or (isinstance(part[key], str) and TAG.fullmatch(part[key])),
                f'{label}: {key} must be a lowercase tag')
    require(not in_family or ('set' in part and 'group' in part),
            f'{label}: a part in a family block names its set and its group')
    require(name != STANDALONE or ('set' not in part and 'group' not in part),
            f'{label}: numbers 1000-2999 are standalone pieces, which belong to no set or group')
    require(type(part['genderedCut']) is bool, label + ': genderedCut must be true or false')
    require(slot != 'chest' or part['genderedCut'], label + ': the chest is always a separate male and female cut')
    tiers = part['tiers']
    joints = SLOT_JOINTS[slot]
    require(isinstance(tiers, dict) and set(tiers) <= set(joints) and all(type(v) is int and v in TIERS for v in tiers.values()),
            f'{label}: tiers map {list(joints)} to 0-3')
    require(slot not in FITTED or set(tiers) == set(joints), f'{label}: a fitted part declares a tier at each of {list(joints)}')
    require(isinstance(part['mesh'], str) and part['mesh'] in MESHES and slot in MESHES[part['mesh']],
            f'{label}: mesh {part["mesh"]!r} is not allowed on this slot')
    require((slot == 'neck') == ('neckCategory' in part), label + ': neckCategory belongs to neck parts, and every neck part has one')
    require(slot != 'neck' or (isinstance(part['neckCategory'], str) and part['neckCategory'] in NECK_CATEGORIES),
            f'{label}: neckCategory must be one of {list(NECK_CATEGORIES)}')
    if slot == 'neck' and name == STANDALONE:
        first, last = NECK_BANDS[part['neckCategory']]
        require(first <= number <= last,
                f'{label}: standalone {part["neckCategory"]} neck parts are numbered {first}-{last}')
    coverage = part['coverage']
    require(isinstance(coverage, dict) and set(coverage) == {'skin', 'headgear'} and all(type(v) is bool for v in coverage.values()),
            label + ': coverage is {skin: bool, headgear: bool}')
    require(not coverage['headgear'] or part.get('neckCategory') == 'headgear', label + ': headgear is a neck part of category headgear')
    _unique(part['channels'], CHANNELS, label + ': channels')
    require(coverage['skin'] == ('skin' in part['channels']), label + ': exposed skin uses the skin channel, and only exposed skin does')
    badge = part['badge']
    if badge is not None:
        require(slot in BADGE_POSITIONS, label + ': logos live only on shoulder parts and neck-slot lanyards')
        require(isinstance(badge, dict) and set(badge) == {'positions'}, label + ': badge is null or {positions: [...]}')
        _unique(badge['positions'], BADGE_POSITIONS[slot], label + ': badge positions')
    if 'sides' in part:
        require(len(SLOTS[slot]['tokens']) == 2, label + ': sides belongs to paired slots')
        _unique(part['sides'], ('l', 'r'), label + ': sides')
        require(badge is None or all({'left': 'l', 'right': 'r'}[p] in part['sides'] for p in badge['positions']),
                label + ': a badge needs its side of the part')
    if 'hide' in part:
        require(slot == 'robe', label + ': hide belongs to robe parts')
        _unique(part['hide'], ROBE_HIDES, label + ': hide', empty=True)
    _unique(part['bodies'], BODIES, label + ': bodies')
    require(not publish or set(part['bodies']) == set(BODIES), label + ': a published number exists on all 20 bodies')
    model_names(part)
    return part


def validate(data, *, publish=False):
    """Check a registry document and return its parts ordered by slot and number."""
    require(isinstance(data, dict) and set(data) == {'schemaVersion', 'kind', 'parts'} and data['schemaVersion'] == 1
            and data['kind'] == KIND and isinstance(data['parts'], list), 'Unsupported registry document')
    seen, owners = set(), {}
    for part in data['parts']:
        validate_part(part, publish=publish)
        key = (part['slot'], part['number'])
        require(key not in seen, f'Duplicate part {key[0]} {key[1]}')
        seen.add(key)
        # A set uses the same number in every slot it covers and the next units for its variants, so ten
        # numbers never belong to two sets; in the same way a hundred never belongs to two groups.
        for kind, size in (('set', 10), ('group', 100)):
            if kind in part:
                first = part['number'] // size * size
                owner = owners.setdefault((kind, first), part[kind])
                require(owner == part[kind],
                        f'Numbers {first}-{first + size - 1} are used by two {kind}s: {owner} and {part[kind]}')
    return sorted(data['parts'], key=lambda part: (part['slot'], part['number']))


def load(path, *, publish=False):
    with Path(path).open(encoding='utf-8-sig') as stream:
        return validate(json.load(stream), publish=publish)


def numbers(parts, slot):
    """Sorted live numbers of one slot."""
    return sorted(part['number'] for part in parts if part['slot'] == slot)


def handoff(parts):
    """The registry as SR_NWN consumes it: each part with the table, item fields and model names it implies.

    A part in a family block also carries `setNumber` (its number with the units digit at 0) and `variant`
    (the units digit). A part's `badge` says where it shows a logo. The handoff does not yet name the shared
    logo material, its parameter or the logo cells (plan.md, revision "logos use the shader value"); that
    entry is Phase 1 work."""
    rows = []
    for part in parts:
        slot = SLOTS[part['slot']]
        used = [slot['tokens'].index(token) for token in tokens(part)]
        number, name = part['number'], block(part['number'])
        digits = {'setNumber': number - number % 10, 'variant': number % 10} if name in FAMILY_BLOCKS else {}
        rows.append({**part, 'table': slot['table'], 'block': name, **digits,
                     'itemFields': [slot['fields'][i] for i in used], 'itemModelIndices': [slot['models'][i] for i in used],
                     'models': model_names(part), 'tintTextures': texture_names(part)})
    return {'schemaVersion': 1, 'kind': KIND + '-handoff', 'parts': rows}
