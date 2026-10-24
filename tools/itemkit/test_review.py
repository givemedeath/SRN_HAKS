import tempfile
import unittest
from pathlib import Path
from tools.headkit.common import pin
from .review import geometry_review_key, reuse_clay, render_variants


class ReviewTests(unittest.TestCase):
    def test_batch_reuses_clay_only_and_rejects_source_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); scene = root/'source.blend'; scene.write_bytes(b'scene')
            texture = root/'texture.png'; texture.write_bytes(b'texture')
            cfg = {'scene': str(scene), 'family': {'family': 'firearm-sling'}, 'render': {'camera': 1}}
            calls = []
            def renderer(config, out, _clay_review=None):
                calls.append(_clay_review is not None)
                if _clay_review:
                    frames, cameras = reuse_clay(config, out, _clay_review)
                else:
                    frames = []; cameras = []
                    for i in range(8):
                        path = out/f'clay-{i}.png'; path.write_bytes(bytes([i]))
                        frames.append(pin(path)); cameras.append({'mode': 'clay', 'view': i})
                return {'frames': frames, 'cameras': cameras}
            result = render_variants(cfg, {'base': texture, 'alt': texture}, root/'batch', renderer=renderer)
            self.assertEqual(calls, [False, True]); self.assertEqual(result['reusedGeometryPasses'], 1)
            for i in range(8):
                self.assertEqual((root/f'batch/base/clay-{i}.png').read_bytes(), (root/f'batch/alt/clay-{i}.png').read_bytes())
            def mutate(config, out, _clay_review=None):
                result = renderer(config, out, _clay_review); scene.write_bytes(b'other'); return result
            with self.assertRaisesRegex(ValueError, 'Stale'):
                render_variants(cfg, {'base': texture}, root/'stale', renderer=mutate)

    def test_key_binds_geometry_cameras_and_family_but_not_finish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); scene = root/'scene'; scene.write_bytes(b'a')
            cfg = {'scene': str(scene), 'family': {'family': 'dagger'}, 'render': {'light': 80}}
            key = geometry_review_key(cfg)
            self.assertEqual(key, geometry_review_key({**cfg, 'texture': 'different'}))
            self.assertNotEqual(key, geometry_review_key({**cfg, 'render': {'light': 81}}))
            self.assertNotEqual(key, geometry_review_key({**cfg, 'family': {'family': 'longsword'}}))
            scene.write_bytes(b'b'); self.assertNotEqual(key, geometry_review_key(cfg))

    def test_invalid_variant_path_and_stale_frames_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); scene = root/'scene'; scene.write_bytes(b'a')
            cfg = {'scene': str(scene), 'family': {}}
            with self.assertRaisesRegex(ValueError, 'variant names'):
                render_variants(cfg, {'../escape': scene}, root/'batch')
            frames = []; cameras = []
            for i in range(8):
                p = root/f'clay-{i}.png'; p.write_bytes(b'a'); frames.append(pin(p)); cameras.append({'mode': 'clay'})
            p.write_bytes(b'b'); out = root/'out'; out.mkdir()
            with self.assertRaisesRegex(ValueError, 'Stale'):
                reuse_clay(cfg, out, {'key': geometry_review_key(cfg), 'frames': frames, 'cameras': cameras})
            self.assertEqual(list(out.iterdir()), [])
