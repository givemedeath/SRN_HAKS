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
generated outfit shows instead, recorded once it is known to have drifted. `suggested`, optional, is the colour
the concept wears the material in, 0-255: the reference image is drawn light and flat so that its materials can
be told apart, the game tints them, and this is the colour the outfit's design means (a dark base and one
accent to an outfit, as the concept sheets have it; user decision 2026-11-15). A bake records it with the
material's channels, and the registry may hand it on (`registry`, a part's `colours`). `"wear": 0.5`, optional,
0 to 1, is how worn the outfit is drawn: its tint shades are mottled, lighter on its raised edges and darker in
its creases by that much of what `texture.WEAR` gives its materials (`bake.tints`). The reference image stays
clean; without the key, or at 0, nothing is worn in (user decision 2026-11-15: a bit of wear, as the concept
sheets show it). `pads` names the sides an outfit
drawn before construction version 2 has a shoulder pad on (`repose.onto_body`, `padded`). `prompt` is the image prompt with `{materials}`
where its colour paragraph goes.

`"construction": 3` and `{construction}` in the prompt add the paragraph that says how an outfit is built so
that it can be cut into parts (`CONSTRUCTIONS`). What the first worn outfit took longest to put right was
drawn into its reference image: frames and piping of metal a face wide, a guard in two plates across an
elbow, a shoulder guard over the sleeve's seam, straps along the joints. Version 1 put a shoulder guard on the
upper arm below the shoulder; version 2 draws no shoulder pads at all, which are made apart from the outfit
(docs/armorkit/plan.md), and a brief of it or a later version lists no `pads`. Version 3 says the same rules of
what the outfit has and names no piece or place to forbid it: an image model draws what its prompt names, and
version 2's list of where straps may go and of guards it forbade came back as straps and guards there. A
brief's own words follow the same rule. No new reference folder is sealed without the current paragraph
(`seal`); a folder sealed before keeps the prompt it was sealed with.

`"tint": "leather"` on a material tints it on another kind's colour channels (user, 2026-11-24: the channels
a part has no use for may be used). `kind` stays what the material is: how it is cut, what counts as a plate
and how it wears. An outfit of three cloths has its third, the flaps of its pockets, coloured on a leather
channel. At most two materials the baked outfit shows are tinted on one kind's channels; a material marked
`unworn` takes none, and names no `channel` or `tint`.

The metal channels are kept for metal and for what is otherwise shiny (user, 2026-11-25): the game draws them
with a metal's sheen, and a T-shirt tinted on one came out glossy in the client. A material of another kind
tinted on metal says so itself, `"shiny": true` beside `"tint": "metal"` (patent leather, wet-look vinyl), and
is refused without.

`"channel": 1` or `2` on an outfit's material names the channel of that kind it is tinted on, wherever it is
worn (`channels`). The reference image's colours then say what is coloured on which channel, and briefs drawn
to one convention give parts that are coloured alike when worn together (user, 2026-11-24). The materials
tinted on a kind all name one, each its own, or none does; without, the channels are told as before
(`texture.channels`).

Where every material of an outfit names its channel, two may name the same one (user, 2026-11-25, a trial:
reference images coloured by material type and accent, not by garment). The channel then says what a material
is, a kind's main (1) or its accent (2), and the colour it is drawn in only tells it from the others: a
shirt and trousers are both the main cloth, drawn in two colours so that the cut can tell top from bottom.

