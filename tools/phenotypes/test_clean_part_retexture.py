import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_clean_part_retexture as runner
from stage_stock_part import sha


class DispatchSafetyTests(unittest.TestCase):
    def test_template_rejected_without_dispatch(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'preparation.json'
            path.write_text(json.dumps({'state':'parameterized-template-not-dispatchable','cleanSourceAcceptance':None}))
            with self.assertRaisesRegex(RuntimeError,'template'):runner.prepared(path)

    def test_uncertain_existing_output_never_submitted(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(runner,'Comfy') as service:
            args=argparse.Namespace(preparation=Path(folder)/'preparation.json',output=Path(folder),service='local')
            with self.assertRaisesRegex(RuntimeError,'uncertain'):runner.submit(args)
            service.assert_not_called()

    def test_lost_response_blocks_different_output_and_preparation_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);prep=root/'prepared';prep.mkdir()
            preparation=prep/'preparation.json';preparation.write_text('{}')
            parent=root/'parent.json';parent.write_text(json.dumps({'promptId':'parent'}))
            graph={'372':{'inputs':{'filename_prefix':'fresh/run/textured'}},
                   '2002':{'inputs':{'filename_prefix':'fresh/run/uv-master'}}}
            (prep/'workflow-api.json').write_text(json.dumps(graph))
            record={'saveNodes':['372','2002'],'parentGeneration':str(parent),
                    'cleanSourceAcceptance':{'source':{'sha256':'source'}}}
            requests=[]
            def request(route,body=None):
                requests.append((route,body))
                if route=='/queue':return {'queue_running':[],'queue_pending':[]}
                raise TimeoutError('Response lost after accepted POST')
            with patch.object(runner,'prepared',return_value=(record,{},graph)), \
                 patch.object(runner,'DISPATCH_RESERVATIONS',root/'reservations'), \
                 patch.object(runner,'Comfy') as service:
                service.return_value.request.side_effect=request
                first=argparse.Namespace(preparation=preparation,output=root/'first',service='local/')
                with self.assertRaises(TimeoutError):runner.submit(first)
                copied=root/'copied';copied.mkdir()
                (copied/'preparation.json').write_bytes(preparation.read_bytes())
                (copied/'workflow-api.json').write_bytes((prep/'workflow-api.json').read_bytes())
                second=argparse.Namespace(preparation=copied/'preparation.json',output=root/'second',service='local')
                with self.assertRaisesRegex(RuntimeError,'reserved'):runner.submit(second)
            self.assertEqual(sum(route=='/prompt' for route,_ in requests),1)
            self.assertFalse((root/'second').exists())
            receipt=json.loads((root/'first/generation.json').read_text())
            reservation=json.loads(Path(receipt['dispatchReservation']).read_text())
            self.assertEqual(receipt['clientId'],reservation['clientId'])
            self.assertEqual(receipt['clientId'],next(body['client_id'] for route,body in requests if route=='/prompt'))

    def receipt(self,root):
        (root/'preparation.json').write_text('{}')
        graph={'372':{'inputs':{'filename_prefix':'fresh/run/textured'}},
               '2002':{'inputs':{'filename_prefix':'fresh/run/uv-master'}}}
        (root/'workflow-api.json').write_text(json.dumps(graph))
        receipt={'promptId':'one-known-job','service':'local','saveNodes':['372','2002'],
                 'preparationSha256':sha(root/'preparation.json'),'apiSha256':sha(root/'workflow-api.json')}
        (root/'generation.json').write_text(json.dumps(receipt));return receipt

    def test_two_declared_masters_collected_and_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.receipt(root)
            outputs={key:{'mesh':[{'filename':name+'_00001.glb','subfolder':'fresh/run','type':'output'}]}
                     for key,name in [('372','textured'),('2002','uv-master')]}
            result={'one-known-job':{'status':{'status_str':'success'},'outputs':outputs}}
            payload=b'glTF'+b'\0'*32
            with patch.object(runner,'Comfy') as service,patch.object(runner.urllib.request,'urlopen',side_effect=lambda *a,**k:BytesIO(payload)):
                service.return_value.request.return_value=result
                runner.status(argparse.Namespace(output=root))
            record=json.loads((root/'generation.json').read_text())
            self.assertEqual(len(record['outputs']),2)
            self.assertTrue(all(row['sha256']==hashlib.sha256(payload).hexdigest() for row in record['outputs']))

    def test_wrong_prefix_rejected_before_download(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.receipt(root)
            result={'one-known-job':{'status':{'status_str':'success'},'outputs':{
                '372':{'mesh':[{'filename':'textured_00001.glb','subfolder':'old/run','type':'output'}]}}}}
            with patch.object(runner,'Comfy') as service,patch.object(runner.urllib.request,'urlopen') as download:
                service.return_value.request.return_value=result
                with self.assertRaisesRegex(RuntimeError,'prefix'):runner.status(argparse.Namespace(output=root))
                download.assert_not_called()


if __name__=='__main__':unittest.main()
