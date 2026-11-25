"""Lit panes are clear by day and full by night, a pane whose texture has a day texture gets a day pane, and an animation names
the whole line of parents of what it fades."""
import json
import re
import tempfile
import unittest
from pathlib import Path

from tools.tilekit import daylight

REPO = Path(__file__).resolve().parents[2]
PACKS = ('srn_t_udp1', 'srn_door', 'srn_placeable')  # the packs that hold the list's textures: named so the test selector checks them out
CITY = ('srn_t_common', 'srn_t_dgt04')  # the same for the Modern Exterior list
SIGNALS = ('udp1-allsigns', 'udp1-msc-red')  # the suburb's traffic-light lenses, emergency lights and hospital crosses: lit at every hour
ARCOLOGY = ('srn_t_fcx01', 'srn_t_common', 'srn_door')  # and for the Futuristic City's
MODEL = """newmodel t_a01
beginmodelgeom t_a01
node dummy t_a01
  parent NULL
endnode
node dummy lights on
  parent t_a01
endnode
node trimesh pane
  parent lights
  selfillumcolor 0.7 0.7 0.7
  bitmap win_b
  verts 3
    0 0 0
    1 0 0
    0 0 1
endnode
node trimesh lens lit01
  parent lights
  selfillumcolor 1 1 1
  bitmap lens
  verts 3
    0 0 0
    1 0 0
    0 0 1
endnode
node trimesh dull
  parent t_a01
  selfillumcolor 0 0 0
  bitmap win_b
  verts 3
    0 0 0
    1 0 0
    0 0 1
endnode
endmodelgeom t_a01
donemodel t_a01
"""
LIT = {'WIN_B': 'win', 'lens': None}


def anim(text, name):
    return re.search(rf'(?ms)^newanim {name} .*?^doneanim {name} ', text).group(0)


