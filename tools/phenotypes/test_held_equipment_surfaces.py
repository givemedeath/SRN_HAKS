import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from review_held_equipment_surfaces import point_triangle_distances,segment_distances,surface_distance,placed_surface,verify_held_binding,structural_equivalence,SOCKETS
import target_contract


class HeldSurfaceTests(unittest.TestCase):
    def test_point_projection_edges_and_degenerate_triangle(self):
        tri=np.array([[0.,0,0],[1,0,0],[0,1,0]])
        self.assertAlmostEqual(float(point_triangle_distances([.2,.2,2],tri)),2)
        self.assertAlmostEqual(float(point_triangle_distances([2,0,0],tri)),1)
        deg=np.array([[0.,0,0],[1,0,0],[1,0,0]])
        self.assertAlmostEqual(float(point_triangle_distances([.5,1,0],deg)),1)

    def test_edge_segment_minima_interior_clamped_parallel(self):
        self.assertAlmostEqual(float(segment_distances(np.array([0.,0,0]),np.array([1.,0,0]),np.array([.5,-1,1]),np.array([.5,1,1]))),1)
        self.assertAlmostEqual(float(segment_distances(np.array([0.,0,0]),np.array([1.,0,0]),np.array([2.,1,0]),np.array([3.,1,0]))),np.sqrt(2))
        self.assertAlmostEqual(float(segment_distances(np.array([0.,0,0]),np.array([1.,0,0]),np.array([.2,1,0]),np.array([.8,1,0]))),1)

    def test_crossing_edge_in_face_without_vertex_contact(self):
        a=np.array([[[0.,0,0],[2,0,0],[0,2,0]]])
        b=np.array([[[.5,.5,-1],[.5,.5,1],[1.5,.5,1]]])
        r=surface_distance(a,b)
        self.assertEqual(r['minimumSurfaceDistanceMeters'],0)
        self.assertEqual(r['surfaceContactTrianglePairs'],1)
        self.assertFalse(r['collisionAccepted'])

    def test_overlapping_bounds_do_not_prove_contact(self):
        a=np.array([[[0.,0,0],[2,0,0],[0,2,0]]])
        b=np.array([[[1.2,1.2,0],[2,1.2,0],[1.2,2,0]]])
        r=surface_distance(a,b)
        self.assertAlmostEqual(r['minimumSurfaceDistanceMeters'],np.sqrt(.08))
        self.assertEqual(r['surfaceContactTrianglePairs'],0)
        self.assertFalse(r['solidContainmentChecked'])

    def test_coplanar_contact_and_parallel_separation(self):
        a=np.array([[[0.,0,0],[2,0,0],[0,2,0]]]);b=a*.25
        self.assertEqual(surface_distance(a,b)['surfaceContactTrianglePairs'],1)
        b[:,:,2]+=3
        self.assertAlmostEqual(surface_distance(a,b)['minimumSurfaceDistanceMeters'],3)

    def test_uniform_scale_proper_rotation_translation_and_symmetry(self):
        a=np.array([[[0.,0,0],[1,0,0],[0,1,0]]]);b=a.copy();b[:,:,2]=2
        frame=np.eye(4);frame[:3,:3]=[[0,-1,0],[1,0,0],[0,0,1]];frame[:3,3]=[4,-8,10]
        aa=placed_surface(a,frame,10/7);bb=placed_surface(b,frame,10/7)
        self.assertAlmostEqual(surface_distance(aa,bb)['minimumSurfaceDistanceMeters'],20/7)
        self.assertAlmostEqual(surface_distance(bb,aa)['minimumSurfaceDistanceMeters'],20/7)
        self.assertTrue(np.allclose(aa[0,0],[4,-8,10]))
        bad=frame.copy();bad[0,0]=-1
        with self.assertRaises(ValueError):placed_surface(a,bad,1)
        with self.assertRaises(ValueError):placed_surface(a,frame,0)

    def test_stale_socket_and_wrong_coordinate_binding_rejected(self):
        # Minimal binding fixture avoids duplicating the full target-contract implementation.
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'contract.json';path.write_text('{}')
            data={'id':'test','rig':{'revision':'rev','frames':{'runtime':{name:np.eye(4).tolist() for name in SOCKETS}}}}
            receipt={'target':{**target_contract.binding(path,data,'runtime'),'socketFramesNwn':{name:np.eye(4).tolist() for name in SOCKETS}},'profilesAccepted':False,'clientAccepted':False}
            verify_held_binding(receipt,path,data)
            receipt['target']['socketFramesNwn']['head_g'][0][3]=.01
            with self.assertRaises(ValueError):verify_held_binding(receipt,path,data)
            receipt['target']['socketFramesNwn']['head_g'][0][3]=0
            receipt['target']['coordinateSpace']='working'
            with self.assertRaises(ValueError):verify_held_binding(receipt,path,data)


    def test_structural_metadata_change_does_not_adopt_prior_receipts(self):
        source={'id':'test','models':{'head':'pmg0_head001'},'rig':{'revision':'v6','pilotAccepted':False,'frames':{'runtime':{'head_g':np.eye(4).tolist()}},'privateAliases':{'pmh0':'pmg0'}}}
        frozen=json.loads(json.dumps(source));frozen['rig']['revision']='offline-frozen';frozen['rig']['pilotAccepted']=True
        frozen['acceptance']={'rigStructureOffline':True,'client':False}
        self.assertEqual(len(structural_equivalence(source,frozen)),64)
        frozen['rig']['frames']['runtime']['head_g'][0][3]=.001
        with self.assertRaises(ValueError):structural_equivalence(source,frozen)

    def test_model_identity_or_private_alias_change_is_not_equivalent(self):
        source={'id':'test','models':{'head':'pmg0_head001'},'rig':{'frames':{},'privateAliases':{'pmh0':'pmg0'}}}
        for section,key,value in (('models','head','pmg0_head002'),('rig','privateAliases',{'pmh0':'other'})):
            frozen=json.loads(json.dumps(source));frozen[section][key]=value
            with self.assertRaises(ValueError):structural_equivalence(source,frozen)


if __name__=='__main__':unittest.main()

