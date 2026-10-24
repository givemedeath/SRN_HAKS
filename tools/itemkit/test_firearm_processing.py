import copy
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
from tools.headkit.common import pin, read, write
from . import contracts
from .firearm_intake import intake_pistol
from .runner import Runner
from .parts import active_parts, assembly_budget, firearm_views, FIREARM_VIEWS
from .firearm_grip import measured_fit, GripDeparture


class FirearmProcessingTests(unittest.TestCase):
    def setUp(self):
        self.standard={'id':'cougar-approved-grip-v1','approval':{'gripSizingApproved':True},
            'usableLength':.18,'targetMidpointSection':{'depth':.03,'visibleFaceWidth':.05},
            'referenceSections':[{'fractionFromPommel':n} for n in (.1,.25,.5,.75,.9)]}
        self.p=np.array([[x,y,z] for x in (-.015,.015) for y in (-.09,.09) for z in (-.025,.025)])
        self.f=np.array([[0,1,3],[0,3,2],[4,6,7],[4,7,5],[0,4,5],[0,5,1],
                         [2,3,7],[2,7,6],[0,2,6],[0,6,4],[1,5,7],[1,7,3]])
        angle=.35;c,s=np.cos(angle),np.sin(angle)
        matrix=np.eye(4);matrix[:3,:3]=[[1,0,0],[0,c,-s],[0,s,c]];matrix[:3,3]=[.01,-.02,.03]
        self.config={'reviewed':True,'sourceSha256':'donor','workingSourceSha256':'working',
                     'matrix':matrix.tolist(),'gripEndpoints':[[0,-.09,0],[0,.09,0]],
                     'nativeGripDepthAxis':[1,0,0],'gripSurfaceFaces':list(range(12))}
        self.origin=matrix[:3,3]
        self.profile={'family':'firearm-sling','firearm':{'subtype':'pistol'},
                      'budgets':{'visible':10000,'shadow':500,'parts':{
                          'b':{'visible':9992,'shadow':500},'m':{'visible':4,'shadow':0},'t':{'visible':4,'shadow':0}}}}

    def fit(self):
        return measured_fit(self.p,self.f,self.config,'donor','working',self.standard,self.origin)

    def test_tilted_grip_preserves_uniform_transform_and_measures_five_sections(self):
        matrix,report=self.fit()
        np.testing.assert_array_equal(matrix,self.config['matrix'])
        self.assertEqual(len(report['measuredFittedSections']),5)
        np.testing.assert_allclose(report['nativeGripAxis'],matrix[:3,1])
        for row in report['measuredFittedSections']:
            self.assertAlmostEqual(row['depth'],.03);self.assertAlmostEqual(row['visibleFaceWidth'],.05)
        a=np.array([0,1,0]);b=np.array([0,1,2])/np.sqrt(5)
        self.assertAlmostEqual(np.dot(a,b),np.dot(matrix[:3,:3]@a,matrix[:3,:3]@b))

    def test_grip_selection_excludes_barrel_sections(self):
        self.p=np.r_[self.p,self.p+[0,0,.25]];self.f=np.r_[self.f,self.f+8]
        _,report=self.fit()
        self.assertAlmostEqual(report['measuredFittedSections'][2]['visibleFaceWidth'],.05)

    def test_firearm_standard_keeps_measurement_and_approval_gates(self):
        self.standard['id']='colt-l36-approved-firearm-grip-v1'
        self.assertEqual(self.fit()[1]['reference'],self.standard['id'])
        self.standard['usableLength']*=1.15
        with self.assertRaisesRegex(ValueError,'usable grip length'):self.fit()
        self.standard['usableLength']/=1.15
        self.standard['approval']['gripSizingApproved']=False
        with self.assertRaisesRegex(ValueError,'Approved grip'):self.fit()
        self.standard['approval']['gripSizingApproved']=True
        self.standard['id']='unreviewed-standard'
        with self.assertRaisesRegex(ValueError,'Approved grip'):self.fit()

    def test_width_departure_requires_exact_measurement_review(self):
        self.p[:,2]*=2
        with self.assertRaises(GripDeparture) as caught:self.fit()
        report=caught.exception.report
        self.config['gripDeparture']={'decision':'approved','measurementDigest':report['measurementDigest'],'notes':'Synthetic departure check'}
        self.assertIn('departureReview',self.fit()[1])
        self.p[:,2]*=1.1
        with self.assertRaises(GripDeparture):self.fit()

    def test_stale_surface_binding_and_bad_selections_fail(self):
        self.config['workingSourceSha256']='changed'
        with self.assertRaisesRegex(ValueError,'another working mesh'):self.fit()
        self.config['workingSourceSha256']='working';self.config['gripSurfaceFaces']=[0,0,1,2]
        with self.assertRaisesRegex(ValueError,'Unique'):self.fit()

    def test_wrong_hand_origin_and_nonuniform_fit_fail(self):
        self.origin=self.origin+[0,.01,0]
        with self.assertRaisesRegex(ValueError,'native hand'):self.fit()
        self.origin=self.origin-[0,.01,0];self.config['matrix'][0][0]=2
        with self.assertRaisesRegex(ValueError,'uniform similarity'):self.fit()

    def test_active_slots_and_full_budget_include_hidden_placeholders(self):
        self.assertEqual(active_parts(self.profile),('b',))
        self.assertEqual(active_parts({'family':'dagger'}),('b','m','t'))
        self.assertEqual(assembly_budget(self.profile,{'b':9992},'visible')['assembly'],10000)
        self.assertEqual(assembly_budget(self.profile,{'b':500},'shadow')['assembly'],500)
        with self.assertRaises(ValueError):assembly_budget(self.profile,{'b':9993},'visible')
        with self.assertRaises(ValueError):assembly_budget(self.profile,{'b':0},'visible')
        with self.assertRaises(ValueError):assembly_budget(self.profile,{'b':500,'m':0},'shadow')

    def test_eight_explicit_views_and_nondegenerate_camera_frames(self):
        views={name:{'direction':[1,0,0],'target':[0,0,0],'up':[0,1,0],'scale':1.1} for name in FIREARM_VIEWS}
        self.assertEqual(tuple(firearm_views(views)),FIREARM_VIEWS)
        bad=copy.deepcopy(views);bad['grip']['up']=[1,0,0]
        with self.assertRaisesRegex(ValueError,'Nondegenerate'):firearm_views(bad)
        del views['muzzle']
        with self.assertRaisesRegex(ValueError,'Eight'):firearm_views(views)

    def test_enabled_pistol_requires_its_own_verified_sling_donors_and_exact_assembly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);reference=root/'ref.png';Image.new('RGB',(512,512)).save(reference)
            intake_pistol(reference,root/'asset','synthetic-pistol')
            profile_path=root/'asset/family.json';manifest_path=root/'asset/asset.json'
            profile=read(profile_path);manifest=read(manifest_path);layer=root/'asset/stock';layer.mkdir()
            table=layer/'baseitems.2da'
            table.write_text('2DA V2.0\n\nlabel ItemClass ModelType MinRange MaxRange InvSlotWidth InvSlotHeight\n61 Sling WBwSl 0 0 50 1 2\n')
            (layer/'wbwsl_011.mdl').write_bytes(b'synthetic donor')
            Image.new('RGBA',(32,64)).save(layer/'iwbwsl_011.tga')
            stack=root/'asset/stack.json'
            write(stack,{'complete':True,'order':'low-to-high','layers':[{'resources':[
                {'resource':p.name,'file':{'path':'stock/'+p.name,'sha256':pin(p)['sha256']}} for p in sorted(layer.iterdir())]}]})
            profile['nativePackaging']='enabled'
            profile['native']={'reviewed':True,'stack':{'path':'stack.json','sha256':pin(stack)['sha256']},
                'baseItem':61,'itemClass':'wbwsl','modelType':0,'packagedModelType':2,'baseitemsSha256':pin(table)['sha256'],
                'donors':{'whole':'wbwsl_011.mdl','icon':'iwbwsl_011.tga'},'frame':np.eye(3).tolist(),
                'gripOrigin':[0,0,0],'gripLength':.18,'iconDimensions':{'b':[32,64]}}
            def save():
                write(profile_path,profile);manifest['familyProfile']['sha256']=pin(profile_path)['sha256'];write(manifest_path,manifest)
            save();self.assertEqual(contracts.manifest(manifest_path)['id'],'synthetic-pistol')
            with self.assertRaisesRegex(ValueError,'assembly allocator'):contracts.model_names(profile,5)
            profile['allowedAssemblies'][0]['m']='synthetic-pistol';save()
            with self.assertRaisesRegex(ValueError,'one declared'):contracts.manifest(manifest_path)
            profile['allowedAssemblies'][0]['m']='hidden-placeholder'
            profile['native']['packagedModelType']=0;save()
            with self.assertRaisesRegex(ValueError,'private Sling'):contracts.family(profile_path)
            profile['native']['packagedModelType']=2;save()
            (layer/'wbwsl_011.mdl').write_bytes(b'changed donor')
            with self.assertRaises(ValueError):contracts.family(profile_path)

    def test_runner_exports_one_variant_without_entering_melee_native_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);profile=folder/'profile.json';write(profile,self.profile)
            runner=Runner.__new__(Runner);runner.family=self.profile;runner.profile_path=profile
            runner.family['runtimeTextureSize']=1024
            result={'shadow':{'scene':{'path':'scene'}},'render':{'icons':{'b':{'path':'icon','sha256':'bound'}}},
                    'bake':{'maps':{'1024':{'path':'texture','sha256':'bound'}}}}
            with patch.object(runner,'result',side_effect=lambda stage, **kwargs:result[stage]), \
                 patch.object(runner,'worker',return_value={'parts':{'b':{'path':'arrays','sha256':'bound'}}}):
                exported=runner._execute('export',folder)
            self.assertEqual(exported['slot'],'b');self.assertEqual(exported['kind'],'firearm-processed-variant')
            with self.assertRaisesRegex(ValueError,'firearm-prepare'):runner._execute('native',folder)


if __name__=='__main__':unittest.main()
