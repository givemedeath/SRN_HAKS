import unittest
import numpy as np
from .morph_preview_pose_v13 import evaluate_adjusted,native_keys_hash
from .morph_preview_pose_constraints_v14a import two_bone_ik,shortest_rotation,evaluate_constrained

def fixture():
    rows=[('actor','null',[0,0,0]),('rootdummy','actor',[0,0,2]),('pelvis_g','rootdummy',[0,0,0]),('torso_g','pelvis_g',[0,0,.2]),('neck_g','torso_g',[0,0,.2]),('head_g','neck_g',[0,0,.1]),('upper_attachment','torso_g',[.1,.1,0])]
    for side,x in (('l',-.2),('r',.2)):
        rows.extend([(side+'thigh_g','pelvis_g',[x,0,0]),(side+'shin_g',side+'thigh_g',[.2,0,-.7]),(side+'foot_g',side+'shin_g',[-.2,.05,-.7]),(side+'toe',side+'foot_g',[0,.15,0]),(side+'thigh_attachment',side+'thigh_g',[.1,0,-.1])])
    skeleton={n:{'parent':p,'position':np.array(v,float),'rotation':np.eye(3)} for n,p,v in rows}
    clip={'name':'pause1','length':1.,'nodes':{'rootdummy':{'controls':{8:{'times':np.array([0,1.]),'values':np.array([[0,0,2],[0,0,2.03]])}}},'pelvis_g':{'controls':{20:{'times':np.array([0,1.]),'values':np.array([[0,0,0,1],[0,0,np.sin(.1),np.cos(.1)]])}}}}}
    baseline={'skeleton':skeleton,'row':{'root':'actor','carrier':'carrier','literalActorScaleToken':'1'},'clips':{'pause1':clip,'pause2':{**clip,'name':'pause2'}}}
    source={n:r['position'].copy() for n,r in skeleton.items()};positions={n:v.copy() for n,v in source.items()}
    for side in ('l','r'):positions[side+'shin_g']=np.array([.2,.05,-.9]);positions[side+'foot_g']=np.array([-.2,.2,-.6])
    result={'uniformScale':1.,'sourceLocalPositions':source,'localPositions':positions,'localRotationOffsets':{},'standingFrames':evaluate_adjusted(baseline,'pause1',0,positions)}
    return baseline,result

class PoseConstraintTests(unittest.TestCase):
    def test_reachable_target_keeps_two_lengths_and_knee_pole(self):
        hip=np.array([0.,0,0]);knee=np.array([.6,0,-.8]);foot=np.array([0.,0,-1.6]);target=np.array([.2,.1,-1.5])
        new_knee,actual,receipt=two_bone_ik(hip,knee,foot,target)
        np.testing.assert_allclose(actual,target,atol=1e-12)
        self.assertAlmostEqual(np.linalg.norm(new_knee-hip),1.);self.assertAlmostEqual(np.linalg.norm(actual-new_knee),1.)
        self.assertFalse(receipt['reachClamped']);self.assertGreater(new_knee[0],0)
    def test_far_and_inner_unreachable_targets_report_exact_reach_clamp(self):
        for target,expected in (([0,0,-5],3.),([0,0,-.1],1.)):
            knee,foot,receipt=two_bone_ik([0,0,0],[0,0,-2],[0,0,-3],target)
            self.assertTrue(receipt['reachClamped']);self.assertAlmostEqual(np.linalg.norm(foot),expected)
            self.assertAlmostEqual(np.linalg.norm(knee),2.);self.assertAlmostEqual(np.linalg.norm(foot-knee),1.)
            self.assertGreater(receipt['requestedReachResidualMeters'],0)
    def test_straight_zero_distance_and_antiparallel_rotations_are_finite_proper(self):
        for target in ([0,0,-1.5],[0,0,0],[0,0,2]):
            knee,foot,receipt=two_bone_ik([0,0,0],[0,0,-1],[0,0,-2],target,[0,0,-1])
            self.assertTrue(np.isfinite(knee).all());self.assertAlmostEqual(np.linalg.norm(knee),1.);self.assertAlmostEqual(np.linalg.norm(foot-knee),1.)
        r=shortest_rotation([0,0,-1],[0,0,1]);np.testing.assert_allclose(r@[0,0,-1],[0,0,1],atol=1e-12);self.assertAlmostEqual(np.linalg.det(r),1.)
    def test_native_relative_trajectory_fixed_lengths_exact_upper_and_keys(self):
        baseline,stage=fixture();before=native_keys_hash(baseline);native=evaluate_adjusted(baseline,'pause2',1,stage['localPositions'])
        frames,receipt=evaluate_constrained(baseline,'pause2',1,stage)
        self.assertEqual(before,native_keys_hash(baseline));self.assertEqual(receipt['nativeKeysSha256Before'],receipt['nativeKeysSha256After'])
        for n in ('actor','rootdummy','pelvis_g','torso_g','neck_g','head_g','upper_attachment'):np.testing.assert_array_equal(frames[n],native[n])
        src=evaluate_adjusted(baseline,'pause2',1,stage['sourceLocalPositions']);standing=evaluate_adjusted(baseline,'pause1',0,stage['sourceLocalPositions'])
        for side in ('l','r'):
            foot=side+'foot_g';row=receipt['legs'][side];expected=stage['standingFrames'][foot][:3,3]+src[foot][:3,3]-standing[foot][:3,3]
            np.testing.assert_allclose(row['requestedFootMeters'],expected,atol=1e-12)
            for bone in ('upper','lower'):self.assertAlmostEqual(row['actualLengthsMeters'][bone],row['lengthsMeters'][bone],places=12)
            np.testing.assert_array_equal(frames[foot][:3,:3],native[foot][:3,:3]);self.assertFalse(receipt['boneStretchApplied'])
        self.assertFalse(receipt['assetApprovalCreated'])
    def test_foot_attachment_counterrotation_propagates_once(self):
        baseline,stage=fixture();native=evaluate_adjusted(baseline,'pause2',1,stage['localPositions']);frames,receipt=evaluate_constrained(baseline,'pause2',1,stage)
        for side in ('l','r'):
            foot=side+'foot_g';toe=side+'toe';local=np.linalg.inv(native[foot])@native[toe]
            np.testing.assert_allclose(frames[toe],frames[foot]@local,atol=1e-12)
            np.testing.assert_array_equal(frames[toe][:3,:3],native[toe][:3,:3])
    def test_human_bypass_and_standing_identity_are_exact(self):
        baseline,stage=fixture();frames,receipt=evaluate_constrained(baseline,'pause1',0,stage)
        for n in frames:np.testing.assert_array_equal(frames[n],stage['standingFrames'][n])
        self.assertFalse(receipt['constraintsApplied']);self.assertTrue(receipt['standingIdentityPreserved'])
        native=evaluate_adjusted(baseline,'pause2',.5,stage['localPositions']);frames,receipt=evaluate_constrained(baseline,'pause2',.5,stage,preserve=True)
        for n in frames:np.testing.assert_array_equal(frames[n],native[n])
        self.assertTrue(receipt['preserveHumanFitIdentity']);self.assertFalse(receipt['constraintsApplied'])
    def test_source_arrays_and_stage_frames_unchanged(self):
        baseline,stage=fixture();before={n:m.copy() for n,m in stage['standingFrames'].items()};positions={n:p.copy() for n,p in stage['localPositions'].items()}
        evaluate_constrained(baseline,'pause2',.5,stage)
        for n in before:np.testing.assert_array_equal(stage['standingFrames'][n],before[n]);np.testing.assert_array_equal(stage['localPositions'][n],positions[n])


