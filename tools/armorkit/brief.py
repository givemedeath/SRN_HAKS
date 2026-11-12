"""The brief of one generated outfit: the materials it is made of, and the prompt its reference image is drawn from.

The game tints an outfit in six channels, two each of cloth, leather and metal (`texture.channels`). Which of an
outfit's materials is of which kind cannot be read off its colours. The first bake guessed (the lightest is
metal, the most coloured leather), which held for one outfit and fails on a dark plate or a pale cloth. The brief
says it, before any image is made: every material has a name, a kind, the flat colour it is drawn in and what
is made of it. The colour paragraph of the image prompt is written from that list (`prompt`), so no image is
asked for without one, and after the bake the materials the outfit's colours show are matched to the brief's
(`worn`).

A reference folder is sealed with its brief (`seal`): the prompt is written into it together with the brief it
came from, and every image made from that prompt is registered there (`register`). Whatever takes an image
further (a geometry or an appearance job) asks first whether it comes from a sealed folder (`admit`). An
outfit whose image was made before briefs existed is taken in as it is (`adopt`).

A brief is a JSON document:

    {"schemaVersion": 1, "kind": "srn-armorkit-brief", "model": "corpsec-siteguard-male", "pads": ["l", "r"],
     "materials": [{"name": "fabric", "kind": "cloth", "colour": [128, 128, 128],
                    "look": "MEDIUM NEUTRAL GREY cloth", "wears": "the shirt and the trousers."}],
     "prompt": "... {materials} ..."}

`colour` is the flat colour the prompt's words (`look`) ask for, 0-255. `shown`, optional, is the colour the
generated outfit shows instead, recorded once it is known to have drifted. `pads` names the sides the outfit is
designed with a shoulder pad on (`repose.onto_body`, `padded`). `prompt` is the image prompt with `{materials}`
where its colour paragraph goes.

`"construction": 1` and `{construction}` in the prompt add the paragraph that says how an outfit is built so
that it can be cut into parts (`CONSTRUCTIONS`). What the first worn outfit took longest to put right was
drawn into its reference image: frames and piping of metal a face wide, a guard in two plates across an
elbow, a shoulder guard over the sleeve's seam, straps along the joints. No new reference folder is sealed
without the current paragraph (`seal`); a folder sealed before keeps the prompt it was sealed with.

`bare` names the slots the outfit leaves to the body, and `skin` those where it covers the body only in part
and the body's skin shows beside it (`bake.bake`): `"bare": ["forearm"], "skin": ["bicep"]` for a shirt with
short sleeves and gloves. They are a fact about the outfit as it is drawn, so they are in the brief the
image is made from, and only what the bake can build is taken (`BARE`, `SKIN`).
"""
import hashlib
import json
from itertools import permutations
from pathlib import Path

import numpy as np

from . import texture
from .registry import require

KIND = 'srn-armorkit-brief'
MARK = '{materials}'
BUILT = '{construction}'
# The paragraph of an image prompt that says how an outfit is built, by version. A sealed folder's prompt is
# written from the version its brief names, so a paragraph is never edited: a change is a new version.
CONSTRUCTIONS = {1: '\n'.join((
    'Construction, how this outfit is built. It will be cut into separate parts at the shoulders, elbows, wrists, waist, hips, knees and ankles:',
    '1. Every hard plate or guard is one solid, simple shape at least as wide as a hand, in its own colour all over. '
    'Nothing thin is drawn in a plate\'s colour: no frames, outlines, piping, trim lines or small tabs on the cloth.',
    '2. An elbow or a knee has at most one guard: a single one-piece shell centred on the joint. '
    'No guard is two plates with a strap or a gap between them.',
    '3. A shoulder guard sits on the outside of the upper arm, below the shoulder. '
    'The top of the shoulder and the seam where the sleeve joins the body are plain cloth with nothing lying over them.',
    '4. Every strap and band goes round the middle of an upper arm, a forearm, a thigh or a shin. '
    'No strap runs along or across a shoulder, an elbow, a wrist, the waist, a hip, a knee or an ankle.',
    '5. Nothing worn on the torso touches the arms: a vest or a carrier is narrow at the sides and ends well short of the armpits.'))}
COUNTS = ('One', 'Two', 'Three', 'Four', 'Five', 'Six')
APART = 30.0  # the least two materials' colours may differ by in a prompt, in `texture.tone`'s space. The first outfit's
# cloth and plates were asked for 10 apart and its cloth came out 21 from what was asked: they could be told only by guessing
MARGIN = 5.0  # the best way of matching the outfit's materials to the brief's beats the next by this much, or it is refused
KEYS = {'schemaVersion', 'kind', 'model', 'pads', 'materials', 'prompt', 'construction', 'bare', 'skin'}
BARE, SKIN = ('forearm',), ('bicep',)  # the slots an outfit may leave to the body, and those it may share with the body's skin
MATERIAL_KEYS = {'name', 'kind', 'colour', 'look', 'wears', 'shown'}
SEAL, SEAL_KIND, PROMPT = 'brief-seal.json', 'srn-armorkit-brief-seal', 'PROMPT.txt'


