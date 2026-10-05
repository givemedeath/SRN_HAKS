"""Independent fixture expectations for target bind and controller transforms."""
import copy
from pathlib import Path
import tempfile
import unittest
import numpy as np

from build_target_rig import export_model, transform_keys, resolve_bind, widen
from build_target_diagnostic import convert_part, points
from retarget import nodes, transforms, signature, rotation_signature
from target_contract import PART_JOINTS, binding, sha, validate, verify_binding
from rig_controller_audit import world_frames, effective_nodes, compatible_parent_basis


def joint(parent, position, orientation=None):
    return {'parent':parent,'position':np.array(position,dtype=float),
            'orientation':orientation or [0,0,0,0]}


class RigTests(unittest.TestCase):
    def test_target_bind_is_not_the_owning_supermodel_bind(self):
        text='''newmodel child
setsupermodel child parent
beginmodelgeom child
node dummy root
 parent NULL
endnode
endmodelgeom child
newanim pause1 child
 length 1
 transtime .1
 node dummy joint
  parent root
  positionkey 2
   0 1 2 3
   1 1.1 2.2 3.3
 endnode
doneanim pause1 child
donemodel child
'''
        original={'child':nodes(text),'parent':{'joint':joint('root',[1,2,3])}}
        target={'root':joint('null',[0,0,0]),'joint':joint('root',[7,8,9])}
        result,audit=export_model(text,'child','sr_child','sr_parent',2,{},original,
            {'child':'parent','parent':'null'},target,target_nodes=target)
        self.assertIn('0 14 16 18',result)
        self.assertIn('1 14.2 16.4 18.6',result)
        self.assertEqual(audit[0]['sourceBind'],[1,2,3])
        self.assertEqual(audit[0]['targetBind'],[14,16,18])

    def test_endlist_position_controller_is_transformed_and_times_are_literal(self):
        text='''newmodel child
setsupermodel child NULL
beginmodelgeom child
node dummy root
 parent NULL
endnode
node dummy joint
 parent root
 position 1 2 3
endnode
endmodelgeom child
newanim pause1 child
 length 1
 transtime .1
 node dummy joint
  parent root
  positionkey
   0.12345678901234567 1 2 3
   0.87654321098765432 1.1 2.2 3.3
  endlist
  orientationkey
   0 0 0 1 .2
   1 0 0 1 .3
  endlist
 endnode
doneanim pause1 child
donemodel child
'''
        result,audit=export_model(text,'child','sr_child','NULL',2,
            {'joint':[.5,0,0]}, {'child':nodes(text)}, {'child':'null'}, {})
        self.assertIn('0.12345678901234567 3 4 6',result)
        self.assertIn('0.87654321098765432 3.2 4.4 6.6',result)
        self.assertIn('orientationkey\n   0 0 0 1 .2\n   1 0 0 1 .3\n  endlist',result)
        self.assertEqual(audit[1]['keys'],2)

    def test_parent_frame_incompatibility_is_rejected(self):
        source={'parent':joint('null',[0,0,0],[0,0,1,np.pi/2]),
                'child':joint('parent',[1,0,0])}
        target=copy.deepcopy(source);target['parent']['orientation']=[0,0,0,0]
        with self.assertRaisesRegex(ValueError,'Incompatible'):
            compatible_parent_basis(source['child'],target['child'],
                                    world_frames(source),world_frames(target))
        target['parent']['orientation']=source['parent']['orientation']
        target['parent']['position']=np.array([50.,100.,200.])
        self.assertEqual(compatible_parent_basis(source['child'],target['child'],
                         world_frames(source),world_frames(target)),0)

    def test_strict_geometry_frames_reject_missing_and_cyclic_parents(self):
        with self.assertRaisesRegex(ValueError,'Unresolved'):
            world_frames({'node':joint('missing',[0,0,0])})
        with self.assertRaisesRegex(ValueError,'cycle'):
            world_frames({'a':joint('b',[0,0,0]),'b':joint('a',[0,0,0])})

    def test_effective_geometry_inherits_parent_binds_then_overrides(self):
        root={'root':joint('null',[0,0,0]),'j':joint('root',[1,2,3])}
        parents={'child':'parent','parent':'null'}
        result=effective_nodes('child',{'child':{},'parent':{'j':joint('root',[4,5,6])}},parents,root)
        np.testing.assert_array_equal(result['j']['position'],[4,5,6])
        np.testing.assert_array_equal(root['j']['position'],[1,2,3])

    def test_identity_and_uniform_scale(self):
        keys=np.array([[0,2,4,8],[.5,3,5,9]])
        np.testing.assert_array_equal(transform_keys(keys,[2,4,8],[2,4,8],1),keys)
        np.testing.assert_allclose(transform_keys(keys,[2,4,8],[4,8,16],2),
                                   [[0,4,8,16],[.5,6,10,18]])

    def test_widened_binding_retains_motion_displacements(self):
        keys=np.array([[0,-.2,.03,.35],[1,-.17,.02,.37]])
        out=transform_keys(keys,[-.2,.03,.35],[-.3,.03,.35],10/7)
        np.testing.assert_allclose(out[:,1:4],
            [[-.3,.03,.35],[-.3+.03*10/7,.03-.01*10/7,.35+.02*10/7]])
        np.testing.assert_array_equal(out[:,0],keys[:,0])

    def test_bezier_points_and_relative_handles_have_different_translations(self):
        rows=[[.5,2,3,4, 1,2,3, 3,4,5]]
        points=transform_keys(rows,[2,3,4],[8,9,10],2,True,
                              bezier_semantics='parent-local-points')
        handles=transform_keys(rows,[2,3,4],[8,9,10],2,True,
                               bezier_semantics='relative-handles')
        np.testing.assert_allclose(points,[[.5,8,9,10,6,7,8,10,11,12]])
        np.testing.assert_allclose(handles,[[.5,8,9,10,2,4,6,6,8,10]])
        with self.assertRaisesRegex(ValueError,'semantics'):
            transform_keys(rows,[2,3,4],[8,9,10],2,True)

    def test_invalid_scale_and_rows_rejected(self):
        for scale in (0,-1,float('nan')):
            with self.assertRaises(ValueError):transform_keys([[0,1,2,3]],[0]*3,[0]*3,scale)
        with self.assertRaises(ValueError):transform_keys([[0,1,2]],[0]*3,[0]*3,1)

    def test_widening_preserves_other_components_and_local_limb_lengths(self):
        rig={'root':joint('null',[.01,.02,1]),'torso':joint('root',[0,.1,.1],[0,0,1,.2]),
             'pelvis':joint('root',[0,.01,-.1]),
             'lbicep_g':joint('torso',[-.2,.01,.3]),'rbicep_g':joint('torso',[.2,.01,.3]),
             'lthigh_g':joint('pelvis',[-.1,0,-.2]),'rthigh_g':joint('pelvis',[.1,0,-.2]),
             'elbow':joint('lbicep_g',[0,0,-.3]),'knee':joint('lthigh_g',[0,0,-.4])}
        original=copy.deepcopy(rig); before=transforms(rig)
        result,changed=widen(rig,.6,.3); after=transforms(result)
        self.assertEqual(set(changed),{'lbicep_g','rbicep_g','lthigh_g','rthigh_g'})
        for name in changed:np.testing.assert_allclose(after[name][1:3,3],before[name][1:3,3])
        self.assertAlmostEqual(after['rbicep_g'][0,3]-after['lbicep_g'][0,3],.6)
        self.assertAlmostEqual(after['rthigh_g'][0,3]-after['lthigh_g'][0,3],.3)
        for name in rig:
            np.testing.assert_array_equal(rig[name]['position'],original[name]['position'])
            self.assertEqual(result[name]['orientation'],original[name]['orientation'])
        for name in ('elbow','knee'):np.testing.assert_array_equal(result[name]['position'],rig[name]['position'])

    def test_inherited_bind_resolution_and_unresolved_rejection(self):
        base={'joint':joint('root',[3,4,5])}
        row,owner=resolve_bind('joint','child',{'child':{},'parent':base},
                               {'child':'parent','parent':'null'}, {})
        self.assertIs(row,base['joint']); self.assertEqual(owner,'parent')
        with self.assertRaisesRegex(ValueError,'Unresolved'):
            resolve_bind('missing','child',{'child':{}},{'child':'null'}, {})
        with self.assertRaisesRegex(ValueError,'cycle'):
            resolve_bind('missing','child',{'child':{}},{'child':'child'}, {})

    def test_export_preserves_events_static_rotations_and_inherited_controller_owner(self):
        text='''newmodel child
setsupermodel child parent
setanimationscale 1
beginmodelgeom child
node dummy root
 parent NULL
 position 0 0 0
 orientation 0 0 0 0
endnode
endmodelgeom child
newanim PAUSE1 child
 length 1.25
 transtime .1
 event .7 hit
 animroot root
 node dummy joint
  parent root
  positionkey 2
   0 1 2 3
   1 1.1 2.2 3.3
  orientationkey 2
   0 0 0 1 .2
   1 0 0 1 .4
  orientation 0 1 0 .35
 endnode
doneanim PAUSE1 child
donemodel child
'''
        result,audit=export_model(text,'child','sr_child','sr_parent',2,
            {'joint':[.5,0,0]}, {'child':nodes(text),'parent':{'joint':joint('root',[1,2,3])}},
            {'child':'parent','parent':'null'}, {})
        self.assertEqual(signature(result),signature(text))
        self.assertEqual(rotation_signature(result),rotation_signature(text))
        self.assertIn('orientation 0 1 0 .35',result)
        self.assertIn('0 3 4 6',result); self.assertIn('1 3.2 4.4 6.6',result)
        self.assertTrue(all(a['sourceBindOwner']=='parent' for a in audit))
        # An inherited rotation-only node must resolve too.
        with self.assertRaisesRegex(ValueError,'Unresolved'):
            export_model(text.replace('positionkey 2\n   0 1 2 3\n   1 1.1 2.2 3.3\n',''),
                'child','sr_child','sr_parent',2,{}, {'child':nodes(text),'parent':{}},
                {'child':'parent','parent':'null'}, {})


