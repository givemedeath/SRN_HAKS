"""External donor provenance/material closure and unchanged collected-job guards."""
import copy
from io import BytesIO
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import numpy as np
from PIL import Image

import target_contract as contract
from target_part_pipeline import execute, external_donor_source, fit_matrix, fit_source
from place_purposebuilt_pelvis import raw_corners, read_glb, rotation_xyz, write_glb
from test_mirror_stock_limb_part import fixture
from test_target_part_pipeline import target_fixture


class ExternalDonorIntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name).resolve()
        self.target = self.root/'target.json'; self.target.write_text(json.dumps(target_fixture()))
        self.target_data = contract.load(self.target)
        self.origin = self.root/'user-download.glb'; self.source = self.root/'frozen-donor.glb'
        self.inventory = self.root/'glb-inventory.json'; self.intake = self.root/'intake.json'
        self.helper = self.root/'executed-intake.py'; self.helper.write_text('# frozen user intake\n')
        self.doc, original = fixture(); binary = bytearray(original)
        self.doc['images'] = []; self.doc['textures'] = []
        for color in [(128,128,255), (170,119,79), (255,121,0)]:
            stream = BytesIO(); Image.new('RGB', (4,4), color).save(stream, format='PNG'); blob = stream.getvalue()
            binary.extend(b'\0'*(-len(binary)%4)); start = len(binary); binary.extend(blob)
            self.doc['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':len(blob)})
            self.doc['images'].append({'bufferView':len(self.doc['bufferViews'])-1,'mimeType':'image/png'})
            self.doc['textures'].append({'source':len(self.doc['images'])-1})
        binary.extend(b'\0'*(-len(binary)%4)); self.doc['buffers'][0]['byteLength'] = len(binary)
        self.binary = bytes(binary)
        self.doc['materials'] = [{'normalTexture':{'index':0}, 'pbrMetallicRoughness':
                                 {'baseColorTexture':{'index':1},'metallicRoughnessTexture':{'index':2}}}]
        self.make_intake()

    def tearDown(self): self.tmp.cleanup()

    def make_intake(self):
        write_glb(self.origin, self.doc, self.binary); shutil.copyfile(self.origin, self.source)
        maps = []
        for i, image in enumerate(self.doc['images']):
            view = self.doc['bufferViews'][image['bufferView']]; start = view.get('byteOffset',0)
            path = self.root/('image-'+str(i)+'.png'); path.write_bytes(self.binary[start:start+view['byteLength']])
            maps.append({'imageIndex':i, 'path':str(path), 'sha256':contract.sha(path), 'mimeType':image['mimeType'],
                         'bufferView':image['bufferView'], 'length':view['byteLength'], 'nativeBytesCopiedWithoutEditing':True})
        inventory = {name:self.doc.get(name) for name in
                     ('asset','scenes','scene','nodes','meshes','materials','textures','samplers','accessors','buffers')}
        inventory.update({name:self.doc.get(name,[]) for name in ('skins','animations','extensionsUsed','extensionsRequired')})
        inventory['images'] = maps; self.inventory.write_text(json.dumps(inventory))
        self.record = {'schemaVersion':1,'kind':'user-provided-external-donor-intake','providerDeclaredByUser':'Meshy',
                       'targetId':self.target_data['id'],'part':'chest','targetContract':str(self.target),
                       'targetContractSha256':contract.sha(self.target),'receivedUtc':'2026-10-04T18:04:48Z',
                       'origin':str(self.origin),'originSha256':contract.sha(self.origin),'source':str(self.source),
                       'sourceSha256':contract.sha(self.source),'byteLength':self.source.stat().st_size,
                       'embeddedImageCopies':maps,'inventory':{'path':str(self.inventory),'sha256':contract.sha(self.inventory)},
                       'userDesignSteering':'User supplied this external static torso for fit review.',
                       'provenanceLimits':['External prompt, seed, model and raw masters are unavailable.'],
                       'selected':False,'sourceUnchanged':True,'frozenInputs':{str(self.origin):contract.sha(self.origin),
                       str(self.target):contract.sha(self.target),str(self.helper):contract.sha(self.helper)}}
        self.save()

    def save(self): self.intake.write_text(json.dumps(self.record))

    def validate(self, **kw):
        return external_donor_source(kw.get('source',self.source), self.intake,
                                     kw.get('target_path',self.target), self.target_data, kw.get('part','chest'))

    def config(self):
        return {'schemaVersion':2,'operation':'fit','part':'chest','coordinateSpace':'working',
                'targetContract':str(self.target),'targetContractSha256':contract.sha(self.target),
                'source':str(self.source),'sourceSha256':contract.sha(self.source),
                'sourceReceipt':str(self.intake),'sourceReceiptSha256':contract.sha(self.intake),
                'uniformScale':.63,'rotationDegreesXYZ':[19,-7,31],
                'sourceAnchorNwn':[.11,.08,.02],'targetAnchorLocal':[.03,-.02,-.04]}

    def test_valid_meshy_intake_without_comfy_job(self):
        result = self.validate(); self.assertEqual(result['providerDeclaredByUser'],'Meshy')
        self.assertNotIn('promptId',result); self.assertNotIn('state',result)
        self.assertEqual(fit_source(self.source,self.intake,self.target,self.target_data,'chest'),result)

    def test_fit_preserves_serialized_attributes_and_complete_source_closure(self):
        config = self.config(); path = self.root/'fit-config.json'; path.write_text(json.dumps(config))
        result = json.loads(execute(path,self.root/'fit').read_text())
        doc, binary = read_glb(self.source); new, baked = read_glb(result['candidate'])
        p,n,uv,_ = raw_corners(doc,binary); ap,an,au,_ = raw_corners(new,baked); matrix = fit_matrix(config)
        np.testing.assert_allclose(ap,p@matrix[:3,:3].T+matrix[:3,3],atol=1e-7)
        np.testing.assert_allclose(an,n@rotation_xyz(config['rotationDegreesXYZ']).T,atol=1e-7)
        self.assertTrue(np.array_equal(uv,au)); self.assertEqual(baked[:len(binary)],binary)
        self.assertEqual(new['materials'],doc['materials']); self.assertEqual(new['images'],doc['images'])
        for path in [self.origin,self.source,self.inventory,self.helper,*[Path(row['path']) for row in self.record['embeddedImageCopies']]]:
            self.assertEqual(result['frozenInputs'][str(path)],contract.sha(path))
        self.assertEqual(result['sourceProvenance']['kind'],'user-provided-external-donor-intake')
        self.assertFalse(result['sourceProvenance']['collectedGenerationReceipt'])
        self.assertFalse(result['sourceProvenance']['externalRigImported']); self.assertEqual(result['statureApplications'],0)
        self.assertFalse(result['productionAccepted']); self.assertFalse(result['clientAccepted'])

    def test_stale_source(self):
        self.source.write_bytes(self.source.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'exact source'): self.validate()

    def test_other_source_path_with_same_bytes(self):
        other=self.root/'other.glb'; shutil.copyfile(self.source,other)
        with self.assertRaisesRegex(ValueError,'exact source'): self.validate(source=other)

    def test_stale_target(self):
        self.target.write_text(self.target.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'another target'): self.validate()

    def test_cross_target_path_identical_bytes(self):
        other=self.root/'other-target.json'; shutil.copyfile(self.target,other)
        with self.assertRaisesRegex(ValueError,'another target'): self.validate(target_path=other)

    def test_cross_target_id(self):
        self.record['targetId']='another-target'; self.save()
        with self.assertRaisesRegex(ValueError,'another target'): self.validate()

    def test_cross_part(self):
        with self.assertRaisesRegex(ValueError,'another target or part'): self.validate(part='bicepl')

    def test_stale_original_origin(self):
        self.origin.write_bytes(self.origin.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'Frozen input'): self.validate()

    def test_unpinned_original_user_input(self):
        del self.record['frozenInputs'][str(self.origin)]; self.save()
        with self.assertRaisesRegex(ValueError,'freeze original user'): self.validate()

    def test_unpinned_target(self):
        del self.record['frozenInputs'][str(self.target)]; self.save()
        with self.assertRaisesRegex(ValueError,'freeze original user'): self.validate()

    def test_stale_executed_intake_pin(self):
        self.helper.write_text('# changed\n')
        with self.assertRaisesRegex(ValueError,'Frozen input'): self.validate()

    def test_false_external_kind_cannot_fall_back_to_fake_job(self):
        self.record.update(kind='unsupported-external-intake',state='success',promptId='fake',
                           outputs=[{'localPath':str(self.source),'sha256':contract.sha(self.source)}]); self.save()
        with self.assertRaisesRegex(ValueError,'never reinterpret'): fit_source(self.source,self.intake,self.target,self.target_data,'chest')

    def test_unsupported_external_schema(self):
        for version in [2,True,'1']:
            self.record['schemaVersion']=version; self.save()
            with self.subTest(version=version), self.assertRaisesRegex(ValueError,'version 1'): self.validate()

    def test_fake_job_fields_not_allowed_in_intake(self):
        self.record.update(state='success',promptId='fake',outputs=[]); self.save()
        with self.assertRaisesRegex(ValueError,'unsupported provenance'): self.validate()

    def test_missing_actual_user_provider(self):
        self.record['providerDeclaredByUser']=' '; self.save()
        with self.assertRaisesRegex(ValueError,'declared user origin'): self.validate()

    def test_origin_must_match_source_bytes(self):
        self.record['originSha256']='0'*64; self.save()
        with self.assertRaisesRegex(ValueError,'unchanged user'): self.validate()

    def test_changed_embedded_image_copy(self):
        image=Path(self.record['embeddedImageCopies'][1]['path']); image.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Frozen input'): self.validate()

    def test_false_map_metadata(self):
        self.record['embeddedImageCopies'][0]['sha256']='0'*64; self.save()
        with self.assertRaisesRegex(ValueError,'literal embedded'): self.validate()

    def test_missing_map_owner(self):
        self.record['embeddedImageCopies'].pop(); self.save()
        with self.assertRaisesRegex(ValueError,'every embedded'): self.validate()

    def test_duplicate_image_owner(self):
        self.record['embeddedImageCopies'][2]['imageIndex']=0; self.save()
        with self.assertRaisesRegex(ValueError,'complete and unique'): self.validate()

    def test_inventory_pin_stale(self):
        self.inventory.write_text('{}')
        with self.assertRaisesRegex(ValueError,'Frozen input'): self.validate()

    def test_rehashed_wrong_inventory_cannot_hide_source_materials(self):
        data=json.loads(self.inventory.read_text()); data['materials']=[]; self.inventory.write_text(json.dumps(data))
        self.record['inventory']['sha256']=contract.sha(self.inventory); self.save()
        with self.assertRaisesRegex(ValueError,'decoded source'): self.validate()

    def test_unresolved_material_texture(self):
        self.doc['materials'][0]['normalTexture']['index']=999; self.make_intake()
        with self.assertRaisesRegex(ValueError,'material texture reference'): self.validate()

    def test_unresolved_texture_image(self):
        self.doc['textures'][0]['source']=999; self.make_intake()
        with self.assertRaisesRegex(ValueError,'texture image reference'): self.validate()

    def test_external_rig_import_rejected(self):
        self.doc['skins']=[{'joints':[0]}]; self.make_intake()
        with self.assertRaisesRegex(ValueError,'no external rig import'): self.validate()

    def test_external_animation_import_rejected(self):
        self.doc['animations']=[{'channels':[],'samplers':[]}]; self.make_intake()
        with self.assertRaisesRegex(ValueError,'no external rig import'): self.validate()

    def test_nonpositive_fit_stays_rejected(self):
        for scale in [0,-1,float('nan')]:
            config=self.config(); config['uniformScale']=scale
            with self.subTest(scale=scale), self.assertRaisesRegex(ValueError,'Positive finite'): fit_matrix(config)


if __name__ == '__main__': unittest.main()
