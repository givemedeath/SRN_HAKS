import copy,unittest
import numpy as np
from diagnostic_upper_arm_girth import validate_approval,mapped_rows,native_child,discrete,PROPOSAL_SHA,ORIGINAL_RECEIPT_SHA
from diagnostic_bicep_girth_math import matrix
from place_purposebuilt_pelvis import BASIS
class UpperArmGirthDiagnosticTests(unittest.TestCase):
    def config(self):
        return {'kind':'root-review-only-upper-arm-girth110-diagnostic-config','coordinateSpace':'working','part':'bicepl','joint':'lbicep_g','factor':1.10,'axialFactor':1.,'statureApplications':0,'originalFitOrPreviousRadialFieldRepeated':False,'rigAndShoulderElbowAnchorsChanged':False,'terminalTaperOrWindowUsed':False,'mirrorHeldUntilActualLeftReview':True,'currentChestCollarRidgesAndLargeTrapsExplicitlyProtected':True,'parentGeometryReceipt':{'sha256':ORIGINAL_RECEIPT_SHA},'protectedNeighborInventory':[{'role':x} for x in ['actual-current-approved-chest-collar-large-traps','current-LEFT-forearm','current-provisional-stock-neck-working']]}
    def approval(self,c):return {'kind':'root-approved-upper-arm-girth110-diagnostic','reviewedBy':'/root','authorizeImplementationAndOneFreshExport':True,'configuration':c,'proposal':{'sha256':PROPOSAL_SHA}}
    def fixture(self):
        p=np.array([[.02,.05,.1],[-.02,.05,.4],[.02,-.05,.8],[.5,.5,.5]]);P=(p@BASIS).astype('<f4');N=np.tile([0,1,0.],(4,1)).astype('<f4');T=np.tile([1,0,0,-1.],(4,1)).astype('<f4');F=np.array([[0,1,2]],dtype=np.int64);M,d,L=matrix([0,0,0],[0,0,1]);return P,N,T,F,M,d,L
    def test_exact_executed_original_left_and_protected_neighbors(self):
        c=self.config();validate_approval(self.approval(c),c)
        for key,value in [('part','bicepr'),('part','legl'),('coordinateSpace','runtime'),('factor',.85),('axialFactor',1.10),('statureApplications',1),('terminalTaperOrWindowUsed',True),('originalFitOrPreviousRadialFieldRepeated',True),('currentChestCollarRidgesAndLargeTrapsExplicitlyProtected',False)]:
            bad=copy.deepcopy(c);bad[key]=value
            with self.assertRaises(ValueError):validate_approval(self.approval(bad),bad)
    def test_missing_current_forearm_or_wrong_original_parent_rejected(self):
        c=self.config();c['protectedNeighborInventory'].pop(1)
        with self.assertRaises(ValueError):validate_approval(self.approval(c),c)
        c=self.config();c['parentGeometryReceipt']['sha256']='bad'
        with self.assertRaises(ValueError):validate_approval(self.approval(c),c)
    def test_root_gate_and_exact_proposal_prevent_unreviewed_recipe(self):
        c=self.config();a=self.approval(c);a['authorizeImplementationAndOneFreshExport']=False
        with self.assertRaises(ValueError):validate_approval(a,c)
        a=self.approval(c);a['proposal']['sha256']='bad'
        with self.assertRaises(ValueError):validate_approval(a,c)
    def test_active_rows_map_once_unused_attributes_literal(self):
        P,N,T,F,M,d,L=self.fixture();N[3]=0;T[3]=[0,0,0,0];rows,active=mapped_rows(P,N,T,F,M);self.assertTrue(np.array_equal(active,[True,True,True,False]));self.assertEqual(rows['POSITION'][3].tobytes(),P[3].tobytes());self.assertEqual(rows['NORMAL'][3].tobytes(),N[3].tobytes());self.assertEqual(rows['TANGENT'][3].tobytes(),T[3].tobytes());p=P.astype(float)@BASIS.T;q=rows['POSITION'].astype(float)@BASIS.T;self.assertTrue(np.array_equal(p[:3,2],q[:3,2]));self.assertTrue(np.allclose(q[:3,:2],p[:3,:2]*1.1,atol=2e-9));self.assertEqual(rows['TANGENT'][:,3].tobytes(),T[:,3].tobytes())
    def test_active_zero_normal_rejected_but_unused_zero_normal_preserved(self):
        P,N,T,F,M,d,L=self.fixture();N[0]=0
        with self.assertRaises(ValueError):mapped_rows(P,N,T,F,M)
    def test_native64_aliases_metadata_and_source_corner_order_literal(self):
        P,N,T,F,M,d,L=self.fixture();p=(P.astype(float)@BASIS.T)[F];n=(N.astype(float)@BASIS.T)[F];t=T.astype(float).copy();t[:,:3]=t[:,:3]@BASIS.T;a={'positions':p,'normals':n,'tangents':t[F],'uvGltf':np.array([[[0.,0.],[1,0],[1,1]]]),'sourceCornerOrder':np.array([[0,1,2]]),'sourceTriangleIds':np.array([8])};q=native_child(a,M);self.assertEqual(q['girthParentPositions'].tobytes(),p.tobytes());self.assertEqual(q['girthParentNormals'].tobytes(),n.tobytes());self.assertEqual(q['uvGltf'].tobytes(),a['uvGltf'].tobytes());self.assertEqual(q['sourceCornerOrder'].tobytes(),a['sourceCornerOrder'].tobytes());self.assertTrue(np.array_equal(q['positions'][...,2],p[...,2]));self.assertTrue(np.allclose(q['positions'][...,:2],p[...,:2]*1.1));self.assertEqual(q['tangents'][...,3].tobytes(),a['tangents'][...,3].tobytes())
    def test_no_shelf_proof_is_constant_homothety_but_keeps_literal_gate(self):
        P,N,T,F,M,d,L=self.fixture();rows,active=mapped_rows(P,N,T,F,M);r=discrete(P,rows['POSITION'],F,np.eye(4),M,d,L);self.assertTrue(r['standingNoShelvesRule']['sameAxisStationRadialContourHomothety']);self.assertTrue(r['standingNoShelvesRule']['constantJacobianNoStationWindowOrTaper']);self.assertTrue(r['standingNoShelvesRule']['actualShoulderElbowJointRidgeShelfRenderReviewRequired']);self.assertFalse(r['standingNoShelvesRule']['globalOrClientAcceptanceClaim']);self.assertEqual(r['beforeTopology']['boundaryEdges'],r['afterTopology']['boundaryEdges'])
    def test_wrong_axis_or_repeated_field_breaks_expected_precision_and_fails(self):
        P,N,T,F,M,d,L=self.fixture();rows,active=mapped_rows(P,N,T,F,M);second,unused=mapped_rows(rows['POSITION'],rows['NORMAL'],rows['TANGENT'],F,M)
        with self.assertRaises(ValueError):discrete(P,second['POSITION'],F,np.eye(4),M,d,L)
if __name__=='__main__':unittest.main()
