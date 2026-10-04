"""Native node names can also occur as material names; cost decoding must distinguish them."""
import struct
import unittest
from measure_effective_body_costs import mesh_counts,mip_pixels


class CostMeasurement(unittest.TestCase):
    def test_repeated_material_name_does_not_duplicate_native_geometry(self):
        data=bytearray(1036);struct.pack_into('<III',data,0,0,1024,0)
        node=12;name=b'bodyp\0';data[node+32:node+32+len(name)]=name
        data[850:850+len(name)]=name
        struct.pack_into('<I',data,node+0x6c,33)
        struct.pack_into('<III',data,node+0x78,950,1,1)
        struct.pack_into('<HH',data,node+0x230,3,1)
        text='node trimesh bodyp\n verts 3\n0 0 0\n1 0 0\n0 1 0\n faces 1\n0 1 2 1 0 1 2 0\nendnode\nendmodelgeom\n'
        self.assertEqual(mesh_counts(bytes(data),text),[{'node':'bodyp','vertices':3,'triangles':1}])
        struct.pack_into('<I',data,node+0x6c,0)
        with self.assertRaisesRegex(RuntimeError,'typed native mesh'):mesh_counts(bytes(data),text)

    def test_mip_chain_counts_non_square_and_one_pixel_terminal(self):
        self.assertEqual(mip_pixels(4,2),8+2+1)
        self.assertEqual(mip_pixels(1,1),1)
        self.assertEqual(mip_pixels(2048,2048),5592405)


if __name__=='__main__':unittest.main()