def validate(document):
    """The brief, checked: what it must hold for a prompt to be written from it and a bake to be sorted by it."""
    require(isinstance(document, dict) and document.get('schemaVersion') == 1 and document.get('kind') == KIND,
            f'A brief is a JSON object of kind {KIND}, schemaVersion 1')
    require(set(document) <= KEYS and {'model', 'materials', 'prompt'} <= set(document), f'A brief holds {sorted(KEYS)}')
    text = lambda value: isinstance(value, str) and bool(value.strip())
    require(text(document['model']), 'A brief names its model')
    require(text(document['prompt']) and document['prompt'].count(MARK) == 1,
            f'The prompt holds {MARK} once, where its colour paragraph goes')
    version = document.get('construction')
    require(version is None or (isinstance(version, int) and not isinstance(version, bool) and version in CONSTRUCTIONS),
            f'The construction paragraph is one of versions {sorted(CONSTRUCTIONS)}')
    require(document['prompt'].count(BUILT) == (0 if version is None else 1),
            f'The prompt holds {BUILT} once where the brief names a construction version, and not without one')
    for key, slots in (('bare', BARE), ('skin', SKIN)):
        listed = document.get(key, [])
        require(isinstance(listed, list) and all(isinstance(slot, str) for slot in listed) and set(listed) <= set(slots)
                and len(set(listed)) == len(listed), f'{key} lists slots, each once, of {list(slots)}: what the bake can build')
    pads = document.get('pads', [])
    require(isinstance(pads, list) and set(pads) <= {'l', 'r'} and len(set(pads)) == len(pads), 'Pads are on the l or r side')
    materials = document['materials']
    require(isinstance(materials, list) and 1 <= len(materials) <= len(COUNTS), 'A brief lists one to six materials')
    colour = lambda value: (isinstance(value, list) and len(value) == 3
                            and all(isinstance(part, int) and not isinstance(part, bool) and 0 <= part <= 255 for part in value))
    for material in materials:
        require(isinstance(material, dict) and set(material) <= MATERIAL_KEYS and MATERIAL_KEYS - {'shown'} <= set(material),
                f'A material holds {sorted(MATERIAL_KEYS - {"shown"})}, and may hold shown')
        require(all(text(material[key]) for key in ('name', 'look', 'wears')), 'A material has a name, a look and what wears it')
        require(material['kind'] in texture.KINDS, f'{material["name"]}: a material is one of {texture.KINDS}')
        require(colour(material['colour']) and ('shown' not in material or colour(material['shown'])),
                f'{material["name"]}: a colour is three whole numbers, 0-255')
    names, kinds = [material['name'] for material in materials], [material['kind'] for material in materials]
    require(len(set(names)) == len(names), 'Material names are unique')
    require(all(kinds.count(kind) <= 2 for kind in kinds), 'The game tints two channels of a kind: at most two materials of one')
    return document


def load(path):
    """The brief in a file, checked."""
    return validate(json.loads(Path(path).read_text(encoding='utf-8')))


def colours(brief):
    """The colour paragraph of the image prompt: every material, the look it is drawn in and what is made of it."""
    materials = brief['materials']
    head = 'One colour, flat and matte:' if len(materials) == 1 else f'{COUNTS[len(materials) - 1]} clearly different colours, each one flat and matte:'
    return '\n'.join([head] + [f'{number}. {material["look"]}: {material["wears"]}' for number, material in enumerate(materials, 1)])


def prompt(brief):
    """The image prompt of a brief, its colour paragraph written from the materials.

    Two materials drawn less than `APART` apart are refused: the generated outfit's colours drift from the
    prompt's, and materials that start close cannot be told apart afterwards, or are told apart the wrong way
    round."""
    brief = validate(brief)
    tones = texture.tone(np.array([material['colour'] for material in brief['materials']], float) / 255)
    for first in range(len(tones)):
        for second in range(first):
            gap = float(np.linalg.norm(tones[first] - tones[second]))
            require(gap >= APART, f'{brief["materials"][second]["name"]} and {brief["materials"][first]["name"]} are drawn too alike '
                                  f'({gap:.0f}, at least {APART:.0f} is needed): give them colours of different hues')
    return composed(brief)


def composed(brief):
    """The brief's prompt as written out, whatever its colours: what `prompt` returns once it has checked them."""
    text = brief['prompt'].replace(MARK, colours(brief))
    return text.replace(BUILT, CONSTRUCTIONS[brief['construction']]) if 'construction' in brief else text


