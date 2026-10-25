"""Opt-in launcher hash cache: hits only on an unchanged stamp, never stores racy files, shares one file safely."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from launch_hash_cache import HashCache
from shared_toolchain import sha
from shared_tools import write_json


def aged(path, seconds=60):
    stat = os.stat(path); os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns - int(seconds * 1e9)))


class HashCacheTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup); self.root = Path(self.folder.name)

    def test_unchanged_stamp_hits_and_any_change_misses(self):
        source = self.root / 'input.bin'; source.write_bytes(b'one'); aged(source)
        cache = HashCache(self.root / 'cache.sqlite'); self.assertEqual(cache.sha(source), sha(source)); cache.flush()
        self.assertEqual(cache.sha(source), sha(source)); self.assertEqual((cache.hits, cache.misses), (1, 1))
        source.write_bytes(b'two'); aged(source)  # same size, new bytes, new mtime
        self.assertEqual(cache.sha(source), sha(source)); self.assertEqual(cache.misses, 2); cache.close()
        reopened = HashCache(self.root / 'cache.sqlite'); self.assertEqual(reopened.sha(source), sha(source))
        self.assertEqual(reopened.hits, 1); reopened.close()

    def test_recently_modified_files_are_hashed_but_never_stored(self):
        source = self.root / 'fresh.bin'; source.write_bytes(b'still being written')
        cache = HashCache(self.root / 'cache.sqlite'); cache.sha(source); cache.flush(); cache.sha(source)
        self.assertEqual((cache.hits, cache.misses, cache.recentRefusals), (0, 2, 2)); cache.close()
        report = cache.report(); self.assertEqual(report['recentRefusals'], 2); self.assertIn('mtime_ns', report['trusts'])

    def test_concurrent_launches_share_one_cache_file(self):
        files = []
        for i in range(40):
            path = self.root / f'f{i}.bin'; path.write_bytes(bytes([i]) * 1000); aged(path); files.append(str(path))
        listing = self.root / 'files.json'; listing.write_text(json.dumps(files))
        script = ('import json,sys;sys.path.insert(0,sys.argv[3]);from launch_hash_cache import HashCache;'
                  'c=HashCache(sys.argv[1]);[c.sha(p) for p in json.load(open(sys.argv[2]))];c.close()')
        here = str(Path(__file__).resolve().parent)
        workers = [subprocess.Popen([sys.executable, '-c', script, str(self.root / 'cache.sqlite'), str(listing), here]) for _ in range(4)]
        self.assertEqual([w.wait(timeout=120) for w in workers], [0] * 4)
        cache = HashCache(self.root / 'cache.sqlite')
        self.assertEqual([cache.sha(p) for p in files], [sha(p) for p in files]); self.assertEqual(cache.hits, 40); cache.close()

    def test_stamp_is_text_so_large_windows_file_ids_fit(self):
        from types import SimpleNamespace
        from launch_hash_cache import stamp
        self.assertEqual(stamp(SimpleNamespace(st_size=1, st_mtime_ns=2, st_ino=2**64 - 1, st_dev=2**63)), f'1:2:{2**64 - 1}:{2**63}')

    def test_helper_snapshots_link_one_verified_read_only_store_entry(self):
        import launch_shared_tool as launch
        helper = self.root / 'helper.py'; helper.write_text('print(1)'); aged(helper); digest = sha(helper)
        cache = HashCache(self.root / 'cache' / 'cache.sqlite')
        for name in ('first', 'second'):
            output = self.root / name; output.mkdir()
            row = launch.helper_snapshots([helper], {str(helper.resolve()): digest}, output, cache)[str(helper)]
            self.assertEqual(row['sha256'], digest); self.assertTrue(os.path.samefile(row['snapshot'], row['store']))
            self.assertEqual(Path(row['snapshot']).read_text(), 'print(1)')
        self.assertEqual(len(list((self.root / 'cache' / 'helper-store').rglob('*.py'))), 1)
        self.assertFalse(os.access(row['store'], os.W_OK)); cache.close()
        helper.write_text('print(2)')  # a helper that no longer matches its frozen digest is refused
        other = HashCache(self.root / 'c2.sqlite'); (self.root / 'third').mkdir(); self.addCleanup(other.close)
        with self.assertRaisesRegex(ValueError, 'Helper changed'):
            launch.helper_snapshots([helper], {str(helper.resolve()): '0' * 64}, self.root / 'third', other)

    def test_launcher_uses_the_cache_only_when_enabled_and_still_detects_drift(self):
        config = self.root / 'binding.json'; source = self.root / 'input.txt'; source.write_text('parent'); aged(source)
        write_json(config, {'schemaVersion': 2, 'kind': 'phenotype-shared-toolchain', 'requiredTools': ['python'],
                            'runtimes': {'python': {'path': sys.executable, 'sha256': sha(sys.executable)}}}, fresh=True)
        paths = self.root / 'paths.json'; write_json(paths, [str(source)], fresh=True)
        launcher = Path(__file__).with_name('launch_shared_tool.py'); cache = self.root / 'cache.sqlite'
        def run(name, code, env):
            result = subprocess.run([sys.executable, '-B', str(launcher), '--toolchain', str(config), '--migration-smoke', '--tool',
                                     'python', '--output', str(self.root / name), '--input-path-list', str(paths), '--', '-c', code],
                                    capture_output=True, env=env)
            return result.returncode, json.loads((self.root / name / 'launch.json').read_text())
        plain = dict(os.environ); plain.pop('SRN_LAUNCH_HASH_CACHE', None); cached = dict(plain, SRN_LAUNCH_HASH_CACHE=str(cache))
        code, receipt = run('plain', 'print("ok")', plain); self.assertEqual(code, 0); self.assertIsNone(receipt['hashCache'])
        code, first = run('first', 'print("ok")', cached); self.assertEqual(code, 0); self.assertGreater(first['hashCache']['misses'], 0)
        code, second = run('second', 'print("ok")', cached); self.assertEqual(code, 0)
        self.assertGreater(second['hashCache']['hits'], 0); same = lambda r: {k: v for k, v in r['frozenInputs'].items() if not k.endswith('verified-inputs.json')}  # per-launch snapshot
        self.assertEqual(same(second), same(first))
        # A write during the run changes the stamp: the post-run check misses, rehashes and invalidates the launch.
        drift = 'from pathlib import Path;Path(' + repr(str(source)) + ').write_text("changed")'
        code, changed = run('drift', drift, cached); self.assertEqual(code, 1); self.assertFalse(changed['inputsUnchanged'])


if __name__ == '__main__':
    unittest.main()
