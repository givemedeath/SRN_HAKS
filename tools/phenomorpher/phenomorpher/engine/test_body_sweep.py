"""body_sweep: requested motion clips must be measurable, or the gap is recorded."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import body_sweep as bs

MODELS = {'pfd0': {'parent': 'a_fa', 'clips': {}}, 'pfh0': {'parent': 'a_fa', 'clips': {}},
          'a_fa': {'parent': 'a_ba', 'clips': {'pause1': {}}}, 'a_ba': {'parent': 'null', 'clips': {'walk': {}}},
          'pmd0': {'parent': 'a_ba', 'clips': {'tlknorm': {}}}, 'pmh0': {'parent': 'a_ba', 'clips': {}}}


class BodySweepClipTests(unittest.TestCase):
    def test_unresolved_clips_name_the_target_or_donor_chain(self):
        self.assertEqual(bs.unresolved_clips(MODELS, ['pfd0'], ['pause1', 'walk']), [])
        self.assertEqual(bs.unresolved_clips(MODELS, ['pfd0'], ['wlak']), ['pfd0:wlak', 'pfh0:wlak'])
        # A clip only the target owns is missing from its donor.
        self.assertEqual(bs.unresolved_clips(MODELS, ['pmd0'], ['tlknorm']), ['pmh0:tlknorm'])

    def test_an_explicit_unresolvable_clip_fails_before_any_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest = root/'contract.json'; output = root/'out'
            manifest.write_text(json.dumps({'version': '1.1.0', 'targets': [{'modelPrefix': 'pfd0'}, {'modelPrefix': 'pfh0'}],
                                            'resources': []}))
            with patch.object(bs, 'consumed', return_value=[]), patch.object(bs.lib, 'stock_files', return_value=({}, {})), \
                    patch.object(bs.lib, 'release_models', return_value=(MODELS, None)), patch.object(bs, 'body') as body:
                with self.assertRaisesRegex(ValueError, 'Requested clip cannot be resolved: pfd0:wlak, pfh0:wlak'):
                    bs.sweep(root, manifest, output, ['pfd0'], stock_manifest=root/'stock.json', with_motion=True, clips=['wlak'])
                body.assert_not_called()
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
