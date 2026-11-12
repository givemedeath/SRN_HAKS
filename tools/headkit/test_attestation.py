"""A shared ComfyUI another program started is usable only as the identity a person approved."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from headkit import attestation
from headkit.common import pin


def identity(root, *, files=None, sources=None, argv=None, mode='attested'):
    """An attested identity whose launch record really exists, as the node writes it."""
    record = Path(root)/'user/headkit/headkit-attested-launch.json'; record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps({'kind': 'headkit-attested-launch-v1', 'argv': argv or ['main.py', '--port', '8188'],
                                  'executable': 'python.exe', 'basePath': str(root), 'environment': {'PATH': 'x'}}), encoding='utf-8')
    core = str(Path(root).resolve())
    return {'schemaVersion': 3, 'python': {'version': '3.12.9 (main)'}, 'torch': {'version': '2.9', 'cuda': '12.8'},
            'coveredSourceRoots': [core], 'roots': ['site'], 'files': files or [{'path': 'C:/site/torch/__init__.py', 'sha256': 'a' * 64}],
            'comfySourceInventory': {'core': core, 'roots': [core], 'files': sources or [
                {'path': str(Path(core)/'custom_nodes/srn_headkit/nodes.py'), 'sha256': 'b' * 64}]},
            'session': {'id': 'c' * 32, 'pid': 1, 'configuration': pin(record), 'settingsSha256': 'd' * 64,
                        **({'mode': mode} if mode else {})}, 'fingerprint': 'f'}


class Client:
    def __init__(self, live): self.live, self.url = live, 'http://127.0.0.1:8188'
    def request(self, route, data=None): return self.live


class AttestationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        # validate_comfy_runtime is the existing schema gate; these tests are about the approval around it.
        patcher = mock.patch('headkit.source_inventory.validate_comfy_runtime', side_effect=lambda value, *a, **k: value)
        patcher.start(); self.addCleanup(patcher.stop); self.addCleanup(self.tmp.cleanup)

    def approved(self, live, notes='Approve this Desktop'):
        client = Client(live)
        attestation.capture(client, self.root/'capture.json')
        result = attestation.approve(client, self.root/'capture.json', notes, self.root/'approved.json')
        return {'comfyAttestation': result['binding']}

    def test_capture_summarises_then_approval_binds_the_exact_identity(self):
        live = identity(self.root)
        summary = attestation.capture(Client(live), self.root/'capture.json')['summary']
        self.assertEqual(summary['customNodes'], ['srn_headkit']); self.assertEqual(summary['cuda'], '12.8')
        with self.assertRaises(ValueError): attestation.approve(Client(live), self.root/'capture.json', ' ', self.root/'a.json')
        local = {'comfyAttestation': attestation.approve(Client(live), self.root/'capture.json', 'yes', self.root/'approved.json')['binding']}
        self.assertIs(attestation.check(live, local), live)
        self.assertEqual(json.loads((self.root/'approved.json').read_text())['notes'], 'yes')

    def test_a_changed_node_or_launch_is_refused_with_its_differences(self):
        local = self.approved(identity(self.root))
        changed = identity(self.root, sources=[{'path': str(self.root.resolve()/'custom_nodes/srn_headkit/nodes.py'), 'sha256': 'e' * 64},
                                                {'path': str(self.root.resolve()/'custom_nodes/new_node/__init__.py'), 'sha256': 'f' * 64}])
        with self.assertRaisesRegex(ValueError, r'1 Comfy source files added: .*new_node.*1 Comfy source files changed'):
            attestation.check(changed, local)
        relaunched = identity(self.root, argv=['main.py', '--port', '8188', '--lowvram'])
        with self.assertRaisesRegex(ValueError, 'launch arguments changed'): attestation.check(relaunched, local)

    def test_unbound_or_unapproved_snapshots_refuse_and_controlled_sessions_pass(self):
        live = identity(self.root)
        with self.assertRaisesRegex(ValueError, 'bind an approved attestation'): attestation.check(live, {})
        attestation.capture(Client(live), self.root/'capture.json')
        with self.assertRaisesRegex(ValueError, 'not an approved snapshot'):
            attestation.check(live, {'comfyAttestation': pin(self.root/'capture.json')})
        controlled = identity(self.root, mode=None)
        self.assertIs(attestation.check(controlled, {}), controlled)

    def test_approval_refuses_a_server_that_changed_since_the_capture(self):
        attestation.capture(Client(identity(self.root)), self.root/'capture.json')
        later = identity(self.root, files=[{'path': 'C:/site/torch/__init__.py', 'sha256': '9' * 64}])
        with self.assertRaisesRegex(ValueError, 'changed since the capture'):
            attestation.approve(Client(later), self.root/'capture.json', 'yes', self.root/'approved.json')

    def test_dispatch_and_completion_recheck_the_approval_bound_at_preparation(self):
        from headkit import comfy
        live = identity(self.root); local = self.approved(live)
        (self.root/'bindings.json').write_text(json.dumps(local), encoding='utf-8')
        prepared = {'comfyRuntimeIdentity': live, 'comfySourceInventory': live['comfySourceInventory'], 'bindings': pin(self.root/'bindings.json')}
        with mock.patch.object(comfy, 'validate_comfy_runtime', side_effect=lambda value, *a, **k: value):
            self.assertEqual(comfy.verify_comfy_runtime(Client(live), prepared), live)
            # The approval file is rewritten after preparation: its pin in the bindings no longer holds.
            approved = json.loads((self.root/'approved.json').read_text()); approved['notes'] = 'edited'
            (self.root/'approved.json').write_text(json.dumps(approved), encoding='utf-8')
            with self.assertRaises(ValueError): comfy.verify_comfy_runtime(Client(live), prepared)


if __name__ == '__main__':
    unittest.main()
