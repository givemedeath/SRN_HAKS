"""Shared UV per-face ownership preserves originals and reviews derived boundaries."""
import copy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

import target_contract as c
from place_purposebuilt_pelvis import raw_corners,read_glb,write_glb
from target_garment_face_ownership import BIND_FIELDS,proposal,reviewed_staging_inputs
from target_garment_ownership import measure_uv_faces
from target_part_pipeline import execute
from target_part_stage import image_pixels,material_inputs,stage
from test_human_female_stock_exact import stock_fixture
from test_target_garment_ownership import two_faces


def shared_uv_fixture():
    doc,binary=two_faces();blob=bytearray(binary);primitive=doc['meshes'][0]['primitives'][0]
    def replace(name,values):
        acc=doc['accessors'][primitive['attributes'][name]];view=doc['bufferViews'][acc['bufferView']]
        start=view.get('byteOffset',0)+acc.get('byteOffset',0);data=np.asarray(values,dtype='<f4').tobytes();blob[start:start+len(data)]=data
    replace('POSITION',[[0,0,0],[.1,0,0],[.1,.1,0],[.1,0,0],[.2,.1,0],[.1,.1,0]])
    replace('TEXCOORD_0',[[.45,.45],[.5,.45],[.5,.55],[.5,.45],[.55,.55],[.5,.55]])
    color=np.empty((2048,2048,3),np.uint8);color[:,:1024]=[180,100,65];color[:,1024:]=[31,43,40]
    stream=BytesIO();Image.fromarray(color).save(stream,format='PNG');data=stream.getvalue();blob.extend(b'\0'*(-len(blob)%4));start=len(blob);blob.extend(data)
    doc['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':len(data)});doc['images'].append({'bufferView':len(doc['bufferViews'])-1,'mimeType':'image/png'});doc['textures'].append({'source':len(doc['images'])-1})
    doc['materials'][0]['pbrMetallicRoughness']['baseColorTexture']['index']=len(doc['textures'])-1
    blob.extend(b'\0'*(-len(blob)%4));doc['buffers'][0]['byteLength']=len(blob)
    return doc,bytes(blob)


class FaceGarmentOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.tp,self.target=stock_fixture(self.root)
        raw=self.root/'raw.glb';write_glb(raw,*shared_uv_fixture());job=self.root/'job.json';job.write_text(json.dumps({'state':'success','promptId':'fixture','outputs':[{'localPath':str(raw),'sha256':c.sha(raw)}]}))
        fit={'schemaVersion':2,'operation':'fit','part':'chest','coordinateSpace':'working','targetContract':str(self.tp),'targetContractSha256':c.sha(self.tp),'source':str(raw),'sourceSha256':c.sha(raw),'sourceReceipt':str(job),'sourceReceiptSha256':c.sha(job),'uniformScale':.7,'rotationDegreesXYZ':[3,4,5],'sourceAnchorNwn':[0,0,0],'targetAnchorLocal':[0,0,0]}
        cfg=self.root/'fit.json';cfg.write_text(json.dumps(fit));self.rp=execute(cfg,self.root/'fit');self.parent=json.loads(self.rp.read_text());self.source=Path(self.parent['candidate'])
        self.identity={**c.binding(self.tp,self.target,'working'),'part':'chest','model':c.model(self.target,'chest'),'source':str(self.source),'sourceSha256':c.sha(self.source),'sourceReceipt':str(self.rp),'sourceReceiptSha256':c.sha(self.rp)}
        self.dp=self.root/'decisions.json';self.decs={'schemaVersion':2,'kind':'target-garment-face-decisions',**self.identity,'sourceFaceIds':[0,1],'faceRoles':['skin','garment'],'accepted':False};self.dp.write_text(json.dumps(self.decs))
        self.mask=self.root/'mask.png';mask=np.zeros((2048,2048),np.uint8);mask[:,1024:]=255;Image.fromarray(mask).save(self.mask)
        self.cfg={'schemaVersion':2,'kind':'target-garment-face-proposal','diagnosticOnly':True,'targetContract':str(self.tp),'targetContractSha256':c.sha(self.tp),'part':'chest','coordinateSpace':'working','source':str(self.source),'sourceSha256':c.sha(self.source),'sourceReceipt':str(self.rp),'sourceReceiptSha256':c.sha(self.rp),'faceDecisions':{'path':str(self.dp),'sha256':c.sha(self.dp)},'ownershipMask':{'path':str(self.mask),'sha256':c.sha(self.mask)},'padding':{'radiusPixels':4},'knownSourceGarmentDefects':[]}

    def tearDown(self):self.tmp.cleanup()

    def propose(self,name='proposed',overrides=None):
        config=copy.deepcopy(self.cfg)
        if overrides:config.update(overrides)
        path=self.root/(name+'.json');path.write_text(json.dumps(config));pp=proposal(path,self.root/name);return pp,json.loads(pp.read_text())

    def review(self,pp,proposed,name='review'):
        value={key:proposed[key] for key in BIND_FIELDS};evidence=[]
        for palette in (3,8):
            image=self.root/(name+'-palette'+str(palette)+'.png');Image.new('RGB',(4,4),(palette,40,70)).save(image)
            evidence.append({'palette':palette,'basis':'native-material-preview','view':'garment-edges','proposalSha256':c.sha(pp),'path':str(image),'sha256':c.sha(image)})
        value.update(schemaVersion=2,kind='target-garment-face-review',proposalReceipt={'path':str(pp),'sha256':c.sha(pp)},sourceFaceIds=proposed['sourceFaceIds'],faceRoles=proposed['faceRoles'],accepted=True,decision='approved-face-ownership-and-material-inputs',reviewer='explicit test review fixture',notes='Protocol fixture; no real body approval.',garmentDesignReviewed=True,reviewedViews=['front','rear','side','uv-boundary'],boundaryReview={'sourceFaceIds':[row['sourceFace'] for row in proposed['measuredAmbiguousFaces']],'decision':'reviewed-per-face-boundary','notes':'These exact shared UV faces and proposed role copies are reviewed in this fixture.'},paletteEdgeEvidence=evidence)
        rp=self.root/(name+'.json');rp.write_text(json.dumps(value));return rp,value

    def inputs(self,pp,rp,strength=0):
        return reviewed_staging_inputs(pp,rp,self.tp,self.target,'chest','working',self.source,self.rp,strength)

    def test_shared_uv_can_propose_separate_role_copies_without_legacy_waiver(self):
        doc,binary=read_glb(self.source);p,n,uv,_=raw_corners(doc,binary);mask=np.asarray(Image.open(self.mask))
        legacy_roles,_,issues=measure_uv_faces(uv,mask,1);self.assertEqual(legacy_roles,['unknown','unknown'])
        pp,pr=self.propose();self.assertFalse(pr['accepted']);self.assertTrue(pr['completeFaceDecisions']);self.assertTrue(pr['paddingResolved']);self.assertEqual(len(pr['measuredAmbiguousFaces']),2)
        self.assertEqual(pr['faceRoles'],['skin','garment']);self.assertTrue(all(row['changedColorTexels']>0 for row in pr['paddingProof'].values()))
        for role,expected in [('skin',[180,100,65]),('garment',[31,43,40])]:
            color=np.asarray(Image.open(pr['derivedCompilerInputs'][role]['baseColor']['path']));support=np.asarray(Image.open(pr['derivedCompilerInputs'][role]['sampledSupport']['path']))!=0
            self.assertTrue(np.all(color[support]==expected));self.assertTrue(pr['paddingProof'][role]['outsideRoleSupportPixelsUnchanged']);self.assertLessEqual(pr['paddingProof'][role]['maximumCopyDistancePixels'],4)
        pending=json.loads((pp.parent/'pending-review-template.json').read_text());self.assertFalse(pending['accepted']);self.assertEqual(pending['paletteEdgeEvidence'],[])
        cfg=json.loads((pp.parent/'pending-stage-interface.json').read_text());self.assertEqual(cfg['kind'],'target-part-stage-reviewed-garment-inputs')
        cfgpath=self.root/'wrong-stage.json';cfgpath.write_text(json.dumps(cfg))
        with self.assertRaisesRegex(ValueError,'diagnostic stage'):stage(cfgpath,self.root/'should-not-stage')
        self.assertEqual(c.sha(self.source),self.parent['candidateSha256'])

    def test_reviewed_adapter_preserves_bin_all_corner_attributes_maps_normal_roughness(self):
        doc,binary=read_glb(self.source);before=raw_corners(doc,binary,extra={});pp,pr=self.propose();rp,_=self.review(pp,pr);result=self.inputs(pp,rp)
        self.assertEqual(result['binary'],binary);after=raw_corners(result['document'],result['binary'],extra={})
        for a,b in zip(before[:3],after[:3]):np.testing.assert_array_equal(a,b)
        original_count=len(doc['accessors']);self.assertEqual(result['document']['accessors'][:original_count],doc['accessors']);self.assertEqual(result['document']['images'],doc['images']);self.assertEqual(result['document']['textures'],doc['textures'])
        self.assertEqual(result['faceRoles'],['skin','garment']);self.assertEqual(len(result['materialRoles']),2)
        original,_=material_inputs(doc,binary,{0:'skin'},'chest',0,{'chest','pelvis'})
        for row in result['materialRows'].values():
            np.testing.assert_array_equal(row['normal'],original['skin']['normal']);np.testing.assert_array_equal(row['roughness'],original['skin']['roughness'])
        self.assertFalse(result['proof']['productionAccepted']);self.assertTrue(result['proof']['normalPixelsExact'])
        # TANGENT, COLOR_0, NORMAL lengths, signs and all original binary bytes survive.
        self.assertEqual(result['document']['meshes'][0]['primitives'][0]['attributes'],doc['meshes'][0]['primitives'][0]['attributes'])

    def test_ao_variants_use_same_derived_parent_and_exact_original_roughness(self):
        pp,pr=self.propose();rp,_=self.review(pp,pr);a=self.inputs(pp,rp,0);b=self.inputs(pp,rp,.15);d=self.inputs(pp,rp,.35)
        for role in ('skin','garment'):
            np.testing.assert_array_equal(a['materialRows'][role]['color'],b['materialRows'][role]['color']);np.testing.assert_array_equal(a['materialRows'][role]['normal'],d['materialRows'][role]['normal']);np.testing.assert_array_equal(a['materialRows'][role]['roughness'],d['materialRows'][role]['roughness'])
        expected=np.asarray(Image.open(pr['derivedCompilerInputs']['skin']['pltIntensityAO0']['path']))
        np.testing.assert_array_equal(expected,a['materialRows']['skin']['intensity'])
        factor=1-.35*(1-80/255);color=a['materialRows']['skin']['color'].astype(float);intensity=(color@np.asarray([.2126,.7152,.0722])*factor).astype(np.uint8)
        np.testing.assert_array_equal(intensity,d['materialRows']['skin']['intensity'])

    def test_unknown_decisions_and_unresolved_padding_stay_diagnostic(self):
        self.decs['faceRoles'][1]='unknown';self.dp.write_text(json.dumps(self.decs));self.cfg['faceDecisions']['sha256']=c.sha(self.dp)
        pp,pr=self.propose();self.assertFalse(pr['completeFaceDecisions']);rp,_=self.review(pp,pr)
        with self.assertRaisesRegex(ValueError,'Complete explicit'):self.inputs(pp,rp)
        # Explicit zero correction radius leaves shared UV edge support unresolved.
        self.decs['faceRoles'][1]='garment';self.dp.write_text(json.dumps(self.decs));self.cfg['faceDecisions']['sha256']=c.sha(self.dp)
        pp,pr=self.propose('no-padding',{'padding':{'radiusPixels':0}});self.assertFalse(pr['paddingResolved']);rp,_=self.review(pp,pr,'review-no-padding')
        with self.assertRaisesRegex(ValueError,'resolved bounded'):self.inputs(pp,rp)

    def test_source_garment_defects_cannot_be_relabelled_accepted(self):
        pp,pr=self.propose(overrides={'knownSourceGarmentDefects':['Four rear straps instead of approved two.']});rp,_=self.review(pp,pr)
        with self.assertRaisesRegex(ValueError,'revised source'):self.inputs(pp,rp)

    def test_cross_target_part_face_inventory_and_padding_types_reject(self):
        for field,value in [('sourceSha256','f'*64),('targetId','other'),('part','pelvis')]:
            bad=copy.deepcopy(self.decs);bad[field]=value;self.dp.write_text(json.dumps(bad));cfg=copy.deepcopy(self.cfg);cfg['faceDecisions']['sha256']=c.sha(self.dp)
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'another source'):self.propose('bad-'+field,cfg)
        self.dp.write_text(json.dumps(self.decs));self.cfg['faceDecisions']['sha256']=c.sha(self.dp)
        for ids in ([1,0],[0,0],[0], [False,1]):
            bad=copy.deepcopy(self.decs);bad['sourceFaceIds']=ids;self.dp.write_text(json.dumps(bad));self.cfg['faceDecisions']['sha256']=c.sha(self.dp)
            with self.subTest(ids=ids),self.assertRaisesRegex(ValueError,'exactly once'):self.propose('bad-ids'+str(len(ids)))
        self.dp.write_text(json.dumps(self.decs));self.cfg['faceDecisions']['sha256']=c.sha(self.dp)
        for radius in (True,-1,1.5,17):
            with self.subTest(radius=radius),self.assertRaisesRegex(ValueError,'bounded'):self.propose('bad-radius'+str(radius),{'padding':{'radiusPixels':radius}})
        with self.assertRaisesRegex(ValueError,'chest/pelvis'):self.propose('other-part',{'part':'handl'})

    def test_missing_or_stale_palette_edge_evidence_and_boundary_decisions_reject(self):
        pp,pr=self.propose();rp,review=self.review(pp,pr)
        for change in ('palette8','proposal','boundary','roles','views'):
            bad=copy.deepcopy(review)
            if change=='palette8':bad['paletteEdgeEvidence']=bad['paletteEdgeEvidence'][:1]
            if change=='proposal':bad['proposalReceipt']['sha256']='f'*64
            if change=='boundary':bad['boundaryReview']['sourceFaceIds']=[]
            if change=='roles':bad['faceRoles']=['garment','skin']
            if change=='views':bad['reviewedViews']=[]
            rp.write_text(json.dumps(bad))
            with self.subTest(change=change),self.assertRaises(ValueError):self.inputs(pp,rp)
        rp.write_text(json.dumps(review));Path(review['paletteEdgeEvidence'][0]['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Frozen input'):self.inputs(pp,rp)

    def test_rehashed_derived_pixels_cannot_forge_bounded_padding_proof(self):
        pp,pr=self.propose();color=Path(pr['derivedCompilerInputs']['skin']['baseColor']['path'])
        altered=np.asarray(Image.open(color)).copy();altered[0,0]=[9,9,9];Image.fromarray(altered).save(color)
        # A newly signed review of edited JSON must still independently
        # reproduce every derived pixel from the original bounded operation.
        pr['derivedCompilerInputs']['skin']['baseColor']['sha256']=c.sha(color);pr['outputHashes'][str(color)]=c.sha(color);pp.write_text(json.dumps(pr))
        rp,_=self.review(pp,pr)
        with self.assertRaisesRegex(ValueError,'measured original-pixel padding'):self.inputs(pp,rp)
    def test_stale_source_and_derived_map_reject_without_stage_or_geometry_output(self):
        pp,pr=self.propose();rp,_=self.review(pp,pr);color=Path(pr['derivedCompilerInputs']['skin']['baseColor']['path']);Image.new('RGB',(2048,2048),(9,9,9)).save(color)
        with self.assertRaisesRegex(ValueError,'Frozen input'):self.inputs(pp,rp)
        self.assertFalse((pp.parent/'candidate-local.glb').exists())
        self.source.write_bytes(self.source.read_bytes()+b'changed')
        with self.assertRaises(ValueError):self.inputs(pp,rp)


if __name__=='__main__':unittest.main()

