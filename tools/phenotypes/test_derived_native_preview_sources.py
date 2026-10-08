"""Exact native preview descendant/control association and byte-corruption guards."""
import copy,json,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import target_contract as c
import prepare_target_native_material_preview as preview
import target_native_tangent_descendant as writer
import audit_derived_native_tangent as independent
from audit_target_native_part import decode
from test_native_tangent_descendant import source_fixture
from test_target_native_material_preview import put_name,NativePreviewTests
from test_human_female_stock_exact import stock_fixture


class DerivedNativePreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.tp,self.target=stock_fixture(self.root);self.model=c.model(self.target,'chest')
        data,old,names,nodes,raw,native,roles=source_fixture();data=bytearray(data)
        put_name(data,20,64,self.model)
        rootnode=struct.unpack_from('<I',data,12+0x48)[0];put_name(data,12+rootnode+32,32,self.model)
        self.names=[self.model+'p'+str(i) for i in range(2)]
        for i,at in enumerate(nodes):
            put_name(data,12+at+32,32,self.names[i]);material=self.model+('f' if i==0 else '')
            for slot in (0,3):put_name(data,12+at+0xe8+slot*64,64,material)
        self.src=bytes(data);self.native,_=decode(self.src,self.model,self.names)
        self.roles={self.names[0]:'garment',self.names[1]:'skin'}
        self.out,_,_=writer.project_skin_tangents(self.src,self.native,self.roles)
        self.original=self.root/'original'/ (self.model+'.mdl');self.original.parent.mkdir();self.original.write_bytes(self.src)
        self.child=self.root/'derived'/ (self.model+'.mdl');self.child.parent.mkdir();self.child.write_bytes(self.out)
        self.stage=self.root/'stage.json';self.stage.write_text('{}')
        self.config=self.root/'derivation-config.json';self.config.write_text('{"unitFixture":true}')
        self.ctx={'targetPath':self.tp,'part':'chest','space':'working','nativePath':self.original,
                  'native':self.native,'roles':self.roles,'stagePath':self.stage,'frozenInputs':{str(self.original):c.sha(self.original)}}
        self.derivation=self.root/'derivation.json'
        self.doc={'schemaVersion':1,'kind':writer.KIND,**c.binding(self.tp,self.target,'working'),
                  'policy':writer.POLICY,'derivationApplications':1,'part':'chest','model':self.model,
                  'originalCompileReceiptRewritten':False,'nativeCompilerExecuted':False,
                  'configuration':writer.file_row(self.config),'frozenInputs':{str(self.original):c.sha(self.original)},
                  'originalCompiledNative':writer.file_row(self.original),'nativeModel':writer.file_row(self.child)}
        self.write_derivation()
        _,_,proof,_=independent.audit_emitted_bytes(self.src,self.out,self.model,self.names,self.roles)
        self.audit={'schemaVersion':1,'kind':independent.KIND_AUDIT,**c.binding(self.tp,self.target,'working'),
                   'part':'chest','model':self.model,'attributeTransportVerified':True,'materialTransportVerified':True,
                   'nativeTangentProjectionIndependentlyReplayed':True,'allNonTBytesExact':True,
                   'originalCompileReceiptRewritten':False,'nativeDerivationReceipt':writer.file_row(self.derivation),
                   'originalCompiledNative':writer.file_row(self.original),'nativeModel':writer.file_row(self.child),
                   'nativeModelSha256':c.sha(self.child),'stageReceipt':str(self.stage),'stageReceiptSha256':c.sha(self.stage),
                   'meshes':proof}
        self.auditpath=self.root/'audit.json';self.auditpath.write_text(json.dumps(self.audit))

    def tearDown(self):self.temp.cleanup()
    def write_derivation(self):self.derivation.write_text(json.dumps(self.doc))
    def entry(self,control=False):return {'kind':'derivation-compiler-parent-control' if control else 'audited-derived-native-candidate',
                    'binding':c.binding(self.tp,self.target,'working'),'nativeModel':writer.file_row(self.original if control else self.child),
                    'nativeAudit':writer.file_row(self.auditpath),'nativeDerivation':writer.file_row(self.derivation)}
    def replay(self,entry=None,audit=None,path=None,ctx=None):
        entry=entry or self.entry();path=path or Path(entry['nativeModel']['path'])
        with patch.object(writer,'load_parent',return_value=ctx or self.ctx):
            return preview.derived_preview_source(entry,audit or self.audit,self.tp,self.target,'working','chest',path,{})

    def test_actual_child_and_known_failing_parent_preserve_distinct_literal_t(self):
        child=self.replay();parent=self.replay(self.entry(True))
        self.assertTrue(child['postcompileTangentXYZDerived']);self.assertFalse(parent['postcompileTangentXYZDerived'])
        self.assertTrue(parent['originalCompilerTangentOrthogonalityKnownFailed'])
        self.assertFalse(parent['originalCompilerPassedNativeTangentAudit']);self.assertFalse(parent['ordinaryHQEngineLightingEmulated'])
        self.assertEqual(parent['originalCompilerTangentFailures'][self.names[1]]['originalVerticesBeyondStrictOrthogonality'],2)
        self.assertEqual(self.original.read_bytes(),self.src);self.assertEqual(self.child.read_bytes(),self.out)
        self.assertNotEqual(decode(self.src,self.model,self.names)[0][self.names[1]]['tangent'].tobytes(),
                            decode(self.out,self.model,self.names)[0][self.names[1]]['tangent'].tobytes())

    def test_no_substituted_child_as_parent_control_or_parent_as_derived(self):
        for control in (False,True):
            e=self.entry(control);p=self.child if control else self.original;e['nativeModel']=writer.file_row(p)
            with self.subTest(control=control),self.assertRaisesRegex(ValueError,'Literal original'):self.replay(e,path=p)

    def test_audit_kind_schema_ownership_and_pass_flags_reject(self):
        cases=[('kind','target-native-part-audit'),('schemaVersion',2),('part','pelvis'),('model','pfh0_pelvis001'),
               ('attributeTransportVerified',False),('materialTransportVerified',False),('allNonTBytesExact',False),
               ('nativeTangentProjectionIndependentlyReplayed',False),('originalCompileReceiptRewritten',True)]
        for key,value in cases:
            a=copy.deepcopy(self.audit);a[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.replay(audit=a)

    def test_repeat_false_compiler_and_wrong_target_space_rig_reject(self):
        for key,value in [('derivationApplications',2),('derivationApplications',True),('nativeCompilerExecuted',True),
                          ('kind','other'),('schemaVersion',2),('targetId','other'),('rigRevision','other'),('coordinateSpace','runtime')]:
            old=copy.deepcopy(self.doc);self.doc[key]=value;self.write_derivation()
            a=copy.deepcopy(self.audit);a['nativeDerivationReceipt']=writer.file_row(self.derivation)
            with self.subTest(key=key),self.assertRaises(ValueError):self.replay(audit=a)
            self.doc=old;self.write_derivation()

    def test_stale_original_child_derivation_and_stage_pins_reject(self):
        for path in (self.original,self.child,self.derivation,self.stage):
            original=path.read_bytes();path.write_bytes(original+b' ')
            with self.subTest(path=path.name),self.assertRaises(ValueError):self.replay()
            path.write_bytes(original)

    def test_independent_byte_replay_rejects_rehashed_corruptions(self):
        row=self.native[self.names[1]];raw=row['layout']['rawOffset'];offsets=[12+0x80]
        offsets += [12+raw+row['layout']['attributeOffsets'][k] for k in ('position','normal','uv','sign','tangent')]
        for offset in offsets:
            bad=bytearray(self.out);bad[offset]^=1;self.child.write_bytes(bad)
            old=copy.deepcopy(self.doc);self.doc['nativeModel']=writer.file_row(self.child);self.write_derivation()
            a=copy.deepcopy(self.audit);a['nativeModel']=writer.file_row(self.child);a['nativeModelSha256']=c.sha(self.child)
            a['nativeDerivationReceipt']=writer.file_row(self.derivation)
            with self.subTest(offset=offset),self.assertRaises(ValueError):self.replay(audit=a)
            self.child.write_bytes(self.out);self.doc=old;self.write_derivation()

    def test_relabelled_audit_mesh_role_layout_or_eligibility_reject(self):
        for field,value in [('role','garment'),('nativeLayout',{}),('eligibleVertices',[])]:
            a=copy.deepcopy(self.audit);a['meshes'][self.names[1]][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'ownership/layout'):self.replay(audit=a)

    def test_wrong_context_target_part_space_reject(self):
        for field,value in [('targetPath',self.root/'other.json'),('part','pelvis'),('space','runtime')]:
            ctx={**self.ctx,field:value}
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'another target'):self.replay(ctx=ctx)

    def test_additive_strict_entry_fields_and_legacy_schema(self):
        old=NativePreviewTests();old.setUp()
        try:
            preview.controls(old.cfg)
            for control in (False,True):
                cfg=copy.deepcopy(old.cfg);cfg['parts']={'chest':self.entry(control)};cfg['render']['focusParts']=['chest']
                preview.controls(cfg)
                for mode in ('missing','extra','old-kind'):
                    bad=copy.deepcopy(cfg)
                    if mode=='missing':bad['parts']['chest'].pop('nativeDerivation')
                    elif mode=='extra':bad['parts']['chest']['allowUnverified']=True
                    else:bad['parts']['chest']['kind']='audited-candidate'
                    with self.subTest(control=control,mode=mode),self.assertRaises(ValueError):preview.controls(bad)
        finally:old.tearDown()


if __name__=='__main__':unittest.main()
