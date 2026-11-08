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

    def test_eye_review_binds_each_image_and_compares_the_apertures(self):
        clay, detail = self.pair()
        cfg = self.alignment()
        eye = {'state': 'open', 'observation': 'Both lid rims visible', 'clay': [45, 40, 49], 'detail': [45, 40, 50]}
        cfg['eyeReview'] = {'claySha256': pin(clay)['sha256'], 'detailSha256': pin(detail)['sha256'],
                            'eyes': {'left': eye, 'right': dict(eye, clay=[82,40,51], detail=[82,40,50])}}
        good = prepare(clay, detail, cfg, self.root/'valid')
        self.assertEqual(good['eyeReview']['right']['openingPixels'], [11,10])
        self.assertTrue(Path(good['eyeReview']['left']['comparison']['path']).is_file())
        for height, message in [(0,'no measured lid separation'),(3,'differs')]:
            eye['clay'][2] = 40 + height
            with self.assertRaisesRegex(ValueError, message):
                prepare(clay, detail, cfg, self.root/str(height))
        cfg['eyeReview']['claySha256'] = 'old'
        with self.assertRaisesRegex(ValueError,'stale'):
            prepare(clay, detail, cfg, self.root/'stale')

    def test_paired_batch_cannot_freeze_unreviewed_eyes(self):
        runner = self.runner()
        (self.root/'design').mkdir()
        write(self.root/'design/design-receipt.json', {})
        with self.assertRaisesRegex(ValueError, 'eye review'):
            freeze(self.root,self.root/'blocked.json')

    def test_small_chin_matte_loss_fails_despite_whole_image_alignment(self):
        clay, detail = self.pair()
        with Image.open(detail) as im:
            ImageDraw.Draw(im).rectangle((56,98,72,109), fill=(0,0,0,0))
            im.save(detail)
        cfg = {'featureChecks': {'horns':0,'tusks':0,'neck':'none','hairBelowJaw':True},
               'landmarks': [{'name':n,'clay':xy,'detail':xy} for n,xy in
                             [('jaw-left',[.2,.5]),('jaw-chin',[.5,.83]),('jaw-right',[.8,.5])]]}
        with self.assertRaisesRegex(ValueError,'detail matte misses measured jaw-chin'):
            prepare(clay, detail, cfg, self.root/'clipped')

    def test_curved_horn_evidence_includes_measured_outer_arc(self):
        cfg={'featureChecks':{'horns':2,'tusks':0,'neck':'none','hairBelowJaw':True}}
        marks={'jaw-left':[.7,.6],'jaw-chin':[.5,.8],'jaw-right':[.3,.6],
               'horn-left-root':[.55,.4],'horn-left-tip':[.6,.45],
               'horn-right-root':[.45,.4],'horn-right-tip':[.4,.45],
               'horn-left-curve-outer':[.8,.2],'horn-right-curve-outer':[.2,.2]}
        cfg['landmarks']=[{'name':name,'clay':p,'detail':p} for name,p in marks.items()]
        clay,detail=self.pair()
        result=prepare(clay,detail,cfg,self.root/'curved-horns')
        left=result['featureChecks']['horn-left']['box']
        right=result['featureChecks']['horn-right']['box']
        self.assertGreaterEqual(left[2],109)
        self.assertLessEqual(right[0],19)
        self.assertLessEqual(left[1],19)
        self.assertLessEqual(right[1],19)
        self.assertGreater(left[0],60)
        self.assertLess(right[2],68)
        self.assertTrue(result['manualReviewRequired'])

    def test_profile_reports_process_peak_without_claiming_stage_allocation(self):
        runner=self.runner();receipt=read(runner.state['stages']['prepare']['path'])
        for key in ('packageVerifySeconds','preflightSeconds','processingSeconds','postVerifySeconds','totalSeconds'):
            self.assertGreaterEqual(receipt['profile'][key],0)
        self.assertGreater(receipt['profile']['workerPeakRssBytes'],0)
        profile=receipt['profile']
        self.assertLessEqual(sum(profile[k] for k in ('packageVerifySeconds','preflightSeconds','processingSeconds','postVerifySeconds')),profile['totalSeconds'])


class ScalpAppearanceFrame(Temporary):
    def test_donor_uses_the_measured_source_frame_after_bounds_change(self):
        import numpy as np
        from unittest.mock import Mock, patch
        from headkit.scalp_appearance import ScalpDonor
        original = np.array([[0.,0.,0.],[1.,1.,1.]])
        final = original*2
        recipe = {'center':[.5,.5,.5], 'outline':[[80,25],[100,25],[100,50],[80,50]]}
        corrected = {'output':{'path':'final'}, 'scalpPatch':{'source':{'path':'original'}, 'recipe':recipe}}
        scene = Mock()
        scene.query.return_value = (np.array([1.]), np.array([0]), None)
        field = Mock()
        field.sample.return_value = (np.ones((1,6)), np.array([False]))
        sampled = np.zeros((1,6))
        with patch('headkit.scalp_appearance.verify') as verify, \
             patch('headkit.scalp_appearance.positions',side_effect=[(final,np.array([[0,1,0]])),(original,[])]), \
             patch('headkit.scalp_appearance.EmbreeScene',return_value=scene):
            donor = ScalpDonor(corrected,'bound-runtime')
            donor.transfer(field,np.array([[1.,.9,.5]]),sampled,np.array([False]))
            donor.close()
        self.assertEqual(donor.transferred,1)
        np.testing.assert_array_equal(sampled,np.ones((1,6)))
        origins,directions=scene.query.call_args.args
        np.testing.assert_allclose(origins+2*directions,[[.5,.5,.5]])
        verify.assert_any_call([corrected['scalpPatch']['source']],fresh=True)
        scene.close.assert_called_once()

if __name__=='__main__':unittest.main()
