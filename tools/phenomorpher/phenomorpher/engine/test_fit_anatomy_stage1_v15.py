import unittest
from unittest.mock import patch
import numpy as np
from . import fit_anatomy_stage1_v15a as engine

def frame(position=(0,0,0),rotation=None):
    f=np.eye(4);f[:3,3]=position
    if rotation is not None:f[:3,:3]=rotation
    return f

def segment_frames():
    result={}
    for part,(a,b) in engine.SEGMENTS.items():
        result.setdefault(a,frame());result[b]=frame(result[a][:3,3]+np.array([.4 if part.endswith('l') else .5,0,0]))
    return result

class AnatomyFirstTests(unittest.TestCase):
    def test_raw_motion_gate_requires_all_six_clips_and_all_thirteen_links(self):
        source=[{'part':'chest'}];candidate={'standingMeshes':[{'part':'chest'}],'standingFrames':{},'localPositions':{},'localRotationOffsets':{},'uniformScale':.7,'partScales':{p:.7 for p in engine.PART_JOINTS}}
        baseline={'clips':{clip:{'length':1.} for clip in engine.CLIPS}};inventory={pair:object() for pair in engine.LINKS}
        contact={'minimumTriangleClearanceMeters':0.,'actualTerminalContact':True}
        with patch.object(engine,'evaluate_adjusted',return_value={}),patch.object(engine,'pose_rigid_meshes',side_effect=lambda m,*a:m),patch.object(engine,'terminal_contact',return_value=contact):
            result=engine.motion_contact_gate(source,{}, {},baseline,candidate,inventory,{}, {'samples':[{'clip':'run','timeSeconds':.3,'sourceRelativeFootTrajectoryErrorMeters':.1}]})
        self.assertEqual({r['clip'] for r in result['samples']},set(engine.CLIPS));self.assertTrue(all(len(r['connectors'])==13 for r in result['samples']));self.assertFalse(result['IKApplied']);self.assertTrue(result['allSelectedPoseGates'])
    def test_motion_contact_failure_rejects_candidate_without_widening_clearance(self):
        candidate={'standingMeshes':[],'standingFrames':{},'localPositions':{},'localRotationOffsets':{},'uniformScale':.7,'partScales':{p:.7 for p in engine.PART_JOINTS}};baseline={'clips':{clip:{'length':1.} for clip in engine.CLIPS}}
        reports=[{'minimumTriangleClearanceMeters':0.,'actualTerminalContact':True},{'minimumTriangleClearanceMeters':.001,'actualTerminalContact':False}]*13
        with patch.object(engine,'evaluate_adjusted',return_value={}),patch.object(engine,'pose_rigid_meshes',side_effect=lambda m,*a:m),patch.object(engine,'terminal_contact',side_effect=reports):
            result=engine.motion_contact_gate([],{}, {},baseline,candidate,{p:object() for p in engine.LINKS},{},{'samples':[{'clip':'run','timeSeconds':.3,'sourceRelativeFootTrajectoryErrorMeters':.1}]})
        self.assertFalse(result['allSelectedPoseGates']);self.assertTrue(result['evaluationStoppedOnFailedCandidate']);self.assertTrue(all(r['numericEpsilonMeters']==1e-8 for r in result['samples'][0]['connectors']))
    def test_connected_static_chain_floor_and_stature_without_nonuniform_mesh_warp(self):
        frames={'pelvis_g':frame((0,0,1.)),'torso_g':frame((0,0,1.25)),'neck_g':frame((0,0,1.7)),'head_g':frame((0,0,1.85))}
        parents={'pelvis_g':'null','torso_g':'pelvis_g','neck_g':'torso_g','head_g':'neck_g'}
        for side,x in (('l',-.2),('r',.2)):
            for name,z,parent in (('bicep',1.5,'torso_g'),('forearm',1.15,side+'bicep_g'),('hand',.9,side+'forearm_g'),('thigh',1.,'pelvis_g'),('shin',.6,side+'thigh_g'),('foot',.1,side+'shin_g')):
                joint=side+name+'_g';frames[joint]=frame((x,0,z));parents[joint]=parent
        meshes=[]
        for part,joint in engine.PART_JOINTS.items():
            offsets=np.array([[-.04,0,-.1],[.04,0,-.1],[0,.1,-.02]]) if part.startswith('foot') else np.array([[0,0,0],[.04,0,0],[0,.03,.05]])
            meshes.append({'part':part,'name':part,'position':frames[joint][:3,3]+offsets,'faces':np.array([[0,1,2]]),'render':True})
        skeleton={n:{'parent':parents[n],'position':f[:3,3].copy(),'rotation':np.eye(3)} for n,f in frames.items()};baseline={'skeleton':skeleton};capture={}
        def backsolve(b,w,s):capture['world']={n:f.copy() for n,f in w.items()};return {n:f[:3,3] for n,f in w.items()},{n:np.eye(3) for n in w}
        with patch.object(engine,'backsolve_canonical_local_positions',side_effect=backsolve),patch.object(engine,'static_bind_frames',side_effect=lambda *a,**k:capture['world']),patch.object(engine,'evaluate_adjusted',side_effect=lambda *a,**k:capture['world']),patch.object(engine,'pose_rigid_meshes',side_effect=lambda m,*a:engine.copy_meshes(m)):
            factors={p:(.9 if p in ('legl','legr','shinl','shinr') else 1.) for p in engine.PART_JOINTS};result=engine.build_candidate(meshes,frames,baseline,1.27,factors)
        self.assertLess(max(abs(z) for z in result['candidateFloor'].values()),1e-9)
        self.assertAlmostEqual(max(m['position'][:,2].max() for m in result['standingMeshes']),1.27)
        for name in ('pelvis_g','torso_g'):self.assertTrue(np.array_equal(result['standingFrames'][name][:3,:3],frames[name][:3,:3]))
        for old,new in zip(meshes,result['standingMeshes']):
            source_distance=np.linalg.norm(old['position'][1]-old['position'][0]);candidate_distance=np.linalg.norm(new['position'][1]-new['position'][0]);self.assertAlmostEqual(candidate_distance/source_distance,result['partScales'][old['part']])
    def test_stature_target_is_rest_pose_not_standing_pose(self):
        # The standing pause1 pose stands lower than rest; the target is rest-pose crown to sole.
        frames={'pelvis_g':frame((0,0,1.)),'torso_g':frame((0,0,1.25)),'neck_g':frame((0,0,1.7)),'head_g':frame((0,0,1.85))}
        parents={'pelvis_g':'null','torso_g':'pelvis_g','neck_g':'torso_g','head_g':'neck_g'}
        for side,x in (('l',-.2),('r',.2)):
            for name,z,parent in (('bicep',1.5,'torso_g'),('forearm',1.15,side+'bicep_g'),('hand',.9,side+'forearm_g'),('thigh',1.,'pelvis_g'),('shin',.6,side+'thigh_g'),('foot',.1,side+'shin_g')):
                joint=side+name+'_g';frames[joint]=frame((x,0,z));parents[joint]=parent
        meshes=[{'part':part,'name':part,'position':frames[joint][:3,3]+np.array([[0,0,0],[.04,0,0],[0,.03,.05]]),'faces':np.array([[0,1,2]]),'render':True}
                for part,joint in engine.PART_JOINTS.items()]
        skeleton={n:{'parent':parents[n],'position':f[:3,3].copy(),'rotation':np.eye(3)} for n,f in frames.items()};capture={}
        def backsolve(b,w,s):capture['world']={n:f.copy() for n,f in w.items()};return {n:f[:3,3] for n,f in w.items()},{n:np.eye(3) for n in w}
        def to_rest(m,*a):  # the rest pose is the standing pose stretched 2% upward from the floor
            out=engine.copy_meshes(m)
            for x in out:x['position']=x['position']*[1,1,1.02]
            return out
        with patch.object(engine,'backsolve_canonical_local_positions',side_effect=backsolve),patch.object(engine,'static_bind_frames',side_effect=lambda *a,**k:capture['world']),patch.object(engine,'evaluate_adjusted',side_effect=lambda *a,**k:capture['world']),patch.object(engine,'pose_rigid_meshes',side_effect=to_rest):
            result=engine.build_candidate(meshes,frames,baseline:={'skeleton':skeleton},1.27,{p:1. for p in engine.PART_JOINTS})
        rest=np.concatenate([m['position'] for m in result['bindMeshes']]);standing=np.concatenate([m['position'] for m in result['standingMeshes']])
        self.assertAlmostEqual(float(np.ptp(rest[:,2])),1.27);self.assertAlmostEqual(float(np.ptp(standing[:,2])),1.27/1.02)
    def test_bilateral_multiplier_preserves_original_asymmetry(self):
        targets={name:{'preferredMultiplier':1.2} for name in engine.GROUPS};factors=engine.bilateral_factors(targets,.5)
        self.assertEqual(factors['legl'],factors['legr']);self.assertAlmostEqual(.4*factors['legl']/(.5*factors['legr']),.8)
        self.assertEqual(factors['head'],1.)
    def test_missing_metrics_use_source_not_historical_exact_image_targets(self):
        targets=engine.length_targets({}, {'proposedTargets':{'upperArmLength':{'modelFittingMeters':100.}}},segment_frames(),.7)
        self.assertTrue(all(not r['available'] and r['preferredMultiplier']==1. for r in targets.values()))
    def test_design_slack_is_separate_from_measurement_uncertainty(self):
        targets=engine.length_targets({'measurements':{'shinLength':{'preferredMeters':.3,'designSlackFraction':.05,'measurementUncertaintyMeters':.008,'confidenceWeight':.35}}},{},segment_frames(),1.)
        self.assertEqual(targets['shin']['measurementUncertaintyMeters'],.008);self.assertEqual(targets['shin']['designSlackFraction'],.05);self.assertEqual(targets['shin']['weight'],.35)
        self.assertLessEqual(targets['shin']['preferredMultiplier'],1.2);self.assertGreaterEqual(targets['shin']['preferredMultiplier'],.8)
    def test_multimesh_similarity_retains_faces_render_uv_and_owner_offset(self):
        a={'lbicep_g':frame((1,2,3))};rotation=np.array([[0,-1,0],[1,0,0],[0,0,1.]])
        b={'lbicep_g':frame((4,5,6),rotation)};uv=np.array([[.1,.2],[.3,.4],[.5,.6]])
        meshes=[{'part':'bicepl','name':name,'position':np.array([[2.,2,3],[1,3,3],[1,2,4]]),'faces':np.array([[0,1,2]]),'render':visible,'uv':uv} for name,visible in (('a',True),('b',False))]
        result=engine.pure_similarities(meshes,a,b,{'bicepl':.5})
        for old,new in zip(meshes,result):
            self.assertTrue(np.array_equal(new['faces'],old['faces']));self.assertIs(new['uv'],uv);self.assertEqual(new['render'],old['render'])
            self.assertTrue(np.allclose(new['position'],b['lbicep_g'][:3,3]+.5*(old['position']-a['lbicep_g'][:3,3])@rotation.T))
        self.assertTrue(np.array_equal(meshes[0]['position'][0],[2,2,3]))
    def test_invalid_scale_or_improper_rotation_is_rejected(self):
        mesh=[{'part':'bicepl','name':'x','position':np.zeros((3,3)),'faces':np.array([[0,1,2]])}];a={'lbicep_g':frame()};b={'lbicep_g':frame(rotation=np.diag([-1,1,1]))}
        with self.assertRaises(ValueError):engine.pure_similarities(mesh,a,b,{'bicepl':1.})
        with self.assertRaises(ValueError):engine.pure_similarities(mesh,a,a,{'bicepl':0.})
    def test_exact_human_branch_preserves_bind_geometry_and_frames(self):
        frames={'pelvis_g':frame()};mesh=[{'part':'pelvis','name':'p','position':np.array([[0.,0,0],[1,0,0],[0,0,1]]),'faces':np.array([[0,1,2]]),'render':True}]
        baseline={'skeleton':{'pelvis_g':{'parent':'null','position':np.zeros(3),'rotation':np.eye(3)}},'clips':{n:{} for n in engine.CLIPS}}
        with patch.object(engine,'native_keys_hash',return_value='same'),patch.object(engine,'evaluate_adjusted',return_value=frames),patch.object(engine,'pose_rigid_meshes',side_effect=lambda m,*args:engine.copy_meshes(m)):
            result=engine.fit_stage1(mesh,frames,baseline,{'slug':'human_female_fit','targetStatureMeters':1.},preserve=True)
        self.assertTrue(np.array_equal(result['bindMeshes'][0]['position'],mesh[0]['position']));self.assertTrue(np.array_equal(result['bindFrames']['pelvis_g'],frames['pelvis_g']))
        self.assertTrue(result['receipt']['identityPreserved']);self.assertFalse(result['receipt']['IKApplied'])

if __name__=='__main__':unittest.main()
