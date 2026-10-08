"""Numerical checks for independent offline pose measurement, not engine claims."""
import unittest
import numpy as np

from retarget import nodes, rotations
from rig_controller_audit import arrays, controller_signature, preserved_controller_signature
from rig_pose_audit import interpolate, sample, inherited_clips
from audit_target_rig import find_bind


class PoseAuditTests(unittest.TestCase):
    def test_independent_source_and_target_lookup_honors_nearest_owner(self):
        child={'joint':{'position':[1,2,3]}}
        parent={'joint':{'position':[10,20,30]},'inherited':{'position':[4,5,6]}}
        hierarchy={'child':'parent','parent':'null'}
        geometry={'child':child,'parent':parent}
        self.assertIs(find_bind('joint','child',geometry,hierarchy,{})[0],child['joint'])
        self.assertEqual(find_bind('inherited','child',geometry,hierarchy,{})[1],'parent')
        fallback={'socket':{'position':[7,8,9]}}
        self.assertIs(find_bind('socket','child',geometry,hierarchy,fallback)[0],fallback['socket'])
        with self.assertRaisesRegex(ValueError,'Unresolved'):
            find_bind('missing','child',geometry,hierarchy,{})
        with self.assertRaisesRegex(ValueError,'cycle'):
            find_bind('missing','child',geometry,{'child':'parent','parent':'child'}, {})

    def test_count_and_endlist_controller_encodings_have_equal_inventory(self):
        counted='  positionkey 2\n   0 1 2 3\n   1 2 3 4\n'
        listed='  positionkey\n   0 1 2 3\n   1 2 3 4\n  endlist\n'
        self.assertEqual(arrays(counted)[0][:2],arrays(listed)[0][:2])
        self.assertEqual(arrays(listed)[0][3],len(listed))
        with self.assertRaisesRegex(ValueError,'endlist'):
            arrays(listed.replace('  endlist\n',''))

    def test_linear_position_times_and_endpoint_clamping(self):
        rows=[[.2,1,2,3],[.6,3,6,9]]
        self.assertEqual(interpolate(rows,0),[1,2,3])
        self.assertEqual(interpolate(rows,1),[3,6,9])
        np.testing.assert_allclose(interpolate(rows,.4),[2,4,6])
        with self.assertRaisesRegex(ValueError,'times'):
            interpolate(list(reversed(rows)),.4)

    def test_rotation_slerp_preserves_shortest_path_across_pi(self):
        output=interpolate([[0,0,0,1,np.deg2rad(170)],
                            [1,0,0,1,np.deg2rad(-170)]],.5,True)
        np.testing.assert_allclose(rotations(output),np.diag([-1,-1,1]),atol=1e-12)

    def test_pose_parent_rotation_places_child_without_double_translation(self):
        rig=nodes('''node dummy root
parent NULL
position 2 3 4
endnode
node dummy joint
parent root
position 1 0 0
endnode
''')
        pose=sample(rig,'''node dummy root
parent NULL
orientationkey 2
 0 0 0 1 0
 1 0 0 1 3.141592653589793
endnode
node dummy joint
parent root
positionkey 2
 0 1 0 0
 1 3 0 0
endnode
''',.5)
        np.testing.assert_allclose(pose['joint'][:3,3],[2,5,4],atol=1e-12)

    def test_bezier_sampler_fails_closed_instead_of_using_linear_endpoints(self):
        rig=nodes('node dummy root\nparent NULL\nendnode\n')
        with self.assertRaisesRegex(ValueError,'Bezier'):
            sample(rig,'node dummy root\nparent NULL\npositionbezierkey 2\n'
                   ' 0 1 2 3 0 0 0 0 0 0\n 1 4 5 6 0 0 0 0 0 0\nendnode\n',.5)

    def test_inherited_clip_owner_and_pause_variants_remain_distinct(self):
        child='newanim pause1 child\nlength 1\ndoneanim pause1 child\n'
        parent=('newanim pause1 parent\nlength 2\ndoneanim pause1 parent\n'
                'newanim pause2 parent\nlength 3\ndoneanim pause2 parent\n')
        result=inherited_clips(['child','parent'],{'child':child,'parent':parent})
        self.assertEqual(result['pause1']['owner'],'child')
        self.assertEqual(result['pause1']['length'],1)
        self.assertEqual(result['pause2']['owner'],'parent')
        self.assertEqual(result['pause2']['length'],3)

    def test_all_controller_types_and_static_rotations_are_frozen(self):
        original=('newanim a root\nlength 1\nnode dummy j\nparent root\n'
                  'orientation 0 0 1 .2\nalpha .7\npositionkey 1\n 0 1 2 3\n'
                  'orientationkey 1\n 0 0 0 1 .3\nendnode\ndoneanim a root\n')
        changed=original.replace('0 1 2 3','0 4 5 6')
        self.assertEqual(preserved_controller_signature(changed),
                         preserved_controller_signature(original))
        for after in [changed.replace('alpha .7','alpha .8'),
                      changed.replace('orientation 0 0 1 .2','orientation 0 0 1 .5'),
                      changed.replace('0 0 0 1 .3','0 0 0 1 .9')]:
            self.assertNotEqual(preserved_controller_signature(after),
                                preserved_controller_signature(original))


if __name__=='__main__':unittest.main()
