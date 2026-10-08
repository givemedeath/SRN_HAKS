"""Stock sections use actual triangles and declared attachment frames."""
import unittest
import numpy as np
from measure_stock_target_basis import section_points,ascii_world_triangles


class StockBasisTests(unittest.TestCase):
    def test_joint_plane_uses_triangle_edges_and_keeps_exact_coplanar_vertices(self):
        tri=np.array([[[0.,0,-1],[2,0,1],[0,2,1]],[[0,0,0],[1,0,0],[0,1,0]]])
        points=section_points(tri,[0,0,0],[0,0,2],0)
        self.assertEqual({tuple(point) for point in points},{(1.,0.,0.),(0.,1.,0.),(0.,0.,0.)})
        self.assertEqual(len(section_points(tri,[0,0,0],[0,0,1],2)),0)
        with self.assertRaises(ValueError):section_points(tri,[0,0,0],[0,0,0],0)

    def test_stock_mesh_local_hierarchy_and_attachment_both_apply(self):
        text='newmodel body\nbeginmodelgeom body\nnode dummy body\n parent NULL\n position 1 0 0\nendnode\nnode trimesh surface\n parent body\n position 0 2 0\n verts 3\n 0 0 0\n 1 0 0\n 0 1 0\n faces 1\n 0 1 2 1 0 1 2 1\nendnode\nendmodelgeom body\n'
        attachment=np.eye(4);attachment[:3,3]=[0,0,3]
        np.testing.assert_array_equal(ascii_world_triangles(text,attachment),[[[1,2,3],[2,2,3],[1,3,3]]])


if __name__=='__main__':unittest.main()