def _seal(folder, brief, adopted):
    folder = Path(folder)
    images = {}
    if (folder / SEAL).is_file():  # sealed again with the same brief, its images stay registered
        before = json.loads((folder / SEAL).read_text(encoding='utf-8'))
        require(before.get('brief') == brief or not before.get('images'),
                f'{folder} holds images made from another brief: seal a new folder')
        images = before.get('images', {}) if before.get('brief') == brief else {}
    record = {'schemaVersion': 1, 'kind': SEAL_KIND, 'adopted': adopted, 'brief': brief, 'images': images}
    (folder / SEAL).write_text(json.dumps(record, indent=1, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')


def seal(brief, folder):
    """Seal a reference folder with its brief and return the image prompt, which is written there as PROMPT.txt.

    The prompt is the brief's (`prompt`), so a brief that does not hold, or one with materials drawn too alike,
    seals nothing. Neither does one without the current construction paragraph: a new image is drawn to
    the rules the outfits before it taught. Images made from the prompt are registered in the folder
    (`register`); only those are taken further (`admit`)."""
    text = prompt(brief)
    require(brief.get('construction') == max(CONSTRUCTIONS),
            f'A new reference image is drawn to the construction rules: give the brief "construction": {max(CONSTRUCTIONS)} and {BUILT} in its prompt')
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    _seal(folder, brief, False)
    (folder / PROMPT).write_text(text + '\n', encoding='utf-8', newline='\n')
    return text


def adopt(brief, folder):
    """Seal a reference folder whose image was made before its brief was written.

    The folder's PROMPT.txt must be the brief's prompt word for word, and every material must have its colour
    as the outfit shows it (`shown`): the image exists, so its colours are a fact to record and no longer a
    choice to check. Its materials may be closer than a new prompt's may."""
    brief, folder = validate(brief), Path(folder)
    require(all('shown' in material for material in brief['materials']), 'An outfit made before its brief has its colours as shown on record')
    require((folder / PROMPT).is_file() and (folder / PROMPT).read_text(encoding='utf-8').strip() == composed(brief).strip(),
            f'The prompt in {folder} is not the one this brief gives')
    _seal(folder, brief, True)


def sealed(folder):
    """(brief, prompt) of a sealed reference folder, checked: the prompt in it is still the one its brief gives."""
    folder = Path(folder)
    require((folder / SEAL).is_file(), f'{folder} is not sealed with a brief: write the brief of the outfit and seal the folder (armorkit brief BRIEF --seal FOLDER)')
    record = json.loads((folder / SEAL).read_text(encoding='utf-8'))
    require(isinstance(record, dict) and record.get('kind') == SEAL_KIND and record.get('schemaVersion') == 1
            and isinstance(record.get('images'), dict) and isinstance(record.get('adopted'), bool), f'{folder / SEAL} is not a brief seal')
    brief = validate(record['brief'])
    text = composed(brief) if record['adopted'] else prompt(brief)
    require((folder / PROMPT).is_file() and (folder / PROMPT).read_text(encoding='utf-8').strip() == text.strip(),
            f'The prompt in {folder} is not the one its brief gives')
    return brief, text


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def register(folder, *images):
    """Record images as made from a sealed folder's prompt, or from such an image (a clay, a calibrated copy)."""
    sealed(folder)
    path = Path(folder) / SEAL
    record = json.loads(path.read_text(encoding='utf-8'))
    for image in images:
        require(Path(image).is_file(), f'{image} is not a file')
        record['images'][digest(image)] = Path(image).name
    path.write_text(json.dumps(record, indent=1, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')


def admit(image, root):
    """(brief, folder) for an image that is to be taken further: the sealed folder under `root` it is registered in.

    An image no sealed folder lists is refused: nothing says what the outfit in it is made of. A geometry or
    appearance job asks this before it is posted."""
    require(Path(image).is_file(), f'{image} is not a file')
    mark = digest(image)
    for path in sorted(Path(root).rglob(SEAL)):
        record = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(record, dict) and mark in record.get('images', {}):
            return sealed(path.parent)[0], path.parent
    require(False, f'{image} does not come from a brief: seal its reference folder (armorkit brief BRIEF --seal FOLDER) and register the image there')


def worn(brief, found):
    """The brief's material for each material the outfit's colours show (`texture.materials`), in that order.

    Every way of pairing the two lists is tried, and the one with the least colour difference in all is taken
    (in `texture.tone`'s space, against a material's `shown` colour where the brief has one). Taken together,
    a drift all materials share (a warm cast) does not turn one into another. If the next best pairing is
    within `MARGIN`, the outfit cannot be told which way round and is refused: its colours as shown belong in
    the brief then. A different number of materials than the brief lists is refused too."""
    materials = validate(brief)['materials']
    seen = np.asarray(found['colours'], float).reshape(-1, 3)
    require(len(seen) == len(materials), f'The outfit shows {len(seen)} materials and its brief lists {len(materials)}')
    asked = texture.tone(np.array([material.get('shown', material['colour']) for material in materials], float) / 255)
    apart = np.linalg.norm(texture.tone(seen)[:, None] - asked[None], axis=2)  # [shown, listed]
    ways = sorted((float(sum(apart[k, way[k]] for k in range(len(way)))), way) for way in permutations(range(len(materials))))
    require(len(ways) == 1 or ways[1][0] - ways[0][0] >= MARGIN,
            'The outfit\'s colours do not tell which material is which: record them as `shown` in the brief. They are '
            + ', '.join(str(np.round(colour * 255).astype(int).tolist()) for colour in seen))
    return [materials[index] for index in ways[0][1]]
