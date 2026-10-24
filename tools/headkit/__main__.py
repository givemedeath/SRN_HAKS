"""Entry point: python -m tools.headkit --help. Processing requires the shared launcher."""
import argparse
from pathlib import Path
import shutil
import uuid
from .common import read,write,pin,verify,require,manifest,bindings,asset,source_version,launched,code_pins,python_package_pins,digest,stage_code_pins,stage_source_version
from . import comfy


def request_stage(manifest_path, bindings_path, stage, output, *, runtime=None, comfy_runtime=None):
    from .generation import prepare_request
    return prepare_request(manifest_path, bindings_path, stage, output,
                           runtime=runtime, comfy_runtime=comfy_runtime, read_json=read)



def startup_config(local,output):
    """Prepare an offline deployment manifest; never start or contact ComfyUI."""
    from .source_inventory import freeze_sources
    from .comfy_nodes.managed_startup import runtime_inventory,launch_arguments
    inventory=freeze_sources(local);python=local['comfyPython'];verify([python])
    roots=[str(Path(root).resolve(strict=True)) for root in local['comfyRuntimeRoots']]
    for root in [*roots,*inventory['roots']]:
        require(not Path(output).resolve().is_relative_to(root),'Startup configuration must be outside deployment roots')
    require(not any(Path(source).is_relative_to(root) or Path(root).is_relative_to(source)
                    for source in inventory['roots'] for root in roots),'Keep Comfy source and runtime roots separate')
    adapter=Path(local['comfyCustomNodes'])/'srn_headkit'
    require(read(adapter/'source-roots.json')=={'schemaVersion':1,'inventory':inventory},
            'Installed source snapshot differs; install the reviewed adapter into an idle dedicated deployment')
    for code in (Path(__file__).parent/'comfy_nodes').glob('*.py'):
        require(pin(adapter/code.name)['sha256']==pin(code)['sha256'],'Installed adapter differs from reviewed toolkit')
    config={'schemaVersion':1,'inventory':inventory,'runtime':{'python':python,'roots':roots,'files':runtime_inventory(roots)},
            'adapterSnapshot':pin(adapter/'source-roots.json'),'launch':dict(local['comfyStartup'])}
    require(config['launch']['endpoint']==comfy.Client(local['comfyUrl']).url,'Startup endpoint differs from local bindings')
    arguments=config['launch']['arguments']
    for field,flag in (('comfyInput','--input-directory'),('comfyOutput','--output-directory')):
        values=[arguments[index+1] for index,value in enumerate(arguments[:-1]) if value==flag]
        values += [value.split('=',1)[1] for value in arguments if value.startswith(flag+'=')]
        require(len(values)==1 and Path(values[0]).resolve()==Path(local[field]).resolve(),
                'Startup input/output directories must exactly match local bindings')
    require(python in config['runtime']['files'],'Runtime roots must include the pinned Comfy Python')
    launch_arguments(config);verify(config['runtime']['files']+inventory['files']+[config['adapterSnapshot']])
    write(output,config,fresh=True);return {'configuration':pin(output),'started':False}


def install_nodes(destination,local):
    require(destination.name=='srn_headkit' and destination.parent.name=='custom_nodes',
            'Use a new custom_nodes/srn_headkit folder')
    require(destination.parent.resolve()==Path(local['comfyCustomNodes']).resolve(),
            'Install destination must match the bound Comfy custom_nodes folder')
    from .source_inventory import capture_sources,freeze_sources
    initial=freeze_sources(local)
    shutil.copytree(Path(__file__).parent/'comfy_nodes',destination,ignore=shutil.ignore_patterns('__pycache__'))
    inventory=capture_sources(initial['core'],initial['roots'])
    write(destination/'source-roots.json',{'schemaVersion':1,'inventory':inventory},fresh=True)
    return {'installed':str(destination),'sourceSnapshot':str(destination/'source-roots.json'),
            'restartRequired':True,'comfyRestarted':False}


OPTIONAL_SECTIONS=('paint','render')  # stages a manifest may leave out entirely


def skip_reason(runner,stage):
    """Why a chain passes over a stage this manifest does not make: an optional section left out, or a pass-through tone."""
    if stage in OPTIONAL_SECTIONS and stage not in runner.data:return 'Not configured: the manifest has no '+stage+' section'
    if stage=='tone' and runner.tone_pass_through():return 'Configured pass-through (no operations): palette reads the colour directly'
    return None


