"""A later tool edit must not invalidate the implementation that made selected maps."""
from pathlib import Path
import tempfile
import unittest
from bake_body_materials import archive_tool_inputs
from stage_stock_part import sha


class FrozenImplementation(unittest.TestCase):
    def test_future_helper_edits_leave_original_archive_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); helper=root/'helper.py'; geometry=root/'source.glb';output=root/'output'
            helper.write_text('print("first")\n');geometry.write_bytes(b'unchanged source');output.mkdir()
            original=sha(helper)
            frozen,origins=archive_tool_inputs({str(helper):original,str(geometry):sha(geometry)},output)
            archive=Path(origins[str(helper.resolve())]['archive'])
            self.assertEqual(sha(archive),original)
            self.assertNotIn(str(helper),frozen)
            self.assertIn(str(geometry),frozen)
            helper.write_text('print("next part improvement")\n')
            self.assertNotEqual(sha(helper),original)
            self.assertTrue(all(sha(Path(path))==pin for path,pin in frozen.items()))
            geometry.write_bytes(b'actual geometry changed')
            self.assertFalse(all(sha(Path(path))==pin for path,pin in frozen.items()))


if __name__=='__main__': unittest.main()
