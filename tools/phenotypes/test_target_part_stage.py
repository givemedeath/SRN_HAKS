"""Painted PLT, original normal, ORM roughness and garment ownership checks."""
from io import BytesIO
import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

import target_contract as contract
from place_purposebuilt_pelvis import write_glb
from target_part_pipeline import execute
from target_part_stage import material_inputs, stage
from test_mirror_stock_limb_part import fixture
from test_target_part_pipeline import target_fixture


def textured_fixture():
    doc, binary = fixture(); blob = bytearray(binary)
    doc['images'] = []; doc['textures'] = []
    for color in [(128,95,72),(111,133,244),(80,170,23)]:
        stream = BytesIO(); Image.new('RGB',(2048,2048),color).save(stream,format='PNG')
        data = stream.getvalue(); blob.extend(b'\0'*(-len(blob)%4)); offset = len(blob); blob.extend(data)
        doc['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':len(data)})
        doc['images'].append({'bufferView':len(doc['bufferViews'])-1,'mimeType':'image/png'})
        doc['textures'].append({'source':len(doc['images'])-1})
    blob.extend(b'\0'*(-len(blob)%4)); doc['buffers'][0]['byteLength'] = len(blob)
    doc['materials'] = [{'pbrMetallicRoughness':{'baseColorTexture':{'index':0},
                          'metallicRoughnessTexture':{'index':2},'roughnessFactor':.6},
                         'normalTexture':{'index':1,'scale':1},'occlusionTexture':{'index':2}}]
    return doc, bytes(blob)


class TargetPartStageTests(unittest.TestCase):
    def test_ao_variants_share_untreated_parent_and_do_not_accumulate(self):
        doc, binary = textured_fixture()
        zero, _ = material_inputs(doc,binary,{0:'skin'},'chest',0)
        light, _ = material_inputs(doc,binary,{0:'skin'},'chest',.15)
        stronger, _ = material_inputs(doc,binary,{0:'skin'},'chest',.35)
        parent_intensity = np.dot([128,95,72],[.2126,.7152,.0722])
        for strength, rows in [(0,zero),(.15,light),(.35,stronger)]:
            self.assertEqual(rows['skin']['intensity'][0,0],int(parent_intensity*(1-strength*(1-80/255))))
            self.assertTrue(np.array_equal(rows['skin']['normal'][0,0],[111,133,244]))
            self.assertEqual(rows['skin']['roughness'][0,0],102)

    def test_material_rejection_guards(self):
        doc,binary = textured_fixture()
        for bad_part, roles, strength, change in [
            ('handl',{0:'garment'},0,None), ('chest',{0:'skin'},.2,None),
            ('chest',{0:'skin'},0,'normal'), ('pelvis',{0:'skin'},0,'alpha'),
            ('chest',{0:'skin'},0,'baseFactor')]:
            bad = copy.deepcopy(doc)
            if change == 'normal': bad['materials'][0]['normalTexture']['scale'] = .35
            if change == 'alpha': bad['materials'][0]['alphaMode'] = 'BLEND'
            if change == 'baseFactor': bad['materials'][0]['pbrMetallicRoughness']['baseColorFactor'] = [.5,1,1,1]
            with self.subTest(change=change,part=bad_part),self.assertRaises(ValueError):
                material_inputs(bad,binary,roles,bad_part,strength)
        # A garment cannot be hidden alongside an otherwise valid skin material.
        doc['materials'].append(copy.deepcopy(doc['materials'][0]))
        with self.assertRaisesRegex(ValueError,'only to pelvis'):
            material_inputs(doc,binary,{0:'skin',1:'garment'},'chest',0)

    def test_stage_transport_and_serialization_do_not_imply_acceptance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root/'raw.glb'; write_glb(source,*textured_fixture())
            target = root/'target.json'; target.write_text(json.dumps(target_fixture()))
            job = root/'job.json'; job.write_text(json.dumps({'state':'success','promptId':'test',
                'outputs':[{'localPath':str(source),'sha256':contract.sha(source)}]}))
            fit = {'schemaVersion':2,'operation':'fit','part':'chest','coordinateSpace':'working',
                   'targetContract':str(target),'targetContractSha256':contract.sha(target),
                   'source':str(source),'sourceSha256':contract.sha(source),
                   'sourceReceipt':str(job),'sourceReceiptSha256':contract.sha(job),
                   'uniformScale':.7,'rotationDegreesXYZ':[11,3,-7],
                   'sourceAnchorNwn':[0,0,0],'targetAnchorLocal':[0,0,0]}
            config = root/'fit.json'; config.write_text(json.dumps(fit)); fitted = execute(config,root/'fit')
            geometry = json.loads(fitted.read_text()); candidate = Path(geometry['candidate'])
            staging = {'schemaVersion':2,'kind':'target-part-stage','diagnosticOnly':True,
                       'part':'chest','coordinateSpace':'working','targetContract':str(target),
                       'targetContractSha256':contract.sha(target),'source':str(candidate),
                       'sourceSha256':contract.sha(candidate),'sourceReceipt':str(fitted),
                       'sourceReceiptSha256':contract.sha(fitted),'materialRoles':{'0':'skin'},'aoStrength':0}
            config = root/'stage.json'; config.write_text(json.dumps(staging)); result = stage(config,root/'stage')
            receipt = json.loads(result.read_text()); resources = root/'stage/resources'
            self.assertEqual(set(receipt['materialResourceHashes']),{'pmg0_chest001.mtr','pmg0_chest001.plt',
                             'pmg0_chest001n.tga','pmg0_chest001r.tga'})
            text = (resources/'pmg0_chest001.mtr').read_text()
            self.assertNotIn('texture0',text); self.assertIn('texture3 pmg0_chest001r',text)
            self.assertIn('Roughness 0',text)
            self.assertTrue(np.array_equal(np.asarray(Image.open(resources/'pmg0_chest001n.tga'))[0,0],[111,133,244]))
            self.assertTrue(np.array_equal(np.asarray(Image.open(resources/'pmg0_chest001r.tga'))[0,0],[102,102,102]))
            pixels = np.frombuffer((resources/'pmg0_chest001.plt').read_bytes()[24:],dtype='u1').reshape(2048,2048,2)
            self.assertFalse(pixels[:,:,1].any()); self.assertEqual(pixels[0,0,0],int(np.dot([128,95,72],[.2126,.7152,.0722])))
            self.assertTrue(receipt['diagnosticOnly']); self.assertFalse(receipt['installedShaderVerified'])
            self.assertFalse(receipt['productionAccepted']); self.assertFalse(receipt['clientAccepted'])
            self.assertFalse(receipt['nativeCompiled']); self.assertEqual(receipt['statureApplications'],0)
            self.assertEqual(receipt['rawAttributeAsciiProof']['skin']['actualAsciiCornerMaximumErrors'],
                             {'position':0,'normal':0,'uv':0})


if __name__ == '__main__': unittest.main()
