"""Reference sets name real crops, prompts ask for an isolated unlit-spill view, and a busy server is left alone."""
import copy
import importlib.util
import itertools
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import reference

SET = Path(__file__).with_name('sets') / 'stuffer-shack.json'
IMAGING = importlib.util.find_spec('PIL') is not None and importlib.util.find_spec('numpy') is not None


class FakeClient:
    """Mocked ComfyUI: never any HTTP. /prompt writes one PNG per batch item into the bound output folder."""
    url = 'http://127.0.0.1:8188'

    def __init__(self, output, busy=False):
        self.output = Path(output); self.busy = busy; self.routes = []; self.graph = None; self.images = []

    def request(self, route, data=None):
        self.routes.append(route)
        if route == '/queue':
            return {'queue_running': [[1]] if self.busy else [], 'queue_pending': []}
        if route == '/prompt':
            from PIL import Image
            self.graph = data['prompt']; folder, stem = self.graph['9']['inputs']['filename_prefix'].rsplit('/', 1)
            path = self.output / folder / f'{stem}_00001_.png'; path.parent.mkdir(parents=True, exist_ok=True)
            Image.new('RGB', (16, 16), (200, 30, 30)).save(path)
            self.images = [{'filename': path.name, 'subfolder': folder, 'type': 'output'}]
            return {'prompt_id': 'p1', 'node_errors': {}}
        if route == '/history/p1':
            return {'p1': {'outputs': {'9': {'images': self.images}}, 'status': {'status_str': 'success', 'completed': True}}}
        raise AssertionError('Unexpected route ' + route)


class SetTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup); self.root = Path(self.folder.name)

    def write(self, data):
        path = self.root / 'set.json'; path.write_text(json.dumps(data), encoding='utf-8'); return path

    def test_the_pilot_set_loads_and_every_asset_has_a_prompt(self):
        data = reference.load_set(SET)
        self.assertIn('building-hero', data['assets'])
        for asset in data['assets'].values():
            text = reference.prompt(asset['kind'], asset['subject'], asset.get('notes', ''))
            self.assertIn('plain white background', text); self.assertIn(asset['subject'], text)

    def test_a_building_prompt_removes_the_street_and_keeps_lit_colours_without_spill(self):
        text = reference.prompt('building', 'corner shop', 'Roof units stay.')
        self.assertIn('Remove the road', text); self.assertIn('Roof units stay.', text)
        self.assertIn('Keep the pavement slab', text); self.assertIn('street furniture on it', text)  # both ship on the building
        self.assertIn('keep their own colours', text); self.assertIn('nothing glows', text)
        for kind in ('prop', 'building'):  # the edit tidies unless told not to
            self.assertIn('do not clean or repaint', reference.prompt(kind, 'thing'))
        self.assertNotIn('Remove the road', reference.prompt('prop', 'crate'))
        with self.assertRaisesRegex(ValueError, 'kind'):
            reference.prompt('vehicle', 'van')

    def test_a_set_rejects_machine_paths_bad_names_and_boxes_off_the_sheet(self):
        good = json.loads(SET.read_text(encoding='utf-8'))
        for change, message in ((lambda d: d['sheet'].update(file='C:/art/sheet.png'), 'bare file name'),
                                (lambda d: d['assets'].update({'Bad Name': d['assets']['trash-can']}), 'safe IDs'),
                                (lambda d: d['assets']['trash-can'].update(box=[0, 0, 5000, 10]), 'outside the sheet'),
                                (lambda d: d['assets']['trash-can'].update(box=[10, 10, 10, 20]), 'outside the sheet'),
                                (lambda d: d['assets']['trash-can'].pop('subject'), 'kind, subject and box')):
            data = copy.deepcopy(good); change(data)
            with self.assertRaisesRegex(ValueError, message):
                reference.load_set(self.write(data))

    def sheet(self, stem, **props):
        assets = {name.replace('_', '-'): {'kind': 'prop', 'subject': name, 'box': [0, 0, 2, 2], **more} for name, more in props.items()}
        data = {'sheet': {'file': stem + '.png', 'sha256': 'a' * 64, 'size': [4, 4]}, 'assets': assets}
        (self.root / f'{stem}.json').write_text(json.dumps(data), encoding='utf-8')

    def test_the_onboarded_sheets_declare_every_repeated_prop(self):
        found = reference.register(SET.parent)  # the game sets in the same folder are not sheets and are passed over
        self.assertEqual(found['types']['trash-can']['original'], ['stuffer-shack/trash-can'])
        self.assertEqual(found['make'] + found['reuse'], sum(len(row) for rows in found['types'].values() for row in rows.values()))

    def test_a_crop_that_catches_its_neighbour_says_so(self):
        """On a packed sheet two boxes can share ground; the edit then needs a note on which object is meant."""
        for path in sorted(SET.parent.glob('*.json')):
            data = json.loads(path.read_text(encoding='utf-8'))
            props = [(name, asset) for name, asset in data.get('assets', {}).items() if 'sheet' in data and asset['kind'] == 'prop']
            for index, (name, asset) in enumerate(props):
                for other, second in props[index + 1:]:
                    (a0, a1, a2, a3), (b0, b1, b2, b3) = asset['box'], second['box']
                    shared = max(0, min(a2, b2) - max(a0, b0)) * max(0, min(a3, b3) - max(a1, b1))
                    if shared * 10 > min((a2 - a0) * (a3 - a1), (b2 - b0) * (b3 - b1)):
                        self.assertTrue('notes' in asset or 'notes' in second, f'{path.stem}: {name} and {other} overlap')

    def test_an_unbranded_prop_is_drawn_without_the_mark_on_its_sheet(self):
        text = reference.prompt('prop', 'access kiosk', unbranded=True)
        self.assertIn('leave off every company logo', text); self.assertNotIn('markings', text)
        self.assertIn('Hazard stripes', text); self.assertIn('do not clean or repaint', text)
        self.assertIn('markings', reference.prompt('prop', 'access kiosk'))
        # A generic sheet's building keeps its slab and generic words, without company or place names.
        building = reference.prompt('building', 'depot with a RAIL FREIGHT sign', unbranded=True)
        self.assertIn('leave off every company name, place name and logo', building); self.assertNotIn('signage', building)
        self.assertIn('FREIGHT', building); self.assertIn('pavement slab', building); self.assertIn('do not clean or repaint', building)
        self.assertIn('signage', reference.prompt('building', 'depot'))
        good = json.loads(SET.read_text(encoding='utf-8'))
        good['assets']['trash-can']['unbranded'] = True; good['assets']['building-front']['unbranded'] = True
        drawn = reference.load_set(self.write(good))['assets']
        self.assertTrue(drawn['trash-can']['unbranded'] and drawn['building-front']['unbranded'])
        data = copy.deepcopy(good); data['assets']['building-front']['type'] = 'shop'
        with self.assertRaisesRegex(ValueError, 'Only props have a type'):
            reference.load_set(self.write(data))
        for change in ({'same': 'shop/bin'}, {'variant': 'Branding: red bin with the shop emblem.'}):  # nothing made; the mark is wanted
            data = copy.deepcopy(good); data['assets']['trash-can'].update(change)
            with self.assertRaisesRegex(ValueError, 'unbranded is for a prop that is made'):
                reference.load_set(self.write(data))

    def test_a_type_drawn_on_two_sheets_must_say_same_or_variant(self):
        self.sheet('shop', bin={'type': 'trash-can'}, camera={'type': 'security-camera'})
        self.sheet('depot', bin={'type': 'trash-can'})
        with self.assertRaisesRegex(ValueError, 'Type trash-can needs one original.*depot/bin, shop/bin'):
            reference.register(self.root)
        self.sheet('depot', bin={'type': 'trash-can', 'same': 'shop/bin'}, skip={'type': 'trash-can', 'variant': 'A wheeled skip.'})
        found = reference.register(self.root)
        self.assertEqual(found['types']['trash-can'], {'original': ['shop/bin'], 'variant': ['depot/skip'], 'same': ['depot/bin']})
        self.assertEqual((found['make'], found['reuse']), (3, 1))

    def test_same_names_a_made_prop_of_its_own_type(self):
        self.sheet('shop', bin={'type': 'trash-can'}, camera={'type': 'security-camera'})
        for target in ('shop/camera', 'shop/gone', 'yard/bin'):  # another type, no such prop, itself only a same
            self.sheet('depot', bin={'type': 'trash-can', 'same': target})
            self.sheet('yard', bin={'type': 'trash-can', 'same': 'shop/bin'})
            with self.assertRaisesRegex(ValueError, 'not a made prop of type trash-can'):
                reference.register(self.root)
        self.sheet('depot', bin={'type': 'trash-can', 'variant': 'Dented.'}); self.sheet('yard', bin={'type': 'trash-can', 'same': 'depot/bin'})
        self.assertEqual(reference.register(self.root)['types']['trash-can']['same'], ['yard/bin'])  # a variant is made, so it serves

    def test_props_carry_a_type_and_buildings_none(self):
        good = json.loads(SET.read_text(encoding='utf-8'))
        for change, message in ((lambda d: d['assets']['trash-can'].pop('type'), 'needs a type'),
                                (lambda d: d['assets']['trash-can'].update(same='shop/bin', variant='Taller.'), 'not both'),
                                (lambda d: d['assets']['trash-can'].update(same='bin'), 'set/asset'),
                                (lambda d: d['assets']['trash-can'].update(variant=' '), 'one line'),
                                (lambda d: d['assets']['trash-can'].update(type='recycle-bin'), 'recycle-bin is now trash-can'),
                                (lambda d: d['assets']['building-hero'].update(type='shop'), 'Only props')):
            data = copy.deepcopy(good); change(data)
            with self.assertRaisesRegex(ValueError, message):
                reference.load_set(self.write(data))

    def test_a_piece_of_a_building_is_cut_from_the_chosen_reference_of_its_whole_view(self):
        """User, 2026-11-12: a building too large for one 4K texture is made in pieces; each piece's view is drawn from the
        one chosen reference of the whole, so the pieces keep its proportions and colours between them."""
        from PIL import Image
        good = json.loads(SET.read_text(encoding='utf-8')); whole = next(name for name, asset in good['assets'].items() if asset['kind'] == 'building')
        good['assets']['building-left'] = {'kind': 'building', 'subject': 'left half of the shop', 'box': [0, 0, 10, 10], 'cut': {'from': whole, 'box': [0, 0, 60, 40]}}
        data = reference.load_set(self.write(good)); selected = self.root / 'selected'; selected.mkdir()
        Image.new('RGB', (100, 40), 'red').save(selected / f'{whole}-s101-b0.png')
        with Image.open(reference.source(data, 'building-left', None, selected, self.root / 'left.png')) as cut:
            margin = round(60 * reference.CUT_MARGIN)  # set on white, so that its cut edges read as the ends of a block
            self.assertEqual(cut.size, (60 + 2 * margin, 40 + 2 * margin)); self.assertEqual(cut.getpixel((0, 0)), (255, 255, 255))
            self.assertEqual(cut.getpixel((margin, margin)), (255, 0, 0))
        for change, message in ((lambda a: a.update(cut={'from': 'trash-can', 'box': [0, 0, 6, 4]}), 'another, whole, view'),
                                (lambda a: a.update(cut={'from': 'building-left', 'box': [0, 0, 6, 4]}), 'another, whole, view'),
                                (lambda a: a.update(cut={'from': whole, 'box': [6, 0, 6, 4]}), 'its box in pixels'),
                                (lambda a: a.update(cut={'from': whole}), 'another, whole, view'),
                                (lambda a: a.update(cut={'from': [whole], 'box': [0, 0, 6, 4]}), 'another, whole, view')):
            data = copy.deepcopy(good); change(data['assets']['building-left'])
            with self.assertRaisesRegex(ValueError, message):
                reference.load_set(self.write(data))
        data = copy.deepcopy(good); data['assets']['building-left']['cut']['box'] = [0, 0, 120, 40]
        with self.assertRaisesRegex(ValueError, 'runs off'):
            reference.source(reference.load_set(self.write(data)), 'building-left', None, selected, self.root / 'left.png')
        # A mirrored cut flips the chosen reference left to right first, and its box is in the flipped picture.
        picture = Image.new('RGB', (100, 40), 'red'); picture.paste((0, 0, 255), (0, 0, 10, 40)); picture.save(selected / f'{whole}-s101-b0.png')
        data = copy.deepcopy(good); data['assets']['building-left']['cut'].update(box=[90, 0, 100, 40], mirror=True)
        with Image.open(reference.source(reference.load_set(self.write(data)), 'building-left', None, selected, self.root / 'mirrored.png')) as cut:
            margin = round(40 * reference.CUT_MARGIN); self.assertEqual(cut.getpixel((margin + 5, margin + 20)), (0, 0, 255))
        for wrong in (False, 'yes'):
            data['assets']['building-left']['cut']['mirror'] = wrong
            with self.assertRaisesRegex(ValueError, 'another, whole, view'):
                reference.load_set(self.write(data))

    def test_a_view_the_sheet_does_not_draw_is_turned_from_the_chosen_reference_of_one_it_does(self):
        """User, 2026-11-13: the rail yard's corner view drew another building than its front ("fix the warehouse back
        view"), so its back is drawn from the front's chosen reference, seen from behind."""
        from PIL import Image
        good = json.loads(SET.read_text(encoding='utf-8')); whole = next(name for name, asset in good['assets'].items() if asset['kind'] == 'building')
        good['assets']['building-back'] = {'kind': 'building', 'unbranded': True, 'subject': 'shop', 'box': [0, 0, 10, 10], 'turn': {'from': whole, 'to': 'the back'}}
        data = reference.load_set(self.write(good)); selected = self.root / 'selected'; selected.mkdir()
        Image.new('RGB', (100, 40), 'red').save(selected / f'{whole}-s101-b0.png')
        with Image.open(reference.source(data, 'building-back', None, selected, self.root / 'back.png')) as back:
            margin = round(100 * reference.CUT_MARGIN)  # the whole reference, set on white
            self.assertEqual(back.size, (100 + 2 * margin, 40 + 2 * margin)); self.assertEqual(back.getpixel((margin, margin)), (255, 0, 0))
        text = reference.prompt('building', 'shop', unbranded=True, turn='the back')
        self.assertIn('Show this same shop seen from the back', text); self.assertNotIn('viewing angle', text)
        self.assertIn('leave off every company name', text.lower()); self.assertIn('pavement slab', text); self.assertIn('do not clean or repaint', text)
        self.assertNotIn('company name', reference.prompt('building', 'shop', turn='the back'))
        for change, message in ((lambda a: a.update(turn={'from': 'trash-can', 'to': 'the back'}), 'another, whole, view'),
                                (lambda a: a.update(turn={'from': 'building-back', 'to': 'the back'}), 'another, whole, view'),
                                (lambda a: a.update(turn={'from': whole}), 'another, whole, view'),
                                (lambda a: a.update(cut={'from': whole, 'box': [0, 0, 6, 4]}), 'another, whole, view'),
                                (lambda a: a.update(turn={'from': whole, 'to': 'the back\nand the side'}), 'one line')):
            data = copy.deepcopy(good); change(data['assets']['building-back'])
            with self.assertRaisesRegex(ValueError, message):
                reference.load_set(self.write(data))
        # A turned view is whole, so a piece may be cut from it (the rail yard's rear piece), but not turned again.
        data = copy.deepcopy(good); data['assets']['building-left'] = {'kind': 'building', 'subject': 'left', 'box': [0, 0, 10, 10], 'cut': {'from': 'building-back', 'box': [0, 0, 6, 4]}}
        self.assertIn('building-left', reference.load_set(self.write(data))['assets'])
        data['assets']['building-left'] = {'kind': 'building', 'subject': 'left', 'box': [0, 0, 10, 10], 'turn': {'from': 'building-back', 'to': 'the left'}}
        with self.assertRaisesRegex(ValueError, 'another, whole, view'):
            reference.load_set(self.write(data))

    def test_a_sheet_is_accepted_only_at_its_recorded_hash(self):
        sheet = {'file': 'sheet.png', 'sha256': 'a' * 64, 'size': [4, 4]}
        with self.assertRaisesRegex(ValueError, 'not found'):
            reference.resolve_sheet(self.root, sheet)
        (self.root / 'sheet.png').write_bytes(b'other bytes')
        with self.assertRaisesRegex(ValueError, 'differs'):
            reference.resolve_sheet(self.root, sheet)


