import hashlib
import contextlib
import io
from unittest.mock import patch
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from . import api, cli
from .engine.convert_model import convert_text, array, parse, MARKER
from .engine.morph_preview_pose_v13 import native_keys_hash

MODEL = '''newmodel sample
setsupermodel sample NULL
beginmodelgeom sample
node dummy sample
parent NULL
position 0 0 0
orientation 0 0 1 0
endnode
node trimesh surface
parent sample
position 0.1 0 0
orientation 0 0 1 0
bitmap skin
materialname skin
verts 3
0 0 0
1 0 0
0 0 1
normals 3
0 -1 0
0 -1 0
0 -1 0
tangents 3
1 0 0 1
1 0 0 1
1 0 0 1
tverts 3
0 0 0
1 0 0
0 1 0
faces 1
0 1 2 0 0 1 2 1
endnode
endmodelgeom sample
donemodel sample
'''


def profile():
    a={'lowerZ':0.,'length':1.,'stations':[0.,1.],
       'centers':[[0.,0.],[0.,0.]],'radii':[[1.,1.],[1.,1.]]}
    b={**a,'radii':[[1.1,1.2],[1.1,1.2]]}
    return {'sourceEnvelope':a,'targetEnvelope':b,'identity':False}


class PublicContractTests(unittest.TestCase):
    def test_inventory_rejects_aliases_of_one_resolved_resource(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'sub').mkdir()
            source=root/'part.mdl'; source.write_bytes(b'fixture')
            manifest=root/'manifest.json'
            row={'path':'part.mdl','sha256':api.digest(source),'bytes':source.stat().st_size}
            for alias in ('part.mdl','sub/../part.mdl','./part.mdl'):
                data={'schemaVersion':1,'kind':'PhenoMorpher-game-ready-bodies','version':'1',
                      'targets':[{'target':'control'}],'resources':[row,{**row,'path':alias}]}
                manifest.write_text(json.dumps(data),encoding='utf-8')
                for snapshot in (None,{str(source.resolve()):api.digest(source)}):
                    with self.subTest(alias=alias,snapshot=snapshot is not None),self.assertRaisesRegex(ValueError,'Duplicate'):
                        api.verify_assets(root,manifest,snapshot)
            other=root/'other.mdl';other.write_bytes(source.read_bytes())
            data['resources']=[row,{**row,'path':'other.mdl'}]
            manifest.write_text(json.dumps(data),encoding='utf-8')
            self.assertEqual(api.verify_assets(root,manifest)['resources'],2)

    def test_sections_include_coplanar_faces_and_patch_extrema(self):
        horizontal={'position':np.array([[-3.,-2.,1.],[4.,-2.,1.],[0.,5.,1.]]),
                    'faces':np.array([[0,1,2]])}
        crossing={'position':np.array([[-.5,0.,0.],[.5,0.,2.],[0.,1.,0.]]),
                  'faces':np.array([[0,1,2]])}
        for meshes in ([horizontal],[crossing,horizontal]):
            self.assertEqual(api.cross_section(meshes,1.,0),7.)
            self.assertEqual(api.cross_section(meshes,1.,1),7.)
        self.assertIsNone(api.cross_section([horizontal],1.1,0))
        self.assertIsNone(api.cross_section([{**horizontal,'render':False}],1.,0))

    def test_sections_keep_edge_vertex_and_ordinary_intersections(self):
        mesh={'position':np.array([[-2.,0.,1.],[3.,0.,1.],[0.,2.,2.]]),
              'faces':np.array([[0,1,2]])}
        self.assertEqual(api.cross_section([mesh],1.,0),5.)
        self.assertEqual(api.cross_section([mesh],2.,0),0.)
        self.assertEqual(api.cross_section([mesh],1.5,0),2.5)

    def test_coplanar_sections_tolerate_roundoff_without_relative_height_slop(self):
        for height, plane in ((.3,.1+.2),(1000.,1000.+5e-13)):
            mesh={'position':np.array([[-3.,-2.,height],[4.,-2.,height],[0.,5.,height]]),
                  'faces':np.array([[0,1,2]])}
            for axis in (0,1):
                with self.subTest(height=height,axis=axis):
                    self.assertEqual(api.cross_section([mesh],plane,axis),7.)
                    self.assertIsNone(api.cross_section([mesh],height+3e-12,axis))

    def test_recipe_roundtrip_preserves_source_float32_motion_hash_and_unsigned_colors(self):
        motion={'clips':{'pause1':{'length':1.,'nodes':{'root':{'controls':{8:{
            'times':np.array([0,1],dtype='<f4'),'values':np.array([[0,0,0],[0,0,1]],dtype='<f4')}}}}}}}
        before=native_keys_hash(motion)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'recipe.json'; api.save_recipe(p,{'schemaVersion':1,'kind':'PhenoMorpher-candidate-inputs',
                'motion':motion,'colors':np.array([0xffffffff],dtype='<u4')})
            actual=api.load_recipe(p)
        self.assertEqual(native_keys_hash(actual['motion']),before)
        self.assertEqual(actual['colors'].dtype,np.dtype('<u4'))
        self.assertEqual(int(actual['colors'][0]),0xffffffff)

    def test_recipe_rejects_object_arrays_and_wrong_shape(self):
        with self.assertRaises(ValueError):
            api.array_hook({'$array':['bad'],'dtype':'O','shape':[1]})
        with self.assertRaises(ValueError):
            api.array_hook({'$array':[1.],'dtype':'<f4','shape':[2]})

    def test_runtime_inventory_detects_drift_and_has_no_approval_side_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);file=root/'part.mdl';file.write_bytes(b'actual native fixture')
            manifest=root/'manifest.json';manifest.write_text(json.dumps({'schemaVersion':1,
                'kind':'PhenoMorpher-game-ready-bodies','version':'1.0.0','targets':[{'target':'control'}],
                'resources':[{'path':'part.mdl','sha256':api.digest(file),'bytes':file.stat().st_size}]}))
            self.assertFalse(api.verify_assets(root,manifest)['assetApprovalCreated'])
            file.write_bytes(b'changed')
            with self.assertRaises(ValueError): api.verify_assets(root,manifest)

    def test_escaped_binding_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'escaped'):
                api.bound(Path(tmp),{'path':'../outside.mdl','sha256':'0'*64})

    def test_repeated_or_weighted_clothing_conversion_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Repeated'):
            convert_text(MARKER+'\n'+MODEL,profile(),'modular-close')
        with self.assertRaisesRegex(ValueError,'weighted'):
            convert_text(MODEL.replace('verts 3','weights 3\nverts 3'),profile(),'modular-close')

    def test_clothing_transfers_detail_preserves_uv_faces_hierarchy_and_tangent_signs(self):
        text,receipt=convert_text(MODEL,profile(),'modular-close')
        before=parse(MODEL)[0][-1]; after=parse(text.replace(MARKER,''))[0][-1]
        np.testing.assert_array_equal(array(before[3],'faces'),array(after[3],'faces'))
        np.testing.assert_array_equal(array(before[3],'tverts'),array(after[3],'tverts'))
        normals=array(after[3],'normals'); tangents=array(after[3],'tangents')
        np.testing.assert_allclose(np.linalg.norm(normals,axis=1),1,atol=1e-10)
        np.testing.assert_allclose(np.linalg.norm(tangents[:,:3],axis=1),1,atol=1e-10)
        np.testing.assert_allclose((normals*tangents[:,:3]).sum(1),0,atol=1e-10)
        np.testing.assert_array_equal(tangents[:,3],1)
        self.assertIn('position 0.1 0 0',after[3]); self.assertIn('materialname skin',after[3])
        self.assertTrue(receipt['completeHierarchyRetained'])

    def test_rigid_island_keeps_all_pairwise_lengths_at_one_scale(self):
        text,receipt=convert_text(MODEL,profile(),'rigid-island')
        a=array(parse(MODEL)[0][-1][3],'verts');b=array(parse(text.replace(MARKER,''))[0][-1][3],'verts')
        np.testing.assert_allclose(np.linalg.norm(b[:,None]-b[None,:],axis=2),
            np.linalg.norm(a[:,None]-a[None,:],axis=2)*receipt['uniformScale'],atol=1e-10)

    def test_cp1252_ascii_attributes_and_native_info_retain_data_and_source_bytes(self):
        material='peau_caf\u00e9'
        payload=('# Skin \u2014 caf\u00e9\n'+MODEL.replace('bitmap skin','bitmap '+material)).encode('cp1252')
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'sample.mdl';source.write_bytes(payload)
            skeleton,attrs,source_pin=api.read_attributes(source)
            self.assertEqual(set(skeleton),{'sample','surface'})
            self.assertEqual(attrs['surface']['material'],[material,'skin'])
            np.testing.assert_array_equal(attrs['surface']['faces'],[[0,1,2]])
            np.testing.assert_array_equal(attrs['surface']['uv'],[[0,0],[1,0],[0,1]])
            np.testing.assert_array_equal(attrs['surface']['normal'],[[0,-1,0]]*3)
            out=io.StringIO()
            with patch.object(cli,'declared'),contextlib.redirect_stdout(out):
                cli.main(['native-info','--input',str(source)])
            result=json.loads(out.getvalue())
            self.assertEqual(result['sourcePin'],source_pin)
            self.assertEqual(result['meshes'][0]['vertices'],3)
            self.assertEqual(result['meshes'][0]['triangles'],1)
            self.assertEqual(source.read_bytes(),payload)


class LineageManifestTests(unittest.TestCase):
    def test_packaged_lineage_matches_the_launcher_copy_and_every_engine_module(self):
        package = Path(__file__).resolve().parent
        packaged = (package/'source-lineage.json').read_bytes()
        launcher = package.parent/'source-lineage.json'
        if launcher.is_file():  # source checkout; an installed wheel ships only the packaged copy
            self.assertEqual(packaged, launcher.read_bytes())
        for row in json.loads(packaged)['modules']:
            module = (package/'engine'/(row['module'] + '.py')).read_bytes().replace(b'\r\n', b'\n')
            self.assertEqual(hashlib.sha256(module).hexdigest(), row['packagedSHA256'], row['module'])
