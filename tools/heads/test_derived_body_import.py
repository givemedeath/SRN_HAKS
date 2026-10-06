import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from head_workflow import pin
from import_derived_body import import_body


class DerivedBodyImportTests(unittest.TestCase):
    def fixture(self, root):
        source = root / 'source'; source.mkdir()
        models = []
        for i in range(14):
            path = source / f'pmg0_part{i:02d}001.mdl'; path.write_bytes(bytes([i]))
            models.append({'name': path.name, 'binarySha256': pin(path)['sha256']})
        receipt = root / 'compile.json'
        receipt.write_text(json.dumps({'complete': True, 'models': models, 'materialResourceHashes': {}}))
        target = root / 'target.json'; target.write_text('{}')
        rig = root / 'pmg0.mdl'; rig.write_text('original rig')
        config = {'kind': 'srn-head-derived-body-import', 'targetId': 'troll-male-fit',
                  'sourceBranchCommit': 'test', 'target': pin(target), 'compileReceipt': pin(receipt),
                  'resources': str(source), 'inputs': [pin(p) for p in source.iterdir()] + [pin(rig)],
                  'extras': [{'source': pin(rig), 'destination': 'ascii/pmg0.mdl'}]}
        path = root / 'import.json'; path.write_text(json.dumps(config))
        return path, config, source

    def test_independent_copy_survives_source_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path, _, source = self.fixture(root)
            result = import_body(path, root / 'bank')
            for original in source.iterdir(): original.unlink()
            self.assertEqual(len(result['resources']), 14)
            self.assertEqual((root / 'bank/ascii/pmg0.mdl').read_text(), 'original rig')
            self.assertFalse(result['productionAccepted'])

    def test_changed_native_resource_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path, _, source = self.fixture(root)
            next(source.iterdir()).write_bytes(b'changed')
            with self.assertRaises(ValueError): import_body(path, root / 'bank')
            self.assertFalse((root / 'bank').exists())

    def test_duplicate_dependency_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path, config, _ = self.fixture(root)
            config['extras'] *= 2; path.write_text(json.dumps(config))
            with self.assertRaises(ValueError): import_body(path, root / 'bank')
            self.assertFalse((root / 'bank').exists())


if __name__ == '__main__': unittest.main()
