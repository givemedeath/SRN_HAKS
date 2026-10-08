"""Exact declared source-face serializer corruption and material ancestry tests.

Synthetic fixtures are never body, material, generation or review evidence.
"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import target_contract as c
import replay_stage_skin_calibration as cal
import target_source_face_material_lineage as lineage
import test_stage_skin_calibration as fixtures
from place_purposebuilt_pelvis import read_glb,write_glb,accessor,BASIS
from target_part_pipeline import execute


def save(path,value):path.write_text(json.dumps(value),encoding='utf-8');return path


def fixture(root,part='shinl',parent_factory=None):
    tp,t,old_rp,old_source=fixtures.fit_fixture(root,part=part) if parent_factory is None else parent_factory(root,part)
    # Restrict this serializer protocol explicitly to real PNUT semantics.
    old_doc,old_bin=read_glb(old_source)
    if 'COLOR_0' in old_doc['meshes'][0]['primitives'][0]['attributes']:
        old_doc['meshes'][0]['primitives'][0]['attributes'].pop('COLOR_0');write_glb(old_source,old_doc,old_bin)
        old=json.loads(old_rp.read_text());old['candidateSha256']=c.sha(old_source);save(old_rp,old)
    else:old=json.loads(old_rp.read_text())
    basep=Path(old['nativeCornerArchive']['path']);base=dict(np.load(basep,allow_pickle=False));op=old_doc['meshes'][0]['primitives'][0]
    old_faces=accessor(old_doc,old_bin,op['indices']).reshape(-1,3).astype('i8');parents=np.repeat(np.arange(len(old_faces)),2)
    half=np.array([[[1,0,0],[.5,.5,0],[0,0,1]],[[.5,.5,0],[0,1,0],[0,0,1]]],float);bary=np.tile(half,(len(old_faces),1,1))
    nat={k:np.einsum('fci,fij->fcj',bary,base[k][parents]) for k in ('positions','normals','uvGltf','uvNative','tangents')}
    protected=parents==0;J=np.tile(np.eye(3),(len(parents),3,1,1));J[~protected,0,0,1]=.05
    Q=nat['positions'].copy();Q[~protected]+=np.array([.003,-.002,.001]);edited=np.any(Q!=nat['positions'],axis=2).reshape(-1);j=J.reshape(-1,3,3)
    N0=nat['normals'];N=np.linalg.solve(j.transpose(0,2,1),N0.reshape(-1,3)[:,:,None])[:,:,0]
    N*=np.linalg.norm(N0.reshape(-1,3),axis=1)[:,None]/np.linalg.norm(N,axis=1)[:,None];N[~edited]=N0.reshape(-1,3)[~edited];N=N.reshape(N0.shape);N[protected]=N0[protected]
    T0=nat['tangents'];v=np.einsum('nij,nj->ni',j,T0.reshape(-1,4)[:,:3]);unit=N.reshape(-1,3)/np.linalg.norm(N.reshape(-1,3),axis=1)[:,None];v-=(v*unit).sum(1)[:,None]*unit;v*=np.linalg.norm(T0.reshape(-1,4)[:,:3],axis=1)[:,None]/np.linalg.norm(v,axis=1)[:,None];v[~edited]=T0.reshape(-1,4)[~edited,:3];T=T0.copy();T[:,:,:3]=v.reshape(T.shape[:2]+(3,));T[protected]=T0[protected]
    archive={'positions':Q,'normals':N,'uvGltf':nat['uvGltf'],'uvNative':nat['uvNative'],'tangents':T,'connectorParentFaceIds':parents,
        'connectorBarycentricNative':bary,'connectorParentPositions':nat['positions'],'connectorParentNormals':N0,
        'connectorProtectedWholeFaceMask':protected,'connectorJacobianLocalCorners':J}
    ap=root/'native.npz';np.savez_compressed(ap,**archive)
    before={'POSITION':nat['positions']@BASIS,'NORMAL':N0@BASIS,'TEXCOORD_0':nat['uvGltf']}
    after={'POSITION':Q@BASIS,'NORMAL':N@BASIS,'TEXCOORD_0':nat['uvGltf']};a=T0.copy();a[:,:,:3]=a[:,:,:3]@BASIS;b=T.copy();b[:,:,:3]=b[:,:,:3]@BASIS;before['TANGENT']=a;after['TANGENT']=b
    doc=deepcopy(old_doc);blob=bytearray(old_bin);attrs={}
    def append(array,kind,ctype):
        array=np.asarray(array);blob.extend(b'\0'*(-len(blob)%4));start=len(blob);blob.extend(array.tobytes());doc['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':array.nbytes});doc['accessors'].append({'bufferView':len(doc['bufferViews'])-1,'count':len(array),'type':kind,'componentType':ctype});return len(doc['accessors'])-1
    for semantic in ('POSITION','NORMAL','TEXCOORD_0','TANGENT'):
        raw=lineage.original_bary(accessor(old_doc,old_bin,op['attributes'][semantic]),old_faces,parents,bary);delta=after[semantic]-before[semantic];expected=(raw+delta).astype('<f4');identity=np.all(delta==0,axis=2);expected[identity]=raw.astype('<f4')[identity];expected[protected]=raw.astype('<f4')[protected];width=expected.shape[2];attrs[semantic]=append(expected.reshape(-1,width),'VEC'+str(width),5126)
    indices=append(np.arange(len(parents)*3,dtype='<u4').reshape(-1,1),'SCALAR',5125);doc['meshes'][0]['primitives'][0]={'attributes':attrs,'indices':indices,'material':0};blob.extend(b'\0'*(-len(blob)%4));doc['buffers'][0]['byteLength']=len(blob);source=root/'candidate.glb';write_glb(source,doc,bytes(blob))
    lp=save(root/'lineage.json',{'sourceGeometry':cal.file_row(old_rp),'nativeSource':cal.file_row(basep),'originalSha256':c.sha(old_source),'allSourceFacesRetained':True,'sourceBinaryPrefixRetainedBytes':len(old_bin)})
    rec=deepcopy(old);rec.update(operation=lineage.OPERATION,source=str(old_source),sourceSha256=c.sha(old_source),sourceReceipt=str(old_rp),sourceReceiptSha256=c.sha(old_rp),candidate=str(source),candidateSha256=c.sha(source),nativeCornerArchive=cal.file_row(ap),lineage=cal.file_row(lp),sourceToAttachmentLocal=np.eye(4).tolist(),proof={'encodedRepresentationPolicy':lineage.POLICY},frozenInputs={str(tp):c.sha(tp),str(old_source):c.sha(old_source),str(old_rp):c.sha(old_rp)})
    rp=save(root/'geometry.json',rec)
    return {'tp':tp,'target':t,'rp':rp,'source':source,'rec':rec,'archive':ap,'old_rp':old_rp,'old_source':old_source,'lineage':lp}


class SourceFaceLineageTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.f=fixture(self.root)
    def tearDown(self):self.tmp.cleanup()
    def current(self):
        f=self.f;return cal.geometry_input(cal.file_row(f['source']),cal.file_row(f['rp']),f['tp'],f['target'],'shinl','working')
    def refresh_rec(self):
        f=self.f;f['rec']['candidateSha256']=c.sha(f['source']);f['rec']['nativeCornerArchive']=cal.file_row(f['archive']);save(f['rp'],f['rec'])
    def mutation(self,semantic=None,index=False,material=False,binary_prefix=False):
        f=self.f;doc,blob=read_glb(f['source']);b=bytearray(blob);pr=doc['meshes'][0]['primitives'][0]
        if material:doc['materials'][0]['normalTexture']['scale']=.5
        elif binary_prefix:b[0]^=1
        else:
            a=doc['accessors'][pr['indices'] if index else pr['attributes'][semantic]];v=doc['bufferViews'][a['bufferView']];off=v['byteOffset'];b[off]^=1
        write_glb(f['source'],doc,bytes(b));self.refresh_rec()
    def relation(self):
        f=self.f;current=self.current();material=cal.geometry_input(cal.file_row(f['old_source']),cal.file_row(f['old_rp']),f['tp'],f['target'],'shinl','working')
        src={'candidate':cal.file_row(f['source']),'geometryReceipt':cal.file_row(f['rp'])}
        ip=save(self.root/'independent.json',{'guardPass':True,'parts':{'shinl':{'candidate':cal.file_row(f['source']),'geometry':cal.file_row(f['rp'])}}})
        ap=save(self.root/'approval.json',{'kind':'reviewed-diagnostic-source-face-material-transfer','approved':True,'target':cal.file_row(f['tp']),'parts':{'shinl':src},'materialOrClientAccepted':False})
        row={'schemaVersion':1,'kind':lineage.LINEAGE_KIND,'diagnosticOnly':True,**c.binding(f['tp'],f['target'],'working'),'part':'shinl','serializerProtocol':lineage.PROTOCOL,
             'materialSource':{'candidate':cal.file_row(f['old_source']),'geometryReceipt':cal.file_row(f['old_rp'])},'currentWorkingSource':src,'nativeCornerArchive':f['rec']['nativeCornerArchive'],'sourceLineage':f['rec']['lineage'],
             'independentGeometryReplay':cal.file_row(ip),'diagnosticAuthorization':cal.file_row(ap)}
        lp=save(self.root/'recipient.json',row);return current,material,lp,row,ap
    def test_exact_serializer_proves_both_distinct_uv_representations(self):
        v=self.current();p=v['serializationProof'];self.assertEqual(p['kind'],lineage.PROTOCOL);self.assertEqual(p['sourceUVBarycentricAreaCoverageMaximumError'],0);self.assertTrue(all(r['literalBytesExact'] for r in p['attributes'].values()));self.assertEqual(p['currentFaces'],2*p['originalFaces'])
        with np.load(self.f['archive']) as z:
            g=json.loads(self.f['old_rp'].read_text())
            with np.load(g['nativeCornerArchive']['path']) as old:
                expected=np.einsum('fci,fij->fcj',z['connectorBarycentricNative'],old['uvNative'][z['connectorParentFaceIds']])
            np.testing.assert_array_equal(z['uvNative'],expected)
        # Show why rounded candidate UV must not replace native-double ancestry.
        values=np.array([.8012744784355164,.5821620225906372],dtype='f4')
        self.assertNotEqual(float((1-values).astype(float).mean().astype('f4')),float(1-values.astype(float).mean().astype('f4')))
    def test_actual_attribute_and_index_corruption_rejected_even_when_candidate_hash_updated(self):
        original=self.f['source'].read_bytes()
        for semantic in ('POSITION','NORMAL','TEXCOORD_0','TANGENT'):
            with self.subTest(semantic=semantic):
                self.f['source'].write_bytes(original);self.mutation(semantic=semantic)
                with self.assertRaisesRegex(ValueError,'serialized byte replay'):self.current()
        self.f['source'].write_bytes(original);self.mutation(index=True)
        with self.assertRaisesRegex(ValueError,'corner index'):self.current()
    def test_original_bin_and_material_definition_remain_strict(self):
        original=self.f['source'].read_bytes()
        self.mutation(material=True)
        with self.assertRaisesRegex(ValueError,'material definition'):self.current()
        self.f['source'].write_bytes(original);self.mutation(binary_prefix=True)
        with self.assertRaisesRegex(ValueError,'BIN prefix'):self.current()
    def test_native_uv_normal_jacobian_parent_and_barycentric_corruptions_rejected(self):
        original=self.f['archive'].read_bytes()
        for key,action in [('uvNative',lambda a:a.__setitem__((0,0,1),a[0,0,1]+.01)),('normals',lambda a:a.__setitem__((2,0,0),a[2,0,0]+.01)),('connectorJacobianLocalCorners',lambda a:a.__setitem__((2,0,0,0),-1)),('connectorParentFaceIds',lambda a:a.__setitem__(0,99999)),('connectorBarycentricNative',lambda a:a.__setitem__((0,0,0),.5))]:
            self.f['archive'].write_bytes(original)
            with np.load(self.f['archive']) as z:d={k:z[k].copy() for k in z.files}
            action(d[key]);np.savez_compressed(self.f['archive'],**d);self.refresh_rec()
            with self.subTest(key=key),self.assertRaises(ValueError):self.current()
    def test_wrong_protocol_target_part_and_coordinate_do_not_fallback(self):
        self.f['rec']['proof']['encodedRepresentationPolicy']='generic-float-tolerance';save(self.f['rp'],self.f['rec'])
        with self.assertRaisesRegex(ValueError,'serializer operation'):self.current()
        self.f['rec']['proof']['encodedRepresentationPolicy']=lineage.POLICY;save(self.f['rp'],self.f['rec'])
        for part,space in [('shinr','working'),('shinl','runtime')]:
            with self.subTest(part=part,space=space),self.assertRaises(ValueError):cal.geometry_input(cal.file_row(self.f['source']),cal.file_row(self.f['rp']),self.f['tp'],self.f['target'],part,space)
    def test_explicit_immediate_material_recipient_and_authorization(self):
        current,material,p,r,ap=self.relation();proof=cal.material_lineage(current,material,self.f['tp'],self.f['target'],'shinl','working',cal.file_row(p));self.assertEqual(proof['kind'],'single-explicit-source-face-original-material-recipient');self.assertFalse(proof['originalParentManifestRelabeled'])
        authorization=json.loads(ap.read_text());authorization['approved']=False;save(ap,authorization);r['diagnosticAuthorization']=cal.file_row(ap);save(p,r)
        with self.assertRaisesRegex(ValueError,'authorization'):cal.material_lineage(current,material,self.f['tp'],self.f['target'],'shinl','working',cal.file_row(p))
    def test_stale_or_cross_part_material_relation_rejected(self):
        current,material,p,r,_=self.relation()
        for key,value in [('part','shinr'),('schemaVersion',True),('serializerProtocol','unreviewed'),('coordinateSpace','runtime')]:
            bad=deepcopy(r);bad[key]=value;save(p,bad)
            with self.subTest(key=key),self.assertRaises(ValueError):cal.material_lineage(current,material,self.f['tp'],self.f['target'],'shinl','working',cal.file_row(p))
        bad=deepcopy(r);bad['currentWorkingSource']['candidate']=cal.file_row(self.f['old_source']);save(p,bad)
        with self.assertRaisesRegex(ValueError,'Stale/cross'):cal.material_lineage(current,material,self.f['tp'],self.f['target'],'shinl','working',cal.file_row(p))
    def test_calibration_samples_actual_recipient_glb_uv_without_altering_detail_parent(self):
        import replay_stage_skin_detail as detail
        current,material,p,r,_=self.relation();f=self.f
        from target_part_stage import material_inputs
        rows,transport=material_inputs(material['document'],material['binary'],{0:'skin'},'shinl',0,c.fixed_garment_parts(f['target']))
        fake={'document':material['document'],'binary':material['binary'],'materialRows':rows,'originalMaterialProof':transport,'proof':{'synthetic':True},'frozenInputs':{}}
        parent={'mode':'original-source-uv-detail-v1','controls':{'mode':'original-source-uv-detail-v1','receipt':cal.file_row(p),'sourceManifest':cal.file_row(p)}}
        ms={'candidate':cal.file_row(f['old_source']),'geometryReceipt':cal.file_row(f['old_rp']),'coordinateSpace':'working','lineageReceipt':cal.file_row(p)}
        recipe=fixtures.recipe_value(f['tp'],f['target'],f['rp'],f['source'],'shinl',parent,rows['skin']['intensity'],material=ms);rp=save(self.root/'calibration.json',recipe)
        with patch.object(detail,'staging_inputs',return_value=fake) as spy:
            v=cal.staging_inputs({'mode':cal.MODE,'recipe':cal.file_row(rp)},f['tp'],f['target'],'shinl','working',f['source'],f['rp'],None,0)
        self.assertEqual(spy.call_args.args[5],f['old_source']);self.assertEqual(v['document'],current['document']);self.assertEqual(v['binary'],current['binary']);np.testing.assert_array_equal(v['materialRows']['skin']['normal'],rows['skin']['normal']);self.assertEqual(v['proof']['sourceGeometrySerializationProof']['kind'],lineage.PROTOCOL)
    def test_exactly_one_material_recipient_then_single_runtime_identity(self):
        current,material,p,r,_=self.relation();f=self.f
        cfg={'schemaVersion':2,'operation':'runtime','part':'shinl','coordinateSpace':'runtime','targetContract':str(f['tp']),'targetContractSha256':c.sha(f['tp']),
            'source':str(f['source']),'sourceSha256':c.sha(f['source']),'sourceReceipt':str(f['rp']),'sourceReceiptSha256':c.sha(f['rp'])}
        runtime_rp=execute(save(self.root/'runtime-config.json',cfg),self.root/'runtime');rr=json.loads(runtime_rp.read_text());runtime=cal.geometry_input(cal.file_row(rr['candidate']),cal.file_row(runtime_rp),f['tp'],f['target'],'shinl','runtime')
        proof=cal.material_lineage(runtime,material,f['tp'],f['target'],'shinl','runtime',cal.file_row(p));self.assertEqual(proof['runtimeConversions'],1);self.assertEqual(proof['sourceFaceOperations'],1)
        rr['statureApplications']=2;save(runtime_rp,rr)
        with self.assertRaises(ValueError):cal.geometry_input(cal.file_row(rr['candidate']),cal.file_row(runtime_rp),f['tp'],f['target'],'shinl','runtime')

if __name__=='__main__':unittest.main()