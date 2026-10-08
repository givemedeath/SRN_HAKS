"""Single-PLT-per-part contract: derived closure, node bindings, MTR bindings and PLT dye layers."""
import unittest

import numpy as np

import single_plt_part_contract as single_plt
import target_contract as contract
from test_target_part_pipeline import target_fixture
from uv_atlas_raster import coverage, dilate4, raster, uv_to_pixels

MODEL = 'pfh0_pelvis001'


def ascii_model(model=MODEL, garment_bitmap=None, extra_node=None):
    """Two quads in separate UV islands: p0 garment (left half), p1 skin (right half)."""
    def node(name, u0, bitmap):
        return ['node trimesh '+name, '  parent '+model, '  position 0 0 0', '  orientation 0 0 0 0',
                '  bitmap '+bitmap, '  materialname '+bitmap, '  render 1', '  shadow 1',
                '  verts 4', '    0 0 0', '    1 0 0', '    1 1 0', '    0 1 0',
                '  normals 4', '    0 0 1', '    0 0 1', '    0 0 1', '    0 0 1',
                '  tverts 4', '    %g 0.1 0' % u0, '    %g 0.1 0' % (u0+0.3), '    %g 0.9 0' % (u0+0.3), '    %g 0.9 0' % u0,
                '  faces 2', '    0 1 2 1 0 1 2 0', '    0 2 3 1 0 2 3 0', 'endnode']
    lines = ['newmodel '+model, 'setsupermodel '+model+' NULL', 'beginmodelgeom '+model,
             'node dummy '+model, '  parent NULL', 'endnode']
    lines += node(model+'p0', 0.1, garment_bitmap or model) + node(model+'p1', 0.6, model)
    if extra_node: lines += node(model+'p2', 0.6, model)
    return '\n'.join(lines+['endmodelgeom '+model, 'donemodel '+model])+'\n'


