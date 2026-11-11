"""Reference sets name real crops, prompts ask for an isolated unlit-spill view, and a busy server is left alone."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

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

    def test_a_busy_server_gets_no_job(self):
        client = FakeClient(self.local['comfyOutput'], busy=True)
        with self.assertRaisesRegex(ValueError, 'busy'):
            reference.make(client, self.local, self.bindings, 'crate', 'redraw', self.sheet, 7, self.root / 'refs')
        self.assertEqual(client.routes, ['/queue'])


if __name__ == '__main__':
    unittest.main()
