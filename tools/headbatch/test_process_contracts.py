"""Adversarial tests of GPU lineage, isolation, cancellation and review evidence."""
from pathlib import Path
import sys,threading,unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_headbatch as fixtures
write=fixtures.write
from workspace import Workspace
import gpu_contract,launcher,gpu_job,guards
from resource_budget import Watchdog,BudgetExceeded
REAL_IDLE=gpu_job.Comfy.ensure_idle

class Contracts(fixtures.Base):
    def fixture(self):
        helper=fixtures.GpuJob();helper.root=self.root;helper.workspace=self.workspace
        head=self.head();ledger=helper.approved_gpu_fixture(head)
        return head,ledger
    def test_shape_cannot_follow_recalibration_or_modified_shape(self):
        head,ledger=self.fixture();gpu_contract.require_geometry_review(head,ledger)
        ledger['stages']['calibrate']['fov']['detail']=55
        with self.assertRaisesRegex(ValueError,'conditioning/camera'):
            gpu_contract.require_geometry_review(head,ledger)
        ledger['stages']['calibrate']['fov']['detail']=30.
        shape=ledger['stages']['geometry']['files']['963:shape.pt'];Path(shape['path']).write_text('drift')
        with self.assertRaisesRegex(ValueError,'Stale'):gpu_contract.require_geometry_review(head,ledger)
    def test_new_submission_and_changed_sheet_invalidate_approval(self):
        head,ledger=self.fixture()
        ledger['stages']['geometry']['submission']=2
        with self.assertRaisesRegex(ValueError,'current geometry'):gpu_contract.require_geometry_review(head,ledger)
        ledger['stages']['geometry']['submission']=1
        path=gpu_contract.evidence_path(head,ledger['stages']['geometry'])
        report=guards.read(path);Path(report['sheet']['path']).write_text('changed')
        with self.assertRaisesRegex(ValueError,'Stale'):gpu_contract.require_geometry_review(head,ledger)
    def test_stage_order_and_recalibration_partial_reuse_are_refused(self):
        for value in ('','appearance,geometry','geometry,geometry','calibrate,appearance','unknown'):
            with self.subTest(value=value),self.assertRaises(ValueError):gpu_contract.stages(value)
        self.assertEqual(gpu_contract.stages('geometry,appearance'),['geometry','appearance'])
    def test_two_workspaces_share_the_device_lock(self):
        other=Workspace(self.root/'other',dict(self.workspace.data))
        with patch.object(launcher,'lock',side_effect=lambda fn:fn()) as lock:
            left=launcher.gpu_lock(self.workspace);right=launcher.gpu_lock(other)
        self.assertEqual(left,right);self.assertIn('shared-tools',str(left[0]))
    def test_ram_floor_cannot_be_removed_or_lowered(self):
        for gates in ({'1':0},{'2':float('nan')},{'9':10}):
            with self.subTest(gates=gates),self.assertRaises(ValueError):
                Workspace(self.root,dict(self.workspace.data,ramGates=gates)).ram_gates()
        self.assertEqual(len(launcher.open_slots(self.workspace,lambda:6)),1)
        self.assertEqual(launcher.open_slots(self.workspace,lambda:5.99),[])
    def test_watchdog_interrupts_while_main_poll_is_blocked(self):
        interrupted=threading.Event();budget=Mock();budget.check.side_effect=BudgetExceeded('budget breach')
        with Watchdog(budget,lambda:interrupted.set() or True) as watcher:
            self.assertTrue(interrupted.wait(1))
        self.assertEqual(watcher.reason,'budget breach');self.assertTrue(watcher.interrupted)
    def test_cancellation_never_interrupts_somebody_elses_job(self):
        comfy=gpu_job.Comfy('http://127.0.0.1:1',self.root);comfy.call=Mock(return_value={'queue_running':[[0,'other']],'queue_pending':[]});comfy.send=Mock()
        self.assertFalse(comfy.interrupt_owned('owned'));comfy.send.assert_not_called()
    def test_busy_queue_never_unloads_or_submits(self):
        comfy=gpu_job.Comfy('http://127.0.0.1:1',self.root);comfy.call=Mock(return_value={'queue_pending':[[0,'other']],'queue_running':[]});comfy.send=Mock()
        comfy.ensure_idle=lambda:REAL_IDLE(comfy)
        with self.assertRaisesRegex(gpu_job.ComfyError,'busy'):comfy.free()
        comfy.send.assert_not_called()

    def test_malformed_queue_cannot_unload_or_interrupt(self):
        for queue in ({},[],{'queue_running':[[]],'queue_pending':[]}):
            comfy=gpu_job.Comfy('http://127.0.0.1:1',self.root)
            comfy.call=Mock(return_value=queue);comfy.send=Mock()
            comfy.ensure_idle=lambda:REAL_IDLE(comfy)
            with self.assertRaisesRegex(gpu_job.ComfyError,'unknown'):comfy.free()
            with self.assertRaisesRegex(gpu_job.ComfyError,'unknown'):comfy.interrupt_owned('owned')
            comfy.send.assert_not_called()
    def test_lost_prompt_id_retains_unique_reconciliation_token(self):
        comfy=gpu_job.Comfy('http://127.0.0.1:1',self.root);comfy.free=Mock()
        comfy.unresolved=self.root/'UNRECONCILED';comfy.call=Mock(return_value={'accepted':True})
        with self.assertRaisesRegex(gpu_job.ComfyError,'reconcile'):comfy.submit({'test':'graph'})
        record=guards.read(comfy.unresolved)
        self.assertEqual(record['graph'],{'test':'graph'});self.assertEqual(len(record['clientId']),32)

if __name__=='__main__':unittest.main()
