import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from ci_result import evaluate,read_jobs

PLAN={'expectedJobs':['Scope','Repository verification','Helpers / ubuntu-latest core','Helpers / windows-latest core']}
NEEDS={'scope':{'result':'success'},'verify':{'result':'success'},'helpers':{'result':'success'}}

def job(name,conclusion='success',attempt=1,status='completed',ident=0):
    return {'name':name,'status':status,'conclusion':conclusion,'run_attempt':attempt,'id':ident}

def passing():return [job(n,ident=i) for i,n in enumerate(PLAN['expectedJobs'])]+[job('CI result',None,status='in_progress',ident=99)]

class ResultTests(unittest.TestCase):
    def test_all_selected_jobs_succeeding_passes(self):
        self.assertEqual(evaluate(PLAN,passing(),NEEDS),(True,[]))
    def test_failure_cancellation_and_timeouts_fail(self):
        for conclusion in ('failure','cancelled','timed_out'):
            jobs=passing();jobs[2]['conclusion']=conclusion
            passed,problems=evaluate(PLAN,jobs,NEEDS)
            self.assertFalse(passed,conclusion);self.assertIn('Helpers / ubuntu-latest core',problems[0])
    def test_selected_job_skipped_or_missing_fails(self):
        jobs=passing();jobs[3]['conclusion']='skipped'
        self.assertFalse(evaluate(PLAN,jobs,NEEDS)[0])
        passed,problems=evaluate(PLAN,[j for j in passing() if j['name']!='Helpers / windows-latest core'],NEEDS)
        self.assertFalse(passed);self.assertEqual(problems,['Selected job missing: Helpers / windows-latest core'])
    def test_unselected_skipped_jobs_pass_but_unselected_failures_do_not(self):
        jobs=passing()+[job('Helpers / wheel','skipped'),job('Helpers / item-import ubuntu-latest','skipped')]
        self.assertTrue(evaluate(PLAN,jobs,NEEDS)[0])
        self.assertFalse(evaluate(PLAN,passing()+[job('Helpers / wheel','failure')],NEEDS)[0])
    def test_failed_dependency_or_missing_plan_fails(self):
        self.assertFalse(evaluate(PLAN,passing(),{**NEEDS,'helpers':{'result':'cancelled'}})[0])
        self.assertFalse(evaluate(None,passing(),{**NEEDS,'scope':{'result':'failure'}})[0])
        self.assertEqual(evaluate(None,[],{})[1],['Scope plan missing'])
    def test_rerun_after_failure_uses_the_latest_attempt(self):
        jobs=passing();jobs[2]['conclusion']='failure'
        self.assertFalse(evaluate(PLAN,jobs,NEEDS)[0])
        rerun=jobs+[job('Helpers / ubuntu-latest core','success',attempt=2,ident=50)]
        self.assertTrue(evaluate(PLAN,rerun,NEEDS)[0])
        again=jobs+[job('Helpers / ubuntu-latest core','failure',attempt=2,ident=50)]
        self.assertFalse(evaluate(PLAN,again,NEEDS)[0])
    def test_jobs_retained_from_an_earlier_attempt_count_after_rerunning_failed_jobs(self):
        # filter=all: attempt 1 holds every job; attempt 2 only re-ran the failed shard.
        first=passing();first[3]['conclusion']='failure'
        rerun=first+[job('Helpers / windows-latest core','success',attempt=2,ident=60),job('CI result',None,attempt=2,status='in_progress',ident=61)]
        self.assertEqual(evaluate(PLAN,rerun,NEEDS),(True,[]))
    def test_stale_unselected_failures_from_older_attempts_are_ignored(self):
        stale=[{**j,'run_attempt':2} for j in passing()]+[job('Helpers / wheel','failure',attempt=1,ident=70)]
        self.assertTrue(evaluate(PLAN,stale,NEEDS)[0])
        self.assertFalse(evaluate(PLAN,stale+[job('Helpers / wheel','failure',attempt=2,ident=71)],NEEDS)[0])
    def test_unfinished_selected_job_fails(self):
        jobs=passing();jobs[1]['status']='in_progress';jobs[1]['conclusion']=None
        self.assertFalse(evaluate(PLAN,jobs,NEEDS)[0])

class CommandLineTests(unittest.TestCase):
    def test_reads_json_lines_pages_and_lists(self):
        rows=passing()
        self.assertEqual(read_jobs('\n'.join(json.dumps(r) for r in rows)),rows)
        self.assertEqual(read_jobs(json.dumps({'jobs':rows})),rows)
        self.assertEqual(read_jobs(json.dumps(rows)),rows)
        self.assertEqual(read_jobs(json.dumps(rows[0])),[rows[0]])
    def test_exit_status_matches_the_decision(self):
        script=Path(__file__).with_name('ci_result.py')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'plan.json').write_text(json.dumps(PLAN));(root/'needs.json').write_text(json.dumps(NEEDS))
            (root/'jobs.jsonl').write_text('\n'.join(json.dumps(r) for r in passing()))
            args=[sys.executable,'-B',str(script),'--plan',str(root/'plan.json'),'--jobs',str(root/'jobs.jsonl'),'--needs',str(root/'needs.json')]
            self.assertEqual(subprocess.run(args,capture_output=True).returncode,0)
            (root/'plan.json').write_text('')
            self.assertEqual(subprocess.run(args,capture_output=True).returncode,1)

if __name__=='__main__':unittest.main()