class Daylight(unittest.TestCase):
    def test_lit_meshes_are_the_glowing_ones_of_the_list(self):
        self.assertEqual(daylight.lit_nodes(MODEL, LIT), [('pane', 'lights', 'win_b'), ('lens lit01', 'lights', 'lens')])

    def test_a_lit_pane_is_clear_by_day_and_its_day_pane_the_other_way(self):
        made, lit, panes = daylight.with_daylight(MODEL, LIT)
        self.assertEqual((lit, panes), (2, 1))
        self.assertIn('node trimesh day00_0\n  parent t_a01a\n  selfillumcolor 0 0 0\n  bitmap win\n', made)
        day, turn = anim(made, 'day'), anim(made, 'day2night')
        self.assertIn('node trimesh pane\n    parent t_a01a\n    alphakey 2\n      0.00000 0\n      0.03333 0\n', day)
        self.assertIn('node trimesh day00_0\n    parent t_a01a\n    alphakey 2\n      0.00000 1\n      0.03333 1\n', day)
        self.assertIn('node trimesh pane\n    parent t_a01a\n    alphakey 2\n      0.00000 0\n      0.56667 1\n', turn)
        self.assertIn('node trimesh day00_0\n    parent t_a01a\n    alphakey 2\n      0.00000 1\n      0.56667 0\n', turn)
        self.assertNotIn('dull', day)
        self.assertTrue(made.rstrip().endswith('donemodel t_a01'))
        # a translucent pane shows at its own alpha, its day pane too: the arcology's half-clear glass was keyed solid (review of PR 198)
        glass, _, _ = daylight.with_daylight(MODEL.replace('  selfillumcolor 0.7 0.7 0.7\n', '  alpha 0.5\n  selfillumcolor 0.7 0.7 0.7\n'), LIT)
        self.assertIn('node trimesh pane\n    parent t_a01a\n    alphakey 2\n      0.00000 0\n      0.56667 0.5\n', anim(glass, 'day2night'))
        self.assertIn('node trimesh day00_0\n    parent t_a01a\n    alphakey 2\n      0.00000 0.5\n      0.03333 0.5\n', anim(glass, 'day'))
        self.assertIn('    alphakey 2\n      0.00000 1\n      0.03333 1\n', anim(glass, 'night'))

    def test_an_animation_names_the_parents_and_a_spaced_name_is_replaced(self):
        # Without the parents in the animation the client fell over as the area loaded (pilot, 2026-11-23).
        made = daylight.with_daylight(MODEL, LIT)[0]; day = anim(made, 'day')
        self.assertLess(day.index('node dummy t_a01a\n    parent t_a01\n'), day.index('node trimesh pane'))
        self.assertEqual(day.count('node dummy t_a01a\n'), 1)  # the name as the game reads it, once
        self.assertNotIn('lens lit01', made); self.assertIn('node trimesh lit01_0\n  parent t_a01a\n', made)

    def test_a_model_with_no_lit_mesh_is_left_and_one_with_a_day_already_is_refused(self):
        self.assertEqual(daylight.with_daylight(MODEL, {'other': None}), (MODEL, 0, 0))
        made = daylight.with_daylight(MODEL, LIT)[0]
        with self.assertRaisesRegex(ValueError, 'already'):
            daylight.with_daylight(made, LIT)

    def test_lit_meshes_of_one_name_each_take_their_own(self):
        # two strip mall tiles name every lit window alike (udp1_b12_04, udp1_b13_09)
        twice = MODEL.replace('node trimesh lens lit01', 'node trimesh pane').replace('endmodelgeom t_a01', 'endmodelgeom t_a01\nnewanim loop t_a01\n  node trimesh pane\n    parent lights\n  endnode\n  node trimesh pane\n    parent lights\n  endnode\ndoneanim loop t_a01')
        made = daylight.with_daylight(twice, LIT)[0]; loop = anim(made, 'loop')
        self.assertEqual(re.findall(r'(?m)^node trimesh (lit\S+)', made), ['lit00_0', 'lit01_0'])
        self.assertEqual(re.findall(r'node trimesh (\S+)', loop), ['lit00_0', 'day00_0', 'lit01_0'])  # the first has a day pane, which goes where it goes
        self.assertIn('node trimesh lit00_0\n  parent t_a01a\n  selfillumcolor 0.7 0.7 0.7\n  bitmap win_b', made)
        shared = MODEL.replace('node trimesh dull', 'node trimesh pane')
        with self.assertRaisesRegex(ValueError, 'shares its name'):
            daylight.with_daylight(shared, LIT)

    def test_names_are_taken_as_the_game_reads_them(self):
        # review of PR 193: a parent written with its second word, a kind in capitals, a name that differs only in case
        spaced = MODEL.replace('  parent lights\n', '  parent lights on\n'); day = anim(daylight.with_daylight(spaced, LIT)[0], 'day')
        self.assertLess(day.index('node dummy t_a01a\n    parent t_a01\n'), day.index('node trimesh pane\n    parent t_a01a\n'))
        capital = MODEL.replace('node trimesh lens lit01', 'node Trimesh lens lit01'); made = daylight.with_daylight(capital, LIT)[0]
        self.assertNotIn('lens lit01', made); self.assertIn('node Trimesh lit01_0\n', made)
        with self.assertRaisesRegex(ValueError, 'shares its name'):
            daylight.with_daylight(MODEL.replace('node trimesh dull', 'node trimesh Pane'), LIT)
        with self.assertRaisesRegex(ValueError, 'has children'):
            daylight.with_daylight(MODEL.replace('  parent t_a01\n  selfillumcolor 0 0 0', '  parent lens\n  selfillumcolor 0 0 0'), LIT)

    def test_write_takes_a_merged_set_s_tiles_and_counts_those_already_done(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary); own = repo / 'srn_t_t'; merged = repo / 'srn_t_m'; out = repo / 'out'
            for folder in (own, merged, repo / 'srn_t_common'):
                folder.mkdir()
            for folder, name in ((own, 't'), (merged, 'm')):
                (folder / f'{name}.set').write_text('[TILES]\nCount=1\n[TILE0]\nModel=t_a01\n', encoding='cp1252')
            (own / 't_a01.mdl').write_text(MODEL, encoding='cp1252')
            self.assertEqual(daylight.write(repo, 't', out, LIT)['models'], {})  # the merged set draws it too
            told = daylight.write(repo, 't', out, LIT, shared=['M'])
            self.assertEqual((told['models'], told['panes'], told['done'], told['refused']), ({'t_a01': 2}, 1, 0, {}))
            again = daylight.write(repo, 't', out, LIT, shared=['M'])  # the folder's copy has its day and night: no refusal
            self.assertEqual((again['models'], again['done'], again['refused']), ({}, 1, {}))
            made = (out / 't_a01.mdl').read_text(encoding='cp1252'); self.assertEqual(daylight.with_daylight(daylight.without(made), LIT)[0], made)
            self.assertEqual(daylight.write(repo, 't', out, LIT, shared=['M'], again=True)['models'], {})  # made anew, the same: not written
            anew = daylight.write(repo, 't', out, {**LIT, 'lens': 'glass'}, shared=['M'], again=True)  # the lens given a day texture since
            self.assertEqual((anew['models'], anew['panes']), ({'t_a01': 2}, 2)); made = (out / 't_a01.mdl').read_text(encoding='cp1252')
            self.assertEqual(len(re.findall(r'(?m)^node trimesh day\d+_\d+$', made)), 2); self.assertEqual(made.count('newanim day t_a01'), 1)

    def test_a_tile_whose_lights_a_loop_switches_has_the_loop_on(self):
        # the suburb set shipped every lit building dark: AnimLoop1 off, the lit panes parked under the tile (2026-11-24)
        loop = 'newanim animloop01 t_a01\n  node dummy lights\n    parent t_a01\n    positionkey\n      0 0 0 10\n    endlist\n  endnode\ndoneanim animloop01 t_a01\n'
        moving = MODEL.replace('donemodel', loop + 'donemodel')
        self.assertTrue(daylight.switched(moving, LIT)); self.assertFalse(daylight.switched(MODEL, LIT))
        self.assertFalse(daylight.switched(moving.replace('node dummy lights\n    parent t_a01\n    positionkey', 'node dummy other\n    parent t_a01\n    positionkey'), LIT))
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary); own = repo / 'srn_t_t'; own.mkdir()
            (own / 't.set').write_text('[TILES]\nCount=2\n[TILE0]\nModel=t_a01\nAnimLoop1=0\nAnimLoop2=0\n\n[TILE1]\nModel=t_b01\nAnimLoop1=0\n', encoding='cp1252')
            (own / 't_a01.mdl').write_text(moving, encoding='cp1252'); (own / 't_b01.mdl').write_text(MODEL.replace('t_a01', 't_b01'), encoding='cp1252')
            self.assertEqual(daylight.lights_on(repo, 't', LIT), ['t_a01'])
            self.assertEqual((own / 't.set').read_text(encoding='cp1252'), '[TILES]\nCount=2\n[TILE0]\nModel=t_a01\nAnimLoop1=1\nAnimLoop2=0\n\n[TILE1]\nModel=t_b01\nAnimLoop1=0\n')
            self.assertEqual(daylight.lights_on(repo, 't', LIT), [])
        lit = json.loads((REPO / 'docs' / 'tilesets' / 'udp1' / 'daylight.json').read_text(encoding='utf-8'))['lit']
        from tools.tilekit import inventory
        off = [keys['Model'] for name, keys in inventory.sections((REPO / 'srn_t_udp1' / 'udp1.set').read_text(encoding='cp1252'))
               for loop in daylight.LOOPS
               if re.fullmatch(r'TILE\d+', name) and keys.get(f'AnimLoop{loop}') != '1' and (REPO / 'sources' / 'srn_t_udp1' / f'{keys["Model"].lower()}.mdl').is_file()
               and daylight.switched((REPO / 'sources' / 'srn_t_udp1' / f'{keys["Model"].lower()}.mdl').read_text(encoding='cp1252'), lit, f'animloop0{loop}')]
        self.assertEqual(off, [])  # the suburb set itself

    def test_a_signal_s_states_are_not_switched_on_together(self):
        # A suburb traffic light has a one-second red (animloop02) and its twenty-second cycle (animloop03), and a builder
        # chooses one. Listed as lit signs, `lights_on` turned both on, and the lenses went clear by day (review of PR 198,
        # 2026-11-24): the signals' textures are not in the list, and no tile has two loops on that move one lens.
        from tools.tilekit import inventory
        lit = json.loads((REPO / 'docs' / 'tilesets' / 'udp1' / 'daylight.json').read_text(encoding='utf-8'))['lit']
        self.assertEqual([name for name in SIGNALS if name in lit], [])
        seen = 0
        for tileset in ('udp1', 'srx01'):
            both = []
            for name, keys in inventory.sections((REPO / f'srn_t_{tileset}' / f'{tileset}.set').read_text(encoding='cp1252')):
                source = REPO / 'sources' / 'srn_t_udp1' / f'{keys.get("Model", "").lower()}.mdl'
                if not re.fullmatch(r'TILE\d+', name) or not source.is_file():
                    continue
                text = source.read_text(encoding='cp1252')
                moved = [set(daylight._switched(text, SIGNALS, f'animloop0{loop}')) for loop in daylight.LOOPS if keys.get(f'AnimLoop{loop}') == '1']
                seen += any(daylight._switched(text, SIGNALS, f'animloop0{loop}') for loop in daylight.LOOPS)
                if any(one & other for index, one in enumerate(moved) for other in moved[index + 1:]):
                    both.append(keys['Model'])
            self.assertEqual(both, [], tileset)
        self.assertGreaterEqual(seen, 20)  # the signal tiles were read, in both sets
        # and the same of every set's own list: no tile has two loops on that move one of its lit or switched meshes
        from tools.tilekit import lamps
        for tileset in ('udp1', 'dgt04', 'fcx01'):
            spec = json.loads((REPO / 'docs' / 'tilesets' / tileset / 'daylight.json').read_text(encoding='utf-8'))
            textures = list(spec['lit']) + list(spec.get('switched', ()))
            with tempfile.TemporaryDirectory() as temporary:
                models = {name: text for name, file, text, others, source in inventory.drawn_copies(REPO, tileset, Path(temporary), lamps.PACKS)}
            both = []
            for name, keys in inventory.sections((REPO / f'srn_t_{tileset}' / f'{tileset}.set').read_text(encoding='cp1252')):
                text = models.get(keys.get('Model', '').lower())
                if re.fullmatch(r'TILE\d+', name) and text:
                    moved = [set(daylight._switched(text, textures, f'animloop0{loop}')) for loop in daylight.LOOPS if keys.get(f'AnimLoop{loop}') == '1']
                    if any(one & other for index, one in enumerate(moved) for other in moved[index + 1:]):
                        both.append(keys['Model'])
            self.assertEqual(both, [], tileset)

    def test_line_ends_are_kept(self):
        made = daylight.with_daylight(MODEL.replace('\n', '\r\n'), LIT)[0]
        self.assertNotIn('\n', made.replace('\r\n', ''))

    def test_the_suburb_list_names_textures_the_pack_holds(self):
        lit = json.loads((REPO / 'docs' / 'tilesets' / 'udp1' / 'daylight.json').read_text(encoding='utf-8'))['lit']
        held = {path.stem.lower() for pack in PACKS for path in (REPO / pack).iterdir()}
        self.assertEqual(sorted(name for pair in lit.items() for name in pair if name and name not in held), [])

    def test_the_arcology_list_names_textures_the_packs_hold_and_no_tile_of_it_glows_at_every_hour(self):
        # the Futuristic City's windows and lamp lenses glowed at noon until they were given the day and night (2026-11-24)
        from tools.tilekit import inventory, lamps
        spec = json.loads((REPO / 'docs' / 'tilesets' / 'fcx01' / 'daylight.json').read_text(encoding='utf-8')); lit = spec['lit']
        held = {path.stem.lower() for pack in ARCOLOGY for path in (REPO / pack).iterdir()}
        self.assertEqual(sorted(name for pair in lit.items() for name in pair if name and name not in held), [])
        with tempfile.TemporaryDirectory() as temporary:
            read = [(name, text) for name, file, text, others, source in inventory.drawn_copies(REPO, 'fcx01', Path(temporary), lamps.PACKS) if daylight.lit_nodes(text, lit, mapped=daylight.mapped(spec))]
        self.assertGreater(len(read), 90)  # the sources were read
        self.assertEqual([name for name, text in read if not re.search(r'(?mi)^[ \t]*newanim[ \t]+day[ \t]', text)], [])

    def test_a_lit_mesh_hangs_from_the_tile_s_animated_node_where_it_stood(self):
        # The game plays a tile's animations under the node named as the model with an `a`: the arcology's panes and
        # School 3's hung from the root and never changed with the hour (found 2026-11-24).
        arm = MODEL.replace('node dummy lights on\n  parent t_a01\n', 'node dummy lights on\n  parent t_a01\n  position 1 2 3\n  orientation 0 0 1 1.5707963\n').replace('node trimesh pane\n  parent lights\n', 'node trimesh pane\n  parent lights\n  position 1 0 0\n')
        made, parent = daylight.animated(arm, 'pane'); self.assertEqual(parent, 't_a01a')
        self.assertIn('node dummy t_a01\n  parent NULL\nendnode\nnode dummy t_a01a\n  parent t_a01\nendnode\n', made)
        before, after = daylight._world(daylight._placed(arm), 'pane'), daylight._world(daylight._placed(made), 'pane')
        for old, new in zip(before[0] + before[1], after[0] + after[1]):
            self.assertAlmostEqual(old, new, places=6)
        self.assertAlmostEqual(after[0][1], 3.0, places=6)  # a quarter turn of the arm about z: one along x is one along y
        self.assertEqual(daylight.animated(made, 'pane'), (made, 't_a01a'))  # under it already: left
        # a mesh under a node a loop keys stays under it, and that node is hung there; the loop names the animated node first
        loop = 'newanim animloop01 t_a01\n  node dummy t_a01\n    parent NULL\n  endnode\n  node dummy lights\n    parent t_a01\n    positionkey 1\n      0 0 0 10\n    endlist\n  endnode\ndoneanim animloop01 t_a01\n'
        lifted, parent = daylight.animated(MODEL.replace('donemodel', loop + 'donemodel'), 'pane'); self.assertEqual(parent, 'lights')
        self.assertIn('node dummy lights on\n  parent t_a01a\n', lifted)
        self.assertIn('  node dummy t_a01a\n    parent t_a01\n  endnode\n  node dummy lights\n    parent t_a01a\n    positionkey 1\n', lifted)
        late = loop.replace('doneanim', '  node dummy t_a01a\n    parent t_a01\n  endnode\ndoneanim')  # named after it, as a tile's own loop has it
        moved = daylight.animated(MODEL.replace('node dummy lights on', 'node dummy t_a01a\n  parent t_a01\nendnode\nnode dummy lights on').replace('donemodel', late + 'donemodel'), 'pane')[0]
        names = re.findall(r'(?m)^  node \w+ (\S+)', anim(moved, 'animloop01')); self.assertEqual(names, ['t_a01', 't_a01a', 'lights'])
        with self.assertRaisesRegex(ValueError, 'do not reach'):  # a parent the model lacks: no root to hang the animated node from
            daylight.animated(MODEL.replace('node dummy lights on\n  parent t_a01\n', 'node dummy lights on\n  parent gone\n'), 'pane')
        with self.assertRaisesRegex(ValueError, 'not placed as'):  # the loop moves it in its old parent's frame
            daylight.animated(arm.replace('donemodel', loop.replace('node dummy lights\n    parent t_a01\n', 'node trimesh pane\n    parent lights\n') + 'donemodel'), 'pane')
        # a plain place in an animation is a key too (review of PR 198): the mesh it places is refused, the parent it places keeps its meshes
        with self.assertRaisesRegex(ValueError, 'not placed as'):
            daylight.animated(arm.replace('donemodel', 'newanim animloop01 t_a01\n  node trimesh pane\n    parent lights\n    position 0 0 5\n  endnode\ndoneanim animloop01 t_a01\ndonemodel'), 'pane')
        plain = MODEL.replace('donemodel', 'newanim animloop01 t_a01\n  node dummy lights\n    parent t_a01\n    position 0 0 5\n  endnode\ndoneanim animloop01 t_a01\ndonemodel')
        self.assertEqual(daylight.animated(plain, 'pane')[1], 'lights')
        # the sets: every mesh the hour fades is under its tile's animated node
        loose = []
        for pack in ('srn_t_fcx01', 'srn_t_udp1', 'srn_t_dgt04', 'srn_t_common'):
            for path in sorted((REPO / 'sources' / pack).glob('*.mdl')):
                text = path.read_bytes().decode('cp1252')
                if not re.search(r'(?mi)^[ \t]*newanim[ \t]+night[ \t]', text):
                    continue
                placed = daylight._placed(text); under = f'{path.stem}a'.lower(); night = re.search(r'(?mis)^[ \t]*newanim[ \t]+night[ \t].*?^[ \t]*doneanim', text).group(0)
                loose += [(path.stem, name) for kind, name, body in daylight.NODE.findall(night) if 'alphakey' in body and under not in daylight._line(placed, name.split()[0].lower())[1:]]
        self.assertEqual(loose, [])

    def test_a_mesh_lit_by_its_material_s_glow_map_is_lit_whatever_its_own_glow(self):
        # the arcology's wall bands glow through their material with no glow of their own, and its cyan panes came out
        # blue at night: the game tints a glow map by the mesh's glow colour (2026-11-24)
        self.assertEqual(daylight.mapped({'lit': {'Win_B': 'win_d'}, 'dayMaterials': {'win_d': 'WIN_B'}}), {'win_b'}); self.assertEqual(daylight.mapped({}), set())
        self.assertEqual([node for node, parent, texture in daylight.lit_nodes(MODEL, LIT, mapped={'win_b'})], ['pane', 'lens lit01', 'dull'])
        made, lit, panes = daylight.with_daylight(MODEL, LIT, {'win_b'}); self.assertEqual((lit, panes), (3, 2))
        self.assertIn('node trimesh pane\n  parent t_a01a\n  selfillumcolor 0 0 0\n  bitmap win_b\n', made)
        self.assertIn('node trimesh lit01_0\n  parent t_a01a\n  selfillumcolor 1 1 1\n  bitmap lens\n', made)  # not one of them: its glow is its own
        self.assertEqual(daylight.with_daylight(daylight.without(made), LIT, {'win_b'})[0], made)
        # the loop checks know such a mesh too (review of PR 198): left no glow of its own, it was not seen parked or raised
        raised = made.replace('donemodel', 'newanim animloop01 t_a01\n  node trimesh pane\n    parent t_a01a\n    positionkey 1\n      0 0 0 10\n    endlist\n  endnode\ndoneanim animloop01 t_a01\ndonemodel')
        self.assertFalse(daylight.switched(raised, {'win_b': 'win'})); self.assertTrue(daylight.switched(raised, {'win_b': 'win'}, mapped={'win_b'}))
        self.assertEqual(daylight.never(raised, {'win_b': 'win'}, {'win_b'}), ['dull'])
        with self.assertRaisesRegex(ValueError, 'texture0'):  # under another name it would draw no picture
            daylight.unlit('renderhint NormalAndSpecMapped\ntexture5 win_i\n')
        spec = json.loads((REPO / 'docs' / 'tilesets' / 'fcx01' / 'daylight.json').read_text(encoding='utf-8')); glowing = daylight.mapped(spec); left = []
        self.assertEqual(len(glowing), 6)
        for path in sorted((REPO / 'sources' / 'srn_t_fcx01').glob('*.mdl')):
            text = path.read_bytes().decode('cp1252'); night = re.search(r'(?mis)^[ \t]*newanim[ \t]+night[ \t].*?^[ \t]*doneanim', text)
            faded = {name.split()[0].lower() for kind, name, body in daylight.NODE.findall(night.group(0)) if 'alphakey' in body} if night else set()
            for kind, name, body in daylight.NODE.findall(daylight._geometry(text)):
                if (daylight._field(body, 'bitmap') or '').lower() in glowing and kind.lower() == 'trimesh':
                    shine = daylight._field(body, 'selfillumcolor')
                    if name.split()[0].lower() not in faded or (shine and max(map(float, shine.split())) > 0):
                        left.append((path.stem, name))
        self.assertEqual(left, [])

    def test_a_day_material_is_the_lit_one_without_its_glow_map(self):
        # as its own day texture a glow-mapped pane was as bright at noon as at night: the arcology (review of PR 198, 2026-11-24)
        material = 'renderhint NormalAndSpecMapped\n\ntexture0 win\ntexture1 win_n\ntexture4 null\ntexture5 win_i\n'
        self.assertEqual(daylight.unlit(material), material.replace('texture5 win_i', 'texture5 null'))
        with self.assertRaises(ValueError):
            daylight.unlit(daylight.unlit(material))
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary); (repo / 'a').mkdir(); (repo / 'b').mkdir(); (repo / 'b' / 'win.mtr').write_bytes(material.encode('ascii'))
            spec = {'lit': {'win': 'win_d'}, 'dayMaterials': {'win_d': 'win'}}
            self.assertEqual(daylight.day_materials(repo, spec, ['a', 'b'], check=True), {'win_d': 'b'}); self.assertFalse((repo / 'b' / 'win_d.mtr').exists())
            self.assertEqual(daylight.day_materials(repo, spec, ['a', 'b']), {'win_d': 'b'})
            self.assertEqual((repo / 'b' / 'win_d.mtr').read_bytes(), daylight.unlit(material).encode('ascii'))
            self.assertEqual(daylight.day_materials(repo, spec, ['a', 'b']), {})
            for bad in ({'Win_D': 'win'}, {'win': 'win'}, {'a_name_longer_than_one': 'win'}, {'win_d': 'none'}):
                with self.assertRaises(ValueError):
                    daylight.day_materials(repo, {'lit': {'win': next(iter(bad))}, 'dayMaterials': bad}, ['a', 'b'])
            for lit in ({}, {'win': 'other'}, {'win': None}):  # not the lit texture's day texture in the list
                with self.assertRaisesRegex(ValueError, 'is the day texture of'):
                    daylight.day_materials(repo, {'lit': lit, 'dayMaterials': {'win_d': 'win'}}, ['a', 'b'])
        # the lists: every day material is in the packs as its lit one makes it, and no day texture has a glow map
        for tileset, packs in (('fcx01', ARCOLOGY), ('udp1', PACKS), ('dgt04', CITY)):
            spec = json.loads((REPO / 'docs' / 'tilesets' / tileset / 'daylight.json').read_text(encoding='utf-8'))
            self.assertEqual(daylight.day_materials(REPO, spec, packs, check=True), {}, tileset)
            self.assertEqual(sorted(set(spec.get('dayMaterials', {})) - set(spec['lit'].values())), [], tileset)
            glowing = [day for day in set(filter(None, spec['lit'].values())) for pack in packs
                       if (REPO / pack / f'{day}.mtr').is_file() and re.search(r'(?mi)^[ \t]*texture5[ \t]+(?!null\b)\S', (REPO / pack / f'{day}.mtr').read_text(encoding='ascii'))]
            self.assertEqual(glowing, [], tileset)

    def test_the_city_list_names_textures_the_packs_hold_and_no_tile_of_it_glows_at_every_hour(self):
        # the Modern Exterior windows glowed at noon until its lit panes were given the day and night (2026-11-24)
        from tools.tilekit import inventory, lamps
        lit = json.loads((REPO / 'docs' / 'tilesets' / 'dgt04' / 'daylight.json').read_text(encoding='utf-8'))['lit']
        held = {path.stem.lower() for pack in CITY for path in (REPO / pack).iterdir()}
        self.assertEqual(sorted(name for pair in lit.items() for name in pair if name and name not in held), [])
        with tempfile.TemporaryDirectory() as temporary:
            read = [(name, text) for name, file, text, others, source in inventory.drawn_copies(REPO, 'dgt04', Path(temporary), lamps.PACKS) if daylight.lit_nodes(text, lit)]
        self.assertGreater(len(read), 150)  # the sources were read: without them every model is compiled and none is looked at
        self.assertEqual([name for name, text in read if not re.search(r'(?mi)^[ \t]*newanim[ \t]+day[ \t]', text)], [])
        # a tile loop lifts a lit pane into place from where it is parked; its day pane was left behind, and the windows
        # that lit at night were bare wall by day (review of PR 194, 2026-11-24): a day pane is moved wherever its lit pane is
        behind = []
        for name, text in read:
            nodes = daylight.NODE.findall(daylight._geometry(text))
            for (kind, lit_pane, body), (_, pane, _) in zip(nodes, nodes[1:]):
                if daylight.PANE.match(pane) and not daylight.PANE.match(lit_pane):
                    for part in re.split(r'(?mi)^[ \t]*newanim[ \t]+', text)[1:]:
                        keyed = {one.split()[0].lower(): re.findall(r'(?mi)^[ \t]*positionkey[^\n]*\n([^\n]*)|^[ \t]*position[ \t]+([^\r\n]*)', block)  # keyed, or a plain place
                                 for _, one, block in daylight.NODE.findall(part)}
                        if keyed.get(lit_pane.split()[0].lower()) != keyed.get(pane.lower()):
                            behind.append((name, pane, part.split()[0]))
        self.assertEqual(behind, [])
        from tools.tilekit import inventory as sets
        spec = json.loads((REPO / 'docs' / 'tilesets' / 'dgt04' / 'daylight.json').read_text(encoding='utf-8')); lit = daylight.switches(spec)
        self.assertEqual(sorted(name for name in spec['switched'] if name not in held), [])  # the signs a loop raises, lit at every hour
        with tempfile.TemporaryDirectory() as temporary:
            signs = [(name, text) for name, file, text, others, source in inventory.drawn_copies(REPO, 'dgt04', Path(temporary), lamps.PACKS) if daylight.lit_nodes(text, lit)]
        for tileset in ('dgt04', 'srx01'):  # and the lights are on unless turned off, as the suburb's
            models = {name: text for name, text in signs}
            off = [keys['Model'] for section, keys in sets.sections((REPO / f'srn_t_{tileset}' / f'{tileset}.set').read_text(encoding='cp1252'))
                   for loop in daylight.LOOPS  # the shops switch their shop window by the second loop
                   if re.fullmatch(r'TILE\d+', section) and keys.get(f'AnimLoop{loop}') != '1' and daylight.switched(models.get(keys['Model'].lower(), ''), lit, f'animloop0{loop}')]
            self.assertEqual(off, [], tileset)
        # and no lit pane is left parked where the others of its tile are raised (the pawn shop window, 2026-11-24)
        self.assertEqual([(name, daylight.never(text, lit)) for name, text in read if daylight.never(text, lit)], [])

    def test_an_animation_names_a_node_once(self):
        # a lit window hung from a lit lens: the lens was named twice and the night never came (police and fire stations, 2026-11-24)
        hung = MODEL.replace('node dummy lights on\n  parent t_a01\nendnode\n', 'node trimesh lights\n  parent t_a01\n  selfillumcolor 1 1 1\n  bitmap lens\n  verts 3\n    0 0 0\n    1 0 0\n    0 0 1\nendnode\n')
        for text in (hung, hung.replace('node trimesh lights\n', 'node trimesh zlast\n', 1).replace('endmodelgeom', 'node trimesh lights\n  parent t_a01\n  selfillumcolor 1 1 1\n  bitmap lens\n  verts 3\n    0 0 0\n    1 0 0\n    0 0 1\nendnode\nendmodelgeom')):
            night = anim(daylight.with_daylight(text, LIT)[0], 'night'); names = re.findall(r'(?m)^  node \w+ (\S+)', night)
            self.assertEqual(len(names), len(set(names)), names)
            self.assertLess(names.index('lights'), names.index('pane'))  # a parent before what hangs from it
            self.assertIn('node trimesh lights\n    parent t_a01a\n    alphakey 2', night)
        twice = []
        for pack in ('srn_t_udp1', 'srn_t_common', 'srn_t_dgt04'):
            for path in sorted((REPO / 'sources' / pack).glob('*.mdl')):
                text = path.read_bytes().decode('cp1252')
                for part in re.split(r'(?mi)^[ \t]*newanim[ \t]+', text)[1:]:
                    names = [name.split()[0].lower() for _, name, _ in daylight.NODE.findall(part)] if part.split()[0].lower() in daylight.ANIMS else []
                    if len(names) != len(set(names)):
                        twice.append((path.stem, part.split()[0]))
        self.assertEqual(twice, [])

    def test_a_day_pane_goes_where_a_loop_moves_its_lit_pane(self):
        loop = 'newanim animloop01 t_a01\n  node dummy t_a01\n    parent NULL\n  endnode\n  node trimesh pane\n    parent lights\n    positionkey 1\n      0 0 0 10\n    endlist\n  endnode\ndoneanim animloop01 t_a01\n'
        moving = MODEL.replace('donemodel', loop + 'donemodel')
        self.assertTrue(daylight.switched(moving, LIT))  # the lit mesh itself is moved
        self.assertFalse(daylight.switched(moving.replace('0 0 0 10', '0 0 0 0'), LIT))  # keyed where it rests: not moved
        new, count, panes = daylight.with_daylight(moving, LIT)
        self.assertEqual(panes, 1)
        part = next(one for one in re.split(r'(?mi)^[ \t]*newanim[ \t]+', new)[1:] if one.startswith('animloop01'))
        names = [one for _, one, block in daylight.NODE.findall(part) if 'positionkey' in block]
        self.assertEqual(len(names), 2); self.assertTrue(daylight.PANE.match(names[1]))
        bare = daylight.without(new)  # and it is taken out of the loop again with its pane
        self.assertNotIn('day00_0', bare); self.assertEqual(daylight.with_daylight(bare, LIT)[0], new)


if __name__ == '__main__':
    unittest.main()
