"""Prevent accidental preparation of the wrong part without network activity."""
import contextlib
import io
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import generate_purpose_built_part as generator


class ExplicitPartConfiguration(unittest.TestCase):
    def test_prepare_without_configuration_fails_before_service_access(self):
        with patch.object(sys, 'argv', ['generator', 'prepare', '--output', 'fresh',
                                      '--views-dir', 'views']), \
                patch.object(generator, 'prepare') as prepare, \
                contextlib.redirect_stderr(io.StringIO()) as error:
            with self.assertRaises(SystemExit) as exit_status:
                generator.main()
        self.assertEqual(exit_status.exception.code, 2)
        self.assertIn('explicit --config', error.getvalue())
        prepare.assert_not_called()

    def test_explicit_configuration_reaches_prepare_unchanged(self):
        with patch.object(sys, 'argv', ['generator', 'prepare', '--output', 'fresh',
                                      '--views-dir', 'views', '--config', 'shin.json']), \
                patch.object(generator, 'prepare') as prepare:
            generator.main()
        self.assertEqual(prepare.call_args.args[0].config, Path('shin.json'))

    def test_collection_uses_receipts_without_a_new_configuration(self):
        with patch.object(sys, 'argv', ['generator', 'status', '--output', 'existing']), \
                patch.object(generator, 'status') as status:
            generator.main()
        self.assertIsNone(status.call_args.args[0].config)




class ExplicitQueueAppendCli(unittest.TestCase):
    def test_submit_requires_idle_by_default_and_passes_explicit_append_flag(self):
        for enabled in (False, True):
            argv = ['generator', 'submit', '--output', 'prepared']
            if enabled: argv.append('--allow-occupied-queue')
            with self.subTest(enabled=enabled), patch.object(sys, 'argv', argv), patch.object(generator, 'submit') as submit:
                generator.main()
                self.assertIs(submit.call_args.args[0].allow_occupied_queue, enabled)

    def test_append_flag_rejected_for_prepare_and_status_before_action(self):
        for action in ('prepare', 'status'):
            with self.subTest(action=action), patch.object(sys, 'argv', ['generator', action, '--output', 'prepared', '--allow-occupied-queue']), \
                    patch.object(generator, action) as handler, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as result: generator.main()
                self.assertEqual(result.exception.code, 2); handler.assert_not_called()


