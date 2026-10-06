"""A validation rejection releases credits only after owning history is reconciled."""
from pathlib import Path
import tempfile
import unittest
from head_workflow import Session,make_roster,validate_remesh,write_fresh


class SubmissionReconciliationTests(unittest.TestCase):
    def test_quad_intermediate_budget_accounts_for_glb_triangulation(self):
        for topology,count in [('triangle',19000),('quad',9500)]:
            validate_remesh({'topology':topology,'target_polycount':count,'target_formats':['glb']})
        for payload in [{'topology':'quad','target_polycount':11000,'target_formats':['glb']},
                        {'topology':'triangle','target_polycount':20001,'target_formats':['glb']},
                        {'topology':'quad','target_polycount':4500,'target_formats':['glb'],'decimation_mode':1}]:
            with self.assertRaisesRegex(ValueError,'bounded'):validate_remesh(payload)

    def test_release_requires_definite_rejection_and_no_possible_remote_task(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);roster=root/'roster.json';write_fresh(roster,make_roster())
            session=Session.create(root/'session',roster)
            session.append('reserved',requestId='oversized',operation='remesh',estimatedCredits=5)
            rejected=root/'rejected.json';history=root/'history.json'
            write_fresh(rejected,{'ok':False,'result':None,'error':{'code':'validation','http_status':400}})
            write_fresh(history,{'ok':True,'result':{'items':[{'resource':'remesh','created_at':0}],
                'page':{'page_num':1,'sort_by':'-created_at'}}})
            self.assertEqual(session.credit_used(),5)
            unknown=root/'unknown.json';write_fresh(unknown,{'ok':False,'result':None,'error':{'code':'submission_unknown'}})
            with self.assertRaisesRegex(ValueError,'definite'):session.reconcile_rejection('oversized',unknown,history)
            possible=root/'possible.json';write_fresh(possible,{'ok':True,'result':{'items':[{'resource':'remesh','created_at':9999999999999}],
                'page':{'page_num':1,'sort_by':'-created_at'}}})
            with self.assertRaisesRegex(ValueError,'possible'):session.reconcile_rejection('oversized',rejected,possible)
            self.assertEqual(session.credit_used(),5)
            session.reconcile_rejection('oversized',rejected,history)
            self.assertEqual(session.credit_used(),0)
            with self.assertRaisesRegex(ValueError,'unsubmitted'):session.reconcile_rejection('oversized',rejected,history)

    def test_reconcile_rejection_accepts_empty_task_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);roster=root/'roster.json';write_fresh(roster,make_roster())
            session=Session.create(root/'session',roster)
            session.append('reserved',requestId='first-dispatch',operation='multi-image-to-3d',estimatedCredits=20)
            rejected=root/'rejected.json';empty_history=root/'empty_history.json'
            write_fresh(rejected,{'ok':False,'result':None,'error':{'code':'validation','http_status':400}})
            write_fresh(empty_history,{'ok':True,'result':{'items':[],
                'page':{'page_num':1,'sort_by':'-created_at'}}})
            self.assertEqual(session.credit_used(),20)
            session.reconcile_rejection('first-dispatch',rejected,empty_history)
            self.assertEqual(session.credit_used(),0)
            bad_history=root/'bad_history.json'
            session.append('reserved',requestId='second-dispatch',operation='multi-image-to-3d',estimatedCredits=20)
            write_fresh(bad_history,{'ok':True,'result':{'items':None,
                'page':{'page_num':1,'sort_by':'-created_at'}}})
            with self.assertRaisesRegex(ValueError,'Newest-first owning task history required'):
                session.reconcile_rejection('second-dispatch',rejected,bad_history)

    def test_reconcile_rejection_cli_commands(self):
        import subprocess, sys
        import head_workflow, meshy_cli
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); roster = root / 'roster.json'; write_fresh(roster, make_roster())
            session = Session.create(root / 'session', roster)
            session.append('reserved', requestId='cli-test', operation='remesh', estimatedCredits=5)
            rejected = root / 'rejected.json'; history = root / 'history.json'
            write_fresh(rejected, {'ok': False, 'result': None, 'error': {'code': 'validation', 'http_status': 400}})
            write_fresh(history, {'ok': True, 'result': {'items': [], 'page': {'page_num': 1, 'sort_by': '-created_at'}}})

            # CLI via meshy_cli.py
            cmd_meshy = [sys.executable, str(Path(meshy_cli.__file__).resolve()), 'reconcile-rejection',
                         '--session', str(session.root), '--request-id', 'cli-test',
                         '--response', str(rejected), '--history', str(history)]
            proc = subprocess.run(cmd_meshy, capture_output=True, text=True, check=True)
            self.assertEqual(proc.stdout.strip(), 'cli-test')
            self.assertEqual(session.credit_used(), 0)

            # CLI via head_workflow.py
            session.append('reserved', requestId='workflow-cli-test', operation='remesh', estimatedCredits=5)
            self.assertEqual(session.credit_used(), 5)
            cmd_workflow = [sys.executable, str(Path(head_workflow.__file__).resolve()), 'reconcile-rejection',
                            '--session', str(session.root), '--request-id', 'workflow-cli-test',
                            '--response', str(rejected), '--history', str(history)]
            proc = subprocess.run(cmd_workflow, capture_output=True, text=True, check=True)
            self.assertEqual(session.credit_used(), 0)


if __name__=='__main__':unittest.main()

