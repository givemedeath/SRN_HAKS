"""Source jobs are posted only for images that come from a brief, and geometry attempts are counted."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import brief, generate
from .test_brief import document


class Engine:
    """The engine, replaced: it records what is posted and answers each job with the outputs set for it."""

    def __init__(self):
        self.posted, self.uploaded, self.busy = [], [], False
        self.outputs = {'12': {'images': [{'filename': 'node-12_00001_.png', 'subfolder': 's', 'type': 'output'}]},
                        '30': {'text': ['fov 36.6']}}
        self.status, self.refuse, self.lost = 'success', False, False
        self.meanwhile = None  # called once while a posted job is being waited for

    def idle(self):
        return not self.busy

    def request(self, route, data=None):
        if route == '/prompt':
            if self.refuse:
                return {'node_errors': {'1': 'bad'}}
            self.posted.append(data)
            return {'prompt_id': f'job-{len(self.posted)}'}
        if self.lost:
            raise ConnectionError('the engine went away')
        if self.meanwhile:
            meanwhile, self.meanwhile = self.meanwhile, None
            meanwhile()
        prompt_id = route.rsplit('/', 1)[1]
        return {prompt_id: {'outputs': self.outputs, 'status': {'status_str': self.status, 'completed': True}}}

    def patches(self):
        def upload(url, path, name, subfolder):
            self.uploaded.append((Path(path).name, name, subfolder))
            return f'{subfolder}/{name}'
        compiled = lambda stage, profile, images, prefix, **options: {'stage': stage, 'profile': profile, 'images': images, 'prefix': prefix, **options}
        return (mock.patch.object(generate.comfy, 'Client', lambda url: self),
                mock.patch.object(generate.comfy, 'compile_graph', compiled),
                mock.patch.object(generate, 'bound', lambda graph, models: ({**graph, 'models': str(models)}, [{'name': 'model', 'sha256': 'abc'}])),
                mock.patch.object(generate, 'export_settings', lambda graph, settings: {**graph, 'settings': settings}),
                mock.patch.object(generate, 'analyze_reference', lambda image: {'route': 'white', 'reason': 'plain', 'size': [8, 8], 'more': 1}),
                mock.patch.object(generate.reference, 'upload', upload),
                mock.patch.object(generate.reference, 'fetch', lambda url, row, timeout=120: ('made ' + row['filename']).encode()))


class GenerateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name).resolve()
        self.folder = self.work / 'outfit' / 'reference-1'
        brief.seal(document(), self.folder)
        self.image = self.folder / 'image.png'
        self.image.write_bytes(b'made from the brief')
        brief.register(self.folder, self.image)
        self.stray = self.work / 'outfit' / 'stray.png'
        self.stray.write_bytes(b'from somewhere else')
        self.engine = Engine()
        for patch in self.engine.patches():
            patch.start()
            self.addCleanup(patch.stop)

    def ledger(self):
        return json.loads((self.work / generate.LEDGER).read_text(encoding='utf-8'))['models']['outfit']

    def test_an_image_with_no_brief_behind_it_is_not_taken_further(self):
        calls = (lambda: generate.calibrate(self.work, 'outfit', self.stray, 'models'),
                 lambda: generate.geometry(self.work, 'outfit', self.stray, 36.0, 'models'),
                 lambda: generate.appearance(self.work, 'outfit', self.stray, 36.0, self.image, 'models'))
        for call in calls:
            with self.assertRaises(ValueError) as refused:
                call()
            self.assertIn('does not come from a brief', str(refused.exception))
        self.assertEqual((self.engine.posted, self.engine.uploaded), ([], []))
        self.assertFalse((self.work / 'outfit' / generate.JOBS).exists())  # no job folder
        self.assertFalse((self.work / generate.LEDGER).exists())  # and no attempt counted

    def test_calibrating_registers_the_copies_it_makes(self):
        done = generate.calibrate(self.work, 'outfit', self.image, 'models')
        folder = self.work / 'outfit' / generate.JOBS / 'calibrate-1'
        self.assertEqual((done['folder'], done['status'], done['files'], done['brief']), (str(folder), 'success', ['node-12_00001_.png'], 'test-outfit'))
        self.assertEqual(done['previews'], {'30': ['fov 36.6']})
        self.assertEqual(done['background'], {'route': 'white', 'reason': 'plain', 'size': [8, 8]})
        record = json.loads((folder / 'record.json').read_text(encoding='utf-8'))
        self.assertEqual((record['stage'], record['imageSha256'], record['route']), ('calibrate', brief.digest(self.image), 'direct, unguarded'))
        posted = self.engine.posted[0]['prompt']
        self.assertEqual((posted['stage'], posted['profile'], posted['models']), ('calibrate', generate.PROFILE, 'models'))
        self.assertEqual(set(posted['images']), {'geometry', 'detail', 'mask'})
        # the copy is the same reference: a geometry job on it is let through
        copy = folder / 'node-12_00001_.png'
        self.assertEqual(copy.read_bytes(), b'made node-12_00001_.png')
        self.assertEqual(brief.admit(copy, self.work / 'outfit')[1], self.folder)
        generate.geometry(self.work, 'outfit', copy, 36.6, 'models')
        self.assertFalse((self.work / generate.LEDGER).read_text(encoding='utf-8').count('calibrate'))  # calibrating is not an attempt

    def test_a_geometry_attempt_is_counted_before_it_is_posted(self):
        done = generate.geometry(self.work, 'outfit', self.image, 36.6, 'models')
        self.assertEqual((done['attempt'], done['status'], done['fov']), (1, 'success', 36.6))
        row = self.ledger()[0]
        self.assertEqual((row['attempt'], row['state'], row['fov'], row['promptId'], row['imageSha256']),
                         (1, 'complete', 36.6, 'job-1', brief.digest(self.image)))
        self.assertEqual(Path(row['folder']), Path('outfit') / generate.JOBS / 'geometry-1')
        self.assertTrue((self.work / row['folder'] / 'graph.json').is_file())
        self.assertEqual(self.engine.posted[0]['prompt']['fov'], 36.6)
        # a job that fails is an attempt all the same
        self.engine.status = 'error'
        generate.geometry(self.work, 'outfit', self.image, 36.6, 'models')
        self.assertEqual([row['state'] for row in self.ledger()], ['complete', 'failed'])

    def test_a_model_gets_five_attempts_earlier_ones_included(self):
        earlier = [{'attempt': k + 1, 'token': str(k), 'state': 'complete'} for k in range(3)]
        (self.work / generate.LEDGER).write_text(json.dumps({'maximumGeometryAttempts': 5, 'models': {'outfit': earlier, 'other': earlier * 2}}), encoding='utf-8')
        self.assertEqual(generate.geometry(self.work, 'outfit', self.image, 36.6, 'models')['attempt'], 4)
        self.assertEqual(generate.geometry(self.work, 'outfit', self.image, 36.6, 'models')['attempt'], 5)
        with self.assertRaises(ValueError) as refused:
            generate.geometry(self.work, 'outfit', self.image, 36.6, 'models')
        self.assertIn('5 geometry attempts', str(refused.exception))
        self.assertEqual((len(self.ledger()), len(self.engine.posted)), (5, 2))
        self.assertEqual(len(generate.attempts(self.work)['models']['other']), 6)  # another model's history is left as it is
        self.assertEqual(generate.attempts(self.work / 'nowhere'), {'maximumGeometryAttempts': 5, 'models': {}})

    def test_another_spelling_of_a_model_has_no_history_of_its_own(self):
        earlier = [{'attempt': k + 1, 'token': str(k), 'state': 'complete'} for k in range(5)]
        (self.work / generate.LEDGER).write_text(json.dumps({'maximumGeometryAttempts': 5, 'models': {'outfit': earlier}}), encoding='utf-8')
        before = (self.work / generate.LEDGER).read_bytes()
        for spelling in ('outfit/', './outfit', 'outfit\\', 'Outfit', 'outfit.', 'outfit/.', '../' + self.work.name + '/outfit', '.', ''):
            with self.subTest(spelling=spelling), self.assertRaises(ValueError) as refused:
                generate.geometry(self.work, spelling, self.image, 36.6, 'models')
            self.assertIn('not the name of a model folder', str(refused.exception))
        with self.assertRaises(ValueError):
            generate.export(self.work, 'outfit/', self.image, 1000)
        self.assertEqual(((self.work / generate.LEDGER).read_bytes(), self.engine.posted), (before, []))

    def test_a_ledger_write_cut_short_leaves_the_ledger_as_it_was(self):
        earlier = [{'attempt': 1, 'token': '0', 'state': 'complete'}]
        (self.work / generate.LEDGER).write_text(json.dumps({'maximumGeometryAttempts': 5, 'models': {'outfit': earlier, 'other': earlier}}), encoding='utf-8')
        before = (self.work / generate.LEDGER).read_bytes()
        with mock.patch.object(generate.common.os, 'replace', side_effect=OSError('cut short')), self.assertRaises(OSError):
            generate.geometry(self.work, 'outfit', self.image, 36.6, 'models')
        self.assertEqual(((self.work / generate.LEDGER).read_bytes(), self.engine.posted), (before, []))  # and nothing was posted uncounted
        self.assertEqual([path.name for path in self.work.glob(generate.LEDGER + '.*') if path.suffix != '.lock'], [])
        self.assertEqual(generate.geometry(self.work, 'outfit', self.image, 36.6, 'models')['attempt'], 2)
        self.assertEqual(len(generate.attempts(self.work)['models']['other']), 1)

    def test_an_attempt_with_no_known_outcome_blocks_the_next(self):
        self.engine.lost = True
        with self.assertRaises(ConnectionError):
            generate.geometry(self.work, 'outfit', self.image, 36.6, 'models')
        row = self.ledger()[0]
        self.assertEqual((row['state'], row['error']), ('submitted', 'the engine went away'))
        self.engine.lost = False
        with self.assertRaises(ValueError) as refused:
            generate.geometry(self.work, 'outfit', self.image, 36.6, 'models')
        self.assertIn('reconcile', str(refused.exception))
        self.assertEqual(len(self.engine.posted), 1)
        generate.appearance(self.work, 'outfit', self.image, 36.6, self.image, 'models')  # only geometry is blocked

    def test_a_second_attempt_started_while_one_is_under_way_is_refused(self):
        (self.work / 'other').mkdir()
        refused = []

        def second():  # as another command would, while the first attempt's job runs: the same model, and another
            for model in ('outfit', 'other'):
                try:
                    generate.geometry(self.work, model, self.image, 36.6, 'models')
                except ValueError as error:
                    refused.append(str(error))
        (self.work / 'other' / 'reference').mkdir()
        brief.seal(document(), self.work / 'other' / 'reference')
        brief.register(self.work / 'other' / 'reference', self.image)
        self.engine.meanwhile = second
        self.assertEqual(generate.geometry(self.work, 'outfit', self.image, 36.6, 'models')['attempt'], 1)
        self.assertEqual(len(refused), 2)
        self.assertTrue(all('under way' in message for message in refused))
        # one job posted and one attempt on record: neither read the ledger the first was still writing
        self.assertEqual(len(self.engine.posted), 1)
        self.assertEqual(list(generate.attempts(self.work)['models']), ['outfit'])
        self.assertEqual([row['state'] for row in self.ledger()], ['complete'])
        self.assertFalse((self.work / 'other' / generate.JOBS).exists())
        # the ledger is let go when the attempt ends, however it ends
        self.assertEqual(generate.geometry(self.work, 'other', self.image, 36.6, 'models')['attempt'], 1)
        self.engine.lost = True
        with self.assertRaises(ConnectionError):
            generate.geometry(self.work, 'other', self.image, 36.6, 'models')
        self.engine.lost = False
        self.assertEqual(generate.geometry(self.work, 'outfit', self.image, 36.6, 'models')['attempt'], 2)

    def test_a_busy_engine_is_left_alone_and_nothing_is_counted(self):
        self.engine.busy = True
        calls = (lambda: generate.calibrate(self.work, 'outfit', self.image, 'models'),
                 lambda: generate.geometry(self.work, 'outfit', self.image, 36.6, 'models'),
                 lambda: generate.appearance(self.work, 'outfit', self.image, 36.6, self.image, 'models'),
                 lambda: generate.export(self.work, 'outfit', self.image, 12000))
        for call in calls:
            with self.assertRaises(ValueError):
                call()
        self.assertEqual(self.engine.posted, [])
        self.assertFalse((self.work / generate.LEDGER).exists())
        self.assertFalse((self.work / 'outfit' / generate.JOBS).exists())
        # a job the engine refuses is not waited for
        self.engine.busy, self.engine.refuse = False, True
        with self.assertRaises(ValueError):
            generate.calibrate(self.work, 'outfit', self.image, 'models')

    def test_appearance_and_export_are_not_counted(self):
        shape = self.work / 'outfit' / 'shape.npz'
        shape.write_bytes(b'a saved shape')
        done = generate.appearance(self.work, 'outfit', self.image, 36.6, shape, 'models')
        self.assertEqual((done['stage'], done['shape']), ('appearance', {'path': str(shape), 'sha256': brief.digest(shape)}))
        self.assertEqual(self.engine.posted[0]['prompt']['shape']['sha256'], brief.digest(shape))
        with self.assertRaises(ValueError):
            generate.appearance(self.work, 'outfit', self.image, 36.6, self.work / 'outfit' / 'missing.npz', 'models')
        mesh = self.work / 'outfit' / 'mesh.glb'
        mesh.write_bytes(b'a generated mesh')
        plain = generate.export(self.work, 'outfit', mesh, 12000)
        self.assertEqual(plain['settings'], {'remeshResolution': 768, 'targetFaceCount': 12000})
        self.assertNotIn('image', plain)
        solid = generate.export(self.work, 'outfit', mesh, 12000, fill=0.5)
        self.assertEqual(solid['settings'], {'remeshResolution': 768, 'targetFaceCount': 12000, 'signMode': 'solid', 'fill': 0.5})
        self.assertEqual(Path(solid['folder']).name, 'export-2')
        self.assertEqual(self.engine.posted[-1]['prompt']['source'], {'path': str(mesh), 'sha256': brief.digest(mesh)})
        outside = self.work / 'elsewhere.glb'
        outside.write_bytes(b'another mesh')
        for given in ((outside, 12000), (mesh, 0), (mesh, 1.5)):  # not this model's mesh; not a number of faces
            with self.assertRaises(ValueError):
                generate.export(self.work, 'outfit', *given)
        self.assertFalse((self.work / generate.LEDGER).exists())
        with self.assertRaises(ValueError):  # no such model
            generate.export(self.work, 'nobody', mesh, 12000)

    def test_model_loaders_are_bound_to_the_hashes_on_record(self):
        mock.patch.stopall()  # the real `bound`, with headkit's loader helpers replaced
        name, recorded = next(iter(json.loads(generate.CHECKPOINTS.read_text(encoding='utf-8')).items()))
        with mock.patch.object(generate, 'model_choices', lambda graph: [('checkpoints', name)]), \
                mock.patch.object(generate, 'path_identity', lambda path: 'identity of ' + path.as_posix()), \
                mock.patch.object(generate, 'bind_loader_models', lambda graph, pins: {**graph, 'pins': len(pins)}):
            graph, pins = generate.bound({'a': 1}, self.work / 'models')
            self.assertEqual(graph, {'a': 1, 'pins': 1})
            self.assertEqual(pins, [{'category': 'checkpoints', 'name': name, 'sha256': recorded,
                                     'pathIdentity': 'identity of ' + (self.work / 'models' / 'checkpoints' / name).as_posix()}])
            with mock.patch.object(generate, 'model_choices', lambda graph: [('checkpoints', 'not-on-record.safetensors')]):
                with self.assertRaises(KeyError):  # a model headkit has no hash for is not loaded
                    generate.bound({'a': 1}, self.work / 'models')

    def test_an_output_named_as_a_path_is_not_written(self):
        self.engine.outputs = {'1': {'images': [{'filename': '../outside.png', 'subfolder': 's', 'type': 'output'}]}}
        with self.assertRaises(ValueError):
            generate.calibrate(self.work, 'outfit', self.image, 'models')
        self.assertFalse((self.work / 'outfit' / generate.JOBS / 'outside.png').exists())


if __name__ == '__main__':
    unittest.main()
