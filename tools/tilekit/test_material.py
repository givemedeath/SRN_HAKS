"""Restyled textures: reading the packs' pictures, the three routes, and the maps and material file written."""
import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
from PIL.ImageOps import flip

from . import material, pictures


def bioware(path, width, height, block):
    """A BioWare DDS of one DXT1 block repeated, its largest level only."""
    path.write_bytes(struct.pack('<IIIIf', width, height, 3, width * height // 2, 1.0) + block * (width // 4 * (height // 4)))


def scan(folder, size=32, metal=False):
    """A tiling scan as ambientCG lays one out: brick-like colour, flat relief, half roughness."""
    folder.mkdir(parents=True); name = folder.name; rng = np.random.default_rng(3)
    colour = np.uint8(rng.integers(100, 160, (size, size, 3))); Image.fromarray(colour).save(folder / f'{name}_1K-JPG_Color.png')
    Image.new('RGB', (size, size), (128, 128, 255)).save(folder / f'{name}_1K-JPG_NormalGL.png'); Image.new('RGB', (size, size), (128, 255, 128)).save(folder / f'{name}_1K-JPG_NormalDX.png')
    Image.new('L', (size, size), 128).save(folder / f'{name}_1K-JPG_Roughness.png')
    if metal:
        Image.new('L', (size, size), 255).save(folder / f'{name}_1K-JPG_Metalness.png')
    return colour


def fake_compress(image, target, mode, size, crunch, *, data):
    """Stands in for the compressor: a standard DDS header that states a whole mip chain, and what was asked."""
    width, height = size if isinstance(size, tuple) else (size, size); header = bytearray(128); header[:4] = b'DDS '
    struct.pack_into('<IIII', header, 12, height, width, 0, 0); struct.pack_into('<I', header, 28, max(width, height).bit_length())
    Path(target).write_bytes(bytes(header) + f'{mode} {(width, height)} {image.mode} {data}'.encode()); return Path(target)


class PictureTests(unittest.TestCase):
    def test_a_bioware_dds_is_decoded_top_row_first(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'two.dds'
            red, blue = struct.pack('<HHI', 0xF800, 0x001F, 0), struct.pack('<HHI', 0x001F, 0xF800, 0)  # colour 0 everywhere: all red, all blue
            path.write_bytes(struct.pack('<IIIIf', 4, 8, 3, 16, 1.0) + red + blue)  # stored bottom row first: red is the bottom block
            pixels = np.asarray(pictures.read(path))
            self.assertEqual(pixels.shape, (8, 4, 3)); self.assertEqual((tuple(pixels[0, 0]), tuple(pixels[7, 3])), ((0, 0, 255), (255, 0, 0)))
            (Path(folder) / 'bad.dds').write_bytes(b'\0' * 40)
            with self.assertRaisesRegex(ValueError, 'no BioWare DDS'):
                pictures.read(Path(folder) / 'bad.dds')

    def test_a_dxt1_block_gives_its_four_colours_and_a_dxt5_block_its_alpha(self):
        block = struct.pack('<HHI', 0xFFFF, 0x0000, 0b11_10_01_00)  # white, black, two thirds white, one third white in the first four pixels
        pixels = pictures.decode_dxt(block, 4, 4, False)
        self.assertEqual([int(pixels[0, x, 0]) for x in range(4)], [255, 0, 170, 85]); self.assertEqual(int(pixels[0, 0, 3]), 255)
        alpha = bytes([200, 100]) + (0b001_000).to_bytes(6, 'little')  # first pixel alpha 0 (200), second alpha 1 (100)
        pixels = pictures.decode_dxt(alpha + block, 4, 4, True)
        self.assertEqual((int(pixels[0, 0, 3]), int(pixels[0, 1, 3]), int(pixels[0, 0, 0])), (200, 100, 255))

    def test_relief_leans_away_from_a_rise_and_wraps_for_a_tiling_picture(self):
        height = np.zeros((8, 8)); height[:, 4:] = 1.0  # a step up to the right
        normal = pictures.relief(height, 2.0).astype(int)
        self.assertLess(normal[4, 4, 0], 100); self.assertGreater(normal[4, 0, 0], 156)  # the rise leans left; where it wraps back down, right
        self.assertEqual(tuple(normal[4, 2]), (128, 128, 255))
        up = np.zeros((8, 8)); up[:4] = 1.0  # higher toward the top of the picture
        self.assertLess(pictures.relief(up, 2.0, wrap=False).astype(int)[4, 4, 1], 100)  # +Y is up the picture: the slope faces down it

    def test_a_scan_takes_the_old_colour_and_a_tiling_picture_is_told_from_one_that_does_not(self):
        rng = np.random.default_rng(1); colour = np.uint8(rng.integers(90, 110, (16, 16, 3))); like = np.full((4, 4, 3), (200, 50, 50), np.uint8)
        moved = pictures.toned(colour, like)
        self.assertTrue(np.allclose(moved.reshape(-1, 3).mean(axis=0), (200, 50, 50), atol=3)); self.assertTrue(np.array_equal(pictures.toned(colour, like, 0.0), colour))
        ramp = np.dstack([np.tile(np.linspace(0, 255, 64), (64, 1))] * 3)
        self.assertGreater(pictures.offset_seams(ramp)[0], 20); self.assertLess(pictures.offset_seams(np.tile(colour, (2, 2, 1)))[0], 2)
        self.assertEqual((pictures.whole_chain(1024, 512), pictures.whole_chain(4, 4)), (11, 3))

    def test_a_grade_changes_every_pixel_alike(self):
        colour = np.zeros((2, 2, 3), np.uint8); colour[0, 0] = (200, 100, 50); colour[1, 1] = (200, 100, 50)
        self.assertTrue(np.array_equal(pictures.graded(colour, {}), colour))
        grey = pictures.graded(colour, {'saturation': 0.0})[0, 0]; self.assertEqual(len(set(int(value) for value in grey)), 1)
        made = pictures.graded(colour, {'gain': 0.5, 'tint': [1.0, 1.0, 2.0]})
        self.assertEqual((tuple(made[0, 0]), tuple(made[1, 1]), tuple(made[0, 1])), ((100, 50, 50), (100, 50, 50), (0, 0, 0)))
        self.assertGreater(int(pictures.graded(colour, {'contrast': 2.0})[0, 0, 0]), 200 - 1); self.assertEqual(int(pictures.graded(colour, {'contrast': 2.0})[0, 1, 1]), 0)
        lined = np.full((8, 8, 3), 90, np.uint8); lined[:, 3] = (230, 230, 230); lined[:, 5] = (200, 160, 20)  # asphalt, a white line and a yellow one
        spared = pictures.graded(lined, {'gain': 0.5, 'paint': 1.0}); self.assertEqual((tuple(spared[0, 0]), tuple(spared[0, 3]), tuple(spared[0, 5])), ((45, 45, 45), (230, 230, 230), (200, 160, 20)))
        with self.assertRaisesRegex(ValueError, 'A grade has no grime'):
            pictures.graded(colour, {'grime': 1})


    def test_stain_wraps_darkens_and_dulls_and_is_the_same_each_time(self):
        made = {'colour': np.full((128, 64, 3), 160, np.uint8), 'roughness': np.full((128, 64), 0.4)}
        one, two = pictures.stained(made, 'brick', 1.0), pictures.stained(made, 'brick', 1.0)
        self.assertTrue(np.array_equal(one['colour'], two['colour']))
        self.assertLess(one['colour'].mean(), 150); self.assertGreater(one['roughness'].mean(), 0.4)
        field = pictures.stain_field((128, 64), 0.3, 1)  # a tile's last row and column run on into its first
        self.assertLess(abs(field[0] - field[-1]).mean(), abs(field[0] - field[64]).mean())
        self.assertFalse(np.array_equal(pictures.stained(made, 'other', 1.0)['colour'], one['colour']))


    def test_wrapped_rows_run_on_from_bottom_to_top_and_keep_the_middle(self):
        picture = np.repeat(np.linspace(0, 255, 100)[:, None, None], 3, axis=2).astype(np.uint8) * np.ones((1, 8, 1), np.uint8)
        made = pictures.wrapped_rows(picture, band=0.1)
        self.assertLess(abs(int(made[0, 0, 0]) - int(made[-1, 0, 0])), 10); self.assertEqual(made[50, 0, 0], picture[50, 0, 0])


class MaterialTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup); self.root = Path(folder.name)
        self.scan_colour = scan(self.root / 'masters' / 'Brick1'); scan(self.root / 'masters' / 'Steel1', metal=True)
        (self.root / 'srn_t_common').mkdir(); Image.new('RGB', (16, 16), (50, 100, 150)).save(self.root / 'srn_t_common' / 'wall.tga')
        bioware(self.root / 'srn_t_common' / 'wall.dds', 16, 16, struct.pack('<HHI', 0xF800, 0xF800, 0))  # the DDS copy is red: it is what the game draws

    def test_a_master_tiles_the_scan_and_takes_the_old_colour(self):
        found = material.master(self.root / 'masters' / 'Brick1')
        self.assertEqual((found['colour'].shape, float(found['roughness'][0, 0]) > 0.49, float(found['metal'].max())), ((32, 32, 3), True, 0.0))
        self.assertEqual(tuple(found['normal'][0, 0]), (128, 128, 255))  # the +Y-up relief, not the other
        old = np.full((16, 16, 3), (180, 60, 40), np.uint8)
        made = material.make(old, {'route': 'master', 'repeat': 2, 'size': [64, 64]}, found)
        self.assertEqual((made['colour'].shape, made['normal'].shape, made['roughness'].shape), ((64, 64, 3), (64, 64, 3), (64, 64)))
        self.assertTrue(np.allclose(made['colour'].reshape(-1, 3).mean(axis=0), (180, 60, 40), atol=4))
        self.assertTrue(np.array_equal(made['colour'][:32, :32], made['colour'][32:, 32:]))  # two repeats of the scan each way
        self.assertEqual(float(material.master(self.root / 'masters' / 'Steel1')['metal'].min()), 1.0)
        wide = {'colour': np.zeros((4, 8, 3), np.uint8), 'normal': np.full((4, 8, 3), (200, 128, 255), np.uint8), 'roughness': np.zeros((4, 8)), 'metal': np.zeros((4, 8))}
        wide['colour'][:, :4] = 255  # a 2:1 scan, light on its left half, its relief leaning right
        lying = material.make(old, {'route': 'master', 'size': [64, 64], 'tone': 0.0}, wide)['colour']; self.assertEqual((int(lying[8, 8, 0]), int(lying[40, 8, 0]), int(lying[8, 40, 0])), (255, 255, 0))  # twice down, not stretched
        up = material.make(old, {'route': 'master', 'size': [64, 64], 'tone': 0.0, 'turn': True}, wide)
        self.assertEqual((int(up['colour'][56, 8, 0]), int(up['colour'][8, 8, 0]), abs(int(up['normal'][8, 8, 0]) - 128) <= 1 and int(up['normal'][8, 8, 1]) > 180), (255, 0, True))  # light now at the bottom, relief leaning up
        with self.assertRaisesRegex(ValueError, 'lacks a colour'):
            (self.root / 'masters' / 'Empty').mkdir(); material.master(self.root / 'masters' / 'Empty')
        for how, said in (({'route': 'paint', 'size': [64, 64]}, 'route is one of'), ({'route': 'master', 'size': [60, 64]}, 'size is two of'), ({'route': 'master', 'size': [64, 64]}, 'needs a scan')):
            with self.assertRaisesRegex(ValueError, said):
                material.make(old, how)

    def test_a_kept_layout_keeps_its_broad_shapes_and_an_upscale_its_picture(self):
        old = np.zeros((16, 16, 3), np.uint8); old[:, :8] = 200  # light on the left, dark on the right: the layout
        found = material.master(self.root / 'masters' / 'Brick1')
        made = material.make(old, {'route': 'layout', 'size': [64, 64], 'keep': 2}, found)
        self.assertGreater(made['colour'][:, 8:24].mean(), 150); self.assertLess(made['colour'][:, 40:56].mean(), 50)
        self.assertGreater(made['colour'][:, 8:24].std(), 3)  # with the scan's grain on it
        large = material.make(old, {'route': 'upscale', 'size': [64, 128], 'roughness': 0.4})
        self.assertEqual((large['colour'].shape, float(large['roughness'][0, 0]), float(large['metal'].max())), ((128, 64, 3), 0.4, 0.0))
        self.assertGreater(large['colour'][:, 4:24].mean(), 180)

    def test_the_maps_and_the_material_file_are_written_under_the_textures_name(self):
        spec = {'textures': {'wall': {'route': 'master', 'master': 'Brick1', 'size': [64, 128]},
                             'a_long_texture_g': {'route': 'upscale', 'size': [64, 64], 'stem': 'altg'}}}
        Image.new('RGB', (16, 16), (9, 9, 9)).save(self.root / 'srn_t_common' / 'a_long_texture_g.tga')
        told = material.build(spec, self.root, self.root / 'masters', self.root / 'out', 'crunch', compress=fake_compress)
        self.assertEqual(told['wall'], {'route': 'master', 'size': [64, 128], 'files': ['wall.dds', 'wall_n.dds', 'wall_s.dds', 'wall_r.dds', 'wall.mtr']})
        self.assertEqual(told['a_long_texture_g']['files'], ['altg.dds', 'altg_n.dds', 'altg_s.dds', 'altg_r.dds', 'a_long_texture_g.mtr'])
        self.assertEqual((self.root / 'out' / 'a_long_texture_g.mtr').read_text(),
                         'renderhint NormalAndSpecMapped\n\ntexture0 altg\ntexture1 altg_n\ntexture2 altg_s\ntexture3 altg_r\ntexture4 null\ntexture5 null\n')
        asked = lambda name: (self.root / 'out' / name).read_bytes()[128:].decode()
        self.assertEqual((asked('wall.dds'), asked('wall_n.dds'), asked('wall_r.dds')), ("-DXT1 (64, 128) RGB False", "-DXN (64, 64) RGB True", "-DXT5A (64, 64) RGBA True"))
        made = material.make(np.asarray(material.current(self.root, 'wall').convert('RGB')), spec['textures']['wall'], material.master(self.root / 'masters' / 'Brick1'))
        self.assertGreater(made['colour'][..., 0].mean(), 200); self.assertLess(made['colour'][..., 2].mean(), 30)  # toned to the DDS copy, the one the game draws
        dark = {'grades': {'dim': {'gain': 0.5}}, 'textures': {'wall': {**spec['textures']['wall'], 'grade': 'dim'}}}
        self.assertEqual(material.build(dark, self.root, self.root / 'masters', self.root / 'dim', 'crunch', compress=fake_compress)['wall']['grade'], 'dim')
        with self.assertRaisesRegex(ValueError, 'wall: the spec has no grade dim'):
            material.build({'textures': dark['textures']}, self.root, self.root / 'masters', self.root / 'dim', 'crunch', compress=fake_compress)
        with self.assertRaisesRegex(ValueError, 'Not in the spec: nope'):
            material.build(spec, self.root, self.root / 'masters', self.root / 'out', 'crunch', only=['nope'], compress=fake_compress)
        with self.assertRaisesRegex(ValueError, 'need a `stem`'):
            material.build({'textures': {'a_long_texture_g': {'route': 'upscale', 'size': [64, 64]}}}, self.root, self.root / 'masters', self.root / 'out', 'crunch', compress=fake_compress)
        with self.assertRaisesRegex(ValueError, 'No pack holds a picture of gone'):
            material.build({'textures': {'gone': {'route': 'upscale', 'size': [64, 64]}}}, self.root, self.root / 'masters', self.root / 'out', 'crunch', compress=fake_compress)

    def test_a_plain_texture_may_have_a_name_too_long_for_maps(self):
        self.assertEqual(material.stem_of('tfb01_floortran2', {'plain': True}), 'tfb01_floortran2')  # 15 or 16 letters: no map adds to them
        with self.assertRaises(ValueError):
            material.stem_of('tfb01_floortran2', {})

    def test_a_base_game_texture_is_read_from_stock_and_water_written_plain(self):
        (self.root / 'stock').mkdir(); Image.new('RGBA', (16, 16), (20, 40, 90, 255)).save(self.root / 'stock' / 'water.tga')
        with self.assertRaisesRegex(ValueError, 'needs --stock'):
            material.current(self.root, 'water')
        told = material.build({'textures': {'water': {'route': 'upscale', 'size': [64, 64], 'plain': True}}}, self.root, self.root / 'masters', self.root / 'out', 'crunch',
                              compress=fake_compress, stock=self.root / 'stock')
        self.assertEqual(told['water']['files'], ['water.dds']); self.assertFalse((self.root / 'out' / 'water.mtr').exists())

    def test_a_restyled_texture_is_read_as_it_was_at_the_spec_s_before_commit(self):
        import subprocess
        repo = self.root / 'repo'; pack = repo / 'srn_t_common'; pack.mkdir(parents=True)
        Image.new('RGB', (8, 8), (200, 10, 10)).save(pack / 'wall.tga'); Image.new('RGB', (8, 8), (9, 9, 9)).save(pack / 'Brick.TGA')
        git = lambda *words: subprocess.run(['git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@t', *words], check=True, capture_output=True, text=True).stdout.strip()
        git('init', '-q'); git('add', '-A'); git('commit', '-q', '-m', 'old'); before = git('rev-parse', 'HEAD')
        (pack / 'wall.tga').unlink(); (pack / 'wall.mtr').write_text('texture0 wall\n', encoding='ascii')
        Image.new('RGB', (8, 8), (10, 10, 200)).save(pack / 'wall.png')  # what a restyle leaves is not the old picture
        with self.assertRaisesRegex(ValueError, 'restyled already'):
            material.current(repo, 'wall')
        self.assertEqual(material.current(repo, 'wall', before=before).getpixel((0, 0)), (200, 10, 10))
        (pack / 'Brick.TGA').unlink(); (pack / 'brick.mtr').write_text('texture0 brick\n', encoding='ascii')
        self.assertEqual(material.current(repo, 'brick', before=before).getpixel((0, 0)), (9, 9, 9))  # as the pack spelled it
        Image.new('RGB', (8, 8), (10, 200, 10)).save(pack / 'added.tga')  # a texture new since `before` is read as it is
        self.assertEqual(material.current(repo, 'added', before=before).getpixel((0, 0)), (10, 200, 10))
        (pack / 'water.dds').write_bytes(b'DDS ' + bytes(124))  # a plain restyle has no material: a standard DDS is one
        with self.assertRaisesRegex(ValueError, 'water is restyled already'):
            material.current(repo, 'water', before=before)
        git('add', '-A'); git('commit', '-q', '-m', 'restyled'); late = git('rev-parse', 'HEAD')  # a `before` after the restyle holds no originals
        for name in ('wall', 'water'):
            with self.assertRaisesRegex(ValueError, f'{name} is restyled already at {late}'):
                material.current(repo, name, before=late)
        upright = Image.new('RGB', (8, 8), (30, 60, 90)); upright.putpixel((0, 7), (1, 2, 3))  # bottom-left as the game shows it
        flip(upright).save(pack / 'water.dds')  # an approved plain restyle a new one builds over, its first row the bottom
        git('add', '-A'); git('commit', '-q', '-m', 'redrawn'); redrawn = git('rev-parse', 'HEAD')
        self.assertEqual(material.current(repo, 'water', before=redrawn, over=True).getpixel((0, 0))[:3], (30, 60, 90))
        self.assertEqual(material.current(repo, 'water', over=True).getpixel((0, 0))[:3], (30, 60, 90))
        self.assertEqual(material.current(repo, 'water', before=redrawn, over=True).getpixel((0, 7))[:3], (1, 2, 3))  # turned upright
        self.assertEqual(material.current(repo, 'water', over=True).getpixel((0, 7))[:3], (1, 2, 3))
        with self.assertRaisesRegex(ValueError, 'wall is restyled already'):  # over never takes a material's maps
            material.current(repo, 'wall', before=redrawn, over=True)

    def test_a_redrawn_or_enlarged_picture_is_taken_only_as_its_record_says_it_was_made(self):
        import hashlib, json
        old = np.zeros((4, 4, 3), np.uint8); sha = lambda picture: hashlib.sha256(repr(picture.shape).encode() + picture.tobytes()).hexdigest()
        folder = self.root / 'made'; folder.mkdir(); (folder / 'day.png').write_bytes(b'day picture')
        material._derived(folder, 'hand', old)  # no record: placed by hand, taken as it is
        record = lambda name, **values: (folder / f'{name}.json').write_text(json.dumps(values), encoding='utf-8')
        record('lit', source=sha(old), of='day', day=hashlib.sha256(b'day picture').hexdigest()); material._derived(folder, 'lit', old)
        record('other', source=sha(old + 1))
        with self.assertRaisesRegex(ValueError, 'made from another picture than the one the spec starts from'):
            material._derived(folder, 'other', old)
        (folder / 'day.png').write_bytes(b'day redrawn again')
        with self.assertRaisesRegex(ValueError, 'made from another day day picture'):
            material._derived(folder, 'lit', old)
        record('big', source=sha(old), doubled=1, upscaler='RealESRGAN_x2plus.pth'); material._derived(folder, 'big', old, doubled=1)
        with self.assertRaisesRegex(ValueError, 'another enlargement than 2 times'):
            material._derived(folder, 'big', old, doubled=2)

    def test_the_wrapped_blur_is_a_box_blur_that_wraps(self):
        values = np.random.default_rng(3).random((9, 13))
        slow = values.copy()
        for axis in (0, 1):
            slow = sum(np.roll(slow, shift, axis=axis) for shift in range(-3, 4)) / 7
        self.assertTrue(np.allclose(pictures._wrapped_blur(values, 3), slow))

    def test_a_crisp_cut_out_has_a_steeper_edge(self):
        holed = np.zeros((16, 16, 4), np.uint8); holed[:, :8] = 255
        soft = material.make(holed, {'route': 'upscale', 'size': [64, 64]})['alpha']; hard = material.make(holed, {'route': 'upscale', 'size': [64, 64], 'crisp': 4})['alpha']
        self.assertLess(int(((hard > 10) & (hard < 245)).sum()), int(((soft > 10) & (soft < 245)).sum()))

    def test_every_map_is_stored_bottom_row_first(self):
        made = material.make(np.zeros((16, 16, 3), np.uint8), {'route': 'upscale', 'size': [64, 64]}); made['colour'] = made['colour'].copy(); made['colour'][:8] = (255, 0, 0)  # red along the top
        seen = {}

        def keep(image, target, mode, size, crunch, *, data):
            seen[Path(target).name] = np.asarray(image.convert('RGB')); return fake_compress(image, target, mode, size, crunch, data=data)
        material.write('wall', made, self.root / 'turned', 'crunch', compress=keep)
        self.assertEqual((tuple(seen['wall.dds'][0, 0]), tuple(seen['wall.dds'][-1, 0])), ((0, 0, 0), (255, 0, 0)))

    def test_a_map_without_its_mip_chain_is_refused_and_a_glow_is_named(self):
        made = material.make(np.zeros((16, 16, 3), np.uint8), {'route': 'upscale', 'size': [64, 64]})

        def top_only(image, target, mode, size, crunch, *, data):
            path = fake_compress(image, target, mode, size, crunch, data=data); raw = bytearray(path.read_bytes()); struct.pack_into('<I', raw, 28, 1); path.write_bytes(bytes(raw)); return path
        with self.assertRaisesRegex(ValueError, 'without its mip chain'):
            material.write('wall', made, self.root / 'bad', 'crunch', compress=top_only)
        files = material.write('wall', made, self.root / 'lit', 'crunch', glow=np.zeros((64, 64, 3), np.uint8), compress=fake_compress)
        self.assertIn('wall_i.dds', files); self.assertIn('texture5 wall_i\n', (self.root / 'lit' / 'wall.mtr').read_text())
        holed = np.zeros((16, 16, 4), np.uint8); holed[:, :8] = (200, 220, 240, 255)  # lit windows on the left, a hole on the right
        lit = material.make(holed, {'route': 'upscale', 'size': [64, 64], 'glow': {'gain': 0.5, 'tint': [1.0, 1.0, 2.0]}})
        self.assertEqual((int(lit['alpha'][8, 8]), int(lit['alpha'][8, 56])), (255, 0))
        self.assertEqual((tuple(int(value) for value in lit['glow'][8, 8]), tuple(int(value) for value in lit['glow'][8, 56])), ((100, 110, 240), (0, 0, 0)))
        files = material.write('panes_g', lit, self.root / 'panes', 'crunch', compress=fake_compress)
        self.assertIn('panes_g_i.dds', files); self.assertTrue((self.root / 'panes' / 'panes_g.dds').read_bytes()[128:].startswith(b'-DXT5 (64, 64) RGBA'))
        self.assertNotIn('alpha', made); self.assertNotIn('glow', made)
        with self.assertRaisesRegex(ValueError, 'A glow has no colour'):
            material.make(holed, {'route': 'upscale', 'size': [64, 64], 'glow': {'colour': 1}})
        self.assertAlmostEqual(float(material.shine(np.full((1, 1, 3), 255, np.uint8), np.array([[1.0]]))[0, 0]), 1.0)
        self.assertAlmostEqual(float(material.shine(np.full((1, 1, 3), 255, np.uint8), np.array([[0.0]]))[0, 0]), 0.04)


if __name__ == '__main__':
    unittest.main()
