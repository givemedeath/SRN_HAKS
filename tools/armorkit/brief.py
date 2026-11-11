"""The brief of one generated outfit: the materials it is made of, and the prompt its reference image is drawn from.

The game tints an outfit in six channels, two each of cloth, leather and metal (`texture.channels`). Which of an
outfit's materials is of which kind cannot be read off its colours. The first bake guessed (the lightest is
metal, the most coloured leather), which held for one outfit and fails on a dark plate or a pale cloth. The brief
says it, before any image is made: every material has a name, a kind, the flat colour it is drawn in and what
is made of it. The colour paragraph of the image prompt is written from that list (`prompt`), so no image is
asked for without one, and after the bake the materials the outfit's colours show are matched to the brief's
(`worn`).

A brief is a JSON document:

    {"schemaVersion": 1, "kind": "srn-armorkit-brief", "model": "corpsec-siteguard-male", "pads": ["l", "r"],
     "materials": [{"name": "fabric", "kind": "cloth", "colour": [128, 128, 128],
                    "look": "MEDIUM NEUTRAL GREY cloth", "wears": "the shirt and the trousers."}],
     "prompt": "... {materials} ..."}

`colour` is the flat colour the prompt's words (`look`) ask for, 0-255. `shown`, optional, is the colour the
generated outfit shows instead, recorded once it is known to have drifted. `pads` names the sides the outfit is
designed with a shoulder pad on (`repose.onto_body`, `padded`). `prompt` is the image prompt with `{materials}`
where its colour paragraph goes.
"""
import json
from itertools import permutations
from pathlib import Path

import numpy as np

from . import texture
from .registry import require

KIND = 'srn-armorkit-brief'
MARK = '{materials}'
COUNTS = ('One', 'Two', 'Three', 'Four', 'Five', 'Six')
APART = 30.0  # the least two materials' colours may differ by in a prompt, in `texture.tone`'s space. The first outfit's
# cloth and plates were asked for 10 apart and its cloth came out 21 from what was asked: they could be told only by guessing
MARGIN = 5.0  # the best way of matching the outfit's materials to the brief's beats the next by this much, or it is refused
KEYS = {'schemaVersion', 'kind', 'model', 'pads', 'materials', 'prompt'}
MATERIAL_KEYS = {'name', 'kind', 'colour', 'look', 'wears', 'shown'}


def validate(document):
    """The brief, checked: what it must hold for a prompt to be written from it and a bake to be sorted by it."""
    require(isinstance(document, dict) and document.get('schemaVersion') == 1 and document.get('kind') == KIND,
            f'A brief is a JSON object of kind {KIND}, schemaVersion 1')
    require(set(document) <= KEYS and {'model', 'materials', 'prompt'} <= set(document), f'A brief holds {sorted(KEYS)}')
    text = lambda value: isinstance(value, str) and bool(value.strip())
    require(text(document['model']), 'A brief names its model')
    require(text(document['prompt']) and document['prompt'].count(MARK) == 1,
            f'The prompt holds {MARK} once, where its colour paragraph goes')
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
    return brief['prompt'].replace(MARK, colours(brief))


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
