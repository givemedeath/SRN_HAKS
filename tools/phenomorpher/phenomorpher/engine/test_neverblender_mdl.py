"""Blender + Neverblender MDL compile/decompile: receipts, caching, fail-closed audits and declared inputs."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from . import neverblender_mdl as nvb
from .test_anim_library import native
from ..inputs import consumed

ROOT_AT_ORIGIN = 'newmodel m\nsetsupermodel m NULL\nbeginmodelgeom m\nnode dummy m\n  parent NULL\nendnode\nendmodelgeom m\ndonemodel m\n'
ROOT_OFFSET = ROOT_AT_ORIGIN.replace('  parent NULL\n', '  parent NULL\n  position 0 0 -0.05\n')


def toolchain(root):
    """A stand-in Blender executable and add-on tree with the version markers toolchain() reads."""
    blender = root/'blender.exe'; blender.write_bytes(b'blender')
    addon = root/'addons/neverblender'; (addon/'cleanmodels').mkdir(parents=True)
    (addon/'__init__.py').write_text("bl_info = {'version': (4, 5, 1)}\n")
    (addon/'cleanmodels/__init__.py').write_text('PORTED_FROM = "v4.10.0"\n')
    (addon/'__pycache__').mkdir(); (addon/'__pycache__/x.pyc').write_bytes(b'cache')
    return blender, addon


def fake_run(binary):
    """Worker stand-in: writes `binary` for every compile job, as the real worker reports it."""
    calls = []
    def run(tools, jobs, timeout=600):
        calls.append([Path(j['input']).name for j in jobs]); rows = []
        for job in jobs:
            Path(job['output']).write_bytes(binary)
            rows.append({'input': str(job['input']), 'output': str(job['output']), 'sourceSha256': nvb.digest(Path(job['input']).read_bytes()),
                         'outputSha256': nvb.digest(binary), 'bytes': len(binary), 'warnings': [], 'seconds': 0.0})
        return {'blenderVersion': '5.2.1 LTS', 'results': rows}
    return run, calls


class CompileFolderTests(unittest.TestCase):
    def test_receipt_caching_and_fresh_compiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); blender, addon = toolchain(root); converted = root/'c'; (converted/'ascii').mkdir(parents=True)
            (converted/'ascii/m.mdl').write_text(ROOT_AT_ORIGIN)
            run, calls = fake_run(native('m', 'null', [('m', '', {})]))
            rerun = root/'d'; (rerun/'ascii').mkdir(parents=True); shutil.copyfile(converted/'ascii/m.mdl', rerun/'ascii/m.mdl')
            with patch.object(nvb, 'run', side_effect=run):
                first = nvb.compile_folder(blender, addon, converted)
                again = nvb.compile_folder(blender, addon, rerun, cache=converted)
                in_place = nvb.compile_folder(blender, addon, converted)  # the folder's own receipt is never a cache
                (rerun/'ascii/m.mdl').write_text(ROOT_AT_ORIGIN.replace('donemodel m', 'donemodel m\n'))
                changed = nvb.compile_folder(blender, addon, rerun, cache=converted)
                with self.assertRaisesRegex(ValueError, 'earlier converted folder'):
                    nvb.compile_folder(blender, addon, converted, cache=converted)
            self.assertEqual(calls, [['m.mdl'], [], ['m.mdl'], ['m.mdl']])
            self.assertEqual((first['compiled'], again['reused'], in_place['compiled'], changed['compiled']), (1, 1, 1, 1))
            self.assertEqual((rerun/'resources/m.mdl').read_bytes(), (converted/'resources/m.mdl').read_bytes())
            receipt = json.loads((converted/'native-compile.json').read_text())
            self.assertEqual((receipt['executionMode'], receipt['complete'], receipt['compiler']['neverblender']['version']),
                             ('neverblender-cleanmodels', True, '4.5.1'))
            self.assertTrue(receipt['models'][0]['audit']['passed'])
            self.assertNotIn('files', receipt['compiler'])
            # Another compiler build never reuses a binary.
            (addon/'nvb_extra.py').write_text('# changed\n')
            with patch.object(nvb, 'run', side_effect=run):
                self.assertEqual(nvb.compile_folder(blender, addon, converted)['compiled'], 1)

    def test_several_folders_compile_in_one_worker_run_with_their_own_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); blender, addon = toolchain(root); folders = []
            for name in ('a', 'b'):
                folder = root/name; (folder/'ascii').mkdir(parents=True); (folder/'ascii/m.mdl').write_text(ROOT_AT_ORIGIN)
                (folder/'resources').mkdir(); (folder/'resources'/f'{name}.plt').write_bytes(name.encode()); folders.append(folder)
            run, calls = fake_run(native('m', 'null', [('m', '', {})]))
            with patch.object(nvb, 'run', side_effect=run):
                receipts = nvb.compile_folders(blender, addon, folders)
                alone = root/'alone'; shutil.copytree(folders[0], alone); (alone/'native-compile.json').unlink(); (alone/'resources/m.mdl').unlink()
                single = nvb.compile_folder(blender, addon, alone)
                copies = []
                for i, folder in enumerate(folders):  # same contents, no outputs: reuse each folder's own binary
                    copy = root/f'copy{i}'; shutil.copytree(folder, copy); (copy/'native-compile.json').unlink(); (copy/'resources/m.mdl').unlink()
                    copies.append(copy)
                cached = nvb.compile_folders(blender, addon, copies, caches=folders)
            self.assertEqual(calls[0], ['m.mdl', 'm.mdl'])  # one worker run for both folders
            self.assertEqual([r['compiled'] for r in receipts], [1, 1]);self.assertEqual([r['reused'] for r in cached], [1, 1]);self.assertEqual(calls[2], [])
            # Each folder looks up only its own files, exactly as compiling it alone would.
            self.assertEqual([sorted(r['lookupHashes']) for r in receipts], [['ascii/m.mdl', 'resources/a.plt'], ['ascii/m.mdl', 'resources/b.plt']])
            self.assertEqual(single['lookupHashes'], receipts[0]['lookupHashes'])
            for folder in folders:self.assertTrue((folder/'resources/m.mdl').is_file() and (folder/'native-compile.json').is_file())
            # One bad folder publishes nothing anywhere.
            bad = root/'bad'; (bad/'ascii').mkdir(parents=True); (bad/'ascii/m.mdl').write_text(ROOT_OFFSET); good = root/'good'
            (good/'ascii').mkdir(parents=True); (good/'ascii/m.mdl').write_text(ROOT_AT_ORIGIN)
            with patch.object(nvb, 'run', side_effect=run), self.assertRaisesRegex(RuntimeError, 'model-root node'):
                nvb.compile_folders(blender, addon, [good, bad])
            for folder in (good, bad):
                self.assertEqual(list((folder/'resources').iterdir()), []);self.assertFalse((folder/'native-compile.json').exists())

    def test_a_dropped_root_transform_fails_and_publishes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); blender, addon = toolchain(root); converted = root/'c'; (converted/'ascii').mkdir(parents=True)
            (converted/'ascii/m.mdl').write_text(ROOT_OFFSET)
            run, _ = fake_run(native('m', 'null', [('m', '', {})]))  # cleanmodels writes no root controllers
            with patch.object(nvb, 'run', side_effect=run), self.assertRaisesRegex(RuntimeError, 'model-root node'):
                nvb.compile_folder(blender, addon, converted)
            self.assertEqual(list((converted/'resources').iterdir()), [])
            self.assertFalse((converted/'native-compile.json').exists())

    def test_worker_outputs_must_be_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); out = root/'x.mdl'; out.write_bytes(b'old')
            with self.assertRaises(FileExistsError):
                nvb.run({}, [{'op': 'compile', 'input': root/'a.mdl', 'output': out, 'dirs': []}])


class DeclaredInputTests(unittest.TestCase):
    def test_compile_declares_blender_addon_sources_and_lookup_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); blender, addon = toolchain(root); converted = root/'c'; (converted/'ascii').mkdir(parents=True)
            (converted/'ascii/m.mdl').write_text(ROOT_AT_ORIGIN); extra = root/'stock'; extra.mkdir()
            (extra/'a_fa.mdl').write_bytes(b'x'); (extra/'notes.txt').write_text('ignored')
            files = consumed(['mdl-compile', '--blender', str(blender), '--neverblender', str(addon), '--converted', str(converted),
                              '--resource-dir', str(extra)])
            names = {p.relative_to(root.resolve()).as_posix() for p in files}
            self.assertEqual(names, {'blender.exe', 'addons/neverblender/__init__.py', 'addons/neverblender/cleanmodels/__init__.py',
                                     'c/ascii/m.mdl', 'stock/a_fa.mdl'})

    def test_a_managed_rerun_leaves_every_declared_input_unchanged(self):
        """The launcher re-hashes declared inputs after the run; compile outputs must not be among them."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); blender, addon = toolchain(root)
            for name in ('c', 'd'):
                (root/name/'ascii').mkdir(parents=True); (root/name/'ascii/m.mdl').write_text(ROOT_AT_ORIGIN)
            (root/'c/ascii/n.mdl').write_text(ROOT_AT_ORIGIN)  # the stand-in compiler writes model m for every job
            run, calls = fake_run(native('m', 'null', [('m', '', {})]))
            base = ['mdl-compile', '--blender', str(blender), '--neverblender', str(addon)]
            with patch.object(nvb, 'run', side_effect=run):
                nvb.compile_folder(blender, addon, root/'c')
                for argv, cache in ((base + ['--converted', str(root/'c')], None),
                                    (base + ['--converted', str(root/'d'), '--cache', str(root/'c')], root/'c')):
                    files = consumed(argv); pinned = {p: nvb.digest(p.read_bytes()) for p in files}
                    nvb.compile_folder(blender, addon, Path(argv[argv.index('--converted') + 1]), cache=cache)
                    with self.subTest(cache=cache):
                        self.assertEqual({p: nvb.digest(p.read_bytes()) for p in files}, pinned)
            # d's lookups differ from c's (no n.mdl), so nothing is reused: caching stays conservative.
            self.assertEqual(calls, [['m.mdl', 'n.mdl'], ['m.mdl', 'n.mdl'], ['m.mdl']])
            names = {p.relative_to(root.resolve()).as_posix() for p in files}
            self.assertTrue({'c/native-compile.json', 'c/resources/m.mdl'} <= names)
            self.assertNotIn('c/resources/n.mdl', names)  # not a source of d, and not in d's lookup folders

    def test_spellings_argparse_could_resolve_differently_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest = root/'m.json'; manifest.write_text(json.dumps({'resources': []}))
            base = ['downsample-textures', '--root', str(root), '--output', str(root/'o')]
            self.assertEqual(consumed(base + ['--manifest', str(manifest)]), {manifest.resolve()})
            for extra, message in ((['--manifest', str(manifest), '--manifest', str(root/'other.json')], 'more than once'),
                                   ([f'--manifest={manifest}'], 'not --name=value')):
                with self.subTest(message), self.assertRaisesRegex(ValueError, message):
                    consumed(base + extra)

    def test_the_cli_refuses_abbreviated_options(self):
        from ..cli import main
        with self.assertRaises(SystemExit), patch('sys.stderr'):
            main(['downsample-textures', '--ro', 'r', '--manifest', 'm', '--output', 'o'])