@unittest.skipUnless(IMAGING, 'needs Pillow and numpy')
class MakeTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup); self.root = Path(self.folder.name)
        # The fake stands for a controlled ComfyUI; the GPU lease lives in this test's own tools root.
        for patcher in (mock.patch('tools.headkit.shared_comfy.proven', return_value={'identity': {}, 'approval': None}),
                        mock.patch('tools.headkit.shared_comfy.recheck'),
                        mock.patch.dict('os.environ', {'SRN_TOOLS_ROOT': str(self.root / 'tools')})):
            patcher.start(); self.addCleanup(patcher.stop)
        self.local = {'comfyInput': str(self.root / 'in'), 'comfyOutput': str(self.root / 'out')}
        self.bindings = self.root / 'bindings.json'; self.bindings.write_text(json.dumps(self.local), encoding='utf-8')
        self.sheet = self.root / 'sheet.png'; Image.new('RGB', (64, 48), (10, 120, 200)).save(self.sheet)

    def test_crop_cuts_the_named_box(self):
        from PIL import Image
        with Image.open(reference.crop(self.sheet, [4, 8, 36, 40], self.root / 'crops' / 'a.png')) as image:
            self.assertEqual(image.size, (32, 32))

    def test_make_sends_the_crop_as_a_qwen_edit_reference_and_leaves_a_receipt(self):
        source = reference.crop(self.sheet, [0, 0, 32, 32], self.root / 'crop.png'); client = FakeClient(self.local['comfyOutput'])
        result = reference.make(client, self.local, self.bindings, 'crate', 'redraw', source, 7, self.root / 'refs')
        self.assertEqual(client.routes[0], '/queue')
        encoder = client.graph['6']['inputs']
        self.assertEqual(encoder['vae'], ['10', 0]); self.assertEqual(encoder['images.image_1'], ['100', 0])
        receipt = json.loads(Path(result['receipt']).read_text(encoding='utf-8'))
        self.assertEqual((receipt['kind'], receipt['asset'], receipt['state']), ('envkit-reference', 'crate', 'complete'))
        self.assertTrue(Path(result['outputs'][0]).is_file())
        with self.assertRaisesRegex(ValueError, 'Receipt already exists'):
            reference.make(client, self.local, self.bindings, 'crate', 'redraw', source, 7, self.root / 'refs')

    def test_a_busy_server_is_waited_for_and_gets_no_job_while_busy(self):
        client = FakeClient(self.local['comfyOutput'], busy=True)
        with mock.patch('tools.headkit.shared_comfy.time.sleep'),                 mock.patch('tools.headkit.shared_comfy.time.monotonic', side_effect=itertools.count(0, 1000)):
            with self.assertRaisesRegex(ValueError, 'stayed busy'):
                reference.make(client, self.local, self.bindings, 'crate', 'redraw', self.sheet, 7, self.root / 'refs')
        self.assertEqual(set(client.routes) - {'/upload/image'}, {'/queue'})

    def test_a_run_may_pass_over_an_asset_that_fails_and_make_the_rest(self):
        from argparse import Namespace
        from unittest import mock
        from . import __main__ as command
        data = {'sheet': 'sheet.png', 'assets': {name: {'kind': 'prop', 'subject': name} for name in ('crate', 'bin', 'lamp')}}

        def made(client, local, bindings, name, *rest, **more):
            if name == 'bin':
                raise ValueError('The shared ComfyUI queue stayed busy for 2700 s; nothing submitted')
            return {'state': 'complete', 'outputs': [name + '.png'], 'elapsedSeconds': 1.0}
        asked = dict(set='set.json', sheets='sheets', asset=[], bindings=str(self.bindings), url='http://127.0.0.1:8188', output=str(self.root / 'refs'), selected=None, seed=7, deadline=60)
        with mock.patch.object(reference, 'load_set', return_value=data), mock.patch.object(reference, 'resolve_sheet'), mock.patch.object(reference, 'source'), \
                mock.patch.object(reference, 'make', side_effect=made) as make, mock.patch('tools.headkit.comfy.Client'), mock.patch('builtins.print') as said:
            with self.assertRaisesRegex(ValueError, '1 of 3 assets were not made: bin'):
                command.command_reference(Namespace(keep_going=True, **asked))
            told = [json.loads(call.args[0]) for call in said.call_args_list]
            self.assertEqual([(one['asset'], one['state']) for one in told], [('crate', 'complete'), ('bin', 'failed'), ('lamp', 'complete')])
            self.assertIn('stayed busy', told[1]['error'])
            make.reset_mock()
            with self.assertRaisesRegex(ValueError, 'stayed busy'):  # without --keep-going the first failure stops the run
                command.command_reference(Namespace(keep_going=False, **asked))
            self.assertEqual([call.args[3] for call in make.call_args_list], ['crate', 'bin'])


if __name__ == '__main__':
    unittest.main()
