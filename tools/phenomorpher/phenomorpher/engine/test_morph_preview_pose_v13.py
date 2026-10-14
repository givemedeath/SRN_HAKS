import unittest
import numpy as np
from .morph_preview_pose_v13 import evaluate_accepted,evaluate_adjusted,sample_native_times,pose_samples,pose_rigid_meshes,validate_pose_hierarchy,bound_female_actor,static_bind_frames,backsolve_canonical_local_positions,native_keys_hash

def turn(axis,angle):
    x,y,z=np.eye(3)[axis];c=np.cos(angle);s=np.sin(angle);k=np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
    return np.eye(3)*c+(1-c)*np.outer([x,y,z],[x,y,z])+s*k

def fixture():
    skeleton={name:{'parent':parent,'position':np.array(position,float),'rotation':np.eye(3)} for name,parent,position in [
        ('pfh0','null',[0,0,0]),('rootdummy','pfh0',[0,0,1]),('pelvis_g','rootdummy',[0,0,0]),
        ('lfoot_g','pelvis_g',[-.1,0,-1]),('rfoot_g','pelvis_g',[.1,0,-1])]}
    clip={'name':'pause1','length':1.,'nodes':{'rootdummy':{'controls':{8:{'times':np.array([0,1],dtype='f4'),
        'values':np.array([[0,0,1],[0,0,1.02]],dtype='f4')}}},'pelvis_g':{'controls':{20:{'times':np.array([0,1],dtype='f4'),
        'values':np.array([[0,0,0,1],[0,0,.01,1]],dtype='f4')}}}}}
    return {'skeleton':skeleton,'row':{'root':'pfh0','carrier':'srn_fa_h0','literalActorScaleToken':'1'},'clips':{
        'pause1':clip,'pause2':{**clip,'name':'pause2'}}}