@unittest.skipUnless(os.environ.get('SRN_BLENDER') and os.environ.get('SRN_NEVERBLENDER'),
                     'Set SRN_BLENDER and SRN_NEVERBLENDER to run the installed Blender + Neverblender smoke')
class InstalledNeverblenderSmoke(unittest.TestCase):
    def test_round_trip_through_the_installed_addon(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); converted = root/'c'; (converted/'ascii').mkdir(parents=True)
            (converted/'ascii/m.mdl').write_text(ROOT_AT_ORIGIN)
            receipt = nvb.compile_folder(os.environ['SRN_BLENDER'], os.environ['SRN_NEVERBLENDER'], converted)
            binary = converted/'resources/m.mdl'
            self.assertEqual(binary.read_bytes()[:4], b'\0\0\0\0'); self.assertTrue(receipt['models'][0]['audit']['passed'])
            shutil.copyfile(binary, root/'m.mdl')
            _, report = nvb.decompile_files(os.environ['SRN_BLENDER'], os.environ['SRN_NEVERBLENDER'], [(root/'m.mdl', root/'m.txt')])
            self.assertIn('newmodel m', (root/'m.txt').read_text(encoding='latin-1')); self.assertEqual(len(report['results']), 1)


if __name__ == '__main__':
    unittest.main()
