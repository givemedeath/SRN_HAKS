"""Deterministic parts of the LEAN reduction pipeline (no Blender, no native compiler)."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

import lean_common as L
from lean_border_repair import Node, validate_config, weld_crack
from lean_compose_basis import skeleton, write_part
from lean_normal_maps import encode, merge, target_field
from lean_parent_representation import validate_declaration
from lean_reduction_core import split_by_material, topo, weld
from lean_single_plt_atlas import islands, majority, place, rank_map, stock_garment_layers
import single_plt_part_contract as single_plt
from stage_lean_part import compiler_corners

QUAD_P = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], float)
QUAD_F = np.array([[0, 1, 2], [0, 2, 3]])


def flat_arrays(uv_scale=1.0, uv_offset=(0.0, 0.0)):
    uv = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], float)*uv_scale+np.asarray(uv_offset)
    return {'position': QUAD_P, 'normal': np.tile([0, 0, 1.0], (4, 1)), 'uv': uv, 'tangent': np.tile([1, 0, 0.0], (4, 1)),
            'sign': np.ones((4, 1)), 'faces': QUAD_F}


PARENT_ASCII = '\n'.join(['newmodel pfh0_legl001', 'setsupermodel pfh0_legl001 NULL', 'beginmodelgeom pfh0_legl001',
                          'node dummy pfh0_legl001', '  parent NULL', 'endnode', 'node trimesh pfh0_legl001p0', '  parent pfh0_legl001',
                          '  bitmap pfh0_legl001', '  materialname pfh0_legl001', '  verts 3', '    0 0 0', '    1 0 0', '    0 1 0',
                          '  normals 3', '    0 0 1', '    0 0 1', '    0 0 1', '  tverts 3', '    0 0 0', '    1 0 0', '    0 1 0',
                          '  faces 1', '    0 1 2 4 0 1 2 2', 'endnode', 'endmodelgeom pfh0_legl001', 'donemodel pfh0_legl001'])+'\n'


class LeanCommonTests(unittest.TestCase):
    def test_frozen_inputs_reject_changes_and_pins_verify(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'input.bin'; path.write_bytes(b'a'); frozen = L.Frozen(); frozen.take(path)
            self.assertEqual(L.exact(L.pin(path)), path.resolve())
            path.write_bytes(b'b')
            with self.assertRaisesRegex(ValueError, 'changed'): frozen.take(path)
            with self.assertRaisesRegex(ValueError, 'changed'): frozen.verify()
            with self.assertRaisesRegex(ValueError, 'Fresh output'): L.fresh(Path(temporary))

    def test_mtr_and_tga_round_trip(self):
        self.assertEqual(L.mtr_textures('renderhint NormalTangents\ntexture1 a_n\nparameter float Roughness 0.72\ntexture3 a_r // c\n'),
                         {'texture1': 'a_n', 'texture3': 'a_r', 'roughness': 0.72})
        with tempfile.TemporaryDirectory() as temporary:
            image = np.arange(2*3*3, dtype=np.uint8).reshape(2, 3, 3)
            head = bytes([0, 0, 2])+bytes(9)+np.array([3, 2], '<u2').tobytes()+bytes([24, 0])
            meta = {'head': head, 'tail': b'', 'top': False}; path = Path(temporary)/'map.tga'; L.tga_write(path, meta, image)
            _, back = L.tga_read(path); np.testing.assert_array_equal(back, image)

    def test_tbn_handedness_and_dilation(self):
        n, t, b = L.tbn(np.array([[0, 0, 2.0]]), np.array([[3.0, 0, 0]]), np.array([-1.0]))
        np.testing.assert_allclose(b, [[0, -1, 0]])
        buffer = np.zeros((5, 5, 3)); buffer[2, 2] = 1; filled = np.zeros((5, 5), bool); filled[2, 2] = True
        grown, mask = L.dilate_values(buffer, filled, 1)
        self.assertEqual(int(mask.sum()), 5); np.testing.assert_allclose(grown[1, 2], 1)


class ReductionCoreTests(unittest.TestCase):
    def test_weld_drops_degenerate_and_duplicate_faces_and_split_restores_nodes(self):
        P = np.vstack([QUAD_P, QUAD_P[[0, 2]]]); F = np.array([[0, 1, 2], [0, 2, 3], [4, 1, 5], [0, 0, 3]])
        U = np.zeros((6, 2)); N = np.tile([0, 0, 1.0], (6, 1)); M = np.array([0, 1, 0, 1])
        Pw, Fw, Uc, Nc, Mf, dropped = weld(P, F, U, N, M)
        self.assertEqual(len(Pw), 4); self.assertEqual(dropped, 2); np.testing.assert_array_equal(Mf, [0, 1])
        boundary, nonmanifold = topo(Fw); self.assertEqual(len(boundary), 4); self.assertEqual(nonmanifold, 0)
        nodes = split_by_material(['a', 'b'], Pw, Fw, Uc, Nc, Mf)
        self.assertEqual(sorted(nodes), ['a', 'b']); self.assertEqual(nodes['a']['faces'].shape, (1, 3))


class ComposeBasisTests(unittest.TestCase):
    def test_geometry_replaced_and_every_other_line_kept(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)/'parent.mdl'; parent.write_text(PARENT_ASCII); out = Path(temporary)/'lean.mdl'
            rows = write_part(parent, {'pfh0_legl001p0': flat_arrays()}, out)
            self.assertEqual(rows['pfh0_legl001p0']['triangles'], 2); self.assertEqual(rows['pfh0_legl001p0']['smoothingGroup'], 4)
            self.assertEqual(skeleton(PARENT_ASCII.splitlines()), skeleton(out.read_text().splitlines()))
            self.assertIn('    0 2 3 4 0 2 3 2', out.read_text())
            with self.assertRaisesRegex(ValueError, 'node inventory'):
                write_part(parent, {'other': flat_arrays()}, Path(temporary)/'bad.mdl')


class NormalMapTests(unittest.TestCase):
    def test_identical_geometry_and_basis_keep_the_detail_map(self):
        detail = np.full((16, 16, 3), [128, 128, 255], np.uint8); detail[4:8, 4:8] = [180, 100, 230]
        field, filled = target_field(flat_arrays(), detail)
        image, covered, stats = encode(field, filled, flat_arrays(), detail)
        # x/y survive exactly; z is recomputed from the unit vector, as in the study encoder
        self.assertTrue(covered.all()); self.assertLessEqual(int(np.abs(image[..., :2].astype(int)-detail[..., :2]).max()), 1)
        self.assertEqual(stats['leanTexelsWithoutParentTarget'], 0)

    def test_shared_map_merge_is_owned_by_coverage(self):
        base = np.zeros((4, 4, 3), np.uint8); a = base.copy(); a[:, :2] = 10; b = base.copy(); b[:, 1:] = 20
        cov_a = np.zeros((4, 4), bool); cov_a[:, :2] = True; cov_b = np.zeros((4, 4), bool); cov_b[:, 2:] = True
        merged = merge(base, {'b': (b, cov_b), 'a': (a, cov_a)})
        self.assertTrue((merged[:, :2] == 10).all() and (merged[:, 2:] == 20).all())


class AtlasTests(unittest.TestCase):
    def test_islands_placement_and_dye_intensity(self):
        P = np.vstack([QUAD_P, QUAD_P+[5, 0, 0]]); U = np.vstack([flat_arrays(0.1)['uv'], flat_arrays(0.1, (0.5, 0.5))['uv']])
        F = np.vstack([QUAD_F, QUAD_F+4]); self.assertEqual(len(np.unique(islands(P, U, F))), 2)
        occ = np.zeros((2048, 2048), bool); occ[:1024] = True; mask = np.zeros((2048, 2048), bool); mask[10:20, 10:20] = True
        dy, dx = place(occ, mask, (10, 10)); self.assertFalse((occ[10+dy:20+dy, 10+dx:20+dx]).any())
        src = np.array([10.0, 20, 30, 40]); out = rank_map(src, np.array([100.0, 160, 220]))
        self.assertEqual(int(np.median(out)), 160); self.assertLessEqual(int(out.max()-out.min()), int(1.5*30)+1)
        lab = np.zeros((2048, 2048), np.uint8); lab[0:9, 0:9] = 5; lab[4, 4] = 4; m = np.zeros_like(lab, bool); m[0:9, 0:9] = True
        self.assertEqual(int(majority(lab, m, [4, 5])[4, 4]), 5)

    def test_stock_garment_layers_are_derived_from_the_stock_plt(self):
        intensity = np.zeros((4, 4), np.uint8); layer = np.array([[0, 4, 2, 3]]*4, np.uint8)
        self.assertEqual(stock_garment_layers(single_plt.write_plt(intensity, layer)), (4,))
        layer[0, 0] = 5; self.assertEqual(stock_garment_layers(single_plt.write_plt(intensity, layer)), (4, 5))


class RepairAndStageTests(unittest.TestCase):
    def test_crack_weld_closes_micro_gap_and_config_is_bounded(self):
        a = {'position': np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 6e-6, 0]], float), 'uv': np.zeros((4, 2)),
             'normal': np.tile([0, 0, 1.0], (4, 1)), 'faces': np.array([[0, 1, 2], [1, 3, 2]])}
        node = Node('n', a); before = weld_crack({'n': node}, 'n', 1e-4)
        self.assertEqual(len(before['weldedPairs']), 1); self.assertLess(before['openEdgesAfter'], before['openEdgesBefore'])
        with self.assertRaisesRegex(ValueError, 'sub-0.1 mm'):
            validate_config({'kind': 'lean-border-repair-config', 'schemaVersion': 1, 'crackWelds': [{'maxSeparationM': 0.01}]})

    def test_compiler_corner_archive_and_declaration_guards(self):
        with tempfile.TemporaryDirectory() as temporary:
            count = compiler_corners(PARENT_ASCII, ['pfh0_legl001p0'], Path(temporary)/'c.npz')
            self.assertEqual(count, 1); self.assertEqual(np.load(Path(temporary)/'c.npz')['pfh0_legl001p0/positions'].shape, (1, 3, 3))
        with self.assertRaisesRegex(ValueError, 'fourteen'):
            validate_declaration({'kind': 'lean-parent-declaration', 'schemaVersion': 1, 'sex': 'female', 'prefix': 'pfh0', 'models': {}})
        with self.assertRaisesRegex(ValueError, 'prefix'):
            validate_declaration({'kind': 'lean-parent-declaration', 'schemaVersion': 1, 'sex': 'female', 'prefix': 'pmh0', 'models': {}})


class SheetTests(unittest.TestCase):
    def test_every_view_lands_on_a_sheet_and_changed_renders_are_rejected(self):
        from PIL import Image
        from compose_lean_gate3_sheets import compose
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); renders = []
            for view in ('full-idle-front', 'full-idle-left', 'full-idle-rear', 'full-walk-front', 'full-walk-left', 'full-walk-rear', 'neck-front'):
                for variant in ('s3-d0', 's8-d26'):
                    path = root/f'{view}-{variant}.png'; Image.new('RGB', (40, 60), (10, 20, 30)).save(path)
                    renders.append({'id': view, 'variant': variant, 'clip': 'walk' if 'walk' in view else 'pause1', 'fraction': 0.5,
                                    'path': str(path), 'sha256': L.sha(path)})
            report = root/'render-report.json'; report.write_text(json.dumps({'renders': renders}))
            groups = root/'groups.json'; groups.write_text(json.dumps({'neck': ['neck-front']}))
            result = L.read_json(compose([report], groups, 'test', root/'sheets')['path'])
            self.assertEqual(result['renderCount'], 14); self.assertIn('03-neck', result['sheets'])
            groups.write_text(json.dumps({}))
            with self.assertRaisesRegex(ValueError, 'missing from every sheet'):
                compose([report], groups, 'test', root/'sheets-2')
            Image.new('RGB', (40, 60), (0, 0, 0)).save(root/'neck-front-s3-d0.png')
            with self.assertRaisesRegex(ValueError, 'changed'):
                compose([report], root/'groups.json', 'test', root/'sheets-3')


if __name__ == '__main__':
    unittest.main()
