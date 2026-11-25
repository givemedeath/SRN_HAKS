"""Checks of the dynamic skies: the dome, the materials, the shader's contract with the engine, the table rows and
the tracked resources. A GL check compiles and renders the real shader when ModernGL can make a context."""
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

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

    def test_no_noise_breaks_where_the_azimuth_wraps(self):
        # noise fed the azimuth (or an atan of the direction) shows a seam where it jumps from 360 to 0 degrees
        for line in MATH.splitlines():
            if re.search(r'Srn(Noise|Fbm)\(', line):
                self.assertNotRegex(line, r'azimuth|atan\(', line)

    def test_glsl_110_habits(self):
        # integer arithmetic and implicit int->float conversions are errors on strict drivers
        body = MATH.split('#define SRN_TAU')[1]
        self.assertNotRegex(body, r'(?<![\w.])\d+\s*/\s*\d+(?![\d.])')
        self.assertNotIn('texture(', body)
        # smoothstep with edge0 >= edge1 is undefined: a falling edge is written 1.0 - smoothstep(low, high, x)
        for low, high in re.findall(r'smoothstep\(([^,()]+(?:\([^()]*\))?[^,()]*),\s*([^,()]+(?:\([^()]*\))?[^,()]*),', body):
            self.assertNotEqual(high.strip(), '0.0', f'smoothstep({low}, {high}, ...)')
            self.assertNotRegex(high, r'^\s*' + re.escape(low.strip()) + r'\s*\*\s*0\.\d+\s*$', f'smoothstep({low}, {high}, ...)')


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
                            '16 Old **** 0 a b c d\n17 SRN_Gone **** 0 a b c d\n', encoding='ascii')
            build.write_table({16: ('New', 1, ['w', 'x', 'y', 'z'])}, path)
            text = path.read_text(encoding='ascii')
            self.assertIn('0 (None)', text)
            self.assertNotIn('Old', text)
            self.assertNotIn('SRN_Gone', text)  # a row of ours the profiles dropped
            self.assertRegex(text, r'16\s+New\s+\*\*\*\*\s+1\s+w\s+x\s+y\s+z')
            longest = 'SRN_' + 'x' * 20, ['m' * 16] * 4  # a label past its column, models at the 16-character limit
            build.write_table({16: (longest[0], 0, longest[1])}, path)
            row = [line for line in path.read_text(encoding='ascii').splitlines() if line.startswith('16')][0]
            self.assertEqual(row.split(), ['16', longest[0], '****', '0', *longest[1]])
            build.write_table({}, path)  # no rows of ours: the rest stays
            self.assertIn('0 (None)', path.read_text(encoding='ascii'))


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

    def test_assembled_strip_keeps_views_and_wraps(self):
        rng = np.random.default_rng(1)
        h, w = panorama.VIEW[1] // 8, panorama.VIEW[0]
        views = [rng.random((h, w, 3)).astype(np.float32) for _ in range(3)]
        joins = [panorama.join_input(views[i], views[(i + 1) % 3]) for i in range(3)]
        strip = panorama.assemble(views, joins)
        step = w + panorama.JOIN_GAP
        self.assertEqual(strip.shape[1], 3 * step)
        # every view's columns outside the joins' overlaps stay as they were; the joins themselves are blended
        keep = panorama.JOIN_KEEP
        for i in range(3):
            self.assertTrue(np.allclose(strip[:, i * step + keep:i * step + w - keep], views[i][:, keep:w - keep], atol=1e-5))

    def test_seam_follows_where_pictures_agree(self):
        a = np.zeros((20, 200, 3), np.float32); b = np.ones((20, 200, 3), np.float32)
        b[:, 120:125] = 0.0  # the two pictures agree only in columns 120-124
        path = panorama.seam_path(a, b)
        self.assertTrue(((path >= 120) & (path < 125)).all())

    def test_searchlights_rise_from_the_rooftops(self):
        mask = np.zeros((100, 50, 3), np.float32)
        mask[60:, :, 0] = 1.0  # windows only in the bottom 40 rows
        self.assertAlmostEqual(panorama.roof_degrees(mask, (-2.0, 8.0)), 8.0 - 65.5 / 100 * 10.0, places=4)
        self.assertEqual(panorama.roof_degrees(np.zeros_like(mask), (-2.0, 8.0)), -2.0)
        _, values = build.material_text('den', profiles.DEN_NIGHT, (-2.0, 15.0, 3.0))
        self.assertEqual(values['SkyGlow'][3], 3.0)

    def test_grade_follows_the_overlap(self):
        rng = np.random.default_rng(2)
        land = rng.random((60, 80, 3)).astype(np.float32) * 0.5 + 0.2
        drifted = np.clip(land * np.array([0.8, 1.1, 0.9], np.float32), 0, 1)
        fixed = panorama.apply_gain(drifted, panorama.row_gain(land, drifted, 'magenta'), 'magenta')
        self.assertLess(np.abs(fixed - land).mean(), np.abs(drifted - land).mean() * 0.25)

    def test_detail_tiles_reassemble_the_strip(self):
        from tools.skykit import detail
        rng = np.random.default_rng(3)
        land = np.zeros((60, 900, 3), np.float32)
        land[:] = panorama.KEYS['magenta']
        land[20:] = (rng.random((40, 1, 3)) * 0.5 + 0.2)  # smooth land: rows of one colour each
        width, starts, height = detail.layout(land)
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            for index in range(len(starts)):  # a perfect redraw: the input itself, at the model's size
                tile = detail.tile_input(land, 'magenta', index)
                Image.fromarray((tile * 255 + 0.5).astype(np.uint8)).resize((1248, 832), Image.BICUBIC).save(folder / f'tile_{index:02d}.png')
            (folder / 'detail.json').write_text(json.dumps({'inputSha256': detail.digest(land), 'tileWidth': width,
                                                            'starts': starts, 'height': height}), encoding='utf-8')
            strip, scale = detail.assemble(land, 'magenta', folder)
            (folder / 'tile_01.png').unlink()
            with self.assertRaisesRegex(FileNotFoundError, r'\[1\]'):
                detail.assemble(land, 'magenta', folder)
        self.assertAlmostEqual(scale, 1248 / width, places=2)
        self.assertEqual(strip.shape[1], int(round(900 * 1248 / width)))
        expected = np.asarray(Image.fromarray((land * 255 + 0.5).astype(np.uint8)).resize(strip.shape[1::-1], Image.BICUBIC), np.float32) / 255
        self.assertLess(np.abs(strip[int(30 * scale):] - expected[int(30 * scale):]).mean(), 0.02)

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
        _, values = build.material_text('stm', profiles.DEN_DUSK, (-2.0, 15.0))
        early = renderer.render(values, (128, 64), time_ms=100000, fade=0.4)
        late = renderer.render(values, (128, 64), time_ms=160000, fade=0.4)
        self.assertGreater(np.abs(early - late).max(), 0.0)          # the clouds move
        self.assertTrue(np.allclose(early[..., 3], 0.4, atol=0.01))  # the engine's fade passes through


