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
DURATIONS='tools/ci-test-durations.json'
VERIFY='Repository verification'

def changed_files(base,head='HEAD',repo=REPO):
    """Return changed paths, or None when there is no usable comparison base."""
    if not base or re.fullmatch(r'0+',base):return None
    result=subprocess.run(['git','-C',str(repo),'diff','--name-only',f'{base}...{head}'],capture_output=True,text=True)
    if result.returncode:return None
    return sorted({line.strip().replace('\\','/') for line in result.stdout.splitlines() if line.strip()})

def shards(tests,count,durations):
    """Deterministic longest-processing-time split; unknown tests weigh the median measured duration."""
    known=sorted(durations.values());default=known[len(known)//2] if known else 1.0
    bins=[[0.0,i,[]] for i in range(count)]
    for test in sorted(tests,key=lambda t:(-durations.get(t,default),t)):
        target=min(bins,key=lambda b:(b[0],b[1]));target[0]+=durations.get(test,default);target[2].append(test)
    return [sorted(b[2]) for b in bins]

def plan(changed,data,config,durations=None,full_reason=None,base=''):
    durations=durations or {}
    if full_reason:selection=test_impact.full(data,full_reason)
    elif changed is None:selection=test_impact.full(data,'Missing or undiffable comparison base; full suite required')
    else:selection=test_impact.select(changed,data,config)
    tests=selection['tests'];paths=changed or []
    everything=selection['fullSuite']
    groups={g['name']:[] for g in config['groups']}
    for test in data['tests'] if everything else tests:
        group=next((g['name'] for g in config['groups'] if re.search(g['pattern'],test)),None)
        if group is None:raise ValueError('Test belongs to no CI group: '+test)
        groups[group].append(test)
    jobs=[];matrix=[]
    for g in config['groups']:
        for index,part in enumerate(shards(groups[g['name']],g['shards'],durations)):
            if not part:continue
            name=g['name'] if g['shards']==1 else f"{g['name']}-{index+1}"
            for os_name in config['operatingSystems']:
                matrix.append({'os':os_name,'group':name,'tests':part})
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

def summary(result):
    lines=['## CI scope plan','',f"- Full suite: **{result['fullSuite']}**; {result['reason']}",
        f"- Changed files: {'unknown' if result['changed'] is None else len(result['changed'])}",
        f"- Item import: {result['itemImport']}; wheel: {result['wheel']}"]
    if result['documentation']:lines.append('- Documentation only (no helper tests): '+', '.join(result['documentation']))
    if result['packs']:lines.append('- Pack assets: '+', '.join(result['packs']))
    lines+=['','| Job | Tests |','|---|---:|']
    seen=set()
    for row in result['helperMatrix']:
        if row['group'] in seen:continue
        seen.add(row['group']);lines.append(f"| {row['group']} | {len(row['tests'])} |")
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
    result=plan(None if a.full_reason else changed_files(a.base,a.head),data,config,durations,a.full_reason or None,a.base)
    a.output.write_text(json.dumps(result,indent=1)+'\n',encoding='utf-8')
    if a.github_output:
        with a.github_output.open('a',encoding='utf-8') as f:f.write('plan='+json.dumps(result,separators=(',',':'))+'\n')
    print(summary(result))

if __name__=='__main__':main()
