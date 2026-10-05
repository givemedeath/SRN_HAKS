"""Novel knee field/basis/transport and explicit scope failure tests only."""
import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
import target_contract as tc
import diagnostic_knee_terminal_connectors as knee
from test_target_part_pipeline import target_fixture
from place_purposebuilt_pelvis import BASIS

def shin_recipe():
    return {'part':'shinl','ellipseDerivedFromActualCapMask':{'coordinateU':[1.,0,0],
        'coordinateV':[0,1.,0],'centerUV':[0.,0.],'radiusUV':[.062,.062]}}
def thigh_recipe():return {'part':'legl','inwardDirectionBindWorld':[-1.,0,0]}

class KneeTerminalTests(unittest.TestCase):
    def test_rounded_rational_end_has_nonflat_rim_and_protected_calf(self):
        p=np.array([[0.,0,-.040],[.062,0,-.040],[.025,0,.060],[.09,0,.12]])
        q,J,protected=knee.field(p,np.zeros(3),np.array([0.,0,1.]),shin_recipe())
        np.testing.assert_allclose(q[0],[0,0,-.030],atol=1e-17,rtol=0)
        np.testing.assert_allclose(q[1],[.0465,0,-.005],atol=1e-17,rtol=0)
        self.assertGreater(abs(J[1,2,0]),.3)
        self.assertEqual(q[2:].tobytes(),p[2:].tobytes());self.assertTrue(protected[2:].all())
        np.testing.assert_array_equal(J[2:],np.broadcast_to(np.eye(3),(2,3,3)))

    def test_shin_jacobian_matches_finite_difference_across_dome_and_blend(self):
        p=np.array([[.021,.01,-.039],[.059,-.012,-.037],[.032,.018,.018],[.06,.013,.04]])
        _,J,_=knee.field(p,np.zeros(3),np.array([0.,0,1.]),shin_recipe())
        for k in range(3):
            e=np.eye(3)[k]*1e-7
            fd=(knee.field(p+e,np.zeros(3),np.array([0.,0,1.]),shin_recipe())[0]-knee.field(p-e,np.zeros(3),np.array([0.,0,1.]),shin_recipe())[0])/2e-7
            np.testing.assert_allclose(fd,J[:,:,k],atol=2e-9,rtol=0)
        self.assertTrue((np.linalg.det(J)>0).all())

    def test_thigh_inward_field_preserves_axis_and_nonterminal_bulk(self):
        p=np.array([[.080,0,.451],[.020,0,.429],[.09,0,.405],[.004,0,.47]])
        q,J,protected=knee.field(p,np.zeros(3),np.array([0.,0,1.]),thigh_recipe())
        np.testing.assert_allclose(q[0],[.074,0,.451],atol=1e-17,rtol=0)
        self.assertEqual(q[:,2].tobytes(),p[:,2].tobytes());self.assertEqual(q[2:].tobytes(),p[2:].tobytes())
        self.assertGreaterEqual(np.linalg.det(J).min(),.625-1e-15)
        for k in range(3):
            e=np.eye(3)[k]*1e-7
            fd=(knee.field(p+e,np.zeros(3),np.array([0.,0,1.]),thigh_recipe())[0]-knee.field(p-e,np.zeros(3),np.array([0.,0,1.]),thigh_recipe())[0])/2e-7
            np.testing.assert_allclose(fd,J[:,:,k],atol=2e-9,rtol=0)

    def test_proper_rotated_coordinate_covariance_and_bad_basis_rejection(self):
        angle=.43;R=np.array([[np.cos(angle),-np.sin(angle),0],[np.sin(angle),np.cos(angle),0],[0,0,1.]])
        p=np.array([[.04,.01,-.038],[.07,.02,.02]]);q,J,_=knee.field(p,np.zeros(3),np.array([0,0,1.]),shin_recipe())
        recipe=shin_recipe();recipe['ellipseDerivedFromActualCapMask']['coordinateU']=(R@np.array([1.,0,0])).tolist();recipe['ellipseDerivedFromActualCapMask']['coordinateV']=(R@np.array([0,1.,0])).tolist()
        a=np.array([.2,.3,.4]);qr,jr,_=knee.field(p@R.T+a,a,R@np.array([0,0,1.]),recipe)
        np.testing.assert_allclose(qr,q@R.T+a,atol=6e-17,rtol=0)
        np.testing.assert_allclose(jr,np.einsum('ij,njk,lk->nil',R,J,R),atol=2e-15,rtol=0)
        bad=shin_recipe();bad['ellipseDerivedFromActualCapMask']['coordinateV']=[0,-1.,0]
        with self.assertRaises(ValueError):knee.field(p,np.zeros(3),np.array([0,0,1.]),bad)
        with self.assertRaises(ValueError):knee.field(p,np.zeros(3),np.array([0,0,2.]),shin_recipe())

    def test_inverse_transpose_normal_and_T_GS_preserve_authored_magnitude_W(self):
        J=np.array([[[.75,0,.2],[0,.75,.1],[.3,.1,.6]],np.eye(3)])
        n=np.array([[.3,.5,1.7],[0.,0,0]]);t=np.array([[1.3,.2,.1,-1.],[0,0,0,0.]])
        nn,tt=knee.shading(n,t,J,np.array([True,False]))
        expected=np.linalg.solve(J[0].T,n[0]);expected*=np.linalg.norm(n[0])/np.linalg.norm(expected)
        np.testing.assert_allclose(nn[0],expected,atol=1e-15,rtol=0)
        self.assertAlmostEqual(float(np.linalg.norm(tt[0,:3])),float(np.linalg.norm(t[0,:3])),places=14)
        self.assertAlmostEqual(float(nn[0]@tt[0,:3]),0.,places=14)
        self.assertEqual(nn[1].tobytes(),n[1].tobytes());self.assertEqual(tt[1].tobytes(),t[1].tobytes());self.assertEqual(tt[:,3].tobytes(),t[:,3].tobytes())
        for badn,badt in [(np.zeros((2,3)),t),(n,np.zeros((2,4))), (n,np.array([[.3,.5,1.7,1.],[0,0,0,0.]]))]:
            with self.assertRaises(ValueError):knee.shading(badn,badt,J,np.array([True,False]))

    def test_raw_BASIS_and_inactive_degenerate_rows_remain_exact(self):
        p=np.array([[.04,.02,.01],[.03,.01,.09],[.08,.02,.02]]);P=(p@BASIS).astype('<f4');N=np.tile([.3,.4,1.7],(3,1)).astype('<f4');T=np.tile([1.3,.1,.1,-1.],(3,1)).astype('<f4');N[2]=0;T[2]=0
        # Repeated indexed face proves shared row use; row2 stays inactive.
        F=np.array([[0,1,0]]);H=np.eye(4);rows={'POSITION':P,'NORMAL':N,'TANGENT':T}
        new,world,ideal,J,protected,changed=knee.mapped(rows,F,H,np.array([0,0,1.]),shin_recipe())
        for name in rows:self.assertEqual(new[name][1:].tobytes(),rows[name][1:].tobytes())
        self.assertEqual(new['TANGENT'][:,3].tobytes(),T[:,3].tobytes())
        self.assertTrue(changed[0]);self.assertFalse(changed[2])

    def test_native_corner_history_maps_and_protected_original_values_preserved(self):
        p=np.array([[[.04,.02,.01],[.03,.01,.09],[.08,.02,.11]]],'<f8');n=np.tile([.3,.4,1.7],(1,3,1));t=np.tile([1.3,.1,.1,-1.],(1,3,1))
        arc={'positions':p,'normals':n,'tangents':t,'uvGltf':np.array([[[.1,.2],[.3,.4],[.5,.6]]]),'sourceTriangleIds':np.array([29]),'sourceCornerOrder':np.array([[0,1,2]]),'oldAuthoredRawBits':np.array([123,456],'<u4')}
        child=knee.native_child(arc,np.eye(4),np.array([0,0,1.]),shin_recipe())
        for key in ['uvGltf','sourceTriangleIds','sourceCornerOrder','oldAuthoredRawBits']:self.assertEqual(child[key].tobytes(),arc[key].tobytes())
        for key in ['positions','normals','tangents']:self.assertEqual(child[key][0,1:].tobytes(),arc[key][0,1:].tobytes())
        self.assertEqual(child['kneeTerminalParentPositions'].tobytes(),p.tobytes());self.assertEqual(child['tangents'][:,:,3].tobytes(),t[:,:,3].tobytes())

    def test_reviewed_serialized_arrays_reject_parent_trial_faces_and_protection_mutations(self):
        original={'POSITION':np.zeros((3,3),'<f4'),'NORMAL':np.tile([0.,0,1.],(3,1)).astype('<f4'),'TANGENT':np.tile([1.,0,0,-1.],(3,1)).astype('<f4')}
        new={k:v.copy() for k,v in original.items()};new['POSITION'][0,0]=.006;F=np.array([[0,1,2]],'<i8');protected=np.array([False,True,True])
        archive={'parentFaces':F.copy(),'protectedRows':np.array([1,2]),**{'parent'+k:v.copy() for k,v in original.items()},**{k:v.copy() for k,v in new.items()}}
        knee.serialized_guard(archive,original,new,F,protected)
        for key in ['parentPOSITION','NORMAL','TANGENT','parentFaces','protectedRows']:
            bad={k:v.copy() for k,v in archive.items()};bad[key].flat[0]+=1
            with self.subTest(key=key),self.assertRaises(ValueError):knee.serialized_guard(bad,original,new,F,protected)
        bad={k:v.copy() for k,v in archive.items()};bad['POSITION']=bad['POSITION'].astype('<f8')
        with self.assertRaises(ValueError):knee.serialized_guard(bad,original,new,F,protected)

    def test_native_serialized_identity_corner_difference_is_measured_without_rewriting(self):
        rows={'POSITION':np.array([[.1,.2,.3],[.2,.3,.4],[.3,.4,.5]],'<f4'),'NORMAL':np.tile([0.,0,1.],(3,1)).astype('<f4'),'TANGENT':np.tile([1.,0,0,-1.],(3,1)).astype('<f4')};F=np.array([[0,1,2]])
        p=rows['POSITION'][F].astype(float)@BASIS.T;n=rows['NORMAL'][F].astype(float)@BASIS.T;t=rows['TANGENT'][F].astype(float);t[:,:,:3]=t[:,:,:3]@BASIS.T
        arc={'positions':p.copy(),'normals':n.copy(),'tangents':t.copy()};native={k:v.copy() for k,v in arc.items()};native['positions'][0,0,2]+=1e-12;native['normals'][0,0,0]+=.00002
        before={k:v.tobytes() for k,v in native.items()};report=knee.native_bridge(rows,rows,F,np.array([False,True,True]),arc,native);subset=report['serializedPIdentityContinuousFloat64FieldCorners']
        self.assertEqual(subset['sourceVertexIDs'],[0]);self.assertEqual(subset['sourceFaceCornerIDs'],[[0,0]]);self.assertEqual(subset['corners'],1);self.assertEqual(subset['maximumNComponentError'],.00002)
        for k,v in native.items():self.assertEqual(v.tobytes(),before[k])

    def test_source_specific_inherited_normal_sets_reject_fourth_new_or_wrong_source_face(self):
        for part,expected in [('shinl',[25828,25932,30336]),('legl',[37038])]:
            knee.inherited_normal_sets(part,expected,expected)
            for old,new in [(expected,expected+[40000]),(expected+[40000],expected),(expected[:-1],expected),(expected,expected[:-1]),([40000],expected)]:
                with self.subTest(part=part,old=old,new=new),self.assertRaises(ValueError):knee.inherited_normal_sets(part,old,new)

    def test_explicit_config_rejects_other_owner_runtime_compound_and_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            tp=Path(directory)/'target.json';target=target_fixture();target['rig'].update(offlineStructureAccepted=True,pilotAcceptanceScope='offline-rig-structure');target['rig']['frames']['working']['lfoot_g'][2][3]=-.4;target['rig']['frames']['runtime']['lfoot_g'][2][3]=-.4*target['rig']['runtimeScale'];tp.write_text(json.dumps(target))
            H=tc.frame(target,'lshin_g','working');end=tc.frame(target,'lfoot_g','working')[:3,3];d=end-H[:3,3];L=float(np.linalg.norm(d));d/=L
            recipe=shin_recipe();proposal={'records':[{'part':'shinl','recipe':recipe,'newZeroFaces':0,'newFiniteOrientationFailures':0}],'arrayArchive':{'path':'fixture','sha256':'1'}}
            c={**tc.binding(tp,target,'working'),'part':'shinl','schemaVersion':1,'kind':'root-pinned-local-knee-terminal-configuration','scope':knee.SCOPE,'statureApplications':0,'fieldApplications':1,'parentFieldsReapplied':False,'globalScaleOrTranslation':False,'joint':'lshin_g','model':tc.model(target,'shinl'),'recipe':recipe,'attachmentWorld':H.tolist(),'axisOriginWorld':H[:3,3].tolist(),'axisUnitWorld':d.tolist(),'jointSpanMetres':L,'expectedExecutor':knee.pin(knee.__file__),'parentReceipt':{'sha256':knee.PARENT_SHA['shinl']},'parentCandidate':{'sha256':knee.CANDIDATE_SHA['shinl']},'ramProposal':{'sha256':knee.PROPOSAL_SHA},'pixelOwnership':{'sha256':knee.OWNERSHIP_SHA},'pendingGates':{k:False for k in knee.FLAGS}}
            c['ramArrays']=copy.deepcopy(proposal['arrayArchive']);c['functionalDependencies']=knee.functional_dependencies();c['inheritedAuthoredNormalExceptionFaces']=knee.INHERITED_NORMAL_FACES['shinl'].copy();c['inheritedNormalConeEvidence']={'sha256':knee.INHERITED_EVIDENCE_SHA['shinl']};knee.validate_config(c,tp,target,proposal)
            for key,value in [('part','shinr'),('coordinateSpace','runtime'),('joint','lthigh_g'),('statureApplications',1),('fieldApplications',2),('parentFieldsReapplied',True),('globalScaleOrTranslation',True),('scope','production'),('noShelfAccepted',True)]:
                bad=copy.deepcopy(c);bad[key]=value
                with self.subTest(key=key),self.assertRaises(ValueError):knee.validate_config(bad,tp,target,proposal)
            bad=copy.deepcopy(c);bad['pendingGates']['materialAccepted']=True
            with self.assertRaises(ValueError):knee.validate_config(bad,tp,target,proposal)
            bad=copy.deepcopy(c);bad['recipe']['ellipseDerivedFromActualCapMask']['radiusUV'][0]+=.001
            with self.assertRaises(ValueError):knee.validate_config(bad,tp,target,proposal)
            bad=copy.deepcopy(c);bad['functionalDependencies'][0]['sha256']='0'*64
            with self.assertRaises(ValueError):knee.validate_config(bad,tp,target,proposal)

if __name__=='__main__':unittest.main()
