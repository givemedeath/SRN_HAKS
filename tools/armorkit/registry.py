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
BADGE_POSITIONS = {'shoulder': ('left', 'right'), 'neck': ('lanyard',)}
BLANK_LOGO = 'srn_logo_0'
ROBE_HIDES = ('FOOTR', 'FOOTL', 'SHINR', 'SHINL', 'LEGR', 'LEGL', 'PELVIS', 'CHEST', 'BELT', 'NECK', 'FORER',
              'FOREL', 'BICEPR', 'BICEPL', 'SHOR', 'SHOL', 'HANDR', 'HANDL', 'HEAD')

# Stock tables hold rows 0-200 (parts_robe 0-38) and stock models run to 255; 256-299 stay empty as a buffer.
FIRST_NUMBER = 300
LAST_NUMBER = 65535  # the word field's range; names stay within 16 characters up to 99999
# Blocks as widened by the user on 2026-11-10 (plan.md, revision of that date): accessories get the widest
# band, every family one thousand numbers.
BLOCKS = ((300, 2999, 'accessory'), (3000, 3999, 'civilian'), (4000, 4999, 'workwear'), (5000, 5999, 'corporate'),
          (6000, 6999, 'security'), (7000, 7999, 'runner'), (8000, 8999, 'gang'), (9000, LAST_NUMBER, None))
FAMILIES = tuple(name for _, _, name in BLOCKS if name) + ('heavy',)

PART_KEYS = {'slot', 'number', 'set', 'families', 'genderedCut', 'tiers', 'neckCategory', 'coverage', 'channels',
             'badge', 'bodies', 'mesh', 'sides', 'hide'}
REQUIRED = PART_KEYS - {'set', 'neckCategory', 'sides', 'hide'}
TAG = re.compile(r'[a-z0-9][a-z0-9-]{0,31}')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def block(number):
    """The family a number's block belongs to; None for the open block from 9000."""
    for first, last, family in BLOCKS:
        if first <= number <= last:
            return family
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
    """The tint texture of each Human model per gender present; other bodies fall back to these."""
    genders = sorted({body[1] for body in part['bodies']})
    return [model_name(f'p{gender}h0', token, part['number']) for gender in genders for token in tokens(part)]


def _unique(values, allowed, label, *, empty=False):
    require(isinstance(values, list) and (empty or values) and len(set(values)) == len(values)
            and all(value in allowed for value in values), f'{label} must be a list of distinct values from {list(allowed)}')


def validate_part(part, *, publish=False):
    require(isinstance(part, dict) and REQUIRED <= set(part) <= PART_KEYS,
            'Part keys must be ' + ', '.join(sorted(REQUIRED)) + ' plus optional set, neckCategory, sides, hide')
    slot, number = part['slot'], part['number']
    require(slot in SLOTS, f'Unknown slot {slot!r}')
    label = f'{slot} {number}'
    require(type(number) is int and FIRST_NUMBER <= number <= LAST_NUMBER,
            f'{label}: numbers start at {FIRST_NUMBER}; stock rows, stock models and the 256-299 buffer are never reused')
    _unique(part['families'], FAMILIES, label + ': families')
    family = block(number)
    require(family is None or family in part['families'], f'{label}: numbers in this block belong to the {family} family')
    if 'set' in part:
        require(isinstance(part['set'], str) and TAG.fullmatch(part['set']), label + ': set must be a lowercase tag')
    require(type(part['genderedCut']) is bool, label + ': genderedCut must be true or false')
    require(slot != 'chest' or part['genderedCut'], label + ': the chest is always a separate male and female cut')
    tiers = part['tiers']
    joints = SLOT_JOINTS[slot]
    require(isinstance(tiers, dict) and set(tiers) <= set(joints) and all(type(v) is int and v in TIERS for v in tiers.values()),
            f'{label}: tiers map {list(joints)} to 0-3')
    require(slot not in FITTED or set(tiers) == set(joints), f'{label}: a fitted part declares a tier at each of {list(joints)}')
    require(part['mesh'] in MESHES and slot in MESHES[part['mesh']], f'{label}: mesh {part["mesh"]!r} is not allowed on this slot')
    require((slot == 'neck') == ('neckCategory' in part), label + ': neckCategory belongs to neck parts, and every neck part has one')
    require(slot != 'neck' or part['neckCategory'] in NECK_CATEGORIES, f'{label}: neckCategory must be one of {list(NECK_CATEGORIES)}')
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
        require(badge is None or all({'left': 'l', 'right': 'r'}.get(p, 'l') in part['sides'] for p in badge['positions']),
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
    seen, sets = set(), {}
    for part in data['parts']:
        validate_part(part, publish=publish)
        key = (part['slot'], part['number'])
        require(key not in seen, f'Duplicate part {key[0]} {key[1]}')
        seen.add(key)
        # A set uses one number in every slot it covers, so a number never belongs to two sets.
        owner = sets.setdefault(part['number'], part.get('set'))
        require(owner == part.get('set'), f'Number {part["number"]} is used by two sets: {owner} and {part.get("set")}')
    return sorted(data['parts'], key=lambda part: (part['slot'], part['number']))


def load(path, *, publish=False):
    with Path(path).open(encoding='utf-8-sig') as stream:
        return validate(json.load(stream), publish=publish)


def numbers(parts, slot):
    """Sorted live numbers of one slot."""
    return sorted(part['number'] for part in parts if part['slot'] == slot)


def handoff(parts):
    """The registry as SR_NWN consumes it: each part with the table, item fields and model names it implies."""
    rows = []
    for part in parts:
        slot = SLOTS[part['slot']]
        used = [slot['tokens'].index(token) for token in tokens(part)]
        rows.append({**part, 'table': slot['table'], 'block': block(part['number']),
                     'itemFields': [slot['fields'][i] for i in used], 'itemModelIndices': [slot['models'][i] for i in used],
                     'models': model_names(part), 'tintTextures': texture_names(part),
                     'logoTexture': BLANK_LOGO if part['badge'] else None})
    return {'schemaVersion': 1, 'kind': KIND + '-handoff', 'parts': rows}
