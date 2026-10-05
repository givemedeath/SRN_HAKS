"""Separate pelvis diagnostic material domains and fail-closed body-map tests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

import target_contract as contract
import target_diagnostic_material_lineage as lineage
from partition_target_pelvis_materials import active_faces, face_layout_sha
from place_purposebuilt_pelvis import accessor, read_glb, write_glb
from segment_target_diagnostic_pelvis_body import subdivide_body
from segment_target_pelvis_boundary import CORNER_KEYS
from target_part_pipeline import verify_source_receipt
from test_segment_target_pelvis_boundary import canonical_fixture, cut_map
from test_target_diagnostic_lineage import indexed_fixture
from test_target_part_pipeline import target_fixture


def fixture(change=None):
    doc, binary, body, _ = canonical_fixture(change); blob = bytearray(binary)
    primitives = doc['meshes'][0]['primitives']; base = primitives[0]
    def append(value, kind):
        value = np.asarray(value); blob.extend(b'\0'*(-len(blob)%4)); offset=len(blob); blob.extend(value.tobytes()); blob.extend(b'\0'*(-len(blob)%4))
        doc['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':value.nbytes})
        doc['accessors'].append({'bufferView':len(doc['bufferViews'])-1,'componentType':5126 if value.dtype.kind=='f' else 5125,
                                'count':len(value),'type':kind})
        return len(doc['accessors'])-1
    # Preserve one intentionally inactive source row with a near-zero normal.
    for key, kind in [('POSITION','VEC3'),('NORMAL','VEC3'),('TEXCOORD_0','VEC2'),('TANGENT','VEC4')]:
        value=accessor(doc,binary,base['attributes'][key]); extra=value[:1].copy()
        if key=='NORMAL':extra[0]=[0,0,1e-13]
        base['attributes'][key]=append(np.concatenate((value,extra)),'VEC'+str(value.shape[1]))
    caps_doc,caps_blob,*_=indexed_fixture()
    doc['materials'].append(copy.deepcopy(caps_doc['materials'][1]))
    for old in caps_doc['meshes'][0]['primitives'][1:]:
        attrs={key:append(accessor(caps_doc,caps_blob,index),'VEC'+str(accessor(caps_doc,caps_blob,index).shape[1])) for key,index in old['attributes'].items()}
        primitives.append({'attributes':attrs,'indices':append(accessor(caps_doc,caps_blob,old['indices']).astype('<u4').reshape(-1),'SCALAR'),'material':1})
    doc['buffers'][0]['byteLength']=len(blob); binary=bytes(blob)
    ids=np.asarray([11,22,33,44],dtype=np.int64); body['sourceTriangleIds']=ids.copy()
    rows=active_faces(doc,binary)
    caps={key:np.concatenate([accessor(doc,binary,p['attributes'][key])[faces] for _,p,faces in rows[1:]]) for key in ('POSITION','NORMAL','TEXCOORD_0','TANGENT')}
    caps.update(primitiveIds=np.asarray([1,2],dtype=np.int64),materialIds=np.ones(2,dtype=np.int64),sourceOriginalFaceIds=np.full(2,-1,dtype=np.int64))
    return doc,binary,body,caps,ids


def selection(doc,binary,ids):
    old=cut_map(doc,binary)
    return {'schemaVersion':2,'kind':lineage.MAP_KIND,'scope':lineage.SCOPE,'coordinateSpace':'working',
            'part':'pelvis','joint':'pelvis_g','statureApplications':0,'faceIdSpace':'parent-active-primitive0-order',
            'parentBodyFaceCount':4,'parentFaceLayoutSha256':face_layout_sha(active_faces(doc,binary)),
            'primitive1And2Mode':lineage.CAP_MODE,'wholeSkinParentBodyFaceIds':[3],'wholeGarmentParentBodyFaceIds':[],
            'ambiguousParentBodyFaceIds':[],'cutFaces':[{'parentBodyFaceId':row['sourceFaceId'],
                'originalSourceFaceId':int(ids[row['sourceFaceId']]),**{k:v for k,v in row.items() if k!='sourceFaceId'}} for row in old['cutFaces']],
            'complete':True,'materialAccepted':False,'capOwnershipAccepted':False,'clientAccepted':False,'productionAccepted':False,
            'rootReview':{'reviewed':True,'reviewedBy':'/root','approveImplementation':True,'authorizeActualExport':True,
                'scope':lineage.SCOPE,'notes':'Synthetic closed cut contour only; no actual source ownership selected.',
                'evidence':[{'path':'synthetic-only','sha256':'0'*64}]}}


class DiagnosticBodyMaterialTests(unittest.TestCase):
    def test_caps_literal_original_prefix_inactive_row_and_body_corner_domains(self):
        doc,blob,body,caps,ids=fixture(); saved=copy.deepcopy(doc)
        new,binary,result,cap_result,proof=subdivide_body(doc,blob,body,caps,ids,selection(doc,blob,ids))
        self.assertEqual(doc,saved);self.assertEqual(binary[:len(blob)],blob)
        self.assertEqual(lineage.literal_json(new['meshes'][0]['primitives'][1:3]),lineage.literal_json(doc['meshes'][0]['primitives'][1:3]))
        self.assertEqual(new['materials'],doc['materials']+[doc['materials'][0]])
        for key in caps:self.assertEqual(cap_result[key].tobytes(),caps[key].tobytes());self.assertEqual(cap_result[key].dtype,caps[key].dtype)
        for key in CORNER_KEYS|{'tangents'}:self.assertEqual(result[key].dtype,np.float64)
        self.assertFalse(set(result['primitiveIds']).intersection({1,2}));self.assertEqual(result['positions'][0].tobytes(),body['positions'][3].tobytes())
        normal_index=doc['meshes'][0]['primitives'][0]['attributes']['NORMAL']
        self.assertEqual(accessor(new,binary,normal_index)[-1].tobytes(),accessor(doc,blob,normal_index)[-1].tobytes())
        self.assertLess(np.linalg.norm(accessor(new,binary,normal_index)[-1]),1e-12)
        for p in new['meshes'][0]['primitives']:
            if p['attributes']['NORMAL']==normal_index:self.assertNotIn(len(accessor(doc,blob,normal_index))-1,accessor(new,binary,p['indices']))
        self.assertEqual(proof['bodyTrianglesAfter'],10);self.assertEqual(proof['statureApplicationsAdded'],0)
        self.assertFalse(proof['historicalFitReapplied']);self.assertFalse(proof['attachmentFrameReapplied'])
        self.assertEqual(result['originalSourceFaceIds'].tolist(),ids[result['parentBodyFaceIds']].tolist())
        for out,face in enumerate(result['parentBodyFaceIds']):
            np.testing.assert_allclose(result['positions'][out],result['originalSourceCornerBarycentrics'][out]@body['positions'][face],atol=1e-16)
            for corner,original in enumerate(result['sourceCornerOrder'][out]):
                if original>=0:
                    for key in CORNER_KEYS|{'tangents'}:self.assertEqual(result[key][out,corner].tobytes(),body[key][face,original].tobytes())
        self.assertLess(proof['maximumAreaFractionError'],1e-12);self.assertLess(proof['maximumPlaneDeviationMetres'],1e-14)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'literal.glb';write_glb(path,new,binary)
            reopened,reblob=read_glb(path);lineage.verify_unchanged_storage(reopened,reblob,doc,blob)
            self.assertEqual(lineage.literal_json(reopened['meshes'][0]['primitives'][1:3]),lineage.literal_json(doc['meshes'][0]['primitives'][1:3]))

    def test_exhaustive_current_body_and_original_face_binding_required(self):
        doc,blob,body,caps,ids=fixture();valid=selection(doc,blob,ids)
        for change in ('missing','duplicate','source-face','caps','stale-layout','ambiguous','not-complete','no-whole-skin','inference'):
            bad=copy.deepcopy(valid)
            if change=='missing':bad['cutFaces'].pop()
            elif change=='duplicate':bad['wholeSkinParentBodyFaceIds']=[0,3]
            elif change=='source-face':bad['cutFaces'][0]['originalSourceFaceId']=22
            elif change=='caps':bad['cutFaces'][0]['parentBodyFaceId']=4
            elif change=='stale-layout':bad['parentFaceLayoutSha256']='wrong'
            elif change=='ambiguous':bad['ambiguousParentBodyFaceIds']=[0]
            elif change=='not-complete':bad['complete']=False
            elif change=='no-whole-skin':bad['wholeSkinParentBodyFaceIds']=[];bad['wholeGarmentParentBodyFaceIds']=[3]
            else:bad['atlasThreshold']=40
            with self.subTest(change=change),self.assertRaises(ValueError):subdivide_body(doc,blob,body,caps,ids,bad)

    def test_root_body_scope_cannot_waive_topology_or_grant_material_cap_acceptance(self):
        doc,blob,body,caps,ids=fixture();valid=selection(doc,blob,ids)
        for key,value in [('scope','barycentric-pelvis-boundary-segmentation'),('authorizeActualExport',False),('reviewedBy','classifier'),
                          ('sourceTopologyResolved',True),('productionAccepted',True),('waiveCaps',True)]:
            bad=copy.deepcopy(valid);bad['rootReview'][key]=value
            with self.subTest(review=key),self.assertRaises(ValueError):subdivide_body(doc,blob,body,caps,ids,bad)
        for key,value in [('statureApplications',1),('coordinateSpace','runtime'),('part','handl'),('capOwnershipAccepted',True),
                          ('primitive1And2Mode','skin-caps'),('materialAccepted',True)]:
            bad=copy.deepcopy(valid);bad[key]=value
            with self.subTest(map=key),self.assertRaises(ValueError):subdivide_body(doc,blob,body,caps,ids,bad)

    def test_cap_byte_changes_and_promoted_precision_rejected(self):
        doc,blob,body,caps,ids=fixture()
        for change in ('position','normal','precision','source-id','primitive-id','material-id'):
            bad={k:v.copy() for k,v in caps.items()}
            if change=='position':bad['POSITION'][0,0,0]+=.0001
            elif change=='normal':bad['NORMAL'][0,0,2]=1
            elif change=='precision':bad['POSITION']=bad['POSITION'].astype(np.float64)
            elif change=='source-id':bad['sourceOriginalFaceIds'][0]=11
            elif change=='primitive-id':bad['primitiveIds'][0]=0
            else:bad['materialIds'][0]=0
            with self.subTest(change=change),self.assertRaises(ValueError):subdivide_body(doc,blob,body,bad,ids,selection(doc,blob,ids))
        new,binary,*_=subdivide_body(doc,blob,body,caps,ids,selection(doc,blob,ids))
        for change in ('cap-descriptor','inactive-normal','cap-index'):
            bad=copy.deepcopy(new);data=bytearray(binary)
            if change=='cap-descriptor':bad['meshes'][0]['primitives'][1]['material']=2
            else:
                primitive=doc['meshes'][0]['primitives'][0 if change=='inactive-normal' else 1]
                index=primitive['attributes']['NORMAL'] if change=='inactive-normal' else primitive['indices']
                view=doc['bufferViews'][doc['accessors'][index]['bufferView']];data[view.get('byteOffset',0)]^=1
            with self.subTest(change=change),self.assertRaises(ValueError):lineage.verify_unchanged_storage(bad,bytes(data),doc,blob)

    def test_no_cut_whole_partition_keeps_caps_and_does_not_normalize_source_rows(self):
        doc,blob,body,caps,ids=fixture();valid=selection(doc,blob,ids)
        valid.update(cutFaces=[],wholeSkinParentBodyFaceIds=[0,1,2],wholeGarmentParentBodyFaceIds=[3])
        new,binary,derived,cap_result,proof=subdivide_body(doc,blob,body,caps,ids,valid)
        self.assertEqual(len(new['meshes'][0]['primitives']),4);self.assertEqual(proof['bodyTrianglesAfter'],4)
        self.assertEqual(proof['cutParentBodyFaceIds'],[])
        for key in CORNER_KEYS|{'tangents'}:self.assertEqual(derived[key].tobytes(),body[key].tobytes())
        self.assertEqual(new['meshes'][0]['primitives'][3]['attributes'],doc['meshes'][0]['primitives'][0]['attributes'])

    def test_interpolation_failures_and_hanging_cut_still_rejected_by_reused_math(self):
        for change,message in [('normal','interpolated normal'),('sign','handedness')]:
            doc,blob,body,caps,ids=fixture(change)
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,message):subdivide_body(doc,blob,body,caps,ids,selection(doc,blob,ids))
        doc,blob,body,caps,ids=fixture();bad=selection(doc,blob,ids);bad['cutFaces'].pop();bad['wholeSkinParentBodyFaceIds']=[2,3]
        with self.assertRaisesRegex(ValueError,'Every cut must match'):subdivide_body(doc,blob,body,caps,ids,bad)

    def test_original_float64_domain_cannot_be_rebuilt_from_active_float32_caps(self):
        _,_,body,caps,ids=fixture()
        fit={key:np.repeat(value[:1],45,axis=0) for key,value in body.items()}
        for key in CORNER_KEYS|{'tangents'}:fit[key][ids]=body[key]
        fit.update(sourceTriangleIds=np.arange(45,dtype=np.int64),primitiveIds=np.zeros(45,dtype=np.int64),
                   sourceCornerOrder=np.tile([0,1,2],(45,1)),tangentTriangleIds=np.arange(45,dtype=np.int64))
        selected=lineage.original_body_archive(fit,ids)
        for key in CORNER_KEYS|{'tangents'}:self.assertEqual(selected[key].tobytes(),body[key].tobytes())
        bad=copy.deepcopy(fit);bad['positions']=bad['positions'].astype(np.float32)
        with self.assertRaisesRegex(ValueError,'float64'):lineage.original_body_archive(bad,ids)
        bad=copy.deepcopy(fit);bad['sourceTriangleIds'][11]=-1
        with self.assertRaisesRegex(ValueError,'ancestry'):lineage.original_body_archive(bad,ids)

    def test_pinned_map_parent_target_and_source_face_mapping_cannot_be_substituted(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);items={}
            for name in ('source-receipt','candidate','target','source-face-map','evidence'):
                path=root/name;path.write_text(name);items[name]={'path':str(path.resolve()),'sha256':contract.sha(path)}
            parent={'receipt':{'candidate':items['candidate']['path'],'candidateSha256':items['candidate']['sha256']},
                    'childMapping':items['source-face-map']}
            valid={'sourceDiagnosticReceipt':items['source-receipt'],'sourceCandidate':items['candidate'],
                   'targetContract':items['target'],'originalSourceFaceIdsBinding':items['source-face-map'],
                   'rootReview':{'evidence':[items['evidence']]}}
            inputs={};lineage.verify_map_bindings(valid,parent,items['source-receipt']['path'],items['target']['path'],inputs)
            self.assertEqual(len(inputs),5)
            for field in ('sourceDiagnosticReceipt','sourceCandidate','targetContract','originalSourceFaceIdsBinding'):
                bad=copy.deepcopy(valid);bad[field]['sha256']='0'*64
                with self.subTest(field=field),self.assertRaises(ValueError):
                    lineage.verify_map_bindings(bad,parent,items['source-receipt']['path'],items['target']['path'],{})
            (root/'evidence').write_text('changed review evidence')
            with self.assertRaisesRegex(ValueError,'changed'):
                lineage.verify_map_bindings(valid,parent,items['source-receipt']['path'],items['target']['path'],{})
    def test_existing_canonical_guard_rejects_new_material_kind_before_geometry_use(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);target=root/'target.json';data=target_fixture();target.write_text(json.dumps(data))
            path=root/'new-material.json';path.write_text(json.dumps({'schemaVersion':2,'kind':lineage.KIND,
                'operation':lineage.OPERATION,**contract.binding(target,data,'working')}))
            with self.assertRaises(ValueError):verify_source_receipt(root/'unused.glb',path,target,data,'pelvis','working')


if __name__=='__main__':unittest.main()