class ExactReachShellTests(unittest.TestCase):
    def test_outer_shell_roundtrip_length_roundoff_cannot_create_knee_bend(self):
        hip=np.array([.121,-.057,.843]);axis=np.array([.231,-.142,-.962]);axis/=np.linalg.norm(axis)
        upper=.417234561234;lower=.283546734567
        pole=np.cross(axis,[1.,0,0]);pole/=np.linalg.norm(pole)
        knee=hip+upper*(.8*axis+.6*pole);foot=knee+lower*axis
        for drift in (-2e-16,0.,2e-16):
            k0=knee+drift*axis;f0=foot-drift*axis
            length=np.linalg.norm(k0-hip)+np.linalg.norm(f0-k0)
            k,end,row=two_bone_ik(hip,k0,f0,hip+2*length*axis)
            self.assertEqual(row['reachShellSolution'],'outer-exact-collinear');self.assertEqual(row['kneeRadiusMeters'],0.)
            self.assertLess(np.linalg.norm(np.cross(k-hip,end-hip)),1e-16)
            self.assertAlmostEqual(np.linalg.norm(k-hip),row['lengthsMeters']['upper'],places=14)
            self.assertAlmostEqual(np.linalg.norm(end-k),row['lengthsMeters']['lower'],places=14)
    def test_inner_shell_handles_both_length_orderings_without_cancellation(self):
        for upper,lower in ((.413,.287),(.287,.413)):
            k,end,row=two_bone_ik([0,0,0],[upper,0,0],[upper,lower,0],[.01,0,0])
            expected=upper if upper>lower else -upper
            np.testing.assert_array_equal(k,[expected,0,0]);self.assertEqual(row['kneeRadiusMeters'],0.)
            self.assertEqual(row['reachShellSolution'],'inner-exact-collinear')
            self.assertAlmostEqual(np.linalg.norm(end-k),lower,places=14)
    def test_genuinely_interior_near_shell_remains_bent_and_not_clamped(self):
        k,end,row=two_bone_ik([0,0,0],[.6,0,-.8],[0,0,-1.6],[0,0,-(2.-1e-8)])
        self.assertEqual(row['reachShellSolution'],'interior-fixed-length');self.assertGreater(row['kneeRadiusMeters'],0.)
        self.assertFalse(row['reachClamped']);self.assertAlmostEqual(np.linalg.norm(k),1.,places=14);self.assertAlmostEqual(np.linalg.norm(end-k),1.,places=14)

if __name__=='__main__':unittest.main()
