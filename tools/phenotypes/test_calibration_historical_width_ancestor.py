"""Historical width/mirror ancestor byte guards using real synthetic producers."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import target_contract as c
import replay_stage_skin_calibration as cal
import target_source_face_material_lineage as lineage
import test_source_face_material_lineage as facefixtures
from test_human_female_stock_exact import stock_fixture
from test_target_part_stage import textured_fixture
from target_part_pipeline import execute
from place_purposebuilt_pelvis import read_glb,write_glb,accessor,raw_corners
from retarget import nodes,transforms
import scale_target_limb_width as producer


def save(path,value):path.write_text(json.dumps(value),encoding='utf-8');return path


def width_parents(root,part):
    tp,t=stock_fixture(root);sp=root/'pfh0.mdl';text=sp.read_text()
    locations={'lthigh_g':[-.086064722,-.001916,1.016476482],'rthigh_g':[.078837478,-.001916,1.016476482],
               'lshin_g':[-.071274122,-.00673854,.554775482],'rshin_g':[.064046878,-.00673854,.554775482]}
    import re
    for name,xyz in locations.items():
        pattern=r'(node dummy '+name+r'\n parent pfh0\n) position [^\n]+\n orientation [^\n]+'
        text,count=re.subn(pattern,lambda m:m[1]+' position '+' '.join(map(str,xyz))+'\n orientation 0 0 1 0',text);assert count==1
    sp.write_text(text);frames={k:v.tolist() for k,v in transforms(nodes(text)).items()};stock=root/'stock.json';proof=json.loads(stock.read_text());proof.update(frames=frames,frozenInputs={str(sp):c.sha(sp)},rootAscii={'path':str(sp),'sha256':c.sha(sp)});save(stock,proof)
    t['rig']['frames']={'working':deepcopy(frames),'runtime':deepcopy(frames)};t['rig']['stockReferenceReceipt']['sha256']=c.sha(stock);save(tp,t);t=c.load(tp)
    doc,blob=textured_fixture();doc['meshes'][0]['primitives'][0]['attributes'].pop('COLOR_0')
    # Unit source normals keep this producer inside its unchanged 1e-7 encoding bound; native/raw position distinctions remain exercised.
    normal_index=doc['meshes'][0]['primitives'][0]['attributes']['NORMAL'];normal_info=doc['accessors'][normal_index];normal_view=doc['bufferViews'][normal_info['bufferView']];offset=normal_view.get('byteOffset',0)+normal_info.get('byteOffset',0);payload=bytearray(blob);payload[offset:offset+normal_info['count']*12]=np.tile(np.array([0,0,1],dtype='<f4'),(normal_info['count'],1)).tobytes();blob=bytes(payload)
    src=root/'synthetic.glb';write_glb(src,doc,blob);job=save(root/'synthetic-job.json',{'state':'success','promptId':'unit-fixture-only','outputs':[{'localPath':str(src),'sha256':c.sha(src)}]})
    fit={'schemaVersion':2,'operation':'fit','part':'legl','coordinateSpace':'working','targetContract':str(tp),'targetContractSha256':c.sha(tp),
         'source':str(src),'sourceSha256':c.sha(src),'sourceReceipt':str(job),'sourceReceiptSha256':c.sha(job),'uniformScale':.413274781,'rotationDegreesXYZ':[4,9,0],
         'sourceAnchorNwn':[0,0,0],'targetAnchorLocal':[0,0,0]}
    rp=execute(save(root/'original-fit.json',fit),root/'original-fit');hip=c.frame(t,'lthigh_g','working');knee=c.frame(t,'lshin_g','working');shaft=(np.linalg.inv(hip)@knee)[:3,3];hint=hip[:3,:3].T@np.array([1.,0,0]);matrix,axis,_,_=producer.width_matrix(shaft,hint,.78)
    cfg={'schemaVersion':2,'kind':'target-thigh-width-diagnostic','targetContract':str(tp),'targetContractSha256':c.sha(tp),'parentReceipt':str(rp),'parentReceiptSha256':c.sha(rp),
         'widthFactor':.78,'matrixLocal':matrix.tolist(),'widthAxisLocal':axis.tolist(),'mirrorPlaneWorldX':-.003613622,'protectedInputs':{str(tp):c.sha(tp)}}
    lp,rr,_=producer.execute(save(root/'width-config.json',cfg),root/'width');p=lp if part=='legl' else rr;rec=json.loads(p.read_text());return tp,t,p,Path(rec['candidate'])


class HistoricalWidthAncestorTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
    def tearDown(self):self.tmp.cleanup()
    def prepare(self,part='legl'):
        self.f=facefixtures.fixture(self.root,part=part,parent_factory=width_parents);return self.current()
    def current(self):
        f=self.f;return cal.geometry_input(cal.file_row(f['source']),cal.file_row(f['rp']),f['tp'],f['target'],f['rec']['part'],'working')
    def refresh_parent(self,rec):
        f=self.f;save(f['old_rp'],rec);f['rec']['sourceReceiptSha256']=c.sha(f['old_rp']);f['rec']['sourceSha256']=c.sha(f['old_source']);f['rec']['frozenInputs'][str(f['old_rp'])]=c.sha(f['old_rp']);f['rec']['frozenInputs'][str(f['old_source'])]=c.sha(f['old_source']);save(f['rp'],f['rec'])
    def test_exact_width_raw_and_separate_native_ancestor_replay(self):
        v=self.prepare();p=v['serializationProof']['parentRepresentationProof'];self.assertTrue(p['actualRawGLBPNUTUVIndexMapsAndBINPrefixByteExact']);self.assertTrue(p['separateNativeDoublePNUVTTransformVerified']);self.assertTrue(p['nativeDoubleEqualityWithRawFloat32NotClaimed'])
        rec=json.loads(self.f['old_rp'].read_text());P,_,_,_=raw_corners(*read_glb(self.f['old_source']))
        with np.load(rec['nativeCornerArchive']['path']) as z:self.assertFalse(np.array_equal(P.astype('f4'),z['positions'].astype('f4')))
    def test_actual_mirror_winding_and_tangent_sign_replay(self):
        v=self.prepare('legr');self.assertEqual(v['serializationProof']['parentRepresentationProof']['operation'],'mirror')
    def test_old_raw_attribute_corruption_rejected_independently_of_child_hash(self):
        self.prepare();f=self.f;doc,blob=read_glb(f['old_source']);b=bytearray(blob);pr=doc['meshes'][0]['primitives'][0];a=doc['accessors'][pr['attributes']['NORMAL']];off=doc['bufferViews'][a['bufferView']]['byteOffset'];b[off]^=1;write_glb(f['old_source'],doc,bytes(b));rec=json.loads(f['old_rp'].read_text());rec['candidateSha256']=c.sha(f['old_source']);self.refresh_parent(rec)
        with self.assertRaisesRegex(ValueError,'raw-source literal attribute'):self.current()
    def test_old_native_field_corruption_rejected_separately(self):
        self.prepare();f=self.f;rec=json.loads(f['old_rp'].read_text());ap=Path(rec['nativeCornerArchive']['path']);z=dict(np.load(ap));z['positions'][0,0,0]+=.0001;np.savez_compressed(ap,**z);rec['nativeCornerArchive']=cal.file_row(ap);self.refresh_parent(rec)
        with self.assertRaisesRegex(ValueError,'separate native'):self.current()
    def test_wrong_width_matrix_coefficient_or_missing_historical_snapshot_rejected(self):
        self.prepare();f=self.f;original=json.loads(f['old_rp'].read_text())
        for change in ('factor','matrix','snapshot'):
            rec=deepcopy(original)
            if change=='factor':rec['proof']['widthFactor']=.9
            elif change=='matrix':rec['proof']['matrixLocal'][0][0]+=.01
            else:rec['frozenInputs'][str(Path(lineage.__file__).parent/'target_part_pipeline.py')]='34ea6b0424c4cbce30635822fc3c1a4d821cfa4236897275e9021ee7294a41ed'
            self.refresh_parent(rec)
            with self.subTest(change=change),self.assertRaises(ValueError):self.current()
    def test_mirror_winding_and_sign_declaration_corruption_rejected(self):
        self.prepare('legr');f=self.f;original=json.loads(f['old_rp'].read_text())
        for key,value in [('triangleCornerOrder',[0,1,2]),('tangentWFlipsExactly',False),('reflectionWorld',np.eye(4).tolist())]:
            rec=deepcopy(original);rec['proof'][key]=value
            if key=='reflectionWorld':rec[key]=value
            self.refresh_parent(rec)
            with self.subTest(key=key),self.assertRaises(ValueError):self.current()

if __name__=='__main__':unittest.main()