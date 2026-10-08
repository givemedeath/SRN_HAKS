"""Explicit cap repair preserves source lineage, maps and all other corner samples."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import numpy as np
from diagnose_native_cap_normal import cap_exception,descendant,oriented_closed_surface,validate_descendant,validate_plan_owner
from place_purposebuilt_pelvis import BASIS,raw_corners,write_glb,read_glb


def fixture():
    p=np.asarray([[0,0,0],[1,0,0],[0,1,0],[0,0,1]],float)
    normals=np.tile([0,0,1],(4,1));t=np.tile([1,0,0,1],(4,1)).astype(float);t[:,:3]=t[:,:3]@BASIS
    uv=np.asarray([[0,0],[1,0],[0,1],[.6,.7]],float);ids=np.asarray([[0,2,1],[0,1,3],[1,2,3],[2,0,3]],dtype='u4')
    b=bytearray();views=[];accessors=[]
    def add(rows,component=5126):
        a=np.asarray(rows,dtype='<f4' if component==5126 else '<u4');width=a.shape[1] if a.ndim==2 else 1;b.extend(b'\0'*(-len(b)%4));offset=len(b);b.extend(a.tobytes());b.extend(b'\0'*(-len(b)%4));views.append({'buffer':0,'byteOffset':offset,'byteLength':a.nbytes});accessors.append({'bufferView':len(views)-1,'componentType':component,'count':len(a),'type':{1:'SCALAR',2:'VEC2',3:'VEC3',4:'VEC4'}[width]});return len(accessors)-1
    attr={'POSITION':add(p@BASIS),'NORMAL':add(normals@BASIS),'TEXCOORD_0':add(uv),'TANGENT':add(t)};ii=add(ids.reshape(-1),5125)
    # A small opaque embedded blob suffices: tests verify exact original bytes
    # rather than decoding or staging 2K material maps.
    payload=b'unchanged-original-map-bytes';offset=len(b);b.extend(payload);b.extend(b'\0'*(-len(b)%4));views.append({'buffer':0,'byteOffset':offset,'byteLength':len(payload)})
    doc={'asset':{'version':'2.0'},'buffers':[{'byteLength':len(b)}],'bufferViews':views,'accessors':accessors,'scene':0,'scenes':[{'nodes':[0]}],'nodes':[{'name':'detached_geometry','mesh':0}],'meshes':[{'primitives':[{'mode':4,'attributes':attr,'indices':ii,'material':0}]}],'materials':[{'name':'unchanged-skin'}],'images':[{'bufferView':len(views)-1,'mimeType':'image/png'}],'textures':[{'source':0}]}
    return doc,bytes(b)


class ExplicitCapNormalTests(unittest.TestCase):
    def test_only_three_duplicated_normal_tangent_corners_change(self):
        d,b=fixture();extra={};p,n,uv,_=raw_corners(d,b,extra=extra);t=np.concatenate(extra['TANGENT']['rows']);nd,nb,pp,nn,uu,tt,order,proof=descendant(d,b,0)
        self.assertEqual(proof['normalsChangedCorners'],3);self.assertEqual(proof['authoredTangentsChangedCorners'],3)
        np.testing.assert_array_equal(nn[1:],n[1:]);np.testing.assert_array_equal(tt[1:],t[1:]);np.testing.assert_array_equal(pp,p);np.testing.assert_array_equal(uu,uv)
        np.testing.assert_array_equal(nn[0],np.tile([0,0,-1],(3,1)))
        self.assertEqual(proof['normalChangeAngleDegrees'],[180.,180.,180.]);self.assertEqual(proof['nativeExpectedWAfterVFlip'],[1.,1.,1.])
        self.assertEqual(order.tolist(),[1,2,3,0]);self.assertEqual(nb[:len(b)],b);self.assertEqual(nd['materials'],d['materials']);self.assertEqual(nd['accessors'][:len(d['accessors'])],d['accessors'])
        self.assertEqual(d['meshes'][0]['primitives'][0]['attributes'],nd['meshes'][0]['primitives'][0]['attributes'])
        self.assertEqual(len(d['meshes'][0]['primitives']),1)

    def test_serialized_descendant_roundtrip_retains_complete_proof(self):
        d,b=fixture();nd,nb,*_=descendant(d,b,0)
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'child.glb';write_glb(path,nd,nb);rd,rb=read_glb(path);_,_,_,_,order,proof=validate_descendant(d,b,rd,rb,0)
            self.assertEqual(order.tolist(),[1,2,3,0]);self.assertEqual(proof['closedDirectedTopology']['boundaryEdges'],0)

    def test_open_incoherent_or_inverted_surface_rejects(self):
        d,b=fixture();p,n,uv,_=raw_corners(d,b)
        for q in [p[:-1],p[:,[0,2,1]],np.concatenate([p,p[:1]])]:
            with self.subTest(shape=q.shape),self.assertRaises(ValueError):oriented_closed_surface(q)
        q=p.copy();q[0]=q[0,[0,2,1]]
        with self.assertRaises(ValueError):oriented_closed_surface(q)

    def test_uv_or_projection_ambiguity_rejects(self):
        d,b=fixture();e={};p,n,uv,_=raw_corners(d,b,extra=e);t=np.concatenate(e['TANGENT']['rows'])
        bad=uv.copy();bad[0]=0
        with self.assertRaisesRegex(ValueError,'UV derivative'):cap_exception(p,n,bad,t,0)
        bad=t.copy();bad[0,:,:3]=[0,0,1]
        with self.assertRaisesRegex(ValueError,'projection collapsed'):cap_exception(p,n,uv,bad,0)
        with self.assertRaises(ValueError):cap_exception(p,n,uv,t,True)

    def test_stale_bytes_material_and_source_lineage_reject(self):
        d,b=fixture();nd,nb,*_=descendant(d,b,0)
        changed=bytearray(nb);changed[0]^=1
        with self.assertRaisesRegex(ValueError,'BIN prefix'):validate_descendant(d,b,nd,bytes(changed),0)
        changed=deepcopy(nd);changed['materials'][0]['name']='changed'
        with self.assertRaisesRegex(ValueError,'binding'):validate_descendant(d,b,changed,nb,0)
        changed=deepcopy(nd);changed['meshes'][0]['primitives'][1]['material']=1
        with self.assertRaisesRegex(ValueError,'material'):validate_descendant(d,b,changed,nb,0)
        with self.assertRaises(ValueError):validate_descendant(d,b,nd,nb,1)

    def test_authoritative_target_id_and_cross_target_plan_binding(self):
        plan={'kind':'explicit-cap-normal-repair-plan','sourceFaceId':24724,'targetId':'female-v1','part':'bicepl','coordinateSpace':'working'}
        parent={'part':'bicepl','splitFaceIds':[24724]};target={'id':'female-v1'}
        self.assertEqual(validate_plan_owner(plan,parent,target),24724)
        for field,value in [('targetId','other'),('part','bicepr'),('coordinateSpace','runtime'),('sourceFaceId',10913),('kind','unreviewed')]:
            changed={**plan,field:value}
            with self.subTest(field=field),self.assertRaises(ValueError):validate_plan_owner(changed,parent,target)

    def test_unknown_attribute_cannot_be_dropped(self):
        d,b=fixture();d['meshes'][0]['primitives'][0]['attributes']['COLOR_0']=0
        with self.assertRaisesRegex(ValueError,'P/N/UV/T-only'):descendant(d,b,0)


if __name__=='__main__':unittest.main()
