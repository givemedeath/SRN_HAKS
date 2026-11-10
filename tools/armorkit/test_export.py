"""Parts are written in their bone's space with their normals, one tint texture each, and compiled by the pinned tool."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from . import export, seams

SQUARE = (np.array([(0, 0, 1.0), (1, 0, 1), (1, 1, 1), (0, 1, 1)]), np.array([(0, 1, 2), (0, 2, 3)]),
          np.array([(0, 0.0), (1, 0), (1, 1), (0, 1)]), np.tile((0.0, 0, 1), (4, 1)))


def block(text, keyword):
    """The rows of numbers under a `keyword count` line of an ASCII model."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.split()[:1] == [keyword])
    count = int(lines[start].split()[1])
    return np.array([[float(x) for x in line.split()] for line in lines[start + 1:start + 1 + count]])


class GeometryTests(unittest.TestCase):
    def test_vertex_normals_follow_the_faces_and_are_unit(self):
        vertices, faces = SQUARE[:2]
        self.assertTrue(np.allclose(export.vertex_normals(vertices, faces), (0, 0, 1)))
        self.assertTrue(np.allclose(export.vertex_normals(vertices, faces[:, ::-1]), (0, 0, -1)))
        loose = np.concatenate([vertices, [(5.0, 5, 5)]])  # a vertex no face uses still gets a unit normal
        self.assertTrue(np.allclose(np.linalg.norm(export.vertex_normals(loose, faces), axis=1), 1))

    def test_points_and_directions_are_taken_into_the_bones_space(self):
        bone = np.array([[0.0, -1, 0, 2], [1, 0, 0, 3], [0, 0, 1, 4], [0, 0, 0, 1]])  # a quarter turn about z, then moved
        local = np.array([(1.0, 0, 0), (0, 2, 0), (0, 0, 3)])
        world = local @ bone[:3, :3].T + bone[:3, 3]
        self.assertTrue(np.allclose(export.to_bone(world, bone), local))
        self.assertTrue(np.allclose(export.to_bone(local @ bone[:3, :3].T, bone, direction=True), local / np.linalg.norm(local, axis=1)[:, None]))
        scaled = bone.copy(); scaled[:3, :3] *= 2.0  # a scaled bone still gives unit directions
        self.assertTrue(np.allclose(np.linalg.norm(export.to_bone(local, scaled, direction=True), axis=1), 1))
        self.assertTrue(np.allclose(export.to_bone(local @ scaled[:3, :3].T + scaled[:3, 3], scaled), local))


class ModelTests(unittest.TestCase):
    def test_a_model_names_its_own_texture_and_carries_every_block(self):
        vertices, faces, uvs, normals = SQUARE
        text = export.model_text('pmh0_chest6030', vertices, faces, uvs, normals)
        lines = [line.strip() for line in text.splitlines()]
        for wanted in ('newmodel pmh0_chest6030', 'classification CHARACTER', 'node dummy pmh0_chest6030', 'node trimesh pmh0_chest6030g',
                       'parent pmh0_chest6030', 'bitmap pmh0_chest6030', 'shadow 1', 'donemodel pmh0_chest6030'):
            self.assertIn(wanted, lines)
        self.assertTrue(np.allclose(block(text, 'verts'), vertices))
        self.assertTrue(np.allclose(block(text, 'normals'), normals))
        self.assertTrue(np.allclose(block(text, 'tverts')[:, :2], uvs))
        rows = block(text, 'faces')
        self.assertTrue(np.array_equal(rows[:, :3], faces) and np.array_equal(rows[:, 4:7], faces))  # texture corners follow the vertices

    def test_a_model_that_cannot_be_drawn_is_refused(self):
        vertices, faces, uvs, normals = SQUARE
        for arguments in (('pmh0_chest6030', vertices, faces[:0], uvs, normals), ('pmh0_chest6030', vertices, faces + 2, uvs, normals),
                          ('pmh0_chest6030', vertices, faces, uvs[:3], normals), ('pmh0_chest6030', vertices, faces, uvs, normals[:, :2]),
                          ('a_name_that_is_too_long', vertices, faces, uvs, normals), ('PMH0_chest001', vertices, faces, uvs, normals)):
            with self.assertRaises(ValueError):
                export.model_text(*arguments)

    def test_a_part_is_written_in_its_bones_space_with_its_tint_texture(self):
        vertices, faces, uvs, normals = SQUARE
        bone = np.eye(4); bone[:3, 3] = (0.5, 0.25, 1.0)
        texture = (np.full((2, 4), 200), np.full((2, 4), export.LAYERS['cloth1']))
        with tempfile.TemporaryDirectory() as folder:
            name = export.write_part(folder, 'pmh0', 'bicepl', 6030, SQUARE, {seams.BONES['bicepl']: bone}, texture)
            self.assertEqual(name, 'pmh0_bicepl6030')
            text = (Path(folder) / 'pmh0_bicepl6030.mdl').read_text(encoding='cp1252')
            self.assertTrue(np.allclose(block(text, 'verts'), vertices - bone[:3, 3]))
            shades, layers = export.read_tint((Path(folder) / 'pmh0_bicepl6030.plt').read_bytes())
            self.assertTrue(np.array_equal(shades, texture[0]) and np.array_equal(layers, texture[1]))


