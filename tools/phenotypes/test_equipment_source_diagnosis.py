import unittest
import struct
import numpy as np
from audit_native_static_equipment import decode_static_equipment
from diagnose_equipment_gff_sources import equipment_claims


def fixture():
    model_size=0x800;raw_size=96
    b=bytearray(12+model_size+raw_size)
    def pack(fmt,offset,*values):struct.pack_into('<'+fmt,b,12+offset,*values)
    struct.pack_into('<III',b,0,0,model_size,raw_size)
    b[20:25]=b'helm\0';pack('II',0x48,0xe8,2)
    for o,flags in ((0xe8,1),(0x15c,33)):
        b[12+o+32:12+o+37]=b'helm\0';pack('I',o+0x6c,flags)
    pack('III',0xe8+0x48,0x158,1,1);pack('I',0x158,0x15c)
    root_values=[0,1,2,3,0,0,0,np.sqrt(.5),np.sqrt(.5)]
    mesh_values=[0,.5,0,0,0,0,0,0,1,0,2]
    for o,keys,values,count,rows in ((0xe8,0x600,0x650,2,root_values),(0x15c,0x680,0x6d0,3,mesh_values)):
        pack('III',o+0x54,keys,count,count);pack('III',o+0x60,values,len(rows),len(rows))
        pack('ihhhbb',keys,8,1,0,1,3,0);pack('ihhhbb',keys+12,20,1,4,5,4,0)
        if count==3:pack('ihhhbb',keys+24,36,1,9,10,1,0)
        pack(str(len(rows))+'f',values,*rows)
    mesh=0x15c
    pack('III',mesh+0x78,0x720,1,1);pack('3H',0x720+26,0,1,2)
    pack('I',mesh+0xdc,1);b[12+mesh+0xe8:12+mesh+0xe8+4]=b'tex\0'
    pack('I',mesh+0x22c,0);pack('HH',mesh+0x230,3,1);pack('I',mesh+0x234,72);pack('I',mesh+0x244,36)
    struct.pack_into('<9f',b,12+model_size,0,0,0,1,0,0,0,1,0)
    struct.pack_into('<9f',b,12+model_size+36,0,0,1,0,0,1,0,0,1)
    struct.pack_into('<6f',b,12+model_size+72,0,0,1,0,0,1)
    return b


class NativeEquipmentTests(unittest.TestCase):
    def test_duplicate_labels_preserve_pointer_tree_and_world_transform(self):
        result=decode_static_equipment(fixture())
        self.assertEqual(result['duplicateNames'],['helm'])
        self.assertEqual(result['nodes'][1]['parentByChildTraversal'],0xe8)
        self.assertEqual(result['nodes'][1]['storedParentPointer'],0)
        np.testing.assert_allclose(result['meshes'][0]['worldPositions'],[[1,2.5,3],[1,4.5,3],[-1,2.5,3]],atol=1e-7)
        np.testing.assert_array_equal(result['meshes'][0]['faces'],[[0,1,2]])
        np.testing.assert_array_equal(result['meshes'][0]['uv'][0],[[0,0],[1,0],[0,1]])
        np.testing.assert_allclose(result['meshes'][0]['worldNormals'],[[0,0,1]]*3,atol=1e-7)

    def test_rejects_native_child_cycle(self):
        b=fixture();struct.pack_into('<I',b,12+0x158,0xe8)
        with self.assertRaisesRegex(ValueError,'cycle'):decode_static_equipment(b)

    def test_rejects_truncation_and_declared_count_mismatch(self):
        b=fixture()
        with self.assertRaisesRegex(ValueError,'sections'):decode_static_equipment(b[:-1])
        struct.pack_into('<I',b,12+0x4c,3)
        with self.assertRaisesRegex(ValueError,'node count'):decode_static_equipment(b)

    def test_rejects_unsupported_skin_and_local_animations(self):
        b=fixture();struct.pack_into('<I',b,12+0x15c+0x6c,97)
        with self.assertRaisesRegex(ValueError,'dummy/trimesh'):decode_static_equipment(b)
        b=fixture();struct.pack_into('<III',b,12+0x78,0x7c0,1,1)
        with self.assertRaisesRegex(ValueError,'Animated'):decode_static_equipment(b)

    def test_rejects_invalid_native_arrays_and_quaternion(self):
        b=fixture();struct.pack_into('<I',b,12+0x15c+0x22c,95)
        with self.assertRaisesRegex(ValueError,'raw section'):decode_static_equipment(b)
        b=fixture();struct.pack_into('<f',b,12+0x650+5*4,2)
        with self.assertRaisesRegex(ValueError,'quaternion'):decode_static_equipment(b)

    def test_gff_nested_inventory_and_cloak_row_not_mesh_id(self):
        def item(base,**fields):return {k:{'type':'int' if k=='BaseItem' else 'byte','value':v} for k,v in {'BaseItem':base,**fields}.items()}
        source={'ItemList':{'type':'list','value':[item(16,ArmorPart_Robe=1,ArmorPart_LShoul=255),item(80,ModelPart1=7),item(80,ModelPart1=10),item(17,ModelPart1=19)]}}
        result=equipment_claims(source)
        self.assertEqual(result[0]['diagnosticFlags'],['robe001','shoulder255'])
        self.assertEqual(result[1]['diagnosticFlags'],[])
        self.assertEqual(result[2]['diagnosticFlags'],['cloak007-table-row10'])
        self.assertEqual(result[3]['diagnosticFlags'],['helmet019'])
        self.assertEqual(result[3]['path'],'/ItemList/value/3')


if __name__=='__main__':unittest.main()
