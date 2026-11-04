"""Only the documented empty /free acknowledgement may omit JSON."""
import io
import json
import unittest
from unittest.mock import Mock, patch
from tools.headkit.comfy import Client, preparation_runtime


class ComfyTransportTests(unittest.TestCase):
    def request(self,route,body,status=200):
        response=io.BytesIO(body)
        response.status=status
        with patch('urllib.request.urlopen',return_value=response):
            return Client('http://127.0.0.1:8188').request(route)

    def test_empty_free_acknowledges_request_without_claiming_release(self):
        self.assertEqual(self.request('/free',b''),{'accepted':True,'emptyResponse':True})

    def test_other_empty_responses_still_fail(self):
        for route,status in (('/queue',200),('/headkit/runtime-identity',200),('/free',204)):
            with self.subTest(route=route,status=status):
                with self.assertRaises(json.JSONDecodeError):self.request(route,b'',status)

    def test_json_response_is_preserved(self):
        self.assertEqual(self.request('/free',b'{"unloaded":true}'),{'unloaded':True})

    def test_legacy_preparation_keeps_full_runtime_verification(self):
        client=Mock();client.request.return_value={'identity':'original'}
        self.assertEqual(preparation_runtime(client,{}),client.request.return_value)
        client.request.assert_called_once_with('/headkit/runtime-identity')

    def test_opt_in_preparation_uses_explicit_dispatch_gated_baseline(self):
        client=Mock();identity={'identity':'startup-only'}
        client.request.return_value={'kind':'preparation-baseline-v1','runtimeIdentity':identity,'requiresFreshDispatch':True}
        self.assertIs(preparation_runtime(client,{'comfyPreparationVerification':'dispatch-gated-baseline-v1'}),identity)
        client.request.assert_called_once_with('/headkit/preparation-identity')
        for payload in ({'verified':True}, {**client.request.return_value,'requiresFreshDispatch':False}):
            client.request.return_value=payload
            with self.assertRaises(ValueError):preparation_runtime(client,{'comfyPreparationVerification':'dispatch-gated-baseline-v1'})

    def test_unknown_preparation_protocol_does_not_contact_service(self):
        client=Mock()
        with self.assertRaises(ValueError):preparation_runtime(client,{'comfyPreparationVerification':'skip'})
        client.request.assert_not_called()
