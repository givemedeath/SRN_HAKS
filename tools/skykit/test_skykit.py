"""Checks of the dynamic skies: the dome, the materials, the shader's contract with the engine, the table rows and
the tracked resources. A GL check compiles and renders the real shader when ModernGL can make a context."""
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

import numpy as np

from tools.skykit import panorama, profiles, sphere
from tools.skykit import __main__ as build

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / 'srn_skybox'
MATH = (PACK / 'srn_sky_math.shd').read_text(encoding='ascii')
FRAGMENT = (PACK / 'srn_sky_fs.shd').read_text(encoding='ascii')


class Dome(unittest.TestCase):
    def test_faces_point_inward_and_are_not_degenerate(self):
        vertices, uvs, faces = sphere.mesh()
        v = np.array(vertices)
        for a, b, c in faces:
            normal = np.cross(v[b] - v[a], v[c] - v[a])
            self.assertGreater(np.linalg.norm(normal), 1e-3)
            self.assertLess(np.dot(normal, (v[a] + v[b] + v[c]) / 3), 0)

    def test_texture_coordinates_follow_azimuth_and_elevation(self):
        vertices, uvs, faces = sphere.mesh()
        for (x, y, z), (u, w) in zip(vertices, uvs):
            self.assertAlmostEqual(np.arcsin(z / sphere.RADIUS), (w - 0.5) * np.pi, places=4)
            if abs(z) < sphere.RADIUS * 0.999:
                azimuth = np.arctan2(y, x) % (2 * np.pi)
                self.assertAlmostEqual(np.cos(azimuth), np.cos(u * 2 * np.pi), places=4)

    def test_model_text_names_its_bitmap(self):
        text = sphere.ascii_model('srn_skyden_d', 'srn_skyden_d')
        self.assertIn('bitmap srn_skyden_d', text)
        self.assertIn('shadow 0', text)
        vertices, uvs, faces = sphere.mesh()
        self.assertIn(f'verts {len(vertices)}', text)
        self.assertIn(f'faces {len(faces)}', text)


class Shader(unittest.TestCase):
    def test_fragment_keeps_the_engine_fade(self):
        # the game's dawn/day/dusk/night crossfade lives in globalColor.a
        self.assertRegex(FRAGMENT, r'gl_FragColor\s*=\s*vec4\(colour,\s*globalColor\.a\)')

    def test_every_material_parameter_is_a_shader_uniform_and_back(self):
        uniforms = set(re.findall(r'uniform\s+(?:float|vec4)\s+(Sky\w+)', MATH))
        self.assertEqual(uniforms, set(build.PARAMETER_ORDER))

    def test_glsl_110_habits(self):
        # integer arithmetic and implicit int->float conversions are errors on strict drivers
        body = MATH.split('#define SRN_TAU')[1]
        self.assertNotRegex(body, r'(?<![\w.])\d+\s*/\s*\d+(?![\d.])')
        self.assertNotIn('texture(', body)


class Profiles(unittest.TestCase):
    def test_every_row_resolves_and_names_fit(self):
        materials = profiles.materials()
        for name in materials:
            self.assertLessEqual(len(name), 16)
        for label, cyclical, key, phases, columns in profiles.SKIES.values():
            self.assertEqual(len(columns), 4)
            for texture in profiles.texture_names(key):
                self.assertLessEqual(len(texture), 16)

    def test_every_phase_sets_every_parameter(self):
        for name, (key, parameters) in profiles.materials().items():
            text, values = build.material_text(key, parameters, (-2.0, 15.0))
            for parameter in build.PARAMETER_ORDER:
                self.assertIn(f'parameter float {parameter} ', text)
            self.assertIn('customshaderFS srn_sky_fs', text)
            self.assertIn(f'customshaderVS {build.VERTEX_SHADER}', text)
            for unit, texture in enumerate(profiles.texture_names(key)):
                self.assertIn(f'texture{unit} {texture}', text)

    def test_table_holds_our_rows(self):
        lines = (ROOT / 'srn_2da' / 'skyboxes.2da').read_text(encoding='ascii').splitlines()
        found = {int(line.split()[0]): line.split() for line in lines if line.split() and line.split()[0].isdigit()}
        for row, (label, cyclical, models) in build.table_rows().items():
            self.assertEqual(found[row], [str(row), label, '****', str(cyclical), *models])

    def test_rewriting_the_table_keeps_other_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'skyboxes.2da'
            path.write_text('2DA V2.0\n\n LABEL STRING_REF CYCLICAL DAWN DAY DUSK NIGHT\n0 (None) **** **** **** **** ****\n'
                            '16 Old **** 0 a b c d\n', encoding='ascii')
            build.write_table({16: ('New', 1, ['w', 'x', 'y', 'z'])}, path)
            text = path.read_text(encoding='ascii')
            self.assertIn('0 (None)', text)
            self.assertNotIn('Old', text)
            self.assertRegex(text, r'16\s+New\s+\*\*\*\*\s+1\s+w\s+x\s+y\s+z')


