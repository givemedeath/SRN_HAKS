"""Armorkit takes cleanmodels from the shared tool root, at the version and bytes the lock names."""
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import toolchain

LOCK = toolchain.REPO / 'tools' / 'shared-tools.lock.json'


class ToolchainTests(unittest.TestCase):
    def entry(self):
        return json.loads(LOCK.read_text(encoding='utf-8-sig'))['tools'][toolchain.CLEANMODELS]

    def test_the_lock_pins_one_cleanmodels_release_in_the_shared_root(self):
        entry = self.entry()
        self.assertEqual((entry['origin'], entry['version']), ('shared', '4.17.5'))
        for platform, binary in entry['platforms'].items():
            self.assertTrue(binary['relativePath'].startswith(f'cleanmodels/v{entry["version"]}/{platform}/'))
            self.assertRegex(binary['sha256'], r'^[0-9a-f]{64}$')
        self.assertIn(entry['version'], entry['installation'])
        self.assertIsNone(re.search(r'[A-Za-z]:[\\/]', json.dumps(entry)))  # no machine path in the portable lock

    def test_cleanmodels_is_resolved_by_the_shared_helper_with_the_given_root(self):
        from tools import shared_tools
        with mock.patch.object(shared_tools, 'resolve_tool', return_value={'path': 'x'}) as resolve:
            self.assertEqual(toolchain.cleanmodels(root='elsewhere'), {'path': 'x'})
        resolve.assert_called_once_with('cleanmodels', toolchain.REPO, 'elsewhere')

    def test_changed_or_missing_bytes_are_refused(self):
        from tools import shared_tools
        entry = self.entry()['platforms'].get(shared_tools.platform_key())
        if entry is None:
            self.skipTest('cleanmodels is not pinned for this platform')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaisesRegex(ValueError, 'Missing tool'):
                toolchain.cleanmodels(root=root)
            target = root / entry['relativePath']
            target.parent.mkdir(parents=True)
            target.write_bytes(b'not the release')
            self.assertNotEqual(hashlib.sha256(target.read_bytes()).hexdigest(), entry['sha256'])
            with self.assertRaisesRegex(ValueError, 'Tool binary changed'):
                toolchain.cleanmodels(root=root)


if __name__ == '__main__':
    unittest.main()