class TintTests(unittest.TestCase):
    def test_a_tint_texture_reads_back_as_written_row_by_row(self):
        shades = np.arange(12).reshape(3, 4) * 20
        layers = np.array([[export.LAYERS['cloth1']] * 4, [export.LAYERS['metal1']] * 4, [export.LAYERS['skin']] * 4])
        blob = export.tint(shades, layers)
        self.assertEqual((blob[:8], len(blob)), (b'PLT V1  ', 24 + 2 * 12))
        self.assertEqual((int.from_bytes(blob[16:20], 'little'), int.from_bytes(blob[20:24], 'little')), (4, 3))  # width, then height
        self.assertEqual(blob[24:26], bytes([0, export.LAYERS['cloth1']]))  # the first pixel given is the first stored
        back = export.read_tint(blob)
        self.assertTrue(np.array_equal(back[0], shades) and np.array_equal(back[1], layers))

    def test_every_registry_channel_has_a_layer_and_others_are_refused(self):
        from . import registry
        self.assertEqual(set(export.LAYERS), set(registry.CHANNELS))
        self.assertEqual(len(set(export.LAYERS.values())), len(export.LAYERS))
        with self.assertRaisesRegex(ValueError, 'layers'):
            export.tint(np.full((2, 2), 100), np.full((2, 2), 1))  # hair is not an armor channel
        with self.assertRaisesRegex(ValueError, 'layers'):
            export.tint(np.full((2, 2), 300), np.full((2, 2), 4))
        with self.assertRaisesRegex(ValueError, 'per pixel'):
            export.tint(np.full((2, 2), 100), np.full((2, 3), 4))
        with self.assertRaisesRegex(ValueError, 'cut short'):
            export.read_tint(export.tint(np.full((2, 2), 100), np.full((2, 2), 4))[:-1])


class CompileTests(unittest.TestCase):
    def run_with(self, returncode, write=True):
        calls = []

        def fake(command, **options):
            calls.append(command)
            if write:
                Path(command[-1]).write_bytes(b'binary')
            return subprocess.CompletedProcess(command, returncode, stdout='', stderr='reading the model failed')
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(export.subprocess, 'run', side_effect=fake):
            sources = [Path(folder) / 'a.mdl', Path(folder) / 'b.mdl']
            out = Path(folder) / 'out'; out.mkdir()
            compiled = export.compile_models(sources, out, tool={'path': 'cleanmodels'}, game='game', resources=['packs', 'more'])
            return calls, [path.relative_to(folder).as_posix() for path in compiled]

    def test_each_model_is_compiled_by_the_given_tool_into_the_output_folder(self):
        calls, compiled = self.run_with(0)
        self.assertEqual(compiled, ['out/a.mdl', 'out/b.mdl'])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][:8], ['cleanmodels', 'compile', '--overwrite', '--game-dir', 'game', '--resource-dir', 'packs', '--resource-dir'])
        self.assertTrue(calls[0][-2].endswith('a.mdl') and calls[0][-1].endswith('a.mdl') and calls[0][-2] != calls[0][-1])

    def test_a_failed_or_empty_compile_raises_with_the_tools_words(self):
        with self.assertRaisesRegex(ValueError, 'a.mdl did not compile: reading the model failed'):
            self.run_with(1)
        with self.assertRaisesRegex(ValueError, 'a.mdl did not compile'):
            self.run_with(0, write=False)

    def test_the_pinned_tool_is_used_when_none_is_given(self):
        with mock.patch.object(export.toolchain, 'cleanmodels', return_value={'path': 'pinned'}) as pinned, \
                mock.patch.object(export.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, stdout='', stderr='no')):
            with self.assertRaises(ValueError):
                export.compile_models(['x.mdl'], 'out')
        pinned.assert_called_once_with()

    def test_a_written_part_compiles_with_the_pinned_tool_where_it_is_installed(self):
        try:
            tool = export.toolchain.cleanmodels()
        except ValueError as error:
            self.skipTest(str(error)[:80])
        bone = np.eye(4)
        with tempfile.TemporaryDirectory() as folder:
            source, out = Path(folder) / 'ascii', Path(folder) / 'out'
            source.mkdir(); out.mkdir()
            name = export.write_part(source, 'pmh0', 'chest', 300, SQUARE, {seams.BONES['chest']: bone},
                                     (np.full((2, 2), 200), np.full((2, 2), export.LAYERS['cloth1'])))
            compiled = export.compile_models([source / (name + '.mdl')], out, tool=tool)
            self.assertGreater(compiled[0].stat().st_size, 100)
            self.assertNotEqual(compiled[0].read_bytes()[:1], b'#')  # binary, not the ASCII source


if __name__ == '__main__':
    unittest.main()
