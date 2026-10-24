"""Private Sling multipart contracts; no changes to legacy melee adapters.

This module plans explicit assemblies, not arbitrary cross-design combinations.
Native compilation and client validation remain separate gates.
"""
import hashlib
import re

from tools.headkit.common import require
from .contracts import integer, resref, twoda


SLOTS = {'pistol': 'b', 'smg': 'm', 'rifle': 't'}
PART_FIELDS = {'b': 'ModelPart1', 'm': 'ModelPart2', 't': 'ModelPart3'}


def sling_row(table):
    """Resolve identity from the effective table; never silently adopt another row."""
    rows = twoda(table.decode('utf-8-sig'))
    found = [(key, row) for key, row in rows.items()
             if row.get('label', '').lower() == 'sling']
    require(len(found) == 1, 'One effective Sling row required')
    key, row = found[0]
    require(key == '61' and row['ItemClass'].lower() == 'wbwsl',
            'Unexpected Sling BaseItem or ItemClass; review the installed contract')
    require(row['ModelType'] in ('0', '2'), 'Unsupported effective Sling ModelType')
    require(0 <= int(row['MinRange']) <= int(row['MaxRange']) <= 255,
            'Sling appearance range must fit a byte')
    return key, row


def part_name(part, index, colour):
    require(part in PART_FIELDS, 'Unknown firearm slot')
    integer(index, 1, 25, 'model index')
    integer(colour, 1, 9, 'colour index')
    integer(index * 10 + colour, 11, 255, 'encoded appearance')
    return resref(f'wbwsl_{part}_{index * 10 + colour:03d}')


