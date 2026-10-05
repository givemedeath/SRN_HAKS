"""Preview sampling and provenance checks without importing Blender."""
from pathlib import Path
import tempfile
import unittest
import numpy as np

from pose_preview_bridge import pose, freeze_helpers, verify_helpers
from target_contract import sha


ROOT='''newmodel pmh0
setsupermodel pmh0 a_ba
beginmodelgeom pmh0
node dummy pmh0
 parent NULL
endnode
node dummy rootdummy
 parent pmh0
 position 2 3 4
endnode
node dummy joint
 parent rootdummy
 position 1 0 0
endnode
endmodelgeom pmh0
donemodel pmh0
'''


def animation(position, rotation='orientation 0 0 1 1.5707963267948966'):
    return '''newmodel a_ba
setsupermodel a_ba NULL
beginmodelgeom a_ba
node dummy a_ba
parent NULL
endnode
endmodelgeom a_ba
newanim pause1 a_ba
 length 1
 transtime .1
 node dummy rootdummy
 parent a_ba
 '''+rotation+'''
 endnode
 node dummy joint
 parent rootdummy
 '''+position+'''
 endnode
doneanim pause1 a_ba
donemodel a_ba
'''


class PreviewBridgeTests(unittest.TestCase):
    def fixtures(self, directory, text):
        root=Path(directory);(root/'pmh0.mdl').write_text(ROOT)
        (root/'a_ba.mdl').write_text(text)
        return root

    def test_default_human_lookup_has_equal_count_and_endlist_poses(self):
        with tempfile.TemporaryDirectory() as directory:
            root=self.fixtures(directory,animation('positionkey 2\n 0 1 0 0\n 1 3 0 0'))
            counted,receipt=pose(root,'pmh0','PAUSE1',.5)
            (root/'a_ba.mdl').write_text(animation('positionkey\n 0 1 0 0\n 1 3 0 0\n endlist'))
            listed,_=pose(root,'pmh0','pause1',.5)
            for node in counted:
                np.testing.assert_array_equal(counted[node],listed[node])
            np.testing.assert_allclose(listed['joint'][:3,3],[2,5,4],atol=1e-12)
            self.assertEqual(receipt['clip'],'PAUSE1')
            self.assertEqual(receipt['length'],1.)
            self.assertEqual(receipt['sampler'],'rig_pose_audit.sample')
            self.assertEqual(len(receipt['sourceInheritance']),2)

    def test_static_animation_positions_and_rotations_override_bind(self):
        with tempfile.TemporaryDirectory() as directory:
            root=self.fixtures(directory,animation('position 3 0 0'))
            sampled,_=pose(root,'pmh0','pause1',0)
            np.testing.assert_allclose(sampled['joint'][:3,3],[2,6,4],atol=1e-12)

    def test_stock_fallback_pins_every_used_inheritance_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);candidate=root/'candidate';stock=root/'stock'
            candidate.mkdir();stock.mkdir();(candidate/'pmh0.mdl').write_text(ROOT)
            (stock/'a_ba.mdl').write_text(animation('position 1 0 0'))
            _,receipt=pose(candidate,'pmh0','pause1',.5,stock)
            self.assertEqual(receipt['file'],str((stock/'a_ba.mdl').resolve()))
            self.assertEqual(receipt['sourceInheritance'][0]['sha256'],sha(candidate/'pmh0.mdl'))
            self.assertEqual(receipt['sourceInheritance'][1]['sha256'],sha(stock/'a_ba.mdl'))

    def test_out_of_range_cycle_missing_and_bezier_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=self.fixtures(directory,animation('position 1 0 0'))
            with self.assertRaisesRegex(RuntimeError,'outside'):
                pose(root,'pmh0','pause1',1.01)
            with self.assertRaisesRegex(RuntimeError,'unavailable'):
                pose(root,'pmh0','missing',0)
            (root/'a_ba.mdl').write_text(animation('positionbezierkey\n'
                ' 0 1 2 3 0 0 0 0 0 0\n 1 4 5 6 0 0 0 0 0 0\n endlist'))
            with self.assertRaisesRegex(RuntimeError,'Bezier'):
                pose(root,'pmh0','pause1',.5)
            (root/'a_ba.mdl').write_text('newmodel a_ba\nsetsupermodel a_ba pmh0\n')
            with self.assertRaisesRegex(RuntimeError,'cycle'):
                pose(root,'pmh0','missing',0)

    def test_helper_snapshots_are_recoverable_and_detect_source_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);additional=root/'temporary-preview-code.py'
            additional.write_text('original')
            manifest=freeze_helpers(root,[additional])
            verify_helpers(manifest)
            pin=manifest[str(additional.resolve())]
            self.assertEqual(Path(pin['snapshot']).read_text(),'original')
            additional.write_text('changed')
            with self.assertRaisesRegex(ValueError,'changed during execution'):
                verify_helpers(manifest)
            self.assertEqual(Path(pin['snapshot']).read_text(),'original')


if __name__=='__main__':unittest.main()
