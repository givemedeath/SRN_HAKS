from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from head_workflow import pin,write_fresh
from build_head_fixture import fixture_identity


class FixtureIdentityTests(unittest.TestCase):
    def test_derived_fixture_requires_same_native_rig_and_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/'source.mdl';source.write_text('protected rig')
            emitted=root/'emitted.mdl';emitted.write_text('parent-first rig')
            binary=root/'binary.mdl';binary.write_bytes(b'native')
            serialization=root/'serialization.json'
            write_fresh(serialization,{'source':pin(source),'output':pin(emitted),'nodeTextPreserved':True})
            audit=root/'audit.json'
            write_fresh(audit,{'passed':True,'maximumFrameError':2.5e-7,'serialization':pin(serialization),'binary':pin(binary)})
            target=root/'target.json';target.write_text('{}')
            body={'path':'body.json','sha256':'protected'}
            contract={'sex':'male','race':'troll','prefix':'pmg0','bodyManifest':body,'rig':pin(source),'runtimeScale':10/7}
            config={'target':pin(target),'bodyManifest':body,'rigAudit':pin(audit),'bodyDependencies':[pin(binary)]}
            with patch('build_head_fixture.validate_target',return_value=contract):
                self.assertEqual(fixture_identity(config),('pmg0',2,2,10/7))
                with self.assertRaisesRegex(ValueError,'omitted'):
                    fixture_identity({**config,'bodyDependencies':[]})
                with self.assertRaisesRegex(ValueError,'body target differs'):
                    fixture_identity({**config,'bodyManifest':{'path':'other'}})
                binary.write_bytes(b'changed')
                with self.assertRaises(ValueError):fixture_identity(config)

    def test_historical_human_default(self):
        self.assertEqual(fixture_identity({}),('pmh0',6,6,1.0))
        with self.assertRaises(ValueError):fixture_identity({'rigAudit':{'unexpected':True}})


if __name__=='__main__':unittest.main()