def plt_bytes(garment_layer=4, skin_layer=0, size=64):
    intensity = np.full((size, size), 100, np.uint8); layer = np.zeros((size, size), np.uint8)
    layer[:, :size//2] = garment_layer; layer[:, size//2:] = skin_layer
    return single_plt.write_plt(intensity, layer)


SLOTS = {MODEL+'p0': {'role': 'garment', 'pltLayers': [4]}, MODEL+'p1': {'role': 'skin', 'pltLayers': [0]}}
MTR = 'renderhint NormalTangents\ntexture1 '+MODEL+'n\nparameter float Roughness 0\ntexture3 '+MODEL+'r\n'


class SinglePltContractTests(unittest.TestCase):
    def test_closure_is_derived_from_declared_owners(self):
        target = target_fixture(); target['rig']['mode'] = 'stock-exact'
        self.assertTrue(single_plt.applies(target))
        self.assertEqual(single_plt.closure_count(target, contract.BODY_PARTS), 5*len(contract.BODY_PARTS))
        self.assertEqual(single_plt.closure_count(target, {'chest', 'pelvis'}), 10)
        names = single_plt.expected_resources(target, {'pelvis'})
        self.assertEqual(names, {contract.model(target, 'pelvis')+suffix for suffix in ('.mdl', '.mtr', '.plt', 'n.tga', 'r.tga')})
        self.assertFalse(any(name.endswith(('f.mtr', 'f.tga', 'fn.tga', 'fr.tga')) for name in names))
        self.assertFalse(single_plt.applies(target_fixture()))

    def test_complete_check_passes_and_reports_layers(self):
        proof = single_plt.check_part(MODEL, ascii_model(), MTR, plt_bytes(), SLOTS)
        self.assertEqual(proof['nodes'][MODEL+'p0']['usedLayers'], [4])
        self.assertEqual(proof['nodes'][MODEL+'p1']['usedLayers'], [0])
        self.assertTrue(proof['everyNodeSamplesModelPlt'])

    def test_every_node_binding_must_equal_model(self):
        with self.assertRaisesRegex(ValueError, 'must equal the model name'):
            single_plt.check_part(MODEL, ascii_model(garment_bitmap=MODEL+'f'), MTR, plt_bytes(), SLOTS)
        with self.assertRaisesRegex(ValueError, 'must equal the model name'):
            single_plt.node_bindings(ascii_model(garment_bitmap='pfh0_pelviss1'), MODEL)

    def test_mtr_binds_only_model_normal_and_roughness(self):
        for text in (MTR+'texture0 '+MODEL+'f\n', MTR.replace(MODEL+'n', MODEL+'fn'), MTR.replace('texture3', 'texture2'),
                     MTR.replace('renderhint NormalTangents\n', '')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                single_plt.mtr_bindings(text, MODEL)

    def test_garment_texels_use_cloth_layers_and_skin_layer_zero(self):
        with self.assertRaisesRegex(ValueError, 'outside its declared garment layers'):
            single_plt.check_part(MODEL, ascii_model(), MTR, plt_bytes(garment_layer=5), SLOTS)
        with self.assertRaisesRegex(ValueError, 'outside its declared skin layers'):
            single_plt.check_part(MODEL, ascii_model(), MTR, plt_bytes(skin_layer=4), SLOTS)
        with self.assertRaisesRegex(ValueError, 'cloth dye layers'):
            single_plt.validate_slots({MODEL+'p0': {'role': 'garment', 'pltLayers': [6]}})
        with self.assertRaisesRegex(ValueError, 'layer 0 only'):
            single_plt.validate_slots({MODEL+'p1': {'role': 'skin', 'pltLayers': [0, 4]}})
        with self.assertRaisesRegex(ValueError, 'node inventory'):
            single_plt.check_part(MODEL, ascii_model(), MTR, plt_bytes(), {MODEL+'p1': SLOTS[MODEL+'p1']})

    def test_nodes_cannot_share_atlas_texels(self):
        slots = {**SLOTS, MODEL+'p2': {'role': 'skin', 'pltLayers': [0]}}
        with self.assertRaisesRegex(ValueError, 'shared between nodes'):
            single_plt.check_part(MODEL, ascii_model(extra_node=True), MTR, plt_bytes(), slots)

    def test_plt_round_trip_keeps_orientation(self):
        intensity = np.arange(12, dtype=np.uint8).reshape(3, 4); layer = (intensity % 2).astype(np.uint8)
        data = single_plt.write_plt(intensity, layer)
        self.assertEqual(data[:8], b'PLT V1  ')
        back_i, back_l = single_plt.read_plt(data)
        np.testing.assert_array_equal(back_i, intensity); np.testing.assert_array_equal(back_l, layer)
        self.assertEqual(data[24:26], bytes([8, 0]))  # file rows are bottom-up
        with self.assertRaises(ValueError):
            single_plt.read_plt(data[:-1])


class UvAtlasRasterTests(unittest.TestCase):
    def test_pixel_centres_and_bottom_up_v(self):
        uv = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], float)
        self.assertEqual(coverage(uv, [[0, 1, 2], [0, 2, 3]], 8, 4).sum(), 32)
        upper = coverage(np.array([[0, .5], [1, .5], [1, 1], [0, 1]]), [[0, 1, 2], [0, 2, 3]], 8, 4)
        self.assertTrue(upper[:2].all() and not upper[2:].any())
        np.testing.assert_allclose(uv_to_pixels([[0.25, 0.75]], 8, 4), [[2, 1]])

    def test_faceid_last_writer_and_barycentrics(self):
        points = np.array([[0, 0], [4, 0], [0, 4]], float)
        faceid, bary = raster(points, [[0, 1, 2], [0, 1, 2]], 4, 4)
        self.assertEqual(int(faceid[0, 0]), 1)
        np.testing.assert_allclose(bary[faceid >= 0].sum(1), 1, atol=1e-6)

    def test_dilate4_is_cross_shaped(self):
        mask = np.zeros((5, 5), bool); mask[2, 2] = True
        grown = dilate4(mask, 1)
        self.assertEqual(int(grown.sum()), 5); self.assertFalse(grown[1, 1])


if __name__ == '__main__':
    unittest.main()
