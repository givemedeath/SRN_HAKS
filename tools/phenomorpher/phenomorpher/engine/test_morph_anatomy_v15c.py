import unittest
from unittest.mock import patch
import numpy as np
from . import morph_anatomy_v15c as M

def tube(part,x=0,width=.4,low=0,high=1):
 points=[];faces=[]
 for i,z in enumerate(np.linspace(low,high,21)):
  points.extend([[x+dx,y,z] for dx,y in ((-width/2,-.1),(width/2,-.1),(width/2,.1),(-width/2,.1))])
  if i:
   for j in range(4):
    a=4*(i-1)+j;b=4*(i-1)+(j+1)%4;c=b+4;d=a+4;faces.extend(((a,b,c),(a,c,d)))
 return {'part':part,'name':part+'mesh','render':True,'position':np.array(points),'faces':np.array(faces),'attachmentFrame':np.eye(4).tolist(),'uv':['authored']}
def fixture():
 source=[tube('chest',low=.4,high=.9),tube('pelvis',low=.1,high=.7),tube('legl',-.3,.2,0,.5),tube('legr',.3,.2,0,.5),tube('head',width=.15,low=.9,high=1),tube('neck',width=.12,low=.8,high=.95),tube('footl',-.3,.2,-.05,0),tube('footr',.3,.2,-.05,0)]
 frames={}
 for n,pos in [('pelvis_g',[0,0,.3]),('torso_g',[0,0,.3]),('neck_g',[0,0,.9]),('lthigh_g',[-.3,0,.5]),('rthigh_g',[.3,0,.5]),('lshin_g',[-.3,0,0]),('rshin_g',[.3,0,0]),('head_g',[0,0,.9]),('lfoot_g',[-.3,0,-.025]),('rfoot_g',[.3,0,-.025])]:
  f=np.eye(4);f[:3,3]=pos;frames[n]=f
 stage={'standingMeshes':source,'bindMeshes':M.copy_meshes(source),'standingFrames':frames,'bindFrames':frames,'receipt':{'native':'preserved'},'uniformScale':1.}
 packet={'views':{'front':{k+'Height':{'value':v} for k,v in [('chest',.7),('waist',.55),('midThigh',.25)]}},'proposedTargets':{'chestWidth':{'modelFittingMeters':.8},'waistWidth':{'modelFittingMeters':.8},'midThighWidth':{'modelFittingMeters':.4}}}
 stage.update(sourceStandingMeshes=M.copy_meshes(source),sourceStandingFrames={n:f.copy() for n,f in frames.items()},partScales={m['part']:1. for m in source})
 packet['canonicalCalibration']={'sourceDonorId':'human-female-v1','sourceCanonicalJointFramesMeters':{n:f.tolist() for n,f in frames.items()}}
 for key,row in packet['proposedTargets'].items():
  section=key.removesuffix('Width').removesuffix('Depth');fraction=packet['views']['front'][section+'Height']['value'];row.update(sourceFraction=fraction,sourcePlaneZMeters=-.05+1.05*fraction,sourceStandingStatureMeters=1.05,destinationFraction=fraction)
 return stage,packet
class FakeContact:
 def __init__(self,source,frames,motion):self.source=source;self.rejectTorso=False
 def check(self,meshes,parts=None):return True,[{'parts':list(p),'sourceCalibratedTerminalGatePassed':True} for p in M.LINKS]
class RegionalConflictContact(FakeContact):
 def check(self,meshes,parts=None):
  if parts and 'chest' in parts:
   i=next(i for i,m in enumerate(meshes) if m['part']=='chest');change=np.max(np.abs(meshes[i]['position']-self.source[i]['position']))
   return change<.032,[{'parts':['chest','pelvis'],'sourceCalibratedTerminalGatePassed':change<.032}]
  return super().check(meshes,parts)
