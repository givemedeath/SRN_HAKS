"""Focused cuff5 physics, untouched-row/native ancestry and scope failures."""
import copy
import tempfile
from pathlib import Path
import unittest
import numpy as np
import diagnostic_pelvis_cuff_contour as cuff
from place_purposebuilt_pelvis import BASIS

CENTERS={'positive':[.1334686125485756,-.047732968335732234],
         'negative':[-.12552949667091073,-.04223338269194496]}

class CuffTests(unittest.TestCase):
    def test_affine_caps_and_exact_axial_protected_support(self):
        p=np.array([[.1,.02,.93],[-.1,.02,.93],[.020,.01,.93],[.1,.02,.965],[.1,.02,1.1]],dtype='<f8')
        q,J,w=cuff.field(p,CENTERS)
        for row,side in [(0,'positive'),(1,'negative')]:
            center=np.array(CENTERS[side]);np.testing.assert_allclose(q[row,:2],center+.95*(p[row,:2]-center),atol=2e-17,rtol=0)
            np.testing.assert_array_equal(J[row],np.diag([.95,.95,1]))
        self.assertEqual(q[:,2].tobytes(),p[:,2].tobytes());self.assertEqual(q[2:].tobytes(),p[2:].tobytes())
        np.testing.assert_array_equal(w,[1,1,0,0,0])

    def test_jacobian_finite_difference_C2_and_positive_bound(self):
        p=np.array([[.024,.01,.953],[-.025,-.03,.947],[.1,.02,.95]])
        _,J,_=cuff.field(p,CENTERS)
        for i in range(3):
            e=np.eye(3)[i]*1e-7
            np.testing.assert_allclose((cuff.field(p+e,CENTERS)[0]-cuff.field(p-e,CENTERS)[0])/2e-7,J[:,:,i],atol=6e-9,rtol=0)
        x,z=np.meshgrid(np.linspace(-.18,.18,97),np.linspace(.90,.99,101))
        _,j,_=cuff.field(np.column_stack([x.ravel(),np.full(x.size,.03),z.ravel()]),CENTERS)
        self.assertGreaterEqual(np.linalg.det(j).min(),.9025-1e-14)
        for boundary in [.942,.965]:
            a=np.array([[.1,.02,boundary-1e-8],[.1,.02,boundary+1e-8]])
            _,j,_=cuff.field(a,CENTERS);np.testing.assert_allclose(j[0],j[1],atol=8e-11,rtol=0)

    def test_inverse_transpose_T_GS_magnitude_and_W(self):
        p=np.array([[.024,.04,.951],[.10,.02,.93]])
        n=np.array([[.3,.4,1.7],[.2,.8,1.3]])
        t=np.array([[1.2,.05,.2,-1.],[1.4,.1,.2,1.]])
        nn,tt=cuff.transport(p,n,t,CENTERS);_,J,_=cuff.field(p,CENTERS)
        expected=np.linalg.solve(J.transpose(0,2,1),n[...,None])[...,0]
        expected*= (np.linalg.norm(n,axis=1)/np.linalg.norm(expected,axis=1))[:,None]
        np.testing.assert_allclose(nn,expected,atol=5e-16,rtol=0)
        np.testing.assert_allclose(np.linalg.norm(nn,axis=1),np.linalg.norm(n,axis=1),atol=5e-16)
        np.testing.assert_allclose(np.linalg.norm(tt[:,:3],axis=1),np.linalg.norm(t[:,:3],axis=1),atol=5e-16)
        np.testing.assert_allclose(np.sum(nn*tt[:,:3],axis=1),0,atol=5e-16)
        self.assertEqual(tt[:,3].tobytes(),t[:,3].tobytes())

    def test_degenerate_only_affected_and_nonfinite_rejected(self):
        n=np.array([[0.,0,0]]);t=np.array([[0.,0,0,0.]])
        nn,tt=cuff.transport(np.array([[.01,0,.93]]),n,t,CENTERS)
        self.assertEqual(nn.tobytes(),n.tobytes());self.assertEqual(tt.tobytes(),t.tobytes())
        for nn,tt in [(n,np.array([[1.,0,0,1.]])),(np.array([[0,0,1.]]),t),(np.array([[0,0,1.]]),np.array([[0,0,1.,1.]]))]:
            with self.assertRaises(ValueError):cuff.transport(np.array([[.1,0,.93]]),nn,tt,CENTERS)
        with self.assertRaises(ValueError):cuff.field(np.array([[np.nan,0,.9]]),CENTERS)
        with self.assertRaises(ValueError):cuff.center_array({'positive':[.02,0],'negative':[-.1,0]})

    def test_raw_basis_and_shared_active_row_protection(self):
        world=np.array([[.1,.02,.93],[.1,.02,.93],[.1,.02,.93],[.1,.02,1.0]])
        P=(world@BASIS).astype('<f4');N=np.tile([.3,.4,1.7],(4,1)).astype('<f4');T=np.tile([1.2,.05,.2,-1.],(4,1)).astype('<f4')
        N[2]=0;T[2]=0
        rows,_,_,_,changed=cuff.mapped_rows(P,N,T,np.array([True,True,False,True]),np.eye(4),CENTERS)
        np.testing.assert_array_equal(changed,[True,True,False,False])
        for name,original in [('POSITION',P),('NORMAL',N),('TANGENT',T)]:self.assertEqual(rows[name][2:].tobytes(),original[2:].tobytes())
        self.assertEqual(rows['POSITION'][:,1].tobytes(),P[:,1].tobytes())
        self.assertEqual(rows['TANGENT'][:,3].tobytes(),T[:,3].tobytes())
        self.assertGreater(np.max(abs(rows['POSITION'][:2]-P[:2])),0)

    def test_cap_field_not_partial_or_dome(self):
        affine=np.array([[.033,-.04,.93],[.14,-.04,.94],[.09,.04,.939]])
        q,J,w=cuff.field(affine,CENTERS);np.testing.assert_array_equal(w,np.ones(3));np.testing.assert_array_equal(J,np.broadcast_to(np.diag([.95,.95,1]),J.shape))
        self.assertEqual(q[:,2].tobytes(),affine[:,2].tobytes())
        _,j,w=cuff.field(np.array([[.025,-.04,.93],[.1,.04,.950]]),CENTERS)
        self.assertTrue((w<1).all());self.assertFalse(np.array_equal(j,np.broadcast_to(np.diag([.95,.95,1]),j.shape)))

    def test_explicit_configuration_rejects_double_scale_or_scope(self):
        c={**cuff.RECIPE,'schemaVersion':1,'kind':'pelvis-cuff-contour5-configuration','scope':cuff.SCOPE,'centersWorldXY':copy.deepcopy(CENTERS),'acceptance':{k:False for k in cuff.FLAGS}}
        cuff.validate_configuration(c)
        for key,value in [('radialReduction',.1),('statureApplications',1),('terminal35Reapplied',True),('fitReapplied',True),('capRoundMetres',.004),('coordinateSpace','runtime'),('scope','production')]:
            bad=copy.deepcopy(c);bad[key]=value
            with self.assertRaises(ValueError):cuff.validate_configuration(bad)
        bad=copy.deepcopy(c);bad['acceptance']['capOwnershipAccepted']=True
        with self.assertRaises(ValueError):cuff.validate_configuration(bad)

    def test_root_review_rejects_template_or_final_acceptance(self):
        a={'schemaVersion':1,'kind':'root-approved-pelvis-cuff-contour5-diagnostic','scope':cuff.SCOPE,'reviewedBy':'/root','reviewed':True,'authorizeImplementationAndOneFreshExport':True,'acceptance':{k:False for k in cuff.FLAGS}}
        cuff.validate_approval(a)
        for key,value in [('reviewed',False),('reviewedBy','worker'),('authorizeImplementationAndOneFreshExport',False),('scope','canonical')]:
            bad=copy.deepcopy(a);bad[key]=value
            with self.assertRaises(ValueError):cuff.validate_approval(bad)
        bad=copy.deepcopy(a);bad['acceptance']['geometryAccepted']=True
        with self.assertRaises(ValueError):cuff.validate_approval(bad)

    def test_parent_proof_rejects_wrong_kind_child_or_promoted_scope(self):
        c={'parentReceipt':{'path':'p','sha256':'1'},'parentCandidate':{'path':'g','sha256':'2'}}
        a={'schemaVersion':1,'kind':'independent-decoded-pelvis-terminal-shortening35-audit','passed':True,'receipt':c['parentReceipt'],'candidate':c['parentCandidate'],'statureApplications':0,'capRoundMetres':0.,**{k:False for k in ['closedExteriorClaim','sourceTopologyResolved','geometryAccepted','materialAccepted','nativeAccepted','clientAccepted','productionAccepted']}}
        cuff.validate_parent_proof(a,c)
        for key,value in [('kind','another-successful-proof'),('passed',False),('candidate',{'path':'other','sha256':'2'}),('statureApplications',1),('sourceTopologyResolved',True)]:
            bad=copy.deepcopy(a);bad[key]=value
            with self.assertRaises(ValueError):cuff.validate_parent_proof(bad,c)
    def test_child_claims_reject_rebound_model_fit_or_owned_caps(self):
        p={'model':'pmg0_pelvis001','fitSourceToAttachmentLocal':np.eye(4).tolist()}
        r={'diagnosticOnly':True,'joint':'pelvis_g','model':p['model'],'fitSourceToAttachmentLocal':p['fitSourceToAttachmentLocal'],'primitiveRoleStatus':{'0':'skin','1':'unowned-neutral-diagnostic-cap','2':'unowned-neutral-diagnostic-cap','3':'garment','4':'skin','5':'garment'},'capShadingPolicy':'parent35-generated-cap-N-inverse-transpose-T-J-GS-original-magnitude-W','capAuthoritativeBasis':'float64-for-this-operation-derived-from-parent-generated-serialized-float32'}
        cuff.validate_child_claims(r,p)
        for key,value in [('model','pmh0_pelvis001'),('joint','torso_g'),('fitSourceToAttachmentLocal',(np.eye(4)*2).tolist()),('capAuthoritativeBasis','original-authored-float64'),('capShadingPolicy','authored-tangent-preserved'),('diagnosticOnly',False)]:
            bad=copy.deepcopy(r);bad[key]=value
            with self.assertRaises(ValueError):cuff.validate_child_claims(bad,p)
        bad=copy.deepcopy(r);bad['primitiveRoleStatus']['1']='skin'
        with self.assertRaises(ValueError):cuff.validate_child_claims(bad,p)
    def test_float64_archives_preserve_source_barycentric_and_generated_lineage(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);shape=(1,3,3)
            p=np.array([[[.1,.02,.93],[.12,.01,.93],[.01,.02,1.0]]],dtype='<f8')
            n=np.tile([.3,.4,1.7],(1,3,1)).astype('<f8');t=np.tile([1.2,.05,.2,-1.],(1,3,1)).astype('<f8')
            source={'positions':p,'normals':n,'tangents':t,'sourceFaceIds':np.array([7],'<i8'),'sourceBarycentric':np.eye(3,dtype='<f8')[None],'terminalParentPositions':p-.035,'sourceCornerRawBits':np.array([123,456],'<u4')}
            bp=folder/'body.npz';np.savez_compressed(bp,**source)
            records={}
            for i,x in [(1,.12),(2,-.12)]:
                world=np.array([[x,.02,.93],[x+.01,.02,.93],[x,.03,.93]])
                P=(world@BASIS).astype('<f4');N=np.tile([.2,.7,1.1],(3,1)).astype('<f4');T=np.tile([1.3,.1,.2,1.],(3,1)).astype('<f4')
                rows,*_=cuff.mapped_rows(P,N,T,np.ones(3,bool),np.eye(4),CENTERS)
                records[i]={'parentP':P,'parentN':N,'parentT':T,'P':rows['POSITION'],'N':rows['NORMAL'],'T':rows['TANGENT'],'F':np.array([[0,1,2]])}
            caps={name:np.concatenate([records[j]['parent'+{'POSITION':'P','NORMAL':'N','TANGENT':'T'}[name]][records[j]['F']] for j in [1,2]]) for name in ['POSITION','NORMAL','TANGENT']}
            caps['sourceCapPrimitiveIds']=np.array([1,2],'<i4');caps['UV']=np.zeros((2,3,2),'<f4')
            cp=folder/'caps.npz';np.savez_compressed(cp,**caps)
            parent={'bodyFloat64DeformedCornerArchive':{'path':str(bp)},'generatedCapDeformedCornerArchive':{'path':str(cp)}}
            body,newcaps=cuff.derived_archives(parent,np.eye(4),CENTERS,records)
            for name in ['sourceFaceIds','sourceBarycentric','terminalParentPositions','sourceCornerRawBits']:self.assertEqual(body[name].tobytes(),source[name].tobytes())
            self.assertEqual(body['positions'][:,:,2].tobytes(),p[:,:,2].tobytes());self.assertEqual(body['positions'][0,2].tobytes(),p[0,2].tobytes())
            self.assertEqual(body['contourParentPositions'].tobytes(),p.tobytes())
            self.assertEqual(newcaps['sourceCapPrimitiveIds'].tobytes(),caps['sourceCapPrimitiveIds'].tobytes());self.assertEqual(newcaps['UV'].tobytes(),caps['UV'].tobytes())
            self.assertEqual(newcaps['contourParentGeneratedPOSITION'].tobytes(),caps['POSITION'].tobytes())
            self.assertEqual(newcaps['derivedWorkingPositions'].dtype,np.dtype('<f8'))
            np.savez_compressed(bp,**body)
            with self.assertRaises(ValueError):cuff.derived_archives(parent,np.eye(4),CENTERS,records)

if __name__=='__main__':unittest.main()