def chain(runner, stages):
    """Execute/reuse CPU stages in order; stop at the first unreviewed dependency or failure. Records no new judgement: only
    an earlier approval carried onto byte-identical rerun outputs (Runner._carry_review), shown as review 'carried'."""
    from .runner import STAGES
    require(stages and len(set(stages))==len(stages) and all(s in STAGES for s in stages)
            and list(stages)==sorted(stages,key=STAGES.index),'Chain stages must be distinct CPU stages in pipeline order')
    def attempt(stage):
        row=runner.state['stages'].get(stage);return (str(Path(row['path']).parent),read(row['path'])) if row else (None,{})
    def decision(stage):
        review=runner.state.get('reviews',{}).get(stage)
        if review is None or not Path(review['path']).is_file():return 'pending'
        review=read(review['path']);return review.get('decision') if review.get('stageReceipt')==runner.state['stages'].get(stage) else 'pending'
    rows=[];stopped=None
    for stage in stages:
        skipped=skip_reason(runner,stage)
        if skipped:
            rows.append({'stage':stage,'status':'skipped','reason':skipped});continue
        blocked=None
        for dependency in runner.dependencies(stage):
            try:runner.result(dependency)
            except (ValueError,OSError) as exc:blocked=(dependency,str(exc));break
        if blocked:
            dependency,reason=blocked;folder,_=attempt(dependency)
            kind='blocked-on-review' if 'review' in reason.lower() else 'blocked-on-dependency'
            rows.append({'stage':stage,'status':kind,'dependency':dependency,'reason':reason,'evidence':folder,
                'next':(f'Inspect {folder} then record `review --stage {dependency}`' if kind=='blocked-on-review'
                        else f'Run or rerun {dependency} before {stage}')})
            stopped=kind;break
        try:outcome=runner.execute(stage)
        except Exception as exc:
            folder,receipt=attempt(stage)
            rows.append({'stage':stage,'status':'failed','error':str(exc),
                'attempt':folder if receipt.get('state')=='failed' else None,'next':'Fix the cause, then rerun chain to resume here'})
            stopped='failed';break
        folder,receipt=attempt(stage)
        rows.append({'stage':stage,'status':'reused' if outcome['reused'] else 'ran','attempt':folder,
                     'elapsedSeconds':receipt.get('elapsedSeconds'),'review':'carried' if 'carriedReview' in outcome else decision(stage)})
        if 'carriedReview' in outcome:rows[-1]['carriedReview']=outcome['carriedReview']
    return {'id':runner.data['id'],'run':str(runner.run),'stages':rows,'stopped':stopped,'autoApproved':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    for name in ('prepare','run','resume','status','review','chain'):
        p=sub.add_parser(name);p.add_argument('--manifest',required=True,type=Path);p.add_argument('--bindings',required=True,type=Path);p.add_argument('--run',required=True,type=Path)
        if name in ('run','resume','review'):p.add_argument('--stage',required=True)
        if name=='chain':
            p.add_argument('--stages',required=True,type=lambda v:[s.strip() for s in v.split(',') if s.strip()])
            # One launch records the operator's review of the stage that gates the chain, then continues it.
            p.add_argument('--approve');p.add_argument('--notes')
        if name=='review':p.add_argument('--decision',choices=['approved','rejected'],required=True);p.add_argument('--notes',required=True)
    p=sub.add_parser('request');p.add_argument('--manifest',required=True,type=Path);p.add_argument('--bindings',required=True,type=Path)
    p.add_argument('--stage',choices=['calibrate','geometry','appearance','export'],required=True);p.add_argument('--output',required=True,type=Path)
    p=sub.add_parser('ledger-init');p.add_argument('--ledger',required=True,type=Path);p.add_argument('--prior-count',required=True,type=int);p.add_argument('--evidence',required=True)
    for name in ('submit','collect','reconcile','release'):
        p=sub.add_parser(name);p.add_argument('--bindings',required=True,type=Path)
        p.add_argument('--ledger',required=True,type=Path)
        if name in ('collect','reconcile'):p.add_argument('--token',required=True)
        if name in ('submit','collect'):p.add_argument('--output',required=True,type=Path)
        if name=='submit':p.add_argument('--request',required=True,type=Path)
        if name=='collect':p.add_argument('--wait',action='store_true')
    p=sub.add_parser('replay');p.add_argument('--config',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p=sub.add_parser('inputs');p.add_argument('--manifest',required=True,type=Path);p.add_argument('--bindings',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--run',type=Path);p.add_argument('--stages')
    p=sub.add_parser('fit-propose');p.add_argument('--bindings',required=True,type=Path);p.add_argument('--source',required=True,type=Path)
    p.add_argument('--reference',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--exclude-lower',type=float,default=.25)
    # Seconds-long previews of manifest texture rules / repair relief on the run's bound outputs (no stage attempt).
    p=sub.add_parser('preview');p.add_argument('--manifest',required=True,type=Path);p.add_argument('--bindings',required=True,type=Path)
    p.add_argument('--run',required=True,type=Path);p.add_argument('--what',choices=['ownership','stats','relief'],required=True)
    p.add_argument('--regions',type=Path);p.add_argument('--output',required=True,type=Path)
    p=sub.add_parser('startup-config');p.add_argument('--bindings',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p=sub.add_parser('install-nodes');p.add_argument('--destination',required=True,type=Path);p.add_argument('--bindings',required=True,type=Path)
    # Direct-dispatch Flux.2 design proposals (see design.py): unguarded, for human review only.
    p=sub.add_parser('design');p.add_argument('--bindings',required=True,type=Path);p.add_argument('--spec',required=True,type=Path)
    p.add_argument('--head',required=True);p.add_argument('--seed',required=True,type=int);p.add_argument('--batch',type=int,default=1)
    p.add_argument('--reference',action='append',default=[],type=Path);p.add_argument('--output',required=True,type=Path)
    p=sub.add_parser('design-inpaint');p.add_argument('--bindings',required=True,type=Path);p.add_argument('--spec',required=True,type=Path)
    p.add_argument('--design',required=True,type=Path);p.add_argument('--skin',required=True);p.add_argument('--seed',required=True,type=int)
    p.add_argument('--batch',type=int,default=2);p.add_argument('--cut',type=int);p.add_argument('--lift',type=int,default=24)
    p.add_argument('--name');p.add_argument('--output',required=True,type=Path)
    p.add_argument('--carve-top',type=int,help='carve mode: keep rows above this and the --keep jaw polygon; stump outline from --stump')
    p.add_argument('--keep',nargs='+',help='carve jaw keep polygon as x,y points');p.add_argument('--stump',help='carve stump cx,wTop,wBottom,ySide,yBottom')
    a=parser.parse_args()
    runtime=launched(getattr(a,'bindings',None)) if a.command not in ('status','inputs') else None
    if a.command in ('prepare','run','resume','status','review','chain'):
        from .runner import Runner
        if a.command=='status':result=Runner(a.manifest,a.bindings,a.run).status()
        else:
            with comfy.locked(a.run/'runner'):
                runner=Runner(a.manifest,a.bindings,a.run,runtime=runtime)
                if a.command=='chain':
                    require((a.approve is None)==(a.notes is None),'--approve and --notes go together')
                    review=runner.review(a.approve,'approved',a.notes) if a.approve else None
                    result=chain(runner,a.stages);result['reviewRecorded']=review
                else:result=runner.review(a.stage,a.decision,a.notes) if a.command=='review' else runner.execute('prepare' if a.command=='prepare' else a.stage)
    elif a.command=='inputs':
        data=manifest(a.manifest);local=bindings(a.bindings);closure=None
        if a.stages:
            # Launch-scoped list: the stages' declared inputs plus the receipts of everything upstream of them.
            from .runner import Runner,STAGES,stage_roles,stage_libraries
            chosen=a.stages.split(',');require(chosen and all(s in STAGES for s in chosen),'Unknown stage in --stages')
            require(a.run is not None,'--stages needs --run');deps=Runner(a.manifest,a.bindings,a.run).dependencies
            closure=set();pending=list(chosen)
            while pending:
                stage=pending.pop()
                if stage not in closure:closure.add(stage);pending+=deps(stage)
            roles=set().union(*(stage_roles(s,data) for s in chosen));libraries=set().union(*(stage_libraries(s,data) for s in chosen))
        else:roles=set(data['inputs']);libraries=set(local.get('libraries',{}))
        # Stage-scoped code for a launch-scoped list; the whole package otherwise.
        code=code_pins() if closure is None else list({row['path']:row for s in sorted(closure) for row in stage_code_pins(s)}.values())
        pins=code+[pin(a.manifest),pin(a.bindings)]+[asset(a.manifest,data['inputs'][r]) for r in sorted(roles)]+python_package_pins(local)
        for name in ('toolchain','migrationReceipt'):
            if name in local:pins.append(pin(local[name]))
        for name in ('python','blender','client','embree'):
            if name in local:pins.append(local[name])
        pins+=list(local.get('models',{}).values())+local.get('comfySources',[])
        if 'comfyStartupConfig' in local:pins.append(pin(local['comfyStartupConfig']))
        if 'comfyPython' in local:pins.append(local['comfyPython'])
        if 'comfyRuntimeRoots' in local:
            from .comfy_nodes.managed_startup import runtime_inventory
            pins+=runtime_inventory(local['comfyRuntimeRoots'])
        for name in sorted(libraries):pins+=local['libraries'][name]['files']
        if 'comfyCustomNodes' in local:
            adapter=Path(local['comfyCustomNodes'])/'srn_headkit'
            pins += [pin(adapter/'source-roots.json')]+[pin(p) for p in adapter.glob('*.py')]
        if a.run and (a.run/'state.json').exists():
            # state.json is the run's mutable index, rewritten by run/chain/review during the launch; the immutable
            # receipts and reviews it points to are the frozen inputs.
            state=read(a.run/'state.json');stale=[]
            from .runner import Runner;scoped=Runner(a.manifest,a.bindings,a.run)
            for stage,row in state['stages'].items():
                if closure is not None and stage not in closure:continue
                receipt=read(row['path'])
                # A receipt from other code or another manifest is rerun, not consumed; its old pins are not inputs.
                if receipt.get('codeVersion')!=stage_source_version(stage) or receipt.get('manifestHash')!=scoped.manifest_digest(stage):stale.append(stage);continue
                pins.append(row);pins+=receipt['inputs']+receipt['outputs']
                if stage in state.get('reviews',{}):pins.append(state['reviews'][stage])
        verify(pins);paths=sorted({p['path'] for p in pins});write(a.output,paths,fresh=True);result={'inputs':str(a.output),'count':len(paths)}
        if a.run and (a.run/'state.json').exists():result['staleStagesSkipped']=stale
    elif a.command=='preview':
        from .runner import Runner
        from .preview import preview
        result=preview(Runner(a.manifest,a.bindings,a.run,runtime=runtime),a.what,a.output,read(a.regions) if a.regions else None)
    elif a.command=='startup-config':result=startup_config(bindings(a.bindings),a.output)
    elif a.command=='request':
        local=bindings(a.bindings)
        server_runtime=comfy.Client(local['comfyUrl']).request('/headkit/runtime-identity')
        result=request_stage(a.manifest,a.bindings,a.stage,a.output,runtime=runtime,comfy_runtime=server_runtime)
    elif a.command=='ledger-init':comfy.initialize_ledger(a.ledger,a.prior_count,a.evidence);result={'ledger':str(a.ledger)}
    elif a.command=='replay':
        from .replay import replay
        result=replay(read(a.config),a.output)
    elif a.command in ('design','design-inpaint'):
        from . import design
        local=bindings(a.bindings);client=comfy.Client(local['comfyUrl'])
        if a.command=='design':result=design.generate(client,local,a.bindings,a.spec,a.head,a.seed,a.batch,a.reference,a.output,runtime=runtime)
        else:
            carve=None
            if a.carve_top is not None or a.keep or a.stump:
                require(a.carve_top is not None and a.keep and a.stump,'Carve needs --carve-top, --keep and --stump together')
                carve={'top':a.carve_top,'keep':[[int(v) for v in point.split(',')] for point in a.keep],'stump':[float(v) for v in a.stump.split(',')]}
            result=design.inpaint(client,local,a.bindings,a.spec,a.design,a.skin,a.seed,a.batch,a.output,cut=a.cut,lift=a.lift,name=a.name,
                                  runtime=runtime,carve=carve)
    elif a.command=='install-nodes':result=install_nodes(a.destination,bindings(a.bindings))
    elif a.command=='fit-propose':
        from .fit import propose
        require(.0<=a.exclude_lower<=.5,'--exclude-lower must be 0..0.5');result=propose(a.source,a.reference,a.output,exclude_lower=a.exclude_lower)
    else:
        local=bindings(a.bindings);client=comfy.Client(local['comfyUrl'])
        if a.command=='release':result=comfy.release(client,a.ledger)
        elif a.command=='submit':
            prepared=read(a.request);require(prepared['codeVersion']==source_version(),'Stale compiled request; prepare again')
            result=comfy.submit(client,a.ledger,prepared,a.output,runtime_identity=runtime,bindings_path=a.bindings)
        elif a.command=='collect':result=comfy.collect(client,a.ledger,a.token,local['comfyOutput'],a.output,wait=a.wait)
        else:result=comfy.reconcile(client,a.ledger,a.token)
    import json
    print(json.dumps(result,indent=2,allow_nan=False))
    if a.command=='chain' and result['stopped']=='failed':raise SystemExit(1)


if __name__=='__main__':main()