class AnatomyFirstTests(unittest.TestCase):
 def test_missing_arm_geometry_is_unavailable_not_an_invented_width(self):
  stage,packet=fixture();rows=M.measurements(stage['standingMeshes'],stage['standingFrames'],packet)
  self.assertIsNone(rows['upperArmWidth']);self.assertIsNone(rows['forearmWidth'])
 def test_soft_design_slack_and_uncertainty_are_separate(self):
  row=M.guide({'preferredMeters':1.,'confidence':1.,'designSlackFraction':.1,'measurementUncertaintyMeters':10},None)
  self.assertEqual(M.soft_factor(1.05,row),1.);self.assertAlmostEqual(M.soft_factor(.5,row),1.8);self.assertEqual(row['measurementUncertaintyMeters'],10)
 def test_source_detail_shared_torso_frame_and_fixed_limb_centers(self):
  stage,packet=fixture();frames=stage['standingFrames'];source=stage['standingMeshes']
  limb=M.regional_frame(source,frames,'legl');changed=M.deform_region(source,'legl',limb,[1.5,1.2]);original=source[2]['position'];new=changed[2]['position']
  np.testing.assert_array_equal(new[[0,1,2,3,-4,-3,-2,-1]],original[[0,1,2,3,-4,-3,-2,-1]])
  for z in np.unique(new[:,2]):self.assertAlmostEqual(new[new[:,2]==z,0].mean(),-.3)
  torso=M.regional_frame(source,frames,'torso');self.assertAlmostEqual(torso[1][2],1.);self.assertTrue(np.isfinite(torso[1]).all())
 def test_single_fresh_pass_protected_geometry_topology_metadata_and_frames(self):
  stage,packet=fixture();before=M.geometry_hash(stage['standingMeshes']);frozen={n:f.copy() for n,f in stage['standingFrames'].items()}
  with patch.object(M,'ContactBaseline',FakeContact):result=M.fit_stage2(stage,packet,{})
  self.assertEqual(before,M.geometry_hash(stage['standingMeshes']));self.assertEqual(result['receipt']['kind'],'anatomy-first-stage2-v15c');self.assertTrue(result['receipt']['motionContactValidationPending']);self.assertFalse(result['receipt']['productionAccepted'])
  for s,m,b in zip(stage['standingMeshes'],result['standingMeshes'],result['bindMeshes']):
   np.testing.assert_array_equal(s['faces'],m['faces']);self.assertEqual(s['uv'],m['uv']);self.assertEqual(s['attachmentFrame'],m['attachmentFrame'])
   if s['part'] in ('head','neck','footl','footr'):np.testing.assert_array_equal(s['position'],m['position']);np.testing.assert_array_equal(s['position'],b['position'])
  for n,f in frozen.items():np.testing.assert_array_equal(f,result['standingFrames'][n])
  self.assertFalse(result['receipt']['measurementUncertaintyAddedToSlack']);self.assertIsNotNone(result['receipt']['guideMeasurements']['waistWidth']['deviationMeters'])
 def test_one_conflicting_region_does_not_flatten_other_regions(self):
  stage,packet=fixture()
  with patch.object(M,'ContactBaseline',RegionalConflictContact):result=M.fit_stage2(stage,packet,{})
  regions={x['region']:x for x in result['receipt']['regions']};self.assertLess(regions['torso']['retainedRegionalFraction'],1);self.assertEqual(regions['legl']['retainedRegionalFraction'],1);self.assertEqual(regions['legr']['retainedRegionalFraction'],1)
 def test_human_identity_is_exact_in_standing_and_bind(self):
  stage,packet=fixture();result=M.fit_stage2(stage,packet,{},preserve=True)
  for s,m,b in zip(stage['standingMeshes'],result['standingMeshes'],result['bindMeshes']):np.testing.assert_array_equal(s['position'],m['position']);np.testing.assert_array_equal(s['position'],b['position']);np.testing.assert_array_equal(s['faces'],m['faces'])
  self.assertTrue(result['receipt']['identityPreserved']);self.assertFalse(result['receipt']['shapeMorphApplied'])
 def test_low_confidence_reduces_adjustment_and_invalid_guides_rejected(self):
  high=M.guide({'preferredMeters':1,'confidence':1},None);low=M.guide({'preferredMeters':1,'confidence':.2},None)
  self.assertLess(M.soft_factor(.5,low)-1,M.soft_factor(.5,high)-1)
  for row in ({'preferredMeters':-1},{'preferredMeters':1,'confidence':2},{'preferredMeters':1,'designSlackFraction':1}):
   with self.assertRaises(ValueError):M.guide(row,None)



