"""Single-PLT native audit: model-named texture slots, exact ordered transport and encoded tangent basis."""
import copy
import struct
import unittest

import numpy as np

from audit_single_plt_native_part import basis_comparison, native_transport

MODEL = 'pfh0_pelvis001'
POSITIONS = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], float)
UVS = np.array([[0, 0], [1, 0], [0, 1]], float)


def native(names, material=MODEL, tangent=(1, 0, 0), sign=1.0, position_offset=0.0):
    """Minimal detached compiled model (layout as audit_target_native_part's fixture)."""
    root = 232; children = root+0x70
    nodes = [children+4*len(names)+index*0x270 for index in range(len(names))]
    faces = [nodes[-1]+0x270+index*32 for index in range(len(names))]
    raw_offset = faces[-1]+32; raw_size = len(names)*3*(12+8+12+12+4)
    data = bytearray(12+raw_offset+raw_size)
    struct.pack_into('<III', data, 0, 0, raw_offset, raw_size)

    def string(at, value):
        blob = value.encode()+b'\0'; data[at:at+len(blob)] = blob
    string(12+8, MODEL); string(12+0xa8, 'NULL')
    struct.pack_into('<II', data, 12+0x48, root, len(names)+1)
    data[12+0x72] = 4; struct.pack_into('<f', data, 12+0xa4, 1)
    string(12+root+32, MODEL); struct.pack_into('<I', data, 12+root+0x6c, 1)
    struct.pack_into('<III', data, 12+root+0x48, children, len(names), len(names))
    pointer = 0
    for index, (offset, face, name) in enumerate(zip(nodes, faces, names)):
        at = 12+offset; string(at+32, name); struct.pack_into('<I', data, 12+children+index*4, offset)
        struct.pack_into('<I', data, at+0x6c, 33); struct.pack_into('<III', data, at+0x78, face, 1, 1)
        struct.pack_into('<HH', data, at+0x230, 3, 1); struct.pack_into('<I', data, at+0x248, 0xffffffff)
        string(at+0xe8, material); string(at+0xe8+3*64, material); struct.pack_into('<I', data, at+0xd4, 1)
        rows = [POSITIONS+position_offset, UVS, np.tile([0, 0, 1], (3, 1)), np.tile(tangent, (3, 1)), np.full((3, 1), sign)]
        for field, row in zip([0x22c, 0x234, 0x244, 0x258, 0x260], rows):
            struct.pack_into('<I', data, at+field, pointer)
            blob = np.asarray(row, '<f4').tobytes(); start = 12+raw_offset+pointer
            data[start:start+len(blob)] = blob; pointer += len(blob)
        struct.pack_into('<HHH', data, 12+face+26, 0, 1, 2)
    return bytes(data)


def ascii_text(names):
    lines = ['newmodel '+MODEL, 'beginmodelgeom '+MODEL, 'node dummy '+MODEL, '  parent NULL', 'endnode']
    for name in names:
        lines += ['node trimesh '+name, '  parent '+MODEL, '  bitmap '+MODEL, '  materialname '+MODEL,
                  '  verts 3', '    0 0 0', '    1 0 0', '    0 1 0', '  normals 3', '    0 0 1', '    0 0 1', '    0 0 1',
                  '  tverts 3', '    0 0 0', '    1 0 0', '    0 1 0', '  faces 1', '    0 1 2 1 0 1 2 0', 'endnode']
    return '\n'.join(lines+['endmodelgeom '+MODEL, 'donemodel '+MODEL])+'\n'


NAMES = [MODEL+'p0', MODEL+'p1']


class SinglePltNativeAuditTests(unittest.TestCase):
    def test_exact_transport_and_model_named_slots(self):
        proof, meshes, root = native_transport(ascii_text(NAMES), native(NAMES), MODEL)
        self.assertEqual(root['name'], MODEL); self.assertEqual(set(proof), set(NAMES))
        for row in proof.values():
            self.assertTrue(row['positionsExactFloat32']); self.assertEqual(row['textureSlots'], [MODEL, '', '', MODEL])
            self.assertEqual(row['uvMaximumUlps'], 0)

    def test_per_node_native_material_or_moved_positions_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'texture slots'):
            native_transport(ascii_text(NAMES), native(NAMES, material=MODEL+'f'), MODEL)
        with self.assertRaisesRegex(ValueError, 'positions differ'):
            native_transport(ascii_text(NAMES), native(NAMES, position_offset=1e-3), MODEL)
        with self.assertRaisesRegex(ValueError, 'must equal the model name'):
            native_transport(ascii_text(NAMES).replace('bitmap '+MODEL, 'bitmap '+MODEL+'f', 1), native(NAMES), MODEL)

    def test_encoded_basis_comparison(self):
        _, meshes, _ = native_transport(ascii_text(NAMES), native(NAMES), MODEL)
        stats = basis_comparison(meshes, copy.deepcopy(meshes))
        self.assertEqual(stats['signMismatches'], 0); self.assertEqual(stats['maxTangentDegrees'], 0)
        _, flipped, _ = native_transport(ascii_text(NAMES), native(NAMES, sign=-1.0), MODEL)
        with self.assertRaisesRegex(ValueError, 'tangent basis differs'):
            basis_comparison(meshes, flipped)
        _, turned, _ = native_transport(ascii_text(NAMES), native(NAMES, tangent=(0, 1, 0)), MODEL)
        with self.assertRaisesRegex(ValueError, 'tangent basis differs'):
            basis_comparison(meshes, turned)


if __name__ == '__main__':
    unittest.main()
