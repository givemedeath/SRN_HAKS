"""Decide the single required CI result from the scope plan and the run's latest job attempts."""
import argparse
import json
from pathlib import Path

PASSING={'success'}

def latest(jobs):
    """Keep each job name's most recent attempt, so re-running failed jobs replaces their old results."""
    chosen={}
    for job in jobs:
        name=job['name'];previous=chosen.get(name)
        if previous is None or (job.get('run_attempt',1),job.get('id',0))>=(previous.get('run_attempt',1),previous.get('id',0)):chosen[name]=job
    return chosen

def evaluate(plan,jobs,needs,self_name='CI result'):
    """Return (passed, problems). Selected jobs must succeed; nothing may fail or be cancelled."""
    problems=[]
    for name,need in sorted(needs.items()):
        if need.get('result') in ('failure','cancelled'):problems.append(f'Dependency {name} {need["result"]}')
    if plan is None:return False,problems+['Scope plan missing']
    current=latest(jobs)
    for name in plan['expectedJobs']:
        job=current.get(name)
        if job is None:problems.append(f'Selected job missing: {name}')
        elif job.get('status')!='completed':problems.append(f'Selected job not completed: {name} ({job.get("status")})')
        elif job.get('conclusion') not in PASSING:problems.append(f'Selected job {job.get("conclusion")}: {name}')
    expected=set(plan['expectedJobs'])|{self_name}
    # Jobs come from every attempt; an unselected job only counts when it ran in the newest attempt.
    newest=max((job.get('run_attempt',1) for job in jobs),default=1)
    for name,job in sorted(current.items()):
        if name not in expected and job.get('run_attempt',1)==newest and job.get('conclusion') in ('failure','cancelled','timed_out','action_required'):
            problems.append(f'Unselected job {job["conclusion"]}: {name}')
    return not problems,problems

def read_jobs(text):
    """Accept a jobs API page, a list of jobs, or JSON lines from `gh api --paginate --jq '.jobs[]'` (filter=all)."""
    try:value=json.loads(text)
    except json.JSONDecodeError:return [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(value,dict):return value.get('jobs',[value])
    return value

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--jobs',type=Path,required=True)
    p.add_argument('--needs',type=Path,required=True)
    p.add_argument('--pending-exit-code',type=int,choices=[2],help='Signal pending-only API metadata so the caller can refresh; never a pass')
    a=p.parse_args()
    plan=json.loads(a.plan.read_text(encoding='utf-8')) if a.plan.is_file() and a.plan.stat().st_size else None
    jobs=read_jobs(a.jobs.read_text(encoding='utf-8'))
    passed,problems=evaluate(plan,jobs,json.loads(a.needs.read_text(encoding='utf-8')))
    if a.pending_exit_code and problems and all(line.startswith(('Selected job missing: ','Selected job not completed: ')) for line in problems):
        print('CI result: waiting for selected job metadata')
        raise SystemExit(a.pending_exit_code)
    for line in problems:print('::error::'+line)
    print('CI result: '+('passed' if passed else 'failed'))
    raise SystemExit(0 if passed else 1)

if __name__=='__main__':main()