class RootPolicyIntegrationTests(unittest.TestCase):
 def test_for_target_label_and_weight_schema_is_used_without_casting_label(self):
  from .anatomy_policy_v15 import for_target
  stage,packet=fixture();packet['slug']='dwarf_female_fit';packet['targetStatureMeters']=1.05
  packet['proposedTargets']['chestWidth']['basis']='garment-surface provisional'
  policy=for_target(packet);self.assertEqual(policy['measurements']['chestWidth']['confidence'],'low');self.assertEqual(policy['measurements']['waistWidth']['confidence'],'medium')
  with patch.object(M,'ContactBaseline',FakeContact):result=M.fit_stage2(stage,packet,policy)
  rows=result['receipt']['guideMeasurements'];self.assertEqual(rows['chestWidth']['confidence'],'low');self.assertEqual(rows['chestWidth']['confidenceWeight'],.35);self.assertEqual(rows['waistWidth']['confidenceWeight'],.7);self.assertEqual(rows['chestWidth']['designSlackFraction'],.1)
  self.assertFalse(result['receipt']['measurementUncertaintyAddedToSlack']);self.assertFalse(result['receipt']['productionAccepted'])
 def test_unknown_label_and_invalid_numeric_weight_rejected(self):
  for row in ({'preferredMeters':1,'confidence':'bogus'},{'preferredMeters':1,'confidence':'low','confidenceWeight':1.1}):
   with self.assertRaises(ValueError):M.guide(row,None)



class RegisteredAnatomyMeasurements(unittest.TestCase):
 def test_reference_destination_fraction_does_not_change_registered_chest_plane(self):
  stage,packet=fixture();packet['proposedTargets']['chestWidth']['destinationFraction']=.4;packet['views']['front']['chestHeight']['value']=.4
  for collection in (stage['standingMeshes'],stage['sourceStandingMeshes']):
   for mesh in collection:
    if mesh['part'] in ('chest','pelvis'):mesh['position'][:,0]*=(1+mesh['position'][:,2])
  registration=M.build_registration(stage,packet);row=registration['chestWidth'];self.assertEqual(row['status'],'registered-source-anatomical-plane');self.assertEqual(row['destinationReferenceFraction'],.4)
  self.assertAlmostEqual(row['candidatePlanePointMeters'][2] if 'candidatePlanePointMeters' in row else row['transports'][0]['candidatePlanePointMeters'][2],-.05+1.05*.7)
  value=M.registered_measurements(stage['standingMeshes'],stage['standingFrames'],packet,registration)['chestWidth'];self.assertAlmostEqual(value,.4*(1+(-.05+1.05*.7)));self.assertNotAlmostEqual(value,.4*(1+(-.05+1.05*.4)))
 def test_affine_plane_and_dimension_basis_transport_are_correct(self):
  stage,packet=fixture();rotation=np.array([[0.,0.,1.],[0.,1.,0.],[-1.,0.,0.]])
  for n,f in stage['standingFrames'].items():f[:3,3]=1.2*rotation@f[:3,3]+[.3,0,.4];f[:3,:3]=rotation@f[:3,:3]
  for part in stage['partScales']:stage['partScales'][part]=1.2
  row=M.build_registration(stage,packet)['chestWidth'];self.assertEqual(row['status'],'registered-source-anatomical-plane');t=row['transports'][0];matrix=np.array(t['sourceToCandidateSimilarity']);n=np.linalg.inv(matrix[:3,:3]).T@row['sourcePlaneNormal'];n/=np.linalg.norm(n)
  np.testing.assert_allclose(n,t['candidatePlaneNormal'],atol=1e-12);self.assertAlmostEqual(np.dot(t['candidatePlaneNormal'],t['candidateProjectedDimensionDirection']),0,places=12)
 def test_missing_or_changed_source_provenance_is_unavailable(self):
  stage,packet=fixture();packet['canonicalCalibration']['sourceCanonicalJointFramesMeters']['pelvis_g'][0][3]+=.01
  row=M.build_registration(stage,packet)['chestWidth'];self.assertEqual(row['status'],'unavailable');self.assertIn('binding differs',row['reason']);self.assertIsNone(M.registered_measurements(stage['standingMeshes'],stage['standingFrames'],packet,{'chestWidth':row})['chestWidth'])
 def test_inconsistent_shared_torso_scale_is_not_invented(self):
  stage,packet=fixture();stage['partScales']['chest']=1.1;row=M.build_registration(stage,packet)['chestWidth'];self.assertEqual(row['status'],'unavailable');self.assertIn('share one',row['reason'])

