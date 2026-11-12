"""Parts are written in their bone's space with their normals, one tint texture each, and compiled by the pinned tool."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from . import export, seams

SQUARE = (np.array([(0, 0, 1.0), (1, 0, 1), (1, 1, 1), (0, 1, 1)]), np.array([(0, 1, 2), (0, 2, 3)]),
          np.array([(0, 0.0), (1, 0), (1, 1), (0, 1)]), np.tile((0.0, 0, 1), (4, 1)))
TEXTURE = (np.full((2, 4), 200), np.full((2, 4), export.LAYERS['cloth1']))


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

    def test_vertices_repeated_at_one_position_share_a_normal(self):
        # two faces folded along the edge (0,0,0)-(1,1,0); the second has its own copies of the edge's vertices
        vertices = np.array([(0, 0, 0.0), (1, 0, 0), (1, 1, 0), (0, 0, 0), (1, 1, 0), (0, 1, 1)])
        normals = export.vertex_normals(vertices, np.array([(0, 1, 2), (3, 4, 5)]))
        self.assertTrue(np.allclose(normals[0], normals[3]) and np.allclose(normals[2], normals[4]))
        self.assertFalse(np.allclose(normals[0], normals[1]))  # the fold's normal is not the flat face's
        self.assertTrue(np.allclose(np.linalg.norm(normals, axis=1), 1))

    def test_sheets_lying_back_to_back_keep_a_normal_each(self):
        vertices = np.concatenate([SQUARE[0][:3], SQUARE[0][:3]])  # the same triangle twice, with its own vertices each time
        normals = export.vertex_normals(vertices, np.array([(0, 1, 2), (3, 5, 4)]))
        self.assertTrue(np.allclose(normals[:3], (0, 0, 1)) and np.allclose(normals[3:], (0, 0, -1)))

    def test_faces_the_split_added_are_lit_as_surfaces_of_their_own(self):
        # a tube along z, eight sides and one ring of faces, closed at its top by a fan from a middle of its own per rim vertex
        angles = np.arange(8) * np.pi / 4
        ring = np.stack([np.cos(angles), np.sin(angles), np.zeros(8)], axis=1)
        vertices = np.concatenate([ring, ring + (0, 0, 1), np.tile((0.0, 0, 1), (8, 1))])  # bottom, top, the fan's middle
        own = [face for i in range(8) for face in ([i, (i + 1) % 8, 8 + i], [(i + 1) % 8, 8 + (i + 1) % 8, 8 + i])]
        fan = [[16 + i, 8 + i, 8 + (i + 1) % 8] for i in range(8)]
        faces, added = np.array(own + fan), np.arange(24) >= 16
        carried = np.concatenate([ring, ring, ring])  # as the split leaves them: every vertex has its edge's normal, straight out
        uvs = np.arange(48.0).reshape(24, 2)
        v, f, n, t = export.added_normals(vertices, faces, added, carried, uvs)
        # the outfit's own faces keep their vertices and normals; the fan has vertices of its own, those on the edge repeated
        self.assertTrue(np.array_equal(f[~added], faces[~added]))
        self.assertTrue(np.array_equal(v[:24], vertices) and np.array_equal(n[:16], carried[:16]) and np.array_equal(t[:24], uvs))
        self.assertEqual(len(v), 24 + 8)
        self.assertFalse(np.isin(f[added], f[~added]).any())
        self.assertTrue(np.allclose(v[f[added]], vertices[faces[added]]))  # the same surface
        self.assertTrue(np.allclose(t[f[added]], uvs[faces[added]]))
        # and it is lit along its own facing, evenly: the edge is a crease
        self.assertTrue(np.allclose(n[np.unique(f[added])], (0, 0, 1)))
        self.assertTrue(np.allclose(np.linalg.norm(n, axis=1), 1.0))
        # a cap rounds the surface on past its edge: it keeps the edge's vertices and their normals, and its own are lit by its faces
        v, f, n = export.added_normals(vertices, faces, added, carried, domed=added)
        self.assertTrue(np.array_equal(f, faces) and np.array_equal(v, vertices))
        self.assertTrue(np.array_equal(n[:16], carried[:16]) and np.allclose(n[16:], (0, 0, 1)))
        # a part with a cap and a closing: only the closing's edge is a crease
        for flags in (True, added[:1], added[:-1]):  # not one flag per face: refused, not spread over the faces
            with self.assertRaises(ValueError):
                export.added_normals(vertices, faces, added, carried, domed=flags)
        v, f, n = export.added_normals(vertices, faces, added, carried, domed=np.arange(24) >= 20)
        self.assertEqual(len(v), 24 + 5)  # the four closing faces' five vertices on the rim
        self.assertTrue(np.array_equal(f[~added], faces[~added]) and np.array_equal(f[20:], faces[20:]))
        self.assertFalse(np.isin(f[16:20], f[~added]).any())
        self.assertTrue(np.allclose(n[np.unique(f[16:20])], (0, 0, 1)) and np.array_equal(n[:16], carried[:16]))
        # a part with nothing added is left as it is
        v, f, n = export.added_normals(vertices[:16], faces[:16], np.zeros(16, bool), carried[:16])
        self.assertTrue(np.array_equal(v, vertices[:16]) and np.array_equal(f, faces[:16]) and np.array_equal(n, carried[:16]))
        for flags, normals in ((added[:-1], carried), (added, carried[:-1])):
            with self.assertRaises(ValueError):
                export.added_normals(vertices, faces, flags, normals)

    def test_points_and_normals_are_taken_into_the_bones_space(self):
        bone = np.array([[0.0, -1, 0, 2], [1, 0, 0, 3], [0, 0, 1, 4], [0, 0, 0, 1]])  # a quarter turn about z, then moved
        local = np.array([(1.0, 0, 0), (0, 2, 0), (0, 0, 3)])
        world = local @ bone[:3, :3].T + bone[:3, 3]
        self.assertTrue(np.allclose(export.to_bone(world, bone), local))
        self.assertTrue(np.allclose(export.to_bone(local @ bone[:3, :3].T, bone, direction=True), local / np.linalg.norm(local, axis=1)[:, None]))
        scaled = bone.copy(); scaled[:3, :3] *= 2.0  # a scaled bone still gives unit normals
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
        broken = vertices.copy(); broken[0, 0] = np.nan
        for arguments in (('pmh0_chest6030', vertices, faces[:0], uvs, normals), ('pmh0_chest6030', vertices, faces + 2, uvs, normals),
                          ('pmh0_chest6030', vertices, faces, uvs[:3], normals), ('pmh0_chest6030', vertices, faces, uvs, normals[:, :2]),
                          ('pmh0_chest6030', broken, faces, uvs, normals), ('pmh0_chest6030', vertices, faces, uvs, np.full_like(normals, np.inf)),
                          ('a_name_that_is_too_long', vertices, faces, uvs, normals), ('PMH0_chest001', vertices, faces, uvs, normals)):
            with self.assertRaises(ValueError):
                export.model_text(*arguments)

    def test_a_part_is_written_in_its_bones_space_with_its_tint_texture(self):
        vertices = SQUARE[0]
        bone = np.eye(4); bone[:3, 3] = (0.5, 0.25, 1.0)
        with tempfile.TemporaryDirectory() as folder:
            name = export.write_part(folder, 'pmh0', 'bicepl', 6030, SQUARE, {seams.BONES['bicepl']: bone}, TEXTURE)
            self.assertEqual(name, 'pmh0_bicepl6030')
            text = (Path(folder) / 'pmh0_bicepl6030.mdl').read_text(encoding='cp1252')
            self.assertTrue(np.allclose(block(text, 'verts'), vertices - bone[:3, 3]))
            shades, layers = export.read_tint((Path(folder) / 'pmh0_bicepl6030.plt').read_bytes())
            self.assertTrue(np.array_equal(shades, TEXTURE[0]) and np.array_equal(layers, TEXTURE[1]))
            mirrored = np.diag((-1.0, 1, 1, 1))
            with self.assertRaisesRegex(ValueError, 'mirrored bone'):
                export.write_part(folder, 'pmh0', 'bicepr', 6030, SQUARE, {seams.BONES['bicepr']: mirrored}, TEXTURE)


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
    """The tool is faked: it writes a file per source and reports as cleanmodels does with --json."""

    def compile(self, names=('a', 'b'), returncode=0, write=True, errors=(), faces=2, noise='', stale=()):
        calls = []

        def fake(command, **options):
            calls.append(command)
            inputs = [Path(argument) for argument in command if argument.endswith('.mdl') and Path(argument).parent.name == 'ascii']
            for source in inputs if write else ():
                (self.out / source.name).write_bytes(b'binary')
            report = [{'file': str(source), **({'error': 'no newmodel line'} if source.stem in errors else {'actions': ['compiled']})} for source in inputs]
            return subprocess.CompletedProcess(command, returncode, stdout=noise + json.dumps(report[0] if len(report) == 1 else report), stderr='the tool said so')
        with tempfile.TemporaryDirectory() as folder:
            source, self.out = Path(folder) / 'ascii', Path(folder) / 'out'
            source.mkdir(); self.out.mkdir()
            for name in names:
                (source / (name + '.mdl')).write_text('node trimesh x\n  faces 2\n    0 1 2 1 0 1 2 1\n    0 2 3 1 0 2 3 1\n', encoding='cp1252')
            (source / 'a.plt').write_bytes(b'tint')
            for name in stale:
                (self.out / name).write_bytes(b'left by an earlier run')
            with mock.patch.object(export.subprocess, 'run', side_effect=fake), \
                    mock.patch.object(export.native_reader, 'decode', return_value=[{'faces': np.zeros((faces, 3), int)}]):
                compiled = export.compile_models([source / (name + '.mdl') for name in names], self.out, tool={'path': 'cleanmodels'},
                                                 game='game', resources=['packs', 'more'])
            return calls, [path.relative_to(folder).as_posix() for path in compiled], sorted(path.name for path in self.out.iterdir())

    def test_all_models_go_to_the_tool_in_one_call_and_their_textures_come_along(self):
        calls, compiled, written = self.compile(stale=('b.plt',))
        self.assertEqual(compiled, ['out/a.mdl', 'out/b.mdl'])
        self.assertEqual(written, ['a.mdl', 'a.plt', 'b.mdl'])  # only a has a texture beside it; b's old one is gone
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][:9], ['cleanmodels', 'compile', '--overwrite', '--json', '--game-dir', 'game', '--resource-dir', 'packs', '--resource-dir'])
        self.assertTrue(calls[0][-3].endswith('a.mdl') and calls[0][-2].endswith('b.mdl') and Path(calls[0][-1]).name == 'out')

    def test_one_model_names_its_output_file_and_words_before_the_report_are_passed_over(self):
        calls, compiled, _ = self.compile(names=('a',), noise='note: no install found\n')
        self.assertEqual(compiled, ['out/a.mdl'])
        self.assertTrue(Path(calls[0][-2]).parent.name == 'ascii' and Path(calls[0][-1]).parts[-2:] == ('out', 'a.mdl'))

    def test_a_model_that_did_not_come_out_whole_raises_with_the_tools_words(self):
        with self.assertRaisesRegex(ValueError, 'The models did not compile: .*the tool said so'):
            self.compile(returncode=1)
        with self.assertRaisesRegex(ValueError, '^b.mdl did not compile: no newmodel line$'):
            self.compile(errors=('b',))
        with self.assertRaisesRegex(ValueError, 'a.mdl did not compile'):
            self.compile(write=False, stale=('a.mdl', 'b.mdl'))  # an earlier run's models do not stand in
        with self.assertRaisesRegex(ValueError, 'a.mdl compiled to 1 faces, not the 2 of its source'):
            self.compile(faces=1)

    def test_many_models_go_to_the_tool_a_batch_at_a_time(self):
        with mock.patch.object(export, 'BATCH', 2):
            calls, compiled, _ = self.compile(names=('a', 'b', 'c'))
        self.assertEqual(compiled, ['out/a.mdl', 'out/b.mdl', 'out/c.mdl'])
        self.assertEqual([sum(argument.endswith('.mdl') and Path(argument).parent.name == 'ascii' for argument in call) for call in calls], [2, 1])
        self.assertTrue(Path(calls[0][-1]).name == 'out' and Path(calls[1][-1]).parts[-2:] == ('out', 'c.mdl'))

    def test_the_report_is_found_after_notes_that_hold_brackets(self):
        said = '\n'.join(['note: looked in {game}', '[1/2] a.mdl ok', '[{"file": "a.mdl"}, 7]', '1 file'])
        self.assertEqual(export.report(said), [{'file': 'a.mdl'}])
        self.assertEqual(export.report('{"file": "a.mdl", "error": "bad"}'), [{'file': 'a.mdl', 'error': 'bad'}])
        self.assertEqual(export.report('nothing to read'), [])

    def test_sources_are_never_compiled_in_place_and_no_sources_need_no_tool(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(export.subprocess, 'run') as run, \
                mock.patch.object(export.toolchain, 'cleanmodels') as pinned:
            self.assertEqual(export.compile_models([], folder), [])
            with self.assertRaisesRegex(ValueError, 'other than the sources'):
                export.compile_models([Path(folder) / 'a.mdl'], folder, tool={'path': 'cleanmodels'})
            with self.assertRaisesRegex(ValueError, 'share a name'):
                export.compile_models([Path(folder) / 'x' / 'a.mdl', Path(folder) / 'y' / 'a.mdl'], folder, tool={'path': 'cleanmodels'})
        run.assert_not_called()
        pinned.assert_not_called()

    def test_the_pinned_tool_is_used_when_none_is_given(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(export.toolchain, 'cleanmodels', return_value={'path': 'pinned'}) as pinned, \
                mock.patch.object(export.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, stdout='', stderr='no')) as run:
            with self.assertRaises(ValueError):
                export.compile_models([Path(folder) / 'ascii' / 'x.mdl'], Path(folder) / 'new' / 'out')
            self.assertTrue((Path(folder) / 'new' / 'out').is_dir())  # a missing output folder is made
            self.assertEqual(run.call_args.args[0][0], 'pinned')
        pinned.assert_called_once_with()

    def test_written_parts_compile_with_the_pinned_tool_where_it_is_installed(self):
        try:
            tool = export.toolchain.cleanmodels()
        except ValueError as error:
            self.skipTest(str(error)[:80])
        rig = {seams.BONES[token]: np.eye(4) for token in ('chest', 'bicepl')}
        with tempfile.TemporaryDirectory() as folder:
            source, out = Path(folder) / 'ascii', Path(folder) / 'out'
            source.mkdir(); out.mkdir()
            names = [export.write_part(source, 'pmh0', 'chest', 300, SQUARE, rig, TEXTURE),
                     export.write_part(source, 'pmh0', 'bicepl', 65535, SQUARE, rig, TEXTURE)]  # the longest name a part can have
            self.assertEqual(len(names[1]), 16)
            compiled = export.compile_models([source / (name + '.mdl') for name in names], out, tool=tool)
            self.assertEqual(sorted(path.name for path in out.iterdir()), sorted(name + suffix for name in names for suffix in ('.mdl', '.plt')))
            for path in compiled:
                self.assertNotEqual(path.read_bytes()[:1], b'#')  # binary, not the ASCII source
            self.assertEqual(export.compile_models([source / (names[0] + '.mdl')], out, tool=tool), [out / (names[0] + '.mdl')])
            text = (source / (names[0] + '.mdl')).read_text(encoding='cp1252')
            (source / (names[0] + '.mdl')).write_text(text[:text.index('  verts')], encoding='cp1252')  # cut short: no mesh data
            with self.assertRaises(ValueError):
                export.compile_models([source / (names[0] + '.mdl')], out, tool=tool)


if __name__ == '__main__':
    unittest.main()
