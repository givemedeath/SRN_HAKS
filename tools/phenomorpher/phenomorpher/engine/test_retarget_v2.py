"""retarget_v2: one Fit-fitted carrier chain over a_fa/a_ba shared by the Fit and Large roots."""
import json
from pathlib import Path
import tempfile
import unittest

from . import anim_library as lib
from .retarget_v2 import retarget

GEOMETRY = """beginmodelgeom {m}
node dummy {m}
  parent NULL
endnode
node dummy rootdummy
  parent {m}
  position 0 0 1
endnode
node dummy torso_g
  parent rootdummy
  position 0 0 0
endnode
node dummy belt_g1
  parent rootdummy
endnode
node dummy neck_g
  parent torso_g
  position 0 0 0.5
endnode
endmodelgeom {m}
"""
CLIP = """newanim {clip} {m}
  length 1
  transtime 0.25
  animroot rootdummy
  event 0.5 hit
  node dummy {m}
    parent NULL
  endnode
  node dummy torso_g
    parent rootdummy
    positionkey 2
      0 0 0 0
      1 0 0 0.1
    orientationkey 2
      0 0 0 1 0
      1 0 0 1 0.2
  endnode
doneanim {clip} {m}
"""


def stock(m, parent, clip=None):
    return (f'newmodel {m}\nsetsupermodel {m} {parent}\nclassification CHARACTER\nsetanimationscale 1\n'
            + GEOMETRY.format(m=m) + (CLIP.format(clip=clip, m=m) if clip else '') + f'donemodel {m}\n')


def converted(root, prefix, height, torso, neck):
    folder = root/prefix; folder.mkdir()
    (folder/'conversion.json').write_text(json.dumps({'modelPrefix': prefix, 'height': height, 'bindPoseNormalization': True,
                                                      'jointWorldNwn': {'torso_g': [0, 0, torso], 'neck_g': [0, 0, neck]}}))
    return folder


class RetargetV2Tests(unittest.TestCase):
    def fixture(self, root):
        baseline = root/'baseline'; (baseline/'ascii').mkdir(parents=True)
        (baseline/'ascii/pfh0.mdl').write_text(stock('pfh0', 'a_fa'))
        (baseline/'ascii/a_fa.mdl').write_text(stock('a_fa', 'a_ba', 'pause1'))
        (baseline/'ascii/a_ba.mdl').write_text(stock('a_ba', 'NULL', 'walk'))
        # The phenotype-2 stock chain exists but must never be the motion source.
        (baseline/'ascii/a_fa2.mdl').write_text(stock('a_fa2', 'a_ba', 'pause1'))
        (baseline/'baseline.json').write_text(json.dumps({'animations': {'a_fa': {'supermodel': 'a_ba'}, 'a_ba': {'supermodel': 'null'},
                                                                         'a_fa2': {'supermodel': 'a_ba'}}}))
        return baseline, converted(root, 'pfd0', 1.3, .65, 1.), converted(root, 'pfd2', 1.5, .7, 1.1)

    def test_fit_and_large_roots_share_one_fit_fitted_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); baseline, fit, large = self.fixture(root)
            receipt = retarget(fit, baseline, large)
            self.assertEqual((receipt['topCarrier'], [c['source'] for c in receipt['carriers']]), ('sr_afd_0', ['a_fa', 'a_ba']))
            fit_root = lib.load_model(fit/'ascii/pfd0.mdl'); large_root = lib.load_model(large/'ascii/pfd2.mdl')
            self.assertEqual((fit_root['parent'], large_root['parent']), ('sr_afd_0', 'sr_afd_0'))
            self.assertFalse((large/'ascii/sr_afd_0.mdl').exists())
            carrier = lib.load_model(fit/'ascii/sr_afd_0.mdl')
            self.assertEqual(carrier['parent'], 'sr_afd_1')
            # Position keys follow the Fit body (scale 0.65), not the Large one.
            keys = carrier['clips']['pause1']['nodes']['torso_g']['controls'][8]['values']
            self.assertAlmostEqual(float(keys[1][2] - keys[0][2]), .065, places=6)
            self.assertTrue(json.loads((fit/'retarget-v2.json').read_text())['fitLargeShareMotion'])

    def test_large_motion_source_and_mismatched_bodies_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); baseline, fit, large = self.fixture(root)
            with self.assertRaisesRegex(RuntimeError, 'must be the Fit'):
                retarget(large, baseline)
            other = converted(root, 'pmd2', 1.5, .7, 1.1)
            (baseline/'ascii/pmh0.mdl').write_text(stock('pmh0', 'a_ba'))
            with self.assertRaisesRegex(RuntimeError, 'share race and gender'):
                retarget(fit, baseline, other)


if __name__ == '__main__':
    unittest.main()
