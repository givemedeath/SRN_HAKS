"""Regressions for conditioning roles, authored skin detail and true runtime previews."""
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from headkit.runner import Runner
from headkit.face_encode import skin_preservation,treat,TREATMENT
from headkit.review_images import atlas_sets
from headkit.cameras import review_cameras

class LocalPaintTests(unittest.TestCase):
    def test_registered_eyes_sample_expected_reference_and_preserve_neighbors(self):
        from headkit.common import pin
        from headkit.reference_eyes import restore
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = np.full((64,64,3), 190, np.uint8)
            source[32,18] = [12,17,24]
            source[32,46] = [24,17,12]
            Image.fromarray(source).save(root/'ref.png')
            yy,xx = np.indices((64,64))
            np.savez(root/'view.npz', hit=np.ones((64,64),bool), face=(xx<yy).astype(int),
                     centre=np.zeros(3), span=1.)
            uv = np.array([[[0,0],[1,0],[1,1]],[[0,0],[1,1],[0,1]]])
            value = dict(uv=uv, faces=np.array([[0,1,2],[0,2,3]]),
                         positions=np.array([[-.5,.5,0],[.5,.5,0],[.5,-.5,0],[-.5,-.5,0]]))
            masks = dict(frontView=pin(root/'view.npz'),frontRender={'sha256':'frame'})
            spec = dict(frontSha256='frame', referenceSha256=pin(root/'ref.png')['sha256'])
            for side,centre in [('R',18),('L',46)]:
                spec[side] = dict(reference=[centre,32,3,3],target=[centre,32,3,3])
            opening = np.zeros((64,64),float)
            opening[30:35,16:21] = opening[30:35,44:49] = 1
            labels = np.zeros((64,64),int)
            labels[32,17] = 1
            colour = np.zeros((64,64,3),np.float32)
            counts = restore(colour, labels, opening, value, masks, root/'ref.png', spec)
            self.assertEqual(counts, {'R':24,'L':25})
            np.testing.assert_array_equal(colour[32,[18,46]], source[32,[18,46]])
            self.assertFalse(colour[32,17].any())
            self.assertFalse(colour[opening==0].any())
            with self.assertRaisesRegex(ValueError,'reference bytes'):
                restore(colour, labels, opening, value, masks, root/'ref.png', dict(spec,frontSha256='stale'))

    def test_reference_lid_repair_is_review_bound_visible_and_skin_only(self):
        import hashlib
        from headkit.common import pin
        from headkit.reference_eyes import restore
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            front = np.full((64,64,3), 128, np.uint8)
            Image.fromarray(front).save(root/'front.png')
            Image.fromarray(np.full_like(front,190)).save(root/'ref.png')
            yy,xx = np.indices((64,64))
            zbuf = np.zeros((64,64)); zbuf[29,19] = .1
            np.savez(root/'view.npz', hit=np.ones((64,64),bool), face=(xx<yy).astype(int),
                     centre=np.zeros(3), span=1., zbuf=zbuf)
            value = dict(uv=np.array([[[0,0],[1,0],[1,1]],[[0,0],[1,1],[0,1]]]),
                         faces=np.array([[0,1,2],[0,2,3]]),
                         positions=np.array([[-.5,.5,0],[.5,.5,0],[.5,-.5,0],[-.5,-.5,0]]))
            masks = dict(frontView=pin(root/'view.npz'),frontRender=pin(root/'front.png'))
            spec = dict(frontSha256=masks['frontRender']['sha256'],
                        referenceSha256=pin(root/'ref.png')['sha256'], includeLids=True)
            contours = dict(rgbSha256=hashlib.sha256(front.tobytes()).hexdigest())
            for side,c in [('R',18),('L',46)]:
                spec[side] = dict(reference=[c,32,3,3],target=[c,32,3,3])
                contours[side] = dict(opening=[[c-3,31],[c+3,31],[c+3,33],[c-3,33]],
                                     iris=[[c-1,31],[c+1,31],[c+1,33],[c-1,33]],
                                     excludeBrow=[[c-5,28],[c+5,28],[c+5,36],[c-5,36]])
            labels = np.zeros((64,64),int); labels[29,17:19] = [1,2]
            opening = np.zeros((64,64),float)
            colour = np.zeros_like(front,dtype=np.float32)
            restore(colour,labels,opening,value,masks,root/'ref.png',spec,contours=contours)
            np.testing.assert_array_equal(colour[29,20], [190]*3)
            self.assertFalse(colour[29,17:20].any())  # hair, metal and occluded skin
            self.assertFalse(colour[20].any())
            self.assertTrue(np.all(colour[28,20] < 190))  # soft outer boundary
            with self.assertRaisesRegex(ValueError,'reviewed contours'):
                restore(colour,labels,opening,value,masks,root/'ref.png',spec)
            with self.assertRaisesRegex(ValueError,'exact front-render'):
                restore(colour,labels,opening,value,masks,root/'ref.png',spec,
                        contours=dict(contours,rgbSha256='stale'))
            with self.assertRaisesRegex(ValueError,'boolean'):
                restore(colour,labels,opening,value,masks,root/'ref.png',dict(spec,includeLids=1),contours=contours)

    def test_material_outline_uses_declared_axes_and_rejects_degenerate_contours(self):
        from headkit.paint import surface_outline
        points = np.array([[.2,.9,.2], [.8,.1,.8], [.2,.1,.8]])
        spec = dict(axes='xz', points=[[0,0],[.8,0],[0,.8]])
        np.testing.assert_array_equal(surface_outline(points, spec), [True,False,False])
        with self.assertRaises(ValueError):
            surface_outline(points, dict(axes='xx', points=spec['points']))
        with self.assertRaises(ValueError):
            surface_outline(points, dict(axes='xy', points=[[0,0],[.1,.1],[.2,.2]]))

    def test_heal_samples_same_surface_and_preserves_neighbor_pixels(self):
        import numpy as np
        from headkit.paint import heal
        n = 64
        ys,xs = np.mgrid[:n,:n]
        coords = np.array([[0.,0.],[1.,0.],[0.,1.],[1.,1.]])
        faces = np.array([[0,1,2],[1,3,2]])
        mesh = {'uv':coords[faces], 'positions':np.column_stack((coords,coords[:,1])), 'faces':faces}
        rgb = np.full((n,n,3),50,np.uint8)
        rgb[20:23,20:23] = [200,0,0]
        rgb[20:23,24:27] = [0,200,0]
        initial = rgb.copy()
        mapped = np.ones((n,n),bool)
        def values():
            return {'mapped':mapped,'face':(xs+ys>=n).astype(int),'r':rgb[...,0],'g':rgb[...,1]}
        op = {'name':'small-mark','target':{'of':'r','gt':190},'donor':{'of':'g','gt':190},
              'offset':[4/n,0.,0.]}
        mask = heal(mesh,rgb,op,{},values,{})['small-mark']
        np.testing.assert_array_equal(rgb[~mask],initial[~mask])
        self.assertTrue(np.all(rgb[mask]==[0,200,0]))
        self.assertEqual(int(mask.sum()),9)


    def test_declared_head_heal_side_checks_actual_target_and_donor_before_painting(self):
        from headkit.paint import heal
        n=64;ys,xs=np.mgrid[:n,:n]
        coords=np.array([[0.,0.],[1.,0.],[0.,1.],[1.,1.]])
        faces=np.array([[0,1,2],[1,3,2]])
        mesh={'uv':coords[faces],'positions':np.column_stack((coords,coords[:,1])),'faces':faces}
        for side,target_y,donor_y,valid in [('rear',20,20,True),('rear',44,44,False),
                                            ('rear',20,44,False),('front',44,44,True),('sideways',20,20,False)]:
            with self.subTest(side=side,target=target_y,donor=donor_y):
                rgb=np.full((n,n,3),50,np.uint8)
                rgb[target_y:target_y+3,20:23]=[200,0,0]
                rgb[donor_y:donor_y+3,24:27]=[0,200,0]
                initial=rgb.copy()
                def values():return {'mapped':np.ones((n,n),bool),'face':(xs+ys>=n).astype(int),'r':rgb[...,0],'g':rgb[...,1]}
                op={'name':'side-bound','headSide':side,'target':{'of':'r','gt':190},'donor':{'of':'g','gt':190},'offset':[4/n,0,0]}
                if valid:
                    report={};mask=heal(mesh,rgb,op,report,values,{})['side-bound']
                    self.assertEqual(report['headSide'],side)
                    np.testing.assert_array_equal(rgb[~mask],initial[~mask])
                else:
                    with self.assertRaisesRegex(ValueError,'Head heal'):heal(mesh,rgb,op,{},values,{})
                    np.testing.assert_array_equal(rgb,initial)


