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
