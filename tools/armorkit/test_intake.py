"""An outfit made elsewhere is read with its textures, sorted into its materials, drawn in the flat colours the
bake tells materials by, and stored as the colour field a bake opens."""
import io
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from tools.headkit import gltf

from . import brief, intake, texture
from .registry import SLOTS  # noqa: F401  (the package loads)

DARK, GREY, PINK = (40, 40, 40), (90, 90, 90), (235, 185, 155)


def png(image):
    out = io.BytesIO()
    Image.fromarray(np.asarray(image, np.uint8)).save(out, format='PNG')
    return out.getvalue()


def textures(side=64):
    """(base colour, metallic-roughness): the left half dark cloth, the right half grey metal, as images."""
    colour = np.zeros((side, side, 3), np.uint8)
    colour[:, :side // 2], colour[:, side // 2:] = DARK, GREY
    other = np.zeros((side, side, 3), np.uint8)
    other[:, :, 1] = 128  # roughness
    other[:, side // 2:, 2] = 200  # metallic
    return colour, other


def box(size=(0.4, 0.2, 1.8)):
    """A box about the origin in glTF's axes (y up), a vertex per face corner: (positions, faces, uv). The faces
    looking along glTF's -x have the texture's left half, the rest its right half."""
    half = np.array([size[0], size[2], size[1]]) / 2
    positions, faces, uv = [], [], []
    for axis in range(3):
        for sign in (-1.0, 1.0):
            u, v = np.eye(3)[(axis + 1) % 3], np.eye(3)[(axis + 2) % 3]
            corners = [sign * np.eye(3)[axis] + a * u + b * v for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            start = len(positions)
            positions += [corner * half for corner in corners]
            faces += [(start, start + 1, start + 2), (start, start + 2, start + 3)] if sign > 0 else [(start, start + 2, start + 1), (start, start + 3, start + 2)]
            left = axis == 0 and sign < 0
            uv += [((0.1 if left else 0.6) + 0.3 * (a > 0), 0.1 + 0.8 * (b > 0)) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    return np.array(positions, np.float32), np.array(faces, np.uint16), np.array(uv, np.float32)


def glb(positions, faces, uv, colour, other=None):
    """The bytes of a mesh file with its textures inside, as an export holds them."""
    blob, views, accessors = bytearray(), [], []

    def view(data):
        blob.extend(b'\0' * (-len(blob) % 4))
        views.append({'buffer': 0, 'byteOffset': len(blob), 'byteLength': len(data)})
        blob.extend(data)
        return len(views) - 1

    for array, kind, component in ((positions, 'VEC3', 5126), (uv, 'VEC2', 5126), (faces.reshape(-1), 'SCALAR', 5123)):
        accessors.append({'bufferView': view(np.ascontiguousarray(array).tobytes()), 'componentType': component, 'count': len(array), 'type': kind})
    images = [{'bufferView': view(png(image)), 'mimeType': 'image/png'} for image in (colour, other) if image is not None]
    shading = {'baseColorTexture': {'index': 0}} if colour is not None else {}
    if other is not None:
        shading['metallicRoughnessTexture'] = {'index': 1}
    document = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0}],
                'meshes': [{'primitives': [{'attributes': {'POSITION': 0, 'TEXCOORD_0': 1}, 'indices': 2, 'material': 0}]}],
                'materials': [{'pbrMetallicRoughness': shading}], 'textures': [{'source': index} for index in range(len(images))],
                'images': images, 'accessors': accessors, 'bufferViews': views, 'buffers': [{'byteLength': len(blob)}]}
    return gltf.encode(document, bytes(blob))


def document(**changes):
    made = {'schemaVersion': 1, 'kind': intake.KIND, 'model': 'meshy-box',
            'source': {'provider': 'Meshy', 'file': 'box.glb', 'sha256': '0' * 64},
            'materials': [{'name': 'fabric', 'kind': 'cloth', 'wears': 'the box.', 'anchors': [{'colour': list(DARK), 'metal': 0.0}]},
                          {'name': 'plates', 'kind': 'metal', 'wears': 'its plate.', 'anchors': [{'colour': list(GREY), 'metal': 0.8}]}],
            'skin': {'anchors': [{'colour': list(PINK)}], 'as': 'fabric'}, 'faces': 2000}
    made.update(changes)
    return made


class IntakeTests(unittest.TestCase):
    def loaded(self, colour=None, other=None, folder=None):
        base, rough = textures()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(folder or temporary) / 'box.glb'
            path.write_bytes(glb(*box(), base if colour is None else colour, rough if other is None else other))
            return intake.load(path)

    def test_a_file_is_read_in_the_bodies_axes_with_its_textures(self):
        mesh = self.loaded()
        self.assertEqual(mesh['vertices'].shape, (24, 3))
        np.testing.assert_allclose(np.ptp(mesh['vertices'], axis=0), (0.4, 0.2, 1.8), atol=1e-6)  # glTF's y is up; the bodies' z is
        self.assertEqual(mesh['colour'].shape, (64, 64, 3))
        self.assertEqual((int(mesh['rough'][0, 0]), int(mesh['metal'][0, 0]), int(mesh['metal'][0, 63])), (128, 0, 200))
        positions, faces, uv = box()
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'bare.glb').write_bytes(glb(positions, faces, uv, None))
            with self.assertRaisesRegex(ValueError, 'no base colour texture'):
                intake.load(Path(folder) / 'bare.glb')

    def test_texels_are_read_at_texture_coordinates_and_held_to_the_edge(self):
        image = np.arange(16).reshape(4, 4)
        np.testing.assert_array_equal(intake.texels(image, [(0.0, 0.0), (0.99, 0.0), (0.3, 0.6), (1.5, -1.0)]), (0, 3, 9, 3))

    def test_a_view_draws_the_mesh_in_its_own_colours(self):
        seen = intake.view(self.loaded(), (-1.0, 0.0, 0.0), size=64)  # looking along -x the bodies' +x face is nearest: glTF's -x, the left half
        self.assertEqual(tuple(int(part) for part in seen[32, 32]), DARK)
        self.assertEqual(tuple(int(part) for part in intake.view(self.loaded(), (1.0, 0.0, 0.0), size=64)[32, 32]), GREY)
        self.assertEqual(tuple(int(part) for part in seen[1, 1]), (255, 255, 255))
        self.assertEqual(intake.views(self.loaded(), size=32).shape, (32, 96, 3))

    def test_texels_are_sorted_by_colour_and_by_metal(self):
        mesh = self.loaded()
        found = intake.sort(mesh, document())
        self.assertTrue((found[:, :32] == 0).all() and (found[:, 32:] == 1).all())
        same = dict(mesh, colour=np.full((64, 64, 3), 60, np.uint8))  # one grey all over: the metal alone tells them
        found = intake.sort(same, document())
        self.assertTrue((found[:, :32] == 0).all() and (found[:, 32:] == 1).all())
        pink = dict(mesh, colour=np.full((64, 64, 3), PINK, np.uint8), metal=np.zeros((64, 64), np.uint8))
        self.assertTrue((intake.sort(pink, document()) == 2).all())  # skin is numbered one past the materials

    def test_a_thin_line_goes_to_the_material_round_it_and_texels_off_the_faces_do_not_vote(self):
        found = np.zeros((40, 40), np.uint8)
        found[:, 20] = 1  # a worn edge, a texel wide
        found[:, 30:] = 1  # a plate
        on = np.ones((40, 40), bool)
        settled = intake.settled(found, on, 2, 3)
        self.assertTrue((settled[:, :26] == 0).all() and (settled[:, 34:] == 1).all())
        on[:, 30:] = False  # the plate's texels are on no face: the cloth beside them stays cloth, and they stay as sorted
        settled = intake.settled(found, on, 2, 3)
        self.assertTrue((settled[:, :30] == 0).all() and (settled[:, 30:] == 1).all())
        np.testing.assert_array_equal(intake.settled(found, on, 2, 0), found)

    def test_the_texels_on_faces_are_found(self):
        on = intake.islands(self.loaded())
        self.assertTrue(on[32, 10] and on[32, 50])  # inside the two islands
        self.assertFalse(on[1, 1] or on[32, 30])  # the margin, and the gap between them

    def test_the_texture_is_drawn_in_flat_colours_with_its_own_shading(self):
        base, other = textures()
        base[:32, :32] = (20, 20, 20)  # the cloth's upper half darker
        mesh = self.loaded(base, other)
        image, record = intake.flat(mesh, document())
        cloth, metal = intake.PALETTE['cloth'][0], intake.PALETTE['metal'][0]
        self.assertEqual(tuple(image[40, 50]), metal)  # at its material's middle lightness a texel is the flat colour
        self.assertLess(int(image[10, 10, 0]), int(image[50, 10, 0]))  # darker cloth stays darker
        np.testing.assert_allclose(image[10, 10] / image[10, 10, 0], np.array(cloth) / cloth[0], atol=0.05)  # in the cloth's own colour
        self.assertEqual(set(record['materials']), {'fabric', 'plates'})
        self.assertAlmostEqual(sum(material['share'] for material in record['materials'].values()), 1.0, places=3)
        found = texture.materials(image[intake.islands(mesh)] / 255.0, 2)  # the bake finds two materials in it
        self.assertEqual(len(found['tones']), 2)

    def test_skin_is_drawn_as_the_material_the_document_names_and_refused_without_one(self):
        base, other = textures()
        base[40:, :32] = PINK
        other[40:, :32, 2] = 0
        mesh = self.loaded(base, other)
        image, record = intake.flat(mesh, document())
        self.assertGreater(record['skinShare'], 0.02)
        cloth = np.array(intake.PALETTE['cloth'][0], float)
        np.testing.assert_allclose(image[50, 10] / image[50, 10, 0], cloth / cloth[0], atol=0.05)  # skin, drawn as cloth
        unnamed = document()
        del unnamed['skin']['as']
        with self.assertRaisesRegex(ValueError, 'what it is drawn as'):
            intake.flat(mesh, unnamed)

    def test_a_material_the_bake_would_not_find_is_refused(self):
        base, other = textures()
        base[:, 32:], other[:, 32:, 2] = DARK, 0  # no plate anywhere
        with self.assertRaisesRegex(ValueError, 'plates is 0.0% of the surface'):
            intake.flat(self.loaded(base, other), document())

    def test_the_flat_colours_are_far_enough_apart_for_a_brief(self):
        colours = np.array([colour for pair in intake.PALETTE.values() for colour in pair], float)
        tones = texture.tone(colours / 255)
        gaps = [float(np.linalg.norm(tones[i] - tones[j])) for i in range(len(tones)) for j in range(i)]
        self.assertGreaterEqual(min(gaps), brief.APART)
        self.assertLessEqual(colours.max() * intake.SHADE[1], 300)  # the lightest shade is still mostly a colour

    def test_the_nearest_face_and_place_on_it(self):
        vertices = np.array([(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 5), (1, 0, 5), (0, 1, 5)], float)
        faces = np.array([(0, 1, 2), (3, 4, 5)])
        face, weights = intake.closest([(0.25, 0.25, 0.3), (0.2, 0.2, 4.0), (2.0, 0.0, 0.1), (-1.0, -1.0, 5.0)], vertices, faces)
        np.testing.assert_array_equal(face, (0, 1, 0, 1))
        np.testing.assert_allclose(weights, [(0.5, 0.25, 0.25), (0.6, 0.2, 0.2), (0, 1, 0), (1, 0, 0)], atol=1e-9)

    def test_a_colour_field_is_stored_as_a_bake_opens_one(self):
        mesh = self.loaded()
        image, _ = intake.flat(mesh, document())
        scale = intake.FILL / 1.8
        framed = intake.to_frame(mesh['vertices'], scale)
        np.testing.assert_allclose(np.ptp(framed, axis=0), np.array((0.4, 1.8, 0.2)) * scale)  # back in glTF's axes, y up
        coords, attrs = intake.colour_field([(framed, mesh['faces'])], intake.reader(mesh, scale, image), resolution=64)
        self.assertEqual((coords.shape[1], attrs.shape[1], len(coords)), (3, 6, len(attrs)))
        self.assertEqual(len(np.unique(coords, axis=0)), len(coords))
        with tempfile.TemporaryDirectory() as folder:
            np.savez_compressed(Path(folder) / 'colours.npz', coords=coords, attrs=attrs, resolution=np.array(64))
            field, levels = texture.open_field(Path(folder) / 'colours.npz')
            at = np.array([(-0.2, 0.0, 0.0), (0.2, 0.0, 0.0)]) * scale  # the middles of the -x and +x faces, in the field's frame, glTF's axes
            values, missed = texture.read_field(field, levels, at)
        self.assertFalse(missed.any())
        np.testing.assert_allclose(values[0, :3] * 255, intake.PALETTE['cloth'][0], atol=3)
        np.testing.assert_allclose(values[1, :3] * 255, intake.PALETTE['metal'][0], atol=3)
        np.testing.assert_allclose(values[:, 3], (0.0, 200 / 255), atol=0.02)  # metallic, then roughness
        np.testing.assert_allclose(values[:, 4], 128 / 255, atol=0.02)

    def test_a_field_refuses_a_surface_outside_its_cube(self):
        mesh = self.loaded()
        with self.assertRaisesRegex(ValueError, 'inside the field'):
            intake.shell([(intake.to_frame(mesh['vertices'], 1.0), mesh['faces'])], resolution=64)

    def test_an_intake_document_is_checked(self):
        self.assertEqual(intake.validate(document())['model'], 'meshy-box')
        for wrong, said in (({'kind': 'srn-armorkit-brief'}, 'kind'), ({'source': {'provider': 'Meshy'}}, 'sha256'), ({'extra': 1}, 'holds'),
                            ({'faces': 100}, '2,000'), ({'skin': {'anchors': [{'colour': [1, 2, 3]}], 'as': 'leather'}}, 'drawn as'),
                            ({'materials': []}, 'one to six')):
            with self.assertRaisesRegex(ValueError, said):
                intake.validate(document(**wrong))
        thrice = document()
        thrice['materials'] = [dict(thrice['materials'][0], name=name) for name in 'abc']
        with self.assertRaisesRegex(ValueError, 'at most two'):
            intake.validate(thrice)
        unanchored = document()
        unanchored['materials'][0]['anchors'] = [{'colour': [300, 0, 0]}]
        with self.assertRaisesRegex(ValueError, 'anchors'):
            intake.validate(unanchored)

    def test_the_brief_of_an_intake_is_one_the_bake_reads(self):
        made = intake.brief(document(bare=['forearm']))
        self.assertEqual(brief.validate(made)['model'], 'meshy-box')
        self.assertEqual([material['colour'] for material in made['materials']], [list(intake.PALETTE['cloth'][0]), list(intake.PALETTE['metal'][0])])
        self.assertEqual((made['bare'], made['pads']), (['forearm'], []))
        self.assertIn('Meshy', brief.composed(made))
        two = document()
        two['materials'].append(dict(two['materials'][0], name='lining'))
        self.assertEqual(intake.brief(two)['materials'][2]['colour'], list(intake.PALETTE['cloth'][1]))  # the second of a kind

    def test_a_file_other_than_the_one_the_document_names_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'box.glb'
            path.write_bytes(glb(*box(), *textures()))
            with self.assertRaisesRegex(ValueError, 'not the file the intake document names'):
                intake.prepare(document(), path, Path(folder) / 'out', None, None)
            self.assertFalse((Path(folder) / 'out').exists())

    def test_the_kept_intake_documents_hold(self):
        for path in sorted(Path(__file__).with_name('intakes').glob('*.json')):
            with self.subTest(path.name):
                kept = intake.validate(json.loads(path.read_text(encoding='utf-8')))
                self.assertEqual(kept['model'], path.stem)
                self.assertRegex(kept['source']['sha256'], r'^[0-9a-f]{64}$')
                brief.prompt(intake.brief(kept))  # its flat colours are far enough apart


