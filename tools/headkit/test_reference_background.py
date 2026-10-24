"""Conditional foreground routing and review gates, without running a GPU model."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image,ImageDraw
from headkit.common import pin
from headkit.reference_background import analyze_reference,require_conditioning_review
from headkit.comfy import compile_graph
from headkit.comfy_nodes.model_resolution import model_choices
from headkit.comfy_nodes.verified_loaders import verified_loader_mappings


class ReferenceBackgroundTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def image(self,name,mode='RGB',colour='gray'):
        path=self.root/name;Image.new(mode,(32,32),colour).save(path);return path
    def cutout(self,name='cutout.png'):
        image=Image.new('RGBA',(32,32),(0,0,0,0));ImageDraw.Draw(image).rectangle((12,4,19,27),fill=(180,150,100,255))
        path=self.root/name;image.save(path);return path
    def graph(self,decision):
        return compile_graph('calibrate','pixal-single-v1',dict.fromkeys(('geometry','detail','mask'),'source.png'),'itemkit/background-test',background=decision)
    def test_opaque_rgb_and_rgba_require_local_removal(self):
        for mode in ('RGB','RGBA'):
            with self.subTest(mode=mode):
                decision=analyze_reference(self.image(mode+'.png',mode))
                self.assertEqual(decision['route'],'remove')
                graph=self.graph(decision)
                self.assertEqual(model_choices(graph),[('background_removal','birefnet.safetensors'),('geometry_estimation','moge_2_vitl_normal_fp16.safetensors')])
                self.assertEqual(graph['5']['inputs']['masks'],['1001',0])
                self.assertEqual(graph['6']['inputs']['masks'],['1001',0])
    def test_existing_alpha_skips_model_and_keeps_mask(self):
        decision=analyze_reference(self.cutout())
        self.assertEqual(decision['route'],'preserve-alpha')
        graph=self.graph(decision)
        self.assertNotIn('1000',graph);self.assertNotIn('1001',graph)
        self.assertEqual(graph['5']['inputs']['masks'],['4',0])
        self.assertEqual(graph['6']['inputs']['masks'],['4',0])
    def test_empty_or_clipped_alpha_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'foreground'):
            analyze_reference(self.image('empty.png','RGBA',(0,0,0,0)))
        path=self.cutout();image=Image.open(path);ImageDraw.Draw(image).point((0,10),fill='white');image.save(path)
        with self.assertRaisesRegex(ValueError,'clipped'):analyze_reference(path)
    def test_mask_cutout_and_normalized_mask_are_retained_without_alpha_inversion(self):
        graph=self.graph(analyze_reference(self.image('opaque.png')))
        self.assertEqual(graph['1004']['inputs']['mask'],['1001',0])
        self.assertEqual(graph['1005']['inputs']['alpha'],['1004',0])
        self.assertEqual(graph['1005']['inputs']['image'],['1',0])
        self.assertEqual(graph['1009']['inputs']['masks'],graph['5']['inputs']['masks'])
        self.assertEqual(graph['1009']['inputs']['images'],['1008',0])
        for key in ('1003','1006','1010'):
            self.assertEqual(graph[key]['class_type'],'SaveImage')
    def reviewed(self):
        reference=self.image('original.png');cutout=self.cutout()
        with Image.open(cutout) as image:
            image.getchannel('A').save(self.root/'mask.png')
            image.convert('RGB').save(self.root/'normalized.png')
        def row(path):return {'path':Path(path).name,'sha256':pin(path)['sha256']}
        inputs={'reference':row(reference),'geometry':row(self.root/'normalized.png'),
                'detail':row(self.root/'normalized.png'),'foregroundMask':row(self.root/'mask.png')}
        review={'decision':'approved','route':'remove','notes':'Mask, tip and opening inspected',
                'imageSha256':inputs['geometry']['sha256'],'maskSha256':inputs['foregroundMask']['sha256'],
                'referenceSha256':inputs['reference']['sha256']}
        return {'inputs':inputs,'approval':{'background':review}}
    def test_review_binds_source_image_and_mask_and_rejects_visible_background(self):
        data=self.reviewed();manifest=self.root/'asset.json'
        self.assertGreater(require_conditioning_review(manifest,data)['foregroundFraction'],0)
        data['approval']['background']['maskSha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Stale background'):require_conditioning_review(manifest,data)
        data=self.reviewed();path=self.root/'normalized.png';image=Image.open(path);ImageDraw.Draw(image).point((1,1),fill='gray');image.save(path)
        data['inputs']['geometry']['sha256']=pin(path)['sha256'];data['inputs']['detail']=dict(data['inputs']['geometry'])
        data['approval']['background']['imageSha256']=pin(path)['sha256']
        with self.assertRaisesRegex(ValueError,'still contains background'):require_conditioning_review(manifest,data)
    def test_missing_review_cannot_use_previously_approved_full_canvas(self):
        data=self.reviewed();data['approval']={'inputReviewComplete':True}
        with self.assertRaisesRegex(ValueError,'Review background isolation'):require_conditioning_review(self.root/'asset.json',data)
    def test_resampling_fringe_is_bounded_to_one_pixel_not_a_background_allowance(self):
        data=self.reviewed();path=self.root/'normalized.png';manifest=self.root/'asset.json'
        with Image.open(path) as image:
            image.putpixel((11,10),(15,15,15));image.save(path)
        def bind():
            data['inputs']['geometry']['sha256']=pin(path)['sha256']
            data['inputs']['detail']=dict(data['inputs']['geometry'])
            data['approval']['background']['imageSha256']=pin(path)['sha256']
        bind();self.assertEqual(require_conditioning_review(manifest,data)['resamplingFringePixels'],1)
        with Image.open(path) as image:image.putpixel((10,10),(15,15,15));image.save(path)
        bind()
        with self.assertRaisesRegex(ValueError,'still contains background'):require_conditioning_review(manifest,data)
    def test_background_loader_wraps_classmethod_execution_with_hash_keys(self):
        marker=object()
        class Loader:
            FUNCTION='execute';RETURN_TYPES=('BACKGROUND_REMOVAL',)
            @classmethod
            def INPUT_TYPES(cls):return {'required':{'bg_removal_name':(['birefnet.safetensors'],)}}
            @classmethod
            def execute(cls,bg_removal_name):return marker
        wrapper=verified_loader_mappings({'LoadBackgroundRemovalModel':Loader},object())['HeadkitVerifiedLoadBackgroundRemovalModelV1']
        with patch('headkit.comfy_nodes.verified_loaders.verify_model_file') as verify:
            self.assertIs(wrapper().load_verified('a'*64,'b'*64,bg_removal_name='birefnet.safetensors'),marker)
            self.assertEqual(verify.call_args.args[:4],('background_removal','birefnet.safetensors','b'*64,'a'*64))