`"slots": ["shin", "foot"]` on an outfit's material lists the slots it is worn on, of `SLOTS`; without, it may
be on any. A part is tinted in the materials worn on its slot and no other (`bake.tints`,
`texture.tint_maps`' `among`): colour alone gave most of a boot to the pocket flaps, whose tone in shadow is
a dark leather's (Street Casual, 2026-11-25).

`bare` names the slots the outfit leaves to the body, and `skin` those where it covers the body only in part
and the body's skin shows beside it (`bake.bake`): `"bare": ["forearm"], "skin": ["bicep"]` for a shirt with
short sleeves and gloves. They are a fact about the outfit as it is drawn, so they are in the brief the
image is made from, and only what the bake can build is taken (`BARE`, `SKIN`). A slot left to the body has no
model: an item names the body's own part there, part 1 (user decision 2026-11-24). Any slot an outfit fills
may be left (`BARE`; user, 2026-11-24): `"bare": ["hand"]` is an outfit worn with bare hands,
`["shin", "foot"]` one that ends at the knee. A chest left bare takes the upper arms with it and a pelvis the
thighs (`WITH`). The image is still drawn as a whole figure, with a plain piece where a slot is left, in one
of the brief's materials: the fit places the outfit by its neck, crotch, feet and palms
(`repose.outfit_joints`), and an arm that ends at a hem with nothing beyond it is refused there. The bake cuts
that piece off on the joint's plane and closes the outfit's end round the body's own part.

`"accessory": "belt"` (or `shoulder`, `neck`) makes it the brief of one accessory piece, generated by itself and
worn whole on that slot (`accessory.py`): it is not cut at any joint, so it carries no construction paragraph,
no `pads`, `bare` or `skin`, and its reference folder is sealed without one. Its materials may each name the
channel of their kind they are tinted on (`"channel": 1` or `2`, 1 without it), so that a belt's webbing takes the
colour of the vest it is worn under and its holster that of the outfit's leg guards: an outfit's garments are
told apart by where they are worn, and a piece worn in one place cannot be.
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
_RULES = (
    'Construction, how this outfit is built. It will be cut into separate parts at the shoulders, elbows, wrists, waist, hips, knees and ankles:',
    '1. Every hard plate or guard is one solid, simple shape at least as wide as a hand, in its own colour all over. '
    'Nothing thin is drawn in a plate\'s colour: no frames, outlines, piping, trim lines or small tabs on the cloth.',
    '2. An elbow or a knee has at most one guard: a single one-piece shell centred on the joint. '
    'No guard is two plates with a strap or a gap between them.',
    '3. A shoulder guard sits on the outside of the upper arm, below the shoulder. '
    'The top of the shoulder and the seam where the sleeve joins the body are plain cloth with nothing lying over them.',
    '4. Every strap and band goes round the middle of an upper arm, a forearm, a thigh or a shin. '
    'No strap runs along or across a shoulder, an elbow, a wrist, the waist, a hip, a knee or an ankle.',
    '5. Nothing worn on the torso touches the arms: a vest or a carrier is narrow at the sides and ends well short of the armpits.')
# version 2: no shoulder pads, which are made apart from the outfit (user decision 2026-11-12)
UNPADDED = ('3. Nothing is worn on the shoulders: no shoulder pad, pauldron or guard over the shoulder or the top of the upper arm; '
            'those are made separately. The top of the shoulder and the seam where the sleeve joins the body are plain, with nothing lying over them.')
# version 3: the same rules said of what the outfit has. Two Facility Security images drawn to version 2 put
# guards on the forearms and straps round the thighs, the pieces and places versions 1 and 2 name to forbid
# them; an image model draws what a prompt names (2026-11-13)
NAMED_ONLY = (
    'Construction, how this outfit is built. It will be cut into separate parts at every joint:',
    '1. Every hard plate or guard this outfit has is one solid, simple shape at least as wide as a hand, in its own colour all over. '
    'The plate colour is used only for these solid shapes, each set on plain cloth.',
    '2. Each guard this outfit has is a single one-piece shell.',
    '3. The top of each shoulder and the seam where each sleeve joins the body are plain, smooth cloth.',
    '4. Each strap this outfit has goes round the middle of a limb, halfway between two joints.',
    '5. The garments on the torso are narrow at the sides and end well short of the armpits, clear of the sleeves.')
CONSTRUCTIONS = {1: '\n'.join(_RULES), 2: '\n'.join(_RULES[:3] + (UNPADDED,) + _RULES[4:]), 3: '\n'.join(NAMED_ONLY)}
PADLESS = 2  # the first version drawn without shoulder pads: a brief of it or a later one lists no `pads`
COUNTS = ('One', 'Two', 'Three', 'Four', 'Five', 'Six')
APART = 30.0  # the least two materials' colours may differ by in a prompt, in `texture.tone`'s space. The first outfit's
# cloth and plates were asked for 10 apart and its cloth came out 21 from what was asked: they could be told only by guessing
MARGIN = 5.0  # the best way of matching the outfit's materials to the brief's beats the next by this much, or it is refused
KEYS = {'schemaVersion', 'kind', 'model', 'pads', 'materials', 'prompt', 'construction', 'bare', 'skin', 'wear', 'accessory'}
ACCESSORIES = ('belt', 'shoulder', 'neck')  # the slots a piece generated by itself is worn whole on
BARE = ('chest', 'pelvis', 'bicep', 'forearm', 'hand', 'thigh', 'shin', 'foot')  # the slots an outfit may leave to the body: any it fills
SKIN = ('bicep',)  # and those it may share with the body's skin
SLOTS = ('chest', 'pelvis', 'shoulder', 'bicep', 'forearm', 'hand', 'thigh', 'shin', 'foot')  # the slots a material may be worn on: `bake.SLOTS`
# A limb's end at the torso is grown to lie inside the outfit's own chest or pelvis. With the torso slot left to the body and the limb
# kept, that end stood 2.2 to 2.8 cm out of the body's skin (Facility Security split again, 2026-11-24): the limb goes with it
WITH = {'chest': 'bicep', 'pelvis': 'thigh'}
MATERIAL_KEYS = {'name', 'kind', 'colour', 'look', 'wears', 'shown', 'suggested', 'channel', 'tint', 'unworn', 'shiny', 'slots'}
OPTIONAL = {'shown', 'suggested', 'channel', 'tint', 'unworn', 'shiny', 'slots'}  # what a material may hold beside what it must
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
    piece = document.get('accessory')
    # the key alone makes a brief an accessory's (`seal` asks no construction of one): it names a slot or is not there
    require('accessory' not in document or piece in ACCESSORIES, f'An accessory is worn on one of {list(ACCESSORIES)}')
    require(piece is None or not ({'construction', 'pads', 'bare', 'skin'} & set(document)),
            'An accessory is worn whole on its slot: its brief has no construction, pads, bare or skin')
    for key, slots in (('bare', BARE), ('skin', SKIN)):
        listed = document.get(key, [])
        require(isinstance(listed, list) and all(isinstance(slot, str) for slot in listed) and set(listed) <= set(slots)
                and len(set(listed)) == len(listed), f'{key} lists slots, each once, of {list(slots)}: what the bake can build')
    bare = set(document.get('bare', []))
    require(not bare & set(document.get('skin', [])), "A slot is left to the body or shared with its skin, not both")
    for torso, limb in WITH.items():
        require(torso not in bare or limb in bare, f'An outfit that leaves the {torso} to the body leaves the {limb} too: its end is made to lie inside the {torso}')
    wear = document.get('wear', 0)
    require(isinstance(wear, (int, float)) and not isinstance(wear, bool) and 0 <= wear <= 1, 'wear is a number from 0, clean, to 1')
    pads = document.get('pads', [])
    require(isinstance(pads, list) and set(pads) <= {'l', 'r'} and len(set(pads)) == len(pads), 'Pads are on the l or r side')
    require(not pads or version is None or version < PADLESS,
            f'An outfit drawn to construction {PADLESS} or later has no shoulder pads: they are made apart from it')
    materials = document['materials']
    require(isinstance(materials, list) and 1 <= len(materials) <= len(COUNTS), 'A brief lists one to six materials')
    colour = lambda value: (isinstance(value, list) and len(value) == 3
                            and all(isinstance(part, int) and not isinstance(part, bool) and 0 <= part <= 255 for part in value))
    for material in materials:
        require(isinstance(material, dict) and set(material) <= MATERIAL_KEYS and MATERIAL_KEYS - OPTIONAL <= set(material),
                f'A material holds {sorted(MATERIAL_KEYS - OPTIONAL)}, and may hold {" and ".join(sorted(OPTIONAL))}')
        require(all(text(material[key]) for key in ('name', 'look', 'wears')), 'A material has a name, a look and what wears it')
        require(material['kind'] in texture.KINDS, f'{material["name"]}: a material is one of {texture.KINDS}')
        require('channel' not in material or (type(material['channel']) is int and material['channel'] in (1, 2)),
                f'{material["name"]}: a material may name channel 1 or 2 of the kind it is tinted on')
        require(colour(material['colour']) and all(key not in material or colour(material[key]) for key in ('shown', 'suggested')),
                f'{material["name"]}: a colour is three whole numbers, 0-255')
        require(material.get('unworn', True) is True, f'{material["name"]}: unworn is true or left out')
        require('tint' not in material or (material['tint'] in texture.KINDS and material['tint'] != material['kind']),
                f'{material["name"]}: tint names another kind of {texture.KINDS}, whose colour channels the material is tinted on')
        require(material.get('shiny', True) is True, f'{material["name"]}: shiny is true or left out')
        require(('shiny' in material) == (material.get('tint') == 'metal'),
                f'{material["name"]}: the metal channels are for metal and for what is shiny. A material of another kind '
                'tinted on them is marked "shiny": true, and nothing else is')
        require('unworn' not in material or not {'channel', 'tint', 'slots'} & set(material),
                f'{material["name"]}: an unworn material is on no baked part, and names no channel, tint or slots')
        slots = material.get('slots')
        require(slots is None or (piece is None and isinstance(slots, list) and slots and len(set(slots)) == len(slots) and set(slots) <= set(SLOTS)),
                f'{material["name"]}: slots lists the slots of {SLOTS} a material of an outfit is worn on, each once')
    names = [material['name'] for material in materials]
    require(len(set(names)) == len(names), 'Material names are unique')
    materials = [material for material in materials if not material.get('unworn')]  # what takes a channel
    kinds = [tinted(material) for material in materials]
    shared = piece is None and all('channel' in material for material in materials)  # drawn by type and accent: garments may share a channel
    require(shared or all(kinds.count(kind) <= 2 for kind in kinds), 'The game tints two channels of a kind: at most two materials are tinted on one, '
            'unless every material names its channel')
    taken = [(tinted(material), material.get('channel', 1)) for material in materials]
    require(piece is None or len(set(taken)) == len(taken), 'Two materials of an accessory are not tinted on one channel')
    if piece is None:  # an outfit's materials name their channels kind by kind: all tinted on a kind, each its own, or none
        for kind in set(kinds):
            named = [material['channel'] for material in materials if tinted(material) == kind and 'channel' in material]
            require(not named or (len(named) == kinds.count(kind) and (shared or len(set(named)) == len(named))),
                    f'The materials tinted on {kind} each name a channel of their own, or none of them names one')
    return document


def on(material, slot):
    """Whether an outfit's material is worn on `slot`: on every slot, or on those its `slots` lists."""
    return slot in material.get('slots', SLOTS)


def tinted(material):
    """The kind whose colour channels a material is tinted on: its own, or the one its `tint` names."""
    return material.get('tint', material['kind'])


def channels(materials):
    """The two colour channels of each of an outfit's `materials`, [(first, second)], as `texture.channels` gives
    them from the kinds they are tinted on, but for a material that names its `channel`: that one has it wherever
    it is worn. Left to `texture.channels`, the commoner of two materials takes a kind's first channel and a
    single one is split between torso and legs, which differs from outfit to outfit; a named channel is the
    same on every outfit drawn to one convention, so their parts can be worn together and coloured as one."""
    if materials and all('channel' in material for material in materials):  # every one named: two garments may be tinted on one
        return [(tinted(material) + str(material['channel']),) * 2 for material in materials]
    found = texture.channels([tinted(material) for material in materials])
    return [(tinted(material) + str(material['channel']),) * 2 if 'channel' in material else pair for material, pair in zip(materials, found)]


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
    seals nothing. Neither does an outfit's without the current construction paragraph: a new image is drawn to
    the rules the outfits before it taught (an accessory is not cut, and has none). Images made from the prompt are registered in the folder
    (`register`); only those are taken further (`admit`)."""
    text = prompt(brief)
    require('accessory' in brief or brief.get('construction') == max(CONSTRUCTIONS),
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


def baked(brief):
    """The brief's materials a baked outfit shows: all but those it marks `unworn`. An unworn material is drawn
    in the reference and generated with the outfit, and cut off with the slots the brief leaves to the body:
    the gloves beyond a short sleeve, which hold the sleeve short in the image and show the fit where the arm
    ends (Street Casual, 2026-11-25). The whole mesh shows it; the parts cut from it do not."""
    return [material for material in brief['materials'] if not material.get('unworn')]


def worn(brief, found, cut=False):
    """The brief's material for each material the outfit's colours show (`texture.materials`), in that order.
    With `cut`, the colours are those of the baked parts, which show no material the brief marks `unworn`
    (`baked`).

    Every way of pairing the two lists is tried, and the one with the least colour difference in all is taken
    (in `texture.tone`'s space, against a material's `shown` colour where the brief has one). Taken together,
    a drift all materials share (a warm cast) does not turn one into another. If the next best pairing is
    within `MARGIN`, the outfit cannot be told which way round and is refused: its colours as shown belong in
    the brief then. A different number of materials than the brief lists is refused too."""
    materials = validate(brief)['materials']
    materials = baked(brief) if cut else materials
    seen = np.asarray(found['colours'], float).reshape(-1, 3)
    require(len(seen) == len(materials), f'The outfit shows {len(seen)} materials and its brief lists {len(materials)}')
    asked = texture.tone(np.array([material.get('shown', material['colour']) for material in materials], float) / 255)
    apart = np.linalg.norm(texture.tone(seen)[:, None] - asked[None], axis=2)  # [shown, listed]
    ways = sorted((float(sum(apart[k, way[k]] for k in range(len(way)))), way) for way in permutations(range(len(materials))))
    require(len(ways) == 1 or ways[1][0] - ways[0][0] >= MARGIN,
            'The outfit\'s colours do not tell which material is which: record them as `shown` in the brief. They are '
            + ', '.join(str(np.round(colour * 255).astype(int).tolist()) for colour in seen))
    return [materials[index] for index in ways[0][1]]
