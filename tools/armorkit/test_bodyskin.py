"""The body's own skin beside an outfit's surface on one part: what is kept of it, and where its textures go."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from . import bodyskin, export, registry, texture
from .test_bake import part
from .test_split import tube


def arm(size=8):
    """A body's upper arm like `bodyskin.body_part` gives: a tube down from the shoulder with textures of its own."""
    v, f = tube((0, 0, 1.5), (0, 0, 1.2), 0.05, around=16, along=12)[:2]
    rows = np.arange(size * size).reshape(size, size)
    relief = np.zeros((size, size, 3)); relief[..., 0], relief[..., 2] = 0.5 + 0.4 * (rows % 2), 1.0
    return {'v': v, 'f': f, 'uv': np.stack([(v[:, 0] + 0.05) * 10, (1.5 - v[:, 2]) / 0.3], axis=1).clip(0, 1), 'n': v * [20.0, 20.0, 0.0],
            'tint': np.stack([60 + rows, np.zeros_like(rows)], axis=2).astype(np.uint8), 'relief': relief, 'rough': rows / rows.max()}


class BodySkinTests(unittest.TestCase):
    def test_an_image_is_read_as_the_kit_writes_one_and_from_the_top_where_it_says_so(self):
        rows = np.arange(24).reshape(2, 4, 3) / 255
        blob = texture.tga(rows)
        self.assertTrue(np.allclose(bodyskin.image(blob), rows))
        flipped = blob[:17] + bytes([0x20]) + blob[18:]
        self.assertTrue(np.allclose(bodyskin.image(flipped), rows[::-1]))
        for wrong in (blob[:30], blob[:2] + bytes([10]) + blob[3:], blob[:16] + bytes([8]) + blob[17:]):  # cut short, packed, grey
            with self.assertRaises(ValueError):
                bodyskin.image(wrong)

    def test_a_skin_material_binds_a_normal_map_and_no_colour_texture(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'skin.mtr').write_text('renderhint NormalTangents\ntexture1 skinn\nparameter float Roughness 0\ntexture3 skinr\n')
            self.assertEqual(bodyskin.material(folder, 'skin'), {'normal': 'skinn', 'rough': 'skinr'})
            (Path(folder) / 'plain.mtr').write_text('texture1 skinn\n')
            self.assertEqual(bodyskin.material(folder, 'plain'), {'normal': 'skinn', 'rough': None})
            (Path(folder) / 'painted.mtr').write_text('texture0 skin\ntexture1 skinn\n')
            for wrong in ('painted', 'none'):
                with self.assertRaises(ValueError):
                    bodyskin.material(folder, wrong)

    def test_a_body_part_is_read_with_its_tint_its_normal_map_and_its_roughness(self):
        own = arm()
        with tempfile.TemporaryDirectory() as folder:
            pack, maps = Path(folder) / 'pack', Path(folder) / 'maps'
            pack.mkdir(); maps.mkdir()
            name = registry.model_name('pmh0', 'bicepl', 1)
            (pack / (name + '.mdl')).write_bytes(b'')
            (pack / (name + '.plt')).write_bytes(export.tint(own['tint'][..., 0], own['tint'][..., 1]))
            (maps / 'skin.mtr').write_text('texture1 skinn\ntexture3 skinr\n')
            (maps / 'skinn.tga').write_bytes(texture.tga(own['relief']))
            (maps / 'skinr.tga').write_bytes(texture.tga(np.repeat(own['rough'][..., None], 3, axis=2)))
            bone = np.eye(4); bone[:3, 3] = (0.2, 0.0, 1.5)
            bone[:3, :3] = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]  # the bone stands turned a quarter about z
            mesh = {'textures': ['skin', '', '', 'skin'], 'position': export.to_bone(own['v'], bone), 'faces': own['f'], 'uv': own['uv'],
                    'normal': np.tile([[1.0, 0.0, 0.0]], (len(own['v']), 1))}
            with mock.patch.object(bodyskin.native_reader, 'decode', lambda *given, **more: [mesh]):
                read = bodyskin.body_part(pack, maps, 'pmh0', 'bicepl', {'lbicep_g': bone})
                self.assertTrue(np.allclose(read['v'], own['v']) and np.array_equal(read['f'], own['f']) and np.allclose(read['uv'], own['uv']))
                self.assertTrue(np.allclose(read['n'], [0.0, 1.0, 0.0]))  # turned with the bone
                self.assertTrue(np.array_equal(read['tint'], own['tint']))
                self.assertTrue(np.allclose(read['relief'], own['relief'], atol=1 / 255) and np.allclose(read['rough'], own['rough'], atol=1 / 255))
                (maps / 'skin.mtr').write_text('texture1 skinn\n')
                with self.assertRaises(ValueError):  # no roughness map: the part's own roughness cannot stand beside the cloth's
                    bodyskin.body_part(pack, maps, 'pmh0', 'bicepl', {'lbicep_g': bone})

    def test_what_a_sleeve_hides_of_the_arm_is_left_out_but_for_a_band_under_its_hem(self):
        own = arm()
        start, end = (0, 0, 1.5), (0, 0, 1.2)
        sleeve = tube(start, (0, 0, 1.35), 0.07, around=24, along=8)[0]  # down to 15 cm from the shoulder
        kept = bodyskin.shown(own['v'], own['f'], sleeve, start, end, band=0.04)
        top = own['v'][own['f']][:, :, 2].max(axis=1)  # a face's highest corner
        self.assertTrue(kept[top < 1.39 - 1e-6].all())  # from 11 cm down, all of the arm
        self.assertFalse(kept[top > 1.42].any())
        self.assertTrue(0.3 < kept.mean() < 0.8)
        # a hem that hangs lower on one side hides no more than its highest reach there and beside it
        slanted = np.concatenate([sleeve, tube((0.07, 0, 1.35), (0.07, 0, 1.25), 0.005, around=4, along=4)[0]])
        self.assertTrue(np.array_equal(bodyskin.shown(own['v'], own['f'], slanted, start, end, band=0.04), kept))
        self.assertTrue(bodyskin.shown(own['v'], own['f'], np.zeros((0, 3)), start, end).all())  # no sleeve: the whole arm

    def test_a_texture_is_made_smaller_by_its_kind_and_larger_by_repeating(self):
        grey = np.arange(16.0).reshape(4, 4)
        self.assertEqual(bodyskin.resized(grey, 2).tolist(), [[2.5, 4.5], [10.5, 12.5]])
        self.assertEqual(bodyskin.resized(grey, 2, 'pick').tolist(), [[5.0, 7.0], [13.0, 15.0]])
        self.assertEqual(bodyskin.resized(grey, 8)[:2, :4].tolist(), [[0, 0, 1, 1], [0, 0, 1, 1]])
        self.assertEqual(bodyskin.resized(grey, 4).tolist(), grey.tolist())
        lean = np.tile([0.5, 0.5, 1.0], (2, 2, 1)); lean[0, 0] = (1.0, 0.5, 0.5)  # one normal along x, three along z
        small = bodyskin.resized(lean, 1, 'normal')[0, 0] * 2 - 1
        self.assertAlmostEqual(float(np.linalg.norm(small)), 1.0)
        self.assertTrue(small[0] > 0 and small[2] > small[0])
        with self.assertRaises(ValueError):
            bodyskin.resized(np.zeros((3, 3)), 2)

    def worn(self, size=4, limit=1024):
        mine, own = part(faces=2, size=size), arm()
        mine['rgb'] = np.random.default_rng(1).random((size, size, 3))
        mine['closing'][0, 1] = True
        mine['v'] = np.array([(0.07, 0.0, 1.5), (0.07, 0.01, 1.5), (0.07, 0.0, 1.45)])  # a sleeve's scrap, 5 cm down the arm
        return mine, own, bodyskin.worn(mine, own, (0, 0, 1.5), (0, 0, 1.2), limit)

    def test_the_bodys_part_is_added_with_its_textures_in_a_quarter_of_their_own(self):
        mine, own, both = self.worn()
        skin = both['skin']
        self.assertEqual((len(both['rgb']), int((~skin).sum()), int(skin.sum())), (8, 2, len(own['f'])))  # 5 cm of sleeve hides nothing within the band
        self.assertTrue(np.array_equal(both['f'][~skin], mine['f']) and np.allclose(both['v'][:3], mine['v']))
        body = np.unique(both['f'][skin])
        self.assertTrue(body.min() == 3 and np.allclose(both['v'][body], own['v']) and np.allclose(both['n'][body], own['n']))
        # texture coordinates: the outfit's halved, the body's halved and moved, neither turned
        self.assertTrue(np.allclose(both['uv'][:3], mine['uv'] / 2) and np.allclose(both['uv'][body], 0.5 + own['uv'] / 2))
        self.assertTrue(np.array_equal(both['rgb'][:4, :4], mine['rgb']) and np.array_equal(both['covered'][:4, :4], mine['covered']))
        self.assertFalse(both['covered'][4:].any() or both['covered'][:, 4:].any())  # the body's texels are no material's
        self.assertTrue(both['closing'][0, 1] and both['closing'].sum() == 1)
        # the body's maps, 8 texels a side, lie in the last quarter at half their size
        self.assertTrue(np.array_equal(both['skin_tint'][4:, 4:, 0], np.round(bodyskin.resized(own['tint'][..., 0], 4)).astype(np.uint8)))
        self.assertTrue(np.allclose(both['relief'][4:, 4:], bodyskin.resized(own['relief'], 4, 'normal')))
        self.assertTrue(np.array_equal(both['relief'][:4, :4], mine['relief']))
        self.assertTrue(np.allclose(both['skin_rough'][4:, 4:] / 255, bodyskin.resized(own['rough'], 4), atol=1 / 255))
        self.assertTrue((both['skin_rough'][:4, :4] == round(bodyskin.ROUGH * 255)).all())
        # and run on a little into the two quarters nothing lies in, never into the outfit's
        at = both['skin_at']
        self.assertTrue(at[4:, 4:].all() and at[4:, 4 - bodyskin.EDGE:4].all() and at[4 - bodyskin.EDGE:4, 4:].all() and not at[:4, :4].any())
        self.assertTrue(np.array_equal(both['skin_tint'][3, 4:], both['skin_tint'][4, 4:]) and np.array_equal(both['skin_tint'][4:, 3], both['skin_tint'][4:, 4]))
        for key in ('added', 'domed'):
            self.assertFalse(both[key][skin].any())
        self.assertTrue((both['trimmed'][skin] == -1).all() and len(both['src']) == len(both['v']))

    def test_at_the_largest_texture_the_outfits_maps_are_halved_to_make_room(self):
        mine, own, both = self.worn(size=8, limit=8)
        self.assertEqual(len(both['rgb']), 8)
        self.assertTrue(np.allclose(both['rgb'][:4, :4], bodyskin.resized(mine['rgb'], 4)))
        self.assertTrue(np.allclose(both['uv'][:3], mine['uv'] / 2))

    def test_an_outfit_that_hides_the_whole_part_is_refused(self):
        v, f = tube((0, 0, 1.5), (0, 0, 1.0), 0.07, around=24, along=8)[:2]  # a sleeve down past the elbow
        cover = dict(part(), v=v, f=f, uv=v[:, :2], n=v, src=v, added=np.zeros(len(f), bool), domed=np.zeros(len(f), bool), trimmed=np.full(len(f), -1))
        with self.assertRaises(ValueError):
            bodyskin.worn(cover, arm(), (0, 0, 1.5), (0, 0, 1.2))


if __name__ == '__main__':
    unittest.main()
