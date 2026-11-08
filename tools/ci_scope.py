"""Compute one CI scope plan: changed files, selected suites, shards and reasons."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_impact

REPO=test_impact.REPO
DURATIONS=test_impact.DURATIONS
VERIFY='Repository verification'

def changed_files(base,head='HEAD',repo=REPO):
    """Return changed paths, or None when there is no usable comparison base."""
    if not base or re.fullmatch(r'0+',base):return None
    result=subprocess.run(['git','-C',str(repo),'diff','--name-only','--no-renames',f'{base}...{head}'],capture_output=True,text=True)
    if result.returncode:return None
    return sorted({line.strip().replace('\\','/') for line in result.stdout.splitlines() if line.strip()})

shards=test_impact.balance

def plan(changed,data,config,durations=None,full_reason=None,base='',deleted=()):
    durations=durations or {}
    if full_reason:selection=test_impact.full(data,full_reason)
    elif changed is None:selection=test_impact.full(data,'Missing or undiffable comparison base; full suite required')
    else:selection=test_impact.select(changed,data,config,deleted)
    tests=selection['tests'];paths=changed or []
    everything=selection['fullSuite']
    groups={g['name']:[] for g in config['groups']}
    planned=data['tests'] if everything else tests
    needs={t:test_impact.pack_needs(data,t) for t in planned}
    for test in planned:
        # A packTests group collects every test that reaches a pack, so the other legs never check packs out.
        group=next((g['name'] for g in config['groups'] if (needs[test] if g.get('packTests') else re.search(g['pattern'],test))),None)
        if group is None:raise ValueError('Test belongs to no CI group: '+test)
        groups[group].append(test)
    jobs=[];matrix=[]
    for g in config['groups']:
        for index,part in enumerate(shards(groups[g['name']],g['shards'],durations)):
            if not part:continue
            name=g['name'] if g['shards']==1 else f"{g['name']}-{index+1}"
            packs=sorted({p for t in part for p in needs[t]})
            for os_name in config['operatingSystems']:
                # checkout is the cone-mode sparse set; root files are always included.
                matrix.append({'os':os_name,'group':name,'tests':part,'packs':packs,'checkout':'\n'.join(config['testCheckout']+packs)})
                jobs.append(f'Helpers / {os_name} {name}')
    # Case-insensitive, matching PowerShell -match in Test-ItemImportScope.ps1.
    item=everything or any(re.search(r,p,re.I) for p in paths for r in config['itemImport'])
    wheel=everything or any(re.search(r,p) for p in paths for r in config['wheel'])
    if item:jobs.extend(f'Helpers / item-import {os_name}' for os_name in config['operatingSystems'])
    if wheel:jobs.append('Helpers / wheel')
    return {'schemaVersion':1,'fullSuite':everything,'reason':selection['reason'],'base':base,'changed':changed,
        'documentation':selection.get('documentation',[]),'packs':selection.get('packs',[]),
        'helperMatrix':matrix,'itemImport':item,'wheel':wheel,'operatingSystems':config['operatingSystems'],
        'expectedJobs':['Scope',VERIFY,*jobs]}

def job_output(result):
    """Compact plan for job outputs. Large changes (thousands of pack assets) would exceed the runner's
    argument limit, so the changed paths become their count; the plan file keeps the full list."""
    changed=result['changed']
    return json.dumps({**result,'changed':None if changed is None else len(changed)},separators=(',',':'))

def summary(result):
    lines=['## CI scope plan','',f"- Full suite: **{result['fullSuite']}**; {result['reason']}",
        f"- Changed files: {'unknown' if result['changed'] is None else len(result['changed'])}",
        f"- Item import: {result['itemImport']}; wheel: {result['wheel']}"]
    if result['documentation']:lines.append('- Documentation only (no helper tests): '+', '.join(result['documentation']))
    if result['packs']:lines.append('- Pack assets: '+', '.join(result['packs']))
    lines+=['','| Job | Tests | Checked-out packs |','|---|---:|---|']
    seen=set()
    for row in result['helperMatrix']:
        if row['group'] in seen:continue
        seen.add(row['group']);lines.append(f"| {row['group']} | {len(row['tests'])} | {', '.join(row['packs']) or 'none'} |")
    return '\n'.join(lines)+'\n'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',default='');p.add_argument('--head',default='HEAD')
    p.add_argument('--full-reason',default='',help='Force the full suite and record why')
    p.add_argument('--output',type=Path,required=True);p.add_argument('--check-catalog',action='store_true')
    p.add_argument('--github-output',type=Path,help='Append plan=<compact JSON> for job outputs')
    a=p.parse_args()
    data=test_impact.catalog();config=test_impact.load_config()
    if a.check_catalog:
        committed=json.loads((REPO/'tools/test-impact.json').read_text(encoding='utf-8'))
        if committed!=data:raise SystemExit('tools/test-impact.json is stale; run: python -B tools/test_impact.py --write-catalog tools/test-impact.json')
    durations=json.loads((REPO/DURATIONS).read_text(encoding='utf-8'))['seconds'] if (REPO/DURATIONS).is_file() else {}
    changed=None if a.full_reason else changed_files(a.base,a.head)
    # The checkout is the head revision, so a changed path missing here was deleted.
    result=plan(changed,data,config,durations,a.full_reason or None,a.base,test_impact.deleted_paths(changed or []))
    a.output.write_text(json.dumps(result,indent=1)+'\n',encoding='utf-8')
    if a.github_output:
        with a.github_output.open('a',encoding='utf-8') as f:f.write('plan='+job_output(result)+'\n')
    print(summary(result))

if __name__=='__main__':main()