class BrowEdgeTests(unittest.TestCase):
    def test_seed_edges_stay_near_core_and_outside_lids_and_exclusions(self):
        from headkit.brow_edges import fringe
        seed=np.ones((24,24),bool);core=np.zeros_like(seed);core[10:12,10:12]=True
        eyes=np.zeros_like(seed);eyes[12:]=True
        excluded=np.zeros_like(seed);excluded[:,:10]=True
        result=fringe(seed,core,eyes,excluded)
        self.assertTrue(result[8,10])
        self.assertFalse(result[6,10] or result[12,10] or result[10,9])
        self.assertFalse(result[0].any())


class MaterialLightTests(unittest.TestCase):
    def test_local_light_balance_keeps_texture_other_materials_and_input(self):
        from headkit.material_light import balance
        n=128;yy,xx=np.indices((n,n));positions=np.dstack((xx/(n-1),yy/(n-1),(yy<n//2).astype(float)))
        labels=np.ones((n,n),np.uint8);labels[:,-2:]=2
        rgb=np.repeat((np.where(yy<n//2,100.,200.)+(xx%7-3))[...,None],3,axis=2).astype(np.float32)
        original=rgb.copy();owners=np.zeros((n,n),int)
        mesh={'positions':np.array([[0,0,0],[1,1,1]],float)}
        spec={'channel':1,'reference':{'of':'z','gt':.8},'neighbours':128}
        with patch('headkit.material_light.surface',return_value=(positions,owners,{})):
            out,report=balance(rgb,labels,mesh,spec)
            self.assertLess(float(np.median(out[n//2:,:-2])),115)
            self.assertGreater(float(np.ptp(out[n//2:,:-2])),2)
            self.assertTrue((out<=rgb+.001).all())
            np.testing.assert_array_equal(out[:,-2:],rgb[:,-2:])
            np.testing.assert_array_equal(rgb,original)
            self.assertGreater(report['darkenedTexels'],n*n//3)
            with self.assertRaisesRegex(ValueError,'32 texels'):
                balance(rgb,labels,mesh,dict(spec,reference={'of':'z','gt':2}))
            with self.assertRaisesRegex(ValueError,'limits'):
                balance(rgb,labels,mesh,dict(spec,strength=float('nan')))
            with self.assertRaisesRegex(ValueError,'channel'):
                balance(rgb,labels,mesh,dict(spec,channel=True))


class SourceRoleTests(unittest.TestCase):
    def test_source_regions_reject_changed_pixels_and_unreviewed_masks(self):
        import hashlib
        from headkit.quality_reference import source_regions

        rgb = np.zeros((32, 64, 3), dtype=np.uint8)
        hit = np.ones(rgb.shape[:2], dtype=bool)
        digest = hashlib.sha256(rgb.tobytes()).hexdigest()
        spec = {
            'rgbSha256': digest,
            'brows': {'of': 'y', 'lt': 8},
            'locks': {'of': 'y', 'gt': 12},
            'maskSha256': {'brows': 'unreviewed', 'locks': 'unreviewed'},
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            with self.assertRaisesRegex(ValueError, 'visually reviewed'):
                source_regions(rgb, hit, hit, spec, output)
            rgb[0, 0, 0] = 1
            with self.assertRaisesRegex(ValueError, 'another front render'):
                source_regions(rgb, hit, hit, spec, output)
            self.assertFalse((output/'source-roles.png').exists())


class Conditioning(unittest.TestCase):
    def test_prepare_prefers_pair_even_with_design_for_palette(self):
        data={'profile':'pixal-single-v1','inputs':{'design':{},'clay':{},'detail':{}},'alignment':{},
              'features':[{'placementReviewed':True}],'approval':{'referenceDesignReviewed':True}}
        runner=SimpleNamespace(data=data,bindings={},input=lambda role:role)
        with patch('headkit.images.prepare',return_value={'paired':True}) as paired, patch('headkit.images.matte') as matte:
            self.assertEqual(Runner._execute(runner,'prepare',Path('output')),{'paired':True})
            paired.assert_called_once_with('clay','detail',{},Path('output/images'));matte.assert_not_called()
        del data['inputs']['detail']
        with self.assertRaisesRegex(ValueError,'both clay and detail'):Runner._execute(runner,'prepare',Path('output'))

    def test_preservation_is_discrete_mapped_skin_only(self):
        labels=np.array([[0,1],[8,0]],np.uint8);mapped=np.array([[1,1],[1,0]],bool)
        np.testing.assert_array_equal(skin_preservation(np.full((2,2),255),labels,mapped),[[True,False],[False,False]])
        for bad in (np.zeros((3,3)),np.full((2,2),.5),np.full((2,2),np.nan)):
            with self.assertRaises(ValueError):skin_preservation(bad,labels,mapped)

    def test_skin_preservation_prevents_smoothing_without_disabling_delight(self):
        size=16;labels=np.zeros((size,size),np.uint8);owners=np.zeros_like(labels,dtype=int)
        points=np.stack(np.meshgrid(np.arange(size),np.arange(size)),axis=-1)
        positions=np.concatenate([points,np.zeros((size,size,1))],axis=-1)
        value={'positions':np.array([[0.,0,0],[1,0,0],[0,1,0]]),'faces':np.array([[0,1,2]]),'uv':np.array([[[0,0],[1,0],[0,1]]])}
        colour=np.full((size,size,3),180.,np.float32);colour[:,7:9]=50
        preserve=np.zeros_like(labels);preserve[:,7:9]=1
        masks={key:np.zeros_like(labels,dtype=float) for key in ('iris','eye','brow','lips','nose','lipline','socket')}
        settings=dict.fromkeys(TREATMENT,0);settings['smooth']=1
        with patch('headkit.face_encode.surface',return_value=(positions,owners,None)),patch('headkit.face_encode.face_region',return_value=(np.array([True]),None)),patch('headkit.face_encode.consistent_blocks',side_effect=lambda c,o:(c,0)),patch('headkit.face_encode.pad',side_effect=lambda c,m:c):
            unprotected,_=treat(colour,labels,masks,value,settings)
            protected,report=treat(colour,labels,masks,value,settings,preserve_skin=preserve)
            np.testing.assert_array_equal(protected[:,7:9],colour[:,7:9])
            self.assertGreater(float(unprotected[:,7:9].mean()),50)
            self.assertEqual(report['preservedSkinTexels'],32)
            settings.update(smooth=0,delight=1)
            with patch('headkit.face_encode._surface_mean',return_value=np.r_[np.full(128,100),np.full(128,200)]):
                delighted,_=treat(np.full_like(colour,180),labels,masks,value,settings,preserve_skin=np.ones_like(labels))
                self.assertLess(float(delighted[8:].mean()),180)

    def test_runtime_atlas_is_separate_from_high_resolution_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);detail=root/'detail.png';runtime=root/'plt.png'
            Image.new('RGB',(2048,2048),'red').save(detail);Image.new('RGB',(1024,1024),'blue').save(runtime)
            sets,pins=atlas_sets({'maps':{'basecolor':str(detail)},'mapsBySize':{'1024':{'basecolor':str(runtime)}}},root/'out',[2048,1024])
            with Image.open(sets[2048]['basecolor']) as image:self.assertEqual(image.getpixel((0,0)),(255,0,0))
            with Image.open(sets[1024]['basecolor']) as image:self.assertEqual(image.getpixel((0,0)),(0,0,255))
            self.assertEqual({row['source']['path'] for row in pins},{str(detail.resolve()),str(runtime.resolve())})
            with self.assertRaisesRegex(ValueError,'no upsampling'):
                atlas_sets({'maps':{'basecolor':str(runtime)}},root/'bad',[2048])

    def test_default_cameras_cover_all_four_three_quarters(self):
        names={row['name'] for row in review_cameras([[0,0,0],[1,1,1]],-90)}
        self.assertTrue({'left-three-quarter','right-three-quarter','left-back-three-quarter','right-back-three-quarter'}<=names)

class SemanticMask(unittest.TestCase):
    def test_mask_operation_emits_selection_without_recolouring(self):
        from headkit.paint import paint
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.glb';source.write_bytes(b'fixture')
            colour=root/'colour.png';Image.new('RGB',(4096,4096),(99,123,145)).save(colour)
            value={'positions':np.array([[0.,0,0],[1,0,1],[0,1,1]]),'faces':np.array([[0,1,2]]),
                   'uv':np.array([[[.1,.1],[.9,.1],[.1,.9]]])}
            with patch('headkit.paint.mesh',return_value=value):
                result=paint(source,colour,{'operations':[{'op':'mask','name':'skin-ink','faces':{'of':'index','ge':0}}]},root/'paint')
            self.assertEqual(result['operations'][0]['paintedTexels'],0)
            with Image.open(result['maps']['basecolor-4096.png']['path']) as image:
                self.assertTrue((np.asarray(image)==[99,123,145]).all())
            with Image.open(result['masks']['skin-ink']['path']) as image:
                mask=np.asarray(image);self.assertTrue((mask==255).any());self.assertTrue((mask==0).any())

if __name__=='__main__':unittest.main()


class MaterialHealContract(unittest.TestCase):
    def test_material_declaration_is_opt_in_hair_only_and_source_bound(self):
        from headkit.paint import material_hint
        source={'sha256':'exact'}
        op={'op':'heal','name':'repair','materialChannel':1,'sourceSha256':'exact','notes':'Measured hair pigment defect'}
        self.assertEqual(material_hint(op,source)['channel'],1)
        self.assertIsNone(material_hint({'op':'heal'},source))
        for change in ({'sourceSha256':'stale'},{'materialChannel':0},{'materialChannel':True},
                       {'notes':''},{'op':'fill'}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                material_hint(dict(op,**change),source)

    def test_material_selection_keeps_priority_and_never_mutates_authored_rules(self):
        from copy import deepcopy
        from headkit.common import pin
        from headkit.paint import material_ownership
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'uv.glb';source.write_bytes(b'geometry')
            digest=pin(source)['sha256'];mask={'path':'local-mask.png','sha256':'mask'}
            hint={'name':'local','channel':1,'sourceSha256':digest,'mask':mask}
            painted={'source':pin(source),'masks':{'local':mask},'ownershipHints':[hint]}
            original={'mode':'rules','rules':[{'name':'skin','channel':0,'when':{'mapped':True}}]}
            before=deepcopy(original)
            selected=material_ownership(original,painted,source)
            self.assertEqual(original,before)
            self.assertEqual(selected['rules'][0]['when'],{'mask':'local'})
            self.assertNotIn('overFaceMasks',selected['rules'][0])
            self.assertEqual(selected['rules'][1],before['rules'][0])
            for invalid in (dict(painted,source={'sha256':'other'}),dict(painted,masks={'local':{'sha256':'other'}})):
                with self.assertRaises(ValueError):material_ownership(original,invalid,source)
            with self.assertRaises(ValueError):material_ownership({'mode':'atlas'},painted,source)
            self.assertIs(material_ownership(original,{},source),original)

    def test_semantic_protection_and_runtime_ownership_are_independent_refusal_gates(self):
        from headkit.common import pin
        from headkit.paint import audit_material_hints
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'mask.png';mask=np.zeros((4096,4096),np.uint8);mask[100:108,100:108]=255
            Image.fromarray(mask).save(path)
            painted={'ownershipHints':[{'name':'local','channel':1,'mask':pin(path)}]}
            labels=np.zeros(mask.shape,np.uint8);labels[mask>0]=1
            onek=np.zeros((1024,1024),np.uint8);onek[25:27,25:27]=1
            mapped=np.ones(mask.shape,bool)
            report=audit_material_hints(labels,onek,painted,mapped)
            self.assertEqual(report[0]['wrong4k'],0);self.assertEqual(report[0]['wrong1k'],0)
            self.assertEqual(report[0]['runtimeTexels'],4)
            for scale in (4096,1024):
                wrong4k=labels.copy();wrong1k=onek.copy()
                if scale==4096:wrong4k[102,102]=0
                else:wrong1k[25,25]=0
                before4k=wrong4k.copy();before1k=wrong1k.copy()
                with self.subTest(scale=scale),self.assertRaisesRegex(ValueError,'conflicts'):
                    audit_material_hints(wrong4k,wrong1k,painted,mapped)
                np.testing.assert_array_equal(wrong4k,before4k);np.testing.assert_array_equal(wrong1k,before1k)

    def test_unknown_uv_or_material_fields_cannot_authorize_production_hints(self):
        from headkit.paint import material_ownership
        from headkit.common import pin
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'uv.glb';source.write_bytes(b'geometry')
            mask={'path':'mask','sha256':'x'};digest=pin(source)['sha256']
            for field in ({'channel':0},{'sourceSha256':'stale'},{'mask':{}}):
                hint=dict({'name':'local','channel':1,'sourceSha256':digest,'mask':mask},**field)
                painted={'source':pin(source),'masks':{'local':mask},'ownershipHints':[hint]}
                with self.assertRaises(ValueError):material_ownership({'mode':'rules','rules':[]},painted,source)


    def test_explicit_local_heal_overrides_soft_skin_but_refuses_anatomical_materials(self):
        from headkit.paint import apply_material_hints
        from headkit.common import pin
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'mask.png';mask=np.zeros((4096,4096),np.uint8);mask[100:108,100:108]=255
            Image.fromarray(mask).save(path)
            painted={'ownershipHints':[{'name':'local','channel':1,'mask':pin(path)}]}
            labels=np.zeros(mask.shape,np.uint8);mapped=np.ones(mask.shape,bool)
            zero=np.zeros(mask.shape,np.float32)
            features={name:zero for name in ('eye','iris','ear','lips','nose')}
            result=apply_material_hints(labels,painted,features,mapped)
            self.assertTrue(np.all(result[mask>0]==1))
            self.assertTrue(np.all(result[mask==0]==0))
            self.assertTrue(np.all(labels==0))
            for name in features:
                blocked=zero.copy();blocked[102,102]=1
                with self.subTest(feature=name),self.assertRaisesRegex(ValueError,'protected'):
                    apply_material_hints(labels,painted,dict(features,**{name:blocked}),mapped)
            other=labels.copy();other[102,102]=9
            with self.assertRaisesRegex(ValueError,'another material'):apply_material_hints(other,painted,features,mapped)

    def test_half_block_ties_are_not_reported_as_strict_runtime_interiors(self):
        from headkit.common import pin
        from headkit.paint import audit_material_hints
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'mask.png';mask=np.zeros((4096,4096),np.uint8)
            mask[100:104,100:104]=255
            mask[104:106,104:108]=255
            Image.fromarray(mask).save(path)
            labels=np.zeros_like(mask);labels[mask>0]=1
            onek=np.zeros((1024,1024),np.uint8);onek[25,25]=1
            painted={'ownershipHints':[{'name':'local','channel':1,'mask':pin(path)}]}
            report=audit_material_hints(labels,onek,painted,np.ones_like(mask,bool))
            self.assertEqual(report[0]['runtimeTexels'],1)
            self.assertEqual(report[0]['boundaryTies'],1)
            self.assertEqual(report[0]['wrong1k'],0)
