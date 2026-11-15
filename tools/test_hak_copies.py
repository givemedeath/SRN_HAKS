"""A pack's copies list (`tools/SrnHaks.Common.psm1`, `Get-SrnHakCopies`): what the build reads and what it refuses."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
PS = shutil.which('pwsh')
# One process reads every case of a test: a line each, the map or the words the list is refused with.
READ = ("Import-Module ./tools/SrnHaks.Common.psm1 -Force; "
        "foreach ($hak in @(Get-Content -Raw ./cases.json | ConvertFrom-Json)) { "
        "try { Get-SrnHakCopies -Hak $hak | ConvertTo-Json -Compress } catch { 'REFUSED ' + ($_.Exception.Message -replace '\\s+', ' ') } }")


class HakCopiesTests(unittest.TestCase):
    """A stand-in repository: pack `srn_x` holds `kept.plt` and `other.tga`, pack `srn_y` also the copy `a_copy.plt`."""

    def setUp(self):
        if not PS:
            self.skipTest('pwsh unavailable')
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.repo = Path(holder.name)
        (self.repo / 'tools').mkdir()
        for module in ('SrnHaks.Common.psm1', 'SrnTools.psm1'):
            shutil.copyfile(TOOLS / module, self.repo / 'tools' / module)
        for pack, names in (('srn_x', ('kept.plt', 'other.tga')), ('srn_y', ('kept.plt', 'a_copy.plt'))):
            (self.repo / pack).mkdir()
            for name in names:
                (self.repo / pack / name).write_bytes(b'image')
        (self.repo / 'docs').mkdir()
        self.cases = []

    def entry(self, text=None, pack='srn_x'):
        """A pack's `hakbuilder.json` entry naming a list of the given text; no list file with None."""
        path = f'./docs/list-{len(self.cases)}.json'
        if text is not None:
            (self.repo / path).write_text(text, encoding='utf-8')
        self.cases.append({'Name': pack, 'Path': f'./{pack}/', 'CompileModels': False, 'Copies': path})
        return len(self.cases) - 1

    def listing(self, copies, pack='srn_x', named=None, **fields):
        """An entry of `pack` whose list holds `copies` and names the pack (`named` where it names another); a field
        given as None is left out of the document."""
        document = {'schemaVersion': 1, 'kind': 'srn-hak-copies', 'pack': named or pack, 'copies': copies, **fields}
        return self.entry(json.dumps({key: value for key, value in document.items() if value is not None}), pack)

    def read(self):
        """What `Get-SrnHakCopies` gives for each case, in order: its map, or the words it refuses the list with."""
        (self.repo / 'cases.json').write_text(json.dumps(self.cases), encoding='utf-8')
        done = subprocess.run([PS, '-NoProfile', '-Command', READ], cwd=self.repo, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = [line for line in done.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), len(self.cases), done.stdout)
        return [line if line.startswith('REFUSED') else json.loads(line) for line in lines]

    def test_a_list_names_each_copy_with_the_file_kept_in_name_order(self):
        self.listing({'b_copy.plt': 'kept.plt', 'a_copy.plt': 'kept.plt'})
        self.listing({})
        self.cases.append({'Name': 'srn_x', 'Path': './srn_x/', 'CompileModels': False})  # a pack without a list has no copies
        both, none, without = self.read()
        self.assertEqual(list(both.items()), [('a_copy.plt', 'kept.plt'), ('b_copy.plt', 'kept.plt')])
        self.assertEqual((none, without), ({}, {}))

    def test_a_copy_must_be_left_out_of_the_folder_and_the_file_kept_must_be_in_it(self):
        self.listing({'a_copy.plt': 'gone.plt'})
        self.listing({'a_copy.plt': 'kept.plt', 'b_copy.plt': 'a_copy.plt'})  # a copy of a copy
        self.listing({'a_copy.plt': 'kept.plt'}, pack='srn_y')
        gone, chained, held = self.read()
        self.assertIn('holds no gone.plt', gone)
        self.assertIn('holds no a_copy.plt', chained)
        self.assertIn('srn_y holds a_copy.plt', held)

    def test_names_are_resource_file_names_of_one_type(self):
        names = ('A_copy.plt', '../a_copy.plt', 'sub/a_copy.plt', 'a_name_of_17_chars.plt', 'a_copy', 'a_copy.plt\n')
        for name in names:
            self.listing({name: 'kept.plt'})
        self.listing({'a_copy.plt': '../kept.plt'})
        self.listing({'a_copy.plt': 'kept.plt\n'})
        self.listing({'a_copy.plt': 'other.tga'})
        *refused, other = self.read()
        for name, said in zip((*names, '../kept.plt', 'kept.plt\n'), refused, strict=True):
            self.assertIn('is no resource file name', said, name)
        self.assertIn('a file of another type', other)

    def test_a_document_that_is_no_copies_list_is_refused_by_name(self):
        good = {'a_copy.plt': 'kept.plt'}
        for fields in ({'kind': 'other'}, {'named': 'srn_y'}, {'schemaVersion': 2}, {'schemaVersion': '1'}, {'kind': None}):  # None: the field is left out
            self.listing(good, **fields)
        self.listing(None)
        self.listing(['a_copy.plt'])
        self.listing('a_copy.plt')
        self.entry('[1, 2]')
        self.entry('{not json')
        missing = self.entry()
        said = self.read()
        for index, words in enumerate(said):
            self.assertIn('names a copies list that does not exist' if index == missing else "is no copies list of 'srn_x'", words, index)


if __name__ == '__main__':
    unittest.main()
