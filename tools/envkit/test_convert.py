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

    def test_zero_normals_are_rebuilt_from_the_faces(self):
        vertices = np.array(WALL['vertices'], float) @ convert.TO_GAME.T; normals = np.array([[0, 1, 0], [0, 0, 0], [0, 1, 0], [0, 0, 0]], float)
        fixed, count = convert.repair_normals(vertices, normals, np.array(WALL['faces']))
        self.assertEqual(count, 2); np.testing.assert_allclose(np.linalg.norm(fixed, axis=1), 1.0)
        np.testing.assert_allclose(fixed[1], [0, 1, 0], atol=1e-9)

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
        walk = convert.walk_text('ek_test', np.array([-1.0, -0.5, 0]), np.array([1.0, 0.5, 2.0]))
        self.assertIn('node trimesh ek_test_wg', walk); self.assertIn('parent ek_test_pwk', walk); self.assertEqual(walk.count(' 7\n'), 10)
        self.assertIn('ek_test_pwk_use01', walk)

    def test_specular_is_small_for_paint_and_the_surface_colour_for_metal(self):
        base = np.full((1, 2, 3), 0.8)
        np.testing.assert_allclose(convert.specular(base, np.array([[0.0, 1.0]])), [[0.04, 0.8]])


class FixtureTests(unittest.TestCase):
    def test_props_are_appended_to_the_table_and_placed_static(self):
        stock = '2DA V2.0\r\n\r\n      Label StrRef ModelName LightColor\r\n0 Armoire 5645 PLC_A01 ****\r\n7 Chest **** PLC_C01 ****\r\n'
        text, rows = fixture.table(stock, ['ek_a', 'ek_b'])
        self.assertEqual(rows, {'ek_a': 8, 'ek_b': 9}); self.assertTrue(text.endswith('9 "[envkit]ek_b" **** ek_b **** **** **** **** **** 1 0 **** **** 1\r\n'))
        self.assertEqual(len(text.split('\r\n')[-2].split()) - 1, fixture.COLUMNS)
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
