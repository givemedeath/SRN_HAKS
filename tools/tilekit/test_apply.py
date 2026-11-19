"""Applying a review overlay: where each texture's files go, what is deleted, and the expected overrides."""
import json
import tempfile
import unittest
from pathlib import Path

from tools.tilekit import apply

MATERIAL = 'renderhint NormalAndSpecMapped\n\ntexture0 {0}\ntexture1 {0}_n\ntexture2 null\n'


class ApplyTests(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory(); self.addCleanup(holder.cleanup)
        self.repo = Path(holder.name) / 'repo'; self.overlay = Path(holder.name) / 'overlay'; self.overlay.mkdir()
        packs = {'srn_t_common': ('wall.tga', 'wall.dds', 'bin.dds', 'wall.txi', 't_a01.mdl'), 'srn_t_tst': ('tst.set',), 'srn_placeable': ('bin.dds', 'crate.dds')}
        for pack, names in packs.items():
            (self.repo / pack).mkdir(parents=True)
            for name in names:
                (self.repo / pack / name).write_bytes(b'old')
        configuration = {'HakList': [{'Name': pack, 'Path': f'./{pack}/'} for pack in packs],
                         'ExpectedOverrides': [{'Resource': 'other.dds', 'Packs': ['srn_t_common', 'srn_placeable']}, {'Resource': 'bin.dds', 'Packs': ['srn_placeable', 'srn_t_common']}]}
        (self.repo / 'hakbuilder.json').write_text(json.dumps(configuration, indent=2) + '\n', encoding='utf-8')
        for name in ('wall', 'bin'):
            (self.overlay / f'{name}.mtr').write_text(MATERIAL.format(name), encoding='ascii')
            for stem in (name, f'{name}_n'):
                (self.overlay / f'{stem}.dds').write_bytes(b'new')
        (self.overlay / 'tcn_w.dds').write_bytes(b'new'); (self.overlay / 'tcn_w.txi').write_bytes(b'proceduretype arturo')
        (self.overlay / 't_a01.mdl').write_bytes(b'model')
        self.spec = {'tileset': 'tst', 'textures': {'wall': {}, 'bin': {}, 'tcn_w': {}}}

    def names(self, pack):
        return sorted(path.name for path in (self.repo / pack).iterdir())

    def test_each_texture_goes_where_its_name_was_and_its_old_copies_go(self):
        (self.overlay / 'stray.dds').write_bytes(b'left')
        told = apply.apply(self.repo, self.spec, self.overlay)
        self.assertEqual(self.names('srn_t_common'), ['bin.dds', 'bin.mtr', 'bin_n.dds', 't_a01.mdl', 'wall.dds', 'wall.mtr', 'wall.txi', 'wall_n.dds'])  # the old TXI is left
        self.assertEqual(self.names('srn_placeable'), ['bin.dds', 'bin.mtr', 'bin_n.dds', 'crate.dds'])
        self.assertEqual(self.names('srn_t_tst'), ['tcn_w.dds', 'tcn_w.txi', 'tst.set'])  # a base-game texture goes to the tileset's pack
        self.assertEqual((self.repo / 'srn_t_common' / 'wall.dds').read_bytes(), b'new'); self.assertEqual((self.repo / 'srn_t_common' / 't_a01.mdl').read_bytes(), b'model')
        overrides = json.loads((self.repo / 'hakbuilder.json').read_text(encoding='utf-8'))['ExpectedOverrides']
        self.assertEqual([(entry['Resource'], entry['Packs']) for entry in overrides],
                         [('other.dds', ['srn_t_common', 'srn_placeable']), ('bin.dds', ['srn_placeable', 'srn_t_common']),
                          ('bin.mtr', ['srn_placeable', 'srn_t_common']), ('bin_n.dds', ['srn_placeable', 'srn_t_common'])])
        self.assertEqual(told, {'put': 12, 'deleted': 1, 'overrides': 3, 'new overrides': 2, 'dropped overrides': 0, 'not applied': ['stray.dds']})  # of no texture of the spec
        apply.apply(self.repo, self.spec, self.overlay)  # again: every entry where it stood
        self.assertEqual(json.loads((self.repo / 'hakbuilder.json').read_text(encoding='utf-8'))['ExpectedOverrides'], overrides)

    def test_an_overlay_of_models_alone_needs_no_spec(self):
        self.assertEqual(apply.apply(self.repo, None, self.overlay)['put'], 1)
        self.assertEqual((self.repo / 'srn_t_common' / 't_a01.mdl').read_bytes(), b'model'); self.assertEqual((self.repo / 'srn_t_common' / 'wall.tga').read_bytes(), b'old')

    def test_applying_again_finds_a_restyle_by_its_material_and_a_model_s_walkmesh_must_stand(self):
        (self.overlay / 'wall.mtr').write_text(MATERIAL.format('wl'), encoding='ascii')  # maps of a stem of their own
        for stem in ('wl', 'wl_n'):
            (self.overlay / f'{stem}.dds').write_bytes(b'new')
        apply.apply(self.repo, self.spec, self.overlay)
        first = self.names('srn_t_common'); apply.apply(self.repo, self.spec, self.overlay)
        self.assertEqual(self.names('srn_t_common'), first); self.assertNotIn('wall.dds', first)
        (self.repo / 'srn_t_common' / 't_a01.mdl').write_text('node aabb wm\n  verts 1\n    0 0 0\nendnode\n', encoding='cp1252')
        (self.overlay / 't_a01.mdl').write_text('node aabb wm\n  verts 1\n    0 0 1\nendnode\n', encoding='cp1252')
        with self.assertRaisesRegex(ValueError, 't_a01.mdl: its walkmesh differs'):
            apply.plan(self.repo, self.spec, self.overlay)

    def test_a_copied_terrain_s_new_models_go_to_the_tileset_s_pack_and_its_tables_replace_theirs(self):
        overlay = self.overlay.parent / 'terrain'; overlay.mkdir()
        tile = '[TILE{0}]\r\nModel=t_{0}\r\nTopLeft=Ground\r\nTopRight=Ground\r\nBottomLeft=Ground\r\nBottomRight=Ground\r\n\r\n'
        laid = lambda count: ('[TERRAIN TYPES]\r\nCount=1\r\n\r\n[TERRAIN0]\r\nName=Ground\r\n\r\n[TILES]\r\nCount=%d\r\n\r\n' % count + ''.join(tile.format(n) for n in range(count))).encode()
        (self.repo / 'srn_t_tst' / 'tst.set').write_bytes(laid(2))
        for name, data in (('n_t01.mdl', b'model'), ('n_t01.wok', b'walk'), ('tst.set', laid(3))):  # the set adds after the pack's entries
            (overlay / name).write_bytes(data)
        told = apply.apply(self.repo, {'tileset': 'tst'}, overlay)
        self.assertEqual((told['put'], told['not applied']), (3, [])); self.assertEqual(self.names('srn_t_tst'), ['n_t01.mdl', 'n_t01.wok', 'tst.set'])
        self.assertEqual((self.repo / 'srn_t_tst' / 'tst.set').read_bytes(), laid(3))
        (overlay / 'n_t01.wok').write_bytes(b'moved')
        with self.assertRaisesRegex(ValueError, 'a walkmesh in a pack is not replaced'):
            apply.plan(self.repo, {'tileset': 'tst'}, overlay)
        (overlay / 'n_t01.wok').write_bytes(b'walk')
        (self.repo / 'srn_t_tst' / 'tst.set').write_bytes(laid(4))  # another addition since the overlay was made
        with self.assertRaisesRegex(ValueError, 'tst.set: it lacks or changes entries the pack copy has'):
            apply.plan(self.repo, {'tileset': 'tst'}, overlay)
        with self.assertRaisesRegex(ValueError, 'is new: the spec names the tileset'):
            (overlay / 'n_t01.wok').unlink(); (overlay / 'n_t02.mdl').write_bytes(b'model'); apply.plan(self.repo, None, overlay)

    def test_names_are_matched_in_any_case_and_a_pack_s_spelling_kept(self):
        (self.repo / 'srn_t_common' / 'wall.tga').rename(self.repo / 'srn_t_common' / 'Wall.TGA')
        apply.apply(self.repo, self.spec, self.overlay)
        self.assertNotIn('Wall.TGA', self.names('srn_t_common')); self.assertIn('wall.mtr', self.names('srn_t_common'))
        (self.repo / 'srn_placeable' / 'Wall_N.dds').write_bytes(b'theirs')
        with self.assertRaisesRegex(ValueError, 'wall_n.dds is already a file of srn_placeable'):
            apply.plan(self.repo, self.spec, self.overlay)

    def test_a_map_named_like_another_packs_file_or_a_missing_one_is_refused(self):
        (self.repo / 'srn_placeable' / 'wall_n.dds').write_bytes(b'theirs')
        with self.assertRaisesRegex(ValueError, 'wall_n.dds is already a file of srn_placeable'):
            apply.plan(self.repo, self.spec, self.overlay)
        (self.repo / 'srn_placeable' / 'wall_n.dds').unlink(); (self.overlay / 'bin_n.dds').unlink()
        with self.assertRaisesRegex(ValueError, 'bin: the overlay lacks bin_n.dds'):
            apply.plan(self.repo, self.spec, self.overlay)
        self.assertEqual((self.repo / 'srn_t_common' / 'wall.tga').read_bytes(), b'old')  # a refused plan changes nothing


if __name__ == '__main__':
    unittest.main()