class LiveModule(unittest.TestCase):
    def test_the_live_scripts_take_the_srn_sky_rows_only(self):
        from tools.skykit import client_fixture
        enter, chat = client_fixture.live_scripts()
        self.assertIn('SetSkyBox(16,', enter)
        self.assertIn('row < 16 || row > 23', chat)
        self.assertEqual(set(client_fixture.SKY_ROWS), set(profiles.SKIES))
        for text in (enter, chat):
            self.assertEqual(text.count('{'), text.count('}'))

    def test_one_kind_of_module_at_a_time(self):
        import contextlib
        import io
        from tools.skykit import client_fixture
        for given in (['--live', '0'], ['--live', '256'], ['--live', '8', '--play'], ['--live', '8', '--transition']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                client_fixture.main(['--nwn-root', 'none', '--build-only', *given])

    def test_a_module_left_running_has_a_frame_limit(self):
        from unittest import mock
        from tools.armorkit import client
        from tools.skykit import client_fixture
        for given in (['--live', '8'], ['--play']):
            with tempfile.TemporaryDirectory() as temporary, mock.patch.object(client_fixture, 'build', return_value=(Path(temporary), 0)),                     mock.patch.object(client, 'start'), mock.patch.object(client_fixture.json, 'dumps', return_value=''), mock.patch('builtins.print'):
                client_fixture.main(['--nwn-root', 'none', *given])
                text = (Path(temporary) / 'settings.tml').read_text(encoding='utf-8')
            self.assertRegex(text, r'target-fps = [1-9]')
            self.assertEqual(text.count('[graphics.keyholing]'), 1)


if __name__ == '__main__':
    unittest.main()
