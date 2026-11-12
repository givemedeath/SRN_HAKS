"""A brief says what an outfit is made of before its image is made, and the bake is sorted by it."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from . import brief, texture

SITEGUARD = Path(__file__).with_name('briefs') / 'corpsec-siteguard-male.json'
GREY, TAN, BLUE, SAGE = [128, 128, 128], [196, 160, 110], [150, 180, 220], [150, 190, 150]


def document(*materials):
    rows = materials or (('fabric', 'cloth', GREY), ('gear', 'leather', TAN), ('plates', 'metal', BLUE))
    return {'schemaVersion': 1, 'kind': brief.KIND, 'model': 'test-outfit', 'pads': ['l', 'r'], 'construction': max(brief.CONSTRUCTIONS),
            'materials': [{'name': name, 'kind': kind, 'colour': colour, 'look': name.upper() + ' look', 'wears': f'the {name} things.'}
                          for name, kind, colour in rows],
            'prompt': 'An outfit.\n\n' + brief.MARK + '\n\n' + brief.BUILT + '\n\nPlain white background.'}


def shown(*colours):
    return {'colours': np.array(colours, float) / 255}


class BriefTests(unittest.TestCase):
    def test_a_brief_lists_its_materials_with_their_kinds(self):
        given = document()
        self.assertIs(brief.validate(given), given)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'brief.json'
            path.write_text(json.dumps(given), encoding='utf-8')
            self.assertEqual(brief.load(path), given)
        changes = (lambda d: d.update(kind='something else'), lambda d: d.update(schemaVersion=2), lambda d: d.pop('materials'),
                   lambda d: d.update(model=' '), lambda d: d.update(extra=1), lambda d: d.update(materials=[]),
                   lambda d: d.update(prompt='no place for the colours'), lambda d: d.update(prompt=brief.MARK * 2),
                   lambda d: d.update(pads=['l', 'x']), lambda d: d.update(pads=['l', 'l']), lambda d: d.update(pads='lr'),
                   lambda d: d['materials'][0].update(kind='silk'), lambda d: d['materials'][0].pop('kind'),
                   lambda d: d['materials'][0].update(colour=[128, 128]), lambda d: d['materials'][0].update(colour=[128, 128, 256]),
                   lambda d: d['materials'][0].update(colour=[0.5, 0.5, 0.5]), lambda d: d['materials'][0].update(shown='grey'),
                   lambda d: d['materials'][0].update(look=''), lambda d: d['materials'][0].update(wears=''),
                   lambda d: d['materials'][0].update(note='x'), lambda d: d['materials'][1].update(name='fabric'))
        for change in changes:
            broken = copy.deepcopy(given)
            change(broken)
            with self.assertRaises(ValueError):
                brief.validate(broken)
        with self.assertRaises(ValueError):
            brief.validate([given])

    def test_a_kind_has_two_channels_and_so_at_most_two_materials(self):
        two = document(('shirt', 'cloth', GREY), ('trousers', 'cloth', BLUE), ('gear', 'leather', TAN))
        self.assertEqual(texture.channels([material['kind'] for material in brief.validate(two)['materials']]),
                         [('cloth1', 'cloth1'), ('cloth2', 'cloth2'), ('leather1', 'leather2')])
        with self.assertRaises(ValueError):
            brief.validate(document(('a', 'cloth', GREY), ('b', 'cloth', BLUE), ('c', 'cloth', TAN)))
        with self.assertRaises(ValueError):  # seven materials: the game has six channels
            brief.validate(document(*[(str(k), texture.KINDS[k % 3], [30 * k, 200 - 20 * k, 90]) for k in range(7)]))

    def test_the_image_prompt_is_written_from_the_materials(self):
        given = document()
        text = brief.prompt(given)
        self.assertEqual(text, 'An outfit.\n\nThree clearly different colours, each one flat and matte:\n1. FABRIC look: the fabric things.\n'
                               '2. GEAR look: the gear things.\n3. PLATES look: the plates things.\n\n'
                               + brief.CONSTRUCTIONS[given['construction']] + '\n\nPlain white background.')
        self.assertNotIn(brief.MARK, text)
        self.assertNotIn(brief.BUILT, text)
        self.assertTrue(brief.colours(document(('fabric', 'cloth', GREY))).startswith('One colour, flat and matte:\n1. FABRIC look'))
        self.assertTrue(brief.colours(document(*[(str(k), texture.KINDS[k % 3], GREY) for k in range(6)])).startswith('Six clearly'))
        with self.assertRaises(ValueError):  # a brief that does not hold up is not prompted from
            brief.prompt({**given, 'materials': []})

    def test_a_brief_names_the_construction_paragraph_its_prompt_holds(self):
        given = document()
        plain = {key: value for key, value in given.items() if key != 'construction'}  # as briefs were before the rules
        plain['prompt'] = plain['prompt'].replace(brief.BUILT + '\n\n', '')
        self.assertEqual(brief.composed(brief.validate(plain)), 'An outfit.\n\n' + brief.colours(plain) + '\n\nPlain white background.')
        for wrong in ({**given, 'construction': 0}, {**given, 'construction': True}, {**given, 'construction': '1'},
                      {**given, 'prompt': plain['prompt']}, {**plain, 'prompt': given['prompt']},  # the paragraph named and not placed, placed and not named
                      {**given, 'prompt': given['prompt'] + brief.BUILT}):
            with self.assertRaises(ValueError):
                brief.validate(wrong)
        text = brief.CONSTRUCTIONS[1]
        for said in ('one solid, simple shape', 'at most one guard', 'below the shoulder', 'round the middle', 'ends well short of the armpits'):
            self.assertIn(said, text)
        # a sealed folder's prompt is written from this paragraph, so it is never edited: a change is a new version
        self.assertEqual(hashlib.sha256(text.encode('utf-8')).hexdigest(), 'cec94d401f7e9ec5cde8db9d626737b5453282f4959cc7b0f0d6c10785a92990')

    def test_materials_drawn_too_alike_are_not_prompted_for(self):
        # the first outfit's cloth and plates: a neutral grey and a pale blue-grey
        alike = document(('fabric', 'cloth', GREY), ('gear', 'leather', TAN), ('plates', 'metal', [170, 180, 190]))
        with self.assertRaises(ValueError) as refused:
            brief.prompt(alike)
        self.assertIn('fabric and plates', str(refused.exception))
        brief.validate(alike)  # it still describes an outfit that exists
        brief.prompt(document(('fabric', 'cloth', GREY), ('gear', 'leather', TAN), ('plates', 'metal', BLUE), ('trim', 'metal', SAGE)))

    def test_the_outfits_materials_are_matched_to_the_briefs(self):
        given = document()
        names = lambda found: [material['name'] for material in brief.worn(given, found)]
        self.assertEqual(names(shown(TAN, BLUE, GREY)), ['gear', 'plates', 'fabric'])
        # every material a little warmer and darker than asked for: still each its own
        cast = lambda colour: [int(colour[0] * 0.85 + 6), int(colour[1] * 0.82), int(colour[2] * 0.7)]
        self.assertEqual(names(shown(cast(GREY), cast(BLUE), cast(TAN))), ['fabric', 'plates', 'gear'])
        self.assertEqual([material['kind'] for material in brief.worn(given, shown(BLUE, TAN, GREY))], ['metal', 'leather', 'cloth'])
        with self.assertRaises(ValueError):  # the outfit shows two materials, the brief lists three
            brief.worn(given, shown(TAN, GREY))
        # two materials the outfit shows half way between two of the brief's: which is which cannot be told
        between = [(a + b) // 2 for a, b in zip(GREY, BLUE)]
        with self.assertRaises(ValueError) as refused:
            brief.worn(given, shown(between, between, TAN))
        self.assertIn('shown', str(refused.exception))
        # recorded as shown, they are matched by that
        drifted = copy.deepcopy(given)
        drifted['materials'][0]['shown'], drifted['materials'][2]['shown'] = [100, 110, 100], [160, 150, 170]
        self.assertEqual([material['name'] for material in brief.worn(drifted, shown([158, 149, 168], TAN, [102, 111, 99]))], ['plates', 'gear', 'fabric'])
        self.assertEqual(brief.worn(document(('fabric', 'cloth', GREY)), shown(TAN))[0]['name'], 'fabric')  # one material is that one

    def test_the_first_outfits_brief_holds_and_sorts_its_materials(self):
        given = brief.load(SITEGUARD)
        self.assertEqual([(material['name'], material['kind']) for material in given['materials']],
                         [('fabric', 'cloth'), ('gear', 'leather'), ('plates', 'metal')])
        self.assertEqual(given['pads'], ['l', 'r'])
        # as its bake found them: fabric, gear, plates, and in another order
        found = shown([95, 89, 77], [135, 102, 65], [138, 140, 143])
        self.assertEqual([material['kind'] for material in brief.worn(given, found)], ['cloth', 'leather', 'metal'])
        self.assertEqual([material['name'] for material in brief.worn(given, shown([140, 143, 145], [95, 89, 77], [136, 103, 66]))],
                         ['plates', 'fabric', 'gear'])
        # its cloth and plates were asked for too alike: the same colours are not asked for again
        with self.assertRaises(ValueError):
            brief.prompt(given)
        self.assertIn('MEDIUM NEUTRAL GREY cloth', brief.colours(given))

    def test_the_first_outfits_second_brief_asks_for_colours_that_can_be_told_apart(self):
        first, second = brief.load(SITEGUARD), brief.load(SITEGUARD.with_name('corpsec-siteguard-male-2.json'))
        self.assertEqual(second['model'], first['model'])
        self.assertEqual([(material['name'], material['kind']) for material in second['materials']],
                         [(material['name'], material['kind']) for material in first['materials']])
        self.assertEqual(second['pads'], first['pads'])
        self.assertIn('BRIGHT LIGHT SKY BLUE hard plastic', brief.prompt(second))  # written: no two materials are drawn too alike


if __name__ == '__main__':
    unittest.main()
