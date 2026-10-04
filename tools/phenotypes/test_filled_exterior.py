"""A measured solid extraction must be closed, oriented, and retain a through opening."""
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from extract_filled_exterior import extract,topology,export
from inspect_generated_part_topology import load
from place_purposebuilt_pelvis import read_glb,write_glb


class FilledExterior(unittest.TestCase):
    def test_solid_and_tunnel_have_closed_outward_surfaces(self):
        grid=np.zeros((11,11,7),bool);grid[2:9,2:9,2:5]=True
        p,n,f=extract(grid,np.zeros(3),1.)
        self.assertEqual(topology(p,f)['boundaryEdges'],0)
        self.assertTrue(np.isfinite(n).all())
        grid[4:7,4:7,:]=False
        p,n,f=extract(grid,np.zeros(3),1.)
        self.assertEqual(topology(p,f)['nonmanifoldEdges'],0)
        # The axial center line stays clear. No projected triangle contains it.
        xy=p[f][:,:,:2];point=np.array([5.5,5.5]);edge=np.roll(xy,-1,axis=1)-xy
        delta=point-xy;cross=edge[:,:,0]*delta[:,:,1]-edge[:,:,1]*delta[:,:,0]
        covered=(np.all(cross>=0,axis=1)|np.all(cross<=0,axis=1))
        # Collinear projections are side walls; discard their zero area.
        a=xy[:,1]-xy[:,0];b=xy[:,2]-xy[:,0]
        area=np.abs(a[:,0]*b[:,1]-a[:,1]*b[:,0])
        self.assertFalse(np.any(covered&(area>0)))

    def test_boundary_contact_requires_explicit_padding(self):
        grid=np.ones((3,3,3),bool)
        with self.assertRaisesRegex(RuntimeError,'touches grid boundary'):extract(grid,np.zeros(3),1.)

    def test_diagonal_cells_do_not_propagate_inconsistent_winding(self):
        grid=np.zeros((5,5,5),bool);grid[1,1,1]=True;grid[2,2,2]=True
        p,n,f=extract(grid,np.zeros(3),1.)
        self.assertEqual(topology(p,f)['inconsistentManifoldEdgeWindings'],0)

    def test_diagnostic_name_is_allowed_but_transform_is_rejected(self):
        grid=np.zeros((4,4,4),bool);grid[1:3,1:3,1:3]=True
        p,n,f=extract(grid,np.zeros(3),1.)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'exterior.glb';export(path,p,n,f)
            actual,faces,normals=load(path)
            self.assertTrue(np.array_equal(actual,p))
            self.assertTrue(np.array_equal(faces,f))
            self.assertTrue(np.array_equal(normals,n))
            document,binary=read_glb(path)
            document['nodes'][0]['translation']=[0,0,1]
            write_glb(path,document,binary)
            with self.assertRaisesRegex(RuntimeError,'identity-node'):load(path)


if __name__=='__main__':unittest.main()
