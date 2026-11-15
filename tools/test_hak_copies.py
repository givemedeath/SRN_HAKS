"""A pack's copies list (`tools/SrnHaks.Common.psm1`, `Get-SrnHakCopies`): what the build reads and what it refuses."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
PS = shutil.which('pwsh')
READ = ("Import-Module ./tools/SrnHaks.Common.psm1 -Force; "
        "try { Get-SrnHakCopies -Hak (Get-SrnConfiguration).HakList[0] | ConvertTo-Json -Compress } catch { 'REFUSED ' + $_.Exception.Message }")


class HakCopiesTests(unittest.TestCase):
    """A stand-in repository with one pack that holds `kept.plt` and `other.tga`."""

    def setUp(self):
        if not PS:
            self.skipTest('pwsh unavailable')
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.repo = Path(holder.name)
        (self.repo / 'tools').mkdir()
        for module in ('SrnHaks.Common.psm1', 'SrnTools.psm1'):
            shutil.copyfile(TOOLS / module, self.repo / 'tools' / module)
        (self.repo / 'srn_x').mkdir()
        (self.repo / 'srn_x' / 'kept.plt').write_bytes(b'tint')
        (self.repo / 'srn_x' / 'other.tga').write_bytes(b'map')
        self.entry = {'Name': 'srn_x', 'Path': './srn_x/', 'CompileModels': False, 'Copies': './docs/copies.json'}
        (self.repo / 'docs').mkdir()

    def read(self, copies=None, entry=None, **fields):
        """What `Get-SrnHakCopies` gives for the pack: its map, or the words it refuses the list with."""
        (self.repo / 'hakbuilder.json').write_text(json.dumps({'HakList': [self.entry if entry is None else entry]}), encoding='utf-8')
        if copies is not None or fields:
            document = {'schemaVersion': 1, 'kind': 'srn-hak-copies', 'pack': 'srn_x', 'copies': copies, **fields}
            (self.repo / 'docs' / 'copies.json').write_text(json.dumps({key: value for key, value in document.items() if value is not None}), encoding='utf-8')
        done = subprocess.run([PS, '-NoProfile', '-Command', READ], cwd=self.repo, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(done.returncode, 0, done.stderr)
        out = done.stdout.strip()
        return out if out.startswith('REFUSED') else json.loads(out)

    def test_a_list_names_each_copy_with_the_file_kept_in_name_order(self):
        self.assertEqual(self.read({'b_copy.plt': 'kept.plt', 'a_copy.plt': 'kept.plt'}), {'a_copy.plt': 'kept.plt', 'b_copy.plt': 'kept.plt'})
        self.assertEqual(self.read({}), {})
        self.assertEqual(self.read(entry={key: value for key, value in self.entry.items() if key != 'Copies'}), {})  # a pack without a list has no copies

    def test_a_copy_must_be_left_out_of_the_folder_and_the_file_kept_must_be_in_it(self):
        self.assertIn('holds no gone.plt', self.read({'a_copy.plt': 'gone.plt'}))
        self.assertIn('holds no a_copy.plt', self.read({'a_copy.plt': 'kept.plt', 'b_copy.plt': 'a_copy.plt'}))  # a copy of a copy
        (self.repo / 'srn_x' / 'a_copy.plt').write_bytes(b'tint')
        self.assertIn('srn_x holds a_copy.plt', self.read({'a_copy.plt': 'kept.plt'}))

    def test_names_are_resource_file_names_of_one_type(self):
        self.assertIn('a file of another type', self.read({'a_copy.plt': 'other.tga'}))
        for name in ('A_copy.plt', '../a_copy.plt', 'sub/a_copy.plt', 'a_name_of_17_chars.plt', 'a_copy'):
            self.assertIn('is no resource file name', self.read({name: 'kept.plt'}), name)
        self.assertIn('is no resource file name', self.read({'a_copy.plt': '../kept.plt'}))

    def test_a_document_that_is_no_copies_list_is_refused_by_name(self):
        refused = "is no copies list of 'srn_x'"
        self.assertIn(refused, self.read({'a_copy.plt': 'kept.plt'}, kind='other'))
        self.assertIn(refused, self.read({'a_copy.plt': 'kept.plt'}, pack='srn_y'))
        self.assertIn(refused, self.read({'a_copy.plt': 'kept.plt'}, schemaVersion=2))
        self.assertIn(refused, self.read({'a_copy.plt': 'kept.plt'}, kind=None))  # a field left out
        self.assertIn(refused, self.read(['a_copy.plt']))
        self.assertIn(refused, self.read('a_copy.plt'))
        (self.repo / 'docs' / 'copies.json').write_text('[1, 2]', encoding='utf-8')
        self.assertIn(refused, self.read())
        (self.repo / 'docs' / 'copies.json').write_text('{not json', encoding='utf-8')
        self.assertIn(refused, self.read())
        (self.repo / 'docs' / 'copies.json').unlink()
        self.assertIn('names a copies list that does not exist', self.read())


if __name__ == '__main__':
    unittest.main()
