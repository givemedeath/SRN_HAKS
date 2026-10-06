"""Unused service atlas fill must not change skin/hair palette calibration."""
import unittest
import numpy as np
from propose_material_masks import choose_palette_row


class PaletteSamplingTests(unittest.TestCase):
    def test_unoccupied_pixels_cannot_bias_selected_source_palette_row(self):
        palette=np.array([[[200,160,120]]*256,[[60,40,20]]*256],float)
        values=np.zeros((20,20,3));mask=np.zeros((20,20),dtype=np.uint8);coverage=np.zeros((20,20),dtype=bool)
        coverage[:2,:2]=True;values[:2,:2]=[200,160,120]
        self.assertEqual(choose_palette_row(values,mask,coverage,palette,0),0)
        values[~coverage]=[60,40,20]
        self.assertEqual(choose_palette_row(values,mask,coverage,palette,0),0)
        with self.assertRaisesRegex(ValueError,'covered'):choose_palette_row(values,mask,np.zeros_like(coverage),palette,0)

    def test_propose_masks_freezes_consumed_inputs_and_merges_compatible_fixed_groups(self):
        from pathlib import Path
        import tempfile
        from PIL import Image
        from unittest.mock import patch
        from head_workflow import pin, write_fresh, read
        from head_export import ascii_model
        from propose_material_masks import propose

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fit_src = root / 'donor.glb'; fit_src.write_bytes(b'glb_bytes')
            fit_file = root / 'fit.json'
            write_fresh(fit_file, {'source': pin(fit_src), 'localMatrix': np.eye(4).tolist()})
            atlas = root / 'atlas.json'
            write_fresh(atlas, {'atlasTransferVerified': True})
            correction = root / 'correction.json'
            write_fresh(correction, {})

            color_img = Image.new('RGB', (2048, 2048), (150, 150, 150))
            color_img.paste((50, 50, 50), (0, 0, 1000, 1000))
            color_path = root / 'color.png'; color_img.save(color_path)
            metal_img = Image.new('L', (2048, 2048), 255)
            metal_path = root / 'metal.png'; metal_img.save(metal_path)
            norm_img = Image.new('RGB', (2048, 2048), (128, 128, 255))
            norm_path = root / 'norm.png'; norm_img.save(norm_path)

            pal_img = Image.new('RGB', (256, 1), (150, 150, 150))
            skin_path = root / 'skin.png'; pal_img.save(skin_path)
            hair_path = root / 'hair.png'; pal_img.save(hair_path)

            inputs = [pin(fit_file), pin(fit_src), pin(atlas), pin(correction),
                      pin(color_path), pin(metal_path), pin(norm_path),
                      pin(skin_path), pin(hair_path)]

            cfg = {
                'kind': 'srn-head-mask-proposal-input',
                'fit': pin(fit_file), 'atlasTransfer': pin(atlas), 'correction': pin(correction),
                'baseColor': str(color_path), 'metallic': str(metal_path), 'originalNormal': str(norm_path),
                'skinPalette': str(skin_path), 'hairPalette': str(hair_path),
                'eyeBounds': [[[0.1, 0.1, 0.1], [0.2, 0.2, 0.2]]],
                'cyberBounds': [[[0.3, 0.3, 0.3], [0.4, 0.4, 0.4]]],
                'fixedAccessoryBounds': [[[0.5, 0.5, 0.5], [0.6, 0.6, 0.6]]],
                'inputs': inputs
            }
            cfg_file = root / 'config.json'
            write_fresh(cfg_file, cfg)

            # Test 1: Omitted consumed input is rejected
            bad_cfg = {**cfg, 'inputs': [pin(fit_file), pin(fit_src), pin(atlas), pin(correction),
                                         pin(metal_path), pin(norm_path), pin(skin_path), pin(hair_path)]}
            bad_cfg_file = root / 'bad_config.json'
            write_fresh(bad_cfg_file, bad_cfg)
            with self.assertRaisesRegex(ValueError, 'Consumed source omitted from declaration'):
                propose(bad_cfg_file, root / 'out_fail')

            # Test 2a: Frozen input modified catches in verify_pins
            tampered_inputs = list(inputs)
            tampered_inputs[0] = {**tampered_inputs[0], 'sha256': '0' * 64}
            tampered_cfg = {**cfg, 'inputs': tampered_inputs}
            tampered_cfg_file = root / 'tampered_config.json'
            write_fresh(tampered_cfg_file, tampered_cfg)
            with self.assertRaisesRegex(ValueError, 'Frozen input changed'):
                propose(tampered_cfg_file, root / 'out_fail2')

            # Test 2b: Consumed pin hash mismatch against declaration
            mismatched_cfg = {**cfg, 'fit': {'path': str(fit_file), 'sha256': '0' * 64}}
            mismatched_cfg_file = root / 'mismatched_config.json'
            write_fresh(mismatched_cfg_file, mismatched_cfg)
            with self.assertRaisesRegex(ValueError, 'Declared pin hash mismatch'):
                propose(mismatched_cfg_file, root / 'out_fail3')

            # Test 3: Eye + Cyber + Accessory all present -> merged dielectric groups stay within exporter limit
            tri_p = np.array([
                [[0.0, 0.0, 0.0], [0.01, 0.0, 0.0], [0.0, 0.01, 0.0]], # palette skin
                [[0.0, 0.0, 0.0], [0.01, 0.0, 0.0], [0.0, 0.01, 0.0]], # palette hair
                [[0.15, 0.15, 0.15], [0.16, 0.15, 0.15], [0.15, 0.16, 0.15]], # eye
                [[0.35, 0.35, 0.35], [0.36, 0.35, 0.35], [0.35, 0.36, 0.35]], # cyber
                [[0.55, 0.55, 0.55], [0.56, 0.55, 0.55], [0.55, 0.56, 0.55]], # horns
            ], dtype=float)
            tri_n = np.tile([0., 0., 1.], (5, 3, 1))
            tri_uv = np.array([
                [[0.1, 0.1], [0.15, 0.1], [0.1, 0.15]], # (204, 1842) -> skin
                [[0.1, 0.8], [0.15, 0.8], [0.1, 0.85]], # (204, 409) -> hair
                [[0.2, 0.2], [0.21, 0.2], [0.2, 0.21]],
                [[0.3, 0.3], [0.31, 0.3], [0.3, 0.31]],
                [[0.4, 0.4], [0.41, 0.4], [0.4, 0.41]],
            ], dtype=float)

            out = root / 'out_success'
            with patch('propose_material_masks.triangles', return_value=(tri_p, tri_n, tri_uv)):
                propose(cfg_file, out)

            prop = read(out / 'proposal.json')
            self.assertEqual(len(prop['groups']), 3)
            kinds = [g['kind'] for g in prop['groups']]
            suffixes = [g.get('suffix') for g in prop['groups']]
            self.assertEqual(kinds, ['palette', 'fixed', 'fixed'])
            self.assertEqual(suffixes, [None, 'e', 'c'])
            self.assertEqual(prop['groups'][0]['triangles'], [0, 1])
            self.assertEqual(prop['groups'][1]['triangles'], [2, 4])
            self.assertEqual(prop['groups'][1]['metallicness'], 0)
            self.assertEqual(prop['groups'][2]['triangles'], [3])
            self.assertEqual(prop['groups'][2]['metallicness'], 1)
            text = ascii_model('pmh0_head022', tri_p, tri_n, tri_uv, prop['groups'])
            self.assertIn('node trimesh pmh0_head022p0', text)
            self.assertIn('node trimesh pmh0_head022p1', text)
            self.assertIn('node trimesh pmh0_head022p2', text)

    def test_prepare_palette_assembly_pins_all_consumed_inputs(self):
        from pathlib import Path
        import struct
        import tempfile
        from PIL import Image
        from head_workflow import pin, write_fresh, read
        from prepare_palette_assembly import prepare

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            native_dir = root / 'native'; native_dir.mkdir()
            mat_dir = root / 'materials'; mat_dir.mkdir()
            body_dir = root / 'body'; body_dir.mkdir()

            plt_data = b'PLT V1  ' + b'\x00'*8 + struct.pack('<II', 2, 2) + bytes([0, 0, 0, 1, 0, 0, 0, 1])
            (native_dir / 'head0.plt').write_bytes(plt_data)
            (body_dir / 'part.plt').write_bytes(plt_data)

            for name in ('semantic', 'color', 'normal', 'roughness'):
                img = Image.new('RGB' if name != 'roughness' else 'L', (2, 2), 0)
                img.save(mat_dir / f'{name}.png')

            pal_img = Image.new('RGB', (256, 1), 100)
            skin_path = root / 'skin.png'; pal_img.save(skin_path)
            hair_path = root / 'hair.png'; pal_img.save(hair_path)

            part_source = root / 'part.mdl'; part_source.write_bytes(b'part_bytes')
            assembly_data = {
                'heads': [{}],
                'parts': [{'source': pin(part_source), 'joint': 'neck'}]
            }

            assembly_file = root / 'assembly.json'
            write_fresh(assembly_file, assembly_data)

            inputs = [
                pin(assembly_file), pin(skin_path), pin(hair_path),
                pin(native_dir / 'head0.plt'),
                pin(mat_dir / 'semantic.png'), pin(mat_dir / 'color.png'),
                pin(mat_dir / 'normal.png'), pin(mat_dir / 'roughness.png'),
                pin(part_source), pin(body_dir / 'part.plt')
            ]

            cfg = {
                'assembly': pin(assembly_file),
                'models': ['head0'],
                'native': [str(native_dir)],
                'materials': [str(mat_dir)],
                'skinPalette': str(skin_path),
                'hairPalette': str(hair_path),
                'skinRow': 0, 'hairRow': 0,
                'body': str(body_dir),
                'inputs': inputs
            }
            cfg_file = root / 'config.json'
            write_fresh(cfg_file, cfg)

            # Test 1: Omitted input fails
            bad_cfg = {**cfg, 'inputs': inputs[:-1]}
            bad_cfg_file = root / 'bad_config.json'
            write_fresh(bad_cfg_file, bad_cfg)
            with self.assertRaisesRegex(ValueError, 'Consumed source omitted from declaration'):
                prepare(bad_cfg_file, root / 'out_fail')

            # Test 2: Valid inputs succeed
            out = root / 'out_success'
            prepare(cfg_file, out)
            res = read(out / 'assembly.json')
            self.assertTrue(res['palettePreview']['nativeResourcesRead'])
            self.assertEqual(res['palettePreview']['skinRow'], 0)


if __name__=='__main__':unittest.main()
