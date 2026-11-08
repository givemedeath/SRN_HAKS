"""Explicit clay fallback binds both images, masks, landmarks and reviews."""
import copy
import unittest
from tools.headkit import test_reference_background as background_tests
from tools.itemkit.conditioning import require_conditioning_review, validate_pair
from tools.itemkit.contracts import stage_roles
from tools.headkit.common import pin


class ClayPairTests(unittest.TestCase):
    setUp=background_tests.ReferenceBackgroundTests.setUp
    tearDown=background_tests.ReferenceBackgroundTests.tearDown
    image=background_tests.ReferenceBackgroundTests.image
    cutout=background_tests.ReferenceBackgroundTests.cutout
    reviewed=background_tests.ReferenceBackgroundTests.reviewed
    def pair_data(self):
        data=self.reviewed();data['conditioning']='clay-detail-v1'
        data['inputs']['geometryForegroundMask']=dict(data['inputs']['foregroundMask'])
        data['approval']['geometryBackground']=copy.deepcopy(data['approval']['background'])
        data['approval']['referencePair']={'decision':'approved','notes':'Matched framing, silhouette and openings reviewed',
            **{role+'Sha256':data['inputs'][role]['sha256'] for role in ('reference','geometry','detail','geometryForegroundMask','foregroundMask')},
            'landmarks':[{'name':str(i),'geometry':p,'detail':p} for i,p in enumerate(([.5,.1],[.5,.5],[.5,.7],[.5,.9]))]}
        return data

    def test_pair_checks_each_background_and_both_image_hashes(self):
        data=self.pair_data();self.assertEqual(set(require_conditioning_review(self.root/'asset.json',data)),{'geometry','detail'})
        for field in ('geometrySha256','detailSha256','geometryForegroundMaskSha256','foregroundMaskSha256'):
            changed=copy.deepcopy(data);changed['approval']['referencePair'][field]='0'*64
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'Stale clay/detail'):validate_pair(changed)
        data['approval']['geometryBackground']['decision']='rejected'
        with self.assertRaisesRegex(ValueError,'Review background'):require_conditioning_review(self.root/'asset.json',data)

    def test_unreviewed_or_misaligned_pair_cannot_pass(self):
        data=self.pair_data();data['approval']['referencePair']['landmarks'][0]['geometry']=[.4,.1]
        with self.assertRaisesRegex(ValueError,'alignment'):validate_pair(data)
        data=self.pair_data();data['approval']['referencePair']['decision']='rejected'
        with self.assertRaisesRegex(ValueError,'Review the clay'):validate_pair(data)

    def mixed_pair(self):
        data=self.pair_data();clay=self.cutout('raw-clay.png')
        data['inputs']['clayReference']={'path':clay.name,'sha256':pin(clay)['sha256']}
        data['approval']['geometryBackground'].update(route='preserve-alpha',referenceSha256=pin(clay)['sha256'])
        return data

    def test_transparent_clay_and_opaque_detail_keep_independent_source_routes(self):
        data=self.mixed_pair()
        self.assertEqual(set(require_conditioning_review(self.root/'asset.json',data)),{'geometry','detail'})
        data['approval']['geometryBackground']['route']='remove'
        with self.assertRaisesRegex(ValueError,'route differs'):
            require_conditioning_review(self.root/'asset.json',data)

    def test_clay_source_cannot_borrow_detailed_source_approval_or_change_bytes(self):
        data=self.mixed_pair()
        data['approval']['geometryBackground']['referenceSha256']=data['inputs']['reference']['sha256']
        with self.assertRaisesRegex(ValueError,'Stale background'):
            require_conditioning_review(self.root/'asset.json',data)
        data=self.mixed_pair();self.image('raw-clay.png')
        with self.assertRaisesRegex(ValueError,'Stale file pin'):
            require_conditioning_review(self.root/'asset.json',data)

    def test_source_used_by_pair_review_is_consumed_by_generation_stages(self):
        for stage in ('geometry','appearance'):
            self.assertIn('clayReference',stage_roles(stage))
        for stage in ('fit','bake','render'):
            self.assertNotIn('clayReference',stage_roles(stage))
