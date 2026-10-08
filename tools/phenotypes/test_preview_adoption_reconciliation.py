"""Female preview identity/material preservation with main strict preparation."""
import ast
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from audit_geometry import arrays
from prepare_effective_body_preview import Resolver, mesh_corners, export_part, sha
from retarget import nodes
from rig_controller_audit import world_frames
from run_preparation import PreparationContext
from test_effective_body_preview import model


class PreviewReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def context(self):
        return PreparationContext(target_revision='pinned-female-target', rig_revision='exact-female-stock',
                                  animation_revision='no-animation-edits', settings={'sourcePrefix': 'pfh0', 'height': 1.837937046})

    def test_effective_decode_rejects_missing_parent_and_cycle(self):
        for text in [model().replace('parent test', 'parent missing'),
                     model().replace('parent NULL', 'parent testp')]:
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, 'Unresolved parent bind|Geometry parent cycle'):
                    mesh_corners(text, authored_required=True)

    def test_pose_stock_geometry_rejects_before_blender_for_incomplete_hierarchy(self):
        path = Path(__file__).with_name('pose_preview.py')
        tree = ast.parse(path.read_text(encoding='utf-8'))
        function = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == 'stock_part')
        module = ast.Module(body=[function], type_ignores=[])
        namespace = {'nodes': nodes, 'world_frames': world_frames, 'arrays': arrays}
        exec(compile(module, str(path), 'exec'), namespace)
        for text in [model().replace('parent test', 'parent missing'),
                     model().replace('parent NULL', 'parent testp')]:
            source = self.root/'stock.mdl'; source.write_text(text, encoding='cp1252')
            with self.assertRaisesRegex(ValueError, 'Unresolved parent bind|Geometry parent cycle'):
                namespace['stock_part'](source, 'part')

    def test_context_image_decode_is_once_immutable_and_same_original_pixels(self):
        pixels = np.array([[[11,22,33,255], [44,55,66,255]]], dtype='u1')
        path = self.root/'skin.tga'; Image.fromarray(pixels).save(path)
        context = self.context(); inputs = {}
        resolver = Resolver([(self.root, {path.name: sha(path)})], inputs, context)
        a = resolver.image(resolver.file(path.name), 'RGBA')
        b = resolver.image(resolver.file(path.name), 'RGBA')
        self.assertIs(a, b); np.testing.assert_array_equal(a, pixels)
        self.assertEqual(context.counts['palette/image-decode'], 1)
        with self.assertRaises(ValueError): a[0,0,0] = 99
        self.assertEqual(inputs[str(path.resolve())], sha(path))

    def test_resolver_freezes_nonimage_material_for_completion(self):
        path = self.root/'skin.mtr'; path.write_text('parameter float Roughness 0\n')
        context = self.context(); resolver = Resolver([(self.root, {path.name: sha(path)})], {}, context)
        resolver.file(path.name); path.write_text('parameter float Roughness 1\n')
        with self.assertRaisesRegex(ValueError, 'Input changed'): context.verify()

    def test_cached_authored_pnu_export_preserves_original_magnitudes_and_indices(self):
        source = self.root/'pfh0_chest001.mdl'; source.write_text(model(second_uv=True, transformed=True), encoding='cp1252')
        context = self.context()
        prepared = context.prepared(source, 'geometry-decode', lambda data: mesh_corners(data.decode('cp1252'), authored_required=True))
        uncached = mesh_corners(source.read_text(encoding='cp1252'), authored_required=True)
        for field in ('position', 'normal', 'uv'):
            np.testing.assert_array_equal(prepared[0][field], uncached[0][field])
        Image.fromarray(np.array([[[17,27,37,255]]], dtype='u1')).save(self.root/'skin.tga')
        pins = {'skin.tga': sha(self.root/'skin.tga')}
        resolver = Resolver([(self.root, pins)], {}, context)
        output = self.root/'export.glb'; receipt = export_part(output, prepared, resolver, {0:3})
        with np.load(receipt['sourceCornerArchive'], allow_pickle=False) as saved:
            for field, key in [('position', 'mesh0PositionNwn'), ('normal', 'mesh0NormalNwn'), ('uv', 'mesh0UvNwn')]:
                np.testing.assert_array_equal(saved[key], uncached[0][field])
        self.assertTrue(receipt['meshes'][0]['serializationProof']['authoredNormalLengthNotRenormalized'])
        context.verify()

    def test_context_identity_keeps_actual_female_target_and_settings(self):
        result = self.context().receipt()
        self.assertEqual(result['identity']['targetRevision'], 'pinned-female-target')
        self.assertEqual(result['identity']['settings']['sourcePrefix'], 'pfh0')
        self.assertEqual(result['identity']['settings']['height'], 1.837937046)
        self.assertFalse(result['clientEvidence'])


if __name__ == '__main__':
    unittest.main()
