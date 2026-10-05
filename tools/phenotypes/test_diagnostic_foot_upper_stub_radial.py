"""Source-bound typed masks, unique corner ownership and append-only RAM preparation."""
import copy,unittest
import numpy as np
import diagnostic_foot_upper_stub_radial as h
from test_mirror_stock_limb_part import fixture
from place_purposebuilt_pelvis import accessor,BASIS
from diagnostic_axis_radial import append_attributes
from conservative_face_selection import mesh_arrays


def source_fixture():
    d,b=fixture();d['meshes'][0]['primitives'][0]['attributes'].pop('COLOR_0')
    raw=accessor(d,b,0).copy();raw*=.025;raw[:,1]+=.022
    d,b=append_attributes(d,b,{'POSITION':raw});P,F,pr=mesh_arrays(d,b);P=P.astype(float)@BASIS.T
    # One proximal vertex and its mixed faces, three lower/protected corners.
    original=(P-[0,0,h.START])/1.2;protected=original[:,2]<=0;active=(P[:,2]>h.START)&~protected
    rows={k:accessor(d,b,v) for k,v in pr['attributes'].items()}
    t=rows['TANGENT'].astype(float).copy();t[:,:3]=t[:,:3]@BASIS.T
    uv=rows['TEXCOORD_0'].astype(float)[F];uvn=uv.copy();uvn[:,:,1]=1-uvn[:,:,1]
    a={'positions':P[F],'normals':(rows['NORMAL'].astype(float)@BASIS.T)[F],
       'tangents':t[F],'uvGltf':uv,'uvNative':uvn,'sourceTriangleIds':np.arange(len(F)),
       'sourceCornerOrder':np.tile([0,1,2],(len(F),1)),'primitiveIds':np.zeros(len(F),int)}
    s,_=h.profile(P[:,2],h.START,h.END,h.FACTOR);s[protected]=1
    masks={'affectedSourceRowIDs':np.flatnonzero(active),'protectedOriginalZeroOrLowerSourceRowIDs':np.flatnonzero(protected),
           'outsideSourceRowIDs':np.flatnonzero(~active),'allAffectedVertexSourceFaceIDs':np.flatnonzero(active[F].all(1)),
           'crossingAffectedProtectedSourceFaceIDs':np.flatnonzero(active[F].any(1)&~active[F].all(1)),
           'protectedWholeSourceFaceIDs':np.flatnonzero(~active[F].any(1)),'sourceFaces':F,'fieldScaleBySourceRow':s}
    return d,b,a,original,masks


