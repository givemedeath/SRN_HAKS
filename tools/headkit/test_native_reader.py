"""Portable native donor-transform fixtures, independent of external compilers."""
import math
import struct
import unittest
import numpy as np
from .native_reader import decode


def donor(position=(1,2,3),rotation=(0,0,math.sqrt(.5),math.sqrt(.5)),scale=2):
    section=0x400;raw=96;data=bytearray(12+section+raw)
    struct.pack_into('<III',data,0,0,section,raw)
    root=12;mesh=12+0x80
    data[root+32:root+37]=b'model';struct.pack_into('<I',data,root+0x6c,1)
    struct.pack_into('<III',data,root+0x48,0x300,1,1)
    struct.pack_into('<I',data,12+0x300,0x80)
    data[mesh+32:mesh+36]=b'part';struct.pack_into('<I',data,mesh+0x6c,33)
    struct.pack_into('<III',data,mesh+0x54,0x310,3,3)
    struct.pack_into('<III',data,mesh+0x60,0x340,8,8)
    for i,(kind,start,width) in enumerate(((8,0,3),(20,3,4),(36,7,1))):
        struct.pack_into('<ihhhbb',data,12+0x310+12*i,kind,1,0,start,width,0)
    struct.pack_into('<8f',data,12+0x340,*position,*rotation,scale)
    struct.pack_into('<III',data,mesh+0x78,0x380,1,1)
    struct.pack_into('<3H',data,12+0x380+26,0,1,2)
    struct.pack_into('<HH',data,mesh+0x230,3,1)
    for field,pointer in ((0x22c,0),(0x234,36),(0x244,60),(0x258,0xffffffff),(0x260,0xffffffff)):
        struct.pack_into('<I',data,mesh+field,pointer)
    struct.pack_into('<9f',data,12+section,0,0,0,0,1,0,0,0,1)
    struct.pack_into('<6f',data,12+section+36,0,0,1,0,0,1)
    struct.pack_into('<9f',data,12+section+60,1,0,0,1,0,0,1,0,0)
    return bytes(data)


class NativeDonorTransformTests(unittest.TestCase):
    def test_constant_alpha_requires_opt_in_and_preserves_corner_attributes(self):
        original=donor(position=(0,0,0),rotation=(0,0,0,1),scale=1)
        data=bytearray(original);node=12+0x80
        data[12+0x3a0:12+0x3a0+36]=data[12+0x310:12+0x310+36]
        struct.pack_into('<III',data,node+0x54,0x3a0,4,4)
        struct.pack_into('<III',data,node+0x60,0x340,9,9)
        struct.pack_into('<ihhhbb',data,12+0x3a0+36,128,1,0,8,1,0)
        struct.pack_into('<f',data,12+0x360,.3)
        with self.assertRaisesRegex(ValueError,'Unsupported animated'):
            decode(bytes(data),'model',require_tangents=False)
        before,=decode(original,'model',require_tangents=False)
        after,=decode(bytes(data),'model',require_tangents=False,allow_constant_alpha=True)
        self.assertAlmostEqual(after['alpha'],.3,places=6)
        for key in ('position','normal','uv','faces'):
            np.testing.assert_array_equal(before[key],after[key])
        for value in (-.1,1.1,float('nan')):
            struct.pack_into('<f',data,12+0x360,value)
            with self.assertRaisesRegex(ValueError,'alpha outside'):
                decode(bytes(data),'model',require_tangents=False,allow_constant_alpha=True)
        struct.pack_into('<f',data,12+0x360,.3)
        struct.pack_into('<III',data,node+0x54,0x3a0,5,5)
        struct.pack_into('<ihhhbb',data,12+0x3a0+48,128,1,0,8,1,0)
        with self.assertRaisesRegex(ValueError,'Invalid static mesh alpha'):
            decode(bytes(data),'model',require_tangents=False,allow_constant_alpha=True)

    def test_final_export_default_remains_strict(self):
        with self.assertRaisesRegex(ValueError,'Nonidentity'):
            decode(donor(),'model',require_tangents=False)

    def test_explicit_donor_transform_preserves_uv_and_maps_positions_normals(self):
        mesh,=decode(donor(),'model',require_tangents=False,apply_rigid_transforms=True)
        np.testing.assert_allclose(mesh['position'],[[1,2,3],[-1,2,3],[1,2,5]],atol=1e-6)
        np.testing.assert_allclose(mesh['normal'],[[0,1,0]]*3,atol=1e-6)
        np.testing.assert_array_equal(mesh['uv'],[[0,0],[1,0],[0,1]])
        np.testing.assert_array_equal(mesh['faces'],[[0,1,2]])

    def test_identity_donor_path_matches_original_attributes(self):
        data=donor(position=(0,0,0),rotation=(0,0,0,1),scale=1)
        before,=decode(data,'model',require_tangents=False)
        after,=decode(data,'model',require_tangents=False,apply_rigid_transforms=True)
        for key in ('position','normal','uv','faces'):np.testing.assert_array_equal(before[key],after[key])

    def test_invalid_donor_controllers_reject(self):
        for data in (donor(scale=0),donor(scale=-1),donor(rotation=(0,0,0,0)),donor(position=(float('nan'),0,0))):
            with self.subTest(data=data[:12]),self.assertRaises(ValueError):
                decode(data,'model',require_tangents=False,apply_rigid_transforms=True)


if __name__=='__main__':unittest.main()
