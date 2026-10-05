"""Synthetic source-corner, mask and append-only wrist export regressions."""
import copy,unittest
import numpy as np
import taper_target_hand_wrist_stub as taper
from test_mirror_stock_limb_part import fixture
from mirror_stock_limb_part import detached_affine_bake
from place_purposebuilt_pelvis import BASIS,accessor
from conservative_face_selection import mesh_arrays
from diagnostic_axis_radial import append_attributes

def source_fixture():
    doc,blob=fixture();doc['meshes'][0]['primitives'][0]['attributes'].pop('COLOR_0')
    p=accessor(doc,blob,0).copy();p*=.04;p[:,1]-=.020
    doc,blob=append_attributes(doc,blob,{'POSITION':p})
    doc,blob,archive,_=detached_affine_bake(doc,blob,np.eye(4),False)
    raw,faces,primitive=mesh_arrays(doc,blob);local=raw.astype(float)@BASIS.T;active=local[:,2]>taper.START
    mask={'kind':'target-hand-stub-radial-review-mask','part':'handr','coordinateSpace':'working','axialBandMetres':[taper.START,taper.END],'reviewApproved':False,'exportAuthorized':False,'activeOriginalVertexRows':np.flatnonzero(active).tolist(),'protectedOriginalVertexRows':np.flatnonzero(~active).tolist(),'fullAffectedOriginalFaceIds':np.flatnonzero(active[faces].all(1)).tolist(),'mixedAffectedOriginalFaceIds':np.flatnonzero(active[faces].any(1)&~active[faces].all(1)).tolist(),'protectedOriginalFaceIds':np.flatnonzero(~active[faces].any(1)).tolist()}
    return doc,blob,archive,mask

