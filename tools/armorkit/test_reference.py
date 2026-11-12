"""A reference image is made from its outfit's brief, and what takes an image further asks where it came from."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import brief, reference
from .test_brief import SITEGUARD, document


class Engine:
    """The image engine, replaced: it records what it is asked and returns one image per job."""

    def __init__(self):
        self.asked = []

    def patches(self):
        def compile_design(prompt, references, seed, batch, prefix, *, profile):
            self.asked.append({'prompt': prompt, 'references': references, 'seed': seed, 'batch': batch, 'prefix': prefix, 'profile': profile})
            return {'graph': len(self.asked)}

        def dispatch(client, graph, token, record, *, deadline):
            record['promptId'] = 'job-%d' % graph['graph']
            return {'outputs': {'9': {'images': [{'filename': f'{k}.png', 'subfolder': 's', 'type': 'output'} for k in range(self.asked[-1]['batch'])]}}}
        return (mock.patch.object(reference.comfy, 'Client', lambda url: ('client', url)),
                mock.patch.object(reference.design, 'compile_design', compile_design),
                mock.patch.object(reference.design, 'dispatch', dispatch),
                mock.patch.object(reference, 'upload', lambda url, path, name: 'staged/' + name),
                mock.patch.object(reference, 'fetch', lambda url, row: ('image ' + row['filename'] + ' of job %d' % len(self.asked)).encode()))


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()  # the long spelling: a temporary folder can come as a short one
        self.given = document()
        self.path = self.root / 'brief.json'
        self.path.write_text(json.dumps(self.given), encoding='utf-8')
        self.engine = Engine()
        for patch in self.engine.patches():
            patch.start()
            self.addCleanup(patch.stop)

    def test_an_image_is_made_from_the_briefs_prompt_and_registered_with_it(self):
        folder = self.root / 'outfit' / 'reference-1'
        earlier = self.root / 'earlier.png'
        earlier.write_bytes(b'an earlier image')
        images = reference.generate(self.path, folder, 11, batch=2, references=[earlier])
        self.assertEqual([path.relative_to(folder).as_posix() for path in images], ['run-1/image-0.png', 'run-1/image-1.png'])
        asked = self.engine.asked[0]
        self.assertEqual(asked['prompt'], brief.prompt(self.given))  # the prompt is the brief's, never handed in
        self.assertEqual((asked['seed'], asked['batch'], len(asked['references'])), (11, 2, 1))
        self.assertEqual((folder / 'PROMPT.txt').read_text(encoding='utf-8'), brief.prompt(self.given) + '\n')
        self.assertEqual((folder / 'run-1' / 'prompt.txt').read_text(encoding='utf-8'), brief.prompt(self.given) + '\n')
        record = json.loads((folder / 'run-1' / 'record.json').read_text(encoding='utf-8'))
        self.assertEqual((record['model'], record['seed'], record['images'], record['references']), ('test-outfit', 11, 2, ['earlier.png']))
        # what takes an image further finds the brief it came from
        for image in images:
            self.assertEqual(brief.admit(image, self.root), (self.given, folder))
        # a second job is a second run, and the first run's images stay registered
        again = reference.generate(self.path, folder, 12)
        self.assertEqual(again[0].relative_to(folder).as_posix(), 'run-2/image-0.png')
        self.assertEqual(brief.admit(images[0], self.root)[1], folder)

    def test_no_image_is_asked_for_without_a_brief_that_holds(self):
        alike = copy.deepcopy(self.given)
        alike['materials'][2]['colour'] = [135, 135, 140]  # the plates nearly the cloth's grey
        broken = {**self.given, 'materials': []}
        for number, given in enumerate((alike, broken)):
            self.path.write_text(json.dumps(given), encoding='utf-8')
            with self.assertRaises(ValueError):
                reference.generate(self.path, self.root / f'refused-{number}', 11)
            self.assertFalse((self.root / f'refused-{number}').exists())
        with self.assertRaises(OSError):  # no brief at all
            reference.generate(self.root / 'none.json', self.root / 'refused', 11)
        with self.assertRaises(ValueError):  # a reference that is not there
            reference.generate(self.path, self.root / 'refused', 11, references=[self.root / 'missing.png'])
        self.assertEqual(self.engine.asked, [])

    def test_an_image_that_no_sealed_folder_lists_is_not_taken_further(self):
        folder = self.root / 'reference-1'
        image = reference.generate(self.path, folder, 11)[0]
        stray = folder / 'run-1' / 'dropped-in.png'
        stray.write_bytes(b'not made from the prompt')
        with self.assertRaises(ValueError) as refused:
            brief.admit(stray, self.root)
        self.assertIn('does not come from a brief', str(refused.exception))
        with self.assertRaises(ValueError):
            brief.admit(self.root / 'missing.png', self.root)
        # an image derived from a registered one (a clay, a calibrated copy) is registered by what made it
        brief.register(folder, stray)
        self.assertEqual(brief.admit(stray, self.root)[1], folder)
        with self.assertRaises(ValueError):
            brief.register(folder, self.root / 'missing.png')
        # a prompt edited by hand after sealing no longer stands for its brief: nothing from the folder is let through
        (folder / 'PROMPT.txt').write_text('An outfit in two greys.', encoding='utf-8')
        for call in (lambda: brief.admit(image, self.root), lambda: brief.sealed(folder), lambda: brief.register(folder, image)):
            with self.assertRaises(ValueError):
                call()
        with self.assertRaises(ValueError):  # a folder that was never sealed
            brief.sealed(self.root)
        with self.assertRaises(ValueError):
            brief.register(self.root, image)

    def test_a_sealed_folder_keeps_to_one_brief(self):
        folder = self.root / 'reference-1'
        self.assertEqual(brief.seal(self.given, folder), brief.prompt(self.given))
        brief.seal(self.given, folder)  # again, with nothing made yet
        image = folder / 'image.png'
        image.write_bytes(b'made')
        brief.register(folder, image)
        brief.seal(self.given, folder)  # the same brief: its image stays registered
        self.assertEqual(brief.admit(image, self.root)[1], folder)
        other = copy.deepcopy(self.given)
        other['materials'][0]['wears'] = 'the shirt alone.'
        with self.assertRaises(ValueError):  # another brief's prompt would stand beside this one's images
            brief.seal(other, folder)
        self.assertEqual(brief.sealed(folder)[0], self.given)

    def test_a_new_folder_is_sealed_only_with_the_current_construction_rules(self):
        plain = {key: value for key, value in self.given.items() if key != 'construction'}
        plain['prompt'] = plain['prompt'].replace(brief.BUILT + '\n\n', '')
        with self.assertRaises(ValueError):
            brief.seal(plain, self.root / 'new')
        self.assertFalse((self.root / 'new').exists())
        folder = self.root / 'old'  # a folder sealed before the rules keeps its prompt, and its images are still taken further
        folder.mkdir()
        brief._seal(folder, plain, False)
        (folder / brief.PROMPT).write_text(brief.prompt(plain) + '\n', encoding='utf-8')
        self.assertEqual(brief.sealed(folder), (plain, brief.prompt(plain)))

    def test_an_outfit_made_before_its_brief_is_taken_in_as_it_is(self):
        given = brief.load(SITEGUARD)
        folder = self.root / 'reference-old'
        folder.mkdir()
        with self.assertRaises(ValueError):  # its colours are too alike for a new prompt
            brief.seal(given, self.root / 'new')
        with self.assertRaises(ValueError):  # no prompt there
            brief.adopt(given, folder)
        (folder / 'PROMPT.txt').write_text('Another prompt.', encoding='utf-8')
        with self.assertRaises(ValueError):
            brief.adopt(given, folder)
        (folder / 'PROMPT.txt').write_text(brief.composed(given) + '\n', encoding='utf-8')
        unrecorded = copy.deepcopy(given)
        del unrecorded['materials'][0]['shown']
        with self.assertRaises(ValueError):  # the colours it shows are not on record
            brief.adopt(unrecorded, folder)
        brief.adopt(given, folder)
        self.assertEqual(brief.sealed(folder), (given, brief.composed(given)))
        image = folder / 'image.png'
        image.write_bytes(b'the image that exists')
        brief.register(folder, image)
        self.assertEqual(brief.admit(image, self.root)[0]['model'], 'corpsec-siteguard-male')


if __name__ == '__main__':
    unittest.main()