class Panorama(unittest.TestCase):
    def test_cut_keeps_land_and_drops_floating_specks(self):
        rgb = np.zeros((40, 10, 3), np.float32)
        rgb[:, :, 1] = 1.0                 # green key everywhere
        rgb[25:, :] = (0.3, 0.2, 0.4)      # land below row 25
        rgb[5, 4] = (0.3, 0.2, 0.4)        # a speck in the sky
        rgb[30, 3] = (0.0, 1.0, 0.0)       # a key-coloured window inside the land
        cut = panorama.cut(rgb, 'green')
        self.assertEqual(cut[5, 4, 3], 0.0)
        self.assertEqual(cut[30, 3, 3], 1.0)
        self.assertEqual(cut[35, 0, 3], 1.0)
        self.assertEqual(cut[10, 0, 3], 0.0)

    def test_tga_header_and_row_order(self):
        image = np.zeros((2, 3, 4), np.float32)
        image[0] = (1, 0, 0, 1)  # top row red
        data = panorama.tga(image)
        self.assertEqual(data[2], 2)
        self.assertEqual((data[12] | data[13] << 8, data[14] | data[15] << 8, data[16]), (3, 2, 32))
        # rows run up from the bottom: the top row is written last, as BGRA
        self.assertEqual(tuple(data[-4:]), (0, 0, 255, 255))

    def test_assembled_strip_keeps_views_and_join_middles(self):
        rng = np.random.default_rng(1)
        h, w = panorama.VIEW[1] // 8, panorama.VIEW[0]
        views = [rng.random((h, w, 3)).astype(np.float32) for _ in range(3)]
        joins = [panorama.join_input(views[i], views[(i + 1) % 3]) for i in range(3)]
        strip = panorama.assemble(views, joins)
        keep, trim, span = panorama.JOIN_KEEP, panorama.JOIN_TRIM, joins[0].shape[1]
        body = w - 2 * (keep - trim)
        self.assertEqual(strip.shape[1], 3 * (body + span - 2 * trim))
        # an unchanged join (the input itself) leaves the views' own columns in place across the meeting
        self.assertTrue(np.allclose(strip[:, :body], views[0][:, keep - trim:w - keep + trim]))
        self.assertTrue(np.allclose(strip[:, body:body + keep - trim], views[0][:, w - keep + trim:], atol=1e-5))

    def test_band_degrees(self):
        strip = np.zeros((100, 3600, 4), np.float32)
        self.assertEqual(panorama.band_degrees(strip, 2.0, 1.0), (-2.0, 8.0))


class Resources(unittest.TestCase):
    def test_manifest_matches_the_pack(self):
        manifest = json.loads((ROOT / 'docs' / 'skies' / 'manifest.json').read_text(encoding='utf-8'))
        for name, digest in manifest['shaders'].items():
            self.assertEqual(hashlib.sha256((PACK / name).read_bytes()).hexdigest(), digest, name)
        for name, digest in manifest['resources'].items():
            self.assertEqual(hashlib.sha256((PACK / name).read_bytes()).hexdigest(), digest, name)
        for name in profiles.materials():
            for suffix in ('.mdl', '.mtr', '.dds'):
                self.assertIn(name + suffix, manifest['resources'])
        for key in {key for key, _ in profiles.materials().values()}:
            for texture in profiles.texture_names(key):
                self.assertIn(texture + '.dds', manifest['resources'])

    def test_tracked_materials_are_what_the_profiles_write(self):
        manifest = json.loads((ROOT / 'docs' / 'skies' / 'manifest.json').read_text(encoding='utf-8'))
        for name, (key, parameters) in profiles.materials().items():
            text, _ = build.material_text(key, parameters, tuple(manifest['panoramas'][key]['band']))
            self.assertEqual((PACK / (name + '.mtr')).read_text(encoding='ascii'), text, name)


class Render(unittest.TestCase):
    def test_shader_compiles_and_animates(self):
        try:
            from tools.skykit.preview import Renderer
            renderer = Renderer()
        except Exception as error:  # no ModernGL or no GL 3.3 context here
            self.skipTest(f'no GL context: {error}')
        land = np.zeros((64, 256, 4), np.float32)
        land[:20, :, :3] = 0.3
        land[:20, :, 3] = 1.0
        mask = np.zeros((64, 256, 3), np.float32)
        renderer.bind([(land[::-1], mask), (land[::-1], mask)])
        _, values = build.material_text('den', profiles.DEN_DUSK, (-2.0, 15.0))
        early = renderer.render(values, (128, 64), time_ms=100000, fade=0.4)
        late = renderer.render(values, (128, 64), time_ms=160000, fade=0.4)
        self.assertGreater(np.abs(early - late).max(), 0.0)          # the clouds move
        self.assertTrue(np.allclose(early[..., 3], 0.4, atol=0.01))  # the engine's fade passes through


if __name__ == '__main__':
    unittest.main()