class ContractTests(unittest.TestCase):
    def target(self):
        frames={joint:np.eye(4).tolist() for joint in PART_JOINTS.values()}
        return {'schemaVersion':2,'kind':'phenotype-target','id':'fixture-target',
            'identity':{'gender':'male','phenotype':0,'prefix':'pmg0','raceId':2,'appearanceRow':2},
            'workingHeightMeters':2.,'heightMeters':4.,
            'models':{p:'pmg0_'+p+'001' for p in PART_JOINTS},
            'rig':{'runtimeScale':2.,'revision':'test-v1','positionPolicy':'bind-relative',
                'preserveRotations':True,'preserveTimingEvents':True,
                'frames':{'working':copy.deepcopy(frames),'runtime':copy.deepcopy(frames)}}}

    def test_identity_inventory_and_female_preservation_guard(self):
        validate(self.target())
        for field,value in [('gender','female'),('phenotype',2),('prefix','pfg0')]:
            data=self.target();data['identity'][field]=value
            with self.assertRaises(ValueError):validate(data)
        data=self.target();data['models']['chest']='pmh0_chest001'
        with self.assertRaisesRegex(ValueError,'inventory'):validate(data)

    def test_frames_reject_repeated_scale_and_nonrigid_rotation(self):
        data=self.target();data['rig']['frames']['working']['torso_g'][0][3]=.3
        data['rig']['frames']['runtime']['torso_g'][0][3]=.6;validate(data)
        data['rig']['frames']['runtime']['torso_g'][0][3]=1.2
        with self.assertRaisesRegex(ValueError,'once'):validate(data)
        data=self.target();data['rig']['frames']['working']['torso_g'][0][0]=2
        with self.assertRaisesRegex(ValueError,'rigid'):validate(data)

    def test_receipt_rejects_changed_revision_and_coordinate_space(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'contract.json';path.write_text('frozen')
            data=self.target();receipt=binding(path,data,'working')
            verify_binding(receipt,path,data,'working')
            with self.assertRaises(ValueError):verify_binding(receipt,path,data,'runtime')
            data['rig']['revision']='test-v2'
            with self.assertRaises(ValueError):verify_binding(receipt,path,data,'working')
            self.assertEqual(receipt['targetContractSha256'],sha(path))


class DiagnosticTests(unittest.TestCase):
    def test_model_namespace_conversion_retains_equal_named_texture_and_uvs(self):
        source='''newmodel pmh0_head001
setsupermodel pmh0_head001 NULL
beginmodelgeom pmh0_head001
node dummy pmh0_head001
 parent NULL
endnode
node trimesh face
 parent pmh0_head001
 position .1 .2 .3
 orientation 0 0 1 1.5707963267948966
 bitmap pmh0_head001
 verts 3
  1 0 0
  0 1 0
  0 0 1
 tverts 3
  0 0 0
  1 0 0
  0 1 0
endnode
endmodelgeom pmh0_head001
donemodel pmh0_head001
'''
        output=convert_part(source,'pmh0_head001','pmg0_head001',2)
        self.assertIn('newmodel pmg0_head001',output)
        self.assertIn('parent pmg0_head001',output)
        self.assertIn('bitmap pmh0_head001',output)
        self.assertIn('tverts 3\n  0 0 0\n  1 0 0\n  0 1 0',output)
        attachment=np.eye(4);attachment[:3,3]=[3,4,5]
        runtime=attachment.copy();runtime[:3,3]*=2
        np.testing.assert_allclose(points(output,runtime),points(source,attachment)*2,atol=1e-11)


if __name__=='__main__':unittest.main()
