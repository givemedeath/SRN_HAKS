"""Read a trial client log and confirm every expected actor spawned on its head slot (and palette rows when logged)."""
import argparse
from pathlib import Path
import re
import sys
from head_workflow import pin,read,require,write_fresh

SESSION=re.compile(r'^Messages for: (?P<started>.+?)\s*$')
ENTRY=re.compile(r'^\[[^\]]*\] (?P<text>.*)$')
FIELDS=re.compile(r'(\w+)=(\S+)')
COLOR_KEYS=('skin','hair','tattoo1','tattoo2')


def last_session(text):
    """Return (header, entry texts) of the newest session block; the client prepends a 'Messages for:' banner per run."""
    started,lines=None,[]
    for line in text.splitlines():
        match=SESSION.match(line)
        if match:started,lines=match['started'],[];continue
        match=ENTRY.match(line)
        if match:lines.append(match['text'])
    return started,lines


def fixture_events(lines,kind):
    """Map actor tag to the ordered field dicts of HEAD_FIXTURE_<kind> entries."""
    events={}
    for line in lines:
        if line.startswith('HEAD_FIXTURE_'+kind+' '):
            fields=dict(FIELDS.findall(line[len('HEAD_FIXTURE_'+kind)+1:]))
            if 'actor' in fields:events.setdefault(fields.pop('actor'),[]).append(fields)
    return events


def check(manifest,text,*,check_colors=True):
    require(manifest.get('kind')=='srn-head-trial-client-view','Trial runtime manifest required')
    started,lines=last_session(text)
    loaded=[line.split(':',1)[1].strip() for line in lines if line.startswith('Loading Module:')]
    slots=fixture_events(lines,'SLOT');colors=fixture_events(lines,'COLORS')
    expected={actor['tag'] for actor in manifest['actors']}
    actors=[]
    for actor in manifest['actors']:
        seen=[event.get('selected') for event in slots.get(actor['tag'],[])]
        row={'tag':actor['tag'],'headId':actor['headId'],'model':actor['model'],'expectedSlot':actor['slot'],'observedSlots':seen}
        if not seen:row['status']='missing'
        elif any(value!=str(actor['slot']) for value in seen):row['status']='wrong-slot'
        else:row['status']='spawned'
        if check_colors and manifest.get('colorsLogged') and row['status']=='spawned':
            logged=colors.get(actor['tag'],[])
            want={key:str(actor[key]) for key in COLOR_KEYS}
            row['observedColors']=logged[-1] if logged else None
            if not logged:row['status']='colors-missing'
            elif any({key:event.get(key) for key in COLOR_KEYS}!=want for event in logged):row['status']='wrong-colors'
        actors.append(row)
    ignored=set(manifest.get('ignoredActors',[]))
    unexpected=sorted(set(slots)-expected-ignored)
    problems=[]
    if started is None:problems.append('No client session banner in log')
    if manifest['module'] not in loaded:problems.append('Module '+manifest['module']+' was not loaded in the newest session')
    if 'HEAD_FIXTURE_CLIENT_ENTER' not in lines:problems.append('Player never entered the module (no HEAD_FIXTURE_CLIENT_ENTER)')
    problems+=[f"{row['tag']} ({row['model']}): {row['status']}" for row in actors if row['status']!='spawned']
    problems+=['Unexpected actor in log: '+tag for tag in unexpected]
    if 'rows' in manifest:
        shown={line.split('shown=',1)[1].split()[0] for line in lines if line.startswith('HEAD_FIXTURE_ROW shown=')}
        problems+=[f"Head row {row['index']+1} ({row['headId']}) never shown" for row in manifest['rows'] if str(row['index']) not in shown]
    return {'kind':'srn-head-trial-log-verification','session':started,'modulesLoaded':loaded,
            'actors':actors,'unexpectedActors':unexpected,'problems':problems,'passed':not problems,
            'limitation':'A logged slot number proves the engine assigned the head slot; it does not prove the model rendered, '
                         'the palette looks right or the anatomy is acceptable. Inspect the client view.'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True,help='runtime-manifest.json written by build_head_trial.py')
    parser.add_argument('--log',type=Path,help='client log; default: <manifest dir>/userdir/logs/nwclientLog1.txt')
    parser.add_argument('--output',type=Path,help='optional fresh JSON report')
    parser.add_argument('--slots-only',action='store_true',help='skip HEAD_FIXTURE_COLORS checks (modules built before colour logging)')
    args=parser.parse_args(argv)
    log=args.log or args.manifest.parent/'userdir'/'logs'/'nwclientLog1.txt'
    if not log.is_file():
        print('Client log not found: '+str(log)+' (run Launch.cmd first)');return 2
    manifest=read(args.manifest)
    report=check(manifest,log.read_text(encoding='utf-8',errors='replace'),check_colors=not args.slots_only)
    module=args.manifest.parent/'userdir'/'modules'/(manifest['module']+'.mod')
    if module.is_file() and log.stat().st_mtime<module.stat().st_mtime:
        report['problems'].append('Client log predates the trial module build');report['passed']=False
    for row in report['actors']:
        print(f"{row['status']:<14} {row['tag']:<16} {row['model']:<14} expected={row['expectedSlot']} observed={','.join(row['observedSlots']) or '-'}")
    for problem in report['problems']:print('PROBLEM: '+problem)
    slotted=sum(r['status'] not in ('missing','wrong-slot') for r in report['actors'])
    print('PASSED' if report['passed'] else 'FAILED',f"({slotted}/{len(report['actors'])} actors on expected slots)")
    if args.output:write_fresh(args.output,{**report,'manifest':pin(args.manifest),'log':pin(log)})
    return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
