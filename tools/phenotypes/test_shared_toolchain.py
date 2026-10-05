"""Shared tool drift, retiring paths and unbound migration receipts fail closed."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from shared_toolchain import load, sha


class SharedToolchainTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.addons=self.root/'addons';self.addons.mkdir()
        (self.addons/'addon.py').write_bytes(b'pinned addon')
        tools={}
        for name in ('armory','blender','python'):
            path=self.root/(name+'.exe');path.write_bytes(name.encode())
            tools[name]={'path':str(path),'sha256':sha(path)}
        self.data={'schemaVersion':1,'kind':'phenotype-shared-toolchain',
            'retiringWorktree':str(self.root/'retiring'),'tools':tools,
            'addons':{'root':str(self.addons),'files':{'addon.py':sha(self.addons/'addon.py')}}}
        self.path=self.root/'tools.json';self.save()

    def tearDown(self):self.tmp.cleanup()

    def save(self):self.path.write_text(json.dumps(self.data))

    def test_loads_pinned_sources_and_ignores_only_derived_python_cache(self):
        (self.addons/'__pycache__').mkdir();(self.addons/'__pycache__/addon.pyc').write_bytes(b'cache')
        self.assertEqual(load(self.path)['tools'],self.data['tools'])

    def test_changed_binary_and_added_or_changed_addon_source_rejected(self):
        path=Path(self.data['tools']['armory']['path']);path.write_bytes(b'drift')
        with self.assertRaisesRegex(ValueError,'binary changed'):load(self.path)
        self.data['tools']['armory']['sha256']=sha(path);self.save()
        extra=self.addons/'new.py';extra.write_bytes(b'new')
        with self.assertRaisesRegex(ValueError,'inventory changed'):load(self.path)
        extra.unlink();(self.addons/'addon.py').write_bytes(b'drift')
        with self.assertRaisesRegex(ValueError,'bytes changed'):load(self.path)

    def test_rejects_retiring_tool_and_addon_roots(self):
        self.data['retiringWorktree']=str(self.root);self.save()
        with self.assertRaisesRegex(ValueError,'retiring worktree'):load(self.path)
        self.data['retiringWorktree']=str(self.addons);self.save()
        with self.assertRaisesRegex(ValueError,'Active addons'):load(self.path)

    def test_requires_passed_migration_associated_with_exact_configuration(self):
        receipt=self.root/'migration.json'
        data={'kind':'phenotype-shared-tool-migration','smokeChecksPassed':True,
              'toolchain':{'path':str(self.path),'sha256':sha(self.path)}}
        receipt.write_text(json.dumps(data));self.assertEqual(load(self.path,receipt),self.data)
        data['toolchain']['sha256']='wrong';receipt.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'does not bind'):load(self.path,receipt)
        data['smokeChecksPassed']=False;receipt.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'Passed shared tool migration'):load(self.path,receipt)


if __name__=='__main__':unittest.main()