class CoordinatedProfileTests(unittest.TestCase):
 def test_C1_positive_nonovershooting_no_waist_notch_or_chest_corner(self):
  anchors=[(0.,1.),(.3,1.1),(.7,1.5),(1.,1.)];q=np.linspace(0,1,10001);f=M.smooth_log_profile(q,anchors)
  self.assertTrue(np.isfinite(f).all());self.assertGreaterEqual(f.min(),1.);self.assertLessEqual(f.max(),1.5+1e-12)
  self.assertTrue(np.all(np.diff(f[(q>=.3)&(q<=.7)])>=-1e-12))
  h=1e-6
  for z,_ in anchors:
   left=(M.smooth_log_profile(z,anchors)-M.smooth_log_profile(z-h,anchors))/h
   right=(M.smooth_log_profile(z+h,anchors)-M.smooth_log_profile(z,anchors))/h
   self.assertLess(abs(float(left-right)),1e-3)
  self.assertLess(abs(float((M.smooth_log_profile(h,anchors)-1)/h)),1e-3)
  self.assertLess(abs(float((1-M.smooth_log_profile(1-h,anchors))/h)),1e-3)
 def test_registered_chest_and_waist_have_independent_factors_not_averaged(self):
  stage,packet=fixture();packet['proposedTargets']['chestWidth']['modelFittingMeters']=.8;packet['proposedTargets']['waistWidth']['modelFittingMeters']=.44
  packet['proposedTargets']['chestWidth'].update(sourcePlaneZMeters=.7,sourceFraction=.75/1.05);packet['proposedTargets']['waistWidth'].update(sourcePlaneZMeters=.55,sourceFraction=.6/1.05)
  registration=M.build_registration(stage,packet);initial=M.registered_measurements(stage['standingMeshes'],stage['standingFrames'],packet,registration)
  guides={k:M.guide({'preferredMeters':r['modelFittingMeters'],'confidenceWeight':1},r) for k,r in packet['proposedTargets'].items()}
  result,receipt=M.coordinated_torso_profile(stage['standingMeshes'],M.regional_frame(stage['standingMeshes'],stage['standingFrames'],'torso'),initial,guides,registration,[.75,1.5])
  measured=M.registered_measurements(result,stage['standingFrames'],packet,registration)
  self.assertAlmostEqual(measured['chestWidth'],.6,places=10);self.assertAlmostEqual(measured['waistWidth'],.4,places=10)
  self.assertTrue(receipt['sharedChestPelvisFrame']);self.assertFalse(receipt['fieldStackingApplied'])
 def test_fresh_source_repeatable_preserves_axial_coordinates_and_terminal_context(self):
  stage,packet=fixture();frozen=M.geometry_hash(stage['standingMeshes'])
  with patch.object(M,'ContactBaseline',FakeContact):a=M.fit_stage2(stage,packet,{});b=M.fit_stage2(stage,packet,{})
  self.assertEqual(M.geometry_hash(a['standingMeshes']),M.geometry_hash(b['standingMeshes']));self.assertEqual(frozen,M.geometry_hash(stage['standingMeshes']))
  frame=M.regional_frame(stage['standingMeshes'],stage['standingFrames'],'torso');o,axis,w,d,low,high=frame
  for source,out in zip(stage['standingMeshes'],a['standingMeshes']):
   if source['part'] not in ('chest','pelvis'):continue
   np.testing.assert_allclose((source['position']-o)@axis,(out['position']-o)@axis,atol=1e-14,rtol=0)
   z=(source['position']-o)@axis;terminal=(z<=low)|(z>=high);np.testing.assert_array_equal(source['position'][terminal],out['position'][terminal])
 def test_invalid_order_and_short_anchor_span_are_explicitly_unavailable(self):
  stage,packet=fixture();packet['proposedTargets']['chestWidth'].update(sourceFraction=.54,sourcePlaneZMeters=-.05+1.05*.54)
  with patch.object(M,'ContactBaseline',FakeContact):out=M.fit_stage2(stage,packet,{})
  torso=out['receipt']['regions'][0];self.assertEqual(torso['coordinatedProfile']['status'],'unavailable');self.assertIn('order',torso['coordinatedProfile']['reason'])
  np.testing.assert_array_equal(stage['standingMeshes'][0]['position'],out['standingMeshes'][0]['position'])

if __name__=='__main__':unittest.main()
