"""Verify explicit offline CPU selection and preserved default preview settings."""
from types import SimpleNamespace
import unittest

from pose_preview_render_settings import apply_render_settings


class RenderSettingsTests(unittest.TestCase):
    def test_default_eevee_preserves_previous_ao_and_does_not_touch_cycles(self):
        scene=SimpleNamespace(render=SimpleNamespace(),eevee=SimpleNamespace())
        result=apply_render_settings(scene,'eevee')
        self.assertEqual(scene.render.engine,'BLENDER_EEVEE')
        self.assertTrue(scene.eevee.use_gtao)
        self.assertEqual(scene.eevee.gtao_distance,.08)
        self.assertFalse(result['clientEvidence'])
        self.assertFalse(hasattr(scene,'cycles'))

    def test_cycles_cpu_forces_device_samples_and_fixed_threads(self):
        scene=SimpleNamespace(render=SimpleNamespace(),cycles=SimpleNamespace(device='GPU'))
        result=apply_render_settings(scene,'cycles-cpu')
        self.assertEqual(scene.render.engine,'CYCLES')
        self.assertEqual(scene.cycles.device,'CPU')
        self.assertEqual(scene.cycles.samples,16)
        self.assertEqual(scene.render.threads_mode,'FIXED')
        self.assertEqual(scene.render.threads,4)
        self.assertEqual(scene.cycles.denoiser,'OPENIMAGEDENOISE')
        self.assertEqual(result['device'],'CPU')
        self.assertFalse(result['clientEvidence'])

    def test_unreviewed_engine_selection_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Unknown'):
            apply_render_settings(SimpleNamespace(),'cycles-gpu')


if __name__=='__main__':unittest.main()
