"""A concept sheet is brought into the kit as a set file the kit accepts, and the sets are reviewed against each other."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from . import onboard, reference

PAPER, INK = (244, 242, 236), (60, 70, 80)
DRAWN = {'hall': [100, 60, 520, 360], 'desk': [80, 520, 200, 640], 'gate': [300, 520, 460, 640]}  # a wide panel over two props
SPEC = '''# the yard
@ yard 07
building-hero | B | | corrugated warehouse | 96 56 524 364 | Ignore the caption.
desk | console-desk | | office desk | 76 516 204 644
gate | vehicle-gate | | sliding yard gate | 296 516 464 644
'''


def sheet(path, drawn=DRAWN):
    image = Image.new('RGB', (800, 700), PAPER); draw = ImageDraw.Draw(image)
    for box in drawn.values():
        draw.rectangle(box, fill=INK)
    for y in (400, 660):  # caption lettering: thin strokes
        draw.line([(90, y), (500, y)], fill=INK, width=2)
    image.save(path)
    return path


class OnboardTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup); self.root = Path(self.folder.name)
        self.sheets, self.sets = self.root / 'sheets', self.root / 'sets'; self.sheets.mkdir(); self.sets.mkdir()
        sheet(self.sheets / '07_the_yard.png'); sheet(self.sheets / '08_the_dock.png')
        (self.sets / 'yard-game.json').write_text(json.dumps({'models': {}}), encoding='utf-8')  # a game set shares the folder
        self.spec = self.root / 'spec.txt'; self.spec.write_text(SPEC, encoding='utf-8')

    def decide(self, text):
        path = self.root / 'decisions.txt'; path.write_text(text, encoding='utf-8')
        return path

    def test_boxes_are_proposed_round_what_is_drawn_and_not_round_the_captions(self):
        told = onboard.propose(self.sheets / '07_the_yard.png', self.root / 'out' / 'boxes.png')
        self.assertEqual((told['size'], told['split']), ([800, 700], 365))  # the split is under the one wide panel
        self.assertEqual(told['boxes'], {'T1': [96, 56, 525, 365], 'P1': [76, 516, 205, 645], 'P2': [296, 516, 465, 645]})
        with Image.open(self.root / 'out' / 'boxes.png') as page:
            self.assertEqual(page.size, (800, 365 // 2 + 700 - 365))  # the building views at half size over the prop set
        self.assertEqual(set(onboard.propose(self.sheets / '07_the_yard.png', self.root / 'out' / 'all.png', split=0)['boxes']), {'P1', 'P2', 'P3'})
        Image.new('RGB', (200, 200), (20, 20, 20)).save(self.root / 'dark.png')
        with self.assertRaisesRegex(ValueError, 'no light background'):
            onboard.propose(self.root / 'dark.png', self.root / 'out' / 'dark.png')

    def test_a_spec_becomes_set_files_in_the_layout_of_the_sets(self):
        self.assertEqual(onboard.write_sets(self.spec, self.sheets, self.sets), {'yard': 3})
        text = (self.sets / 'yard.json').read_text(encoding='utf-8'); data = reference.load_set(self.sets / 'yard.json')
        self.assertEqual(data['sheet'], {'file': '07_the_yard.png', 'sha256': hashlib.sha256((self.sheets / '07_the_yard.png').read_bytes()).hexdigest(), 'size': [800, 700]})
        self.assertEqual(data['assets']['gate'], {'kind': 'prop', 'type': 'vehicle-gate', 'subject': 'sliding yard gate', 'box': [296, 516, 464, 644]})
        self.assertEqual(data['assets']['building-hero']['notes'], 'Ignore the caption.')
        self.assertEqual(len(text.splitlines()), 6 + 3 + 3); self.assertEqual(text, onboard.layout(data['sheet'], data['assets']))  # one asset to a line
        with self.assertRaisesRegex(ValueError, 'yard is no new set name'):  # a set that is there is changed with revise
            onboard.write_sets(self.spec, self.sheets, self.sets)
        self.spec.write_text('@ yard2 07\nbuilding-hero | B | | the same warehouse | 96 56 524 364\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'yard2: 07_the_yard.png is the sheet of yard already'):  # under another name, it is the same sheet
            onboard.write_sets(self.spec, self.sheets, self.sets)
        self.spec.write_text('@ dock 08\nbuilding-hero | B | | dock shed | 96 56 524 364\n@ dock2 08\nbuilding-hero | B | | dock shed | 96 56 524 364\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'dock2: 08_the_dock.png is the sheet of dock already'):  # and so it is within one spec
            onboard.write_sets(self.spec, self.sheets, self.sets)
        self.assertEqual(sorted(path.name for path in self.sets.glob('*.json')), ['yard-game.json', 'yard.json'])

    def test_a_spec_the_kit_would_not_accept_writes_nothing(self):
        onboard.write_sets(self.spec, self.sheets, self.sets)
        for said, spec in (('Type console-desk needs one original', '@ dock 08\nbuilding-hero | B | | dock shed | 96 56 524 364\ndesk | console-desk | | dock desk | 76 516 204 644\n'),
                           ('Crop box is outside the sheet', '@ dock 08\nbuilding-hero | B | | dock shed | 96 56 524 900\n'),
                           ('one sheet starts 09_ and 0 were found', '@ dock 09\nbuilding-hero | B | | dock shed | 96 56 524 364\n'),
                           ('A box is x0 y0 x1 y1', '@ dock 08\nbuilding-hero | B | | dock shed | 96 56 524\n'),
                           ('A relation is', '@ dock 08\ndesk | console-desk | yard/desk | dock desk | 76 516 204 644\n'),
                           ('A building view has no relation', '@ dock 08\nbuilding-hero | B | =yard/desk | dock shed | 96 56 524 364\n'),
                           ('under its block', 'desk | console-desk | | dock desk | 76 516 204 644\n'), ('states no set', '# nothing\n')):
            self.spec.write_text(spec, encoding='utf-8')
            with self.assertRaisesRegex(ValueError, said):
                onboard.write_sets(self.spec, self.sheets, self.sets)
            self.assertFalse((self.sets / 'dock.json').exists(), said)
        self.spec.write_text('@ dock 08\nbuilding-hero | B | | dock shed | 96 56 524 364\ndesk | console-desk | =yard/desk | dock desk | 76 516 204 644\n', encoding='utf-8')
        self.spec.write_text(self.spec.read_text(encoding='utf-8') + 'gate | vehicle-gate | ~Branding: Dock gate. | dock gate | 296 516 464 644\nlamp | console-desk | ~!Lamp. | desk with a lamp | 600 500 700 650\n', encoding='utf-8')
        self.assertEqual(onboard.write_sets(self.spec, self.sheets, self.sets), {'dock': 4})  # the same prop, a branding variant and an unbranded one, each said so
        dock = reference.load_set(self.sets / 'dock.json')['assets']; self.assertEqual(reference.register(self.sets)['reuse'], 1)
        self.assertEqual((dock['desk']['same'], dock['gate']['variant'], dock['lamp']['variant'], dock['lamp']['unbranded']), ('yard/desk', 'Branding: Dock gate.', 'Lamp.', True))

    def test_the_decisions_of_a_review_are_applied_together_or_not_at_all(self):
        onboard.write_sets(self.spec, self.sheets, self.sets)
        self.spec.write_text('@ dock 08\nbuilding-hero | B | | dock shed | 96 56 524 364\ndesk | console-desk | =yard/desk | dock desk | 76 516 204 644\n'
                             'gate | vehicle-gate | ~Branding: Dock gate. | dock gate | 296 516 464 644\n', encoding='utf-8')
        onboard.write_sets(self.spec, self.sheets, self.sets); before = {path.name: path.read_bytes() for path in self.sets.glob('*.json')}
        self.assertEqual(onboard.revise(self.decide('# nothing\n'), self.sets), [])
        for said, text in (('No such asset', 'dock/crane | !\n'), ('Type console-desk needs one original', 'dock/desk | ^\n'), ('decided once', 'dock/desk | !\ndock/desk | ^\n'),
                           ('has it already', '+ dock/desk | console-desk | =yard/desk | dock desk | 76 516 204 644\n'), ('its box alone', 'dock/building-hero | !\n'),
                           ('A rename is', '* console-desk\n'), ('starts with set/asset', 'desk | !\n'), ('Crop box is outside', 'dock/desk | box 76 516 204 900\n')):
            with self.assertRaisesRegex(ValueError, said):
                onboard.revise(self.decide('yard/gate | box 290 510 470 650\n' + text), self.sets)  # the good decision beside it is not written either
            self.assertEqual({path.name: path.read_bytes() for path in self.sets.glob('*.json')}, before, said)
        changed = onboard.revise(self.decide('dock/desk | ~!Desk with a dock lamp.\ndock/gate | =yard/gate\nyard/gate | ! | box 290 510 470 650\n'
                                             '+ dock/lamp | yard-lamp | | pole lamp | 600 500 700 650\n* console-desk > office-desk\n'), self.sets)
        self.assertEqual(changed, ['dock', 'yard']); dock, yard = (reference.load_set(self.sets / f'{name}.json')['assets'] for name in ('dock', 'yard'))
        self.assertEqual(dock['desk'], {'kind': 'prop', 'type': 'office-desk', 'variant': 'Desk with a dock lamp.', 'unbranded': True, 'subject': 'dock desk', 'box': [76, 516, 204, 644]})
        self.assertEqual((dock['gate']['same'], 'variant' in dock['gate'], dock['lamp']['type'], yard['desk']['type']), ('yard/gate', False, 'yard-lamp', 'office-desk'))
        self.assertEqual(yard['gate'], {'kind': 'prop', 'type': 'vehicle-gate', 'unbranded': True, 'subject': 'sliding yard gate', 'box': [290, 510, 470, 650]})
        self.assertEqual(before['yard-game.json'], (self.sets / 'yard-game.json').read_bytes())
        self.assertEqual(onboard.revise(self.decide('dock/desk | ~Branding: Desk with the dock\'s name.\n'), self.sets), ['dock'])  # a branding variant is not drawn unbranded
        self.assertNotIn('unbranded', reference.load_set(self.sets / 'dock.json')['assets']['desk'])
        self.assertEqual(onboard.revise(self.decide('dock/gate | ^ | type dock-gate\n'), self.sets), ['dock'])  # the original of a type of its own
        self.assertEqual(reference.load_set(self.sets / 'dock.json')['assets']['gate'], {'kind': 'prop', 'type': 'dock-gate', 'subject': 'dock gate', 'box': [296, 516, 464, 644]})

    def test_the_shipped_sets_are_in_the_layout_a_revision_writes(self):
        """`revise` writes a set only where its text changes: a set out of the layout would be rewritten by any review."""
        shipped = onboard.concept_sets(Path(__file__).with_name('sets')); self.assertGreaterEqual(len(shipped), 55)
        for name, data in shipped.items():
            self.assertEqual(onboard.layout(data['sheet'], data['assets']).encode('utf-8'), (Path(__file__).with_name('sets') / f'{name}.json').read_bytes(), name)

    def test_the_audit_tells_what_a_reading_would_not_catch(self):
        onboard.write_sets(self.spec, self.sheets, self.sets)
        self.assertEqual(onboard.audit(self.sets, self.sheets), {'sets': 1, 'props': 2, 'findings': {'sheets without a set': ['08_the_dock.png'], 'types of one prop': ['console-desk', 'vehicle-gate']}})
        data = json.loads((self.sets / 'yard.json').read_text(encoding='utf-8')); assets = data['assets']
        assets['desk'].update(subject='Ares office desk.', box=[76, 516, 204, 540]); assets['gate']['box'] = [100, 500, 464, 644]; del assets['building-hero']['notes']
        assets['building-rear'] = assets.pop('building-hero'); assets['lamp'] = {'kind': 'prop', 'type': 'yard-lamp', 'same': 'yard/desk', 'subject': 'pole  lamp', 'box': [600, 500, 700, 650], 'notes': 'Tall'}
        (self.sets / 'yard.json').write_text(onboard.layout(data['sheet'], assets).replace('"kind": "prop", "type": "yard-lamp"', '"kind": "building", "kind": "prop", "type": "yard-lamp"'), encoding='utf-8')
        sheet(self.sheets / '07_the_yard.png', {'hall': [100, 60, 520, 300]})  # the sheet was drawn again
        found = onboard.audit(self.sets, self.sheets)['findings']
        self.assertEqual(found['sheet differs from the set'], ['yard']); self.assertEqual(found['no building-hero'], ['yard']); self.assertEqual(found['key stated twice'], ['yard: kind'])
        self.assertEqual(found['tiny box'], ['yard/desk 128x24']); self.assertEqual(found['prop boxes overlap'], ['yard: desk / gate 81% NO NOTE'])
        self.assertEqual(found['subject form'], ['yard/desk: Ares office desk.']); self.assertEqual(found['brand word in an unbranded prop'], ['yard/desk [console-desk] subject: Ares office desk.'])
        self.assertEqual(found['untidy text'], ["yard/lamp subject: 'pole  lamp'"]); self.assertEqual(found['no full stop'], ['yard/lamp notes: Tall']); self.assertEqual(found['same with notes'], ['yard/lamp: Tall'])
        del assets['lamp']['box']; (self.sets / 'yard.json').write_text(onboard.layout(data['sheet'], assets), encoding='utf-8')  # a set the kit cannot read
        (self.sets / 'dock.json').write_text(onboard.layout({**data['sheet'], 'file': '08_the_dock.png'}, {'building-hero': {'kind': 'building', 'subject': 'dock shed', 'box': [96, 56, 524, 364]}}), encoding='utf-8')
        found = onboard.audit(self.sets, self.sheets)
        self.assertEqual((found['sets'], found['findings']['set refused']), (1, ['yard: Asset needs kind, subject and box: lamp']))  # told, and the other set is still audited
        self.assertEqual(found['findings']['hero without notes'], ['dock']); self.assertNotIn('sheets without a set', found['findings'])  # the refused set's sheet is not told as one without a set

    def test_the_pictures_of_a_review_are_drawn(self):
        onboard.write_sets(self.spec, self.sheets, self.sets); out = self.root / 'out'
        self.spec.write_text('@ dock 08\nbuilding-hero | B | | dock shed | 96 56 524 364\ndesk | console-desk | =yard/desk | dock desk | 76 516 204 644\n'
                             'gate | vehicle-gate | ~Branding: Dock gate. | dock gate | 296 516 464 644\n', encoding='utf-8'); onboard.write_sets(self.spec, self.sheets, self.sets)
        self.assertEqual(onboard.crops_page(self.sets / 'yard.json', self.sheets, out / 'crops.png'), 3)
        self.assertEqual(onboard.overlay(self.sets, self.sheets, str(out / 'overlay')), [str(out / 'overlay') + '-01.png'])
        with Image.open(out / 'overlay-01.png') as page:
            colours = {colour for _, colour in page.convert('RGB').getcolors(1 << 20)}
        self.assertTrue({onboard.MADE, onboard.REUSED, onboard.BUILDING} <= colours)  # made, reused and a building view, each in its colour
        self.assertEqual(onboard.type_page(self.sets, self.sheets, out / 'types.png', ['vehicle-gate', 'console-desk']), 3)  # the reused desk is not drawn
        self.assertEqual(onboard.same_pages(self.sets, self.sheets, str(out / 'same')), {'targets': 1, 'reuses': 1, 'pages': [str(out / 'same') + '-01.png']})
        self.assertEqual(onboard.same_pages(self.sets, self.sheets, str(out / 'dock'), only=['dock'])['reuses'], 1)
        for said, call in (('No made prop is of type crane', lambda: onboard.type_page(self.sets, self.sheets, out / 'none.png', ['crane'])),
                           ('Name a type', lambda: onboard.type_page(self.sets, self.sheets, out / 'none.png', [])),
                           ('No prop reuses another in harbour', lambda: onboard.same_pages(self.sets, self.sheets, str(out / 'none'), only=['harbour'])),
                           ('No concept sets', lambda: onboard.overlay(self.root / 'sheets', self.sheets, str(out / 'none'))),
                           ('Concept sheet not found', lambda: onboard.crops_page(self.sets / 'yard.json', self.root / 'out', out / 'none.png'))):
            with self.assertRaisesRegex(ValueError, said):
                call()
        sheet(self.sheets / '07_the_yard.png', {'hall': [100, 60, 520, 300]})  # drawn again under its name: the set's boxes are on the drawing before
        for call in (lambda: onboard.crops_page(self.sets / 'yard.json', self.sheets, out / 'again.png'), lambda: onboard.overlay(self.sets, self.sheets, str(out / 'again')),
                     lambda: onboard.type_page(self.sets, self.sheets, out / 'again.png', ['vehicle-gate']), lambda: onboard.same_pages(self.sets, self.sheets, str(out / 'again'))):
            with self.assertRaisesRegex(ValueError, 'Concept sheet differs from the set: 07_the_yard.png'):
                call()

    def test_the_commands_say_what_they_need(self):
        from argparse import Namespace
        from . import __main__ as command
        blank = dict(sets=str(self.sets), sheets=None, sheet=None, split=None, spec=None, set=None, type=[], only=[], decisions=None, output=None)
        for action, said in (('boxes', '--sheet, --output'), ('sets', '--spec, --sheets'), ('types', '--sheets, --output, --type'), ('revise', '--decisions')):
            with self.assertRaisesRegex(ValueError, f'onboard {action} needs {said}'):
                command.command_onboard(Namespace(action=action, **blank))
        for action, given, said in (('audit', dict(sheets='s', only=['yard']), '--only'), ('revise', dict(decisions='d', sheets='s', split=0), '--sheets, --split'),
                                    ('crops', dict(set='x', sheets='s', output='o', type=['desk']), '--type')):
            with self.assertRaisesRegex(ValueError, f'onboard {action} does not take {said}'):  # what it would ignore is refused
                command.command_onboard(Namespace(action=action, **{**blank, **given}))
        for action, given, said in (('pathnodes', dict(tileset=['dgt04'], tile=[3], output=None), 'takes --packs and --tileset alone'),
                                    ('tiles', dict(tileset=['dgt04', 'udp1'], tile=[3], output='o'), 'reads one --tileset'), ('tiles', dict(tileset=['dgt04'], tile=[], output='o'), 'needs --tile')):
            with self.assertRaisesRegex(ValueError, said):
                command.command_study(Namespace(action=action, packs=str(self.root), **given))


if __name__ == '__main__':
    unittest.main()
