"""What a build worked out from a model is read back by the next build of the same model, and by no other."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from tools.envkit import cache


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()); self.made = 0
        patches = [mock.patch.object(cache, 'ROOT', self.root), mock.patch.object(cache, 'LEAST', 2), mock.patch.object(cache, 'KEPT', 2), mock.patch.dict('os.environ')]
        for one in patches:
            one.start(); self.addCleanup(one.stop)
        import os; os.environ.pop('ENVKIT_NO_CACHE', None)

    def make(self, value):
        def made():
            self.made += 1; return np.full((2, 3), value), np.array(value + 1)
        return made

    def test_the_same_inputs_are_read_back_and_others_are_made(self):
        points = np.arange(6.0).reshape(2, 3)
        first = cache.arrays('kind', (points, 4, 'a'), self.make(1.0), faces=5); again = cache.arrays('kind', (points.copy(), 4, 'a'), self.make(9.0), faces=5)
        np.testing.assert_array_equal(first[0], again[0]); self.assertEqual((int(again[1]), self.made), (2, 1))
        cache.arrays('kind', (points + 1, 4, 'a'), self.make(3.0), faces=5); cache.arrays('kind', (points, 5, 'a'), self.make(3.0), faces=5)
        cache.arrays('kind', (points.astype(np.float32), 4, 'a'), self.make(3.0), faces=5); self.assertEqual(self.made, 4)
        self.assertEqual(len(list((self.root / 'kind').glob('*.npz'))), 2)  # the oldest go

    def test_a_file_is_hashed_by_its_bytes_and_a_small_model_is_never_kept(self):
        code = self.root / 'code.py'; code.write_text('one'); before = cache.key(code); code.write_text('two'); self.assertNotEqual(before, cache.key(code))
        cache.arrays('kind', (1,), self.make(1.0), faces=1); cache.arrays('kind', (1,), self.make(1.0), faces=1); self.assertEqual(self.made, 2)
        self.assertFalse((self.root / 'kind').exists())

    def test_it_is_switched_off_and_a_half_written_one_is_made_again(self):
        import os
        cache.arrays('kind', (1,), self.make(1.0), faces=5); kept = next((self.root / 'kind').glob('*.npz')); kept.write_bytes(b'half')
        self.assertEqual(float(cache.arrays('kind', (1,), self.make(2.0), faces=5)[0][0, 0]), 2.0)
        os.environ['ENVKIT_NO_CACHE'] = '1'
        self.assertEqual(float(cache.arrays('kind', (1,), self.make(7.0), faces=5)[0][0, 0]), 7.0)


if __name__ == '__main__':
    unittest.main()