class FootSourceTests(unittest.TestCase):
    def test_append_only_pnt_protected_rows_uv_material_bin_face_corner_exact(self):
        d,b,a,original,m=source_fixture();nd,nb,arc,p=h.bake_ram(d,b,a,original,m)
        self.assertEqual(b,nb[:len(b)]);self.assertEqual(d['materials'],nd['materials']);self.assertEqual(d['images'],nd['images'])
        op=d['meshes'][0]['primitives'][0];np_=nd['meshes'][0]['primitives'][0]
        self.assertEqual(op['indices'],np_['indices']);self.assertEqual(op['attributes']['TEXCOORD_0'],np_['attributes']['TEXCOORD_0'])
        protected=m['outsideSourceRowIDs'];F=m['sourceFaces'];active=np.zeros(len(original),bool);active[m['affectedSourceRowIDs']]=True
        self.assertTrue(active.any());self.assertTrue((~active).any())
        for sem in ('POSITION','NORMAL','TANGENT'):
            old=accessor(d,b,op['attributes'][sem]);new=accessor(nd,nb,np_['attributes'][sem])
            self.assertEqual(old[protected].tobytes(),new[protected].tobytes())
            self.assertEqual(old.tobytes(),accessor(nd,nb,op['attributes'][sem]).tobytes())
        for key in a:
            if key in ('positions','normals','tangents'):self.assertEqual(a[key][~active[F]].tobytes(),arc[key][~active[F]].tobytes())
            else:self.assertEqual(a[key].tobytes(),arc[key].tobytes())
        self.assertFalse(p['meshExported']);self.assertFalse(p['noShelfVisualAcceptance'])
    def test_incomplete_duplicated_reordered_fractional_or_unassigned_masks_rejected(self):
        d,b,a,o,m=source_fixture()
        changes=[('affectedSourceRowIDs',np.array([],int)),('outsideSourceRowIDs',np.r_[m['outsideSourceRowIDs'],m['outsideSourceRowIDs'][0]]),
                 ('outsideSourceRowIDs',m['outsideSourceRowIDs'][::-1]),('affectedSourceRowIDs',m['affectedSourceRowIDs'].astype(float)),
                 ('crossingAffectedProtectedSourceFaceIDs',np.array([],int)),('sourceFaces',m['sourceFaces'][:,[0,2,1]])]
        for key,value in changes:
            bad={k:v.copy() for k,v in m.items()};bad[key]=value
            with self.subTest(mask=key),self.assertRaises(ValueError):h.bake_ram(d,b,a,o,bad)
    def test_shared_index_ambiguous_corner_owner_fail_closed(self):
        d,b,a,o,m=source_fixture();bad={k:v.copy() for k,v in a.items()};bad['positions'][1,0,0]+=1e-12
        with self.assertRaisesRegex(ValueError,'Ambiguous'):h.bake_ram(d,b,bad,o,m)
    def test_shared_index_signed_zero_owner_is_not_silently_merged(self):
        faces=np.array([[0,1,2],[0,2,1]]);p=np.zeros((2,3,3));p[1,0,0]=-0.
        with self.assertRaisesRegex(ValueError,'Ambiguous'):h.archive_rows(p,faces,3)
    def test_unreferenced_vertex_or_nonfinite_authoritative_position_rejected(self):
        d,b,a,o,m=source_fixture()
        with self.assertRaisesRegex(ValueError,'Unreferenced'):h.archive_rows(a['positions'],m['sourceFaces'],len(o)+1)
        bad=a['positions'].copy();bad.flat[0]=np.nan
        with self.assertRaises(ValueError):h.archive_rows(bad,m['sourceFaces'],len(o))
    def test_changed_normal_tangent_uv_face_order_or_primitive_ownership_rejected(self):
        d,b,a,o,m=source_fixture()
        for key in ('normals','tangents','uvGltf','sourceCornerOrder','sourceTriangleIds','primitiveIds'):
            bad={k:v.copy() for k,v in a.items()};bad[key].flat[0]+=1
            with self.subTest(array=key),self.assertRaises(ValueError):h.bake_ram(d,b,bad,o,m)
    def test_nonfinite_serialized_attrs_fail_closed(self):
        d,b,a,o,m=source_fixture()
        for semantic in ('POSITION','NORMAL','TANGENT','TEXCOORD_0'):
            index=d['meshes'][0]['primitives'][0]['attributes'][semantic];r=accessor(d,b,index).copy();r.flat[0]=np.inf
            view=d['bufferViews'][d['accessors'][index]['bufferView']];offset=view.get('byteOffset',0);bb=bytearray(b);bb[offset:offset+r.nbytes]=r.tobytes()
            with self.subTest(semantic=semantic),self.assertRaises((ValueError,RuntimeError)):h.bake_ram(d,bytes(bb),a,o,m)
    def test_other_part_runtime_offset_scale_or_adoption_proposals_rejected(self):
        c={'schemaVersion':1,'kind':'review-only-foot120-upper-stub-contour-derived-radial-field','part':'footl','joint':'lfoot_g','coordinateSpace':'working',
           'startCurrentLocalMetres':h.START,'endCurrentLocalMetres':h.END,'terminalRadialFactor':h.FACTOR,'statureApplications':0,
           'globalTranslationScaleRollOrFrameChange':False,'localOffsetProposed':False,'currentFoot120OriginalScaleNotReapplied':True,
           'currentFootAxialScaleUnchanged':True,'noMeshExportOrRepairExecution':True,'rootReviewRequiredBeforeImplementationExport':True,
           'protectedSpecificFaces':{'12586':True,'44222':True},'geometryAccepted':False,'connectorAccepted':False,'clientAccepted':False,'productionAccepted':False}
        h.check_proposal(c)
        for key,value in [('part','footr'),('joint','rfoot_g'),('coordinateSpace','runtime'),('statureApplications',1),('localOffsetProposed',True),
                          ('endCurrentLocalMetres',h.END+.001),('terminalRadialFactor',.6),('geometryAccepted',True),('currentFootAxialScaleUnchanged',False)]:
            bad=copy.deepcopy(c);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):h.check_proposal(bad)
    def test_helper_has_no_export_command_or_mesh_writer(self):
        self.assertFalse(hasattr(h,'execute'));self.assertFalse(hasattr(h,'export'));self.assertFalse(hasattr(h,'write_glb'))
if __name__=='__main__':unittest.main()
