"""Multi-role native hierarchy, attribute bounds and detached transform guards."""
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np

from audit_target_native_part import ascii_meshes, decode, tangent_proof
from target_part_stage import write_model


def fixture(roles=('garment','skin')):
    model = 'pmg0_pelvis001'; root = 232; children = root+0x70
    nodes = [children+4*len(roles)+index*0x270 for index in range(len(roles))]
    faces = [nodes[-1]+0x270+index*32 for index in range(len(roles))]
    raw_offset = faces[-1]+32; raw_size = len(roles)*3*(12+8+12+12+4)
    data = bytearray(12+raw_offset+raw_size)
    struct.pack_into('<III',data,0,0,raw_offset,raw_size)
    def string(at,value):
        blob = value.encode()+b'\0'; data[at:at+len(blob)] = blob
    string(12+8,model); string(12+0xa8,'NULL')
    struct.pack_into('<II',data,12+0x48,root,len(roles)+1)
    data[12+0x72] = 4; struct.pack_into('<f',data,12+0xa4,1)
    string(12+root+32,model); struct.pack_into('<I',data,12+root+0x6c,1)
    struct.pack_into('<III',data,12+root+0x48,children,len(roles),len(roles))
    mesh_names = []; raw_pointer = 0
    for index,(offset,role,face) in enumerate(zip(nodes,roles,faces)):
        at = 12+offset; mesh_name = model+'p'+str(index); mesh_names.append(mesh_name)
        string(at+32,mesh_name); struct.pack_into('<I',data,12+children+index*4,offset)
        struct.pack_into('<I',data,at+0x6c,33); struct.pack_into('<III',data,at+0x78,face,1,1)
        struct.pack_into('<HH',data,at+0x230,3,1); struct.pack_into('<I',data,at+0x248,0xffffffff)
        material = model+('f' if role == 'garment' else '')
        string(at+0xe8,material); string(at+0xe8+3*64,material)
        struct.pack_into('<I',data,at+0xd4,1)
        rows = [np.array([[0,0,0],[1,0,0],[0,1,0]]), np.array([[0,0],[1,0],[0,1]]),
                np.tile([0,0,1],(3,1)),np.tile([1,0,0],(3,1)),np.ones((3,1))]
        for field,row in zip([0x22c,0x234,0x244,0x258,0x260],rows):
            struct.pack_into('<I',data,at+field,raw_pointer)
            blob = row.astype('<f4').tobytes(); start = 12+raw_offset+raw_pointer
            data[start:start+len(blob)] = blob; raw_pointer += len(blob)
        struct.pack_into('<HHH',data,12+face+26,0,1,2)
    return data,model,mesh_names,nodes,raw_offset


class TargetNativePartAuditTests(unittest.TestCase):
    def test_declared_skin_and_garment_meshes_decode_independently(self):
        data,model,names,_,_ = fixture(); decoded,root = decode(data,model,names)
        self.assertEqual(root['name'],model); self.assertEqual(set(decoded),set(names))
        self.assertEqual(decoded[names[0]]['layout']['textureSlots'][0],model+'f')
        self.assertEqual(decoded[names[1]]['layout']['textureSlots'][0],model)
        for native in decoded.values():
            np.testing.assert_array_equal(native['faces'],[[0,1,2]])
            proof = tangent_proof(native)
            self.assertEqual(proof['positiveHandednessVertices'],3)
            self.assertEqual(proof['faceUvDirectionCosinesDiagnosticOnly']['tangent']['minimum'],1)

    def test_hierarchy_rejects_missing_extra_nested_and_cyclic_nodes(self):
        data,model,names,nodes,_ = fixture()
        with self.assertRaises(ValueError): decode(data,model,names[:1])
        for change in ['skin','nested','cycle','count']:
            changed = data.copy()
            if change == 'skin': struct.pack_into('<I',changed,12+nodes[0]+0x6c,97)
            if change == 'nested': struct.pack_into('<III',changed,12+nodes[0]+0x48,344,1,1)
            if change == 'cycle': struct.pack_into('<I',changed,12+344,232)
            if change == 'count': struct.pack_into('<I',changed,12+0x4c,4)
            with self.subTest(change=change),self.assertRaises(ValueError): decode(changed,model,names)

    def test_missing_outside_nonfinite_and_wrong_sign_arrays_rejected(self):
        for change in ['missing','outside','nonfinite','sign','index','color']:
            data,model,names,nodes,raw = fixture(); at = 12+nodes[0]
            if change == 'missing': struct.pack_into('<I',data,at+0x258,0xffffffff)
            if change == 'outside': struct.pack_into('<I',data,at+0x258,999999)
            if change == 'color': struct.pack_into('<I',data,at+0x248,0)
            if change in ('nonfinite','sign'):
                field = 0x244 if change == 'nonfinite' else 0x260
                pointer = struct.unpack_from('<I',data,at+field)[0]
                struct.pack_into('<f',data,12+raw+pointer,float('nan') if change == 'nonfinite' else 0)
            if change == 'index':
                face = struct.unpack_from('<I',data,at+0x78)[0]; struct.pack_into('<H',data,12+face+26,3)
            with self.subTest(change=change),self.assertRaises(ValueError): decode(data,model,names)

    def test_material_or_transform_controller_cannot_hide_in_native(self):
        data,model,names,nodes,raw = fixture()
        # Put a static position controller in model bytes otherwise unused by the
        # structural fixture; it must be identity before any geometry proof.
        keys,values = 200,180
        at = 12+nodes[0]
        struct.pack_into('<III',data,at+0x54,keys,1,1)
        struct.pack_into('<III',data,at+0x60,values,4,4)
        struct.pack_into('<ihhhbb',data,12+keys,8,1,0,1,3,0)
        struct.pack_into('<ffff',data,12+values,0,.01,0,0)
        with self.assertRaisesRegex(ValueError,'Nonidentity'): decode(data,model,names)
        struct.pack_into('<ffff',data,12+values,0,0,0,0)
        decode(data,model,names)

    def test_ascii_roles_preserve_grouped_ordered_corners_and_block_scale(self):
        p = np.asarray([[[0,0,0],[1,0,0],[0,1,0]],[[0,0,1],[1,0,1],[0,1,1]]],float)
        n = np.tile([0,0,1],(2,3,1)); uv = p[...,:2].copy(); model = 'pmg0_pelvis001'
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'test.mdl'; write_model(path,model,p,n,uv,['skin','garment'])
            text = path.read_text(); parsed = ascii_meshes(text,model,['skin','garment'])
            np.testing.assert_array_equal(parsed[model+'p0']['corners']['position'],p[1:])
            np.testing.assert_array_equal(parsed[model+'p1']['corners']['position'],p[:1])
            self.assertEqual(parsed[model+'p0']['material'],model+'f')
            for change in [text.replace('  position 0 0 0','  position .1 0 0'),
                           text.replace('  position 0 0 0','  position 0 0 0\n  scale 1.428571'),
                           text.replace('node trimesh '+model+'p0','node skin '+model+'p0')]:
                with self.assertRaises(ValueError): ascii_meshes(change,model,['skin','garment'])


if __name__ == '__main__': unittest.main()
