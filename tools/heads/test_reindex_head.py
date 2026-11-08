"""Native head renames preserve all non-name bytes and reject ambiguous layouts."""
import struct
import unittest
from reindex_head import rename_native

def fixture():
    name='pmg0_head033'; section=0x600; raw=96
    data=bytearray(12+section+raw)
    struct.pack_into('<III',data,0,0,section,raw)
    data[20:20+len(name)]=name.encode()
    struct.pack_into('<II',data,12+0x48,0x100,2)
    root,mesh=12+0x100,12+0x180
    for at,value in ((root+32,name),(mesh+32,name+'p0'),(mesh+0xe8,name),(mesh+0xe8+192,name)):
        data[at:at+len(value)]=value.encode()
    struct.pack_into('<I',data,root+0x6c,1)
    struct.pack_into('<III',data,root+0x48,0x480,1,1)
    struct.pack_into('<I',data,12+0x480,0x180)
    struct.pack_into('<I',data,mesh+0x6c,33)
    struct.pack_into('<III',data,mesh+0x78,0x500,1,1)
    struct.pack_into('<3H',data,12+0x500+26,0,1,2)
    struct.pack_into('<HH',data,mesh+0x230,3,1)
    for field,pointer in ((0x22c,0),(0x234,36),(0x244,60),(0x258,0xffffffff),(0x260,0xffffffff)):
        struct.pack_into('<I',data,mesh+field,pointer)
    struct.pack_into('<9f',data,12+section,0,0,0,0,1,0,0,0,1)
    struct.pack_into('<6f',data,12+section+36,0,0,1,0,0,1)
    struct.pack_into('<9f',data,12+section+60,1,0,0,1,0,0,1,0,0)
    return bytes(data)

class ReindexTests(unittest.TestCase):
    def test_changes_only_declared_name_fields_and_roundtrips_exactly(self):
        original=fixture();result,report=rename_native(original,'pmg0_head033','pmg0_head017')
        self.assertEqual(len(report['renames']),5)
        self.assertEqual(report['triangles'],1)
        allowed=set()
        for row in report['renames']:allowed.update(range(row['offset'],row['offset']+len(row['before'])))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(original,result)) if a!=b))
        restored,_=rename_native(result,'pmg0_head017','pmg0_head033')
        self.assertEqual(original,restored)
    def test_unknown_name_and_external_texture_refuse(self):
        for at,text in ((12+0x550,b'pmg0_head033'),(12+0x180+0xe8,b'foreignhead')):
            data=bytearray(fixture());data[at:at+len(text)]=text
            with self.assertRaises(ValueError):rename_native(bytes(data),'pmg0_head033','pmg0_head017')
    def test_wrong_header_prefix_and_animation_refuse(self):
        with self.assertRaises(ValueError):rename_native(fixture(),'pmg0_head033','pfg0_head017')
        for at,value in ((20,ord('x')),(12+0x7c,1),(12+0x4c,3)):
            data=bytearray(fixture());data[at]=value
            with self.assertRaises(ValueError):rename_native(bytes(data),'pmg0_head033','pmg0_head017')

if __name__=='__main__':unittest.main()