class OnceOnlyQueueSubmission(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.args = SimpleNamespace(output=self.root, service=None, allow_occupied_queue=False)
        (self.root / 'views').mkdir()
        self.reference_bytes = b'unchanged-frozen-reference-for-mocked-upload'
        self.graph = {str(1000 + i): {'class_type': 'LoadImage', 'inputs': {'image': '__PENDING__'}} for i in range(4)}
        generator.save_json(self.root / 'workflow-api-template.json', self.graph)
        views = {}; frozen = {'workflow-api-template.json': generator.digest(self.root / 'workflow-api-template.json')}
        for view in generator.VIEW_ORDER:
            path = self.root / 'views' / (view + '.png'); path.write_bytes(self.reference_bytes)
            views[view] = {'path': 'views/' + view + '.png', 'sha256': generator.digest(path)}
            frozen[views[view]['path']] = generator.digest(path)
        self.preparation = {'schemaVersion': 1, 'service': 'http://mock.invalid', 'views': views,
            'viewOrder': list(generator.VIEW_ORDER), 'frozenFiles': frozen, 'externalDependencies': {},
            'outputPrefix': 'test/unique-master', 'clientAccepted': False}
        generator.save_json(self.root / 'preparation.json', self.preparation)
        self.empty = {'queue_running': [], 'queue_pending': []}
        self.occupied = {'queue_running': [[1, 'other-running', {}, {'client_id': 'other-owner'}]],
                         'queue_pending': [[2, 'other-pending', {}, {'client_id': 'other-owner-2'}]]}
        self.quiet = contextlib.redirect_stdout(io.StringIO()); self.quiet.__enter__()

    def tearDown(self):
        self.quiet.__exit__(None, None, None); self.tmp.cleanup()

    def service(self, queues, timeout=False):
        service = MagicMock(); service.base = 'http://mock.invalid'
        service.upload.side_effect = lambda path, folder: folder + '/' + path.name
        observed = [copy.deepcopy(queue) for queue in queues]
        requests = []
        def request(route, payload=None):
            requests.append((route, copy.deepcopy(payload)))
            if route == '/queue':
                self.assertTrue(observed, 'Unexpected repeated queue poll during dispatch')
                return observed.pop(0)
            self.assertEqual(route, '/prompt')
            receipt = generator.read_json(self.root / 'generation.json')
            self.assertEqual(receipt['state'], 'submission-started')
            self.assertEqual(receipt['clientId'], payload['client_id'])
            self.assertTrue(receipt['clientId'].startswith('srn-purpose-built-'))
            self.assertEqual(receipt['queueAtSubmission'], queues[-1])
            self.assertIs(receipt['allowOccupiedQueue'], self.args.allow_occupied_queue)
            self.assertEqual(receipt['queuePolicy'], 'append-existing-queue' if self.args.allow_occupied_queue else 'require-idle')
            self.assertEqual(receipt['preparationSha256'], generator.digest(self.root / 'preparation.json'))
            self.assertEqual(receipt['apiSha256'], generator.digest(self.root / 'workflow-api.json'))
            self.assertEqual(payload['prompt'], generator.read_json(self.root / 'workflow-api.json'))
            self.assertEqual(receipt['saveNodes'], ['372', '1010', '1012'])
            self.assertFalse(receipt['clientAccepted'])
            if timeout: raise TimeoutError('POST result unknown')
            return {'prompt_id': 'our-prompt', 'node_errors': {}}
        service.request.side_effect = request
        service.observed_requests = requests
        return service

    def dispatch(self, service):
        with patch.object(generator, 'Comfy', return_value=service), \
                patch.object(generator.urllib.request, 'urlopen', side_effect=lambda *args, **kwargs: io.BytesIO(self.reference_bytes)):
            generator.submit(self.args)

    def test_default_occupied_guard_prevents_upload_post_or_receipt(self):
        service = self.service([self.occupied])
        with self.assertRaisesRegex(RuntimeError, 'occupied'): self.dispatch(service)
        service.upload.assert_not_called()
        self.assertEqual([route for route, _ in service.observed_requests], ['/queue'])
        self.assertFalse((self.root / 'generation.json').exists()); self.assertFalse((self.root / 'workflow-api.json').exists())

    def test_default_guard_rechecks_latest_queue_after_uploads(self):
        service = self.service([self.empty, self.occupied])
        with self.assertRaisesRegex(RuntimeError, 'occupied'): self.dispatch(service)
        self.assertEqual(service.upload.call_count, 4)
        self.assertEqual([route for route, _ in service.observed_requests], ['/queue', '/queue'])
        self.assertFalse((self.root / 'generation.json').exists()); self.assertFalse((self.root / 'workflow-api.json').exists())

    def test_explicit_append_records_actual_latest_queue_and_preserves_other_work(self):
        self.args.allow_occupied_queue = True
        latest = copy.deepcopy(self.occupied); latest['queue_pending'].append([3, 'new-other-pending', {}, {'client_id': 'another-owner'}])
        before = copy.deepcopy([self.occupied, latest])
        service = self.service([self.occupied, latest]); self.dispatch(service)
        receipt = generator.read_json(self.root / 'generation.json')
        self.assertEqual(receipt['queueAtSubmission'], latest)
        self.assertEqual(receipt['queuePolicy'], 'append-existing-queue'); self.assertTrue(receipt['allowOccupiedQueue'])
        self.assertEqual(receipt['state'], 'queued'); self.assertEqual(receipt['promptId'], 'our-prompt')
        self.assertEqual([route for route, _ in service.observed_requests], ['/queue', '/queue', '/prompt'])
        self.assertEqual([self.occupied, latest], before)
        self.assertEqual(service.upload.call_count, 4)
        self.assertEqual(generator.read_json(self.root / 'workflow-api-template.json'), self.graph)
        self.assertEqual(generator.read_json(self.root / 'preparation.json'), self.preparation)

    def test_idle_default_records_require_idle_policy_and_before_post_identity(self):
        service = self.service([self.empty, self.empty]); self.dispatch(service)
        receipt = generator.read_json(self.root / 'generation.json')
        self.assertEqual(receipt['queuePolicy'], 'require-idle'); self.assertFalse(receipt['allowOccupiedQueue'])
        self.assertEqual(receipt['clientId'], service.observed_requests[-1][1]['client_id'])

    def test_timeout_retains_queue_and_unique_identity_before_post_then_blocks_duplicate(self):
        self.args.allow_occupied_queue = True
        service = self.service([self.occupied, self.occupied], timeout=True)
        with self.assertRaisesRegex(TimeoutError, 'unknown'): self.dispatch(service)
        receipt = generator.read_json(self.root / 'generation.json')
        self.assertEqual(receipt['state'], 'submission-started'); self.assertNotIn('promptId', receipt)
        self.assertEqual(receipt['clientId'], service.observed_requests[-1][1]['client_id'])
        self.assertEqual(receipt['queueAtSubmission'], self.occupied)
        preserved = (self.root / 'generation.json').read_bytes()
        with patch.object(generator, 'verify_record') as verify, patch.object(generator, 'Comfy') as network:
            with self.assertRaisesRegex(RuntimeError, 'never duplicate'): generator.submit(self.args)
            verify.assert_not_called(); network.assert_not_called()
        self.assertEqual((self.root / 'generation.json').read_bytes(), preserved)
        self.assertEqual([route for route, _ in service.observed_requests].count('/prompt'), 1)

    def test_existing_job_blocks_before_preparation_verification_or_network_even_with_append(self):
        self.args.allow_occupied_queue = True
        (self.root / 'generation.json').write_bytes(b'preserve-even-unreadable-existing-receipt')
        preserved = (self.root / 'generation.json').read_bytes()
        with patch.object(generator, 'verify_record') as verify, patch.object(generator, 'Comfy') as network:
            with self.assertRaisesRegex(RuntimeError, 'never duplicate'): generator.submit(self.args)
            verify.assert_not_called(); network.assert_not_called()
        self.assertEqual((self.root / 'generation.json').read_bytes(), preserved)


if __name__ == '__main__': unittest.main()
