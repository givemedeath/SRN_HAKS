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

    def test_head_only_migration_receipt_honors_allowed_tool_runs(self):
        receipt=self.root/'head_migration.json'
        smoke_file=self.root/'smoke.json';smoke_file.write_text('{}')
        data={'kind':'phenotype-shared-tool-migration','scope':'head-tools','smokeChecksPassed':True,
              'allowedTools':['python','blender'],
              'frozenSmokeFiles':[{'path':str(smoke_file),'sha256':sha(smoke_file)}],
              'toolchain':{'path':str(self.path),'sha256':sha(self.path)}}
        receipt.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'Head-only migration does not cover this tool'):
            load(self.path,receipt)
        with self.assertRaisesRegex(ValueError,'Head-only migration does not cover this tool'):
            load(self.path,receipt,required=['armory'])
        self.assertEqual(load(self.path,receipt,required=['python','blender']),self.data)
        self.assertEqual(load(self.path,receipt,required=['python']),self.data)

    def measurement_receipt(self):
        smoke=self.root/'measurement-smoke.json';smoke.write_text('{}',encoding='utf-8')
        data={'kind':'phenotype-shared-tool-migration','scope':'measurement-tools','smokeChecksPassed':True,
              'allowedTools':['python'],'frozenSmokeFiles':[{'path':str(smoke),'sha256':sha(smoke)}],
              'toolchain':{'path':str(self.path),'sha256':sha(self.path)}}
        receipt=self.root/'measurement-migration.json';receipt.write_text(json.dumps(data),encoding='utf-8')
        return receipt,data,smoke

    def test_measurement_only_migration_rejects_every_uncovered_tool_and_default_inventory(self):
        receipt,_,_=self.measurement_receipt()
        self.assertEqual(load(self.path,receipt,required=['python']),self.data)
        for required in (None,[],['blender'],['armory'],['python','blender']):
            with self.subTest(required=required),self.assertRaisesRegex(ValueError,'Measurement-only migration does not cover'):
                load(self.path,receipt,required=required)

    def test_measurement_scope_requires_exact_allowlist_frozen_smoke_and_unchanged_bytes(self):
        receipt,original,smoke=self.measurement_receipt()
        for changes in ({'allowedTools':['python','blender']},{'allowedTools':[]},{'allowedTools':'python'},{'frozenSmokeFiles':[]}):
            receipt.write_text(json.dumps({**original,**changes}),encoding='utf-8')
            with self.subTest(changes=changes),self.assertRaisesRegex(ValueError,'Python-only scope and frozen smokes'):
                load(self.path,receipt,required=['python'])
        receipt.write_text(json.dumps(original),encoding='utf-8');smoke.write_text('changed',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Measurement migration smoke changed'):
            load(self.path,receipt,required=['python'])


if __name__=='__main__':unittest.main()

