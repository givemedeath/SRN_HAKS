"""The local job is one connected graph from a cut-out reference to a textured model at its triangle target."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

from . import fresh, local

IMAGING = importlib.util.find_spec('PIL') is not None and importlib.util.find_spec('numpy') is not None


class FreshFolderTests(unittest.TestCase):
    def test_a_folder_appears_only_when_its_work_finished_and_a_failure_does_not_block_the_retry(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / 'made'
            with self.assertRaisesRegex(ValueError, 'no roughness'):
                with fresh(target) as staging:
                    (staging / 'model.glb').write_bytes(b'x')
                    raise ValueError('no roughness map')
            self.assertFalse(target.exists())
            with fresh(target) as staging:  # the retry starts clean: the first attempt's file is gone
                self.assertEqual(list(staging.iterdir()), []); (staging / 'report.json').write_text('{}', encoding='utf-8')
            self.assertEqual([path.name for path in Path(root).iterdir()], ['made']); self.assertTrue((target / 'report.json').is_file())
            with self.assertRaisesRegex(ValueError, 'fresh folder'):
                with fresh(target):
                    pass


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.graph = local.compile_local('envkit-local/t/reference.png', 7, 3000, 'envkit-local/t')

    def test_every_link_names_an_existing_node(self):
        for node in self.graph.values():
            for value in node['inputs'].values():
                if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
                    self.assertIn(value[0], self.graph)

    def test_the_reference_is_cut_out_before_conditioning_and_each_stage_has_its_own_seed(self):
        self.assertEqual(self.graph['3']['inputs']['masks'], ['2', 0]); self.assertEqual(self.graph['2']['inputs']['mask'], ['1', 1])
        self.assertEqual(self.graph['20']['inputs']['image'], ['3', 0])
        # The field of view is measured from that same cut-out, not guessed.
        self.assertEqual((self.graph['5']['inputs']['image'], self.graph['20']['inputs']['camera_angle_x']), (['3', 0], ['6', 0]))
        seeds = [node['inputs']['seed'] for node in self.graph.values() if node['class_type'] == 'KSampler']
        self.assertEqual(sorted(seeds), [7, 8, 9, 10])
        self.assertEqual(self.graph['26']['inputs']['resolution'], '32')  # a choice: the server refuses the number 32

    def test_the_saved_model_is_the_decimated_mesh_with_maps_baked_from_the_dense_one(self):
        self.assertEqual(self.graph['51']['inputs']['target_face_count'], 3000)
        self.assertEqual(self.graph['52']['inputs']['mesh'], ['51', 0])
        self.assertEqual((self.graph['53']['inputs']['mesh'], self.graph['53']['inputs']['reference_mesh']), (['52', 0], ['33', 0]))
        self.assertEqual((self.graph['54']['inputs']['low_poly'], self.graph['54']['inputs']['high_poly']), (['52', 0], ['33', 0]))
        self.assertEqual(self.graph['56']['inputs'], {'mesh': ['55', 0], 'filename_prefix': 'envkit-local/t/model'})
        # One skin, not the two shells that tore the first trash can apart, and a spare of it at a high count.
        self.assertEqual(self.graph['50']['inputs']['sign_mode'], 'solid')
        self.assertEqual((self.graph['57']['inputs']['mesh'], self.graph['57']['inputs']['target_face_count']), (['50', 0], local.MASTER_TRIANGLES))
        self.assertEqual(self.graph['58']['inputs']['filename_prefix'], 'envkit-local/t/master')
        saved = sorted(node['inputs']['filename_prefix'].rsplit('/', 1)[1] for node in self.graph.values() if node['class_type'] == 'SaveImage')
        self.assertEqual(saved, sorted(local.MAPS))

    def test_a_triangle_target_outside_the_kit_range_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'triangle target'):
            local.compile_local('envkit-local/t/reference.png', 7, 250000, 'envkit-local/t')


@unittest.skipUnless(IMAGING, 'needs Pillow and numpy')
class MatteTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup); self.root = Path(self.folder.name)

    def test_the_background_goes_but_white_inside_the_object_stays(self):
        from PIL import Image, ImageDraw
        image = Image.new('RGB', (64, 64), (252, 252, 252)); draw = ImageDraw.Draw(image)
        draw.rectangle([16, 16, 47, 47], fill=(40, 60, 200)); draw.rectangle([28, 28, 35, 35], fill=(255, 255, 255))  # a white mark on the bin
        source = self.root / 'ref.png'; image.save(source)
        with Image.open(local.matte(source, self.root / 'out' / 'ref.png')) as cut:
            alpha = cut.getchannel('A')
            self.assertEqual((alpha.getpixel((2, 2)), alpha.getpixel((20, 20)), alpha.getpixel((31, 31))), (0, 255, 255))

    def test_every_attempt_keeps_its_own_record_and_none_is_written_over(self):
        import json
        from unittest import mock
        from PIL import Image, ImageDraw
        image = Image.new('RGB', (64, 64), (252, 252, 252)); ImageDraw.Draw(image).rectangle([16, 16, 47, 47], fill=(40, 60, 200))
        source = self.root / 'ref.png'; image.save(source)
        bound = {'comfyInput': str(self.root / 'in'), 'comfyOutput': str(self.root / 'out')}; output = self.root / 'models' / 'bin'

        class Idle:
            def request(self, path):
                return {'queue_running': [], 'queue_pending': []}

        def timed_out(client, graph, token, record, deadline, **options):
            record['promptId'] = 'p-1'; raise ValueError('The job did not finish in time')

        def finished(client, graph, token, record, deadline, **options):
            made = self.root / 'out' / local.SUBFOLDER / token; made.mkdir(parents=True)
            for name in ('model_00001_.glb', *(f'{kind}_00001_.png' for kind in local.MAPS)):
                (made / name).write_bytes(b'x')
        with mock.patch('tools.headkit.design.dispatch', timed_out), self.assertRaisesRegex(ValueError, 'in time'):
            local.make(Idle(), bound, 'bin', source, 7, 3000, output)
        first = list(output.parent.glob('bin.failed-*.json')); self.assertEqual(len(first), 1); kept = first[0].read_bytes()
        self.assertEqual((json.loads(kept)['state'], json.loads(kept)['promptId'], output.exists()), ('failed', 'p-1', False))
        with mock.patch('tools.headkit.design.dispatch', finished):  # the retry is not blocked, and names itself apart
            self.assertEqual(local.make(Idle(), bound, 'bin', source, 7, 3000, output)['state'], 'complete')
        self.assertEqual(first[0].read_bytes(), kept)  # the timed-out job can still be traced by its own record
        self.assertEqual(json.loads((output.parent / 'bin.json').read_text(encoding='utf-8'))['state'], 'complete')
        self.assertEqual(sorted(path.name for path in output.iterdir()), ['model.glb', *sorted(f'texture_0_{kind}.png' for kind in local.MAPS)])
        with mock.patch('tools.headkit.design.dispatch', finished), self.assertRaisesRegex(ValueError, 'Fresh output folder'):
            local.make(Idle(), bound, 'bin', source, 7, 3000, output)

    def test_an_image_with_no_plain_background_is_refused(self):
        from PIL import Image
        source = self.root / 'full.png'; Image.new('RGB', (32, 32), (10, 10, 10)).save(source)
        with self.assertRaisesRegex(ValueError, 'matte kept'):
            local.matte(source, self.root / 'full-out.png')


if __name__ == '__main__':
    unittest.main()