class AcceptedPoseTests(unittest.TestCase):
    def test_noncommuting_local_rotations_compose_through_parent_once(self):
        baseline=fixture();baseline['skeleton']['lfoot_g']['rotation']=turn(0,.4)
        offsets={'pelvis_g':turn(1,.2),'lfoot_g':turn(2,-.3)}
        native=evaluate_adjusted(baseline,'pause1',1,{})
        posed=evaluate_adjusted(baseline,'pause1',1,{},local_rotation_offsets=offsets)
        native_p=native['pelvis_g'][:3,:3];expected_parent=offsets['pelvis_g']@native_p
        expected_child=expected_parent@offsets['lfoot_g']@turn(0,.4)
        np.testing.assert_allclose(posed['lfoot_g'][:3,:3],expected_child,atol=1e-12)
        self.assertGreater(np.linalg.norm(expected_child-offsets['lfoot_g']@expected_parent@turn(0,.4)),.01)
        np.testing.assert_allclose(posed['lfoot_g'][:3,3],posed['pelvis_g'][:3,3]+expected_parent@baseline['skeleton']['lfoot_g']['position'])

    def test_canonical_backsolve_handles_rotated_parent_native_root_translation(self):
        baseline=fixture();baseline['skeleton']['rootdummy']['position']=np.array([.3,.1,.8])
        desired=evaluate_adjusted(baseline,'pause1',0,{},1.4,local_rotation_offsets={'pelvis_g':turn(1,.3),'lfoot_g':turn(0,.2)})
        desired['lfoot_g'][:3,3]+=[.15,-.06,.08]
        positions,offsets=backsolve_canonical_local_positions(baseline,desired,1.4)
        replay=evaluate_adjusted(baseline,'pause1',0,positions,1.4,local_rotation_offsets=offsets)
        for name in desired:np.testing.assert_allclose(replay[name],desired[name],atol=1e-12)
        bind=static_bind_frames(baseline['skeleton'],positions,local_rotation_offsets=offsets)
        expected=offsets['pelvis_g']@baseline['skeleton']['pelvis_g']['rotation']
        np.testing.assert_allclose(np.linalg.inv(bind['rootdummy'])@bind['pelvis_g'],np.block([[expected,positions['pelvis_g'][:,None]],[np.zeros((1,3)),np.ones((1,1))]]),atol=1e-12)

    def test_offsets_keep_keys_immutable_and_report_actual_protected_rotations(self):
        baseline=fixture();baseline['skeleton']['torso_g']={'parent':'pelvis_g','position':np.array([0,0,.2]),'rotation':turn(0,.1)}
        before=native_keys_hash(baseline)
        report=pose_samples(baseline,local_rotation_offsets={'lfoot_g':turn(1,.2)})
        self.assertEqual(before,native_keys_hash(baseline))
        self.assertTrue(all(r['pelvisRotationDifferenceDegrees']==0 and r['upperLeanRotationDifferenceDegrees']==0 for r in report['samples']))
        changed=pose_samples(baseline,local_rotation_offsets={'pelvis_g':turn(1,.2)})
        self.assertGreater(changed['samples'][0]['pelvisRotationDifferenceDegrees'],10.)
        self.assertGreater(changed['samples'][0]['upperLeanRotationDifferenceDegrees'],10.)
        self.assertFalse(changed['motionFitValidated'])

    def test_invalid_offsets_reflection_shear_unknown_and_alias_conflict_fail(self):
        baseline=fixture()
        for offsets in ({'pelvis_g':np.diag([-1,1,1])},{'pelvis_g':np.diag([2,1,1])},{'missing':np.eye(3)},{'pelvis_g':np.zeros((4,4))}):
            with self.assertRaises(ValueError):evaluate_adjusted(baseline,'pause1',0,{},local_rotation_offsets=offsets)
        with self.assertRaisesRegex(ValueError,'one rotation'):evaluate_adjusted(baseline,'pause1',0,{},local_rotation_offsets={},local_rotation_corrections={})

    def test_identity_preserves_byte_exact_native_frames_and_mesh_rig_transport(self):
        baseline=fixture();native=evaluate_adjusted(baseline,'pause1',.5,{})
        explicit=evaluate_adjusted(baseline,'pause1',.5,{},local_rotation_offsets={})
        for name in native:self.assertTrue(np.array_equal(native[name],explicit[name]))
        offsets={'lfoot_g':turn(1,.2)};bind=static_bind_frames(baseline['skeleton'],{},local_rotation_offsets=offsets)
        posed=evaluate_adjusted(baseline,'pause1',0,{},local_rotation_offsets=offsets)
        mesh={'part':'footl','name':'foot','position':np.array([[0,0,0],[1,0,0],[0,1,0]],float),'faces':np.array([[0,1,2]])}
        out=pose_rigid_meshes([mesh],bind,posed)[0];delta=posed['lfoot_g']@np.linalg.inv(bind['lfoot_g'])
        np.testing.assert_allclose(out['position'],mesh['position']@delta[:3,:3].T+delta[:3,3],atol=1e-12)
    def test_actor_source_compatibility_rejects_unpinned_mesh_or_duplicate_changes(self):
        with self.assertRaisesRegex(ValueError,'Unbound female actor source compatibility'):
            bound_female_actor(b'node trimesh rootdummy\n render 1\nendnode',{'root':'pfh0','actorOwnedCarrierStaticNodes':56})
    def test_complete_hierarchy_rejects_missing_animated_joint_and_parent(self):
        baseline=fixture();validate_pose_hierarchy(baseline['skeleton'],baseline['clips'],'pfh0','srn_fa_h0')
        baseline['clips']['pause1']['nodes']['missing']={'controls':{}}
        with self.assertRaisesRegex(ValueError,'Animated joint'):validate_pose_hierarchy(baseline['skeleton'],baseline['clips'],'pfh0','srn_fa_h0')
        baseline=fixture();baseline['skeleton']['lfoot_g']['parent']='missing'
        with self.assertRaisesRegex(ValueError,'Incomplete'):validate_pose_hierarchy(baseline['skeleton'],baseline['clips'],'pfh0','srn_fa_h0')
    def test_identity_and_explicit_scaled_positions_match_native_pose(self):
        baseline=fixture()
        for time in sample_native_times(baseline['clips']['pause1']):
            accepted=evaluate_accepted(baseline,'pause1',time)
            adjusted=evaluate_adjusted(baseline,'pause1',time,{n:v['position'].copy() for n,v in baseline['skeleton'].items()})
            for n in accepted:self.assertTrue(np.array_equal(accepted[n],adjusted[n]))

    def test_changed_bone_translation_exposes_foot_drift_preserving_native_keys(self):
        baseline=fixture();control=baseline['clips']['pause1']['nodes']['rootdummy']['controls'][8]
        before=control['values'].tobytes()
        result=pose_samples(baseline,{'lfoot_g':[-.1,0,-1.1]})
        self.assertAlmostEqual(result['worstFootDrift']['maximumDriftMeters'],.1)
        self.assertGreater(result['standingFootJointDriftMeters'],.09)
        self.assertFalse(result['motionFitValidated'])
        self.assertEqual(control['values'].tobytes(),before)
        first=evaluate_adjusted(baseline,'pause1',0,{'lfoot_g':[-.1,0,-1.1]})
        last=evaluate_adjusted(baseline,'pause1',1,{'lfoot_g':[-.1,0,-1.1]})
        self.assertAlmostEqual(last['rootdummy'][2,3]-first['rootdummy'][2,3],.02,places=6)

    def test_rigid_mesh_pose_transforms_all_vertices_preserves_faces(self):
        mesh={'part':'footl','name':'foot','position':np.array([[0,0,0],[1,0,0],[0,1,0]],float),'faces':np.array([[0,1,2]])}
        bind={'lfoot_g':np.eye(4)};posed={'lfoot_g':np.eye(4)};posed['lfoot_g'][:3,3]=[2,3,4]
        trial=pose_rigid_meshes([mesh],bind,posed)[0]
        self.assertTrue(np.array_equal(trial['position'],mesh['position']+[2,3,4]))
        self.assertTrue(np.array_equal(trial['faces'],mesh['faces']))
        self.assertTrue(np.array_equal(mesh['position'][0],[0,0,0]))

    def test_native_times_include_endpoints_and_midpoints(self):
        self.assertEqual(sample_native_times(fixture()['clips']['pause1']),[0.,.5,1.])

    def test_constant_stance_offset_not_falsely_reported_as_dynamic_drift(self):
        baseline=fixture();result=pose_samples(baseline,{'rootdummy':[1,0,1]})
        self.assertAlmostEqual(result['standingFootJointDriftMeters'],1)
        self.assertLess(result['worstDynamicPlantResidual']['maximumDriftMeters'],1e-12)
        self.assertIn('standing stance and foot-surface review pending',result['footPlantDiagnosticStatus'])

    def test_offset_rotated_by_native_motion_exposes_dynamic_plant_drift(self):
        result=pose_samples(fixture(),{'lfoot_g':[.3,0,-1]})
        self.assertGreater(result['worstDynamicPlantResidual']['maximumDriftMeters'],.002)
        self.assertEqual(result['footPlantDiagnosticStatus'],'dynamic-motion-unresolved')

if __name__=='__main__':unittest.main()
