"""Dagger identity, operation-local verification and calibrated grip regressions."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from tools.headkit.common import pin,write,read,digest
from tools.itemkit.verification import VerificationPass
from tools.itemkit.runner import Runner
from tools.itemkit.test_itemkit import Fixture
from tools.itemkit import contracts
from tools.itemkit.__main__ import intake
from tools.itemkit.grip import affine_corners,calibration,section_dimensions
from tools.itemkit.fixture import blueprint


class VerificationTests(unittest.TestCase):
    def test_render_dependency_lookups_share_one_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);r=Runner.__new__(Runner);r.data={};r.local={};r.runtime=None
            r.family={'runtimeTextureSize':1024};r.state={'stages':{},'reviews':{}}
            for stage,parents,result in [('a',[],{}),('bake',['a'],{'maps':{'1024':{'path':'texture'}}}),
                                         ('shadow',['bake'],{'scene':{'path':'scene'}})]:
                p=root/(stage+'.json');write(p,{'state':'complete','manifestHash':digest({}),'bindingsHash':digest({}),
                    'codeVersion':'version','inputs':[],'outputs':[],'dependencies':{k:r.state['stages'][k] for k in parents},'result':result})
                r.state['stages'][stage]=pin(p);q=root/(stage+'-review.json')
                write(q,{'stageReceipt':pin(p),'decision':'approved'});r.state['reviews'][stage]=pin(q)
            with patch('tools.itemkit.runner.source_version',return_value='version') as version, patch.object(r,'worker',return_value={}) as worker:
                r._execute('render',root)
                self.assertEqual(version.call_count,1)
                worker.assert_called_once_with('render',root,scene='scene',texture='texture')
            with patch.object(r,'result',side_effect=AssertionError('Repeated dependency validation')), patch.object(r,'worker',return_value={}):
                r._execute('render',root,parent_results={'shadow':{'scene':{'path':'scene'}},'bake':{'maps':{'1024':{'path':'texture'}}}})

    def test_hash_once_conflict_and_fresh_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'data';p.write_bytes(b'abc');row=pin(p);a=VerificationPass()
            a.verify([row,row]);self.assertEqual(a.bytes_hashed,3)
            with self.assertRaisesRegex(ValueError,'Conflicting'):a.verify([{**row,'sha256':'0'*64}])
            p.write_bytes(b'xyz')
            with self.assertRaisesRegex(ValueError,'Stale'):VerificationPass().verify([row])

    def test_new_pass_rereads_same_size_rewrite_with_restored_timestamp(self):
        import os
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'data';p.write_bytes(b'abc');os.utime(p,ns=(10**18,10**18));stat=p.stat()
            row=pin(p);VerificationPass().verify([row])  # Old enough for the process hash cache.
            p.write_bytes(b'xyz');os.utime(p,ns=(stat.st_atime_ns,stat.st_mtime_ns))
            with self.assertRaisesRegex(ValueError,'Stale'):VerificationPass().verify([row])

    def test_diamond_reviews_and_cycle(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);r=Runner.__new__(Runner);r.data={};r.local={};r.runtime=None;r.state={'stages':{},'reviews':{}}
            for stage,parents in [('a',[]),('b',['a']),('c',['a']),('d',['b','c'])]:
                p=root/(stage+'.json');write(p,{'state':'complete','manifestHash':digest({}),'bindingsHash':digest({}),
                    'codeVersion':'version','inputs':[],'outputs':[],'dependencies':{k:r.state['stages'][k] for k in parents},'result':stage})
                r.state['stages'][stage]=pin(p);q=root/(stage+'-review.json');write(q,{'stageReceipt':pin(p),'decision':'approved'});r.state['reviews'][stage]=pin(q)
            audit=VerificationPass()
            with patch('tools.itemkit.runner.source_version',return_value='version') as version:
                self.assertEqual(r.result('d',_audit=audit),'d');self.assertEqual(len(audit.results),4);self.assertEqual(version.call_count,1)
            with patch('tools.itemkit.runner.source_version',return_value='changed'):
                with self.assertRaisesRegex(ValueError,'Stale item'):r.result('d')
            q=root/'a-review.json';write(q,{'stageReceipt':r.state['stages']['a'],'decision':'rejected'});r.state['reviews']['a']=pin(q)
            with patch('tools.itemkit.runner.source_version',return_value='version'):
                with self.assertRaisesRegex(ValueError,'rejected'):r.result('d')
                with self.assertRaisesRegex(ValueError,'Cyclic'):r.result('a',seen={'a'})


class DaggerTests(Fixture):
    def test_longsword_intake_contract_and_comparison_scope(self):
        intake(self.root/'reference.png',self.root/'long','cougar-fineblade-longsword','longsword')
        profile=read(self.root/'long/family.json')
        self.assertEqual(profile['budgets']['visible'],12000)
        self.assertEqual(profile['sourceExport']['signMode'],'udf')
        self.assertEqual(profile['resources']['blueprint'],'sr_cfs')
        self.native();table=self.path.parent/'stack/base/baseitems.2da'
        table.write_text('2DA V2.0\n\nLabel ItemClass ModelType\n1 longsword WSwLs 2\n')
        stack=self.path.parent/'stack/stack.json';d=read(stack)
        d['layers'][0]['resources'][0]['file']['sha256']=pin(table)['sha256'];write(stack,d)
        self.profile['family']='longsword'
        self.profile['native'].update(baseItem=1,itemClass='wswls',baseitemsSha256=pin(table)['sha256'])
        self.profile['native']['stack']['sha256']=pin(stack)['sha256'];self.save_profile()
        contracts.family(self.profile_path)
        self.profile['native']['baseItem']=22;self.save_profile()
        with self.assertRaises((ValueError,KeyError)):contracts.family(self.profile_path)
        self.data['inputs']['comparisonBlueprint2']={'path':'missing.uti','sha256':'0'*64};write(self.path,self.data)
        with self.assertRaises(OSError):contracts.all_pins(self.path,roles={'comparisonBlueprint'},native=False)

    def test_preparation_omits_unconsumed_geometry_but_full_validation_rejects_it(self):
        missing={'path':'missing-raw.glb','sha256':'0'*64}
        self.data['inputs']['geometryRaw']=missing;write(self.path,self.data)
        pins=contracts.all_pins(self.path,roles={'reference'},native=False)
        self.assertNotIn(str(self.path.parent/'missing-raw.glb'),[row['path'] for row in pins])
        with self.assertRaises(OSError):contracts.manifest(self.path)

    def test_dagger_table_contract_and_identity(self):
        self.native();table=self.path.parent/'stack/base/baseitems.2da'
        table.write_text('2DA V2.0\n\nLabel ItemClass ModelType\n22 dagger WSwDg 2\n')
        stack=self.path.parent/'stack/stack.json';d=read(stack);d['layers'][0]['resources'][0]['file']['sha256']=pin(table)['sha256'];write(stack,d)
        self.profile['family']='dagger';n=self.profile['native'];n.update(baseItem=22,itemClass='wswdg',baseitemsSha256=pin(table)['sha256']);n['stack']['sha256']=pin(stack)['sha256'];self.save_profile()
        contracts.family(self.profile_path)
        self.profile['resources']={'texturePrefix':'sr_cfk','blueprint':'sr_cfk'}
        allocation=contracts.reserve(self.profile,{'sr_cfk_01.tga':None})
        self.assertEqual(allocation['models']['t'],'wswdg_t_021')
        with self.assertRaisesRegex(ValueError,'Blueprint'):contracts.reserve(self.profile,{'sr_cfk.uti':None})
        self.assertEqual(blueprint(22,allocation,{'blueprint':'sr_cfk','displayName':'Knife'})['TemplateResRef']['value'],'sr_cfk')

    def test_intake_identity_and_budget(self):
        intake(self.root/'reference.png',self.root/'knife','cougar-fineblade-knife','dagger')
        data=read(self.root/'knife/asset.json');family=read(self.root/'knife/family.json')
        self.assertEqual(data['id'],'cougar-fineblade-knife');self.assertEqual(family['family'],'dagger')
        self.assertEqual(sum(x['visible'] for x in family['budgets']['parts'].values()),5000)


class GripTests(unittest.TestCase):
    def test_resize_archive_is_closed_immutable_and_preserves_length(self):
        from tools.itemkit.resize import transform_part
        from tools.itemkit.test_itemkit import GeometryTests
        v,f=GeometryTests().tetra();p=v[f]
        n=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);n/=np.linalg.norm(n,axis=1)[:,None]
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.npz'
            np.savez(source,positions=p,normals=np.repeat(n[:,None,:],3,axis=1),uv=np.zeros((len(f),3,2)),shadowVertices=v,shadowFaces=f)
            before=pin(source);result=transform_part(source,np.diag([.8,1,.64,1]),root/'revision')
            self.assertEqual(pin(source),before);self.assertEqual(result['retainedAxes'],[1]);self.assertTrue(result['uvExact'])
            with self.assertRaises(FileExistsError):transform_part(source,np.eye(4),root/'revision')

    def test_inverse_transpose_and_uv_length(self):
        p=np.array([[[1.,2.,3.],[2.,2.,3.],[1.,3.,3.]]]);n=np.ones_like(p)/np.sqrt(3);uv=np.zeros((1,3,2));m=np.diag([.8,1.,.64,1.])
        q,nn,uu=affine_corners(p,n,uv,m)
        np.testing.assert_array_equal(q[...,1],p[...,1]);np.testing.assert_array_equal(uu,uv)
        np.testing.assert_allclose(np.linalg.norm(nn,axis=-1),1)
        self.assertFalse(np.allclose(nn,n))

    def test_measured_grip_calibration(self):
        v=np.array([[x,y,z] for x in [-.1,.1] for y in [-.2,.2] for z in [-.2,.2]])
        f=np.array([[0,1,3],[0,3,2],[4,6,7],[4,7,5],[0,4,5],[0,5,1],[2,3,7],[2,7,6]])
        standard={'id':'cougar-approved-grip-v1','approval':{'gripSizingApproved':True},'targetMidpointSection':{'depth':.03,'visibleFaceWidth':.05}}
        m,_=calibration(v,f,np.eye(4),[0,0,0],standard);out=(np.c_[v,np.ones(len(v))]@m.T)[:,:3]
        np.testing.assert_allclose(section_dimensions(out,f,0),[.03,.05]);np.testing.assert_array_equal(v[:,1],out[:,1])

if __name__=='__main__':unittest.main()
