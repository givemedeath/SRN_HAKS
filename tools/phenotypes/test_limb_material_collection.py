"""Guard accepted ownership and positive/negative palette clipping."""
import struct
import unittest
import numpy as np
from prepare_limb_material_collection import selected_parts, skin_offset


class CalibrationSafety(unittest.TestCase):
    def test_clipping_both_directions_preserves_other_layers(self):
        a = np.array([[[250, 0], [4, 0], [130, 2]]], np.uint8)
        data = b'PLT V1  '+struct.pack('<IIII', 10, 0, 3, 1)+a.tobytes()
        payload, proof = skin_offset(data, 11)
        actual = np.frombuffer(payload[24:], np.uint8).reshape(a.shape)
        self.assertEqual(actual.tolist(), [[[255, 0], [15, 0], [130, 2]]])
        self.assertEqual(proof['highClampedPixels'], 1)
        self.assertEqual(proof['lowClampedPixels'], 0)
        payload, proof = skin_offset(data, -10)
        self.assertEqual(np.frombuffer(payload[24:], np.uint8).reshape(a.shape).tolist(),
                         [[[240, 0], [0, 0], [130, 2]]])
        self.assertEqual(proof['lowClampedPixels'], 1)
        self.assertEqual(proof['highClampedPixels'], 0)
        with self.assertRaises(ValueError): skin_offset(data, 0)
        with self.assertRaises(RuntimeError): skin_offset(data, True)

    def test_preserved_parts_and_partial_pairs_cannot_enter(self):
        selected_parts(['bicepl', 'bicepr', 'forel', 'forer'])
        for parts in [[], ['chest'], ['pelvis'], ['bicepl'], ['forel', 'forel']]:
            with self.assertRaises(RuntimeError): selected_parts(parts)


if __name__ == '__main__': unittest.main()
