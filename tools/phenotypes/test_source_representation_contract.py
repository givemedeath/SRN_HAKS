"""Portable exact representation contracts; all assets are synthetic."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import unittest
import numpy as np

import source_representation_contract as representation
import target_contract as contract
from place_purposebuilt_pelvis import read_glb, write_glb, raw_corners
from test_execution_adoption import ExecutionFixture
from test_mirror_stock_limb_part import fixture

REPO = Path(__file__).resolve().parents[2]


class RepresentationFixture:
    def __init__(self, owner, absent=False, archive_mutator=None, source_without_tangent=False):
        self.f = f = ExecutionFixture(owner)
        self.part = 'chest' if absent else 'bicepl'
        source_doc, source_bin = read_glb(f.local_source)
        for pr in source_doc['meshes'][0]['primitives']:
            pr['attributes'].pop('COLOR_0',None)
        if absent:
            for pr in source_doc['meshes'][0]['primitives']:
                pr['attributes'].pop('TANGENT', None)
        for path in (f.external_source, f.local_source, f.saved_source):
            write_glb(path, source_doc, source_bin)
        digest = contract.sha(f.local_source)
        f.proof['assetSourceMappings'][0]['originalClaimedSource']['sha256'] = digest
        f.proof['assetSourceMappings'][0]['worktreeRelativeCopy']['sha256'] = digest
        for row in f.documents.values():
            row['sourceSha256'] = digest
            row['frozenInputs'][row['source']] = digest
        candidate_doc = copy.deepcopy(source_doc)
        candidate_doc['nodes'] = [{'name':'detached_geometry','mesh':0}]
        for part, path in f.candidates.items():
            write_glb(path, candidate_doc, source_bin)
            f.documents[part]['candidateSha256'] = contract.sha(path)
        extra = {}
        p, n, u, _ = raw_corners(candidate_doc, source_bin, extra=extra)
        un = u.copy(); un[:, :, 1] = 1-un[:, :, 1]
        arrays = dict(positions=p, normals=n, uvGltf=u, uvNative=un)
        if not absent:
            arrays['authoredTangents'] = np.concatenate(extra['TANGENT']['rows'])
        self.archive = f.out/(self.part+'-representation-corners.npz')
        if archive_mutator is not None:archive_mutator(arrays)
        np.savez(self.archive, **arrays)
        row = f.documents[self.part]
        row['nativeCornerArchive'] = f.pin(self.archive)
        row['frozenInputs'][str(self.archive)] = contract.sha(self.archive)
        f.seal()
        current = {str(p):contract.sha(p) for p in representation.current_helper_paths() if p.parent==Path(representation.__file__).resolve().parent}
        f.proof['currentHelpers'].update(current)
        reconciliation = Path(f.proof['reconciliation']['path'])
        record = json.loads(reconciliation.read_text())
        record['helpers'] = {p:{'sha256':h,'features':['Exact representation current pure array proof']}
                            for p,h in f.proof['currentHelpers'].items()}
        f.write(reconciliation, record)
        f.proof['reconciliation'] = f.pin(reconciliation)
        f.save()
        receipt = f.documents[self.part]
        receipt_pin = f.pin(f.part_paths[self.part])
        closure = dict(receipt['frozenInputs'])
        closure.update({str(f.part_paths[self.part]):receipt_pin['sha256'],
                        str(f.candidates[self.part]):receipt['candidateSha256'],
                        str(self.archive):contract.sha(self.archive)})
        self.document = {
            'schemaVersion':1, 'kind':representation.KIND, 'operation':representation.OPERATION,
            'verificationApplications':1, 'targetContract':f.pin(f.target_path),
            'targetId':f.target['id'], 'rigRevision':f.target['rig']['revision'],
            'coordinateSpace':'working','part':self.part,
            'joint':contract.PART_JOINTS[self.part],'model':contract.model(f.target,self.part),
            'statureApplications':0,
            'protocol':'absent-authored-tangent-direct-encoded-v1' if absent else 'literal-exact-v1',
            'candidate':f.pin(f.candidates[self.part]), 'geometryReceipt':receipt_pin,
            'nativeCornerArchive':f.pin(self.archive), 'adoptionProof':f.pin(f.proof_path),
            'inputReceipts':[receipt_pin],
            'currentCodeSupport':{str(p):contract.sha(p) for p in representation.current_helper_paths() if p.parent!=Path(representation.__file__).resolve().parent},
            'protocolInputs':{'parentCandidate':{'path':receipt['source'],'sha256':receipt['sourceSha256']}},
            'sourceClosure':closure,'ancestorContract':None}
        self.path = f.out/'representation.json'
        if source_without_tangent:
            d,b=read_glb(f.local_source)
            for pr in d['meshes'][0]['primitives']:pr['attributes'].pop('TANGENT',None)
            for source in (f.external_source,f.local_source,f.saved_source):write_glb(source,d,b)
            digest=contract.sha(f.local_source)
            f.proof['assetSourceMappings'][0]['originalClaimedSource']['sha256']=digest
            f.proof['assetSourceMappings'][0]['worktreeRelativeCopy']['sha256']=digest
            for receipt in f.documents.values():
                receipt['sourceSha256']=digest;receipt['frozenInputs'][receipt['source']]=digest
            f.seal()
            r=f.documents[self.part];rp=f.pin(f.part_paths[self.part])
            closure=dict(r['frozenInputs']);closure.update({str(f.part_paths[self.part]):rp['sha256'],
                str(f.candidates[self.part]):r['candidateSha256'],str(self.archive):contract.sha(self.archive)})
            self.document.update(geometryReceipt=rp,inputReceipts=[rp],sourceClosure=closure,
                adoptionProof=f.pin(f.proof_path),protocolInputs={'parentCandidate':{'path':r['source'],'sha256':digest}})
        self.save()

    def save(self):
        self.f.write(self.path, self.document)
        self.pin = self.f.pin(self.path)

    def verify(self, **kw):
        return representation.verify_source_representation(self.pin,
            target_path=self.f.target_path, target=self.f.target,
            part=kw.get('part',self.part), space=kw.get('space','working'))


class ContractTests(unittest.TestCase):
    def setUp(self): self.x = RepresentationFixture(self)

    def test_literal_encoded_arrays_are_exact_and_history_immutable(self):
        x = self.x; before={p:p.read_bytes() for p in
            [x.f.bank_path,x.f.proof_path,*x.f.part_paths.values(),*x.f.candidates.values(),x.archive]}
        result=x.verify()
        self.assertTrue(result.proof['protocolProof']['literalPNUTBytesExact'])
        np.testing.assert_array_equal(result.array('positions'),
            np.load(x.archive,allow_pickle=False)['positions'])
        self.assertFalse(result.array('positions').flags.writeable)
        with self.assertRaises(ValueError): result.array('positions').setflags(write=True)
        with self.assertRaises(TypeError): result.proof['part']='handr'
        for p,b in before.items(): self.assertEqual(p.read_bytes(),b)
        self.assertFalse(x.f.sentinel.exists())

    def test_missing_external_original_uses_exact_verified_relative_copy(self):
        self.x.f.external_source.unlink()
        result=self.x.verify()
        self.assertNotIn(str(self.x.f.external_source),result.inputs)
        self.assertIn(str(self.x.f.local_source),result.inputs)
        self.assertFalse(self.x.f.sentinel.exists())

    def test_defaults_remain_stale_rejecting_without_context(self):
        import target_part_pipeline as pipeline
        with self.assertRaises(ValueError):
            pipeline.verify_source_receipt(self.x.f.candidates[self.x.part],
                self.x.f.part_paths[self.x.part],self.x.f.target_path,
                self.x.f.target,self.x.part,'working')

    def test_absent_authored_t_remains_absent_in_all_representations(self):
        x=RepresentationFixture(self,absent=True)
        result=x.verify()
        self.assertEqual(result.proof['protocolProof']['authoredTangentStatus'],'absent')
        with self.assertRaises(KeyError): result.array('tangents')
        self.assertFalse(x.f.sentinel.exists())


    def test_native_archive_dtype_and_shape_are_not_coerced(self):
        for name in ('positions','normals','uvGltf','uvNative','authoredTangents'):
            x=RepresentationFixture(self,archive_mutator=lambda rows,key=name:rows.update({key:rows[key].astype('<f4')}))
            with self.subTest(name=name),self.assertRaises(ValueError):x.verify()
        x=RepresentationFixture(self,archive_mutator=lambda rows:rows.update(normals=rows['normals'][:-1]))
        with self.assertRaises(ValueError):x.verify()

    def test_literal_cannot_invent_source_tangents(self):
        x=RepresentationFixture(self,source_without_tangent=True)
        with self.assertRaises(ValueError):x.verify()

    def test_wrong_part_and_runtime_space_rejected(self):
        for kw in ({'part':'bicepr'},{'space':'runtime'}):
            with self.subTest(kw=kw),self.assertRaises(ValueError): self.x.verify(**kw)

    def test_typed_singular_scope_and_protocol_corruptions(self):
        changes=[
            ('schemaVersion',True),('verificationApplications',True),
            ('verificationApplications',2),('statureApplications',1),
            ('coordinateSpace','runtime'),('targetId','cross-target'),
            ('rigRevision','stale'),('joint','rhand_g'),('model','pmh0_bicepl001'),
            ('protocol','generic-nearest-tolerance-v1')]
        original=copy.deepcopy(self.x.document)
        for key,value in changes:
            self.x.document=copy.deepcopy(original);self.x.document[key]=value;self.x.save()
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):self.x.verify()

    def test_current_support_import_missing_extra_or_stale_rejected(self):
        original=copy.deepcopy(self.x.document)
        for change in ('missing','extra','stale'):
            self.x.document=copy.deepcopy(original)
            support=self.x.document['currentCodeSupport']
            if change=='missing':support.clear()
            elif change=='extra':support[str(self.x.f.old_helper)]='0'*64
            else:support[next(iter(support))]='0'*64
            self.x.save()
            with self.subTest(change=change),self.assertRaises(ValueError):self.x.verify()

    def test_extra_contract_or_equation_fields_rejected(self):
        original=copy.deepcopy(self.x.document)
        for field in ('unknown','protocol'):
            self.x.document=copy.deepcopy(original)
            if field=='unknown':self.x.document['fallbackTolerance']=1e-6
            else:self.x.document['protocolInputs']['inventedTangent']='forbidden'
            self.x.save()
            with self.subTest(field=field),self.assertRaises(ValueError):self.x.verify()

    def test_stale_current_code_pin_rejected(self):
        proof=self.x.f.proof
        proof['currentHelpers'][str(Path(representation.__file__).resolve())]='0'*64
        self.x.f.save();self.x.document['adoptionProof']=self.x.f.pin(self.x.f.proof_path);self.x.save()
        with self.assertRaises(ValueError):self.x.verify()

    def test_source_closure_missing_or_digest_changed_rejected(self):
        original=copy.deepcopy(self.x.document)
        for mutate in ('missing','changed'):
            self.x.document=copy.deepcopy(original)
            p=next(iter(self.x.document['sourceClosure']))
            if mutate=='missing':self.x.document['sourceClosure'].pop(p)
            else:self.x.document['sourceClosure'][p]='0'*64
            self.x.save()
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.x.verify()

    def test_candidate_archive_and_local_copy_drift_rejected(self):
        for p in (self.x.f.candidates[self.x.part],self.x.archive,self.x.f.local_source):
            original=p.read_bytes();p.write_bytes(original+b'drift')
            with self.subTest(path=p.name),self.assertRaises(ValueError):self.x.verify()
            p.write_bytes(original)

    def test_verified_result_detects_input_drift(self):
        result=self.x.verify()
        p=self.x.f.local_source;p.write_bytes(p.read_bytes()+b'drift')
        with self.assertRaises(ValueError):result.verify()


class ExactArrayAndDecoderTests(unittest.TestCase):
    def test_one_word_and_signed_zero_and_dtype_corruptions_rejected(self):
        a=np.array([0.,1.],dtype='<f4')
        changes=[np.array([-0.,1.],dtype='<f4'),a.astype('<f8'),
                 np.array([0.,np.nextafter(np.float32(1),np.float32(2))],dtype='<f4')]
        for b in changes:
            with self.subTest(dtype=b.dtype,bytes=b.tobytes()),self.assertRaises(ValueError):
                representation.equal(a,b,'word')

    def test_index_winding_and_shape_are_not_nearest_equivalent(self):
        a=np.array([[0,1,2]],dtype='i8')
        for b in (a[:,[0,2,1]],a.reshape(-1)):
            with self.assertRaises(ValueError):representation.equal(a,b,'indices')

    def test_accessor_out_of_view_bounds_and_truncated_stride_rejected(self):
        doc,binary=fixture();i=doc['meshes'][0]['primitives'][0]['attributes']['POSITION']
        for change in ('length','stride','count'):
            d=copy.deepcopy(doc);v=d['bufferViews'][d['accessors'][i]['bufferView']]
            if change=='length':v['byteLength']=4
            elif change=='stride':v['byteStride']=2
            else:d['accessors'][i]['count']=10**7
            with self.subTest(change=change),self.assertRaises(ValueError):
                representation.accessor(d,binary,i)

    def test_accessor_nonfinite_and_wrong_count_rejected(self):
        doc,binary=fixture();i=doc['meshes'][0]['primitives'][0]['attributes']['POSITION']
        view=doc['bufferViews'][doc['accessors'][i]['bufferView']]
        changed=bytearray(binary);struct.pack_into('<f',changed,view.get('byteOffset',0),float('nan'))
        with self.assertRaises(ValueError):representation.accessor(doc,changed,i)
        doc['accessors'][i]['count']=0
        with self.assertRaises(ValueError):representation.accessor(doc,binary,i)

    def test_static_mesh_rejects_morph_wrong_mode_and_tangent_sign(self):
        doc,binary=fixture()
        doc['meshes'][0]['primitives'][0]['attributes'].pop('COLOR_0')
        for kind in ('morph','mode','sign'):
            d=copy.deepcopy(doc);b=bytearray(binary);pr=d['meshes'][0]['primitives'][0]
            if kind=='morph':pr['targets']=[{'POSITION':0}]
            elif kind=='mode':pr['mode']=1
            else:
                a=d['accessors'][pr['attributes']['TANGENT']]
                start=d['bufferViews'][a['bufferView']].get('byteOffset',0)
                struct.pack_into('<f',b,start+12,0)
            with self.subTest(kind=kind),self.assertRaises(ValueError):representation.mesh(d,b)

    def test_original_material_sampler_and_bin_prefix_protected(self):
        doc,binary=fixture()
        for kind in ('binary','material','sampler','owner'):
            d=copy.deepcopy(doc);b=binary
            if kind=='binary':b=bytes([binary[0]^1])+binary[1:]
            elif kind=='material':d['materials'][0]['name']='changed'
            elif kind=='owner':d['meshes'][0]['primitives'][0]['material']=99
            else:d['samplers']=[{'wrapS':33071}]
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                representation.preservation(d,b,doc,binary)

    def test_native_complement_uses_promoted_encoded_float32(self):
        aa=[dict(POSITION=np.array([[0,0,0],[1,0,0],[0,1,0]],dtype='<f4'),
             NORMAL=np.array([[0,0,1]]*3,dtype='<f4'),
             TEXCOORD_0=np.array([[.23,.37],[.61,.78],[.19,.91]],dtype='<f4'))]
        ff=[np.array([[0,1,2]],dtype='i8')]
        result=representation.corners(aa,ff)
        expected=1-aa[0]['TEXCOORD_0'][ff[0]][:,:,1].astype('<f8')
        representation.equal(expected,result['uvNative'][:,:,1],'promoted complement')
        self.assertNotIn('tangents',result)

    def test_mixed_tangent_primitive_presence_rejected(self):
        a=dict(POSITION=np.array([[0,0,0],[1,0,0],[0,1,0]],dtype='<f4'),
               NORMAL=np.array([[0,0,1]]*3,dtype='<f4'),
               TEXCOORD_0=np.zeros((3,2),dtype='<f4'))
        b=copy.deepcopy(a);b['TANGENT']=np.array([[1,0,0,1]]*3,dtype='<f4')
        with self.assertRaises(ValueError):
            representation.corners([a,b],[np.array([[0,1,2]]),np.array([[0,1,2]])])

    def test_duplicate_and_nonfinite_json_rejected(self):
        for raw in ('{"part":"legl","part":"legr"}','{"scale":NaN}','{"a":Infinity}'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):representation.decode_json(raw)

    def test_color0_is_explicitly_unsupported(self):
        doc,binary=fixture()
        with self.assertRaises(ValueError):representation.mesh(doc,binary)

    def test_accessor_unaligned_word_rejected(self):
        doc,binary=fixture();i=doc['meshes'][0]['primitives'][0]['attributes']['POSITION']
        doc['accessors'][i]['byteOffset']=1
        with self.assertRaises(ValueError):representation.accessor(doc,binary,i)

    def test_current_image_view_redirection_rejected(self):
        doc,binary=fixture();d=copy.deepcopy(doc)
        view=d['images'][0]['bufferView']
        d['bufferViews'][view]['byteOffset']=0
        with self.assertRaises(ValueError):representation.preservation(d,binary,doc,binary)

def knee_arrays(complement=False):
    """Independent two-child planar triangle with a protected whole child."""
    old=dict(POSITION=np.array([[0,0,0],[.6,0,0],[0,.5,0]],dtype='<f4'),
        NORMAL=np.array([[0,0,1.25]]*3,dtype='<f4'),
        TANGENT=np.array([[1.2,0,0,-1]]*3,dtype='<f4'),
        TEXCOORD_0=np.array([[.23,.37],[.61,.78],[.19,.91]],dtype='<f4'))
    f=np.array([[0,1,2]],dtype='i8')
    basis=np.array([[1.,0,0],[0,0,-1],[0,1,0]])
    base=dict(positions=(old['POSITION'].astype(float)@basis.T)[f],
              normals=(old['NORMAL'].astype(float)@basis.T)[f],
              uvGltf=old['TEXCOORD_0'][f].astype(float))
    base['uvNative']=base['uvGltf'].copy();base['uvNative'][:,:,1]=1-base['uvNative'][:,:,1]
    base['tangents']=old['TANGENT'][f].astype(float)
    base['tangents'][:,:,:3]=base['tangents'][:,:,:3]@basis.T
    w=np.array([[[1,0,0],[.5,.5,0],[0,0,1]],
                [[.5,.5,0],[0,1,0],[0,0,1]]],dtype='f8')
    parents=np.array([0,0],dtype='i8')
    native={k:np.einsum('fci,fij->fcj',w,v[parents]) for k,v in base.items()}
    z={k:v.copy() for k,v in native.items()}
    z['positions'][0,:,0]*=1.2
    j=np.tile(np.eye(3),(2,3,1,1));j[0,:,0,0]=1.2
    z.update(connectorParentFaceIds=parents,connectorBarycentricNative=w,
        connectorProtectedWholeFaceMask=np.array([False,True]),
        connectorParentPositions=native['positions'].copy(),
        connectorParentNormals=native['normals'].copy(),
        connectorJacobianLocalCorners=j)
    expected={}
    for sem,key in (('POSITION','positions'),('NORMAL','normals'),('TEXCOORD_0','uvGltf'),('TANGENT','tangents')):
        raw=np.einsum('fci,fij->fcj',w,old[sem][f[parents]].astype(float))
        before=native[key].copy();after=z[key].copy()
        if sem in ('POSITION','NORMAL'):before=before@basis;after=after@basis
        if sem=='TANGENT':before[:,:,:3]=before[:,:,:3]@basis;after[:,:,:3]=after[:,:,:3]@basis
        delta=after-before
        value=(raw+delta).astype('<f4');zero=np.all(delta==0,axis=2)
        value[zero]=raw.astype('<f4')[zero];value[1]=raw.astype('<f4')[1]
        expected[sem]=value.reshape(-1,value.shape[-1])
    if complement:
        for sem,key in (('POSITION','positions'),('NORMAL','normals')):
            expected[sem]=(z[key]@basis).astype('<f4').reshape(-1,3)
        value=z['tangents'].copy();value[:,:,:3]=value[:,:,:3]@basis
        expected['TANGENT']=value.astype('<f4').reshape(-1,4)
        value=z['uvNative'].copy();value[:,:,1]=1-value[:,:,1]
        expected['TEXCOORD_0']=value.astype('<f4').reshape(-1,2)
    return z,base,[expected],[np.arange(6,dtype='i8').reshape(-1,3)],[old],[f]


class NamedEquationTests(unittest.TestCase):
    def test_thigh_raw_barycentric_native_delta_exact(self):
        args=knee_arrays()
        proof=representation.knee(*args)
        self.assertTrue(proof['rawPNUTBytesExact'])
        self.assertTrue(proof['nativeTransportBytesExact'])
        self.assertEqual(proof['protectedWholeFaces'],1)

    def test_shin_dual_uv_lineages_and_complement_exact(self):
        args=knee_arrays(complement=True)
        proof=representation.knee(*args,complement=True)
        self.assertTrue(proof['nativeTransportBytesExact'])
        self.assertIn('decoded GLB UV',proof['sampledUV'])

    def test_named_equations_reject_one_word_geometry_uv_tangent_sign(self):
        for complement in (False,True):
            for semantic in ('POSITION','NORMAL','TEXCOORD_0','TANGENT'):
                args=knee_arrays(complement);a=args[2][0][semantic]
                a.flat[0]=np.nextafter(a.flat[0],np.float32(10))
                with self.subTest(complement=complement,semantic=semantic),self.assertRaises(ValueError):
                    representation.knee(*args,complement=complement)
            args=knee_arrays(complement);args[2][0]['TANGENT'][0,3]=1
            with self.assertRaises(ValueError):representation.knee(*args,complement=complement)

    def test_parent_coverage_winding_and_protected_mask_corruptions(self):
        for kind in ('coverage','winding','protected','nativeUV','jacobian','cornerorder'):
            args=knee_arrays();z=args[0]
            if kind=='coverage':z['connectorParentFaceIds']=np.array([0,1],dtype='i8')
            elif kind=='winding':z['connectorBarycentricNative'][0]=z['connectorBarycentricNative'][0,[0,2,1]]
            elif kind=='protected':z['connectorProtectedWholeFaceMask'][0]=True
            elif kind=='nativeUV':z['uvNative'][0,0,1]=np.nextafter(z['uvNative'][0,0,1],np.float64(10))
            elif kind=='jacobian':z['connectorJacobianLocalCorners'][0,0,0,0]=-1
            else:args[3][0][0]=args[3][0][0,[0,2,1]]
            with self.subTest(kind=kind),self.assertRaises((ValueError,IndexError)):
                representation.knee(*args)

    def test_stock_derived_mirror_rejects_self_declared_oblique_involution(self):
        old=knee_arrays()[4][0];oldf=knee_arrays()[5][0]
        left_frame=np.eye(4);right_frame=np.eye(4)
        left_frame[0,3]=.3;right_frame[0,3]=-.3
        target={'rig':{'frames':{'working':{'lthigh_g':left_frame.tolist(),'rthigh_g':right_frame.tolist()}}}}
        reflection=np.diag([-1.,1.,1.,1.])
        expected=np.linalg.inv(right_frame)@reflection@left_frame
        parent={'part':'legr','operation':'mirror','reflectionWorld':reflection.tolist(),
                'proof':{'sourceToRightLocal':expected.tolist()}}
        config={'kind':'target-thigh-width-diagnostic','schemaVersion':2,'widthFactor':.78,'mirrorPlaneWorldX':0.}
        aa=copy.deepcopy(old);aa['POSITION'][:,0]*=-1;aa['NORMAL'][:,0]*=-1
        aa['TANGENT'][:,0]*=-1;aa['TANGENT'][:,3]*=-1
        aa['POSITION'][old['POSITION'][:,0]==0,0]=0
        aa['NORMAL'][old['NORMAL'][:,0]==0,0]=0
        representation.mirror_parent(parent,{'part':'legl'},[aa],[oldf[:,[0,2,1]]],[old],[oldf],target,config)
        oblique=reflection.copy();oblique[0,1]=2
        self.assertTrue(np.array_equal(oblique@oblique,np.eye(4)))
        parent['reflectionWorld']=oblique.tolist()
        parent['proof']['sourceToRightLocal']=(np.linalg.inv(right_frame)@oblique@left_frame).tolist()
        with self.assertRaises(ValueError):
            representation.mirror_parent(parent,{'part':'legl'},[aa],[oldf[:,[0,2,1]]],[old],[oldf],target,config)

def pelvis_arrays():
    """One explicit triangle, six horizontal splits, independent analytic field."""
    raw=dict(POSITION=np.array([[0,0,0],[.1,.1,0],[0,.1,.1]],dtype='<f4'),
             NORMAL=np.array([[0,0,1.25]]*3,dtype='<f4'),
             TANGENT=np.array([[1.2,0,0,1]]*3,dtype='<f4'),
             TEXCOORD_0=np.array([[.1,.2],[.7,.2],[.1,.8]],dtype='<f4'))
    faces=np.array([[0,1,2]],dtype='i8')
    base=representation.corners([raw],[faces])
    base={k:base[k] for k in ('positions','normals','uvGltf','uvNative','tangents')}
    cfg=dict(subdivisionPlanesLocalZMetres=[.02,.03,.04,.05,.06,.07],
             planeLocalZMetres=.02,fullScaleLocalZMetres=.07,
             centreLocalXYMetres=[0.,0.],endXYScale=[.9,.8])
    split=representation.subdivide(raw,faces,cfg['subdivisionPlanesLocalZMetres'],base)
    line=dict(steps=split['steps'],originalRowCount=3,previewNativeBarycentricDifferenceExplicit=True)
    basis=np.array([[1.,0,0],[0,0,-1],[0,1,0]])
    plane=float(np.float32(.02));full=.07
    def analytic(p):
        u=np.clip((p[:,2]-plane)/(full-plane),0,1)
        h=u*u*(3-2*u);dh=6*u*(1-u)/(full-plane)
        delta=1-np.asarray(cfg['endXYScale'])
        scale=1-h[:,None]*delta
        q=p.copy();q[:,:2]=p[:,:2]*scale
        j=np.tile(np.eye(3),(len(p),1,1))
        j[:,0,0]=scale[:,0];j[:,1,1]=scale[:,1]
        j[:,:2,2]=-p[:,:2]*delta*dh[:,None]
        protected=p[:,2]<=plane;q[protected]=p[protected];j[protected]=np.eye(3)
        return q,j
    def analytic_nt(n,t,j,edited):
        length=np.linalg.norm(n,axis=1)
        nn=np.einsum('nij,nj->ni',np.linalg.inv(j).transpose(0,2,1),n)
        nn*=(length/np.linalg.norm(nn,axis=1))[:,None];nn[~edited]=n[~edited]
        v=np.einsum('nij,nj->ni',j,t[:,:3]);unit=nn/length[:,None]
        v-=np.sum(v*unit,axis=1)[:,None]*unit
        v*=(np.linalg.norm(t[:,:3],axis=1)/np.linalg.norm(v,axis=1))[:,None]
        tt=t.copy();tt[:,:3]=v;tt[~edited]=t[~edited]
        return nn,tt
    attrs=split['attributes'];f=split['faces'];local=attrs['POSITION'].astype(float)@basis.T
    q,j=analytic(local);active=np.zeros(len(local),bool);active[np.unique(f)]=True
    q[~active]=local[~active];j[~active]=np.eye(3)
    edited=active&np.any(q!=local,axis=1)
    n0=attrs['NORMAL'].astype(float)@basis.T
    t0=attrs['TANGENT'].astype(float).copy();t0[:,:3]=t0[:,:3]@basis.T
    n,tt=analytic_nt(n0,t0,j,edited)
    aa={k:v.copy() for k,v in attrs.items()}
    aa['POSITION'][edited]=(q[edited]@basis).astype('<f4')
    aa['NORMAL'][edited]=(n[edited]@basis).astype('<f4')
    tt[:,:3]=tt[:,:3]@basis;aa['TANGENT'][edited]=tt[edited].astype('<f4')
    native=split['nativeValues'];p=native['positions'].reshape(-1,3)
    qp,jp=analytic(p);en=np.any(qp!=p,axis=1)
    nn,nt=analytic_nt(native['normals'].reshape(-1,3),
                      native['tangents'].reshape(-1,4),jp,en)
    z=dict(positions=qp.reshape(native['positions'].shape),
           normals=nn.reshape(native['normals'].shape),
           tangents=nt.reshape(native['tangents'].shape),
           uvGltf=native['uvGltf'].copy(),uvNative=native['uvNative'].copy(),
           connectorParentFaces=faces.copy(),connectorSplitFaces=f.copy(),
           connectorParentFaceIds=split['parentFaceIds'].copy(),
           connectorBarycentricPreview=split['barycentric'].copy(),
           connectorBarycentricNative=split['nativeBarycentric'].copy(),
           connectorLowerFaceMask=split['lowerFaceMask'].copy(),
           connectorJacobianLocal=j.copy(),connectorEditedVertexMask=edited.copy())
    return z,base,[aa],[f],[raw],[faces],line,cfg


class PelvisEquationTests(unittest.TestCase):
    def test_six_sequential_float32_planes_and_dual_native_field(self):
        args=pelvis_arrays()
        self.assertEqual([r['childFaces'] for r in args[6]['steps']],[3,7,13,21,31,43])
        self.assertEqual(len(args[3][0]),43)
        for plane in args[7]['subdivisionPlanesLocalZMetres']:
            self.assertIn(float(np.float32(plane)),args[2][0]['POSITION'][:,1])
        proof=representation.pelvis(*args)
        self.assertTrue(proof['rawPNUTBytesExact'])
        self.assertTrue(proof['sequentialNativePNUTBytesExact'])

    def test_pelvis_step_jacobian_mask_and_one_word_corruptions(self):
        for kind in ('stepOrder','stepOmitted','bWeight','J','edited','rawUV','nativeN','indices'):
            args=pelvis_arrays();z=args[0]
            if kind=='stepOrder':args[6]['steps'][0],args[6]['steps'][1]=args[6]['steps'][1],args[6]['steps'][0]
            elif kind=='stepOmitted':args[6]['steps'].pop()
            elif kind=='bWeight':
                row=next(iter(args[6]['steps'][0]['splitRawRows'].values()));row['bWeight']=.2
            elif kind=='J':z['connectorJacobianLocal'][0,0,0]=1.1
            elif kind=='edited':z['connectorEditedVertexMask'][0]=not z['connectorEditedVertexMask'][0]
            elif kind=='rawUV':args[2][0]['TEXCOORD_0'][0,0]=np.nextafter(args[2][0]['TEXCOORD_0'][0,0],np.float32(10))
            elif kind=='nativeN':z['normals'][0,0,0]=np.nextafter(z['normals'][0,0,0],np.float64(10))
            else:args[3][0][0]=args[3][0][0,[0,2,1]]
            with self.subTest(kind=kind),self.assertRaises((ValueError,IndexError)):
                representation.pelvis(*args)




class ReviewBoundaryTests(unittest.TestCase):
    def test_ordinary_json_exponent_overflow_rejected(self):
        for value in ('{"a":1e999}','{"a":-1e999}','{"rows":[{"a":1e999}]}'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                representation.decode_json(value)

    def test_image_view_indices_are_typed_and_bounded(self):
        doc,binary=fixture()
        for value in (True,False,-1,len(doc['bufferViews'])):
            old=copy.deepcopy(doc);current=copy.deepcopy(doc)
            old['images'][0]['bufferView']=value;current['images'][0]['bufferView']=value
            with self.subTest(value=value),self.assertRaises(ValueError):
                representation.preservation(current,binary,old,binary)




class NonDirectRepresentationFixture:
    """End-to-end contracts with separate synthetic old helper versions."""
    def __init__(self,owner,part, *, corrupt_width_native=False,corrupt_mirror_native=False):
        self.x=x=RepresentationFixture(owner);self.f=f=x.f;self.part=part
        # Real complete stock bind hierarchy, with nondegenerate thigh axes.
        from retarget import nodes,transforms
        import re
        sp=Path(f.target['rig']['stockReferenceReceipt']['path'])
        stock=json.loads(sp.read_text());ascii_path=Path(stock['rootAscii']['path'])
        text=ascii_path.read_text()
        locations={'lthigh_g':[-.086064722,-.001916,1.016476482],'rthigh_g':[.078837478,-.001916,1.016476482],
            'lshin_g':[-.071274122,-.00673854,.554775482],'rshin_g':[.064046878,-.00673854,.554775482]}
        for name,xyz in locations.items():
            pattern=r'(node dummy '+name+r'\n parent pfh0\n) position [^\n]+\n orientation [^\n]+'
            text,count=re.subn(pattern,lambda m:m[1]+' position '+' '.join(map(str,xyz))+'\n orientation 0 0 1 0',text)
            assert count==1
        ascii_path.write_text(text);frames={k:v.tolist() for k,v in transforms(nodes(text)).items()}
        stock.update(frames=frames,frozenInputs={str(ascii_path):contract.sha(ascii_path)},
            rootAscii=f.pin(ascii_path));f.write(sp,stock)
        f.target['rig']['frames']={'working':copy.deepcopy(frames),'runtime':copy.deepcopy(frames)}
        f.target['rig']['stockReferenceReceipt']=f.pin(sp);f.write(f.target_path,f.target)
        f.target=contract.load(f.target_path)
        f.proof['targetContract']=f.pin(f.target_path)
        for name,rec in f.documents.items():
            rec.update(contract.binding(f.target_path,f.target,'working'))
            rec['attachmentWorld']=frames[contract.PART_JOINTS[name]]
            rec['frozenInputs'][str(f.target_path)]=contract.sha(f.target_path)
        self.live=str(REPO/'tools/phenotypes/target_part_pipeline.py')
        self.bank_snapshot=f.out/'helpers/bank/target_part_pipeline.py'
        self.old_snapshot=f.out/'helpers/ancestor/target_part_pipeline.py'
        self.old_sentinel=f.out/'ANCESTOR_EXECUTED'
        for p,body in ((self.bank_snapshot,b"raise AssertionError('Bank old helper must remain inert')\n"),
            (self.old_snapshot,("from pathlib import Path\nPath("+repr(str(self.old_sentinel))+").write_text('bad')\n").encode())):
            p.parent.mkdir(parents=True);p.write_bytes(body)
        self.saved_bank=f.archive/'files/00000002.bin';self.saved_bank.write_bytes(self.bank_snapshot.read_bytes())
        self.saved_old=f.archive/'files/00000003.bin';self.saved_old.write_bytes(self.old_snapshot.read_bytes())
        self.bank_hash=contract.sha(self.saved_bank);self.old_hash=contract.sha(self.saved_old)
        assert self.bank_hash!=self.old_hash
        for rec in f.documents.values():rec['frozenInputs'][self.live]=self.bank_hash
        f.proof['helperMappings'].append({'originalClaimedSource':{'path':self.live,'sha256':self.bank_hash},
            'actualArchivedSourcePath':str(self.bank_snapshot),'archivedCopy':f.pin(self.saved_bank),
            'size':self.saved_bank.stat().st_size})
        self.ancestors=[];self.parent_rows=[];self.protocol_inputs={}
        template,blob=read_glb(f.local_source)
        raw=pelvis_arrays()[4][0] if part=='pelvis' else knee_arrays()[4][0]
        faces=np.array([[0,1,2]],dtype='i8')
        source,doc,binary=self.asset('fit',template,blob,raw,faces)
        base=representation.corners([raw],[faces])
        base={k:base[k] for k in ('positions','normals','uvGltf','uvNative','tangents')}
        fitpart='legl' if part in ('legl','legr') else part
        fit=self.receipt('fit',fitpart,'fit',source,base,source,None)
        parent=fit;parent_doc=doc;parent_bin=binary;parent_raw=raw;parent_faces=faces;parent_native=base
        if part in ('legl','legr'):
            hip=contract.frame(f.target,'lthigh_g','working');knee=contract.frame(f.target,'lshin_g','working')
            shaft=(np.linalg.inv(hip)@knee)[:3,3];u=shaft/np.linalg.norm(shaft)
            hint=hip[:3,:3].T@np.array([1.,0,0]);axis=hint-hint.dot(u)*u;axis/=np.linalg.norm(axis)
            matrix=np.eye(3)+(.78-1)*np.outer(axis,axis)
            from scale_target_limb_width import encode,native_transform
            wdoc,wbin,_=encode(doc,binary,matrix,np.zeros(3))
            wsource=f.out/'width.glb';write_glb(wsource,wdoc,wbin)
            wnative=native_transform(base,matrix,np.zeros(3))
            if corrupt_width_native:wnative['positions'][0,0,0]+=.001
            width=self.receipt('width','legl','bone-axis-width-affine',wsource,wnative,source,fit)
            width['row']['proof']={'widthFactor':.78,'matrixLocal':matrix.tolist(),'widthAxisLocal':axis.tolist()}
            f.write(width['path'],width['row'])
            config={'schemaVersion':2,'kind':'target-thigh-width-diagnostic',
                'targetContract':str(f.target_path),'targetContractSha256':contract.sha(f.target_path),
                'parentReceipt':str(fit['path']),'parentReceiptSha256':contract.sha(fit['path']),
                'widthFactor':.78,'matrixLocal':matrix.tolist(),'widthAxisLocal':axis.tolist(),
                'mirrorPlaneWorldX':-.003613622}
            config_path=f.write(f.out/'width-config.json',config)
            width['row']['frozenInputs'][str(config_path)]=contract.sha(config_path);f.write(width['path'],width['row'])
            self.protocol_inputs.update(widthSource=self.source_row(fit),widthConfiguration=f.pin(config_path))
            parent=width;parent_doc=wdoc;parent_bin=wbin;parent_native=wnative
            parent_raw=representation.mesh(*representation.glb(wsource))[0][0]
            if part=='legr':
                right=contract.frame(f.target,'rthigh_g','working')
                from mirror_stock_limb_part import reflection_between_frames
                mirror,world=reflection_between_frames(hip,right,[config['mirrorPlaneWorldX'],0,0],[1,0,0])
                mdoc,mbin,_=encode(wdoc,wbin,mirror[:3,:3],mirror[:3,3],True)
                msource=f.out/'mirror.glb';write_glb(msource,mdoc,mbin)
                mnative=native_transform(wnative,mirror[:3,:3],mirror[:3,3],True)
                if corrupt_mirror_native:mnative['tangents'][0,0,0]+=.001
                parent=self.receipt('mirror','legr','mirror',msource,mnative,wsource,width)
                parent['row'].update(reflectionWorld=world.tolist(),proof={'sourceToRightLocal':mirror.tolist(),
                    'triangleCornerOrder':[0,2,1],'tangentWFlipsExactly':True})
                f.write(parent['path'],parent['row'])
                self.protocol_inputs.update(mirrorSource=self.source_row(width),mirrorConfiguration=f.pin(config_path))
                parent_doc=mdoc;parent_bin=mbin;parent_native=mnative
                parent_raw=representation.mesh(*representation.glb(msource))[0][0]
                parent_faces=faces[:,[0,2,1]]
        if part=='pelvis':
            z,native,aa,ff,_,_,line,cfg=pelvis_arrays()
            child,_,_=self.asset('child',parent_doc,parent_bin,aa[0],ff[0])
            line_path=f.write(f.out/'split-lineage.json',line)
            operation='face-aware-pelvis-upper-connector-plane-subdivision'
            additions={'splitLineage':f.pin(line_path),'connectorConfiguration':cfg}
            self.protocol='sequential-plane-split-raw-field-v1'
        else:
            complement=part in ('shinl','shinr')
            parents=np.array([0,0],dtype='i8');w=np.array([[[1,0,0],[.5,.5,0],[0,0,1]],
                [[.5,.5,0],[0,1,0],[0,0,1]]],dtype='f8')
            native={k:np.einsum('fci,fij->fcj',w,parent_native[k][parents])
                for k in ('positions','normals','uvGltf','uvNative','tangents')}
            z={k:v.copy() for k,v in native.items()};z['positions'][0,:,0]*=1.2
            j=np.tile(np.eye(3),(2,3,1,1));j[0,:,0,0]=1.2
            edited=np.any(z['positions']!=native['positions'],axis=2).reshape(-1)
            from deform_target_terminal_envelope import transport
            n,t=transport(native['normals'].reshape(-1,3),native['tangents'].reshape(-1,4),j.reshape(-1,3,3),edited)
            z['normals']=n.reshape(2,3,3);z['tangents']=t.reshape(2,3,4)
            z.update(connectorParentFaceIds=parents,connectorBarycentricNative=w,
                connectorProtectedWholeFaceMask=np.array([False,True]),
                connectorParentPositions=native['positions'].copy(),connectorParentNormals=native['normals'].copy(),
                connectorJacobianLocalCorners=j)
            before={'POSITION':native['positions']@representation.B,'NORMAL':native['normals']@representation.B,
                'TEXCOORD_0':native['uvGltf']}
            after={'POSITION':z['positions']@representation.B,'NORMAL':z['normals']@representation.B,
                'TEXCOORD_0':z['uvGltf']}
            for group,value in ((before,native['tangents']),(after,z['tangents'])):
                group['TANGENT']=value.copy();group['TANGENT'][:,:,:3]=value[:,:,:3]@representation.B
            expected={}
            for semantic in before:
                raw_value=representation.raw_bary(parent_raw[semantic],parent_faces,parents,w)
                delta=after[semantic]-before[semantic];value=(raw_value+delta).astype('<f4')
                zero=np.all(delta==0,axis=2);value[zero]=raw_value.astype('<f4')[zero]
                value[1]=raw_value.astype('<f4')[1]
                expected[semantic]=value.reshape(-1,value.shape[-1])
            if complement:
                for semantic in ('POSITION','NORMAL','TANGENT'):
                    value=after[semantic].astype('<f4');expected[semantic]=value.reshape(-1,value.shape[-1])
                value=z['uvNative'].copy();value[:,:,1]=1-value[:,:,1]
                expected['TEXCOORD_0']=value.astype('<f4').reshape(-1,2)
            child,_,_=self.asset('child',parent_doc,parent_bin,expected,np.arange(6,dtype='i8').reshape(-1,3))
            line={'sourceGeometry':f.pin(parent['path']),'nativeSource':parent['row']['nativeCornerArchive'],
                'originalSha256':contract.sha(parent['source']),'allSourceFacesRetained':True}
            line_path=f.write(f.out/'knee-lineage.json',line);additions={'lineage':f.pin(line_path)}
            operation='measured-convex-knee-endpoint-source-face-subdivision'
            self.protocol='native-v-complement-f32-v1' if complement else 'original-source-barycentric-plus-native-field-delta-v1'
        current=self.receipt('current',part,operation,child,z,parent['source'],parent,ancestor=False)
        current['row'].update(additions)
        # Real producers pin their output lineage on the receipt, after freezing inputs.
        current['row']['frozenInputs'].update({
            str(Path(parent['row']['nativeCornerArchive']['path'])):parent['row']['nativeCornerArchive']['sha256']})
        current['row']['frozenInputs'].update({self.live:self.bank_hash,str(f.old_helper):f.old_digest})
        f.documents[part]=current['row'];f.part_paths[part]=current['path'];f.candidates[part]=child
        self.current=current;self.parent=parent
        self.protocol_inputs.update(parentCandidate=f.pin(parent['source']),parentGeometryReceipt=f.pin(parent['path']),
            parentNativeCornerArchive=parent['row']['nativeCornerArchive'],sourceLineage=f.pin(line_path))
        # Fit is an actual required width ancestor only for thighs.
        used=[parent]
        if part in ('legl','legr'):
            used.append(fit)
            if part=='legr':used.append(width)
        self.ancestors=used
        self.seal()

    def source_row(self,row):
        return {'candidate':self.f.pin(row['source']),'geometryReceipt':self.f.pin(row['path']),
            'nativeCornerArchive':row['row']['nativeCornerArchive']}

    def asset(self,name,doc,binary,rows,faces):
        f=self.f;d=copy.deepcopy(doc);blob=bytearray(binary);d['nodes']=[{'name':'detached_geometry','mesh':0}]
        def append(array,kind,ctype):
            array=np.asarray(array);blob.extend(b'\0'*(-len(blob)%4));start=len(blob);blob.extend(array.tobytes())
            d['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':array.nbytes})
            d['accessors'].append({'bufferView':len(d['bufferViews'])-1,'count':len(array),'type':kind,'componentType':ctype})
            return len(d['accessors'])-1
        attrs={key:append(value.astype('<f4'),'VEC'+str(value.shape[1]),5126) for key,value in rows.items()}
        indices=append(faces.astype('<u4').reshape(-1,1),'SCALAR',5125)
        d['meshes'][0]['primitives']=[{'attributes':attrs,'indices':indices,'material':0}]
        blob.extend(b'\0'*(-len(blob)%4));d['buffers'][0]['byteLength']=len(blob)
        path=f.out/(name+'.glb');write_glb(path,d,bytes(blob));return path,d,bytes(blob)

    def receipt(self,name,part,operation,source,native,parent_source,parent,ancestor=True):
        f=self.f;archive=f.out/(name+'-native.npz');np.savez(archive,**native)
        if parent is None:
            origin=f.write(f.out/(name+'-origin.json'),{'kind':'synthetic-source-only'})
        else:origin=parent['path']
        row={'schemaVersion':2,'kind':'target-part-geometry',**contract.binding(f.target_path,f.target,'working'),
            'operation':operation,'part':part,'joint':contract.PART_JOINTS[part],'model':contract.model(f.target,part),
            'candidate':str(source),'candidateSha256':contract.sha(source),'nativeCornerArchive':f.pin(archive),
            'source':str(parent_source),'sourceSha256':contract.sha(parent_source),
            'sourceReceipt':str(origin),'sourceReceiptSha256':contract.sha(origin),'statureApplications':0,
            'attachmentWorld':f.target['rig']['frames']['working'][contract.PART_JOINTS[part]],
            'diagnosticOnly':True,'proof':{},'frozenInputs':{str(f.target_path):contract.sha(f.target_path),
                str(parent_source):contract.sha(parent_source),str(origin):contract.sha(origin),
                self.live:self.old_hash if ancestor else self.bank_hash}}
        path=f.write(f.out/(name+'-geometry.json'),row)
        return {'path':path,'row':row,'source':source,'archive':archive}

    def seal(self):
        f=self.f
        for item in self.ancestors:f.write(item['path'],item['row'])
        f.seal()
        manifest=json.loads(f.manifest_path.read_text())
        for source,saved in ((self.bank_snapshot,self.saved_bank),(self.old_snapshot,self.saved_old)):
            manifest['files'].append({'source':str(source),'relative':source.relative_to(REPO).as_posix(),
                'copy':str(saved),'size':saved.stat().st_size,'sha256':contract.sha(saved),'role':'ignoredAssetOrEvidence'})
        manifest['helperHashes'][self.live]=self.bank_hash;f.write(f.manifest_path,manifest)
        f.proof['preservationManifest']=f.pin(f.manifest_path);f.save()
        scoped={'originalClaimedSource':{'path':self.live,'sha256':self.old_hash},
            'preservationManifest':f.pin(f.manifest_path),'actualArchivedSourcePath':str(self.old_snapshot),
            'archivedCopy':f.pin(self.saved_old),'size':self.saved_old.stat().st_size}
        ancestor={'schemaVersion':1,'kind':representation.ANCESTOR_KIND,
            'operation':'verify-receipt-scoped-ancestors-v1','verificationApplications':1,
            'targetContract':f.pin(f.target_path),'targetId':f.target['id'],'rigRevision':f.target['rig']['revision'],
            'coordinateSpace':'working','adoptionProof':f.pin(f.proof_path),
            'receipts':[{'receipt':f.pin(item['path']),'historicalPipeline':copy.deepcopy(scoped)} for item in self.ancestors]}
        self.ancestor_document=ancestor;self.ancestor_path=f.write(f.out/'ancestor-contract.json',ancestor)
        current=f.documents[self.part];rp=f.pin(f.part_paths[self.part])
        closure=dict(current['frozenInputs']);closure.update({rp['path']:rp['sha256'],
            current['candidate']:current['candidateSha256'],current['nativeCornerArchive']['path']:current['nativeCornerArchive']['sha256']})
        self.document={**self.x.document,'targetContract':f.pin(f.target_path),'targetId':f.target['id'],
            'rigRevision':f.target['rig']['revision'],'part':self.part,'joint':contract.PART_JOINTS[self.part],
            'model':contract.model(f.target,self.part),'protocol':self.protocol,
            'candidate':f.pin(f.candidates[self.part]),'geometryReceipt':rp,'nativeCornerArchive':current['nativeCornerArchive'],
            'adoptionProof':f.pin(f.proof_path),'inputReceipts':[rp],'sourceClosure':closure,
            'protocolInputs':copy.deepcopy(self.protocol_inputs),'ancestorContract':f.pin(self.ancestor_path)}
        self.path=f.write(f.out/'non-direct-representation.json',self.document)

    def verify(self):
        f=self.f
        return representation.verify_source_representation(f.pin(self.path),
            target_path=f.target_path,target=f.target,part=self.part,space='working')


class NonDirectFactoryTests(unittest.TestCase):
    def test_all_non_direct_protocols_accept_separately_scoped_helper_versions(self):
        for part in ('pelvis','legl','legr','shinl','shinr'):
            with self.subTest(part=part):
                x=NonDirectRepresentationFixture(self,part)
                pins=[x.f.bank_path,x.f.proof_path,x.path,x.ancestor_path,*[r['path'] for r in x.ancestors]]
                before={p:p.read_bytes() for p in pins};result=x.verify()
                self.assertTrue(result.proof['nativeDoubleLineageKeptSeparate'])
                self.assertTrue(result.proof['ancestorEvidence']['receipts'])
                self.assertIn(str(x.saved_bank),result.inputs);self.assertIn(str(x.saved_old),result.inputs)
                self.assertEqual(result.proof['executionAdoption']['receiptPins'].keys(),
                    {str(x.f.part_paths[part])})
                self.assertFalse(x.old_sentinel.exists());self.assertFalse(x.f.sentinel.exists())
                for p,value in before.items():self.assertEqual(p.read_bytes(),value)
                if part in ('legl','legr'):
                    self.assertTrue(result.proof['protocolProof']['widthAncestor']['nativeWidthPNUTBytesExact'])
                if part=='legr':
                    self.assertTrue(result.proof['protocolProof']['mirrorAncestor']['nativeMirrorPNUTBytesExact'])

    def test_conflicting_original_helper_versions_cannot_join_global_scope(self):
        import phenotype_infrastructure_adoption as adoption
        x=NonDirectRepresentationFixture(self,'pelvis')
        original=copy.deepcopy(x.f.proof)
        original['historicalReceipts'].append({'receipt':x.f.pin(x.parent['path']),
            'kind':'target-part-geometry','closures':['frozenInputs']})
        path=x.f.write(x.f.out/'forbidden-global-proof.json',original)
        with self.assertRaisesRegex(ValueError,'Original closure digest'):
            adoption.verify_proof(x.f.pin(path),repo=REPO)
        x.verify()

    def test_missing_or_wrong_scoped_association_does_not_fall_back(self):
        for change in ('missing','wrongDigest','wrongArchive','extraReceipt','crossTarget'):
            x=NonDirectRepresentationFixture(self,'pelvis')
            if change=='missing':x.ancestor_document['receipts'][0]['historicalPipeline']=None
            elif change=='wrongDigest':
                x.ancestor_document['receipts'][0]['historicalPipeline']['originalClaimedSource']['sha256']=x.bank_hash
            elif change=='wrongArchive':
                x.ancestor_document['receipts'][0]['historicalPipeline']['archivedCopy']=x.f.pin(x.saved_bank)
            elif change=='extraReceipt':
                x.ancestor_document['receipts'].append(copy.deepcopy(x.ancestor_document['receipts'][0]))
            else:x.ancestor_document['targetId']='different-target'
            x.f.write(x.ancestor_path,x.ancestor_document)
            x.document['ancestorContract']=x.f.pin(x.ancestor_path);x.f.write(x.path,x.document)
            with self.subTest(change=change),self.assertRaises(ValueError):x.verify()

    def test_raw_and_native_ancestor_proofs_are_independent(self):
        for part,kw in (('legl',{'corrupt_width_native':True}),('legr',{'corrupt_mirror_native':True})):
            x=NonDirectRepresentationFixture(self,part,**kw)
            with self.subTest(part=part),self.assertRaisesRegex(ValueError,'separate native'):x.verify()

    def test_scoped_input_drift_invalidates_verified_result(self):
        x=NonDirectRepresentationFixture(self,'legr');result=x.verify()
        x.saved_old.write_bytes(x.saved_old.read_bytes()+b'drift')
        with self.assertRaises(ValueError):result.verify()

    def test_receipt_owned_lineage_keeps_literal_frozen_closure_unchanged(self):
        for part in ('pelvis','legl','legr','shinl','shinr'):
            with self.subTest(part=part):
                x=NonDirectRepresentationFixture(self,part)
                field='splitLineage' if part=='pelvis' else 'lineage'
                output=x.current['row'][field]
                self.assertNotIn(output['path'],x.current['row']['frozenInputs'])
                self.assertNotIn(output['path'],x.document['sourceClosure'])
                before={p:p.read_bytes() for p in (x.current['path'],x.path,x.f.proof_path)}
                result=x.verify()
                self.assertEqual(dict(result.proof['receiptOwnedOutputs'][field]),output)
                self.assertEqual(result.inputs[output['path']],output['sha256'])
                for p,value in before.items():self.assertEqual(p.read_bytes(),value)

    def test_receipt_owned_lineage_requires_exact_owner_and_protocol_pin(self):
        for change in ('missingOwner','wrongOperation','differentProtocolPin','malformedOwnerPin','wrongOwnerHash'):
            with self.subTest(change=change):
                x=NonDirectRepresentationFixture(self,'pelvis')
                if change=='missingOwner':x.current['row'].pop('splitLineage')
                elif change=='wrongOperation':x.current['row']['operation']='fit'
                elif change=='malformedOwnerPin':x.current['row']['splitLineage']['path']='relative-lineage.json'
                elif change=='wrongOwnerHash':x.current['row']['splitLineage']['sha256']='1'*64
                else:
                    other=x.f.write(x.f.out/'foreign-lineage.json',{'not':'the owned lineage'})
                    x.protocol_inputs['sourceLineage']=x.f.pin(other)
                x.seal()
                with self.assertRaises(ValueError):x.verify()

    def test_receipt_owned_lineage_changed_bytes_invalidate_result(self):
        for part in ('pelvis','shinl'):
            with self.subTest(part=part):
                x=NonDirectRepresentationFixture(self,part);result=x.verify()
                path=Path(x.protocol_inputs['sourceLineage']['path'])
                path.write_bytes(path.read_bytes()+b' ')
                with self.assertRaises(ValueError):result.verify()
                with self.assertRaises(ValueError):x.verify()

    def test_receipt_owned_lineage_conflicting_literal_claim_is_rejected(self):
        x=NonDirectRepresentationFixture(self,'pelvis')
        pin=x.current['row']['splitLineage']
        x.current['row']['frozenInputs'][pin['path']]='2'*64
        x.seal()
        with self.assertRaises(ValueError):x.verify()

    def test_original_householder_signed_zero_bytes_are_replayed_by_factory(self):
        x=NonDirectRepresentationFixture(self,'legr')
        world=np.asarray(x.parent['row']['reflectionWorld'],dtype='f8')
        self.assertEqual(world[1,3],0.)
        self.assertEqual(world[2,3],0.)
        self.assertTrue(np.signbit(world[1,3]))
        self.assertTrue(np.signbit(world[2,3]))
        result=x.verify()
        self.assertTrue(result.proof['protocolProof']['mirrorAncestor']['nativeMirrorPNUTBytesExact'])
        self.assertTrue(result.proof['protocolProof']['mirrorAncestor']['tangentWFlipsExactly'])

    def test_signed_zero_normalization_is_still_a_byte_change(self):
        x=NonDirectRepresentationFixture(self,'legr')
        left=next(row for row in x.ancestors if row['row']['operation']=='bone-axis-width-affine')
        aa,ff,_=representation.mesh(*representation.glb(x.parent['source']))
        old,oldf,_=representation.mesh(*representation.glb(left['source']))
        parent=copy.deepcopy(x.parent['row'])
        parent['reflectionWorld'][1][3]=0.
        config=representation.read_json(x.protocol_inputs['mirrorConfiguration']['path'])
        with self.assertRaisesRegex(ValueError,'configured stock reflection'):
            representation.mirror_parent(parent,left['row'],aa,ff,old,oldf,x.f.target,config)

if __name__=='__main__':unittest.main()
