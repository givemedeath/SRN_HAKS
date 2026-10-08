"""Detached component removal must preserve real corner bytes and provenance."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import target_contract as contract
from conservative_face_selection import mesh_arrays
from place_purposebuilt_pelvis import read_glb, write_glb, raw_corners
from remove_target_detached_components import execute, catalogue, select_components
from target_part_pipeline import execute as fit
from test_mirror_stock_limb_part import fixture
from test_target_part_pipeline import target_fixture


def source_fixture():
    doc,blob=fixture()
    vertices=[[0.,0.,0.],[.8,0.,0.],[0.,.5,0.],[0.,0.,.4]]
    faces=np.array([[0,2,1],[0,1,3],[0,3,2],[1,2,3]])
    for _ in range(2):
        mid={};new=[]
        def midpoint(a,b):
            key=tuple(sorted((int(a),int(b))))
            if key not in mid:
                mid[key]=len(vertices)
                vertices.append(((np.asarray(vertices[a])+vertices[b])*.5).tolist())
            return mid[key]
        for a,b,c in faces:
            ab,bc,ca=midpoint(a,b),midpoint(b,c),midpoint(c,a)
            new.extend([[a,ab,ca],[ab,b,bc],[ca,bc,c],[ab,bc,ca]])
        faces=np.asarray(new)
    first=len(vertices)
    vertices.extend([[1.5,0.,0.],[1.58,0.,0.],[1.5,.05,0.],[1.5,0.,.04]])
    faces=np.concatenate((faces,np.asarray([[0,2,1],[0,1,3],[0,3,2],[1,2,3]])+first))
    p=np.asarray(vertices,dtype='<f4');count=len(p)
    n=np.tile(np.array([0.,0.,1.3],'<f4'),(count,1))
    uv=np.column_stack((np.linspace(.1,.8,count),np.linspace(.9,.2,count))).astype('<f4')
    tangent=np.tile(np.array([1.2,0,0,-1],'<f4'),(count,1))
    color=np.tile(np.array([13,27,255,255],'u1'),(count,1))
    payload=bytearray(blob);attrs={}
    for name,array,kind,component in [('POSITION',p,'VEC3',5126),('NORMAL',n,'VEC3',5126),
          ('TEXCOORD_0',uv,'VEC2',5126),('TANGENT',tangent,'VEC4',5126),('COLOR_0',color,'VEC4',5121)]:
        payload.extend(b'\0'*(-len(payload)%4));offset=len(payload);payload.extend(array.tobytes())
        doc['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':array.nbytes})
        doc['accessors'].append({'bufferView':len(doc['bufferViews'])-1,'count':len(array),
                                'type':kind,'componentType':component})
        if name=='COLOR_0':doc['accessors'][-1]['normalized']=True
        attrs[name]=len(doc['accessors'])-1
    indices=faces.reshape(-1).astype('<u4')
    payload.extend(b'\0'*(-len(payload)%4));offset=len(payload);payload.extend(indices.tobytes())
    doc['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':indices.nbytes})
    doc['accessors'].append({'bufferView':len(doc['bufferViews'])-1,'count':len(indices),
                            'type':'SCALAR','componentType':5125})
    doc['meshes'][0]['primitives'][0].update(attributes=attrs,indices=len(doc['accessors'])-1)
    payload.extend(b'\0'*(-len(payload)%4));doc['buffers'][0]['byteLength']=len(payload)
    return doc,bytes(payload)


class DetachedComponentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.target=self.root/'target.json'
        self.target.write_text(json.dumps(target_fixture()),encoding='utf-8')
        self.raw=self.root/'raw.glb';write_glb(self.raw,*source_fixture())
        self.job=self.root/'generation.json'
        self.job.write_text(json.dumps({'state':'success','promptId':'collected-once',
             'outputs':[{'localPath':str(self.raw),'sha256':contract.sha(self.raw)}]}))
        cfg={'schemaVersion':2,'operation':'fit','part':'pelvis','coordinateSpace':'working',
             'targetContract':str(self.target),'targetContractSha256':contract.sha(self.target),
             'source':str(self.raw),'sourceSha256':contract.sha(self.raw),'sourceReceipt':str(self.job),
             'sourceReceiptSha256':contract.sha(self.job),'uniformScale':.63,
             'rotationDegreesXYZ':[19,-7,31],'sourceAnchorNwn':[.11,.08,.02],
             'targetAnchorLocal':[.03,-.02,-.04]}
        path=self.root/'fit.json';path.write_text(json.dumps(cfg))
        self.parent_path=fit(path,self.root/'fit');self.parent=json.loads(self.parent_path.read_text())
        self.source=Path(self.parent['candidate'])
        self.positions,self.faces,_=mesh_arrays(*read_glb(self.source))
        _,self.rows=catalogue(self.positions,self.faces)
        self.measure=self.root/'measurement.json'
        self.measure_doc={'schemaVersion':2,'kind':'target-detached-component-measurement',
                **contract.binding(self.target,target_fixture(),'working'),'part':'pelvis',
                'source':str(self.source),'sourceSha256':contract.sha(self.source),
                'sourceReceiptSha256':contract.sha(self.parent_path),'componentCatalogue':self.rows}
        self.config={'schemaVersion':2,'kind':'target-detached-component-removal','diagnosticOnly':True,
                'targetContract':str(self.target),'targetContractSha256':contract.sha(self.target),
                'part':'pelvis','coordinateSpace':'working','source':str(self.source),
                'sourceSha256':contract.sha(self.source),'sourceReceipt':str(self.parent_path),
                'sourceReceiptSha256':contract.sha(self.parent_path),
                'removedComponents':[{k:v for k,v in self.rows[1].items()
                    if k in {'seedSourceFaceId','faceCount','faceIdsSha256'}}|{'reason':'Isolated non-anatomical debris'}],
                'maximumRemovedFaceFraction':.1}
    def tearDown(self):self.tmp.cleanup()
    def run_trial(self,name='trial'):
        self.measure.write_text(json.dumps(self.measure_doc),encoding='utf-8')
        self.config['measurementReceipt']={'path':str(self.measure),'sha256':contract.sha(self.measure)}
        path=self.root/(name+'.json');path.write_text(json.dumps(self.config),encoding='utf-8')
        result=execute(path,self.root/name)
        return result,json.loads(result.read_text(encoding='utf-8'))
    def test_exact_parent_corners_maps_indices_and_native_lineage(self):
        original=self.source.read_bytes();_,record=self.run_trial()
        self.assertEqual(self.source.read_bytes(),original)
        self.assertEqual(record['proof']['deletedSourceFaces'],4)
        self.assertEqual(record['proof']['afterTopology']['components'],1)
        self.assertEqual(record['proof']['afterTopology']['boundaryEdges'],0)
        for old,new in zip(raw_corners(*read_glb(self.source))[:3],
                           raw_corners(*read_glb(record['candidate']))[:3]):
            self.assertTrue(np.array_equal(old[:64],new))
        with np.load(self.parent['nativeCornerArchive']['path']) as a,np.load(record['nativeCornerArchive']['path']) as b:
            for key in ('positions','normals','uvNative','uvGltf','sourcePositions','tangents'):
                self.assertTrue(np.array_equal(a[key][:64],b[key]),key)
            self.assertEqual(b['sourceTriangleIds'].tolist(),list(range(64)))
        self.assertTrue(record['proof']['sourceBinPrefixExact'])
        self.assertFalse(record['productionAccepted']);self.assertEqual(record['statureApplications'],0)
    def test_rejects_main_partial_component_and_excessive_removal(self):
        bad=copy.deepcopy(self.config['removedComponents'])
        bad[0]['seedSourceFaceId']=0
        with self.assertRaisesRegex(ValueError,'Largest anatomical'):select_components(self.positions,self.faces,bad,.1)
        bad=copy.deepcopy(self.config['removedComponents']);bad[0]['faceCount']=3
        with self.assertRaisesRegex(ValueError,'membership/count'):select_components(self.positions,self.faces,bad,.1)
        with self.assertRaisesRegex(ValueError,'exceeds explicit fraction'):
            select_components(self.positions,self.faces,self.config['removedComponents'],.01)
    def test_rejects_forged_measurement_and_unknown_controls(self):
        self.measure_doc['sourceSha256']='0'*64
        with self.assertRaisesRegex(ValueError,'another source/part'):self.run_trial()
        self.measure_doc['sourceSha256']=contract.sha(self.source);self.config['unseenInnerSheetDeletion']=True
        with self.assertRaisesRegex(ValueError,'Explicit detached removal'):self.run_trial()
    def test_repeated_repair_rejected_and_point_contacts_not_detached(self):
        path,record=self.run_trial()
        self.config.update(source=record['candidate'],sourceSha256=record['candidateSha256'],
                           sourceReceipt=str(path),sourceReceiptSha256=contract.sha(path))
        with self.assertRaisesRegex(ValueError,'repeated repair rejected'):self.run_trial('repeat')
        p=self.positions.copy()
        p[self.faces[64,0]]=p[self.faces[0,0]]
        groups,_=catalogue(p,self.faces)
        self.assertEqual(len(groups),1)


if __name__=='__main__':unittest.main()
