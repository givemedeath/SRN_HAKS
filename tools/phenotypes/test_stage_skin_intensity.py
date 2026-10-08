"""Pinned intensity replay, protected pixels, exact ancestry and native input tests."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

import target_contract as c
import target_skin_lighting_contract as lighting
import skin_lighting_atlas as atlas
import replay_stage_skin_intensity as replay
from place_purposebuilt_pelvis import raw_corners,read_glb,write_glb
from target_part_pipeline import execute
from target_part_stage import stage,stage_controls,material_inputs
from audit_target_native_part import audit_source_inputs,audit_material_resources
import test_target_skin_lighting as lighting_fixture
from test_diagnose_native_cap_normal import fixture as cap_fixture
from diagnose_native_cap_normal import descendant
from test_human_female_stock_exact import stock_fixture


def save(path,value):
    path.write_text(json.dumps(value));return path


def prepare_small_atlas():
    p=np.array([[[0,0,0],[.3,0,0],[0,.3,0]],[[0,0,.5],[.3,0,.5],[0,.3,.5]]])
    uv=np.array([[[.1,.1],[.3,.1],[.1,.3]],[[.6,.6],[.9,.6],[.6,.9]]])
    data={'positions':p,'normals':np.tile([0,0,1],(2,3,1)),'uv':uv,'triangleRoles':['skin']*2,
          'originalIntensity':np.full((64,64),100,dtype='u1'),
          'config':{'protectedRegions':[{'originLocal':[0,0,0],'normalLocal':[0,0,1],
                      'halfWidthMeters':.02,'fadeWidthMeters':.1}],
                    'treatment':{'maxDarkenShades':64,'maxBrightenShades':48}}}
    cfg={'paddingRadiusPixels':3,'maskGuardPixels':2,'positionOverlapToleranceMeters':1e-5,
         'normalOverlapTolerance':1e-4,'requiredZeroSourceFaces':[0]}
    raw=np.repeat(np.linspace(.2,1.2,64)[None,:,None],64,axis=0);raw=np.repeat(raw,3,axis=2).astype('f4')
    samples,weights=lighting.surface_samples(p,uv,data['triangleRoles']);luma=raw.astype(float)@lighting.LUMA
    field=luma/np.average(atlas.sample_texels(luma,samples,True),weights=weights)
    masks=atlas.geometry_masks(p,data['normals'],uv,data['triangleRoles'],64,data['config']['protectedRegions'],2,1e-5,1e-4)
    lineage,dist,dest=atlas.pad_lineage(masks['coverage'],masks['protected']|masks['garment']|masks['ambiguous'],3)
    recorded={**masks,'normalizedLuminance':field.astype('f4'),'paddingSourceTexelIndex':lineage,
              'paddingSteps':dist,'paddingDestination':dest}
    return data,cfg,raw,recorded


class IntensityReplayMathTests(unittest.TestCase):
    def test_full_mask_padding_and_intensity_replay_preserves_joint_and_original(self):
        data,cfg,raw,recorded=prepare_small_atlas();old=data['originalIntensity'].copy()
        derived,masks,_=replay.replay_atlas(data,cfg,raw,recorded,.65)
        np.testing.assert_array_equal(derived[masks['protected']],old[masks['protected']])
        self.assertTrue(np.any(derived!=old));np.testing.assert_array_equal(data['originalIntensity'],old)
        zero,_,_=replay.replay_atlas(data,cfg,raw,recorded,0);np.testing.assert_array_equal(zero,old)
        self.assertTrue(replay.zero_face_proof(data['uv'],[0],masks['influence'],old,derived))

    def test_rehashed_mask_influence_and_padding_corruption_rejected(self):
        data,cfg,raw,recorded=prepare_small_atlas()
        for key in ('influence','protected','normalizedLuminance','paddingSourceTexelIndex'):
            bad={k:v.copy() for k,v in recorded.items()};bad[key].flat[50]=not bad[key].flat[50] if bad[key].dtype==bool else bad[key].flat[50]+1
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'atlas replay differs'):
                replay.replay_atlas(data,cfg,raw,bad,.65)

    def test_whole_bilinear_footprint_detects_boundary_change_away_from_centroid(self):
        uv=np.array([[[.2,.2],[.8,.2],[.2,.8]]]);original=np.full((32,32),100,dtype='u1');derived=original.copy();influence=np.zeros((32,32))
        support=replay.face_filter_footprint(uv[0],32);centroid=atlas.sample_texels(influence,np.array([[.4,.4]]),True)
        self.assertEqual(centroid[0],0);edge=int(support[0]);derived.flat[edge]=99
        with self.assertRaisesRegex(ValueError,'wholly zero-treatment'):replay.zero_face_proof(uv,[0],influence,original,derived)
        derived.flat[edge]=100;influence.flat[edge]=.01
        with self.assertRaisesRegex(ValueError,'wholly zero-treatment'):replay.zero_face_proof(uv,[0],influence,original,derived)
        self.assertIn(0,replay.face_filter_footprint(np.array([[0,0],[.05,0],[0,.05]]),32))
        self.assertIn(31,replay.face_filter_footprint(np.array([[0,0],[.05,0],[0,.05]]),32))

    def test_ao_starts_from_original_fractional_luma_and_treatment_delta_once(self):
        color=np.tile([128,95,72],(2,2,1)).astype('u1');original=(color.astype(float)@lighting.LUMA).astype('u1')
        derived=original.copy();derived[1,1]-=30;red=np.full((2,2),80,dtype='u1')
        for ao in (0,.15,.35):
            expected=((color.astype(float)@lighting.LUMA)*(1-ao*(1-80/255))).astype('u1')
            unt=replay.with_original_ao(color,original,original,red,ao);np.testing.assert_array_equal(unt,expected)
            treated=replay.with_original_ao(color,original,derived,red,ao)
            self.assertEqual(treated[0,0],expected[0,0]);self.assertEqual(treated[1,1],int((float(color[1,1]@lighting.LUMA)-30)*(1-ao*(1-80/255))))
        for bad in (True,.2):
            with self.assertRaises(ValueError):replay.with_original_ao(color,original,derived,red,bad)

    def test_explicit_controls_and_competing_material_paths_rejected(self):
        base={'kind':'target-part-stage','diagnosticOnly':True,'materialRoles':{'0':'skin'},
              'skinIntensityInputs':{'receipt':{'path':'p','sha256':'f'*64},'strength':.65}}
        stage_controls(base)
        for bad in ({'receipt':{},'strength':.65},{'receipt':{'path':'p','sha256':'f'*64},'strength':True},
                    {'receipt':{'path':'p','sha256':'f'*64},'strength':.65,'accepted':True}):
            value={**base,'skinIntensityInputs':bad}
            with self.assertRaises(ValueError):stage_controls(value)
        both={**base,'garmentFaceInputs':{'proposal':{},'review':{}}}
        with self.assertRaises(ValueError):stage_controls(both)


class IntensityGeometryAncestryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();tp,target=stock_fixture(self.root)
        doc,binary=cap_fixture();source=self.root/'source.glb';write_glb(source,doc,binary)
        extra={};p,n,uv,_=raw_corners(doc,binary,extra=extra);t=np.concatenate(extra['TANGENT']['rows'])
        base={'schemaVersion':2,'kind':'target-part-geometry',**c.binding(tp,target,'working'),
              'part':'bicepl','joint':'lbicep_g','model':'pfh0_bicepl001','operation':'fit','candidate':str(source),
              'candidateSha256':c.sha(source),'statureApplications':0,'attachmentWorld':c.frame(target,'lbicep_g','working').tolist(),
              'frozenInputs':{str(source):c.sha(source)}}
        rp=save(self.root/'source-receipt.json',base)
        self.data={'targetPath':tp,'target':target,'source':source,'sourceReceipt':rp,'doc':doc,'binary':binary,
              'config':{'part':'bicepl'},'c1Config':{'requiredZeroSourceFaces':[0]},'normals':n,
              'originalIntensity':np.full((64,64),100,dtype='u1')}
        nd,nb,p,cn,uv,ct,order,proof=descendant(doc,binary,0);child=self.root/'cap.glb';write_glb(child,nd,nb)
        plan={'schemaVersion':2,'kind':'explicit-cap-normal-repair-plan','targetId':target['id'],
              'part':'bicepl','coordinateSpace':'working','sourceFaceId':0,'originalPositionsMetres':p[0].tolist(),
              'oldAuthoredNormals':n[0].tolist(),'proposedGeometricNormalDouble':proof['geometricNormalDouble'],
              'proposedProjectedTangentsDouble':ct[0].tolist()}
        pp=save(self.root/'plan.json',plan)
        cap={**base,'operation':'explicit-cap-normal-corner-exception','candidate':str(child),'candidateSha256':c.sha(child),
             'sourcePart':'bicepl','source':str(source),'sourceSha256':c.sha(source),'sourceReceipt':str(rp),
             'sourceReceiptSha256':c.sha(rp),'repairPlan':replay.file_row(pp),
             'sourceToAttachmentLocal':np.eye(4).tolist(),'reflectionWorld':None}
        self.child=child;self.cap=cap;self.cp=save(self.root/'cap-receipt.json',cap)
        self.masks={'influence':np.zeros((64,64))}

    def tearDown(self):self.tmp.cleanup()

    def invoke(self,child=None,rp=None):
        return replay.geometry_ancestry(child or self.child,rp or self.cp,self.data,self.data['originalIntensity'],self.masks,{},[])

    def test_exact_three_corner_exception_and_opposite_frame_mirror_replay(self):
        _,proof=self.invoke();self.assertEqual(proof['operation'],'explicit-cap-normal-corner-exception')
        self.assertEqual(proof['changedNormalFaces'][0]['originalSourceFaceId'],0)
        config={'schemaVersion':2,'operation':'mirror','part':'bicepr','sourcePart':'bicepl','coordinateSpace':'working',
                'targetContract':str(self.data['targetPath']),'targetContractSha256':c.sha(self.data['targetPath']),
                'source':str(self.child),'sourceSha256':c.sha(self.child),'sourceReceipt':str(self.cp),'sourceReceiptSha256':c.sha(self.cp),
                'planeOriginWorld':[0,0,0],'planeNormalWorld':[1,0,0]}
        cfg=save(self.root/'mirror.json',config);mp=execute(cfg,self.root/'mirror');m=json.loads(mp.read_text())
        _,proof=self.invoke(Path(m['candidate']),mp)
        self.assertTrue(proof['reflectionBetweenDeclaredOppositeFramesExact'])
        self.assertTrue(proof['positionsNormalsUVTangentsWAndMapsReplayed'])
        m['sourceToAttachmentLocal'][0][3]+=.01;save(mp,m)
        with self.assertRaisesRegex(ValueError,'transform differs'):self.invoke(Path(m['candidate']),mp)

    def test_unexplained_rebound_normal_uv_map_and_source_changes_rejected(self):
        original=self.child.read_bytes();doc,binary=read_glb(self.child)
        bad=deepcopy(doc);bad['materials'][0]['name']='changed';write_glb(self.child,bad,binary)
        updated={**self.cap,'candidateSha256':c.sha(self.child)};save(self.cp,updated)
        with self.assertRaisesRegex(ValueError,'binding changed'):self.invoke()
        self.child.write_bytes(original)
        for attribute in ('POSITION','NORMAL','TEXCOORD_0'):
            doc,binary=read_glb(self.child);accessor=doc['accessors'][doc['meshes'][0]['primitives'][0]['attributes'][attribute]]
            view=doc['bufferViews'][accessor['bufferView']];changed=bytearray(binary)
            changed[view.get('byteOffset',0)+accessor.get('byteOffset',0)]^=1
            write_glb(self.child,doc,bytes(changed));save(self.cp,{**self.cap,'candidateSha256':c.sha(self.child)})
            with self.subTest(attribute=attribute),self.assertRaisesRegex(ValueError,'BIN prefix'):self.invoke()
            self.child.write_bytes(original)
        save(self.cp,{**self.cap,'operation':'skin-intensity-applied'})
        with self.assertRaisesRegex(ValueError,'Unexplained'):self.invoke()
        save(self.cp,self.cap);self.masks['influence'][:]=.1
        with self.assertRaisesRegex(ValueError,'wholly zero-treatment'):self.invoke()

    def test_historical_resolution_requires_explicit_saved_helper_and_strict_data_pins(self):
        current=Path(replay.__file__).with_name('target_part_stage.py').resolve();own=self.root/'helpers'/current.name
        own.parent.mkdir();own.write_bytes(b'explicit historical fixture code');digest=c.sha(own)
        rec={'frozenInputs':{str(current):digest,str(own):digest}}
        pins,resolved=replay.frozen_inputs(rec,self.cp);self.assertNotIn(str(current),pins);self.assertEqual(resolved[0]['snapshot']['sha256'],digest)
        del rec['frozenInputs'][str(own)]
        with self.assertRaisesRegex(ValueError,'Missing or ambiguous'):replay.frozen_inputs(rec,self.cp)
        one=self.root/'other/helpers'/current.name;one.parent.mkdir(parents=True);one.write_bytes(own.read_bytes())
        two=self.root/'another/helpers'/current.name;two.parent.mkdir(parents=True);two.write_bytes(own.read_bytes())
        rec['frozenInputs'].update({str(one):digest,str(two):digest})
        with self.assertRaisesRegex(ValueError,'Missing or ambiguous'):replay.frozen_inputs(rec,self.cp)
        rec={'frozenInputs':{str(self.child):'0'*64}}
        with self.assertRaisesRegex(ValueError,'non-helper'):replay.frozen_inputs(rec,self.cp)


class IntensityStagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        f=lighting_fixture.SkinLightingContractTests(methodName='test_prepare_retains_untreated_model_and_maps_without_selection');f.setUp();cls.f=f
        # One genuine generated/fitted triangle has an isolated UV chart; the
        # inherited tetra fixture has overlapping charts that correctly block all treatment.
        doc,binary=read_glb(f.source);doc['accessors'][doc['meshes'][0]['primitives'][0]['indices']]['count']=3
        write_glb(f.source,doc,binary)
        fit_path=f.root/'fit.json';fit=json.loads(fit_path.read_text());job_path=Path(fit['sourceReceipt'])
        job=json.loads(job_path.read_text());job['outputs'][0]['sha256']=c.sha(f.source);save(job_path,job)
        fit.update(sourceSha256=c.sha(f.source),sourceReceiptSha256=c.sha(job_path));save(fit_path,fit)
        fitted=execute(fit_path,f.root/'fitted-isolated-chart');geometry=json.loads(fitted.read_text());f.candidate=Path(geometry['candidate'])
        f.config.update(source=str(f.candidate),sourceSha256=c.sha(f.candidate),sourceReceipt=str(fitted),sourceReceiptSha256=c.sha(fitted))
        review_path=Path(f.config['normalInputReview']['path']);review=json.loads(review_path.read_text());review['source']['sha256']=c.sha(f.source);save(review_path,review)
        f.config['normalInputReview']['sha256']=c.sha(review_path)
        f.config['protectedRegions'][0]['normalLocal']=[1,0,0]
        f.config['treatment']['strengths']=[0,.65];f.path.write_text(json.dumps(f.config));data=lighting.prepare(f.path);cls.data=data
        root=f.root;original=data['originalIntensity'];size=len(original)
        job={'kind':'target-skin-lighting-worker-input','diagnosticOnly':True,**c.binding(data['targetPath'],data['target'],'working'),
             'part':'bicepl','source':{**replay.file_row(data['source']),'byteCount':data['source'].stat().st_size},
             'attachmentWorld':c.frame(data['target'],'lbicep_g','working').tolist(),'materials':{},'primitives':data['primitives'],
             'lighting':data['config']['lighting'],'frozenInputs':data['frozenInputs']}
        arrays=root/'arrays.npz';np.savez_compressed(arrays,**{k:data[k] for k in ('positions','normals','uv','tangents')});job['arrays']=replay.file_row(arrays)
        copies={}
        for mid,entry in data['materials'].items():
            maps={}
            for key,(blob,_) in entry['maps'].items():
                p=root/(str(mid)+'-'+key+'.png');p.write_bytes(blob);maps[key]=replay.file_row(p)
            job['materials'][str(mid)]={'role':entry['role'],'maps':maps};copies[str(mid)]=maps
        jp=save(root/'worker-input.json',job)
        raw=np.tile(np.linspace(.2,1.2,size,dtype='f4')[None,:,None],(size,1,3));raw_path=root/'raw.npz';np.savez_compressed(raw_path,rawLinearRGB=raw)
        worker={'kind':'target-skin-lighting-worker-bake','cpuOnly':True,'cameraUsedForBake':False,
                'input':replay.file_row(jp),'rawBake':replay.file_row(raw_path),'frozenInputs':{str(jp):c.sha(jp)}}
        wp=save(root/'worker.json',worker);ap=root/'parent-atlas.npz';np.savez_compressed(ap,rawLinearRGB=raw)
        lp=save(root/'launch.json',{'tool':'blender','exitCode':0,'frozenInputs':{str(jp):c.sha(jp)}})
        parent={'schemaVersion':2,'kind':'target-skin-lighting-diagnostic',**c.binding(data['targetPath'],data['target'],'working'),
                'part':'bicepl','source':str(data['source']),'sourceSha256':c.sha(data['source']),
                'sourceReceipt':str(data['sourceReceipt']),'sourceReceiptSha256':c.sha(data['sourceReceipt']),
                'untreatedParentSha256':c.sha(data['source']),'normalStrength':1,'lighting':data['config']['lighting'],
                'workerReceipts':{'bake':replay.file_row(wp)},'workerLaunchReceipts':{'bake':replay.file_row(lp)},
                'originalMapCopies':copies,'lightingAtlas':replay.file_row(ap),'frozenInputs':data['frozenInputs'],
                'originalIntensityArraySha256':hashlib.sha256(original.tobytes()).hexdigest()}
        pp=save(root/'parent.json',parent)
        cfg={'schemaVersion':1,'kind':'target-skin-lighting-c1-padding-diagnostic','diagnosticOnly':True,
             'sourceConfig':replay.file_row(f.path),'parentLighting':replay.file_row(pp),'paddingRadiusPixels':2,'maskGuardPixels':2,
             'positionOverlapToleranceMeters':1e-5,'normalOverlapTolerance':1e-4,'requiredZeroSourceFaces':[]}
        cp=save(root/'c1-config.json',cfg)
        samples,weights=lighting.surface_samples(data['positions'],data['uv'],data['triangleRoles']);luma=raw.astype(float)@lighting.LUMA
        mean=float(np.average(atlas.sample_texels(luma,samples,True),weights=weights));field=luma/mean
        masks=atlas.geometry_masks(data['positions'],data['normals'],data['uv'],data['triangleRoles'],size,data['config']['protectedRegions'],2,1e-5,1e-4)
        forbidden=masks['protected']|masks['garment']|masks['ambiguous'];lineage,dist,dest=atlas.pad_lineage(masks['coverage'],forbidden,2)
        npz=root/'c1-atlas.npz';np.savez_compressed(npz,**masks,normalizedLuminance=field.astype('f4'),paddingSourceTexelIndex=lineage,paddingSteps=dist,paddingDestination=dest)
        variants=[]
        for strength in (0,.65):
            value=lighting.compose(original,field,masks['influence'],masks['garment'],masks['protected']|masks['ambiguous'],strength,64,48)
            value=atlas.apply_padding(original,value,lineage,dest,strength);path=root/('intensity-'+str(strength)+'.png');Image.fromarray(value).save(path)
            variants.append({'strength':strength,'intensity':replay.file_row(path),'untreatedParentSha256':c.sha(data['source'])})
        receipt={'schemaVersion':2,'kind':'target-skin-lighting-c1-padding-diagnostic',**c.binding(data['targetPath'],data['target'],'working'),
            'part':'bicepl','source':str(data['source']),'sourceSha256':c.sha(data['source']),'sourceReceipt':str(data['sourceReceipt']),
            'sourceReceiptSha256':c.sha(data['sourceReceipt']),'config':replay.file_row(cp),'parentLighting':replay.file_row(pp),
            'maskAndPaddingLineage':replay.file_row(npz),'normalizationMean':mean,'variants':variants,'frozenInputs':data['frozenInputs']}
        cls.rp=save(root/'c1.json',receipt);cls.receipt=receipt;cls.masks=masks
        cls.base={'schemaVersion':2,'kind':'target-part-stage','diagnosticOnly':True,'part':'bicepl','coordinateSpace':'working',
            'targetContract':str(data['targetPath']),'targetContractSha256':c.sha(data['targetPath']),
            'source':str(data['source']),'sourceSha256':c.sha(data['source']),'sourceReceipt':str(data['sourceReceipt']),
            'sourceReceiptSha256':c.sha(data['sourceReceipt']),'materialRoles':{'0':'skin'},'aoStrength':0}
        cls.counter=0

    @classmethod
    def tearDownClass(cls):cls.f.tearDown()

    def setUp(self):
        save(self.rp,self.receipt)

    def config(self,strength=.65):
        return {**self.base,'skinIntensityInputs':{'receipt':replay.file_row(self.rp),'strength':strength}}

    def invoke(self,value=None):
        value=value or self.config()
        return replay.staging_inputs(value['skinIntensityInputs'],self.data['targetPath'],self.data['target'],
            value['part'],value['coordinateSpace'],Path(value['source']),Path(value['sourceReceipt']),
            {int(k):v for k,v in value['materialRoles'].items()},value['aoStrength'])

    def test_actual_stage_plt_and_auditor_replay_with_exact_original_normal_roughness(self):
        config=self.config();path=save(self.f.root/'new-stage.json',config);out=self.f.root/'new-stage';rp=stage(path,out);receipt=json.loads(rp.read_text())
        self.assertEqual(receipt['materialInputBasis'],replay.BASIS);self.assertFalse(receipt['productionAccepted'])
        effective=audit_source_inputs(receipt,Path(config['source']),Path(config['sourceReceipt']),self.data['targetPath'],self.data['target'],'bicepl','working')
        self.assertTrue(effective['materialIntensityPixelsEdited']);self.assertFalse(effective['materialColorPixelsEdited'])
        proof,_=audit_material_resources(out/'resources','pfh0_bicepl001','skin',effective['materialRows']['skin'],
                                         {'materialResourceHashes':receipt['materialResourceHashes']})
        self.assertTrue(proof['normalPixelsExact']);self.assertTrue(proof['roughnessPixelsExact'])
        bad=deepcopy(receipt);bad['derivedMaterialProof']['protectedOriginalPixelsExact']=False
        with self.assertRaisesRegex(ValueError,'proof differs'):audit_source_inputs(bad,Path(config['source']),Path(config['sourceReceipt']),self.data['targetPath'],self.data['target'],'bicepl','working')
        plt=out/'resources/pfh0_bicepl001.plt';content=bytearray(plt.read_bytes());content[24]^=1;plt.write_bytes(content)
        with self.assertRaisesRegex(ValueError,'PLT painted shade'):audit_material_resources(out/'resources','pfh0_bicepl001','skin',effective['materialRows']['skin'],{'materialResourceHashes':receipt['materialResourceHashes']})

    def test_strength_zero_keeps_legacy_ascii_and_every_material_resource_byte_exact(self):
        legacy=save(self.f.root/'legacy.json',self.base);old=stage(legacy,self.f.root/'legacy')
        config=save(self.f.root/'zero.json',self.config(0));new=stage(config,self.f.root/'zero')
        a=json.loads(old.read_text());b=json.loads(new.read_text());self.assertEqual(a['materialResourceHashes'],b['materialResourceHashes'])
        self.assertEqual(a['asciiModelSha256'],b['asciiModelSha256']);self.assertEqual(a['rawAttributeAsciiProof'],b['rawAttributeAsciiProof'])

    def test_rehashed_intensity_with_protected_pixel_edit_cannot_pass(self):
        entry=self.receipt['variants'][1];path=Path(entry['intensity']['path']);old=path.read_bytes()
        pixels=np.asarray(Image.open(path)).copy();index=np.argwhere(self.masks['protected'])[0];pixels[tuple(index)]^=1;Image.fromarray(pixels).save(path)
        changed=deepcopy(self.receipt);changed['variants'][1]['intensity']=replay.file_row(path);save(self.rp,changed)
        try:
            with self.assertRaisesRegex(ValueError,'pixels differ'):self.invoke()
        finally:path.write_bytes(old)

    def test_strength_roles_garment_target_parent_and_repeated_treatment_fail_closed(self):
        for update in ({'part':'chest'},{'coordinateSpace':'runtime'},{'materialRoles':{'0':'garment'}},{'aoStrength':.2}):
            cfg=self.config();cfg.update(update)
            with self.subTest(update=update),self.assertRaises(ValueError):self.invoke(cfg)
        cfg=self.config(.4)
        with self.assertRaisesRegex(ValueError,'unique declared'):self.invoke(cfg)
        changed=deepcopy(self.receipt);changed['targetId']='other';save(self.rp,changed)
        with self.assertRaisesRegex(ValueError,'another target'):self.invoke()
        changed=deepcopy(self.receipt);changed['variants'][1]['untreatedParentSha256']='0'*64;save(self.rp,changed)
        with self.assertRaisesRegex(ValueError,'AO/lighting parent'):self.invoke()
        changed=deepcopy(self.receipt);changed['kind']=replay.KIND;save(self.rp,changed)
        with self.assertRaisesRegex(ValueError,'repeated treatment'):self.invoke()
        save(self.rp,self.receipt);cfg=self.config();cfg['skinIntensityInputs']['receipt']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Frozen input'):self.invoke(cfg)


if __name__=='__main__':unittest.main()
