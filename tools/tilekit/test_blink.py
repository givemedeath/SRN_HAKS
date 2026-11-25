import json
import re
import unittest
from pathlib import Path

import numpy as np

from tools.tilekit import blink, daylight, material, pictures

REPO = Path(__file__).resolve().parents[2]
# a desk of two flats that meet in a fold at v 0.5: the lower one lies flat, the upper one stands
MODEL = """newmodel t_a01
beginmodelgeom t_a01
node dummy t_a01
  parent NULL
endnode
node trimesh desk
  parent t_a01
  position 1 2 3
  bitmap console
  verts 6
    0 0 0
    2 0 0
    2 1 0
    0 1 0
    2 1 1
    0 1 1
  faces 4
    0 1 2  1  0 1 2  1
    0 2 3  1  0 2 3  1
    3 2 4  1  3 2 4  1
    3 4 5  1  3 4 5  1
  tverts 6
    0 0 0
    1 0 0
    1 0.5 0
    0 0.5 0
    1 1 0
    0 1 0
endnode
endmodelgeom t_a01
donemodel t_a01
"""
SPEC = {'texture': 'Console', 'lamp': 'Plain', 'patch': [0.1, 0.1, 0.2, 0.2], 'period': 4.0, 'lift': 0.01,
        'lights': {'red': {'boxes': [[0.25, 0.7, 0.5, 0.9]], 'colour': [1, 0.1, 0], 'on': [[0.0, 1.0], [2.0, 3.0]]},
                   'green': {'boxes': [[0.5, 0.1, 0.75, 0.3]], 'colour': [0, 1, 0.2], 'on': [[1.5, 3.5]]}}}


