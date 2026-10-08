"""Behavioral regression tests for frozen-runtime CPU material previews."""
from io import BytesIO
from unittest.mock import patch
import json
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np
from PIL import Image

from prepare_effective_body_preview import (Resolver, colorize_plt, export_part,
                                           material_inputs, mesh_corners, mtr_fields,
                                           plt_pixels, sha, preview_identity, stock_inventory_hashes)
from place_purposebuilt_pelvis import accessor, read_glb


def plt_bytes(top_down):
    h,w,_ = top_down.shape
    return b'PLT V1  '+struct.pack('<IIII',10,0,w,h)+top_down[::-1].tobytes()


def model(normals=True, second_uv=False, transformed=False):
    return '\n'.join(['newmodel test','setsupermodel test NULL','beginmodelgeom test',
        'node dummy test',' parent NULL','endnode','node trimesh testp',' parent test',
        ' position 1 2 3' if transformed else ' position 0 0 0',
        ' orientation 0 0 1 1.5707963267948966' if transformed else ' orientation 0 0 0 0',
        ' bitmap skin',' materialname skin',' verts 3',' 0 0 0',' 1 0 0',' 0 1 0',
        *([' normals 3',' 0 0 .97',' 0 0 .97',' 0 0 .97'] if normals else []),
        ' tverts '+('4' if second_uv else '3'), ' .125 .25 0',' .75 .25 0',' .125 .75 0',
        *([' .9 .8 0'] if second_uv else []), ' faces 1',
        ' 0 1 2 1 0 1 '+('3' if second_uv else '2')+' 1', 'endnode','endmodelgeom test','donemodel test'])+'\n'


class EffectivePreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='effective-body-preview-test-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name).resolve()
        self.inputs = {}

    def resolver(self):
        hashes = {p.name:sha(p) for p in self.path.iterdir() if p.is_file()}
        return Resolver([(self.path,hashes)], self.inputs)

    def image(self,name,values):
        Image.fromarray(np.array(values,dtype=np.uint8)).save(self.path/name)

    def stock_palettes(self):
        palette = np.zeros((8,256,3),np.uint8)
        palette[:,:,0] = np.arange(256,dtype=np.uint8)[None,:]
        palette[:,:,1] = np.arange(8,dtype=np.uint8)[:,None]*20
        palette[:,:,2] = 100
        Image.fromarray(palette).save(self.path/'pal_skin01.tga')
        return palette

    def skin(self):
        self.stock_palettes()
        self.path.joinpath('skin.plt').write_bytes(plt_bytes(np.array([[[17,0],[23,0]],[[31,0],[41,0]]],np.uint8)))

    def test_female_identity_requires_pinned_stock_contract_and_measured_height(self):
        path=self.path/'female-target.json';path.write_text('{}');pin=sha(path)
        target={'identity':{'prefix':'pfh0'},'heightMeters':1.837937046,'rig':{'mode':'stock-exact'}}
        config={'targetContract':{'path':str(path),'sha256':pin}}
        with patch('prepare_effective_body_preview.contract.load',return_value=target):
            self.assertEqual(preview_identity(config,{str(path):pin})[:2],('pfh0',1.837937046))
            with self.assertRaises(RuntimeError):preview_identity(config,{})
        with self.assertRaises(RuntimeError):preview_identity({'sourcePrefix':'pfh0'},{})
        self.assertEqual(preview_identity({}, {})[:2],('pmh0',1.9339157))

    def test_fresh_stock_baseline_native_and_decompiled_hashes(self):
        raw,ascii=stock_inventory_hashes({'resources':[{'name':'pfh0.mdl','sha256':'native','asciiSha256':'decompiled'},{'name':'pal_skin01.tga','sha256':'palette'}]},self.path)
        self.assertEqual(raw,{'pfh0.mdl':'native','pal_skin01.tga':'palette'});self.assertEqual(ascii,{'pfh0.mdl':'decompiled'})

    def test_plt_origin_exact_rows_layers_and_transparency(self):
        top = np.array([[[1,0],[2,1]],[[3,0],[0,255]]],np.uint8)
        data = plt_bytes(top)
        np.testing.assert_array_equal(plt_pixels(data),top)
        skin = np.zeros((9,256,3),np.uint8)
        hair = np.zeros_like(skin)
        skin[3,:,:] = np.arange(256,dtype=np.uint8)[:,None]
        hair[5,:,:] = [20,30,40]
        rendered = colorize_plt(data,{0:skin,1:hair},{0:3,1:5})
        np.testing.assert_array_equal(rendered,np.array([[[1,1,1,255],[20,30,40,255]],[[3,3,3,255],[0,0,0,0]]],np.uint8))

    def test_invalid_plt_payload_layer_and_selector_fail(self):
        top = np.array([[[1,0]]],np.uint8)
        data = plt_bytes(top)
        for invalid in [data[:-1],b'PLT X0  '+data[8:],plt_bytes(np.array([[[1,12]]],np.uint8))]:
            with self.assertRaises(RuntimeError):
                plt_pixels(invalid)
        with self.assertRaises(RuntimeError):
            colorize_plt(data,{0:np.zeros((4,256,3),np.uint8)},{0:8})

    def test_pinned_resolver_rejects_changed_and_unlisted_resources(self):
        self.path.joinpath('example.mtr').write_text('parameter float Roughness .7\n')
        resolver = self.resolver()
        resolver.file('example.mtr')
        self.path.joinpath('example.mtr').write_text('parameter float Roughness .6\n')
        with self.assertRaises(RuntimeError):
            resolver.file('example.mtr')
        self.path.joinpath('new.mtr').write_text('')
        with self.assertRaises(RuntimeError):
            resolver.file('new.mtr')
        with self.assertRaises(RuntimeError):
            resolver.file('../example.mtr')
        self.assertIsNone(resolver.file('missing.mtr',optional=True))

    def test_mesh_transform_and_independent_uv_indices(self):
        row = mesh_corners(model(second_uv=True,transformed=True),authored_required=True)[0]
        np.testing.assert_allclose(row['position'][0],[[1,2,3],[1,3,3],[0,2,3]],atol=1e-15)
        np.testing.assert_array_equal(row['uv'][0],[[.125,.25],[.75,.25],[.9,.8]])
        np.testing.assert_allclose(row['normal'][0],[[0,0,.97]]*3,atol=1e-15)
        self.assertIn('authored',row['normalPolicy'])

    def test_stock_missing_normals_computed_only_explicit_fallback(self):
        row = mesh_corners(model(normals=False))[0]
        np.testing.assert_array_equal(row['normal'][0],[[0,0,1]]*3)
        self.assertIn('not actual compiled',row['normalPolicy'])
        with self.assertRaises(RuntimeError):
            mesh_corners(model(normals=False),authored_required=True)

    def test_roughness_zero_uses_actual_red_and_normal_pixels(self):
        self.skin()
        self.image('norm.tga', [[[30,140,230],[35,145,235]]])
        self.image('rough.tga', [[[45,9,200],[80,19,180]]])
        self.path.joinpath('skin.mtr').write_text('renderhint NormalTangents\ntexture1 norm\ntexture3 rough\nparameter float Roughness 0\nparameter float Metallicness .001\n')
        color,normal,rough,scalar,metallic,proof = material_inputs(mesh_corners(model())[0],self.resolver(),{0:3})
        np.testing.assert_array_equal(color[0,0],[17,60,100,255])
        np.testing.assert_array_equal(normal[0],[[30,140,230],[35,145,235]])
        np.testing.assert_array_equal(rough[0,:,1],[45,80])
        self.assertEqual(scalar,0); self.assertEqual(metallic,.001)
        self.assertIn('texture3 red',proof['roughnessPolicy'])

    def test_positive_roughness_precedence_fixed_texture_zero(self):
        self.image('fixed.tga', [[[15,25,35,255],[40,50,60,255]]])
        self.path.joinpath('skin.mtr').write_text('texture0 fixed\ntexture3 deliberately_missing\nparameter float Roughness .72\n')
        color,normal,rough,scalar,_,proof = material_inputs(mesh_corners(model())[0],self.resolver(),{0:3})
        np.testing.assert_array_equal(color[0],[[15,25,35,255],[40,50,60,255]])
        self.assertIsNone(rough); self.assertIsNone(normal); self.assertEqual(scalar,.72)
        self.assertEqual(proof['colorPolicy'],'fixed MTR texture0')
        self.assertIn('precedence',proof['roughnessPolicy'])

    def test_unsupported_mtr_and_duplicate_binding_rejected(self):
        for text in ['texture2 specular','texture1 first\ntexture1 second',
                     'parameter float Roughness nan','texture0 ../unsafe','renderhint Unsupported']:
            with self.assertRaises(RuntimeError):
                mtr_fields(text)

    def test_serialized_corner_basis_uv_and_actual_palette_image(self):
        self.skin()
        row = mesh_corners(model(second_uv=True,transformed=True),authored_required=True)[0]
        target = self.path/'test.glb'
        proof = export_part(target,[row],self.resolver(),{0:3})
        doc,blob = read_glb(target)
        primitive = doc['meshes'][0]['primitives'][0]
        p = accessor(doc,blob,primitive['attributes']['POSITION'])
        np.testing.assert_allclose(p,[[1,3,-2],[1,3,-3],[0,3,-2]],atol=1e-7)
        uv = accessor(doc,blob,primitive['attributes']['TEXCOORD_0'])
        np.testing.assert_allclose(uv,[[.125,.75],[.75,.75],[.9,.2]],atol=1e-7)
        normals = accessor(doc,blob,primitive['attributes']['NORMAL'])
        np.testing.assert_allclose(normals,[[0,.97,0]]*3,atol=1e-7)
        image = doc['images'][0]; view = doc['bufferViews'][image['bufferView']]
        pixels = np.asarray(Image.open(BytesIO(blob[view['byteOffset']:view['byteOffset']+view['byteLength']])))
        np.testing.assert_array_equal(pixels[0,0],[17,60,100,255])
        self.assertTrue(proof['meshes'][0]['serializationProof']['positionsNormalsFloat32ExactAfterInverseBasis'])
        archive = np.load(proof['sourceCornerArchive'])
        np.testing.assert_array_equal(archive['mesh0PositionNwn'],row['position'])
        np.testing.assert_array_equal(archive['mesh0NormalNwn'],row['normal'])
        np.testing.assert_array_equal(archive['mesh0UvNwn'],row['uv'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