class SourceConservationTests(unittest.TestCase):
    def test_append_only_source_arrays_and_protected_corner_conservation(self):
        doc,blob,archive,mask=source_fixture();new,payload,arc,proof=taper.bake(doc,blob,archive,mask,taper.START,taper.END,.8990269023138446)
        self.assertEqual(payload[:len(blob)],blob);self.assertEqual(new['materials'],doc['materials']);self.assertEqual(new['images'],doc['images'])
        oldattrs=doc['meshes'][0]['primitives'][0]['attributes'];newattrs=new['meshes'][0]['primitives'][0]['attributes'];raw,faces,_=mesh_arrays(doc,blob);active=(raw.astype(float)@BASIS.T)[:,2]>taper.START
        self.assertTrue(active.any());self.assertTrue((~active).any())
        for sem in ['POSITION','NORMAL','TANGENT']:
            old=accessor(doc,blob,oldattrs[sem]);actual=accessor(new,payload,newattrs[sem]);self.assertEqual(old[~active].tobytes(),actual[~active].tobytes());self.assertEqual(accessor(new,payload,oldattrs[sem]).tobytes(),old.tobytes())
        self.assertEqual(newattrs['TEXCOORD_0'],oldattrs['TEXCOORD_0']);self.assertEqual(new['meshes'][0]['primitives'][0]['indices'],doc['meshes'][0]['primitives'][0]['indices'])
        cm=active[faces]
        for key in ['positions','normals','tangents']:self.assertEqual(archive[key][~cm].tobytes(),arc[key][~cm].tobytes())
        for key in archive:
            if key not in ['positions','normals','tangents']:np.testing.assert_array_equal(archive[key],arc[key])
        self.assertGreater(proof['minimumDiscreteFaceNormalDot'],0)
        for key in taper.TOPOLOGY_KEYS:self.assertEqual(proof['beforeTopology'][key],proof['afterTopology'][key])
    def test_axial_and_handedness_preserved_for_every_row(self):
        d,b,a,m=source_fixture();n,p,arc,proof=taper.bake(d,b,a,m,taper.START,taper.END,.8990269023138446)
        oa=d['meshes'][0]['primitives'][0]['attributes'];na=n['meshes'][0]['primitives'][0]['attributes']
        self.assertEqual(accessor(d,b,oa['POSITION'])[:,1].tobytes(),accessor(n,p,na['POSITION'])[:,1].tobytes())
        self.assertEqual(accessor(d,b,oa['TANGENT'])[:,3].tobytes(),accessor(n,p,na['TANGENT'])[:,3].tobytes())
    def test_identity_field_preserves_all_actual_and_authoritative_pnt_bytes(self):
        d,b,a,m=source_fixture();n,p,arc,_=taper.bake(d,b,a,m,taper.START,taper.END,1.)
        oa=d['meshes'][0]['primitives'][0]['attributes'];na=n['meshes'][0]['primitives'][0]['attributes']
        for sem in ['POSITION','NORMAL','TANGENT']:self.assertEqual(accessor(d,b,oa[sem]).tobytes(),accessor(n,p,na[sem]).tobytes())
        for key in ['positions','normals','tangents']:self.assertEqual(a[key].tobytes(),arc[key].tobytes())
    def test_partial_duplicated_reordered_or_fractional_masks_rejected(self):
        d,b,a,m=source_fixture()
        mutations=[('activeOriginalVertexRows',[]),('protectedOriginalVertexRows',m['protectedOriginalVertexRows']+[m['protectedOriginalVertexRows'][0]]),('mixedAffectedOriginalFaceIds',m['mixedAffectedOriginalFaceIds'][::-1]),('activeOriginalVertexRows',[v+.1 for v in m['activeOriginalVertexRows']])]
        for key,value in mutations:
            bad=copy.deepcopy(m);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):taper.bake(d,b,a,bad,taper.START,taper.END,.8990269023138446)
    def test_forearm_runtime_or_adopted_mask_rejected(self):
        d,b,a,m=source_fixture()
        for key,value in [('part','forer'),('coordinateSpace','runtime'),('reviewApproved',True),('exportAuthorized',True)]:
            bad=copy.deepcopy(m);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):taper.bake(d,b,a,bad,taper.START,taper.END,.8990269023138446)
    def test_changed_source_corner_position_normal_uv_or_order_rejected(self):
        d,b,a,m=source_fixture()
        for key in ['positions','normals','uvGltf','sourceCornerOrder','sourceTriangleIds']:
            bad={k:v.copy() for k,v in a.items()};bad[key].flat[0]+=1
            with self.subTest(key=key),self.assertRaises(ValueError):taper.bake(d,b,bad,m,taper.START,taper.END,.8990269023138446)
    def test_approval_hash_required_before_any_schema_or_source_work(self):
        for approved in [None,'wrong','a'*63]:
            with self.assertRaisesRegex(ValueError,'approved review'):taper.checked_config({},'a'*64,approved)
    def test_unknown_controls_and_missing_source_schema_rejected(self):
        with self.assertRaisesRegex(ValueError,'Exact source-bound'):taper.checked_config({'uniformScale':.9},'a'*64,'a'*64)

    def test_declared_one_ulp_radius_roundoff_passes_with_exact_physical_factor(self):
        saved=.0396145120993792;k=.8990269023138446
        for actual in [saved,np.nextafter(saved,np.inf),np.nextafter(saved,-np.inf)]:
            proof=taper.validate_radius_scalars(saved,actual,k,.004)
            self.assertLessEqual(abs(proof['radiusDifferenceULPs']),1)
            self.assertLessEqual(proof['analyticMaximumRadialMovementMetres'],.004+np.spacing(.004))
    def test_two_ulp_radius_drift_is_not_waived(self):
        saved=.0396145120993792;k=.8990269023138446
        for direction in [np.inf,-np.inf]:
            actual=np.nextafter(np.nextafter(saved,direction),direction)
            with self.assertRaisesRegex(ValueError,'more than 1 declared ULP'):taper.validate_radius_scalars(saved,actual,k,.004)
    def test_scalar_nonfinite_changed_factor_or_physical_bound_rejected(self):
        saved=.0396145120993792;k=.8990269023138446
        for values in [(saved,np.nan,k,.004),(0,saved,k,.004),(saved,saved,k-.001,.004),(saved,saved,np.nextafter(k,-np.inf),.004)]:
            with self.subTest(values=values),self.assertRaises(ValueError):taper.validate_radius_scalars(*values)
    def test_nonfinite_source_positions_normals_and_tangents_rejected(self):
        d,b,a,m=source_fixture()
        for sem in ['POSITION','NORMAL','TANGENT']:
            index=d['meshes'][0]['primitives'][0]['attributes'][sem];raw=accessor(d,b,index).copy();raw.flat[0]=np.nan
            acc=d['accessors'][index];view=d['bufferViews'][acc['bufferView']];offset=view.get('byteOffset',0)+acc.get('byteOffset',0);blob=bytearray(b);blob[offset:offset+raw.nbytes]=raw.tobytes()
            error=RuntimeError if sem=='POSITION' else ValueError
            with self.subTest(sem=sem),self.assertRaises(error):taper.bake(d,bytes(blob),a,m,taper.START,taper.END,.8990269023138446)
    def test_frozen_source_bind_frame_proper_fit_and_zero_stature_required(self):
        from test_target_part_pipeline import target_fixture
        target=target_fixture();frame=target['rig']['frames']['working']['rhand_g'];M=np.diag([.23355055421264603]*3+[1.])
        parent={'part':'handr','joint':'rhand_g','coordinateSpace':'working','statureApplications':0,'operation':'fit','reflectionWorld':None,'attachmentWorld':frame,'sourceToAttachmentLocal':M.tolist()}
        np.testing.assert_array_equal(taper.checked_parent_frame(parent,target),frame)
        bad=copy.deepcopy(parent);bad['attachmentWorld'][0][3]+=1e-9
        with self.assertRaisesRegex(ValueError,'attachment changed'):taper.checked_parent_frame(bad,target)
        for key,value in [('part','handl'),('joint','lhand_g'),('coordinateSpace','runtime'),('statureApplications',1),('operation','bounded-hand-wrist-stub-radial-taper'),('reflectionWorld',np.eye(4).tolist()),('sourceToAttachmentLocal',np.diag([-.2,.2,.2,1.]).tolist()),('sourceToAttachmentLocal',np.diag([.2,.3,.2,1.]).tolist()),('sourceToAttachmentLocal',np.full((4,4),np.nan).tolist())]:
            bad=copy.deepcopy(parent);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):taper.checked_parent_frame(bad,target)
if __name__=='__main__':unittest.main()