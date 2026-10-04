"""Focused decoder/transport negatives; actual compiled files audited separately."""
import struct
import unittest

import numpy as np
from audit_native_limb_shading import decode, validate_transport, validate_target


def fixture():
    model = 'pmh0_legl001'; node = 64; face_offset = node + 0x264 - 12
    raw_offset = face_offset + 32; raw_size = 3 * (12 + 8 + 12 + 12 + 4)
    data = bytearray(12 + raw_offset + raw_size)
    struct.pack_into('<III', data, 0, 0, raw_offset, raw_size)
    name = (model + 'p').encode() + b'\0'; data[node + 32:node + 32 + len(name)] = name
    struct.pack_into('<I', data, node + 0x6c, 33)
    struct.pack_into('<III', data, node + 0x78, face_offset, 1, 1)
    struct.pack_into('<HH', data, node + 0x230, 3, 1)
    pointer_fields = [0x22c, 0x234, 0x244, 0x258, 0x260]
    rows = [np.eye(3), np.array([[0., 0.], [1., 0.], [0., 1.]]),
            np.tile([0., 0., 1.], (3, 1)), np.tile([1., 0., 0.], (3, 1)), np.ones((3, 1))]
    offset = 0
    for field, row in zip(pointer_fields, rows):
        struct.pack_into('<I', data, node + field, offset)
        blob = row.astype('<f4').tobytes(); data[12 + raw_offset + offset:12 + raw_offset + offset + len(blob)] = blob
        offset += len(blob)
    struct.pack_into('<HHH', data, 12 + face_offset + 26, 0, 1, 2)
    return data, node, raw_offset


class NativeLimbAuditTests(unittest.TestCase):
    def test_explicit_thigh_shin_targets_and_cross_family_model_rejections(self):
        joints={'legl':'lthigh_g','legr':'rthigh_g','shinl':'lshin_g','shinr':'rshin_g','footl':'lfoot_g','footr':'rfoot_g',
                'bicepl':'lbicep_g','bicepr':'rbicep_g','forel':'lforearm_g','forer':'rforearm_g','handl':'lhand_g','handr':'rhand_g'}
        for part,joint in joints.items():
            good={'part':part,'model':'pmh0_'+part+'001','joint':joint}
            self.assertEqual(validate_target(good),(part,good['model']))
            for key,value in [('joint','rthigh_g' if joint!='rthigh_g' else 'lshin_g'),
                              ('model','pmh0_handl001' if part!='handl' else 'pmh0_handr001'),('model','pfh0_'+part+'001'),
                              ('model','pmh0'),('part','chest'),('part','head')]:
                with self.subTest(part=part,key=key,value=value),self.assertRaises(ValueError):
                    validate_target({**good,key:value})

    def test_valid_structural_fixture(self):
        data, _, _ = fixture(); result = decode(data, 'pmh0_legl001')
        self.assertEqual(result['layout']['triangles'], 1)
        np.testing.assert_array_equal(result['faces'], [[0, 1, 2]])

    def test_truncated_or_wrong_model(self):
        data, _, _ = fixture()
        for candidate, model in [(data[:-1], 'pmh0_legl001'), (data, 'pmh0_legr001')]:
            with self.assertRaises(ValueError): decode(candidate, model)

    def test_missing_or_outside_tangent(self):
        for pointer in [0xffffffff, 999999]:
            data, node, _ = fixture(); struct.pack_into('<I', data, node + 0x258, pointer)
            with self.assertRaises(ValueError): decode(data, 'pmh0_legl001')

    def test_invalid_handedness_or_nonfinite(self):
        for value in [0., float('nan')]:
            data, node, raw_offset = fixture(); pointer = struct.unpack_from('<I', data, node + 0x260)[0]
            struct.pack_into('<f', data, 12 + raw_offset + pointer, value)
            with self.assertRaises(ValueError): decode(data, 'pmh0_legl001')

    def test_invalid_indices_or_skin_node(self):
        for field, value in [(0x6c, 97), (0x230, 2)]:
            data, node, _ = fixture()
            if field == 0x230: struct.pack_into('<H', data, node + field, value)
            else: struct.pack_into('<I', data, node + field, value)
            with self.assertRaises(ValueError): decode(data, 'pmh0_legl001')

    def test_transport_only_float32_rounding(self):
        source = {'position': np.array([[[.123456789, 0., 0.], [1., 0., 0.], [0., 1., 0.]]]),
                  'normal': np.tile([0., 0., 1.], (1, 3, 1)),
                  'uv': np.array([[[0., 0.], [1., 0.], [0., 1.]]])}
        ascii_corners = {key: value.copy() for key, value in source.items()}
        native = {key: value.astype(np.float32) for key, value in source.items()}
        self.assertTrue(all(validate_transport(source, ascii_corners, native)[2].values()))
        for key in source:
            changed = {name: value.copy() for name, value in native.items()}
            changed[key].flat[0] += .01
            with self.assertRaises(ValueError): validate_transport(source, ascii_corners, changed)
        changed_ascii = {key: value.copy() for key, value in ascii_corners.items()}
        changed_ascii['position'][0] = changed_ascii['position'][0, [0, 2, 1]]
        with self.assertRaises(ValueError): validate_transport(source, changed_ascii, native)

    def test_one_ulp_uv_policy_is_explicit_bounded_and_does_not_relax_normals(self):
        source={'position':np.eye(3)[None], 'normal':np.tile([0.,0.,1.],(1,3,1)),
                'uv':np.full((1,3,2),np.float32(.600302))}
        native={key:row.astype(np.float32) for key,row in source.items()}
        native['uv'][0,0,0]=np.nextafter(native['uv'][0,0,0],np.float32(1))
        with self.assertRaises(ValueError):validate_transport(source,source,native)
        self.assertFalse(validate_transport(source,source,native,1)[2]['uv'])
        native['uv'][0,0,0]=np.nextafter(native['uv'][0,0,0],np.float32(1))
        with self.assertRaises(ValueError):validate_transport(source,source,native,1)
        native={key:row.astype(np.float32) for key,row in source.items()}
        native['normal'][0,0,2]=np.nextafter(native['normal'][0,0,2],np.float32(2))
        with self.assertRaises(ValueError):validate_transport(source,source,native,1)


if __name__ == '__main__':
    unittest.main()
