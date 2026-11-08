"""GPU selection and admission must fail closed without changing render fidelity."""
from pathlib import Path
from types import SimpleNamespace as NS
from contextlib import contextmanager
import tempfile
import unittest
from unittest.mock import patch
from headkit.render_device import settings,pci,configure,MemoryWatch,lease
from headkit.common import read


class RenderDevice(unittest.TestCase):
    def config(self,folder):
        return {'compute':{'device':'GPU','backend':'OPTIX','gpuIndex':0,'memoryLimitBytes':100,'gpuLock':str(Path(folder)/'gpu-0'),'comfyUrl':'http://127.0.0.1:8188'}}
    def test_cpu_default_does_not_require_a_gpu(self):
        scene=NS(cycles=NS(device='unset'));bpy=NS(context=NS(scene=scene))
        self.assertEqual(configure(bpy,{},None),{'device':'CPU'});self.assertEqual(scene.cycles.device,'CPU')
        with MemoryWatch({},Path('unused'),sampler=lambda _:self.fail('CPU used sampler')):pass
    def test_gpu_requires_budget_and_shared_coordination(self):
        with tempfile.TemporaryDirectory() as root:
            for key in ('backend','gpuIndex','memoryLimitBytes','gpuLock','comfyUrl'):
                cfg=self.config(root);del cfg['compute'][key]
                with self.assertRaises(ValueError):settings(cfg)
            cfg=self.config(root);cfg['compute']['memoryLimitBytes']=True
            with self.assertRaises(ValueError):settings(cfg)
    def test_selects_budgeted_pci_device_and_disables_cpu_and_other_gpu(self):
        devices=[NS(type='CPU',id='CPU',name='CPU',use=True),NS(type='OPTIX',id='NVIDIA_0000:01:00_OptiX',name='GPU',use=False),NS(type='OPTIX',id='NVIDIA_0000:02:00_OptiX',name='GPU',use=True)]
        prefs=NS(devices=devices,refresh_devices=lambda:None);scene=NS(cycles=NS(device='CPU'));bpy=NS(context=NS(scene=scene,preferences=NS(addons={'cycles':NS(preferences=prefs)})))
        with tempfile.TemporaryDirectory() as root:
            selected=configure(bpy,self.config(root),{'name':'GPU','pci':'00000000:01:00.0'})
            self.assertEqual([d.use for d in devices],[False,True,False]);self.assertEqual(scene.cycles.device,'GPU');self.assertEqual(selected['backend'],'OPTIX')
            with self.assertRaisesRegex(ValueError,'CPU fallback refused'):configure(bpy,self.config(root),{'name':'GPU','pci':'00000000:03:00.0'})
    def test_sampled_cap_includes_other_processes_and_preserves_failure_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            row={'usedBytes':100,'name':'GPU','pci':'00000000:01:00.0'};watch=MemoryWatch(self.config(root),Path(root)/'memory.json',sampler=lambda _:row)
            self.assertIsNone(watch.tick());row['usedBytes']=101;self.assertIn('budget exceeded',watch.tick());watch.save()
            self.assertEqual(read(watch.output)['sampledPeakDeviceBytes'],101);self.assertFalse(read(watch.output)['allocatorHardLimit'])
            failure=MemoryWatch(self.config(root),Path(root)/'failure.json',sampler=lambda _:(_ for _ in ()).throw(OSError('sampler unavailable')))
            with self.assertRaisesRegex(ValueError,'sampler unavailable'):failure.__enter__()
            self.assertIn('sampler unavailable',read(failure.output)['reason'])
    def test_busy_comfy_refuses_and_releases_shared_lock(self):
        from headkit.comfy import locked
        with tempfile.TemporaryDirectory() as root:
            cfg=self.config(root)
            with patch('headkit.render_device.comfy_idle',return_value=False):
                with self.assertRaisesRegex(ValueError,'ComfyUI is busy'):
                    with lease(cfg):self.fail('GPU admitted behind ComfyUI')
            with locked(Path(cfg['compute']['gpuLock'])):pass
    def test_gpu_lease_uses_the_existing_shared_mutex(self):
        from headkit.comfy import locked
        with tempfile.TemporaryDirectory() as root:
            cfg=self.config(root)
            with locked(Path(cfg['compute']['gpuLock'])),patch('headkit.render_device.time.monotonic',side_effect=[0,301]):
                with self.assertRaisesRegex(ValueError,'Timed out'):
                    with lease(cfg):self.fail('Shared GPU lock bypassed')


class QueueAdmission(unittest.TestCase):
    def test_queue_is_local_complete_and_fail_closed(self):
        from headkit.render_device import comfy_idle
        import json
        with patch('headkit.render_device.urllib.request.urlopen') as request:
            response=request.return_value.__enter__.return_value
            for row,expected in [({'queue_running':[],'queue_pending':[]},True),
                                 ({'queue_running':[1],'queue_pending':[]},False),
                                 ({'queue_running':[],'queue_pending':[1]},False)]:
                response.read.return_value=json.dumps(row).encode()
                self.assertEqual(comfy_idle('http://localhost:8188'),expected)
            for row in [{}, {'queue_running':[]}, {'queue_running':None,'queue_pending':[]}]:
                response.read.return_value=json.dumps(row).encode()
                with self.assertRaisesRegex(ValueError,'queue response'):comfy_idle('http://localhost:8188')
            request.reset_mock()
            for url in ['https://localhost:8188','http://example.com','http://u:p@localhost:8188','http://localhost:8188/?x=1']:
                with self.assertRaisesRegex(ValueError,'bound local'):comfy_idle(url)
            request.assert_not_called()


if __name__=='__main__':unittest.main()
