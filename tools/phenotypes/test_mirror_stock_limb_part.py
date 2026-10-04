"""Meaningful detached mirror/frame/attribute rejection tests; no client."""
import copy
import argparse
import json
from io import BytesIO
from pathlib import Path
import shutil
import tempfile
import unittest

import numpy as np
from PIL import Image

from mirror_stock_limb_part import detached_affine_bake, reflection_between_frames
from place_purposebuilt_pelvis import accessor, raw_corners, rotation_xyz, write_glb
from place_purposebuilt_pelvis import sha


def fixture():
    p = np.asarray([[0,0,0],[.8,0,0],[0,.5,0],[0,0,.4]],dtype='<f4')
    n = np.tile(np.asarray([0,0,1.3],dtype='<f4'),(4,1))
    uv = np.asarray([[.13,.27],[.61,.09],[.02,.94],[.88,.53]],dtype='<f4')
    indices = np.asarray([0,2,1,0,1,3,0,3,2,1,2,3],dtype='<u2')
    tangent = np.tile(np.asarray([1.2,0,0,-1],dtype='<f4'),(4,1))
    color = np.asarray([[13,27,255,255],[61,9,244,128],[2,94,122,64],[88,53,0,255]],dtype='u1')
    binary = bytearray(); views = []; attrs = []
    for array,kind in [(p,'VEC3'),(n,'VEC3'),(uv,'VEC2'),(indices,'SCALAR'),(tangent,'VEC4'),(color,'VEC4')]:
        binary.extend(b'\0'*(-len(binary)%4)); start = len(binary); binary.extend(array.tobytes())
        views.append({'buffer':0,'byteOffset':start,'byteLength':array.nbytes})
        attrs.append({'bufferView':len(views)-1,'count':len(array),'type':kind,
            'componentType':{np.dtype('<u2'):5123,np.dtype('u1'):5121,np.dtype('<f4'):5126}[array.dtype]})
        if array.dtype == np.dtype('u1'): attrs[-1]['normalized'] = True
    binary.extend(b'\0'*(-len(binary)%4)); start=len(binary); binary.extend(b'embedded-image-provenance')
    views.append({'buffer':0,'byteOffset':start,'byteLength':len(b'embedded-image-provenance')})
    binary.extend(b'\0'*(-len(binary)%4))
    doc={'asset':{'version':'2.0'}, 'buffers':[{'byteLength':len(binary)}], 'bufferViews':views,'accessors':attrs,
        'nodes':[{'mesh':0}], 'scenes':[{'nodes':[0]}], 'scene':0,
        'meshes':[{'primitives':[{'attributes':{'POSITION':0,'NORMAL':1,'TEXCOORD_0':2,'TANGENT':4,'COLOR_0':5},'indices':3,'material':0}]}],
        'images':[{'bufferView':6,'mimeType':'image/png'}],'textures':[{'source':0}],
        'materials':[{'pbrMetallicRoughness':{'baseColorTexture':{'index':0}},'normalTexture':{'index':0}}]}
    return doc,bytes(binary)


