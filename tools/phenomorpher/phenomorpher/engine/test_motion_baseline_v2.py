"""Motion baselines resolve the published library chain the way the client does."""
import json
from pathlib import Path
import tempfile
import unittest

from . import test_runtime_release as fixtures
from .motion_baseline_v2 import load, max_frame_difference
from .runtime_release import adopt


class MotionBaselineTests(unittest.TestCase):
    def test_adopted_chain_reproduces_the_carrier_motion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); plan = fixtures.AdoptionTests().release(root)
            before = load(root, root/plan['baseContract']['path'], root/plan['stock']['path'], ['pfx0'])['pfx0']
            frames_before = {(c, t): before.frames(c, t) for c in before.owners for t in before.times(c)}
            adopt(root, root/'plan.json', root/'staged')
            for path in (root/'staged/files').rglob('*'):
                if path.is_file():
                    (root/path.relative_to(root/'staged/files')).write_bytes(path.read_bytes())
            for row in json.loads((root/'staged/remove.json').read_text()):
                (root/row['path']).unlink()
            after = load(root, root/'staged/game-ready-assets.json', root/plan['stock']['path'], ['pfx0'])['pfx0']
            self.assertEqual(after.chain, ['pfx0', 'srn_an_xf', 'a_fa', 'a_ba'])
            self.assertEqual(after.summary()['origins']['srn_an_xf']['role'], 'animation-library')
            self.assertEqual(set(after.owners), set(before.owners))
            worst = max(max_frame_difference(frames_before[(c, t)], after.frames(c, t)) for c, t in frames_before)
            # Inherited clips may differ within the inheritance rule (0.05 degrees, about 8.7e-4 in a frame matrix).
            self.assertLess(worst, 8.8e-4)

    def test_unknown_roots_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); plan = fixtures.AdoptionTests().release(root)
            with self.assertRaisesRegex(ValueError, 'not a published rig'):
                load(root, root/plan['baseContract']['path'], root/plan['stock']['path'], ['pzz0'])


if __name__ == '__main__':
    unittest.main()