class WrapTests(unittest.TestCase):
    def setUp(self):
        try:
            import igl
            import pymeshlab
        except ImportError:
            self.skipTest('igl and pymeshlab not on the path (from the local runtime binding)')
        self.igl, self.meshlab = igl, pymeshlab

    def test_an_open_mesh_with_a_sheet_on_it_is_rebuilt_as_one_closed_surface(self):
        positions, faces, _ = box((0.2, 0.2, 0.6))
        weld = np.unique(np.round(positions, 6), axis=0, return_inverse=True)
        v, f = weld[0].astype(float), weld[1].reshape(-1)[faces.astype(int)]
        f = f[2:]  # one side of the box left open
        fin = len(v)  # and a sheet standing on an edge of it, which three faces then share
        v = np.concatenate([v, v[f[0, :2]] + (0.0, 0.05, 0.0)])
        f = np.concatenate([f, [(f[0, 0], f[0, 1], fin), (f[0, 1], fin + 1, fin)]])
        fine_v, fine_f, out_v, out_f = intake.wrap(v, f, self.igl, self.meshlab, voxel=0.01, offset=0.005, target=600)
        for points, triangles in ((fine_v, fine_f), (out_v, out_f)):
            edges = np.sort(np.concatenate([triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]]), axis=1)
            self.assertTrue((np.unique(edges, axis=0, return_counts=True)[1] == 2).all())  # closed, and no edge shared by three
            self.assertEqual(len(np.unique(intake.components(points, triangles))), 1)
            self.assertGreater(intake.volumes(points, triangles, np.zeros(len(triangles), int))[0], 0.5 * 0.2 * 0.6 * 0.2)  # wound to face out
        self.assertLessEqual(len(out_f), 620)
        self.assertLess(np.abs(out_v[:, 0]).max(), 0.1 + 0.02)  # and it lies on the box: its sides are where they were, the offset out


if __name__ == '__main__':
    unittest.main()
