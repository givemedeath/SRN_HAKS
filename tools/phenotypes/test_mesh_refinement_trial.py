"""A diagnostic must use its pinned parent and cannot repeat uncertain dispatch."""
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from run_mesh_refinement_trial import pinned_request, submit, status
from stage_stock_part import sha


class DiagnosticDispatch(unittest.TestCase):
    def fixture(self,root):
        source=root/'raw.glb';source.write_bytes(b'retained raw')
        settings={'sign_mode':'sdf','resolution':384}
        graph={
            '1':{'class_type':'Load3DAdvanced','inputs':{'model_file':'frozen/raw.glb [output]'}},
            '2':{'class_type':'Get3DComponents','inputs':{'model_3d':['1',0]}},
            '3':{'class_type':'RemeshMesh','inputs':{'mesh':['2',0],**settings}},
            '4':{'class_type':'MeshToFile3D','inputs':{'mesh':['3',0]}},
            '5':{'class_type':'Save3DAdvanced','inputs':{'model_3d':['4',0]}}}
        api=root/'api.json';api.write_text(json.dumps(graph))
        generation=root/'parent.json';generation.write_text(json.dumps({'state':'success','promptId':'parent',
            'outputs':[{'sha256':sha(source),'filename':'raw.glb','subfolder':'frozen','type':'output'}]}))
        aux=root/'proof.json';aux.write_text('{}')
        request={'source':str(source),'sourceSha256':sha(source),'serverSource':str(source),
            'serverSha256':sha(source),'generationReceipt':str(generation),'generationSha256':sha(generation),
            'originalPromptId':'parent','parentApi':str(aux),'parentApiSha256':sha(aux),
            'api':str(api),'apiSha256':sha(api),'loaderProof':str(aux),'loaderProofSha256':sha(aux),
            'liveSchemas':str(aux),'liveSchemasSha256':sha(aux),'installedDependencies':{},'settings':settings}
        path=root/'request.json';path.write_text(json.dumps(request))
        return path,request,graph

    def test_wrong_source_or_rewired_graph_rejected_even_with_updated_api_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path,record,graph=self.fixture(root)
            pinned_request(path)
            graph['1']['inputs']['model_file']='frozen/wrong.glb [output]'
            Path(record['api']).write_text(json.dumps(graph));record['apiSha256']=sha(record['api'])
            path.write_text(json.dumps(record))
            with self.assertRaisesRegex(RuntimeError,'Loader'):pinned_request(path)
            graph['1']['inputs']['model_file']='frozen/raw.glb [output]'
            graph['4']['inputs']['mesh']=['2',0]
            Path(record['api']).write_text(json.dumps(graph));record['apiSha256']=sha(record['api'])
            path.write_text(json.dumps(record))
            with self.assertRaisesRegex(RuntimeError,'graph must consume'):pinned_request(path)

    def test_changed_master_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path,record,_=self.fixture(Path(directory))
            Path(record['source']).write_bytes(b'changed actual geometry')
            with self.assertRaisesRegex(RuntimeError,'input changed'):pinned_request(path)

    def test_existing_output_blocks_network_even_when_submission_uncertain(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory);request=output/'request.json';request.write_text('{}')
            with patch('run_mesh_refinement_trial.Comfy') as network:
                with self.assertRaisesRegex(RuntimeError,'never repeat uncertain'):
                    submit(types.SimpleNamespace(request=request,output=output,service='unused'))
                network.assert_not_called()

    def test_uncertain_receipt_requires_history_investigation_without_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'request.json').write_text('{}');(root/'workflow-api.json').write_text('{}')
            (root/'generation.json').write_text(json.dumps({'state':'submission-started',
                'requestSha256':sha(root/'request.json'),'apiSha256':sha(root/'workflow-api.json')}))
            with patch('run_mesh_refinement_trial.Comfy') as network:
                with self.assertRaisesRegex(RuntimeError,'Uncertain submission'):
                    status(types.SimpleNamespace(output=root))
                network.assert_not_called()


if __name__=='__main__':unittest.main()
