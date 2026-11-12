"""Every toolkit submits to the shared ComfyUI through one gate: GPU lease, proven server, idle queue."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

from headkit import attestation, shared_comfy
from headkit.comfy import Client
from headkit.test_attestation import identity


class Fake:
    """A ComfyUI whose queue empties after `busy` polls and which records what was posted."""
    def __init__(self, live, busy=0):
        self.live, self.busy, self.url, self.posted = live, busy, 'http://127.0.0.1:8188', []

    def request(self, route, data=None):
        if route == '/headkit/runtime-identity': return self.live
        if route == '/queue':
            self.busy -= 1
            return {'queue_running': [[0, 'other']] if self.busy >= 0 else [], 'queue_pending': []}
        if route == '/prompt':
            self.posted.append(shared_comfy.holding()); return {'prompt_id': 'p'}
        if route == '/history/p': return {'p': {'outputs': {}, 'status': {'completed': True, 'status_str': 'success'}}}
        raise AssertionError(route)


class SharedComfyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name).resolve(); self.addCleanup(self.tmp.cleanup)
        for patcher in (mock.patch.dict(os.environ, {'SRN_TOOLS_ROOT': str(self.root)}),
                        mock.patch('headkit.source_inventory.validate_comfy_runtime', side_effect=lambda value, *a, **k: value)):
            patcher.start(); self.addCleanup(patcher.stop)
        os.environ.pop(shared_comfy.LEASE_ENV, None)

    def approve(self, live):
        client = Fake(live)
        captured = attestation.capture(client)['snapshot']
        return attestation.approve(client, captured, 'Approve this Desktop')

    def test_one_approval_in_the_registry_serves_every_toolkit_and_a_binding_overrides_it(self):
        live = identity(self.root/'desktop')
        with self.assertRaisesRegex(ValueError, 'no approved snapshot is published'): attestation.check(live)
        result = self.approve(live)
        self.assertTrue(Path(result['approved']).is_relative_to(self.root/'comfy'))
        self.assertEqual(attestation.published()['attestation'], result['binding'])
        self.assertIs(attestation.check(live), live)                                   # no bindings needed
        self.assertEqual(attestation.approval({}), result['binding'])
        own = {'path': str(self.root/'elsewhere.json'), 'sha256': '0' * 64}
        self.assertEqual(attestation.approval({'comfyAttestation': own}), own)        # a toolkit's own binding wins

    def test_a_slot_waits_for_the_queue_proves_the_server_and_only_then_allows_a_prompt(self):
        live = identity(self.root/'desktop'); self.approve(live)
        client, naps = Fake(live, busy=2), []
        with shared_comfy.slot(client, sleep=naps.append, say=None) as proven:
            self.assertEqual(proven, {'identity': live, 'approval': attestation.published()['attestation']}); client.request('/prompt')
        self.assertEqual(client.posted, [True]); self.assertEqual(len(naps), 2); self.assertFalse(shared_comfy.holding())
        with self.assertRaisesRegex(ValueError, 'shared_comfy.slot'): Client('http://127.0.0.1:9').request('/prompt', {})
        with self.assertRaisesRegex(ValueError, 'stayed busy'):
            with shared_comfy.slot(Fake(live, busy=99), limit=0, sleep=lambda s: None, say=None): pass
        relaunched = Fake(live, busy=1)                                           # Desktop restarts during the wait
        def restart(seconds): relaunched.live = identity(self.root/'desktop', argv=['main.py', '--restarted'])
        with self.assertRaisesRegex(ValueError, 'launch arguments changed'):
            with shared_comfy.slot(relaunched, sleep=restart, say=None): self.fail('proven before the wait only')
        changed = identity(self.root/'desktop', argv=['main.py', '--lowvram'])  # relaunched with other arguments
        with self.assertRaisesRegex(ValueError, 'launch arguments changed'):
            with shared_comfy.slot(Fake(changed), say=None): self.fail('a drifted server got a slot')

    def test_the_lease_excludes_other_processes_and_passes_to_children_of_its_holder(self):
        path = shared_comfy.lease_path(0, self.root)
        holder = subprocess.Popen([sys.executable, '-c', 'import sys,time;sys.path[:0]=sys.argv[1:2];'
                                   'from headkit.shared_comfy import gpu_lease;'
                                   'cm=gpu_lease(0,sys.argv[2],say=None);cm.__enter__();print("held",flush=True);time.sleep(60)',
                                   str(Path(__file__).resolve().parents[1]), str(self.root)], stdout=subprocess.PIPE, text=True)
        self.addCleanup(holder.stdout.close); self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline().strip(), 'held')
        with self.assertRaisesRegex(ValueError, 'stayed leased'):
            with shared_comfy.gpu_lease(0, self.root, limit=0, say=None): pass
        holder.kill(); holder.wait()
        with shared_comfy.gpu_lease(0, self.root, say=None):
            self.assertEqual(os.environ[shared_comfy.LEASE_ENV], f'{os.path.normcase(str(path.resolve()))}|{os.getpid()}')
            with shared_comfy.gpu_lease(0, self.root, limit=0, say=None): pass        # nested on this thread: no wait
            self.assertEqual(shared_comfy.status(Fake(identity(self.root/'desktop')), root=self.root)['lease'], 'held by this session (thread)')
            refused = []
            def other():  # another thread of this process holds nothing of its own: it waits like any submitter
                try:
                    with shared_comfy.gpu_lease(0, self.root, limit=0, say=None): pass
                except ValueError as exc: refused.append(str(exc))
            worker = threading.Thread(target=other); worker.start(); worker.join()
            self.assertEqual(len(refused), 1); self.assertIn('stayed leased', refused[0])
            child = subprocess.run([sys.executable, '-c', 'import sys;sys.path.insert(0,sys.argv[1]);'
                                    'from headkit.shared_comfy import gpu_lease;'
                                    'cm=gpu_lease(0,sys.argv[2],limit=0,say=None);cm.__enter__();print("inherited")',
                                    str(Path(__file__).resolve().parents[1]), str(self.root)], capture_output=True, text=True)
            self.assertEqual(child.stdout.strip(), 'inherited', child.stderr)  # a child of the holder passes through
        self.assertNotIn(shared_comfy.LEASE_ENV, os.environ)

    def test_a_design_job_is_held_to_its_own_attestation_binding_first(self):
        from headkit import design
        live = identity(self.root/'desktop'); client = Fake(live)
        captured = attestation.capture(client)['snapshot']
        own = attestation.approve(client, captured, 'Approve for this design only', publish=False)['binding']
        self.assertIsNone(attestation.published())
        with self.assertRaisesRegex(ValueError, 'no approved snapshot is published'):
            design.dispatch(client, {}, 't', {}, poll=0)
        design.dispatch(client, {}, 't', {}, poll=0, local={'comfyAttestation': own})
        self.assertEqual(client.posted, [True])

    def test_a_job_is_rechecked_against_the_proof_frozen_at_dispatch(self):
        live = identity(self.root/'desktop'); approved = self.approve(live)['binding']
        proof = shared_comfy.proven(Fake(live).request, {})
        self.assertEqual(proof['approval'], approved)
        self.assertIs(shared_comfy.recheck(Fake(live).request, proof), live)
        restarted = dict(live, session=dict(live['session'], pid=2))
        with self.assertRaisesRegex(ValueError, 'restarted during the job'): shared_comfy.recheck(Fake(restarted).request, proof)
        changed = dict(live, files=[{'path': 'C:/site/torch/__init__.py', 'sha256': '9' * 64}])
        with self.assertRaisesRegex(ValueError, 'differs from its approved snapshot'): shared_comfy.recheck(Fake(changed).request, proof)
        controlled = identity(self.root/'desktop', mode=None); proof = shared_comfy.proven(Fake(controlled).request)
        self.assertIsNone(proof['approval'])
        with self.assertRaisesRegex(ValueError, 'runtime files changed'):
            shared_comfy.recheck(Fake(dict(controlled, files=changed['files'])).request, proof)

    def test_status_reports_instead_of_raising(self):
        live = identity(self.root/'desktop')
        report = shared_comfy.status(Fake(live), root=self.root)
        self.assertIn('refused', report['server']); self.assertEqual(report['lease'], 'free'); self.assertIs(report['queueIdle'], True)
        self.approve(live)
        self.assertEqual(shared_comfy.status(Fake(live))['server'], 'attested, matches the approved snapshot')


if __name__ == '__main__':
    unittest.main()
