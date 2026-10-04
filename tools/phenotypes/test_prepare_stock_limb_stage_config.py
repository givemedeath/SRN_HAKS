"""Map/side/receipt guard tests; synthetic geometry never staged or launched."""
import argparse
import copy
from io import BytesIO
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import numpy as np
from PIL import Image

import prepare_stock_limb_stage_config as prepare
from mirror_stock_limb_part import detached_affine_bake
from place_purposebuilt_pelvis import write_glb
from test_mirror_stock_limb_part import fixture


def synthetic_maps():
    doc,binary=fixture();blob=bytearray(binary)
    for color in [(162,91,74),(128,128,255)]:
        stream=BytesIO();Image.new('RGB',(2048,2048),color).save(stream,format='PNG')
        encoded=stream.getvalue();start=len(blob);blob.extend(encoded);blob.extend(b'\0'*(-len(blob)%4))
        doc['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':len(encoded)})
    doc['images']=[{'bufferView':len(doc['bufferViews'])-2,'mimeType':'image/png'},
                   {'bufferView':len(doc['bufferViews'])-1,'mimeType':'image/png'}]
    doc['textures']=[{'source':0},{'source':1}]
    doc['materials']=[{'pbrMetallicRoughness':{'baseColorTexture':{'index':0}},'normalTexture':{'index':1}}]
    doc['meshes'][0]['primitives'][0]['attributes'].pop('COLOR_0')
    doc['buffers'][0]['byteLength']=len(blob)
    return doc,bytes(blob)


