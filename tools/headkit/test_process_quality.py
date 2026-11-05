"""Regression tests for preflight, conditioning evidence and GPU handoff freshness."""
from pathlib import Path
import sys
import unittest
from PIL import Image, ImageDraw
from headkit.test_headkit import Temporary
from headkit.common import pin, write, read
from headkit.runner import Runner
from headkit.cameras import review_cameras
from headkit.review_images import render_plan, material_inputs
from headkit.images import prepare,feature_landmarks
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headbatch'))
from gpu_inputs import freeze
from head_setup import face_quality_profile

class ProcessQuality(Temporary):
    def pair(self):
        files=[]
        for name,colour in (('clay','gray'),('detail','brown')):
            path=self.root/(name+'.png');image=Image.new('RGBA',(128,128));ImageDraw.Draw(image).rectangle((20,20,108,108),fill=colour);image.save(path);files.append(path)
        return files
    def alignment(self):
        return {'landmarks':[{'name':str(i),'clay':p,'detail':p} for i,p in enumerate(([.3,.3],[.7,.3],[.5,.7]))]}
    def runner(self):
        clay,detail=self.pair();head=self.root
        write(head/'bindings.json',self.bindings_data())
        write(head/'manifest.json',{'schemaVersion':1,'id':'fixture','profile':'pixal-single-v1',
             'inputs':{'clay':dict(pin(clay),path=clay.name),'detail':dict(pin(detail),path=detail.name)},'alignment':self.alignment(),
             'features':[{'name':'hair','placementReviewed':True}],'approval':{'referenceDesignReviewed':True}})
        runner=Runner(head/'manifest.json',head/'bindings.json',head/'run')
        runner.execute('prepare');runner.review('prepare','approved','synthetic test fixture only')
        return runner

    def test_prepared_gpu_snapshot_rejects_changed_manifest_and_bytes(self):
        runner=self.runner()
        result=freeze(self.root,self.root/'frozen.json')
        self.assertEqual(result['attempt'],'attempt-01')
        self.assertTrue(result['review'] in result['pins'])
        self.assertTrue(pin(self.root/'manifest.json') in result['pins'])
        data=read(self.root/'manifest.json');data['alignment']['maximumRelativeResidual']=.009;write(self.root/'manifest.json',data)
        with self.assertRaisesRegex(ValueError,'Stale stage'):freeze(self.root,self.root/'bad.json')
        write(self.root/'manifest.json',runner.data)
        Path(result['images']['detail']['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Stale'):freeze(self.root,self.root/'changed.json')

    def test_unapproved_prepare_cannot_reach_gpu(self):
        runner=self.runner();runner.state['reviews']={};write(runner.state_path,runner.state)
        with self.assertRaisesRegex(ValueError,'review pending'):freeze(self.root,self.root/'bad.json')

    def test_face_profile_is_renderable_and_missing_maps_fail_before_blender(self):
        cfg=face_quality_profile()['render'];cfg['cameras']=review_cameras([[0,0,0],[1,1,1]],-90)
        self.assertEqual(len(render_plan(cfg)),84)
        del cfg['materialConstants']
        with self.assertRaisesRegex(ValueError,'Missing render material inputs'):render_plan(cfg)
        cfg['materialConstants']={'roughness':.8,'metallic':0,'opacity':1}
        cfg['mapsBySize']={'1024':{'roughness':'conflicting-map'}}
        with self.assertRaisesRegex(ValueError,'both a map and a constant'):render_plan(cfg)

    def test_material_constants_reject_nonfinite_and_out_of_range(self):
        for value in (float('nan'),float('inf'),-1,2,True):
            with self.subTest(value=value),self.assertRaises(ValueError):
                material_inputs({'modes':['clay'],'materialConstants':{'roughness':value}})

    def test_feature_checks_require_roots_tips_and_jaw_and_keep_hair_allowed(self):
        cfg=self.alignment();cfg['featureChecks']={'horns':2,'tusks':2,'neck':'none','hairBelowJaw':True}
        with self.assertRaisesRegex(ValueError,'Missing horn/tusk'):feature_landmarks(cfg)
        names=['jaw-left','jaw-chin','jaw-right']+[f'{part}-{side}-{end}' for part in ('horn','tusk') for side in ('left','right') for end in ('root','tip')]
        positions=([.3,.6],[.5,.8],[.7,.6],[.3,.3],[.25,.2],[.7,.3],[.75,.2],[.4,.5],[.35,.4],[.6,.5],[.65,.4])
        cfg['landmarks']=[{'name':name,'clay':p,'detail':p} for name,p in zip(names,positions)]
        clay,detail=self.pair();result=prepare(clay,detail,cfg,self.root/'checked')
        self.assertEqual(set(result['featureChecks']),{'jaw','horn-left','horn-right','tusk-left','tusk-right'})
        self.assertTrue(result['manualReviewRequired'])
        self.assertTrue(Path(result['featureChecks']['jaw']['comparison']['path']).is_file())

    def test_profile_reports_process_peak_without_claiming_stage_allocation(self):
        runner=self.runner();receipt=read(runner.state['stages']['prepare']['path'])
        for key in ('packageVerifySeconds','preflightSeconds','processingSeconds','postVerifySeconds','totalSeconds'):
            self.assertGreaterEqual(receipt['profile'][key],0)
        self.assertGreater(receipt['profile']['workerPeakRssBytes'],0)
        profile=receipt['profile']
        self.assertLessEqual(sum(profile[k] for k in ('packageVerifySeconds','preflightSeconds','processingSeconds','postVerifySeconds')),profile['totalSeconds'])

if __name__=='__main__':unittest.main()
