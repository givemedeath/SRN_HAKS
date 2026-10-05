from pathlib import Path
import tempfile
import unittest
import numpy as np
from head_workflow import pin,read,write_fresh
from prepare_fixture_rig import prepare
from retarget import nodes,transforms
from derived_profiles import emit_ascii_skeleton


class FixtureRigTests(unittest.TestCase):
    def test_parent_first_copy_preserves_original_node_text_and_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'pmg0.mdl'
            text='newmodel pmg0\nsetsupermodel pmg0 a_ba\nbeginmodelgeom pmg0\nnode dummy head_g\n parent pmg0\n position 0 0 1.75\n orientation 1 0 0 0\nendnode\nnode dummy pmg0\n parent null\n position 0 0 0\n orientation 0 0 0 0\nendnode\nendmodelgeom pmg0\ndonemodel pmg0\n'
            source.write_text(text);prepare(source,root/'candidate')
            returned=(root/'candidate/ascii/pmg0.mdl').read_text()
            self.assertLess(returned.index('node dummy pmg0'),returned.index('node dummy head_g'))
            self.assertEqual(source.read_text(),text)
            before=transforms(nodes(text));after=transforms(nodes(returned))
            for name in before:np.testing.assert_array_equal(before[name],after[name])
            self.assertTrue(read(root/'candidate/serialization.json')['nodeTextPreserved'])
            emitted=emit_ascii_skeleton('pmg0','a_ba',nodes(text))
            self.assertLess(emitted.index('node dummy pmg0'),emitted.index('node dummy head_g'))

    def test_missing_parent_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'pmg0.mdl'
            source.write_text('newmodel pmg0\nbeginmodelgeom pmg0\nnode dummy head_g\n parent absent\nendnode\nnode dummy pmg0\n parent null\nendnode\nendmodelgeom pmg0\n')
            with self.assertRaisesRegex(ValueError,'Missing rig parent'):prepare(source,root/'candidate')
            self.assertFalse((root/'candidate').exists())


if __name__=='__main__':unittest.main()