class Blink(unittest.TestCase):
    def test_a_pane_lies_just_over_the_face_that_draws_its_box(self):
        body = daylight.NODE.search(MODEL[MODEL.index('node trimesh'):]).group(3)
        (quad,) = blink.panes(body, [[0.25, 0.7, 0.5, 0.9]], 0.01)  # the top of the picture first: v 0.3 to 0.1, on the flat that lies
        self.assertEqual([tuple(round(value, 4) for value in corner) for corner in quad], [(0.5, 0.6, 0.01), (1.0, 0.6, 0.01), (1.0, 0.2, 0.01), (0.5, 0.2, 0.01)][::-1])
        (stood,) = blink.panes(body, [[0.5, 0.1, 0.75, 0.3]], 0.01)  # on the flat that stands: lifted towards -y, as it faces
        self.assertEqual({round(corner[1], 4) for corner in stood}, {0.99}); self.assertEqual(sorted({round(corner[2], 4) for corner in stood}), [0.4, 0.8])
        for quad, normal in ((quad, (0, 0, 1)), (stood, (0, -1, 0))):  # it faces as the face under it does
            facing = blink._cross(blink._minus(quad[1], quad[0]), blink._minus(quad[2], quad[0]))
            self.assertGreater(sum(a * b for a, b in zip(facing, normal)), 0)
        self.assertEqual(blink.panes(body, [[1.2, 0.1, 1.4, 0.3]], 0.01), [])  # nothing of the mesh draws it
        self.assertEqual(len(blink.panes(body, [[0.4, 0.7, 0.6, 0.8]], 0.01)), 1)  # its middle on the edge two faces share: one pane (review of PR 198)
        with self.assertRaisesRegex(ValueError, 'runs off the flat'):
            blink.panes(body, [[0.25, 0.4, 0.5, 0.6]], 0.01)  # over the fold

    def test_lamp_panes_rest_clear_under_the_animated_node_and_the_loop_blinks_them(self):
        made, count = blink.with_lights(MODEL, SPEC); self.assertEqual(count, 2)
        self.assertEqual(blink.with_lights(MODEL, {**SPEC, 'texture': 'other'}), (MODEL, 0))
        lamps = {name: body for kind, name, body in daylight.NODE.findall(daylight._geometry(made)) if blink.LAMP.match(name)}
        self.assertEqual(sorted(lamps), ['blink00', 'blink01'])
        for body, colour in zip(lamps.values(), ('1 0.1 0', '0 1 0.2')):
            self.assertEqual([daylight._field(body, word) for word in ('parent', 'position', 'alpha', 'selfillumcolor', 'diffuse', 'ambient', 'bitmap', 'shadow')],
                             ['t_a01a', '1 2 3', '0.0', colour, '0 0 0', '0 0 0', 'plain', '0'])
            self.assertIn('  tverts 4\n    0.100000 0.900000 0\n    0.200000 0.900000 0\n    0.200000 0.800000 0\n    0.100000 0.800000 0\n', body)
        loop = re.search(r'(?ms)^newanim animloop01 t_a01\n.*?^doneanim animloop01 t_a01', made).group(0)
        self.assertIn('  length 4.00000\n', loop); self.assertLess(loop.index('node dummy t_a01a\n    parent t_a01\n'), loop.index('node trimesh blink00'))
        self.assertIn('  node trimesh blink00\n    parent t_a01a\n    alphakey 8\n      0.00000 1\n      1.00000 1\n      1.02000 0\n      1.98000 0\n      2.00000 1\n      3.00000 1\n      3.02000 0\n      4.00000 0\n    endlist\n', loop)
        self.assertIn('  node trimesh blink01\n    parent t_a01a\n    alphakey 6\n      0.00000 0\n      1.48000 0\n      1.50000 1\n      3.50000 1\n      3.52000 0\n      4.00000 0\n    endlist\n', loop)
        bare = blink.without(made); self.assertNotIn('blink', bare); self.assertNotIn('newanim', bare); self.assertEqual(blink.with_lights(bare, SPEC)[0], made)
        self.assertEqual(blink.without(MODEL), MODEL)
        close = blink.with_lights(MODEL, {**SPEC, 'lights': {'red': {**SPEC['lights']['red'], 'on': [[0.1, 0.7], [0.74, 1.0]]}}})[0]  # two edges apart: no key time twice
        times = re.findall(r'(?m)^      (\d+\.\d+) ', close); self.assertEqual(len(times), len(set(times)), times)
        # an animation that keys nothing and blinked no lamp is the tile's own, and stays (review of PR 198)
        own = 'newanim tiledefault t_a01\n  node emitter spray\n    parent t_a01\n  endnode\ndoneanim tiledefault t_a01\n'
        kept = made.replace('newanim animloop01', own + 'newanim animloop01'); self.assertEqual(blink.without(kept), bare.replace('donemodel', own + 'donemodel'))
        for lack in ('texture', 'lamp', 'patch', 'period', 'lights'):
            with self.assertRaisesRegex(ValueError, 'A blink list has'):
                blink.with_lights(MODEL, {key: value for key, value in SPEC.items() if key != lack})
        with self.assertRaisesRegex(ValueError, 'its boxes are'):
            blink.with_lights(MODEL, {**SPEC, 'lights': {'red': {**SPEC['lights']['red'], 'boxes': [[0.25, 0.7, 0.5]]}}})
        for wrong, told in ((made, 'lamp panes already'), (MODEL.replace('donemodel', 'newanim animloop01 t_a01\ndoneanim animloop01 t_a01\ndonemodel'), 'has the loop')):
            with self.assertRaisesRegex(ValueError, told):
                blink.with_lights(wrong, SPEC)
        for lights in ({'red': {**SPEC['lights']['red'], 'on': [[0.0, 4.0]]}}, {'red': {**SPEC['lights']['red'], 'on': [[1.0, 2.0], [2.0, 3.0]]}}, {'red': {**SPEC['lights']['red'], 'colour': [2, 0, 0]}}):
            with self.assertRaises(ValueError):
                blink.with_lights(MODEL, {**SPEC, 'lights': lights})

    def test_made_anew_a_model_loses_the_lamps_the_list_no_longer_has(self):
        # review of PR 198: a model the list gave no pane any more was not written, and kept its old lamps
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary); out = repo / 'out'
            for folder in ('srn_t_t', 'srn_t_common'):
                (repo / folder).mkdir()
            (repo / 'srn_t_t' / 't.set').write_text('[TILES]\nCount=1\n[TILE0]\nModel=t_a01\n', encoding='cp1252')
            (repo / 'srn_t_t' / 't_a01.mdl').write_text(MODEL, encoding='cp1252')
            with self.assertRaisesRegex(ValueError, 'A blink list has'):
                blink.with_lights(MODEL, {**SPEC, 'lamp': ' '})
            with self.assertRaisesRegex(ValueError, 'A blink list has'):  # and not that no pack has it
                blink.write(repo, 't', out, {key: value for key, value in SPEC.items() if key != 'lamp'})
            (repo / 'srn_t_common' / 'Plain.mtr').write_text('texture5 glow', encoding='ascii')  # through a material the lamps come out pale (review of PR 199)
            with self.assertRaisesRegex(ValueError, 'has a material in srn_t_common'):
                blink.write(repo, 't', out, SPEC)
            (repo / 'srn_t_common' / 'Plain.mtr').unlink()
            with self.assertRaisesRegex(ValueError, 'No pack has the lamp picture plain'):
                blink.write(repo, 't', out, SPEC)
            (repo / 'srn_t_common' / 'plain.dds').write_bytes(b'picture')
            self.assertEqual(blink.write(repo, 't', out, SPEC)['models'], {'t_a01': 2})
            self.assertEqual(blink.write(repo, 't', out, SPEC), {'models': {}, 'refused': {}, 'done': 1})  # it has them: left
            self.assertEqual(blink.write(repo, 't', out, SPEC, again=True)['models'], {})  # made anew, the same: not written
            gone = {**SPEC, 'lights': {'red': {**SPEC['lights']['red'], 'boxes': [[1.2, 0.1, 1.4, 0.3]]}}}
            self.assertEqual(blink.write(repo, 't', out, gone, again=True)['models'], {'t_a01': 0})
            self.assertEqual(blink.without((out / 't_a01.mdl').read_text(encoding='cp1252')), (out / 't_a01.mdl').read_text(encoding='cp1252'))

    def test_a_glow_s_boxes_light_only_what_is_inside_them(self):
        colour = np.full((8, 8, 3), 200, np.uint8); colour[:, 4:] = 90
        lit = material.glow({'colour': colour}, {'boxes': [{'box': [0, 0, 0.5, 0.5]}, {'box': [0.5, 0.5, 1, 1], 'above': 100}]})
        self.assertTrue((lit[:4, :4] == 200).all()); self.assertEqual(int(lit.sum()), 16 * 3 * 200)  # the second box's pixels are under its own threshold
        self.assertEqual(int(material.glow({'colour': colour}, {'above': 250, 'boxes': [{'box': [0, 0, 1, 1], 'above': 50}]}).min()), 90)
        for wrong in ([{'box': [0.5, 0.5, 0.51, 0.51]}], [{'box': [0.5, 0, 0.5, 1]}], [{'box': [0, 0, 1, 1.5]}], [{'box': [0, 0, 1, 1], 'gain': 2}], [[0, 0, 1, 1]]):
            with self.assertRaises(ValueError):
                material.glow({'colour': colour}, {'boxes': wrong})

    def test_the_arcology_console_has_its_lights(self):
        # user, 2026-11-24: the wall console needs a few glowing and blinking lights
        spec = json.loads((REPO / 'docs' / 'tilesets' / 'fcx01' / 'blink.json').read_text(encoding='utf-8')); pack = REPO / 'srn_t_fcx01'
        boxes = sum(len(how['boxes']) for how in spec['lights'].values())
        for name in ('fcx01_m01_02', 'fcx01_m01_11'):  # two consoles in each: the list made anew gives the source as it is
            text = (REPO / 'sources' / 'srn_t_fcx01' / f'{name}.mdl').read_bytes().decode('cp1252')
            self.assertEqual(blink.with_lights(blink.without(text), spec), (text, 2 * boxes), name)
        laid = 0
        for path in sorted(REPO.glob('srn_t_*/*.set')):  # the loop is on in every set that lays the tile: the merged one too (review of PR 198)
            tile = path.read_bytes().decode('cp1252')
            for name in ('fcx01_m01_02', 'fcx01_m01_11'):
                for block in re.findall(rf'(?mis)^\[TILE\d+\]\s*\nModel={name}\s*\n.*?(?=^\[)', tile):
                    laid += 1; self.assertRegex(block, r'(?m)^AnimLoop1=1\s*$', f'{path.name}: {name}')
        self.assertGreaterEqual(laid, 4)  # fcx01 and srx01, two tiles each
        # the steady lights: the console's material has its glow map
        self.assertNotEqual(re.search(r'(?m)^texture5[ \t]+(\S+)', (pack / f'{spec["texture"]}.mtr').read_text(encoding='ascii')).group(1), 'null')
        # the lamps draw the picture the material draws, plainly: no material of that name, or its glow map would pale them
        self.assertEqual(re.search(r'(?m)^texture0[ \t]+(\S+)', (pack / f'{spec["texture"]}.mtr').read_text(encoding='ascii')).group(1), spec['lamp'])
        self.assertEqual([path for path in REPO.glob(f'srn_*/{spec["lamp"]}.mtr')], [])
        # and their patch is a pale place of it: a lamp over a dark place would never show
        glow = np.asarray(pictures.read(pack / f'{spec["lamp"]}.dds'))[::-1]; height, width = glow.shape[:2]  # stored bottom row first
        left, top, right, bottom = spec['patch']; patch = glow[int(top * height):max(int(bottom * height), int(top * height) + 1), int(left * width):max(int(right * width), int(left * width) + 1), :3]
        self.assertGreater(float(patch.max(axis=2).min()) * (1 if patch.dtype == np.uint8 else 255), 150)  # every pixel of it bright


if __name__ == '__main__':
    unittest.main()
