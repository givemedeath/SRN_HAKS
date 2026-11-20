"""Textures enlarged by the upscaling model: what is sent, what is kept, and what a build takes from it."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

from . import enlarge, material
from .test_material import fake_compress


def doubling(sent):
    """Stands in for the shared ComfyUI: the staged picture doubled, pixel for pixel, where a job leaves its output."""
    def execute(client, local, bindings, graph, receipt, sources, output, base, batch, runtime, queue=None):
        with Image.open(sources['reference-0.png']) as picture:
            sent.append(picture.size); picture.resize((picture.width * 2, picture.height * 2), Image.NEAREST).save(Path(output) / f'{base}-b0.png')
    return execute


class EnlargeTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup); self.root = Path(folder.name); (self.root / 'srn_t_common').mkdir()
        pane = np.zeros((8, 8, 3), np.uint8); pane[:, :4] = (200, 220, 240); pane[0, 7] = (255, 0, 0)  # a lit half, and one red pixel in the top right corner
        Image.fromarray(pane).save(self.root / 'srn_t_common' / 'pane.tga'); Image.new('RGB', (8, 8)).save(self.root / 'srn_t_common' / 'wall.tga')
        self.spec = {'textures': {'pane': {'route': 'upscale', 'size': [64, 64], 'doubled': 2}, 'wall': {'route': 'upscale', 'size': [64, 64]}}}

    def test_a_picture_goes_with_itself_wrapped_round_it_and_comes_back_without(self):
        self.assertEqual(tuple(enlarge.wrapped(np.arange(12, dtype=np.uint8).reshape(2, 2, 3), 1)[0, 0]), (9, 10, 11))  # the far corner, wrapped round
        sent = []
        with mock.patch('tools.headkit.design._execute', side_effect=doubling(sent)):
            told = enlarge.enlarge(None, {}, None, self.root, self.spec, self.root / 'big', say=None)
            self.assertEqual((told, sent), ({'pane': 'enlarged'}, [(40, 40), (80, 80)]))  # twice, with the margin; the wall is not asked for
            made = enlarge.picture_of(self.root / 'big', 'pane')
            self.assertEqual((made.shape, tuple(made[0, 31]), tuple(made[20, 4]), tuple(made[20, 20])), ((32, 32, 3), (255, 0, 0), (200, 220, 240), (0, 0, 0)))
            self.assertEqual(enlarge.enlarge(None, {}, None, self.root, self.spec, self.root / 'big', say=None), {'pane': 'kept'}); self.assertEqual(len(sent), 2)
            with mock.patch('tools.envkit.reference.UPSCALER', 'another.pth'), self.assertRaisesRegex(ValueError, 'doubled 2 times by another.pth'):  # made by another model
                enlarge.enlarge(None, {}, None, self.root, self.spec, self.root / 'big', say=None)
            Image.new('RGB', (8, 8), (9, 9, 9)).save(self.root / 'srn_t_common' / 'pane.tga')  # the game draws another picture now
            with self.assertRaisesRegex(ValueError, 'was not made from the pane the game draws now'):
                enlarge.enlarge(None, {}, None, self.root, self.spec, self.root / 'big', say=None)
        self.assertEqual(json.loads((self.root / 'big' / 'pane.json').read_text())['doubled'], 2)
        with self.assertRaisesRegex(ValueError, 'doubled once or twice'):
            enlarge.enlarge(None, {}, None, self.root, {'textures': {'pane': {'doubled': 3}}}, self.root / 'other', say=None)

    def test_a_build_starts_a_doubled_texture_from_its_enlarged_picture(self):
        (self.root / 'big').mkdir(); Image.new('RGB', (32, 32), (0, 255, 0)).save(self.root / 'big' / 'pane.png')
        seen = {}

        def keep(image, target, mode, size, crunch, *, data):
            seen[Path(target).name] = np.asarray(image.convert('RGB')); return fake_compress(image, target, mode, size, crunch, data=data)
        material.build(self.spec, self.root, self.root, self.root / 'out', 'crunch', compress=keep, enlarged=self.root / 'big')
        self.assertEqual((tuple(seen['pane.dds'][8, 8]), tuple(seen['wall.dds'][8, 8])), ((0, 255, 0), (0, 0, 0)))
        with self.assertRaisesRegex(ValueError, 'pane is to be doubled and has no enlarged picture'):
            material.build(self.spec, self.root, self.root, self.root / 'none', 'crunch', compress=keep)
        with self.assertRaisesRegex(ValueError, 'Only an upscale starts from an enlarged picture'):
            material.make(np.zeros((8, 8, 3), np.uint8), {'route': 'master', 'size': [64, 64]}, {}, enlarged=np.zeros((8, 8, 3), np.uint8))


if __name__ == '__main__':
    unittest.main()
