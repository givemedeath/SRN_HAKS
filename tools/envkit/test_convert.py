"""A generated model reaches the game upright, to scale, facing front, with unit normals and node-sized meshes."""
import json
import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np

from . import convert, prop_fixture as fixture


def glb(path, vertices, normals, uvs, faces, *, rotation=None):
    """A binary glTF holding one triangle mesh under one node."""
    blobs = [np.asarray(vertices, '<f4').tobytes(), np.asarray(normals, '<f4').tobytes(), np.asarray(uvs, '<f4').tobytes(),
             np.asarray(faces, '<u4').tobytes()]
    views, offset = [], 0
    for blob in blobs:
        views.append({'buffer': 0, 'byteOffset': offset, 'byteLength': len(blob)}); offset += len(blob)
    count = len(vertices)
    document = {'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0, **({'rotation': rotation} if rotation else {})}],
                'meshes': [{'primitives': [{'attributes': {'POSITION': 0, 'NORMAL': 1, 'TEXCOORD_0': 2}, 'indices': 3}]}],
                'buffers': [{'byteLength': offset}], 'bufferViews': views,
                'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': count, 'type': 'VEC3'},
                              {'bufferView': 1, 'componentType': 5126, 'count': count, 'type': 'VEC3'},
                              {'bufferView': 2, 'componentType': 5126, 'count': count, 'type': 'VEC2'},
                              {'bufferView': 3, 'componentType': 5125, 'count': len(faces) * 3, 'type': 'SCALAR'}]}
    text = json.dumps(document).encode(); text += b' ' * (-len(text) % 4); binary = b''.join(blobs)
    Path(path).write_bytes(b'glTF' + struct.pack('<II', 2, 28 + len(text) + len(binary)) + struct.pack('<II', len(text), 0x4E4F534A) + text
                           + struct.pack('<II', len(binary), 0x004E4942) + binary)
    return Path(path)


# A wall in glTF space: 2 wide (X), 4 tall (Y), facing the viewer (+Z).
WALL = dict(vertices=[[-1, 0, 0], [1, 0, 0], [1, 4, 0], [-1, 4, 0]], normals=[[0, 0, 1]] * 4, uvs=[[0, 1], [1, 1], [1, 0], [0, 0]],
            faces=[[0, 1, 2], [0, 2, 3]])


class ConvertTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup); self.root = Path(self.folder.name)

    def test_a_model_stands_up_to_scale_and_faces_front(self):
        vertices, normals, uvs, faces = convert.read_glb(glb(self.root / 'wall.glb', **WALL))
        points, turned, texture, scale, angles = convert.fit(vertices, normals, uvs, 2.0)
        self.assertAlmostEqual(scale, 0.5); self.assertEqual(angles, (0.0, 0.0, 0.0))
        np.testing.assert_allclose(points.min(0), [-0.5, 0, 0], atol=1e-9); np.testing.assert_allclose(points.max(0), [0.5, 0, 2.0], atol=1e-9)
        np.testing.assert_allclose(turned, [[0, 1, 0]] * 4, atol=1e-9)  # glTF's front is the game's +Y
        np.testing.assert_allclose(texture, uvs)  # unchanged: flipping v scrambled every island in the client
        # Still a rotation, not a mirror: the triangles keep facing the way their normals point.
        self.assertGreater(np.cross(points[1] - points[0], points[2] - points[0]) @ turned[0], 0)

    def test_a_node_transform_in_the_file_is_applied(self):
        quarter = [0, 0.7071067811865476, 0, 0.7071067811865476]  # 90 degrees about glTF's up axis
        vertices, normals, _, _ = convert.read_glb(glb(self.root / 'turned.glb', **WALL, rotation=quarter))
        np.testing.assert_allclose(normals, [[1, 0, 0]] * 4, atol=1e-6); self.assertAlmostEqual(float(np.ptp(vertices[:, 0])), 0, places=5)

    def test_a_model_left_at_three_quarters_is_squared_but_a_shapeless_one_is_not(self):
        box = np.array([[x, y, z] for x in (-1, 1) for y in (-0.4, 0.4) for z in (0, 2)], float)
        angle = np.radians(30); turn = np.array([[np.cos(angle), -np.sin(angle), 0], [np.sin(angle), np.cos(angle), 0], [0, 0, 1]])
        self.assertAlmostEqual(convert.square_up(box @ turn.T), -30.0, delta=0.3)
        self.assertEqual(convert.square_up(box), 0.0)
        ring = np.array([[np.cos(a), np.sin(a), 0] for a in np.linspace(0, 2 * np.pi, 90, endpoint=False)])
        self.assertEqual(convert.square_up(ring), 0.0)

    def test_a_leaning_box_is_stood_upright_but_a_ball_is_left_alone(self):
        corners = np.array([[x, y, z] for x in (-1, 1) for y in (-0.4, 0.4) for z in (0, 2)], float)  # 2 wide, 0.8 deep, 2 tall
        faces = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1], [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]])
        leaning = corners @ convert._turn(20.0, 12.0, -7.0).T  # as a model drawn from above and to one side comes back
        angles = convert.upright(leaning, faces)
        self.assertNotEqual(angles, (0.0, 0.0, 0.0))
        stood = leaning @ convert._turn(*angles).T
        np.testing.assert_allclose(np.ptp(stood, axis=0), [2.0, 0.8, 2.0], rtol=0.015)  # the same box, the same way round
        self.assertEqual(convert.upright(corners, faces), (0.0, 0.0, 0.0))  # already square: nothing to do
        ball = np.random.default_rng(3).normal(size=(3000, 3)); ball /= np.linalg.norm(ball, axis=1)[:, None]  # no way up to find
        self.assertEqual(convert.upright(ball, np.arange(3000).reshape(-1, 3)), (0.0, 0.0, 0.0))
        # Through fit, the leaning box ends standing on the ground at its stated height.
        points, _, _, _, used = convert.fit(leaning @ convert.TO_GAME, np.tile([0, 0, 1.0], (8, 1)), np.zeros((8, 2)), 2.0, faces=faces)
        self.assertEqual(used, angles); np.testing.assert_allclose(np.ptp(points, axis=0), [2.0, 0.8, 2.0], rtol=0.015)

    def test_a_two_sided_sign_is_its_front_sheet_and_a_half_turned_copy(self):
        def slab(low, high):  # a box and its outward triangles
            corners = np.array([[x, y, z] for x in (low[0], high[0]) for y in (low[1], high[1]) for z in (low[2], high[2])], float)
            return corners, np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1], [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]])
        front, faces = slab((-0.4, 0.2, 0.0), (0.4, 0.3, 1.0))  # upright, as the generator stood it
        rear = slab((-0.4, 0.1, 0.0), (0.4, 0.2, 1.1))[0]; rear[:, 1] -= 0.45 * (1 - rear[:, 2] / 1.1)  # slanting away behind it
        points = np.concatenate([front, rear]); both = np.concatenate([faces, faces + 8])
        normals = np.tile([0, 1.0, 0], (16, 1)); uvs = np.linspace(0, 1, 32).reshape(16, 2)
        sheet, out, texture, made = convert.two_sided(points, normals, uvs, both, 15.0)
        self.assertEqual((len(sheet), len(made)), (16, 24))  # the front slab twice; nothing of the invented rear
        np.testing.assert_allclose(texture[:8], uvs[:8]); np.testing.assert_allclose(texture[8:], uvs[:8])  # both sides show the front's picture
        np.testing.assert_allclose(out[0], [0, np.cos(np.radians(15)), np.sin(np.radians(15))], atol=1e-9)  # leaning back
        np.testing.assert_allclose(out[8], out[0] * [-1, -1, 1], atol=1e-9)
        # A half turn about an upright line: the same heights, the footprint the same either way round, no mirror.
        np.testing.assert_allclose(sheet[8:, 2], sheet[:8, 2]); middle = (sheet[:, 1].min() + sheet[:, 1].max()) / 2
        np.testing.assert_allclose(sorted(sheet[:8, 1] - middle), sorted(middle - sheet[8:, 1]), atol=1e-9)
        for a, b, c in made:  # every triangle of both slabs still faces out of its own slab
            self.assertGreater(np.cross(sheet[b] - sheet[a], sheet[c] - sheet[a]) @ (sheet[[a, b, c]].mean(0) - sheet[:8 if a < 8 else 16][-8:].mean(0)), 0)
        self.assertAlmostEqual(float(sheet[:8, 1].min()), float(sheet[8:, 1].max()), places=6)  # their backs meet along the top
        with self.assertRaisesRegex(ValueError, 'not a two-sided sign'):
            convert.two_sided(front, normals[:8], uvs[:8], faces, 15.0)

    def test_a_model_whose_front_came_back_facing_a_side_is_turned(self):
        from PIL import Image
        model = glb(self.root / 'wall.glb', **WALL); Image.new('RGB', (8, 8), (200, 100, 50)).save(self.root / 'colour.png')
        made = convert.shape(model, {'base_color': self.root / 'colour.png'}, height=2.0, turn=90)
        np.testing.assert_allclose(made['normals'], [[-1, 0, 0]] * 4, atol=1e-9)  # counter-clockwise seen from above: the front now faces -X
        np.testing.assert_allclose(made['vertices'].max(0) - made['vertices'].min(0), [0, 1.0, 2.0], atol=1e-9)
        np.testing.assert_allclose(made['vertices'].mean(0)[:2], [0, 0], atol=1e-9)  # still centred on its spot
        self.assertIsNone(made['colour']); self.assertIsNone(made['flat'])  # nothing retouched: the picture ships as generated

    def test_a_colour_picture_is_toned_painted_and_given_a_wire_mesh_by_place_on_the_model(self):
        from PIL import Image
        vertices, normals, uvs, faces = convert.read_glb(glb(self.root / 'wall.glb', **WALL))
        points, _, texture, _, _ = convert.fit(vertices, normals, uvs, 2.0)  # 1 wide (x -0.5 to 0.5), 2 tall, the picture across the whole of it
        picture = Image.new('RGB', (64, 64), (200, 100, 50))
        toned, flat, _ = convert.retouch(picture, points, texture, faces, tone=0.5)
        self.assertEqual(toned.mode, 'RGB'); self.assertIsNone(flat); self.assertEqual(toned.getpixel((5, 5)), (100, 50, 25))
        painted, flat, _ = convert.retouch(picture, points, texture, faces, paint=[{'box': [[-0.6, -0.1, 1.0], [0.6, 0.1, 2.1]], 'colour': [1, 2, 3]}])
        self.assertIsNone(flat); self.assertEqual(painted.getpixel((32, 8)), (1, 2, 3)); self.assertEqual(painted.getpixel((32, 56)), (200, 100, 50))  # the top half only
        meshed, flat, plain = convert.retouch(picture, points, texture, faces, mesh=[{'box': [[-0.6, -0.1, -0.1], [0.6, 0.1, 1.0]], 'pitch': 0.25, 'wire': 0.05}])
        self.assertEqual(meshed.mode, 'RGBA'); pixels = np.asarray(meshed); lower, upper = pixels[36:], pixels[:28]
        self.assertTrue((upper[..., 3] == 255).all()); np.testing.assert_array_equal(upper[0, 0, :3], [200, 100, 50])  # outside the panel nothing changes
        gaps = float((lower[..., 3] == 0).mean()); self.assertGreater(gaps, 0.4); self.assertLess(gaps, 0.8)  # wires a fifth of the pitch, crossing
        self.assertTrue((lower[..., :3] == convert.WIRE).all())  # the wire's colour under the gaps too, so a filtered edge has no fringe
        self.assertTrue(np.asarray(flat)[40:].all()); self.assertFalse(np.asarray(flat)[:28].any())  # the panel's relief is levelled
        self.assertIsNone(plain)  # a wire mesh smooths nothing: the other maps of its panel stay as they are
        row = np.asarray(meshed)[60, :, 3]; self.assertGreaterEqual(int((np.diff(row.astype(int)) != 0).sum()), 6)  # wires and gaps alternate along it
        with self.assertRaisesRegex(ValueError, 'thinner'):
            convert.retouch(picture, points, texture, faces, mesh=[{'box': [[-1, -1, 0], [1, 1, 1]], 'pitch': 0.1, 'wire': 0.2}])
        # The pattern is laid along the way the panel runs. Laid by x + y it was out of step on the two faces of a panel
        # by the panel's thickness, and a panel across the corner of a yard would have had level stripes for diamonds.
        from . import glow
        along = np.linspace(0, 2, 400); faces_apart = np.array([[x, y, 1.0] for x in along for y in (-0.02, 0.02)])
        np.testing.assert_array_equal(convert._run(faces_apart), [1.0, 0.0])  # along the axis exactly, whichever face a texel is on
        slant = np.array([[x, -x, 1.0] for x in along / np.sqrt(2)]); ahead = convert._run(slant)
        np.testing.assert_allclose(ahead, [np.sqrt(0.5), -np.sqrt(0.5)], atol=1e-9); up = np.linspace(0, 1, 400)
        diamonds = glow.wires((slant[:, :2] @ ahead)[:, None], up[None, :], 0.25, 0.05); straight = glow.wires(along[:, None], up[None, :], 0.25, 0.05)
        self.assertGreater(float((diamonds == straight).mean()), 0.99)  # the diagonal panel shows what a panel along X shows
        self.assertTrue(diamonds.any(1).all() and (~diamonds).any(1).all())  # wires and gaps along every line of it: no stripes
        corner = np.array([[x, 0.0, 1.0] for x in along] + [[0.0, y, 1.0] for y in along])
        with self.assertRaisesRegex(ValueError, 'one flat panel'):  # two panels round a corner are two parts
            convert._run(corner)

    def test_a_pattern_is_smoothed_off_a_surface_and_its_tones_are_left(self):
        """The Ares Depot's wall came back with its fence's chain-link painted on it (seen in the client, 2026-11-11)."""
        from PIL import Image
        vertices, normals, uvs, faces = convert.read_glb(glb(self.root / 'wall.glb', **WALL))
        points, _, texture, _, _ = convert.fit(vertices, normals, uvs, 2.0)  # 1 wide, 2 tall: 64 texels to the metre across, 32 up
        stripes = np.zeros((64, 64, 3), np.uint8); stripes[:] = (200, 200, 200); stripes[:, ::4] = (40, 40, 40)  # a dark line every sixteenth of a metre
        smoothed, flat, plain = convert.retouch(Image.fromarray(stripes), points, texture, faces, smooth=[{'box': [[-0.6, -0.1, -0.1], [0.6, 0.1, 1.0]], 'radius': 0.1}])
        self.assertEqual(smoothed.mode, 'RGB'); pixels = np.asarray(smoothed).astype(int); lower, upper = pixels[40:, 8:56, 0], pixels[:28]
        np.testing.assert_array_equal(upper, stripes[:28])  # outside the box nothing changes
        self.assertLess(int(lower.max() - lower.min()), 12); self.assertLess(abs(float(lower.mean()) - 160), 8)  # the lines are gone, the tone is theirs and the wall's
        self.assertTrue(np.asarray(flat)[40:].all()); self.assertFalse(np.asarray(flat)[:28].any())  # and the relief that drew them is levelled
        # The generator drew the same lines into the roughness and the metal: they go from those maps over the same reach.
        (chosen, reach), = plain; self.assertTrue(chosen[40:].all()); self.assertFalse(chosen[:28].any()); self.assertGreaterEqual(reach, 1)
        lined = stripes[..., 0] / 255; level = convert._levelled(lined, plain)
        np.testing.assert_array_equal(level[:28], lined[:28]); self.assertLess(float(np.ptp(level[40:, 8:56])), 12 / 255); self.assertGreater(float(np.ptp(lined[40:, 8:56])), 0.5)
        toward, _, _ = convert.retouch(Image.fromarray(stripes), points, texture, faces, smooth=[{'box': [[-0.6, -0.1, -0.1], [0.6, 0.1, 1.0]], 'radius': 0.1, 'colour': [100, 110, 120]}])
        np.testing.assert_allclose(np.asarray(toward)[40:, 8:56].reshape(-1, 3).mean(0), [100, 110, 120], atol=3)
        # A roller door's slats, which a generator draws as a moiré, are drawn again: a darker joint every quarter metre up.
        slatted, _, _ = convert.retouch(Image.fromarray(stripes), points, texture, faces, smooth=[{'box': [[-0.6, -0.1, -0.1], [0.6, 0.1, 1.0]], 'radius': 0.1, 'slats': 0.25}])
        column = np.asarray(slatted)[33:, 32, 0].astype(int)  # rows from z 0.97 down to the foot, 32 texels a metre
        self.assertGreater(int(column.max() - column.min()), column.max() * convert.SLAT_SHADE / 2)  # a joint between texel centres shows part of its shade
        self.assertEqual(int(np.argmin(column[:16])) % 8, int(np.argmin(column[16:])) % 8)  # the same joint every eight texels
        np.testing.assert_array_equal(np.asarray(slatted)[:28], stripes[:28])
        # A door in two boxes that meet: a joint where they overlap is darkened once, as deep as the others.
        halves = [{'box': [[-0.6, -0.1, -0.1], [0.6, 0.1, 0.55]], 'radius': 0.1, 'slats': 0.25}, {'box': [[-0.6, -0.1, 0.45], [0.6, 0.1, 1.0]], 'radius': 0.1, 'slats': 0.25}]
        split, _, _ = convert.retouch(Image.fromarray(stripes), points, texture, faces, smooth=halves)
        deepest = [int(np.asarray(split)[row:row + 8, 32, 0].min()) for row in range(33, 57, 8)]
        self.assertLess(max(deepest) - min(deepest), max(deepest) * convert.SLAT_SHADE / 3)
        with self.assertRaisesRegex(ValueError, 'under four texels'):  # a joint every texel and a half would alias again
            convert.retouch(Image.fromarray(stripes), points, texture, faces, smooth=[{'box': [[-0.6, -0.1, -0.1], [0.6, 0.1, 1.0]], 'radius': 0.1, 'slats': 0.05}])
        # A box that holds none of the model is a mistake in the set, not a part to pass over.
        off = [[-0.6, -0.1, 5.0], [0.6, 0.1, 6.0]]
        for retouching in ({'paint': [{'box': off, 'colour': [1, 2, 3]}]}, {'smooth': [{'box': off, 'radius': 0.1}]}, {'mesh': [{'box': off, 'pitch': 0.09, 'wire': 0.016}]}):
            with self.assertRaisesRegex(ValueError, 'holds none of the model'):
                convert.retouch(Image.fromarray(stripes), points, texture, faces, **retouching)
        # One column of texels has no neighbour to measure a step by: the blur's reach stays within the picture.
        from unittest import mock
        with mock.patch.object(convert, '_blur', wraps=convert._blur) as blur:
            convert.retouch(Image.fromarray(stripes), points, texture, faces, smooth=[{'box': [[0.001, -0.1, -0.1], [0.0155, 0.1, 1.0]], 'radius': 0.1}])
        self.assertTrue(blur.call_args_list); self.assertTrue(all(call.args[1] <= 64 / 8 for call in blur.call_args_list))
        # Each part is smoothed among its own texels, in the colour and in the other maps alike: two parts side by side
        # with the same reach do not run into each other.
        halves = np.zeros((64, 64, 3), np.uint8); halves[:, :32] = (40, 40, 40); halves[:, 32:] = (200, 200, 200)
        sides = [{'box': [[-0.6, -0.1, -0.1], [0.0, 0.1, 2.1]], 'radius': 0.2}, {'box': [[0.0, -0.1, -0.1], [0.6, 0.1, 2.1]], 'radius': 0.2}]
        apart, _, parts = convert.retouch(Image.fromarray(halves), points, texture, faces, smooth=sides)
        self.assertEqual((len(parts), parts[0][1]), (2, parts[1][1])); np.testing.assert_array_equal(np.asarray(apart), halves)
        np.testing.assert_allclose(convert._levelled(halves[..., 0] / 255, parts), halves[..., 0] / 255, atol=1 / 255)
        # Only the texels the blur can reach are worked on, and the answer is the whole picture's.
        field = np.random.default_rng(0).random((96, 96)).astype(np.float32); patch = np.zeros((96, 96), bool); patch[40:50, 60:70] = True
        whole = convert._blur(field * patch, 2) / np.maximum(convert._blur(patch.astype(np.float32), 2), 1e-6)
        with mock.patch.object(convert, '_blur', wraps=convert._blur) as blur:
            box, soft, near = convert._soften(field, patch, 2)
        self.assertTrue(near[patch[box]].all()); np.testing.assert_allclose(soft[near], whole[box][near], atol=1e-5)
        self.assertTrue(all(max(call.args[0].shape[:2]) <= 10 + 2 * 7 for call in blur.call_args_list))  # ten texels and three reaches and one round them
        # A part's tones are carried past its own texels, so the picture enlarged has them at the part's edge: a dark
        # neighbour on the texture does not show through as a fringe.
        island = np.zeros((64, 64, 3), np.uint8); island[:, 32:] = (200, 200, 200)  # black to the left of the wall's right half
        edge, _, _ = convert.retouch(Image.fromarray(island).resize((128, 128), Image.NEAREST), points, texture, faces, size=64, smooth=[sides[1]])
        self.assertEqual(int(np.asarray(edge)[:, 64:].min()), 200); self.assertEqual(int(np.asarray(edge)[:, :64].max()), 0)

    def test_a_tinted_marking_is_taken_off_a_surface_and_its_grain_is_left(self):
        """The Ares fence section's concrete base came back with a smeared red marking on it; smoothing the whole face
        took the concrete's weathering off with it and left a plain panel beside weathered ones (seen in the client,
        2026-11-12)."""
        from PIL import Image
        vertices, normals, uvs, faces = convert.read_glb(glb(self.root / 'wall.glb', **WALL))
        points, _, texture, _, _ = convert.fit(vertices, normals, uvs, 2.0)  # 1 wide, 2 tall: 64 texels to the metre across, 32 up
        grain = np.random.default_rng(1).integers(150, 200, (64, 64), dtype=np.uint8); concrete = np.repeat(grain[..., None], 3, 2)
        smeared = concrete.copy(); smeared[44:54, 20:44] = (200, 40, 40); lower = [[-0.6, -0.1, -0.1], [0.6, 0.1, 1.0]]
        cleaned, flat, plain = convert.retouch(Image.fromarray(smeared), points, texture, faces, smooth=[{'box': lower, 'radius': 0.2, 'tint': 30}])
        pixels = np.asarray(cleaned).astype(int); about = np.ones((64, 64), bool); about[41:57, 17:47] = False  # the marking and the three texels round it
        np.testing.assert_array_equal(pixels[about], concrete[about])  # the surface keeps every texel of its grain, in the box and out of it
        patch = pixels[44:54, 20:44]; self.assertLess(int(np.abs(patch - patch.mean(-1, keepdims=True)).max()), 2)  # no tint is left where it was
        self.assertLess(abs(float(patch.mean()) - 175), 12)  # and what is there is the concrete about it
        self.assertTrue(np.asarray(flat)[44:54, 20:44].all()); self.assertFalse(np.asarray(flat)[about].any())
        (surface, reach, marked), = plain; self.assertTrue(marked[44:54, 20:44].all()); self.assertFalse(marked[about].any()); self.assertFalse((surface & marked).any())
        lined = grain / 255; lined[48] = 0.0; level = convert._levelled(lined, plain)  # the marking's line in the roughness goes with it, and no other
        self.assertGreater(float(level[48, 20:44].min()), 0.5); np.testing.assert_array_equal(level[about], lined[about])
        with self.assertRaisesRegex(ValueError, 'no tint'):  # a box with no marking in it is a mistake in the set
            convert.retouch(Image.fromarray(concrete), points, texture, faces, smooth=[{'box': lower, 'radius': 0.2, 'tint': 30}])
        with self.assertRaisesRegex(ValueError, 'further from any'):  # and a marking is filled from within its radius, or not at all
            convert.retouch(Image.fromarray(smeared), points, texture, faces, smooth=[{'box': lower, 'radius': 0.02, 'tint': 30}])
        # A box that is mostly marking has the marking's tint for its usual one: the concrete would be taken off and the
        # red spread over it.
        flooded = concrete.copy(); flooded[36:60, 8:56] = (200, 40, 40)
        with self.assertRaisesRegex(ValueError, 'most of the box is the marking'):
            convert.retouch(Image.fromarray(flooded), points, texture, faces, smooth=[{'box': lower, 'radius': 0.2, 'tint': 30}])
        # A marking on an island of its own, further from the surface than the blur works over, was cut out of the
        # check with the rest of the picture and passed for done with nothing changed (review of PR #124).
        picture = np.full((64, 64), 0.5, np.float32); surface = np.zeros((64, 64), bool); surface[2:10, 2:10] = True
        island = np.zeros((64, 64), bool); island[50:54, 50:54] = True; picture[island] = 1.0
        with self.assertRaisesRegex(ValueError, 'further from any'):
            convert._spread(picture, [(surface, 2.0, None, island)])
        beside = np.zeros((64, 64), bool); beside[10:12, 4:8] = True; picture[beside] = 1.0
        spread, done = convert._spread(picture, [(surface, 2.0, None, beside)])
        self.assertLess(float(np.abs(spread[beside] - 0.5).max()), 1e-5); np.testing.assert_array_equal(done, beside); self.assertEqual(float(spread[island].min()), 1.0)

    def test_a_hole_is_closed_between_the_models_own_vertices(self):
        """The Ares fence section came back with a wedge of its concrete base open to the ground behind it (seen in
        the client, 2026-11-12)."""
        from unittest import mock
        from PIL import Image
        vertices = np.array([[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1], [0, 0, 1]], float)  # a square wall with half of it missing
        normals = np.array([[0, -1, 0]] * 5, float); faces = np.array([[0, 1, 2]])
        uvs = np.array([[0, 0], [1, 0], [1, 1], [0, 1], [5, 5]], float)  # the last stands where the fourth does, on another island of the picture
        stated = [{'part': 'upper half', 'corners': [[0.0, 0.0, 0.005], [0.0, 0.0, 1.0], [1.0, 0.004, 1.0]]}]
        whole = convert.closed(vertices, normals, uvs, faces, stated)
        np.testing.assert_array_equal(whole, [[0, 1, 2], [0, 2, 3]])  # the model's own vertices, the picture round the hole, and the wall's facing
        np.testing.assert_array_equal(np.cross(vertices[2] - vertices[0], vertices[3] - vertices[0]) > 0, [False, False, False])
        with self.assertRaisesRegex(ValueError, 'none lies within'):  # a corner in the air is a mistake in the set
            convert.closed(vertices, normals, uvs, faces, [{'corners': [[0, 0, 0], [0, 0, 1], [1, 0.5, 1]]}])
        with self.assertRaisesRegex(ValueError, 'already has a face'):
            convert.closed(vertices, normals, uvs, faces, [{'corners': [[0, 0, 0], [1, 0, 0], [1, 0, 1]]}])
        with self.assertRaisesRegex(ValueError, 'apart from one another'):
            convert.closed(vertices, normals, uvs, faces, [{'corners': [[0, 0, 0], [0, 0, 1], [0, 0, 1]]}])
        with self.assertRaisesRegex(ValueError, 'already has a face'):  # stated twice, the second would lie over the first
            convert.closed(vertices, normals, uvs, faces, stated * 2)
        # At a seam of the picture each place has two vertices, and the face the model has there may use the others: a
        # second face over it would flicker against it.
        seam = np.vstack([vertices, vertices[:3]]); island = np.vstack([uvs, [[9.0, 9.0], [9.1, 9.0], [9.1, 9.1]]])
        with self.assertRaisesRegex(ValueError, 'already has a face'):
            convert.closed(seam, np.vstack([normals, normals[:3]]), island, faces, [{'corners': [[0, 0, 0], [1, 0, 0], [1, 0, 1]]}])
        # A model is closed as it is shaped, on the finished model: a face it has already is refused there too.
        model = glb(self.root / 'wall.glb', **WALL); Image.new('RGB', (64, 64), (128, 128, 128)).save(self.root / 'grey.png')
        shaped = convert.shape(model, {'base_color': self.root / 'grey.png'}, height=2.0)
        with mock.patch.object(convert, 'closed', wraps=convert.closed) as closing, self.assertRaisesRegex(ValueError, 'already has a face'):
            convert.shape(model, {'base_color': self.root / 'grey.png'}, height=2.0, close=[{'corners': shaped['vertices'][shaped['faces'][0]].tolist()}])
        closing.assert_called_once()

    def test_what_stands_in_a_cleared_box_is_taken_away_and_the_floor_stays(self):
        """The Saeder-Krupp yard's bay had a railed-off square under a metre from the vehicle beside it, too narrow a
        way into the back of the bay (user, 2026-11-12)."""
        from PIL import Image
        floor = [[0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0]]; post = [[1, 1, 0], [1.1, 1, 0], [1.1, 1, 1], [1, 1, 1]]
        vertices = np.array(floor + post, float); normals = np.array([[0, 0, 1]] * 4 + [[0, -1, 0]] * 4, float)
        uvs = np.array([[0, 0], [1, 0], [1, 1], [0, 1]] * 2, float) / [1, 2]; faces = np.array([[0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7]])
        stated = [{'part': 'post', 'box': [[0.5, 0.5, 0.05], [1.5, 1.5, 2.0]]}]
        kept_vertices, kept_normals, kept_uvs, kept_faces = convert.cleared(vertices, normals, uvs, faces, stated)
        np.testing.assert_array_equal(kept_faces, [[0, 1, 2], [0, 2, 3]])  # the floor, under the box, stays; the post, with its foot on it, goes
        np.testing.assert_array_equal(kept_vertices, floor); np.testing.assert_array_equal(kept_normals, normals[:4]); np.testing.assert_array_equal(kept_uvs, uvs[:4])
        with self.assertRaisesRegex(ValueError, 'takes no face'):  # a box in the air, or one stated twice, is a mistake in the set
            convert.cleared(vertices, normals, uvs, faces, [{'box': [[5, 5, 0], [6, 6, 1]]}])
        with self.assertRaisesRegex(ValueError, 'takes no face'):
            convert.cleared(vertices, normals, uvs, faces, stated * 2)
        # A model is cleared as it is shaped, on the finished model.
        model = glb(self.root / 'wall.glb', **WALL); Image.new('RGB', (64, 64), (128, 128, 128)).save(self.root / 'grey.png')
        whole = convert.shape(model, {'base_color': self.root / 'grey.png'}, height=2.0)
        middle = whole['vertices'][whole['faces'][0]].mean(0)
        less = convert.shape(model, {'base_color': self.root / 'grey.png'}, height=2.0, clear=[{'box': [(middle - 1e-4).tolist(), (middle + 1e-4).tolist()]}])
        self.assertEqual(len(less['faces']), len(whole['faces']) - 1)

    def test_the_glow_is_of_the_picture_as_it_ships_and_a_fence_ends_at_the_model(self):
        """Found in review, 2026-11-12: the glow map was made from the picture as generated, so what `paint` covered by
        day still shone by night; and a fence was checked for its heights only."""
        from PIL import Image
        from unittest import mock
        from . import glow
        model = glb(self.root / 'wall.glb', **WALL); Image.new('RGB', (512, 512), (250, 240, 230)).save(self.root / 'colour.png')
        maps = {'base_color': self.root / 'colour.png'}; whole = [{'box': [[-0.6, -0.1, -0.1], [0.6, 0.1, 2.1]]}]
        cover = [{'box': [[-0.6, -0.1, -0.1], [0.6, 0.1, 1.0]], 'colour': [0, 0, 0]}]  # an invented logo on the lower half, painted out
        with mock.patch.object(glow, 'position_map', wraps=glow.position_map) as placed:
            made = convert.shape(model, maps, height=2.0, lit=whole, paint=cover)
        shine = np.asarray(made['illumination']); self.assertEqual(shine.shape[:2], (512, 512))
        self.assertGreater(int(shine[:200].min()), 200); self.assertEqual(int(shine[300:].max()), 0)  # dark by night too
        self.assertEqual(placed.call_count, 1)  # the glow's map of places serves the retouching: both are 512 texels across
        sheet = {'from': [-0.5, 0.0], 'to': [0.5, 0.0], 'z': [0.5, 1.5], 'pitch': 0.09, 'wire': 0.016}
        self.assertGreater(len(convert.shape(model, maps, height=2.0, fence=[sheet])['wire']['faces']), 0)
        with self.assertRaisesRegex(ValueError, 'hangs between posts.*east side'):  # measured before a turn: it would hang beside the wall
            convert.shape(model, maps, height=2.0, fence=[{**sheet, 'part': 'east side', 'from': [1.5, -0.5], 'to': [1.5, 0.5]}])
        with mock.patch.object(glow, 'position_map', wraps=glow.position_map) as placed:  # and it is said before the long work on the pictures
            with self.assertRaisesRegex(ValueError, 'hangs between posts'):
                convert.shape(model, maps, height=2.0, lit=whole, paint=cover, fence=[{**sheet, 'from': [1.5, -0.5], 'to': [1.5, 0.5]}])
        self.assertEqual(placed.call_count, 0)

    def test_a_fence_is_hung_as_sheets_that_show_a_wire_picture_of_their_own(self):
        """The same fence's frames came back empty. A sheet is real faces, seen through between its wires. The wires are
        not drawn on the model's own colour picture: an alpha channel there doubled the depot's, to 22 MB (2026-11-12)."""
        fences = [{'from': [0.0, 0.0], 'to': [2.0, 0.0], 'z': [1.0, 2.0], 'pitch': 0.09, 'wire': 0.016}]
        wire = convert.sheets(fences); vertices, normals, uvs, faces, image = (wire[key] for key in ('vertices', 'normals', 'uvs', 'faces', 'image'))
        links = round(wire['period'] / (0.09 * np.sqrt(2))); self.assertGreaterEqual(links, 1); self.assertAlmostEqual(wire['period'], links * 0.09 * np.sqrt(2))
        self.assertGreaterEqual(0.016 / wire['period'] * image.width, convert.WIRE_TEXELS)  # a wire keeps its pixels
        across, up = int(np.ceil(2.0 / wire['period'])), int(np.ceil(1.0 / wire['period']))
        self.assertEqual((len(faces), len(vertices)), (across * up * 4, across * up * 8))  # two faces a square, each way
        np.testing.assert_allclose(vertices.min(0), [0.0, 0.0, 1.0]); np.testing.assert_allclose(vertices.max(0), [2.0, 0.0, 2.0])
        self.assertTrue(((uvs >= 0) & (uvs <= 1 + 1e-9)).all()); np.testing.assert_allclose(uvs[:4], [[0, 0], [1, 0], [1, 1], [0, 1]])  # a whole square shows the whole picture
        out = np.cross(vertices[faces[:, 1]] - vertices[faces[:, 0]], vertices[faces[:, 2]] - vertices[faces[:, 0]])[:, 1]
        self.assertEqual((int((out > 0).sum()), int((out < 0).sum())), (len(faces) // 2, len(faces) // 2))  # seen from both sides
        np.testing.assert_allclose(np.abs(normals[:, 1]), 1.0)
        pixels = np.asarray(image); self.assertEqual((image.mode, image.size), ('RGBA', (convert.WIRE_PICTURE, convert.WIRE_PICTURE)))
        self.assertTrue((pixels[..., :3] == convert.WIRE).all()); gaps = float((pixels[..., 3] == 0).mean()); self.assertGreater(gaps, 0.4); self.assertLess(gaps, 0.8)
        text = convert.model_text('ek_test', np.zeros((3, 3)), np.tile([0, 0, 1.0], (3, 1)), np.zeros((3, 2)), np.array([[0, 1, 2]]), wire=wire)
        self.assertIn('node trimesh ek_test_w0', text); self.assertIn('  bitmap ek_test_w\n', text); self.assertEqual(text.count('  bitmap ek_test\n'), 1)
        with self.assertRaisesRegex(ValueError, 'share one wire mesh'):
            convert.sheets(fences + [{**fences[0], 'wire': 0.02}])
        with self.assertRaisesRegex(ValueError, 'cannot be drawn'):
            convert.sheets([{**fences[0], 'wire': 0.001}])

    def test_zero_normals_are_rebuilt_from_the_faces(self):
        vertices = np.array(WALL['vertices'], float) @ convert.TO_GAME.T; normals = np.array([[0, 1, 0], [0, 0, 0], [0, 1, 0], [0, 0, 0]], float)
        fixed, count = convert.repair_normals(vertices, normals, np.array(WALL['faces']))
        self.assertEqual(count, 2); np.testing.assert_allclose(np.linalg.norm(fixed, axis=1), 1.0)
        np.testing.assert_allclose(fixed[1], [0, 1, 0], atol=1e-9)

    def test_a_normal_that_points_against_its_faces_is_turned_round(self):
        """The rail yard's boxcar (2026-11-13): a sixth of it carried normals against its winding and shaded dark."""
        vertices = np.array(WALL['vertices'], float) @ convert.TO_GAME.T; faces = np.array(WALL['faces'])
        right = convert.repair_normals(vertices, np.zeros((len(vertices), 3)), faces)[0]
        wrong = right.copy(); wrong[[0, 2]] *= -1
        fixed, turned = convert.turn_normals(vertices, wrong, faces)
        self.assertEqual(turned, 2); np.testing.assert_allclose(fixed, right, atol=1e-9)
        self.assertEqual(convert.turn_normals(vertices, right, faces)[1], 0)  # a model drawn right is left alone

    def test_a_model_named_like_a_file_of_another_is_refused(self):
        """The rail yard (2026-11-13): a copy of the office named ek_rf_admin_s would have written over its shine map."""
        group = {'ground': 'pavement', 'group': 'G', 'label': 'G', 'sets': {'dgt04': 'Concrete'}}
        for clash in ('ek_x_s', 'ek_x_n', 'ek_x_h', 'ek_x_t00', 'ek_xp1'):
            models = {'ek_x': {'source': 'meshy/x', 'height': 3.0, 'measuredAt': 3.0, 'tiles': {**group, 'parts': [{'model': 'ek_y', 'at': [5, 0, 0]}]}},
                      'ek_y': {'source': 'meshy/y', 'height': 1.0}, clash: {'source': 'meshy/x', 'height': 3.0}}
            path = self.root / 'set.json'; path.write_text(json.dumps({'models': models}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'named like a file of ek_x'):
                convert.load_models(path)
        models['ek_xs'] = models.pop(clash); path.write_text(json.dumps({'models': models}), encoding='utf-8')
        self.assertIn('ek_xs', convert.load_models(path))
        models['ek_x_tower'] = models.pop('ek_xs'); path.write_text(json.dumps({'models': models}), encoding='utf-8')
        self.assertIn('ek_x_tower', convert.load_models(path))  # only ek_x_t<row><column> is a tile's name (review, 2026-11-14)

    def test_a_model_laid_underfoot_is_a_part_and_never_a_group(self):
        """The rail freight depot (2026-11-13): its tracks are parts laid underfoot, walked across and run off its edges."""
        group = {'ground': 'pavement', 'group': 'G', 'label': 'G', 'sets': {'dgt04': 'Concrete'}}
        models = {'ek_x': {'source': 'meshy/x', 'height': 3.0, 'measuredAt': 3.0, 'tiles': {**group, 'parts': [{'model': 'ek_y', 'at': [5, 0, 0]}]}},
                  'ek_y': {'source': 'track/y', 'height': 0.3, 'underfoot': True}}
        path = self.root / 'set.json'; path.write_text(json.dumps({'models': models}), encoding='utf-8')
        self.assertIs(convert.load_models(path)['ek_y']['underfoot'], True)
        for change in ({'ek_y': {**models['ek_y'], 'underfoot': False}}, {'ek_y': {**models['ek_y'], 'underfoot': 'yes'}}, {'ek_x': {**models['ek_x'], 'underfoot': True}}):
            path.write_text(json.dumps({'models': {**models, **change}}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'underfoot is true'):
                convert.load_models(path)

    def test_a_face_seen_from_behind_is_turned_round(self):
        """The rail yard (2026-11-13): faces wound inward were holes onto whatever stood behind them."""
        corners = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], float)
        cube = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1], [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]])
        quick = {'cells': 32, 'views': 24}; front, back, whole = convert.seen(corners, cube, **quick)
        # drawn right all round: seen from the front, but for the few pixels where a near face's spots miss and the far side shows
        self.assertTrue((front > 0).all()); self.assertLess(back.sum(), 0.05 * front.sum()); self.assertEqual(convert.turn_faces(corners, cube, **quick)[1], 0)
        self.assertLess(abs(front.sum() / whole.sum() - 0.5), 0.1)  # of all it would show, half is in front of the rest
        inside_out = cube.copy(); inside_out[[2, 3, 10, 11]] = inside_out[[2, 3, 10, 11]][:, [0, 2, 1]]
        fixed, turned = convert.turn_faces(corners, inside_out, **quick)
        self.assertEqual(turned, 4); np.testing.assert_array_equal(fixed, cube)
        # A liner wound inward, a few centimetres inside the skin, is never seen and stays as it is: judged by the open
        # air on either side, the first attempt turned such liners outward.
        liner = np.vstack([corners, (corners - 0.5) * 0.97 + 0.5]); walls = np.vstack([cube, (cube + 8)[:, [0, 2, 1]]])
        self.assertEqual(convert.turn_faces(liner, walls, **quick)[1], 0)
        # A sheet seen from both sides is a sign or a fence: it is not the eye's to say which way it faces.
        sheet = np.array([[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]], float)
        for faces in ([[0, 1, 2], [0, 2, 3]], [[0, 2, 1], [0, 3, 2]]):
            self.assertEqual(convert.turn_faces(sheet, np.array(faces), **quick)[1], 0)
        # A side made of two faces back to back, one drawn outward and one inward on the same plane, stays so: the
        # inward one ties with the outward one from outside and was turned onto it (the rail yard's models, 2026-11-13).
        backed = np.vstack([cube, cube[:2][:, [0, 2, 1]]])
        self.assertEqual(convert.turn_faces(corners, backed, **quick)[1], 0)
        np.testing.assert_array_equal(convert.back_to_back(corners, backed, np.ones(len(backed), bool)), [True, True] + [False] * 10 + [True, True])
        # ... but not one a few centimetres inside, nor one wound inward with no face over it.
        inner = np.vstack([corners, corners + [0.03, 0.0, 0.0]])
        self.assertFalse(convert.back_to_back(inner, np.vstack([cube, (cube[:2] + 8)[:, [0, 2, 1]]]), np.ones(14, bool))[12:].any())
        self.assertFalse(convert.back_to_back(corners, inside_out, np.ones(12, bool)).any())

    def test_a_box_drawn_from_outside_only_is_given_backs(self):
        """The rail yard's dumpster (2026-11-13): through the gaps of its slatted lid the client showed what stood
        behind it, its far walls not drawn from inside."""
        corners = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], float)
        cube = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1], [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]])
        normals = corners - 0.5; uvs = corners[:, :2]
        points, turned, places, faces = convert.backed(corners, normals, uvs, cube)
        self.assertEqual((len(points), len(faces)), (16, 24))
        np.testing.assert_array_equal(points[8:], corners); np.testing.assert_array_equal(turned[8:], -normals); np.testing.assert_array_equal(places[8:], uvs)
        # each back faces the other way from its face, on the same corners
        of = lambda f: np.cross(points[f[:, 1]] - points[f[:, 0]], points[f[:, 2]] - points[f[:, 0]])
        np.testing.assert_allclose(of(faces[12:]), -of(faces[:12]))
        self.assertTrue((np.einsum('ij,ij->i', of(faces[12:]), turned[faces[12:, 0]]) > 0).all())  # normals agree with the backs' winding
        # the game set says so with `inside: true`, and nothing else
        path = Path(tempfile.mkdtemp()) / 'set.json'
        for value, ok in ((True, True), (False, False), ('yes', False)):
            path.write_text(json.dumps({'models': {'ek_x': {'source': 'a', 'height': 1.0, 'inside': value}}}), encoding='utf-8')
            if ok:
                self.assertIs(convert.load_models(path)['ek_x']['inside'], True)
            else:
                with self.assertRaisesRegex(ValueError, 'inside is true'):
                    convert.load_models(path)

    def test_a_cars_trucks_are_drawn_in_to_the_track_and_the_body_is_left_as_it_was(self):
        """The rail yard's cars (2026-11-13): their wheels stood 0.15 to 0.2 m outside the rails."""
        points = np.array([[0.0, 0.85, 0.5], [0.0, -0.85, 0.5], [0.0, 1.5, 2.0], [0.0, 0.85, 1.075], [9.0, 0.85, 0.5], [3.075, 0.85, 0.5]])
        normals = np.tile([0.0, 0.6, 0.8], (len(points), 1))
        moved, turned = convert.gauged(points, normals, {'spans': [[-3.0, 3.0]], 'top': 1.0, 'back': 0.85})
        np.testing.assert_allclose(moved[:2, 1], [convert.WHEEL_BACK, -convert.WHEEL_BACK])  # the wheels' backs at gauge, either side
        np.testing.assert_allclose(moved[[2, 4], 1], [1.5, 0.85])  # the body above and what is beyond the trucks stay
        self.assertTrue(convert.WHEEL_BACK < moved[3, 1] < 0.85 and convert.WHEEL_BACK < moved[5, 1] < 0.85)  # eased back over the blend
        np.testing.assert_allclose(moved[:, [0, 2]], points[:, [0, 2]])
        np.testing.assert_allclose(np.linalg.norm(turned, axis=1), 1.0)
        self.assertGreater(turned[0, 1], 0.6)  # a surface drawn in across leans its normal further across
        path = Path(tempfile.mkdtemp()) / 'set.json'
        for wheels, ok in (({'spans': [[-3, 3]], 'top': 1.3, 'back': 0.85}, True), ({'spans': [[3, -3]], 'top': 1.3, 'back': 0.85}, False),
                           ({'spans': [[-3, 3]], 'top': 1.3, 'back': 2.0}, False), ({'spans': [[-3, 3]], 'top': 1.3}, False)):
            path.write_text(json.dumps({'models': {'ek_x': {'source': 'a', 'height': 4.0, 'wheels': wheels, 'measuredAt': 4.0}}}), encoding='utf-8')
            if ok:
                self.assertEqual(convert.load_models(path)['ek_x']['wheels'], wheels)
            else:
                with self.assertRaisesRegex(ValueError, 'wheels are'):
                    convert.load_models(path)
        path.write_text(json.dumps({'models': {'ek_x': {'source': 'a', 'height': 4.0, 'wheels': {'spans': [[-3, 3]], 'top': 1.3, 'back': 0.85}}}}), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'measuredAt'):
            convert.load_models(path)  # spans and top are measured on the model as it stands

    def test_a_hole_is_filled_from_its_rim_and_faces_the_way_the_wall_does(self):
        """The rail yard's crane leg sills and warehouse wall (2026-11-13): holes of 12 to 16 corners."""
        turns = np.linspace(0, 2 * np.pi, 8, endpoint=False)  # an octagonal hole in a wall of radius 3 facing -y
        vertices = np.array([[r * np.cos(a), 0.0, r * np.sin(a) + 2] for r in (1, 3) for a in turns], float)
        normals = np.tile([0.0, -1.0, 0.0], (16, 1)); uvs = np.zeros((16, 2))
        faces = np.array([face for k in range(8) for face in ([k, (k + 1) % 8, 8 + k], [(k + 1) % 8, 8 + (k + 1) % 8, 8 + k])])
        before = len(faces)
        filled = convert.filled(vertices, normals, uvs, faces, [{'part': 'octagon', 'at': [1.0, 0.0, 2.0]}])
        made = filled[before:]
        self.assertEqual(len(made), 6)  # an eight-cornered ring takes six faces between its own corners
        self.assertTrue(set(made.ravel()) <= set(range(8)))
        across = np.cross(vertices[made[:, 1]] - vertices[made[:, 0]], vertices[made[:, 2]] - vertices[made[:, 0]])
        self.assertTrue((across[:, 1] < 0).all())  # wound to face -y, as the wall's normals do
        with self.assertRaisesRegex(ValueError, 'No hole'):  # a point near no rim is a mistake in the set
            convert.filled(vertices, normals, uvs, faces, [{'at': [0.0, 0.0, 2.0]}])

    def test_only_the_faces_in_a_box_are_given_backs(self):
        """The rail yard's crane sills (2026-11-13) had faces wound inward."""
        vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 0, 1], [5, 0, 0], [6, 0, 0], [5, 0, 1]], float)
        normals = np.tile([0.0, -1.0, 0.0], (6, 1)); uvs = np.zeros((6, 2)); faces = np.array([[0, 1, 2], [3, 4, 5]])
        v, n, u, f = convert.backed(vertices, normals, uvs, faces, [{'box': [[4, -1, -1], [7, 1, 2]]}])
        self.assertEqual(len(f), 3); np.testing.assert_array_equal(v[f[2]], vertices[[3, 5, 4]])  # the far face again, wound the other way
        np.testing.assert_array_equal(n[f[2]], -normals[[3, 5, 4]])
        self.assertEqual(len(convert.backed(vertices, normals, uvs, faces)[3]), 4)  # without boxes every face is backed
        with self.assertRaisesRegex(ValueError, 'holds no face'):
            convert.backed(vertices, normals, uvs, faces, [{'box': [[10, -1, -1], [11, 1, 2]]}])

    def test_a_rod_clears_a_slanted_rail_and_leaves_the_treads_under_it(self):
        """The rail yard's stair tower (2026-11-13): wavy handrails along its flights."""
        rail = [[x, 0.0, 1.0 + x] for x in (0.0, 0.1, 2.0, 2.1)]; tread = [[1.0, -0.5, 0.0], [1.2, -0.5, 0.0], [1.2, 0.5, 0.0]]
        vertices = np.array(rail + tread, float); normals = np.tile([0.0, 0.0, 1.0], (7, 1)); uvs = np.zeros((7, 2))
        faces = np.array([[0, 1, 2], [1, 3, 2], [4, 5, 6]])
        _, _, _, kept = convert.cleared(vertices, normals, uvs, faces, [{'from': [0, 0, 1], 'to': [2, 0, 3], 'radius': 0.3}])
        self.assertEqual(len(kept), 1)  # only the tread is left
        with self.assertRaisesRegex(ValueError, 'takes no face'):
            convert.cleared(vertices, normals, uvs, faces, [{'from': [0, 3, 1], 'to': [2, 3, 3], 'radius': 0.3}])

    def test_a_moved_part_is_carried_whole_and_what_tied_it_on_is_taken_away(self):
        """The rail yard's walkway (2026-11-13): a leg 1.7 m in from its corner."""
        leg = [[0, 0, 0], [0.1, 0, 0], [0.1, 0, 1]]; deck = [[-1, -1, 2], [3, -1, 2], [3, 1, 2]]
        vertices = np.array(leg + deck, float); normals = np.tile([0.0, 0.0, 1.0], (6, 1)); uvs = np.arange(12, dtype=float).reshape(6, 2)
        faces = np.array([[0, 1, 2], [3, 4, 5], [2, 1, 3]])  # the leg, the deck and a brace from the leg's top to the deck
        v, n, u, f = convert.moved(vertices, normals, uvs, faces, [{'box': [[-0.1, -0.1, -0.1], [0.2, 0.1, 1.1]], 'by': [2, 0, 0]}])
        self.assertEqual(len(f), 2)  # the brace, torn between box and deck, goes
        shifted = [face for face in f if v[face][:, 0].min() >= 1.9 and v[face][:, 2].max() <= 1.0]
        self.assertEqual(len(shifted), 1); np.testing.assert_allclose(sorted(map(tuple, v[shifted[0]])), sorted(map(tuple, np.array(leg) + [2, 0, 0])))
        self.assertEqual(len(v), 6)  # the leg's old corners are let go
        with self.assertRaisesRegex(ValueError, 'holds no whole face'):
            convert.moved(vertices, normals, uvs, faces, [{'box': [[5, 5, 5], [6, 6, 6]], 'by': [1, 0, 0]}])

    def test_built_stairs_and_railings_are_straight_steel_coloured_from_the_model(self):
        """The rail yard's walkway had no stairs up to its deck, and its stair tower's rails were wavy (2026-11-13)."""
        members = convert.flight([0, -3, 0], [0, 0, 2.13], 0.9)
        treads = [m for m in members if m[3] == 'tread']; posts = [m for m in members if m[3] == 'post']
        rises = 2.13 / (len(treads) + 1)
        self.assertLessEqual(rises, convert.STEP_RISE); self.assertEqual(len(treads), int(np.ceil(2.13 / convert.STEP_RISE)) - 1)
        self.assertEqual(sum(m[3] == 'stringer' for m in members), 2)
        self.assertTrue(all(np.linalg.norm(np.subtract(m[1], m[0])[:2]) <= 1e-9 for m in posts))  # posts stand upright
        rails = convert.railing([[0, 0, 0], [2.5, 0, 0], [2.5, 1, 0]], height=1.0)
        self.assertEqual(sum(m[3] == 'rail' for m in rails), 4)  # a top and a mid rail on each leg
        spots = sorted({tuple(np.round(m[0][:2], 3)) for m in rails if m[3] == 'post'})
        self.assertIn((0.0, 0.0), spots); self.assertIn((2.5, 0.0), spots); self.assertIn((2.5, 1.0), spots)  # a post at every corner
        self.assertEqual(len(spots), len(set(spots)))
        points, normals, faces = convert._bar([0, 0, 0], [1, 0, 0], (0.1, 0.2))
        self.assertEqual((len(points), len(faces)), (24, 12)); np.testing.assert_allclose(np.ptp(points, axis=0), [1, 0.1, 0.2])
        across = np.cross(points[faces[:, 1]] - points[faces[:, 0]], points[faces[:, 2]] - points[faces[:, 0]])
        self.assertTrue(((across * normals[faces[:, 0]]).sum(1) > 0).all())  # every face wound outward
        # The colour is the model's picture where `picture` touches it.
        vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [5, 0, 0], [6, 0, 0], [5, 1, 0]], float)
        uvs = np.array([[0.1, 0.1]] * 3 + [[0.9, 0.9]] * 3); base = np.array([[0, 1, 2], [3, 4, 5]])
        np.testing.assert_allclose(convert.picture_at(vertices, uvs, base, [5.2, 0.2, 0.3]), [0.9, 0.9])
        v, n, u, f = convert.with_built(vertices, np.tile([0.0, 0.0, 1.0], (6, 1)), uvs, base,
                                        [{'railing': [[0, 0, 0], [1, 0, 0]], 'height': 1.0, 'picture': [0.2, 0.2, 0]},
                                         {'stairs': {'foot': [0, -3, 0], 'top': [0, 0, 2.13], 'width': 0.9}, 'picture': [0.2, 0.2, 0], 'rails': [5.2, 0.2, 0]}])
        self.assertEqual(len(f), 2 + 12 * (len(convert.railing([[0, 0, 0], [1, 0, 0]], 1.0)) + len(members)))
        stair_uvs = u[len(u) - 24 * len(members):]; kinds = [m[3] for m in members for _ in range(24)]
        np.testing.assert_allclose(stair_uvs[[k for k, kind in enumerate(kinds) if kind in ('rail', 'post')]], 0.9)
        np.testing.assert_allclose(stair_uvs[[k for k, kind in enumerate(kinds) if kind == 'tread']], 0.1)

    def test_a_game_set_states_fills_moves_backs_rods_and_built_parts_on_the_finished_model(self):
        path = Path(tempfile.mkdtemp()) / 'set.json'
        good = {'fill': [{'part': 'p', 'at': [0, 0, 1]}], 'move': [{'box': [[0, 0, 0], [1, 1, 1]], 'by': [1, 0, 0]}],
                'inside': [{'box': [[0, 0, 0], [1, 1, 1]]}], 'clear': [{'from': [0, 0, 1], 'to': [1, 0, 2], 'radius': 0.3}],
                'built': [{'railing': [[0, 0, 1], [1, 0, 1]], 'height': 1.0, 'picture': [0, 0, 1]},
                          {'stairs': {'foot': [0, -3, 0], 'top': [0, 0, 2], 'width': 0.9}, 'picture': [0, 0, 1]}]}
        for key, value in good.items():
            path.write_text(json.dumps({'models': {'ek_x': {'source': 'a', 'height': 4.0, key: value, 'measuredAt': 4.0}}}), encoding='utf-8')
            self.assertEqual(convert.load_models(path)['ek_x'][key], value)
            path.write_text(json.dumps({'models': {'ek_x': {'source': 'a', 'height': 4.0, key: value}}}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'measuredAt'):
                convert.load_models(path)  # each is measured on the model as it stands
        for key, value in (('move', [{'box': [[0, 0, 0], [1, 1, 1]]}]), ('fill', [{'at': [0, 0]}]),
                           ('built', [{'railing': [[0, 0, 1], [1, 0, 1]], 'height': 3.0, 'picture': [0, 0, 1]}]),
                           ('built', [{'stairs': {'foot': [0, -3, 0], 'top': [0, 0, 2]}, 'picture': [0, 0, 1]}]),  # a flight needs its width
                           ('built', [{'stairs': {'foot': [0, 0, 0], 'top': [0, 0, 2], 'width': 0.9}, 'picture': [0, 0, 1]}])):  # and a run, or it is a ladder
            path.write_text(json.dumps({'models': {'ek_x': {'source': 'a', 'height': 4.0, key: value, 'measuredAt': 4.0}}}), encoding='utf-8')
            with self.assertRaises(ValueError):
                convert.load_models(path)

    def test_a_model_is_drawn_out_along_its_longer_side_to_a_length(self):
        """The rail yard's shipping containers (2026-11-13) came out a third to a half short at their true height."""
        box = np.array([[x, y, z] for x in (-1.75, 1.75) for y in (-1.2, 1.2) for z in (0, 2.6)], float)
        slant = np.tile(np.array([1.0, 0.0, 1.0]) / np.sqrt(2), (8, 1))
        points, normals = convert.stretched(box, slant, 6.06)
        np.testing.assert_allclose(np.ptp(points, axis=0), [6.06, 2.4, 2.6]); np.testing.assert_allclose(np.linalg.norm(normals, axis=1), 1.0)
        self.assertLess(normals[0, 0], normals[0, 2])  # a surface drawn out leans less along the stretch: its normal turns away from it
        points, _ = convert.stretched(box[:, [1, 0, 2]], slant, 6.06)  # the longer side along the other axis is the one drawn out
        np.testing.assert_allclose(np.ptp(points, axis=0), [2.4, 6.06, 2.6])
        with self.assertRaisesRegex(ValueError, 'A length is a number of metres'):
            convert.stretched(box, slant, 0)

    def test_a_mesh_too_big_for_one_node_is_cut_into_nodes_that_keep_every_face(self):
        faces = np.arange(300).reshape(-1, 3)  # 100 triangles sharing no vertex
        parts = convert.split(faces, limit=90)
        self.assertGreater(len(parts), 1); self.assertTrue(all(len(used) <= 90 for used, _ in parts))
        self.assertEqual(sum(len(part) for _, part in parts), 100)
        np.testing.assert_array_equal(np.concatenate([used[part] for used, part in parts]), faces)
        vertices = np.zeros((300, 3)); text = convert.model_text('ek_test', vertices, np.tile([0, 0, 1.0], (300, 1)), np.zeros((300, 2)), faces)
        self.assertEqual(text.count('node trimesh'), 1)  # under the real limit it is one node
        self.assertIn('  bitmap ek_test', text); self.assertIn('  shadow 0', text); self.assertIn('faces 100', text)
        with self.assertRaisesRegex(ValueError, 'resref'):
            convert.model_text('ek_name_too_long', vertices, vertices, np.zeros((300, 2)), faces)

    def test_material_and_collision_follow_the_working_layout(self):
        material = convert.material_text('ek_test', illumination=True)
        self.assertIn('renderhint NormalAndSpecMapped', material)
        for line in ('texture0 ek_test', 'texture1 ek_test_n', 'texture2 ek_test_s', 'texture3 ek_test_r', 'texture5 ek_test_i'):
            self.assertIn(line, material)
        self.assertIn('texture5 null', convert.material_text('ek_test'))
        crate = np.array([[x, y, z] for x in (-1.0, 1.0) for y in (-0.5, 0.5) for z in (0.0, 2.0)])
        walk = convert.walk_text('ek_test', crate)
        self.assertIn('node trimesh ek_test_wg', walk); self.assertIn('parent ek_test_pwk', walk); self.assertEqual(walk.count(' 7\n'), 10)
        self.assertIn('ek_test_pwk_use01', walk); self.assertIn('  position 0 1.00000 0', walk)  # half a metre in front of it
        self.assertEqual(convert.outline(crate), [(1.0, 0.5), (-1.0, 0.5), (-1.0, -0.5), (1.0, -0.5)])  # a box keeps its four corners
        # A camera on an arm: a small housing far out along +y from a wall plate. The block follows it, not its bounding box.
        arm = np.array([[x, y, 0.0] for x, y in ((-0.5, 0.0), (0.5, 0.0), (-0.1, 1.0), (0.1, 1.0))])
        corners = np.array(convert.outline(arm)); x, y = corners[:, 0], corners[:, 1]
        area = abs(float(x @ np.roll(y, -1) - y @ np.roll(x, -1))) / 2
        self.assertLess(area, 0.9); self.assertGreaterEqual(area, 0.6 - 1e-9)  # between the shape itself (0.6) and its box (1.0): the corners are cut
        for index in range(len(corners)):  # and it holds every point: none lies outside any of its sides
            edge = corners[(index + 1) % len(corners)] - corners[index]; out = np.array([edge[1], -edge[0]])
            self.assertLessEqual(float(((arm[:, :2] - corners[index]) @ out).max()), 1e-9)
        hung = convert.walk_text('ek_test', crate + [0, 0, 2.6], overhead=True)
        self.assertNotIn('_wg', hung); self.assertIn('ek_test_pwk_use02', hung)  # walked under: nothing to walk into

    def test_specular_is_small_for_paint_and_the_surface_colour_for_metal(self):
        base = np.full((1, 2, 3), 0.8)
        np.testing.assert_allclose(convert.specular(base, np.array([[0.0, 1.0]])), [[0.04, 0.8]])


class FixtureTests(unittest.TestCase):
    def test_props_are_appended_to_the_table_and_placed_static(self):
        stock = ('2DA V2.0\r\n\r\n  Label StrRef ModelName LightColor LightOffsetX LightOffsetY LightOffsetZ SoundAppType ShadowSize BodyBag LowGore Reflection Static\r\n'
                 '0 Armoire 5645 PLC_A01 **** **** **** **** 13 1 0 **** **** 1\r\n7 Chest **** ek_a **** **** **** **** 27 1 0 **** **** 1\r\n')
        text, rows = fixture.table(stock, ['ek_a', 'ek_b'])  # ek_a is in the table already: the one under test still gets a row of its own
        self.assertEqual(rows, {'ek_a': 8, 'ek_b': 9}); self.assertTrue(text.startswith(stock))
        self.assertEqual(text.split('\r\n')[-2].split(), ['9', '"[envkit]ek_b"', '****', 'ek_b', '****', '****', '****', '****', '****', '1', '0', '****', '****', '1'])
        prop = fixture.placed('fx_p0', 8, [30.0, 40.0], 3.14)
        self.assertEqual((prop['__struct_id'], prop['Appearance']['value'], prop['Static']['value']), (9, 8, 1))
        self.assertEqual(fixture.placed('fx_p1', 8, [30.0, 40.0], 3.14, static=False)['Static']['value'], 0)  # one a script can reach
        with self.assertRaisesRegex(ValueError, 'Unexpected placeables table'):
            fixture.table('not a table\n\nx\n', ['ek_a'])

    def test_the_entry_script_steps_through_the_shots_and_says_when_it_is_done(self):
        script = fixture.enter_script([{'label': 'a', 'stand': [30, 38]}, {'label': 'b', 'stand': [34, 38], 'distance': 9}])
        self.assertIn('if(n>=2) { WriteTimestampedLogEntry("ENVKIT done"); return; }', script)
        self.assertIn('x=34.000; y=38.000; facing=90.000; distance=9.000;', script); self.assertIn('ENVKIT shot=', script)
        dark = fixture.enter_script([{'label': 'a', 'stand': [30, 38], 'run': 'ReplaceObjectTexture(GetObjectByTag("fx_p0"),"ek_a_i","ek_black");'}])
        self.assertIn('label="a"; ReplaceObjectTexture(GetObjectByTag("fx_p0"),"ek_a_i","ek_black"); }', dark)
        with self.assertRaisesRegex(ValueError, 'one line'):
            fixture.enter_script([{'label': 'a', 'stand': [30, 38], 'run': 'a;' + chr(10) + 'b;'}])
        for label in ('say "hi"', 'lights off', 'a/b'):  # it goes into the script, the log line and a file name
            with self.assertRaisesRegex(ValueError, 'shot label'):
                fixture.enter_script([{'label': label, 'stand': [30, 38]}])


if __name__ == '__main__':
    unittest.main()
