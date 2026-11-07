import re
import unittest

from tools.itemkit import firearm_fx_pilot as fx

GUN = '''newmodel wbwsl_b_051
setsupermodel wbwsl_b_051 NULL
setanimationscale 1

beginmodelgeom wbwsl_b_051
node dummy wbwsl_b_051
  parent NULL
endnode
node trimesh wbwsl_b_051v
  parent wbwsl_b_051
  verts 3
    0.0 0.1 -0.3
    0.0 0.2 -0.3
    0.0 0.5 0.1
endnode
endmodelgeom wbwsl_b_051

donemodel wbwsl_b_051
'''


class TaggedGun(unittest.TestCase):
    def test_muzzle_is_the_barrel_tip(self):
        self.assertEqual(fx.muzzle(GUN).round(3).tolist(), [0., .15, -.3])

    def test_each_build_has_one_burst_on_one_set_of_names(self):
        for names, emitter, other, count in (('stock', 'srp_red', 'srp_green', 2), ('replaced', 'srp_green', 'srp_red', 15)):
            text = fx.tagged_gun(GUN, 'fire_pst', names)
            clips = re.findall(r'(?ms)^newanim (\S+) wbwsl_b_051\n(.*?)^doneanim', text)
            self.assertEqual(len(clips), count)
            self.assertNotIn(other, text)
            for _, body in clips:
                self.assertIn('event 0.1 detonate', body)
                self.assertIn(emitter, body)

    def test_replaced_names_cover_every_slot(self):
        text = fx.tagged_gun(GUN, 'fire_pst', 'replaced')
        self.assertIn('newanim fire_pst_tfl wbwsl_b_051', text)
        self.assertNotIn('newanim throwr', text)

    def test_clips_sit_after_the_geometry_and_inside_the_model(self):
        text = fx.tagged_gun(GUN, 'fire_pst', 'stock')
        self.assertLess(text.index('endmodelgeom'), text.index('newanim'))
        self.assertLess(text.rindex('doneanim'), text.index('donemodel'))
        self.assertLess(text.index('node emitter srp_marker'), text.index('endmodelgeom'))
        self.assertIn('classification Character', text)

    def test_quiet_clips_send_no_event(self):
        text = fx.tagged_gun(GUN, 'fire_pst', 'replaced', quiet=True)
        clips = dict(re.findall(r'(?ms)^newanim (\S+) wbwsl_b_051\n(.*?)^doneanim', text))
        self.assertEqual(len(clips), 15 + len(fx.QUIET_CLIPS))
        for name in fx.QUIET_CLIPS:
            self.assertNotIn('event', clips[name])
        self.assertIn('event 0.1 detonate', clips['fire_pst_hm'])

    def test_retimed_hits_move_every_fire_clip_and_leave_the_rest(self):
        text = (fx.REPO / 'srn_body' / 'a_ba_custom.mdl').read_text(encoding='cp1252')
        retimed = fx.retimed_hits(text)
        events = dict(re.findall(r'(?ms)^newanim (\S+) a_ba_custom\n(.*?)^doneanim', retimed))
        for name, body in events.items():
            stem = name.rsplit('_', 1)[0]
            hits = re.findall(r'(?m)^\s*event (\S+) hit$', body)
            if stem in fx.HIT_TIMES:
                self.assertEqual(hits, [str(fx.HIT_TIMES[stem])], name)
        self.assertEqual(re.findall(r'(?m)^\s*event (\S+) hit$', events['throw_gren_hm']), ['0.5'])
        self.assertEqual(retimed.count('\n'), text.count('\n') + 15)

    def test_old_effects_move_onto_the_muzzle_and_port(self):
        def block(name, position, extra=''):
            fields = ''.join(f'  {field} 0\r\n' for field in ('sizeStart', 'sizeEnd', 'sizeStart_y', 'sizeEnd_y',
                                                                  'alphaEnd', 'lifeExp'))
            return (f'node emitter {name}\r\n  parent old\r\n  position {position}\r\n  texture fxpa_smoke02\r\n'
                    f'  fps 0\r\n  framestart 0\r\n  frameend 16\r\n{fields}{extra}endnode\r\n')
        old = block('muzzle_flash01', '0 0.1 -0.28') + block('muzzle_flash02', '0 0.1 -0.38')
        old += 'newanim x old\r\n' + block('muzzle_flash03', '0 0 0') + 'doneanim x old\r\n'
        flashes = fx.emitter_blocks(old, 'muzzle_flash')
        self.assertEqual(sorted(flashes), ['muzzle_flash01', 'muzzle_flash02'])
        casing = fx.emitter_blocks(block('Casings39', '1 2 3'), 'Casings')
        nodes = fx.old_effects('wbwsl_b_051', GUN, flashes, casing, (.025, .1, -.05))
        self.assertEqual(list(nodes), ['srn_flash01', 'srn_flash02', 'srn_casing'])
        self.assertIn('position 0.00000 0.15000 -0.30000', nodes['srn_flash01'])
        self.assertIn('position 0.00000 0.15000 -0.40000', nodes['srn_flash02'])
        self.assertIn('parent wbwsl_b_051', nodes['srn_casing'])
        self.assertIn('position 0.02500 0.10000 -0.05000', nodes['srn_casing'])
        self.assertIn(f'texture {fx.CASING_SHEET}', nodes['srn_casing'])
        self.assertIn('frameend 15', nodes['srn_casing'])
        self.assertIn(f'sizeStart {fx.CASING_SIZE}', nodes['srn_casing'])
        self.assertIn('alphaEnd 0', nodes['srn_flash01'])
        text = fx.tagged_gun(GUN, 'fire_pst', 'replaced', effects=nodes)
        self.assertNotIn('srp_', text)
        self.assertIn(f'event {fx.SHOT_TIME} detonate', text)
        smg = fx.tagged_gun(GUN, 'fire_smg', 'replaced', effects=nodes)
        body = re.search(r'(?ms)^newanim fire_smg_hm wbwsl_b_051\n(.*?)^doneanim', smg)[1]
        self.assertEqual(re.findall(r'event (\S+) detonate', body), [str(t) for t in fx.KICK_TIMES['fire_smg']])

    def test_tumbling_sheet_has_sixteen_turning_frames(self):
        import tempfile
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            source = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
            for x in range(4):
                for y in range(4):
                    source.paste((200, 150, 50, 255), (x * 32 + 2, y * 32 + 12, x * 32 + 30, y * 32 + 20))
            source.save(folder + '/old.tga')
            fx.tumbling_sheet(folder + '/old.tga', folder + '/new.tga')
            sheet = Image.open(folder + '/new.tga')
            widths = [sheet.crop(((f % 4) * 64, (f // 4) * 64, (f % 4 + 1) * 64, (f // 4 + 1) * 64)).getbbox()
                      for f in range(16)]
            spans = [box[2] - box[0] for box in widths]
            self.assertEqual(sheet.size, (256, 256))
            self.assertGreater(spans[0], 2 * spans[4])
            self.assertEqual(spans[0], spans[8])

    def test_a_gun_with_clips_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'Unexpected gun shape'):
            fx.tagged_gun(GUN.replace('donemodel', 'newanim old wbwsl_b_051\ndoneanim old wbwsl_b_051\ndonemodel'), 'fire_pst', 'stock')


if __name__ == '__main__':
    unittest.main()