class PrepareGuards(unittest.TestCase):
    def base_receipt(self,folder,part='legl'):
        doc,binary=synthetic_maps();source=folder/'synthetic-source.glb';write_glb(source,doc,binary)
        archive=folder/'synthetic-corners.npz';np.savez(archive,diagnosticOnly=np.asarray(True))
        generation=folder/'generation.json';generation.write_text(json.dumps({'state':'success','promptId':'synthetic-test-only',
            'outputs':[{'localPath':str(source),'sha256':prepare.sha(source)}]}))
        receipt={'candidate':str(source),'candidateSha256':prepare.sha(source),'part':part,'model':'pmh0_'+part+'001','joint':prepare.JOINTS[part],
            'nativeCornerArchive':{'path':str(archive),'sha256':prepare.sha(archive)},'source':str(source),'sourceSha256':prepare.sha(source),
            'generation':str(generation),'generationSha256':prepare.sha(generation),'jobPromptId':'synthetic-test-only'}
        path=folder/'placement.json';path.write_text(json.dumps(receipt))
        return path,receipt,doc,binary

    def test_exact_encoded_2k_map_blobs(self):
        doc,binary=synthetic_maps();maps,limitations=prepare.material_maps(doc,binary)
        self.assertEqual(set(maps),{'color','normal'})
        for item in maps.values():
            image=doc['images'][item['imageIndex']];view=doc['bufferViews'][image['bufferView']]
            self.assertEqual(item['blob'],binary[view['byteOffset']:view['byteOffset']+view['byteLength']])
            self.assertEqual(Image.open(BytesIO(item['blob'])).size,(2048,2048))
        self.assertTrue(limitations)

    def test_visible_material_modifier_rejections(self):
        doc,binary=synthetic_maps()
        for change in ['factor','alpha','normal','emissive','extension','texcoord','uri','imagebounds','vertexcolor']:
            bad=copy.deepcopy(doc);material=bad['materials'][0]
            if change=='factor':material['pbrMetallicRoughness']['baseColorFactor']=[.8,1,1,1]
            elif change=='alpha':material['alphaMode']='BLEND'
            elif change=='normal':material['normalTexture']['scale']=.35
            elif change=='emissive':material['emissiveFactor']=[1,0,0]
            elif change=='extension':material['extensions']={'KHR_materials_unlit':{}}
            elif change=='texcoord':material['normalTexture']['texCoord']=1
            elif change=='uri':bad['images'][0]['uri']='old-body-color.png'
            elif change=='imagebounds':bad['bufferViews'][bad['images'][0]['bufferView']]['byteLength']=len(binary)+1
            else:bad['meshes'][0]['primitives'][0]['attributes']['COLOR_0']=5
            with self.subTest(change=change),self.assertRaises(RuntimeError):prepare.material_maps(bad,binary)

    def test_receipt_candidate_generation_and_side_rejections(self):
        with tempfile.TemporaryDirectory() as temporary:
            path,receipt,_,_=self.base_receipt(Path(temporary))
            _,part,lineage=prepare.receipt_lineage(path);self.assertEqual(part,'legl');self.assertEqual(len(lineage),1)
            for key,value in [('candidateSha256','0'*64),('generationSha256','0'*64),('part','legr'),('joint','rthigh_g')]:
                bad={**receipt,key:value};path.write_text(json.dumps(bad))
                with self.subTest(key=key),self.assertRaises(RuntimeError):prepare.receipt_lineage(path)

    def test_repair_parent_chain_and_cycle_rejections(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);parent,receipt,_,_=self.base_receipt(folder)
            child={**receipt,'parentReceipt':str(parent),'parentReceiptSha256':prepare.sha(parent),
                'parentSource':receipt['candidate'],'parentSourceSha256':receipt['candidateSha256']}
            child_path=folder/'repair.json';child_path.write_text(json.dumps(child))
            self.assertEqual(len(prepare.receipt_lineage(child_path)[2]),2)
            child['parentSourceSha256']='0'*64;child_path.write_text(json.dumps(child))
            with self.assertRaises(RuntimeError):prepare.receipt_lineage(child_path)
            with self.assertRaisesRegex(RuntimeError,'Cyclic'):prepare.receipt_lineage(parent,{parent.resolve()})

    def test_mirror_actual_winding_uv_normals_tangent_and_map_proof(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);parent,receipt,doc,binary=self.base_receipt(folder)
            reflection=np.diag([-1.,1,1,1]);new,blob,archive,_=detached_affine_bake(doc,binary,reflection,True)
            candidate=folder/'synthetic-mirror.glb';write_glb(candidate,new,blob)
            corners=folder/'mirror-corners.npz';np.savez(corners,**archive)
            mirror={'candidate':str(candidate),'candidateSha256':prepare.sha(candidate),'source':receipt['candidate'],
                'sourceSha256':receipt['candidateSha256'],'sourceReceipt':str(parent),'sourceReceiptSha256':prepare.sha(parent),
                'configuration':{'sourceJoint':'lthigh_g','targetJoint':'rthigh_g'},'sourceToTargetLocal':reflection.tolist(),
                'nativeCornerArchive':{'path':str(corners),'sha256':prepare.sha(corners)}}
            path=folder/'mirror.json';path.write_text(json.dumps(mirror))
            self.assertEqual(prepare.receipt_lineage(path)[1],'legr')
            # Relabeling the unreflected donor as right must fail even when hashes are truthful.
            mirror['candidate']=receipt['candidate'];mirror['candidateSha256']=receipt['candidateSha256'];path.write_text(json.dumps(mirror))
            with self.assertRaisesRegex(RuntimeError,'Actual mirrored'):prepare.receipt_lineage(path)

    def test_shin_mirror_and_cross_family_fake_rejection(self):
        for donor,target in [('shinl','shinr'),('legl','legr'),('footl','footr')]:
            with tempfile.TemporaryDirectory() as temporary:
                folder=Path(temporary);parent,receipt,doc,binary=self.base_receipt(folder,donor)
                reflection=np.diag([-1.,1,1,1]);new,blob,archive,_=detached_affine_bake(doc,binary,reflection,True)
                candidate=folder/'mirror.glb';write_glb(candidate,new,blob)
                corners=folder/'mirror.npz';np.savez(corners,**archive)
                mirror={'candidate':str(candidate),'candidateSha256':prepare.sha(candidate),'source':receipt['candidate'],
                    'sourceSha256':receipt['candidateSha256'],'sourceReceipt':str(parent),'sourceReceiptSha256':prepare.sha(parent),
                    'configuration':{'sourceJoint':prepare.JOINTS[donor],'targetJoint':prepare.JOINTS[target]},
                    'sourceToTargetLocal':reflection.tolist(),'nativeCornerArchive':{'path':str(corners),'sha256':prepare.sha(corners)}}
                path=folder/'mirror.json';path.write_text(json.dumps(mirror))
                self.assertEqual(prepare.receipt_lineage(path)[1],target)
                # Even genuinely reflected geometry cannot be relabeled as another anatomical family.
                mirror['configuration']['targetJoint']='rthigh_g' if donor=='shinl' else 'rshin_g'
                path.write_text(json.dumps(mirror))
                with self.assertRaisesRegex(RuntimeError,'joint side association'):prepare.receipt_lineage(path)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PrepareGuards))
    if args.output:
        args.output.mkdir(parents=True,exist_ok=False)
        for path in [Path(__file__),Path(prepare.__file__)]:shutil.copyfile(path,args.output/path.name)
        (args.output/'tests.json').write_text(json.dumps({'passed':result.wasSuccessful(),'testMethods':result.testsRun,
            'helperSha256':prepare.sha(prepare.__file__),'testSha256':prepare.sha(__file__),
            'failures':[str(t) for t,_ in result.failures],'errors':[str(t) for t,_ in result.errors],
            'scope':'Synthetic map/receipt/reflection guards only; no generated anatomy, native or client acceptance.'},indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
