"""Applying a review overlay: where each texture's files go, what is deleted, and the expected overrides."""
import hashlib
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
        with self.assertRaisesRegex(ValueError, 'n_t01.mdl is new, and the overlay has no made-from.json'):  # new tiles come with a whole copy
            apply.plan(self.repo, {'tileset': 'tst'}, overlay)
        bare = {'kind': 'tilekit-terrain-copy', 'from': {}}
        (overlay / apply.MADE_FROM).write_text(json.dumps(bare), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'n_t01.mdl is new, and made-from.json catalogues no tile of it'):  # a stray model is not installed
            apply.plan(self.repo, {'tileset': 'tst'}, overlay)
        self.catalog(); entry = {'tileset': 'tst', 'terrain': 'Tower_2', 'tiles': [2], 'models': ['n_t01'], 'pack': 'srn_t_tst', 'madeBy': 'tilekit', 'source': 's', 'provenance': 'p', 'added': '2026-11-19'}
        (overlay / apply.MADE_FROM).write_text(json.dumps({**bare, 'catalog': {'terrainTiles': [entry]}}), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'tst.set: a set file, edge table or palette replaces its pack copy only with the made-from.json'):  # the record holds no hash of it
            apply.plan(self.repo, {'tileset': 'tst'}, overlay)
        made_from = lambda data: json.dumps({**bare, 'from': {'tst.set': hashlib.sha256(data).hexdigest()}, 'catalog': {'terrainTiles': [entry]}})
        (overlay / apply.MADE_FROM).write_text(made_from(laid(2)), encoding='utf-8')
        (overlay / 'n_t01.wok').unlink()
        with self.assertRaisesRegex(ValueError, 'The overlay lacks what its made-from.json says the copy made: n_t01.wok'):  # a new tile is its model and its walkmesh
            apply.plan(self.repo, {'tileset': 'tst'}, overlay)
        (overlay / 'n_t01.wok').write_bytes(b'walk'); (overlay / 'tst.set').rename(overlay / 'tst.kept')
        with self.assertRaisesRegex(ValueError, 'lacks what its made-from.json says the copy made: tst.set'):  # a copy applies whole
            apply.plan(self.repo, {'tileset': 'tst'}, overlay)
        (overlay / 'tst.kept').rename(overlay / 'tst.set')
        (overlay / apply.MADE_FROM).write_text(json.dumps({**json.loads(made_from(laid(2))), 'textures': ['flat_wall']}), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'name textures no pack holds and this apply brings none of: flat_wall'):  # a copy's tiles come with their textures
            apply.plan(self.repo, {'tileset': 'tst'}, overlay)
        (self.repo / 'srn_t_common' / 'flat_wall.dds').write_bytes(b'dds'); self.assertEqual(len(apply.plan(self.repo, {'tileset': 'tst'}, overlay)['put']), 3)
        (self.repo / 'srn_t_common' / 'flat_wall.dds').unlink(); (overlay / apply.MADE_FROM).write_text(made_from(laid(2)), encoding='utf-8')
        told = apply.apply(self.repo, {'tileset': 'tst'}, overlay)
        self.assertEqual((told['put'], told['not applied']), (3, [])); self.assertEqual(self.names('srn_t_tst'), ['n_t01.mdl', 'n_t01.wok', 'tst.set'])
        self.assertEqual((self.repo / 'srn_t_tst' / 'tst.set').read_bytes(), laid(3))
        (overlay / 'n_t01.wok').write_bytes(b'moved')
        with self.assertRaisesRegex(ValueError, 'a walkmesh in a pack is not replaced'):
            apply.plan(self.repo, {'tileset': 'tst'}, overlay)
        (overlay / 'n_t01.wok').write_bytes(b'walk')
        (self.repo / 'srn_t_tst' / 'tst.set').write_bytes(laid(4))  # another addition since the overlay was made
        with self.assertRaisesRegex(ValueError, 'tst.set: the pack copy changed since the overlay was made'):
            apply.plan(self.repo, {'tileset': 'tst'}, overlay)
        (overlay / apply.MADE_FROM).write_text(made_from(laid(4)), encoding='utf-8')  # a record that matches, held to the entries all the same
        with self.assertRaisesRegex(ValueError, 'tst.set: it lacks or changes entries the pack copy has'):
            apply.plan(self.repo, {'tileset': 'tst'}, overlay)
        with self.assertRaisesRegex(ValueError, 'is new: the spec names the tileset'):
            (overlay / apply.MADE_FROM).write_text(json.dumps(bare), encoding='utf-8')
            (overlay / 'n_t01.wok').unlink(); (overlay / 'n_t02.mdl').write_bytes(b'model'); apply.plan(self.repo, None, overlay)

    def test_a_copy_s_edge_tile_comes_with_its_record_and_needs_no_walkmesh(self):
        overlay = self.overlay.parent / 'edged'; overlay.mkdir()
        (overlay / apply.MADE_FROM).write_text(json.dumps({'kind': 'tilekit-terrain-copy', 'from': {}, 'edges': ['n_z01']}), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'lacks what its made-from.json says the copy made: n_z01.mdl'):
            apply.plan(self.repo, {'tileset': 'tst'}, overlay)
        (overlay / 'n_z01.mdl').write_bytes(b'model')
        self.assertEqual([(path.name, target.parent.name) for path, target in apply.plan(self.repo, {'tileset': 'tst'}, overlay)['put']], [('n_z01.mdl', 'srn_t_tst')])

    def catalog(self):
        (self.repo / 'docs' / 'additions').mkdir(parents=True)
        (self.repo / 'docs' / 'additions' / 'catalog.json').write_text(json.dumps({'schemaVersion': 1, 'kind': 'srn-additions-catalog', 'placeables': [], 'tileGroups': [],
            'baseline': {'placeables': {'table': 't.2da', 'lastImportedRow': 0}, 'tilesets': {'tst': {'set': 'srn_t_tst/tst.set', 'importedTiles': 3, 'importedGroups': 1}}}}), encoding='utf-8')

    def test_a_palette_replaces_its_pack_copy_only_with_the_record_of_the_copy_that_made_it(self):
        overlay = self.overlay.parent / 'palette'; overlay.mkdir(); (overlay / 'tstpalstd.itp').write_bytes(b'palette 2'); (self.repo / 'srn_t_tst' / 'tstpalstd.itp').write_bytes(b'palette 1')
        with self.assertRaisesRegex(ValueError, 'tstpalstd.itp: a set file, edge table or palette replaces its pack copy only with the made-from.json'):
            apply.plan(self.repo, {'tileset': 'tst'}, overlay)
        (self.repo / 'srn_t_tst' / 'tstpalstd.itp').write_bytes(b'palette 2')  # one in place already is applied again
        self.assertEqual(len(apply.plan(self.repo, {'tileset': 'tst'}, overlay)['put']), 1)

    def test_a_copy_s_record_holds_its_tables_to_the_pack_files_they_were_made_from_and_writes_its_catalog_entries(self):
        import hashlib
        overlay = self.overlay.parent / 'copied'; overlay.mkdir(); (overlay / 'tstpalstd.itp').write_bytes(b'palette 2'); (self.repo / 'srn_t_tst' / 'tstpalstd.itp').write_bytes(b'palette 1')
        entry = {'tileset': 'tst', 'pack': 'srn_t_tst', 'madeBy': 'tilekit', 'source': 'specs/towers.json', 'provenance': 'Towers', 'added': '2026-11-19'}
        record = {'kind': 'tilekit-terrain-copy', 'from': {'TstPalStd.itp': hashlib.sha256(b'palette 1').hexdigest()},  # a name read in any case
                  'catalog': {'terrainTiles': [{**entry, 'terrain': 'Tower_2', 'tiles': [3], 'models': ['n_t01']}],
                              'tileGroups': [{**entry, 'group': 1, 'name': 'Flats_Roof', 'rows': 1, 'columns': 1, 'tiles': [3], 'models': ['n_t01']}]}}
        (overlay / apply.MADE_FROM).write_text(json.dumps(record), encoding='utf-8'); self.catalog()
        (overlay / 'n_t01.mdl').write_bytes(b'model'); (overlay / 'n_t01.wok').write_bytes(b'walk')  # the tile the record catalogues
        (self.repo / 'srn_t_tst' / 'tstpalstd.itp').write_bytes(b'palette 1b')  # changed since the copy was made
        with self.assertRaisesRegex(ValueError, 'tstpalstd.itp: the pack copy changed since the overlay was made'):
            apply.plan(self.repo, {'tileset': 'tst'}, overlay)
        (self.repo / 'srn_t_tst' / 'tstpalstd.itp').write_bytes(b'palette 1')
        told = apply.apply(self.repo, {'tileset': 'tst'}, overlay)
        self.assertEqual((told['put'], told['not applied'], told['catalogued']), (3, [], True))  # the record itself is no pack file
        written = json.loads((self.repo / 'docs' / 'additions' / 'catalog.json').read_text(encoding='utf-8'))
        self.assertEqual(([one['terrain'] for one in written['terrainTiles']], [one['group'] for one in written['tileGroups']]), (['Tower_2'], [1]))
        import datetime
        self.assertEqual({one['added'] for one in written['terrainTiles'] + written['tileGroups']}, {datetime.date.today().isoformat()})  # the day they reached the packs
        apply.apply(self.repo, {'tileset': 'tst'}, overlay); written = json.loads((self.repo / 'docs' / 'additions' / 'catalog.json').read_text(encoding='utf-8'))  # applied again
        self.assertEqual((len(written['terrainTiles']), len(written['tileGroups'])), (1, 1))
        moved = {**record, 'catalog': {'terrainTiles': [{**record['catalog']['terrainTiles'][0], 'tiles': [4]}]}}  # numbers once given are kept
        (overlay / apply.MADE_FROM).write_text(json.dumps(moved), encoding='utf-8'); (self.repo / 'srn_t_tst' / 'tstpalstd.itp').write_bytes(b'palette 1')
        with self.assertRaisesRegex(ValueError, r'Terrain Tower_2 of tst has tiles \[3\] in the additions catalog'):
            apply.apply(self.repo, {'tileset': 'tst'}, overlay)
        self.assertEqual((self.repo / 'srn_t_tst' / 'tstpalstd.itp').read_bytes(), b'palette 1')  # refused before anything was written
        clash = {**record, 'catalog': {'terrainTiles': [{**record['catalog']['terrainTiles'][0], 'terrain': 'Tower_3'}]}}  # tile 3 is Tower_2's
        (overlay / apply.MADE_FROM).write_text(json.dumps(clash), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'more than one entry for'):
            apply.plan(self.repo, {'tileset': 'tst'}, overlay)
        for wrong, message in (({**record, 'kind': 'other'}, 'is not a terrain copy'), ({**record, 'textures': [None]}, 'is not a terrain copy'),
                               ({**record, 'catalog': {'terrainTiles': [{'tileset': 'tst', 'terrain': 'Tower_4'}]}}, 'A terrain tiles entry is incomplete'), (record, 'is a copy of tst, not of the spec')):
            (overlay / apply.MADE_FROM).write_text(json.dumps(wrong), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, message):
                apply.plan(self.repo, {'tileset': 'oth'} if wrong is record else {'tileset': 'tst'}, overlay)

    def test_a_changed_model_replaces_only_the_pack_copy_it_was_made_from(self):
        apply.noted(self.overlay, 'T_A01.mdl', self.repo / 'srn_t_common' / 't_a01.mdl')  # as lamps and shadows record it
        apply.noted(self.overlay, 't_a01.mdl', self.overlay / 't_a01.mdl')  # changed again (shadows after lamps): still made from the first
        self.assertEqual(json.loads((self.overlay / apply.MODELS_FROM).read_text(encoding='utf-8')), {'t_a01.mdl': hashlib.sha256(b'old').hexdigest()})
        (self.repo / 'srn_t_common' / 't_a01.mdl').write_bytes(b'changed since')  # another overlay applied, or a hand edit
        with self.assertRaisesRegex(ValueError, 't_a01.mdl: the pack copy changed since the overlay copy was made from it'):
            apply.plan(self.repo, None, self.overlay)
        (self.repo / 'srn_t_common' / 't_a01.mdl').write_bytes(b'old')
        told = apply.apply(self.repo, None, self.overlay); self.assertEqual(told['put'], 1); self.assertNotIn(apply.MODELS_FROM, told['not applied'])  # the record is no pack file
        self.assertEqual(len(apply.plan(self.repo, None, self.overlay)['put']), 1)  # applied again: in place already

    def test_a_plain_texture_takes_away_the_material_an_earlier_apply_put_in(self):
        apply.apply(self.repo, self.spec, self.overlay)
        for name in ('wall.mtr', 'wall_n.dds'):
            (self.overlay / name).unlink()
        (self.overlay / 'wall.txi').write_bytes(b'envmap x')  # the look the game makes from its TXI, which the material would take over
        apply.apply(self.repo, self.spec, self.overlay)
        self.assertEqual([name for name in self.names('srn_t_common') if name.startswith('wall')], ['wall.dds', 'wall.txi'])

    def test_a_copy_of_a_tileset_the_catalog_has_no_baseline_for_is_refused(self):
        overlay = self.overlay.parent / 'unknown'; overlay.mkdir(); self.catalog(); path = self.repo / 'docs' / 'additions' / 'catalog.json'
        data = json.loads(path.read_text(encoding='utf-8')); data['baseline']['tilesets'] = {}; path.write_text(json.dumps(data), encoding='utf-8')  # tst has none
        entry = {'tileset': 'tst', 'terrain': 'Tower_2', 'tiles': [2], 'models': ['n_t01'], 'pack': 'srn_t_tst', 'madeBy': 'tilekit', 'source': 's', 'provenance': 'p', 'added': '2026-11-19'}
        (overlay / apply.MADE_FROM).write_text(json.dumps({'kind': 'tilekit-terrain-copy', 'from': {}, 'catalog': {'terrainTiles': [entry]}}), encoding='utf-8')
        (overlay / 'n_t01.mdl').write_bytes(b'model'); (overlay / 'n_t01.wok').write_bytes(b'walk')
        with self.assertRaisesRegex(ValueError, 'The additions catalog has no baseline for tst'):  # as envkit's install refuses it
            apply.plan(self.repo, {'tileset': 'tst'}, overlay)
        for wrong in ({'edges': 5}, {'catalog': []}):  # refused in words, not thrown
            (overlay / apply.MADE_FROM).write_text(json.dumps({'kind': 'tilekit-terrain-copy', 'from': {}, **wrong}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'is not a terrain copy'):
                apply.plan(self.repo, {'tileset': 'tst'}, overlay)

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