def plan(subtype, colours, occupied, texture_prefix, blueprint_prefix):
    """Reserve a whole shape index, including other colours and orphan icons.

    Placeholders are private resources too: existing ones cannot be silently
    reused without an exact byte-bound adoption contract. This first trial
    therefore fails on a placeholder collision.
    """
    require(subtype in SLOTS, 'Unknown firearm subtype')
    require(isinstance(colours, (list, tuple)) and len(colours) >= 1,
            'At least one explicit Color required')
    require(len(set(colours)) == len(colours), 'Duplicate Color')
    for colour in colours:
        integer(colour, 1, 9, 'colour index')
    colours = sorted(colours)
    # Toolset Color discovery expects a contiguous range.
    require(colours == list(range(colours[0], colours[-1] + 1)), 'Contiguous Colors required')
    resref(texture_prefix); resref(blueprint_prefix)
    occupied = {name.lower() for name in occupied}
    slot = SLOTS[subtype]
    placeholders = {part_name(p, 1, c) for p in PART_FIELDS for c in colours}
    def resource_names(model):
        return {model + '.mdl', 'i' + model + '.tga', 'i' + model + '.dds'}
    require(not set().union(*(resource_names(n) for n in placeholders)) & occupied,
            'Placeholder resource collision')
    # Reserve one design's entire shape slot, so a later Color cannot overwrite
    # an older finish. Build the occupied index set once rather than rescanning.
    pattern = re.compile(rf'^i?wbwsl_{slot}_(\d{{3}})\.(?:mdl|tga|dds)$')
    taken = {int(m.group(1)) // 10 for name in occupied if (m := pattern.fullmatch(name))}
    candidates = [i for i in range(2, 26) if i not in taken and i * 10 + colours[-1] <= 255]
    require(candidates, 'No collision-free firearm shape index')
    index = candidates[0]
    variants = []
    all_resources = set().union(*(resource_names(n) - {('i' + n + '.dds')} for n in placeholders))
    for colour in colours:
        models = {p: part_name(p, index if p == slot else 1, colour) for p in PART_FIELDS}
        texture = resref(f'{texture_prefix}_{index:02d}{colour}')
        blueprint = resref(f'{blueprint_prefix}_{colour}')
        require(not {texture + ext for ext in ('.tga', '.dds', '.txi', '.mtr')} & occupied,
                'Texture resource collision')
        require(blueprint + '.uti' not in occupied, 'Blueprint resource collision')
        names = {models[slot]+'.mdl', 'i'+models[slot]+'.tga', texture+'.tga', blueprint+'.uti'}
        require(not names & all_resources, 'Generated resource aliases another variant or placeholder')
        all_resources |= names
        variants.append({'colour': colour, 'models': models,
                         'icons': {p: 'i'+name for p, name in models.items()},
                         'utiParts': {PART_FIELDS[p]: (index if p == slot else 1)*10+colour
                                      for p in PART_FIELDS},
                         'texture': texture, 'blueprint': blueprint})
    return {'schemaVersion': 1, 'baseItem': 61, 'itemClass': 'wbwsl', 'modelType': 2,
            'subtype': subtype, 'slot': slot, 'modelIndex': index,
            'slotReservations': dict(SLOTS), 'colours': colours,
            'placeholders': sorted(placeholders), 'variants': variants,
            'resources': sorted(all_resources), 'clientValidated': False}


def private_override(table, allocation):
    """Change only ModelType and the necessary appearance range tokens.

    Preserve every other byte, including whitespace, comments and other rows.
    The reported diff is checked independently against the parsed original.
    """
    key, row = sling_row(table)
    values = [value for v in allocation['variants'] for value in v['utiParts'].values()]
    require(values and all(type(v) is int and 11 <= v <= 255 for v in values),
            'Validated encoded assembly parts required')
    edits = {'ModelType': '2'}
    if min(values) < int(row['MinRange']): edits['MinRange'] = str(min(values))
    if max(values) > int(row['MaxRange']): edits['MaxRange'] = str(max(values))
    edits = {name: value for name, value in edits.items() if row[name] != value}
    lines = table.splitlines(keepends=True)
    meaningful = [i for i, line in enumerate(lines)
                  if line.strip() and not line.lstrip().startswith(b'//')]
    header_index = 2 if lines[meaningful[1]].lstrip().upper().startswith(b'DEFAULT:') else 1
    columns = lines[meaningful[header_index]].split()
    target = [i for i in meaningful[header_index+1:] if lines[i].split()[0] == key.encode()]
    require(len(target) == 1, 'Unique Sling row required')
    line_index = target[0]
    spans = list(re.finditer(rb'\S+', lines[line_index]))
    changes = []
    for name, value in edits.items():
        token = spans[columns.index(name.encode()) + 1]
        changes.append((token.start(), token.end(), value.encode()))
    line = lines[line_index]
    for start, end, value in sorted(changes, reverse=True): line = line[:start]+value+line[end:]
    lines[line_index] = line
    result = b''.join(lines)
    before, after = twoda(table.decode('utf-8-sig')), twoda(result.decode('utf-8-sig'))
    expected = {k: dict(v) for k, v in before.items()}
    expected[key].update(edits)
    require(after == expected, 'Private override changed unrelated fields')
    return result, {'resource': 'baseitems.2da', 'intentionalOverride': True, 'baseItem': int(key),
                    'originalSha256': hashlib.sha256(table).hexdigest(),
                    'overrideSha256': hashlib.sha256(result).hexdigest(),
                    'changes': {k: {'before': row[k], 'after': v} for k, v in edits.items()},
                    'unrelatedBytesPreserved': True}


def validate_assembly(allocation, variant, counts):
    """Validate exact declared assembly and caps, including active placeholders."""
    require(variant in allocation['variants'], 'Undeclared Color/assembly')
    slot = SLOTS[allocation['subtype']]
    for p in PART_FIELDS:
        index = allocation['modelIndex'] if p == slot else 1
        expected = part_name(p, index, variant['colour'])
        require(variant['models'][p] == expected and variant['icons'][p] == 'i'+expected,
                'Mixed or malformed firearm assembly')
        require(variant['utiParts'][PART_FIELDS[p]] == index*10+variant['colour'], 'UTI part mismatch')
    require(set(counts) == set(PART_FIELDS), 'All active parts must be counted')
    for p, values in counts.items():
        require(set(values) == {'visible', 'shadow'}, 'Visible and shadow counts required')
        integer(values['visible'], 4, 10000, 'visible triangles')
        integer(values['shadow'], 0, 500, 'shadow triangles')
        if p != slot:
            require(values == {'visible': 4, 'shadow': 0}, 'Placeholder must be four triangles with no shadow')
    require(sum(x['visible'] for x in counts.values()) <= 10000, 'Complete firearm visible budget exceeded')
    require(sum(x['shadow'] for x in counts.values()) <= 500, 'Complete firearm shadow budget exceeded')
    return True
