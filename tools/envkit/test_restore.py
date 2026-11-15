import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.envkit import restore


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup); self.root = Path(self.temporary.name)
        self.models = self.root / 'yard-game.json'
        self.models.write_text(json.dumps({'models': {'ek_a': {'source': 'meshy/models/a-1', 'height': 1.0}, 'ek_b': {'source': 'meshy/models/b-1', 'height': 1.0}}}), encoding='utf-8')

    def archive(self, name, files, bases=(), held=None):
        """An archive folder: `files` {path: bytes} in its manifest, the objects of `held` (default: all of them) in its store."""
        folder = self.root / name; manifest = {'bases': list(bases), 'files': {}}
        for path, data in files.items():
            digest = hashlib.sha256(data).hexdigest(); manifest['files'][path] = {'sha256': digest, 'size': len(data)}
            if held is None or path in held:
                (folder / 'objects' / digest[:2]).mkdir(parents=True, exist_ok=True); (folder / 'objects' / digest[:2] / digest).write_bytes(data)
        folder.mkdir(exist_ok=True); (folder / 'archive-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        return folder

    def test_a_models_whole_source_folder_comes_back_checked_and_nothing_else(self):
        """The older sets' props were restored for a look at their shape, model and colour map alone, and their
        conversion failed at the first missing map (2026-11-15)."""
        files = {'output/envkit/yard/meshy/models/a-1/model.glb': b'glb', 'output/envkit/yard/meshy/models/a-1/texture_0_normal.png': b'normal',
                 'output/envkit/yard/meshy/models/a-1/deeper/notes.txt': b'no source file', 'output/envkit/yard/meshy/models/b-1/model.glb': b'other',
                 'output/envkit/yard/meshy/ledger.json': b'{}'}
        archive = self.archive('kept', files); output = self.root / 'mine'
        told = restore.sources(archive, output, self.models, ['ek_a'])
        self.assertEqual(sorted(path.relative_to(output).as_posix() for path in output.rglob('*') if path.is_file()),
                         ['output/envkit/yard/meshy/models/a-1/model.glb', 'output/envkit/yard/meshy/models/a-1/texture_0_normal.png'])
        self.assertEqual(told, {'ek_a': {'source': 'meshy/models/a-1', 'files': 2, 'roots': [str((output / 'output/envkit/yard').resolve())]}})
        self.assertEqual(restore.sources(archive, output, self.models, ['ek_a'])['ek_a']['files'], 0)  # what is there and right is left
        (output / 'output/envkit/yard/meshy/models/a-1/model.glb').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'not the archive'):  # and what is there and differs is never written over
            restore.sources(archive, output, self.models, ['ek_a'])
        self.assertEqual((output / 'output/envkit/yard/meshy/models/a-1/model.glb').read_bytes(), b'changed')

    def test_objects_are_found_in_an_archives_bases_and_an_archive_is_only_read(self):
        files = {'output/envkit/yard/meshy/models/a-1/model.glb': b'glb', 'output/envkit/yard/meshy/models/a-1/texture_0_base_color.png': b'colour'}
        self.archive('older', files, held={'output/envkit/yard/meshy/models/a-1/model.glb'})
        archive = self.archive('newer', files, bases=['../older'], held={'output/envkit/yard/meshy/models/a-1/texture_0_base_color.png'})
        self.assertEqual(restore.sources(archive, self.root / 'mine', self.models, ['ek_a'])['ek_a']['files'], 2)
        for said, arguments in (('only read', (archive, archive / 'restored', self.models, ['ek_a'])), ('No such model', (archive, self.root / 'two', self.models, ['ek_c'])),
                                ('holds no source folder', (archive, self.root / 'two', self.models, ['ek_b'])), ('No archive-manifest', (self.root, self.root / 'two', self.models, ['ek_a']))):
            with self.assertRaisesRegex(ValueError, said):
                restore.sources(*arguments)
        self.assertFalse((archive / 'restored').exists()); self.assertFalse((self.root / 'older' / 'restored').exists()); self.assertFalse((self.root / 'older' / 'output').exists()); self.assertFalse((self.root / 'two').exists())
        lone = self.archive('lone', files, held=set())  # a manifest whose objects are gone
        with self.assertRaisesRegex(ValueError, 'hold no object'):
            restore.sources(lone, self.root / 'three', self.models, ['ek_a'])


if __name__ == '__main__':
    unittest.main()
