"""Actual-byte corruption tests for explicit native T-only derivation."""
import copy,json,struct,tempfile,unittest
from pathlib import Path
import numpy as np
from audit_target_native_part import decode
from test_audit_target_native_part import fixture
import target_native_tangent_descendant as writer
import audit_derived_native_tangent as audit
import target_contract as c


def source_fixture():
    data,model,names,nodes,raw=fixture();roles={names[0]:'garment',names[1]:'skin'}
    at=12+nodes[1];offset=struct.unpack_from('<I',data,at+0x244)[0]
    # Preserve nonunit authored N and one original eligible sign/normal ambiguity.
    data[12+raw+offset:12+raw+offset+36]=np.array([[0,0,.2],[0,0,.8],[0,0,.13781935]],'<f4').tobytes()
    offset=struct.unpack_from('<I',data,at+0x258)[0]
    data[12+raw+offset:12+raw+offset+36]=np.array([[.8,0,.6],[.8,0,-.6],[1,0,-0.0]],'<f4').tobytes()
    native,root=decode(bytes(data),model,names)
    return bytes(data),model,names,nodes,raw,native,roles


class NativeTangentDescendantTests(unittest.TestCase):
    def test_only_two_failing_skin_txyz_rows_change_all_other_bytes_exact(self):
        src,model,names,nodes,raw,native,roles=source_fixture();out,rows,allowed=writer.project_skin_tangents(src,native,roles)
        actual,root,proofs,_=audit.audit_emitted_bytes(src,out,model,names,roles)
        self.assertEqual(rows[names[0]]['eligibleCount'],0);self.assertEqual(rows[names[1]]['eligibleVertices'],[0,1])
        self.assertEqual(allowed.sum(),24)
        self.assertEqual(src[~allowed] if isinstance(src,np.ndarray) else np.frombuffer(src,'u1')[~allowed].tobytes(),np.frombuffer(out,'u1')[~allowed].tobytes())
        for name in names:
            for key in ['position','normal','uv','sign','faces']:self.assertEqual(native[name][key].tobytes(),actual[name][key].tobytes())
        self.assertEqual(actual[names[1]]['tangent'][2].tobytes(),native[names[1]]['tangent'][2].tobytes())
        self.assertFalse(np.array_equal(native[names[1]]['normal'],native[names[1]]['normal']/np.linalg.norm(native[names[1]]['normal'],axis=1)[:,None]))
        self.assertEqual(proofs[names[1]]['UVGradientDirectionBeforeAfter']['bitangent']['newlyNegativeCorners'],0)

    def test_header_position_normal_uv_sign_face_cloth_and_noneligible_corruptions_reject(self):
        src,model,names,nodes,raw,native,roles=source_fixture();out,_,_=writer.project_skin_tangents(src,native,roles)
        cases={'header-unused':12+0x80,'face':12+native[names[1]]['layout']['faceOffset']+26}
        for name in names:
            row=native[name];base=12+raw
            for key in ['position','normal','uv','sign']:cases[name+':'+key]=base+row['layout']['attributeOffsets'][key]
        cases['cloth-tangent']=12+raw+native[names[0]]['layout']['attributeOffsets']['tangent']
        cases['retained-skin-tangent']=12+raw+native[names[1]]['layout']['attributeOffsets']['tangent']+24
        for label,offset in cases.items():
            bad=bytearray(out);bad[offset]^=1
            with self.subTest(label=label),self.assertRaises(ValueError):audit.audit_emitted_bytes(src,bytes(bad),model,names,roles)

    def test_false_projected_value_and_original_sign_flip_reject(self):
        src,model,names,nodes,raw,native,roles=source_fixture();out,_,_=writer.project_skin_tangents(src,native,roles)
        for mode in ('projected','sign'):
            changed=bytearray(out);row=native[names[1]];offset=12+raw+row['layout']['attributeOffsets']['tangent' if mode=='projected' else 'sign']
            struct.pack_into('<f',changed,offset,.99 if mode=='projected' else -1)
            with self.subTest(mode=mode),self.assertRaises(ValueError):audit.audit_emitted_bytes(src,bytes(changed),model,names,roles)

    def test_repeated_already_orthogonal_parent_rejected(self):
        src,model,names,nodes,raw,native,roles=source_fixture();out,_,_=writer.project_skin_tangents(src,native,roles);second,_=decode(out,model,names)
        with self.assertRaisesRegex(ValueError,'repeated|unnecessary'):writer.project_skin_tangents(out,second,roles)
        with self.assertRaisesRegex(ValueError,'Repeated|unnecessary'):audit.audit_emitted_bytes(out,out,model,names,roles)

    def test_cloth_failure_wrong_owner_and_attribute_alias_reject(self):
        src,model,names,nodes,raw,native,roles=source_fixture()
        bad_roles={names[0]:'skin',names[1]:'garment'}
        with self.assertRaisesRegex(ValueError,'Cloth'):writer.project_skin_tangents(src,native,bad_roles)
        with self.assertRaises(ValueError):writer.project_skin_tangents(src,native,{names[0]:'cloth',names[1]:'skin'})
        aliased=copy.deepcopy(native);aliased[names[1]]['layout']['attributeOffsets']['tangent']=aliased[names[1]]['layout']['attributeOffsets']['normal']
        with self.assertRaisesRegex(ValueError,'Aliased'):writer.project_skin_tangents(src,aliased,roles)

    def test_degenerate_projection_never_constructs_arbitrary_axis(self):
        src,model,names,nodes,raw,native,roles=source_fixture();bad=copy.deepcopy(native);bad[names[1]]['tangent'][:]=[0,0,1]
        with self.assertRaisesRegex(ValueError,'Degenerate'):writer.project_skin_tangents(src,bad,roles)

    def test_invalid_schema_kind_space_part_repeat_policy_and_bool_reject(self):
        base={'schemaVersion':1,'kind':writer.CONFIG,'diagnosticOnly':True,'targetContract':{},'targetId':'x','rigRevision':'x',
              'part':'chest','coordinateSpace':'working','sourceAuditConfiguration':{},'installedShaderSupplement':{},'policy':writer.POLICY}
        writer.controls(base)
        for field,value in [('schemaVersion',True),('schemaVersion',2),('kind','target-native-part-audit'),('diagnosticOnly',1),
                            ('part','neck'),('coordinateSpace','source'),('policy','normalize-source-normals')]:
            cfg={**base,field:value}
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):writer.controls(cfg)
        with self.assertRaises(ValueError):writer.controls({**base,'allowGarmentChange':True})

    def test_stale_relative_and_conflicting_pins_reject(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'parent.json';p.write_text('original');row=writer.file_row(p)
            with self.assertRaises(ValueError):writer.exact({**row,'path':'parent.json'},{})
            with self.assertRaises(ValueError):writer.exact(row,{str(p):'0'*64})
            p.write_text('tampered')
            with self.assertRaises(ValueError):writer.exact(row,{})

    def test_cross_target_rig_reject_before_loading_audit_configuration(self):
        import test_human_female_stock_exact as female
        with tempfile.TemporaryDirectory() as temp:
            tp,target=female.stock_fixture(Path(temp));base={'schemaVersion':1,'kind':writer.CONFIG,'diagnosticOnly':True,
              'targetContract':writer.file_row(tp),'targetId':target['id'],'rigRevision':target['rig']['revision'],'part':'chest',
              'coordinateSpace':'working','sourceAuditConfiguration':{},'installedShaderSupplement':{},'policy':writer.POLICY}
            for field in ('targetId','rigRevision'):
                with self.subTest(field=field),self.assertRaisesRegex(ValueError,'target/rig'):writer.load_parent({**base,field:'other'})

    def test_old_audit_remains_strict_for_nonorthogonal_compiler_parent(self):
        from audit_target_native_part import tangent_proof
        src,model,names,nodes,raw,native,roles=source_fixture()
        with self.assertRaisesRegex(ValueError,'not orthogonal'):tangent_proof(native[names[1]])


if __name__=='__main__':unittest.main()
