"""Source appearance must be baked before fitting and preserve geometry in transport."""
from pathlib import Path
import tempfile
import unittest
import numpy as np
from PIL import Image
from tools.headkit.gltf import write_mesh,load,arrays
from tools.itemkit.donor import geometry_frame,embed_diffuse,unwrap_source,field_policy,build
from unittest.mock import patch


class DonorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.v=np.array([[.1,.2,.3],[.4,.2,.3],[.1,.5,.3]],np.float32);self.f=np.array([[0,1,2]])
        self.uv=np.array([[[.1,.1],[.8,.1],[.1,.8]]])
        self.source=self.root/'source.glb';write_mesh(self.source,self.v,self.f)
        self.unwrapped=self.root/'uv.glb';write_mesh(self.unwrapped,self.v,self.f,self.uv)
    def tearDown(self):self.temp.cleanup()
    def test_uv_source_is_still_in_the_original_field_frame(self):
        self.assertEqual(geometry_frame(self.source,self.unwrapped)['maximumCoordinateDifference'],0)
    def test_source_unwrap_uses_maintained_atlas_and_keeps_original_field_frame(self):
        from tools.headkit.gltf import mesh
        v=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1]],np.float32)
        f=np.array([[0,2,1],[0,1,3],[0,3,2],[1,2,3]])
        self.source.unlink(); self.unwrapped.unlink()
        write_mesh(self.source,v,f); write_mesh(self.unwrapped,v,f,np.tile(self.uv,(4,1,1)))
        value=mesh(self.unwrapped);local={'libraries':{'xatlas':{'fixture':'bound'}}}
        with patch('tools.itemkit.source_atlas.unwrap',return_value=(value,{'verified':'fixture'})) as unwrap:
            result=unwrap_source(self.source,local,self.root/'source-unwrap')
        self.assertEqual(result['frame']['maximumCoordinateDifference'],0)
        self.assertEqual(unwrap.call_args.args[1],local)
        self.assertEqual(unwrap.call_args.args[2],self.root/'source-unwrap'/'atlas')
    def test_open_source_is_rejected_before_atlas_processing(self):
        with patch('tools.itemkit.source_atlas.unwrap') as unwrap:
            with self.assertRaisesRegex(ValueError,'source blocks UV/bake'):
                unwrap_source(self.source,{},self.root/'invalid-source')
        unwrap.assert_not_called()
    def test_transformed_or_reversed_source_cannot_sample_original_field(self):
        for label,vertices,faces in (('translated',self.v+[0,1,0],self.f),('reversed',self.v,self.f[:,::-1])):
            path=self.root/(label+'.glb');write_mesh(path,vertices,faces,self.uv)
            with self.assertRaisesRegex(ValueError,'original appearance-field frame'):geometry_frame(self.source,path)
    def test_texture_embedding_retains_exact_geometry_and_real_uvs(self):
        texture=self.root/'source.png';Image.new('RGB',(4096,4096),(60,65,70)).save(texture)
        target=self.root/'donor.glb';embed_diffuse(self.unwrapped,texture,target)
        before=arrays(*load(self.unwrapped.read_bytes()));d,b,p=load(target.read_bytes());after=arrays(d,b,p)
        for a,c in zip(before[:2],after[:2]):np.testing.assert_array_equal(a,c)
        np.testing.assert_array_equal(before[2]['TEXCOORD_0'],after[2]['TEXCOORD_0'])
        self.assertEqual(d['materials'][0]['pbrMetallicRoughness']['baseColorTexture']['index'],0)
        self.assertEqual(d['images'][0]['mimeType'],'image/png')
    def test_texture_embedding_rejects_missing_uv_or_wrong_source_resolution(self):
        texture=self.root/'small.png';Image.new('RGB',(16,16)).save(texture)
        for source in (self.source,self.unwrapped):
            with self.assertRaises(ValueError):embed_diffuse(source,texture,self.root/'bad.glb')

    def test_reviewed_field_policy_keeps_legacy_and_binds_custom_ranges(self):
        legacy={'minimum':-.02,'maximum':1.032,'allowDecoderOvershoot':True}
        self.assertEqual(field_policy(legacy,'a'*64),legacy)
        knife={'minimum':-.087,'maximum':1.102,'allowDecoderOvershoot':True,'fieldSha256':'a'*64}
        self.assertEqual(field_policy(knife,'a'*64),knife)
        for value in (None,{},dict(knife,extra=1),{k:v for k,v in knife.items() if k!='minimum'},
                      {k:v for k,v in knife.items() if k!='fieldSha256'},dict(knife,fieldSha256='b'*64),
                      dict(knife,minimum=True),dict(knife,maximum='1.102'),dict(knife,minimum=float('nan')),
                      dict(knife,maximum=float('inf')),dict(knife,minimum=-1),dict(knife,maximum=2),
                      dict(knife,minimum=.1),dict(knife,maximum=.9),dict(knife,allowDecoderOvershoot=1)):
            with self.subTest(policy=value),self.assertRaises(ValueError):field_policy(value,'a'*64)

    def test_build_preserves_raw_values_and_binds_field_before_and_after_bake(self):
        from tools.headkit.common import pin
        field=self.root/'field.npz';raw=np.array([[-.08642578125,1.1015625,.5,0,.8,1]],np.float32)
        np.savez(field,coords=np.array([[0,0,0]]),attrs=raw,resolution=1)
        original=field.read_bytes();policy={'minimum':-.087,'maximum':1.102,'allowDecoderOvershoot':True,
                                          'fieldSha256':pin(field)['sha256']}
        def bake(source,path,output,**options):
            self.assertTrue(options['allow_decoder_overshoot'])
            with np.load(path) as data:np.testing.assert_array_equal(data['attrs'],raw)
            return {'maps':{'basecolor-4096.png':{'path':'fixture'}}}
        with patch('tools.headkit.textures.bake',side_effect=bake),patch('tools.itemkit.donor.embed_diffuse',return_value={'fixture':True}):
            result=build(self.source,self.unwrapped,field,policy,self.root/'valid')
        self.assertEqual(field.read_bytes(),original);self.assertEqual(result['fieldPolicy'],policy)
        self.assertEqual(result['field'],pin(field));self.assertFalse(result['fitApplied'])
        def changed(*args,**kwargs):
            field.write_bytes(b'changed during bake');return {'maps':{}}
        with patch('tools.headkit.textures.bake',side_effect=changed),patch('tools.itemkit.donor.embed_diffuse') as embed:
            with self.assertRaisesRegex(ValueError,'Stale file pin'):build(self.source,self.unwrapped,field,policy,self.root/'stale')
        embed.assert_not_called()

    def test_invalid_field_stops_before_bake_and_output_creation(self):
        from tools.headkit.common import pin
        for index,raw in enumerate((np.full((1,6),float('nan')),np.full((1,6),1.11),np.zeros((0,6)),np.zeros((1,5)))):
            field=self.root/f'bad-field-{index}.npz';np.savez(field,coords=np.array([[0,0,0]]),attrs=raw,resolution=1)
            policy={'minimum':-.087,'maximum':1.102,'allowDecoderOvershoot':True,'fieldSha256':pin(field)['sha256']}
            output=self.root/f'bad-{index}'
            with patch('tools.headkit.textures.bake') as bake:
                with self.assertRaises(ValueError):build(self.source,self.unwrapped,field,policy,output)
                bake.assert_not_called()
            self.assertFalse(output.exists())


if __name__=='__main__':unittest.main()
