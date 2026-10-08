"""Serializer/auditor integration at the original-detail replay boundary.

The expensive chart worker has independent math, source and real2K replay tests.
These synthetic fixtures substitute its output, while exercising real stage
ASCII/PLT/TGA/MTR serializers and the native audit's effective-row checks.
"""
from copy import deepcopy
import json
import shutil
import struct
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

import target_contract as c
import source_skin_detail_contract as detail
import replay_stage_skin_detail as replay
import target_part_stage as stage
import audit_target_native_part as audit
from place_purposebuilt_pelvis import read_glb, write_glb
from target_part_pipeline import execute
import test_target_part_stage as material_fixture
import test_human_female_stock_exact as female_fixture


def save(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')
    return path


def native_fixture(model,positions,normals,uv):
    """Construct a literal synthetic detached native buffer, never compile it."""
    p=positions.reshape(-1,3).astype('f4');n=normals.reshape(-1,3).astype('f4');u=uv.reshape(-1,2).astype('f4')
    unit=n.astype(float)/np.linalg.norm(n,axis=1)[:,None]
    t=np.tile([1.,0,0],(len(p),1));t-=unit*np.einsum('ij,ij->i',t,unit)[:,None]
    t/=np.linalg.norm(t,axis=1)[:,None]
    root=232;children=root+0x70;mesh=children+4;faces=mesh+0x270
    raw_offset=faces+len(positions)*32;raw_size=len(p)*(12+8+12+12+4)
    data=bytearray(12+raw_offset+raw_size)
    struct.pack_into('<III',data,0,0,raw_offset,raw_size)
    def string(at,value):
        blob=value.encode('ascii')+b'\0';data[at:at+len(blob)]=blob
    string(12+8,model);string(12+0xa8,'NULL');struct.pack_into('<II',data,12+0x48,root,2)
    data[12+0x72]=4;struct.pack_into('<f',data,12+0xa4,1)
    string(12+root+32,model);struct.pack_into('<I',data,12+root+0x6c,1)
    struct.pack_into('<III',data,12+root+0x48,children,1,1);struct.pack_into('<I',data,12+children,mesh)
    at=12+mesh;string(at+32,model+'p0');struct.pack_into('<I',data,at+0x6c,33)
    struct.pack_into('<III',data,at+0x78,faces,len(positions),len(positions))
    struct.pack_into('<HH',data,at+0x230,len(p),1);struct.pack_into('<I',data,at+0x248,0xffffffff)
    string(at+0xe8,model);string(at+0xe8+3*64,model);struct.pack_into('<I',data,at+0xd4,1)
    pointer=0
    for field,row in zip([0x22c,0x234,0x244,0x258,0x260],[p,u,n,t,np.ones((len(p),1))]):
        struct.pack_into('<I',data,at+field,pointer);blob=row.astype('<f4').tobytes()
        start=12+raw_offset+pointer;data[start:start+len(blob)]=blob;pointer+=len(blob)
    for face in range(len(positions)):
        struct.pack_into('<HHH',data,12+faces+face*32+26,face*3,face*3+1,face*3+2)
    return bytes(data)

class SourceDetailDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.tp, cls.target = female_fixture.stock_fixture(cls.root)
        cls.raw = cls.root/'raw.glb'
        write_glb(cls.raw, *material_fixture.textured_fixture())
        job = save(cls.root/'job.json', {'state':'success', 'promptId':'synthetic-dispatch',
            'outputs':[{'localPath':str(cls.raw), 'sha256':c.sha(cls.raw)}]})
        fit = {'schemaVersion':2, 'operation':'fit', 'part':'shinl', 'coordinateSpace':'working',
            'targetContract':str(cls.tp), 'targetContractSha256':c.sha(cls.tp),
            'source':str(cls.raw), 'sourceSha256':c.sha(cls.raw),
            'sourceReceipt':str(job), 'sourceReceiptSha256':c.sha(job),
            'uniformScale':.4, 'rotationDegreesXYZ':[4,9,0],
            'sourceAnchorNwn':[0,0,0], 'targetAnchorLocal':[0,0,0]}
        cls.rp = execute(save(cls.root/'fit.json', fit), cls.root/'fitted')
        cls.parent = json.loads(cls.rp.read_text(encoding='utf-8'))
        cls.source = Path(cls.parent['candidate'])
        cls.doc, cls.binary = read_glb(cls.source)
        cls.original, cls.transport = stage.material_inputs(cls.doc, cls.binary, {0:'skin'}, 'shinl', 0,
                                                          c.fixed_garment_parts(cls.target))
        # Asymmetric literal fixture rows expose accidental flips and original-map fallbacks.
        cls.color = cls.original['skin']['color'].copy()
        cls.color[:1024,:1024] = [183,103,59]
        cls.color[1024:,1024:] = [145,83,61]
        cls.original_red = np.full((2048,2048), 80, dtype='u1')
        cls.recipe = save(cls.root/'synthetic-recipe.json', {'unitFixture':True, 'notAnAcceptedRecipe':True})
        cls.manifest = save(cls.root/'synthetic-manifest.json', {'unitFixture':True})
        cls.controls = {'mode':detail.MODE, 'receipt':replay.file_row(cls.recipe),
                        'sourceManifest':replay.file_row(cls.manifest)}
        cls.base = {'schemaVersion':2, 'kind':'target-part-stage', 'diagnosticOnly':True,
            'part':'shinl', 'coordinateSpace':'working',
            'targetContract':str(cls.tp), 'targetContractSha256':c.sha(cls.tp),
            'source':str(cls.source), 'sourceSha256':c.sha(cls.source),
            'sourceReceipt':str(cls.rp), 'sourceReceiptSha256':c.sha(cls.rp),
            'materialRoles':{'0':'skin'}, 'aoStrength':0}
        cls.counter = 0

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def worker(self, value, tp, target, part, space, source, rp, roles, ao):
        """Controlled replay result; no fake generated/native/client evidence."""
        detail.controls(value)
        self.assertEqual(value, self.controls)
        self.assertEqual((tp, target, part, space, source, rp, roles),
                         (self.tp, self.target, 'shinl', 'working', self.source, self.rp, {0:'skin'}))
        rows = {key:val.copy() for key,val in self.original['skin'].items()}
        rows['color'] = self.color.copy()
        rows['intensity'] = detail.intensity(self.color, self.original_red, ao)
        proof = {'kind':detail.KIND, 'recipeMode':detail.MODE,
            'materialReceipt':replay.file_row(self.recipe), 'sourceManifest':replay.file_row(self.manifest),
            'independentUntreatedParent':replay.file_row(self.source),
            'derivedColorPixelsEdited':bool(np.any(self.color!=self.original['skin']['color'])),
            'derivedIntensityPixelsEdited':bool(np.any(rows['intensity']!=detail.intensity(self.original['skin']['color'],self.original_red,ao))),
            'originalEmbeddedMapsEdited':False, 'normalPixelsEdited':False, 'roughnessPixelsEdited':False,
            'unitFixture':True, 'aoStrength':ao}
        return {'document':self.doc, 'binary':self.binary, 'materialRows':{'skin':rows},
            'originalMaterialProof':self.transport, 'proof':proof, 'sourceReceipt':self.parent,
            'frozenInputs':{str(p):c.sha(p) for p in (self.recipe,self.manifest)},
            'auditFiles':[self.recipe,self.manifest]}

    def stage_fixture(self, ao=0, derived=True):
        type(self).counter += 1
        name = 'stage-'+str(self.counter)
        value = {**self.base, 'aoStrength':ao}
        if derived:value['skinIntensityInputs'] = deepcopy(self.controls)
        config = save(self.root/(name+'.json'), value)
        out = self.root/name
        with patch.object(replay, 'staging_inputs', side_effect=self.worker) as worker:
            rp = stage.stage(config, out)
        self.assertEqual(worker.call_count, int(derived))
        return json.loads(rp.read_text(encoding='utf-8')),out

    def effective(self, receipt):
        with patch.object(replay, 'staging_inputs', side_effect=self.worker) as worker:
            result = audit.audit_source_inputs(receipt,self.source,self.rp,self.tp,self.target,'shinl','working')
        self.assertEqual(worker.call_count, int(receipt.get('derivedMaterialProof') is not None))
        return result

    def check_resources(self, receipt, out, effective):
        proof,_ = audit.audit_material_resources(out/'resources','pfh0_shinl001','skin',
            effective['materialRows']['skin'], {'materialResourceHashes':receipt['materialResourceHashes']})
        self.assertTrue(proof['normalPixelsExact'])
        self.assertTrue(proof['roughnessPixelsExact'])
        self.assertTrue(proof['compileTimeDependenciesExact'])

    def test_real_serializers_and_native_material_rows_use_replayed_inputs(self):
        original_source = self.source.read_bytes()
        receipt,out = self.stage_fixture()
        self.assertEqual(receipt['materialInputBasis'],detail.BASIS)
        self.assertEqual(receipt['untreatedParentSha256'],c.sha(self.source))
        self.assertEqual(receipt['rawAttributeAsciiProof']['skin']['actualAsciiCornerMaximumErrors'],
                         {'position':0,'normal':0,'uv':0})
        effective = self.effective(receipt)
        self.assertTrue(effective['materialColorPixelsEdited'])
        self.assertTrue(effective['materialIntensityPixelsEdited'])
        self.check_resources(receipt,out,effective)
        data = (out/'resources/pfh0_shinl001.plt').read_bytes()
        pixels = np.frombuffer(data[24:],dtype='u1').reshape(2048,2048,2)[::-1]
        np.testing.assert_array_equal(pixels[:,:,0],detail.intensity(self.color,self.original_red,0))
        self.assertFalse(pixels[:,:,1].any())
        self.assertNotEqual(int(pixels[50,50,0]),int(pixels[-50,-50,0]))
        self.assertEqual(self.source.read_bytes(),original_source)
        for field in ('productionAccepted','clientAccepted','nativeCompiled','installedShaderVerified'):
            self.assertFalse(receipt[field])
        self.assertIn(str(self.recipe),receipt['frozenInputs'])
        self.assertIn(str(self.manifest),receipt['frozenInputs'])

    def test_ao_siblings_are_independent_and_geometry_normal_roughness_equal_legacy(self):
        legacy,old = self.stage_fixture(derived=False)
        prior = None
        for ao in (0,.15,.35):
            receipt,out = self.stage_fixture(ao)
            effective = self.effective(receipt)
            self.check_resources(receipt,out,effective)
            expected = (self.color.astype(float)@np.array([.2126,.7152,.0722])*(1-ao*(1-80/255))).astype('u1')
            np.testing.assert_array_equal(effective['materialRows']['skin']['intensity'],expected)
            self.assertEqual(receipt['untreatedParentSha256'],legacy['untreatedParentSha256'])
            self.assertEqual(receipt['asciiModelSha256'],legacy['asciiModelSha256'])
            self.assertEqual(receipt['rawAttributeAsciiProof'],legacy['rawAttributeAsciiProof'])
            for name in ('pfh0_shinl001.mtr','pfh0_shinl001n.tga','pfh0_shinl001r.tga'):
                self.assertEqual((out/'resources'/name).read_bytes(),(old/'resources'/name).read_bytes())
            if prior is not None:self.assertTrue((expected<=prior).all())
            if ao==.35:
                cumulative=(prior.astype(float)*(1-.35*(1-80/255))).astype('u1')
                self.assertFalse(np.array_equal(expected,cumulative))
            prior=expected

    def test_native_replay_rejects_forged_proof_parent_and_basis(self):
        receipt,_ = self.stage_fixture()
        changes = [('unitFixture',False),('normalPixelsEdited',True),('aoStrength',.35)]
        for key,value in changes:
            bad=deepcopy(receipt);bad['derivedMaterialProof'][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'proof differs'):
                self.effective(bad)
        bad=deepcopy(receipt);bad['untreatedParentSha256']='0'*64
        with self.assertRaisesRegex(ValueError,'untreated source-detail material parent'):
            self.effective(bad)
        for basis in ('original-embedded-maps',None):
            bad=deepcopy(receipt);bad['materialInputBasis']=basis
            with self.subTest(basis=basis),self.assertRaisesRegex(ValueError,'Explicit original-source detail basis'):
                self.effective(bad)
        bad=deepcopy(receipt);bad['derivedMaterialProof']=None
        with self.assertRaisesRegex(ValueError,'cannot fall through'):
            self.effective(bad)

    def test_rehashed_native_plt_normal_and_roughness_corruption_rejects(self):
        receipt,out = self.stage_fixture()
        effective = self.effective(receipt)
        for suffix,pattern in (('.plt','PLT painted shade'),('n.tga','normal pixels'),('r.tga','Roughness transport')):
            path=out/'resources'/('pfh0_shinl001'+suffix);saved=path.read_bytes()
            try:
                if suffix=='.plt':
                    data=bytearray(saved);data[24]^=1;path.write_bytes(data)
                else:
                    pixels=np.asarray(Image.open(path)).copy();pixels[0,0,0]^=1;Image.fromarray(pixels).save(path)
                receipt['materialResourceHashes'][path.name]=c.sha(path)
                with self.subTest(suffix=suffix),self.assertRaisesRegex(ValueError,pattern):
                    self.check_resources(receipt,out,effective)
            finally:path.write_bytes(saved);receipt['materialResourceHashes'][path.name]=c.sha(path)

    def test_legacy_original_embedded_rows_and_historical_missing_basis_stay_compatible(self):
        receipt,out = self.stage_fixture(derived=False)
        for historical in (False,True):
            value=deepcopy(receipt)
            if historical:del value['materialInputBasis']
            effective=self.effective(value)
            self.assertEqual(effective['materialInputBasis'],'original-embedded-maps')
            self.assertFalse(effective['materialColorPixelsEdited'])
            self.assertNotIn('materialIntensityPixelsEdited',effective)
            self.check_resources(value,out,effective)
            np.testing.assert_array_equal(effective['materialRows']['skin']['color'],self.original['skin']['color'])

    def test_malformed_new_mode_fails_before_replay_or_any_output(self):
        malformed = [None,[],{'mode':'foreign'},
            {**self.controls,'mode':'original-source-uv-detail-v2'},
            {**self.controls,'png':'arbitrary.png'},
            {**self.controls,'receipt':{'path':'p','sha256':'A'*64}},
            {**self.controls,'sourceManifest':None}]
        for index,controls in enumerate(malformed):
            value={**self.base,'skinIntensityInputs':controls}
            path=save(self.root/('bad-mode-'+str(index)+'.json'),value)
            out=self.root/('bad-mode-'+str(index))
            with self.subTest(controls=controls),patch.object(replay,'staging_inputs') as worker:
                with self.assertRaises(ValueError):stage.stage(path,out)
                worker.assert_not_called();self.assertFalse(out.exists())


    def test_complete_synthetic_native_audit_records_rgb_only_edit_truthfully(self):
        # Change hue within one PLT shade: the serialized PLT remains original.
        rgb=self.original['skin']['color'].copy();rgb[0,0]=[129,95,70]
        np.testing.assert_array_equal(detail.intensity(rgb,self.original_red,0),self.original['skin']['intensity'])
        with patch.object(type(self),'color',rgb):
            receipt,out=self.stage_fixture()
            stage_path=out/'target-stage.json'
            converted=self.root/('synthetic-native-'+str(self.counter));converted.mkdir()
            shutil.copytree(out/'ascii',converted/'ascii')
            shutil.copytree(out/'resources',converted/'resources')
            model='pfh0_shinl001';ascii_hashes={p.name:c.sha(p) for p in (converted/'ascii').iterdir()}
            p,n,uv,_=replay.raw_corners(self.doc,self.binary);uv=uv.copy();uv[:,:,1]=1-uv[:,:,1]
            native=converted/'resources'/(model+'.mdl');native.write_bytes(native_fixture(model,p,n,uv))
            composition={'schemaVersion':2,'kind':'target-body-composition',**c.binding(self.tp,self.target,'working'),
                'unitFixture':True,'composition':{'sourceReceipts':[{'part':'shinl','path':str(stage_path),'sha256':c.sha(stage_path)}]},
                'asciiModelHashes':ascii_hashes,'materialResourceHashes':receipt['materialResourceHashes'],
                'modelParts':{model+'.mdl':'shinl'},'frozenInputs':{}}
            cp=save(converted/'conversion.json',composition)
            # Synthetic receipts exercise audit plumbing; no compiler is executed.
            client=self.root/'synthetic-not-a-client';client.write_bytes(b'unit fixture only')
            compiled={'complete':True,'executionMode':'compilemodel','interactiveClientLaunched':False,
                'unitFixture':True,'client':str(client),'clientSha256':c.sha(client),
                'materialResourceHashes':receipt['materialResourceHashes'],
                'models':[{'name':native.name,'sourceSha256':ascii_hashes[native.name],
                           'binarySha256':c.sha(native),'bytes':native.stat().st_size}]}
            native_receipt=save(converted/'native-compile.json',compiled)
            layout=self.root/('synthetic-layout-'+str(self.counter));layout.mkdir()
            header=layout/'fixture-layout.h';header.write_bytes(b'synthetic layout fixture')
            config={'schemaVersion':2,'kind':'target-native-part-audit','targetContract':str(self.tp),
                'targetContractSha256':c.sha(self.tp),'part':'shinl','coordinateSpace':'working',
                'stageReceipt':str(stage_path),'stageReceiptSha256':c.sha(stage_path),
                'converted':str(converted),'compositionSha256':c.sha(cp),
                'nativeReceiptSha256':c.sha(native_receipt),'layoutDirectory':str(layout)}
            cfg=save(self.root/('native-audit-'+str(self.counter)+'.json'),config)
            with patch.object(replay,'staging_inputs',side_effect=self.worker),patch.object(audit,'LAYOUT_PINS',{header.name:c.sha(header)}):
                result=audit.audit(cfg,self.root/('native-audit-'+str(self.counter)))
            proof=json.loads(result.read_text(encoding='utf-8'))
        self.assertTrue(proof['materialPixelsEdited'])
        self.assertTrue(proof['materialColorPixelsEdited'])
        self.assertFalse(proof['materialIntensityPixelsEdited'])
        self.assertFalse(proof['originalEmbeddedMapsEdited'])
        self.assertFalse(proof['normalPixelsEdited']);self.assertFalse(proof['roughnessPixelsEdited'])
        self.assertEqual(proof['materialInputBasis'],detail.BASIS)
        self.assertTrue(proof['attributeTransportVerified']);self.assertTrue(proof['materialTransportVerified'])
        self.assertFalse(proof['nativeCompilerExecuted']);self.assertFalse(proof['productionAccepted'])
        self.assertFalse(proof['clientAccepted'])

if __name__=='__main__':unittest.main()