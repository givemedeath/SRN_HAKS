"""Server-owned model bytes retain fresh boundary checks and legacy behavior."""
import copy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from headkit import comfy
from headkit.common import read, write, pin, verification_pass
from headkit.model_contract import model_contract, SERVER_MODEL_VERIFICATION
from headkit.comfy_nodes.model_resolution import bind_loader_models, verify_loader_models as server_verify
from headkit.test_headkit import Temporary, FakeClient


class ModelContractTests(Temporary):
    def prepared(self):
        self.model=self.file('pixal3d_int8_convrot.safetensors','reviewed model bytes')
        self.model_pin=pin(self.model);self.checkpoints={self.model.name:self.model_pin['sha256']}
        self.binding=self.root/'dispatch-bindings.json'
        write(self.binding,{'models':{self.model.name:self.model_pin}})
        standard={'1':{'class_type':'UNETLoader','inputs':{'unet_name':self.model.name}}}
        models,inputs=model_contract(standard,{self.model.name:self.model_pin},self.checkpoints)
        result=self.freeze_request({'token':'model-test','stage':'geometry','prompt':bind_loader_models(standard,models),'inputs':[]})
        self.bind_dispatch(result)
        result.update(modelVerification=SERVER_MODEL_VERIFICATION,modelInputs=inputs,loaderModels=models)
        original=comfy.read
        self.profile_patch=patch('headkit.comfy.read',side_effect=lambda path:self.checkpoints if Path(path).name=='checkpoints.json' else original(path))
        self.profile_patch.start();self.addCleanup(self.profile_patch.stop)
        return result

    def client(self,request):
        client=FakeClient();client.server_runtime=request['comfyRuntimeIdentity'];original=client.request
        folder=SimpleNamespace(get_full_path_or_raise=lambda category,name:str(self.model))
        def call(route,data=None):
            if route=='/headkit/verify-loader-models':return server_verify(data['models'],folder,data['prompt'])
            return original(route,data)
        client.request=call
        return client

    def test_client_does_not_read_weights_and_server_checks_fresh_bytes(self):
        request=self.prepared();client=self.client(request)
        original=comfy.verify
        def verify_client(rows):
            self.assertNotIn(str(self.model),[row['path'] for row in rows]);return original(rows)
        with patch('headkit.comfy.verify',side_effect=verify_client):
            self.assertEqual(comfy.verify_loader_models(client,request),{'verified':True,'count':1})
        self.model.write_text('changed after preparation')
        with self.assertRaisesRegex(ValueError,'bytes different'):comfy.verify_loader_models(client,request)

    def test_contract_requires_exact_bindings_and_rejects_unknown_protocol(self):
        request=self.prepared();client=self.client(request)
        for mode in ('extra','missing','wrong-path','unknown'):
            candidate=copy.deepcopy(request)
            if mode=='extra':candidate['modelInputs'].append(dict(self.model_pin))
            if mode=='missing':candidate['modelInputs']=[]
            if mode=='wrong-path':candidate['modelInputs'][0]['path']=str(self.file('other','reviewed model bytes'))
            if mode=='unknown':candidate['modelVerification']='timestamp-cache'
            with self.subTest(mode=mode),self.assertRaises(ValueError):comfy.verify_loader_models(client,candidate)

    def test_legacy_requests_still_verify_client_bytes(self):
        request=self.prepared();request.pop('modelVerification');request.pop('modelInputs');request['inputs'].append(self.model_pin)
        client=self.client(request);self.model.write_text('changed')
        with self.assertRaisesRegex(ValueError,'Stale file pin'):comfy.verify_loader_models(client,request)

    def test_changed_model_before_dispatch_is_rejected_without_spending_attempt(self):
        request=self.prepared();client=self.client(request);ledger=self.root/'ledger.json'
        comfy.initialize_ledger(ledger,0,'fixture');client.on_idle=lambda:self.model.write_text('changed under lock')
        with self.assertRaisesRegex(ValueError,'bytes different'):
            comfy.submit(client,ledger,request,self.root/'job',runtime_identity=request['runtimeIdentity'],bindings_path=self.binding)
        self.assertEqual(read(ledger)['jobs'][0]['state'],'preflight-rejected');self.assertEqual(client.posts,0)

    def collection(self,changed=False):
        request=self.prepared();client=self.client(request);ledger=self.root/'ledger.json';job=self.root/'job';output=self.root/'output'
        comfy.initialize_ledger(ledger,0,'fixture')
        comfy.submit(client,ledger,request,job,runtime_identity=request['runtimeIdentity'],bindings_path=self.binding)
        artifact=output/'headkit'/request['token']/'mesh.glb';artifact.parent.mkdir(parents=True);artifact.write_bytes(b'fixture mesh')
        history={'status':{'status_str':'success'},'outputs':{'1':{'files':[{'filename':'mesh.glb','subfolder':'headkit/'+request['token'],'type':'output'}]}}}
        original=client.request
        client.request=lambda route,data=None:{'prompt-1':history} if route.startswith('/history/') else original(route,data)
        if changed:self.model.write_text('changed after dispatch')
        return client,ledger,job,output,request['token']

    def test_completion_rejects_changed_model_and_records_terminal_failure(self):
        client,ledger,job,output,token=self.collection(changed=True)
        with self.assertRaisesRegex(ValueError,'bytes different'):comfy.collect(client,ledger,token,output,job)
        self.assertEqual(read(ledger)['jobs'][0]['state'],'failed-validation')
        self.assertEqual(read(job/'collection.json')['state'],'failed-validation')

    def test_completion_retains_server_proof_and_recollection_needs_no_server(self):
        client,ledger,job,output,token=self.collection()
        result=comfy.collect(client,ledger,token,output,job)
        self.assertEqual(result['modelCompletionProof'],{'verified':True,'count':1})
        self.assertEqual(result['modelInputs'],[self.model_pin])
        with patch.object(client,'request',side_effect=AssertionError('No repeat server request')):
            self.assertEqual(comfy.collect(client,ledger,token,output,job),result)

    def test_fresh_validation_passes_do_not_reuse_model_hashes(self):
        request=self.prepared();client=self.client(request)
        with verification_pass('first'):comfy.verify_loader_models(client,request)
        self.model.write_text('changed between passes')
        with verification_pass('second'),self.assertRaisesRegex(ValueError,'bytes different'):
            comfy.verify_loader_models(client,request)
