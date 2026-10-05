import unittest,tempfile
from pathlib import Path
import numpy as np
import export_target_regional_chest002 as pilot
from stage_target_rigid_equipment import mesh_data


def source_fixture():
    p=np.c_[np.arange(37)/100.,np.arange(37)/-200.,np.arange(37)/300.]
    uv=np.c_[np.arange(51)/100.,np.arange(51)/200.,np.zeros(51)]
    f=np.array([[i%37,(i+1)%37,(i+2)%37,1,i%51,(i+1)%51,(i+2)%51,0] for i in range(70)])
    text='newmodel pmh0_chest002\nsetsupermodel pmh0_chest002 NULL\nclassification CHARACTER\nsetanimationscale 1\nbeginmodelgeom pmh0_chest002\nnode dummy pmh0_chest002\n  parent NULL\n  position 0 0 0\n  orientation 0 0 1 0\n  scale 1\nendnode\nnode trimesh pmh0_chest002g\n  parent pmh0_chest002\n  bitmap pmh0_chest002\n  ambient 1 1 1\n  diffuse 1 1 1\n  shininess 1\n'
    for key,rows in [('verts',p),('tverts',uv),('faces',f)]:text+='  '+key+' '+str(len(rows))+'\n'+''.join('    '+' '.join(str(x) for x in row)+'\n' for row in rows)
    text+='endnode\nendmodelgeom pmh0_chest002\ndonemodel pmh0_chest002\n'
    return text,p,uv,f


class RegionalPilotExportTests(unittest.TestCase):
    def test_roundtrip37_position_normal_values_and_exact_face_uv_text(self):
        text,p,uv,f=source_fixture();q=p.copy();q[:,0]+=.002;normals=np.tile([.11,.21,.93],(37,1));out=pilot.serialize37(text,q,normals);m=next(iter(mesh_data(out).values()))
        np.testing.assert_array_equal(m['vertices'],q);np.testing.assert_array_equal(m['normals'],normals)
        np.testing.assert_array_equal(m['arrays']['tverts'],uv);np.testing.assert_array_equal(m['arrays']['faces'],f)
        self.assertIn('setsupermodel pmg0_chest002 NULL\n',out)
        self.assertEqual(pilot.array_span(text,'faces')[2],pilot.array_span(out,'faces')[2])
        self.assertEqual(pilot.array_span(text,'tverts')[2],pilot.array_span(out,'tverts')[2])
        self.assertIn('  ambient 1 1 1\n  diffuse 1 1 1\n  shininess 1\n',out)

    def test_no_source_normal_magnitude_regeneration(self):
        text,p,_,_=source_fixture();n=np.tile([.3,.1,.99],(37,1));out=pilot.serialize37(text,p,n);actual=next(iter(mesh_data(out).values()))['normals']
        np.testing.assert_array_equal(actual,n);self.assertNotEqual(float(np.linalg.norm(actual[0])),1.)

    def test_existing_normals_weights_tangents_rejected(self):
        text,p,_,_=source_fixture();n=np.tile([0.,0.,1.],(37,1))
        for key in ('normals','tangents','weights'):
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'no authored'):pilot.serialize37(text.replace('  bitmap','  '+key+' 0\n  bitmap',1),p,n)

    def test_human_inherited_or_nonidentity_source_rejected(self):
        text,p,_,_=source_fixture();n=np.tile([0.,0.,1.],(37,1))
        for altered in (text.replace('chest002 NULL','chest002 pmh0'),text.replace('position 0 0 0','position .01 0 0')):
            with self.assertRaises(ValueError):pilot.serialize37(altered,p,n)

    def test_nonfinite_or_wrong_row_count_rejected(self):
        text,p,_,_=source_fixture();n=np.tile([0.,0.,1.],(37,1));bad=p.copy();bad[1,0]=np.nan
        for q in (p[:-1],bad):
            with self.assertRaisesRegex(ValueError,'finite'):pilot.serialize37(text,q,n)

    def approval(self):
        ref={'path':'review.json','sha256':'a'*64};approval={'kind':'root-approved-regional-equipment-working-pilot','reviewedBy':'/root','configuration':ref,'authorizeImplementationAndOneFreshWorkingPilot':True,'authorizeIndependentNativeCompileAndDecode':True}
        approval.update({k:False for k in ('geometryAccepted','equipmentFitAccepted','collisionAccepted','materialAccepted','clientAccepted','productionAccepted')});return ref,approval

    def test_exact_approval_passes_changed_config_or_acceptance_rejected(self):
        ref,a=self.approval();pilot.check_approval(ref,a)
        for change in ('sha','authorization','author','acceptance'):
            ref,a=self.approval()
            if change=='sha':ref=dict(ref,sha256='b'*64)
            if change=='authorization':a['authorizeIndependentNativeCompileAndDecode']=False
            if change=='author':a['reviewedBy']='unknown'
            if change=='acceptance':a['equipmentFitAccepted']=True
            with self.subTest(change=change),self.assertRaises(ValueError):pilot.check_approval(ref,a)

    def test_existing_output_duplicate_guard_precedes_missing_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'once-only'):pilot.export('missing','missing','missing',Path(d))

    def test_outside_target_equipment_output_rejected_before_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ('pmh0_chest002','equipment-chest002-regional-working-pilot-v1'):
                with self.subTest(name=name),self.assertRaisesRegex(ValueError,'Isolated target'):pilot.export('missing','missing','missing',Path(d)/name)


if __name__=='__main__':unittest.main()