class MirrorTests(unittest.TestCase):
    def test_measured_frame_conjugation_not_local_x(self):
        left=np.eye(4); right=np.eye(4)
        left[:3,:3]=rotation_xyz([17,9,-31]); right[:3,:3]=rotation_xyz([-8,12,42])
        left[:3,3]=[-.1,.03,.9]; right[:3,3]=[.12,.02,.91]
        matrix,world=reflection_between_frames(left,right,[.004,.02,.1],[.9,.2,.1])
        points=np.asarray([[.1,.03,-.2,1],[0,-.07,-.4,1]])
        self.assertTrue(np.allclose((points@matrix.T)@right.T,(points@left.T)@world.T,atol=1e-14))
        self.assertFalse(np.allclose(matrix[:3,:3],np.diag([-1,1,1])))

    def test_mirror_winding_volume_and_material_sampling(self):
        doc,binary=fixture(); before=copy.deepcopy(doc)
        matrix=np.diag([-1.,1,1,1]); matrix[0,3]=-.000000994
        new,blob,a,proof=detached_affine_bake(doc,binary,matrix,True)
        self.assertEqual(doc,before); self.assertEqual(blob[:len(binary)],binary)
        self.assertEqual(new['materials'],doc['materials']); self.assertEqual(new['images'],doc['images'])
        primitive=new['meshes'][0]['primitives'][0]
        for key in ['TEXCOORD_0','COLOR_0']: self.assertEqual(primitive['attributes'][key],doc['meshes'][0]['primitives'][0]['attributes'][key])
        p,n,uv,_=raw_corners(doc,binary)
        self.assertTrue(np.array_equal(a['uvGltf'],uv[:,[0,2,1]]))
        self.assertTrue(np.array_equal(a['uvNative'][:,:,1],1-a['uvGltf'][:,:,1]))
        cross=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])
        out=np.cross(a['positions'][:,1]-a['positions'][:,0],a['positions'][:,2]-a['positions'][:,0])
        self.assertTrue(np.allclose(out,cross@matrix[:3,:3].T))
        volume=lambda q:np.einsum('ij,ij->i',q[:,0],np.cross(q[:,1],q[:,2])).sum()/6
        self.assertAlmostEqual(volume(p),volume(a['positions']),places=14)
        self.assertLess(proof['maximumAuthoredNormalLengthDifference'],1e-14)
        self.assertTrue(np.all(a['tangents'][:,:,3] == 1))
        self.assertTrue(np.allclose(np.linalg.norm(a['tangents'][:,:,:3],axis=2),1.2))
        # TBN parity: flipping tangent w is necessary to reflect bitangent too.
        extra={}; raw_corners(doc,binary,extra=extra)
        oldt=np.concatenate(extra['TANGENT']['rows'])[:,[0,2,1]]
        oldn=n[:,[0,2,1]]
        oldb=np.cross(oldn,oldt[:,:,:3])*oldt[:,:,3,None]
        newb=np.cross(a['normals'],a['tangents'][:,:,:3])*a['tangents'][:,:,3,None]
        self.assertTrue(np.allclose(newb,oldb@matrix[:3,:3].T))

    def test_proper_uniform_bake_and_nonunit_authored_directions(self):
        doc,binary=fixture(); doc['nodes']=[{'children':[1],'scale':[2,2,2],'translation':[.1,.2,.3]}, {'mesh':0}]
        matrix=np.eye(4); matrix[:3,:3]=rotation_xyz([11,7,-24])*.73;matrix[:3,3]=[.02,-.03,.01]
        new,blob,a,proof=detached_affine_bake(doc,binary,matrix)
        self.assertEqual(new['nodes'],[{'name':'detached_geometry','mesh':0}])
        self.assertTrue(np.allclose(np.linalg.norm(a['normals'],axis=2),1.3))
        self.assertTrue(np.all(a['tangents'][:,:,3] == -1))
        self.assertEqual(proof['triangleCornerOrder'],[0,1,2])
        self.assertEqual(new['meshes'][0]['primitives'][0]['indices'],3)

    def test_double_mirror_roundtrip(self):
        doc,binary=fixture(); matrix=np.diag([-1.,1,1,1]);matrix[0,3]=.012
        first,blob,a,_=detached_affine_bake(doc,binary,matrix,True)
        _,_,b,_=detached_affine_bake(first,blob,matrix,True)
        p,n,uv,_=raw_corners(doc,binary)
        self.assertTrue(np.allclose(p,b['positions'],atol=4e-8,rtol=0))
        self.assertTrue(np.array_equal(n,b['normals']))
        self.assertTrue(np.array_equal(uv,b['uvGltf']))
        self.assertTrue(np.all(b['tangents'][:,:,3] == -1))

    def test_multiple_primitives_and_zero_uv_changes(self):
        doc,binary=fixture(); doc['meshes'][0]['primitives'].append(copy.deepcopy(doc['meshes'][0]['primitives'][0]))
        new,_,a,proof=detached_affine_bake(doc,binary,np.eye(4))
        self.assertEqual(len(new['meshes'][0]['primitives']),2)
        self.assertEqual(proof['triangles'],8)
        self.assertEqual(a['primitiveIds'].tolist(),[0]*4+[1]*4)

    def test_deterministic_geometry_bake(self):
        doc,binary=fixture(); matrix=np.diag([-1.,1,1,1])
        a=detached_affine_bake(doc,binary,matrix,True)
        b=detached_affine_bake(doc,binary,matrix,True)
        self.assertEqual(a[0],b[0]);self.assertEqual(a[1],b[1]);self.assertEqual(a[3],b[3])
        for key in a[2]:self.assertTrue(np.array_equal(a[2][key],b[2][key]))

    def test_canonical_mirror_passes_existing_raw_stage_loader(self):
        from stage_stock_part import raw_triangles
        doc,binary=fixture(); blob=bytearray(binary)
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory); paths=[]; doc['images']=[];doc['textures']=[]
            for color in [(128,95,72),(128,128,255)]:
                path=directory/f'map{len(paths)}.png'
                Image.new('RGB',(2048,2048),color).save(path); paths.append(path)
                data=path.read_bytes();blob.extend(b'\0'*(-len(blob)%4));offset=len(blob);blob.extend(data)
                doc['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':len(data)})
                doc['images'].append({'bufferView':len(doc['bufferViews'])-1,'mimeType':'image/png'})
                doc['textures'].append({'source':len(doc['images'])-1})
            blob.extend(b'\0'*(-len(blob)%4));doc['buffers'][0]['byteLength']=len(blob)
            doc['materials'][0]['normalTexture']['index']=1
            new,baked,archive,_=detached_affine_bake(doc,bytes(blob),np.diag([-1.,1,1,1]),True)
            target=directory/'mirrored.glb';write_glb(target,new,baked)
            p,uv,n,materials=raw_triangles(target,*paths)
            self.assertTrue(np.allclose(p,archive['positions'],atol=3e-8,rtol=0))
            self.assertTrue(np.allclose(n,archive['normals'],atol=6e-8,rtol=0))
            self.assertTrue(np.array_equal(uv,archive['uvNative']))
            self.assertTrue(materials[0]['commonColorPixelsExact'] and materials[0]['commonNormalPixelsExact'])

    def test_reject_unsafe_sources_and_transforms(self):
        doc,binary=fixture()
        for transform in [np.diag([1.,.8,1,1]),np.diag([0.,0,0,1]),np.diag([-1.,1,1,1])]:
            with self.assertRaises(RuntimeError): detached_affine_bake(doc,binary,transform)
        for change in ['animations','skins','weights','targets','JOINTS_0','duplicate','reflected-node','stretch-node','nan','tangent-w']:
            bad=copy.deepcopy(doc); changed_binary=binary
            if change in ['animations','skins']: bad[change]=[{}]
            elif change=='weights': bad['nodes'][0]['weights']=[1]
            elif change=='targets': bad['meshes'][0]['primitives'][0]['targets']=[{}]
            elif change=='JOINTS_0': bad['meshes'][0]['primitives'][0]['attributes']['JOINTS_0']=0
            elif change=='duplicate':bad['scenes'][0]['nodes']=[0,0]
            elif change=='reflected-node':bad['nodes'][0]['scale']=[-1,1,1]
            elif change=='stretch-node':bad['nodes'][0]['scale']=[1,1.1,1]
            else:
                blob=bytearray(binary); index=0 if change=='nan' else 4
                start=bad['bufferViews'][index]['byteOffset']+(0 if change=='nan' else 12)
                blob[start:start+4]=np.asarray([np.nan if change=='nan' else 0],dtype='<f4').tobytes();changed_binary=bytes(blob)
            with self.subTest(change=change), self.assertRaises(RuntimeError): detached_affine_bake(bad,changed_binary,np.eye(4))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(MirrorTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if args.output:
        args.output.mkdir(parents=True,exist_ok=False)
        helper=Path(__file__).with_name('mirror_stock_limb_part.py')
        shutil.copyfile(helper,args.output/'executed-helper.py')
        shutil.copyfile(__file__,args.output/'executed-tests.py')
        report={'schemaVersion':1,'passed':result.wasSuccessful(),'testMethods':result.testsRun,
            'helperSha256':sha(helper),'testSha256':sha(__file__),
            'failures':[str(test) for test,_ in result.failures],'errors':[str(test) for test,_ in result.errors],
            'scope':'Synthetic geometry/frame/UV/TBN preservation and rejection guards; no donor/client acceptance.'}
        (args.output/'tests.json').write_text(json.dumps(report,indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
