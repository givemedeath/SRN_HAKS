"""Entry point: python -m tools.headkit --help. Processing requires the shared launcher."""
import argparse
from pathlib import Path
import shutil
import uuid
from .common import read,write,pin,verify,require,manifest,bindings,asset,source_version,launched,code_pins,python_package_pins
from . import comfy


def request_stage(manifest_path, bindings_path, stage, output, *, runtime=None, comfy_runtime=None):
    data=manifest(manifest_path);local=bindings(bindings_path)
    require(data.get('approval',{}).get('inputReviewComplete') is True,'Review measured input overlays and feature inventory before GPU preparation')
    profile=data.get('profile','pixal-single-v1');camera=data.get('camera',{})
    if stage in ('geometry','appearance'):
        require(camera.get('reviewed') is True,'Reviewed camera calibration required')
    names={'calibrate':['geometry','detail','mask'],'geometry':['geometry'],'appearance':['detail'],'export':[]}[stage]
    if profile=='pixal-multiview-v1' and stage=='geometry':names=['front','left','back','right']
    require(stage!='geometry' or (data.get('features') and all(x.get('placementReviewed') is True for x in data['features'])),
            'Review hairstyle routing, all accessories and counts before generation')
    shape=asset(manifest_path,data['inputs']['shape']) if stage=='appearance' else None
    expected_mesh=asset(manifest_path,data['inputs']['geometryRaw']) if stage=='appearance' else None
    if stage=='appearance':
        review=data.get('approval',{}).get('generatedGeometry',{})
        require(review.get('decision')=='approved' and bool(review.get('notes','').strip())
                and review.get('geometryRawSha256')==expected_mesh['sha256']
                and review.get('shapeSha256')==shape['sha256'],
                'Approve generated clay with geometryRaw and shape hashes before appearance preparation')
    export_source=asset(manifest_path,data['inputs']['exportSource']) if stage=='export' else None
    if stage=='export':
        review=data.get('approval',{}).get('exportGeometry',{})
        require(review.get('decision')=='approved' and bool(review.get('notes','').strip())
                and review.get('exportSourceSha256')==export_source['sha256'],
                'Approve generated clay with the exact exportSource hash before export preparation')
    binding_pin=pin(bindings_path)
    images={};pins=[pin(manifest_path),binding_pin]+code_pins()
    if runtime is not None:pins.extend(runtime[name] for name in ('toolchain','migrationReceipt','python'))
    from .source_inventory import freeze_sources,validate_comfy_runtime
    inventory=freeze_sources(local)
    comfy_runtime=validate_comfy_runtime(comfy_runtime,inventory['roots'],inventory)
    pins+=inventory['files']+comfy_runtime['files']
    adapter=Path(local['comfyCustomNodes'])/'srn_headkit'
    source_config=adapter/'source-roots.json'
    require(read(source_config)=={'schemaVersion':1,'inventory':inventory},
            'Installed Comfy source snapshot differs; reinstall the current adapter and restart ComfyUI')
    pins.append(pin(source_config))
    for code in (Path(__file__).parent/'comfy_nodes').glob('*.py'):
        installed=adapter/code.name;require(pin(installed)['sha256']==pin(code)['sha256'],'Installed headkit nodes differ; install current adapters and restart ComfyUI')
        pins.append(pin(installed))
    root=Path(local['comfyInput']).resolve();token=uuid.uuid4().hex;staging=root/'headkit'/token;staging.mkdir(parents=True,exist_ok=False)
    for name in names:
        source=asset(manifest_path,data['inputs'][name]);pins.append(source)
        target=staging/(name+'.png')
        from PIL import Image
        image=Image.open(source['path']).convert('RGBA')
        if name=='mask':image.save(target)
        else:
            background=Image.new('RGBA',image.size,(0,0,0,255));background.alpha_composite(image);background.convert('RGB').save(target)
        images[name]=target.relative_to(root).as_posix();pins.append(pin(target))
    pins += [p for p in (shape,export_source) if p]
    if expected_mesh:pins.append(expected_mesh)
    graph=comfy.compile_graph(stage,profile,images,'headkit/'+token,fov=camera.get('fovDegrees'),shape=shape,source=export_source)
    from .comfy_nodes.model_resolution import loader_models,bind_loader_models
    models=loader_models(graph,local.get('models',{}),read(Path(__file__).parent/'checkpoints.json'))
    graph=bind_loader_models(graph,models)
    # Pin each model's filename, Comfy folder category, resolved path identity and bytes.
    for model in models:
        row=local['models'][model['name']]
        if row not in pins:pins.append(row)
    result={'stage':stage,'profile':profile,'token':token,'prompt':graph,'inputs':pins,'codeVersion':source_version(),
            'timeoutSeconds':2700,'generationCeiling':100,'expectedGeometry':expected_mesh,'comfySourceInventory':inventory,
            'comfyRuntimeIdentity':comfy_runtime,'runtimeIdentity':runtime,'bindings':binding_pin,'comfyEndpoint':comfy.Client(local['comfyUrl']).url,
            'loaderModels':models}
    write(output,result,fresh=True);return result


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


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    for name in ('prepare','run','resume','status','review'):
        p=sub.add_parser(name);p.add_argument('--manifest',required=True,type=Path);p.add_argument('--bindings',required=True,type=Path);p.add_argument('--run',required=True,type=Path)
        if name in ('run','resume','review'):p.add_argument('--stage',required=True)
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
    p=sub.add_parser('inputs');p.add_argument('--manifest',required=True,type=Path);p.add_argument('--bindings',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--run',type=Path)
    p=sub.add_parser('install-nodes');p.add_argument('--destination',required=True,type=Path);p.add_argument('--bindings',required=True,type=Path)
    a=parser.parse_args()
    runtime=launched(getattr(a,'bindings',None)) if a.command not in ('status','inputs') else None
    if a.command in ('prepare','run','resume','status','review'):
        from .runner import Runner
        if a.command=='status':result=Runner(a.manifest,a.bindings,a.run).status()
        else:
            with comfy.locked(a.run/'runner'):
                runner=Runner(a.manifest,a.bindings,a.run,runtime=runtime)
                result=runner.review(a.stage,a.decision,a.notes) if a.command=='review' else runner.execute('prepare' if a.command=='prepare' else a.stage)
    elif a.command=='inputs':
        data=manifest(a.manifest);local=bindings(a.bindings)
        pins=code_pins()+[pin(a.manifest),pin(a.bindings)]+[asset(a.manifest,p) for p in data['inputs'].values()]+python_package_pins(local)
        for name in ('toolchain','migrationReceipt'):
            if name in local:pins.append(pin(local[name]))
        for name in ('python','blender','client','embree'):
            if name in local:pins.append(local[name])
        pins+=list(local.get('models',{}).values())+local.get('comfySources',[])
        for row in local.get('libraries',{}).values():pins+=row['files']
        if 'comfyCustomNodes' in local:
            pins += [pin(p) for p in (Path(local['comfyCustomNodes'])/'srn_headkit').glob('*.py')]
        if a.run and (a.run/'state.json').exists():
            pins.append(pin(a.run/'state.json'))
            state=read(a.run/'state.json');pins+=list(state.get('reviews',{}).values())
            for row in state['stages'].values():
                pins.append(row);pins+=read(row['path'])['inputs']+read(row['path'])['outputs']
        verify(pins);paths=sorted({p['path'] for p in pins});write(a.output,paths,fresh=True);result={'inputs':str(a.output),'count':len(paths)}
    elif a.command=='request':
        local=bindings(a.bindings)
        server_runtime=comfy.Client(local['comfyUrl']).request('/headkit/runtime-identity')
        result=request_stage(a.manifest,a.bindings,a.stage,a.output,runtime=runtime,comfy_runtime=server_runtime)
    elif a.command=='ledger-init':comfy.initialize_ledger(a.ledger,a.prior_count,a.evidence);result={'ledger':str(a.ledger)}
    elif a.command=='replay':
        from .replay import replay
        result=replay(read(a.config),a.output)
    elif a.command=='install-nodes':result=install_nodes(a.destination,bindings(a.bindings))
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


if __name__=='__main__':main()
