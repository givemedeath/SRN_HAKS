"""Frozen Pixal request compiler and one-at-a-time, crash-safe local dispatch."""
from contextlib import contextmanager
from pathlib import Path
import copy
import errno
import json
import os
import threading
import time
import urllib.request
import urllib.error
from urllib.parse import urlparse
import uuid
from .common import read, write, require, pin, verify, digest
from .source_inventory import request_sources,verify_sources,validate_comfy_runtime

TEMPLATES = Path(__file__).parent / 'templates'
MULTIVIEW_VIEWS=('Front','Left','Back','Right')
_LOCAL_LOCKS=set()
_LOCAL_LOCKS_GUARD=threading.Lock()


def compile_graph(stage, profile, images, prefix, *, fov=None, shape=None, source=None):
    require(stage in ('calibrate', 'geometry', 'appearance', 'export'), 'Unknown Comfy stage')
    require(profile in ('pixal-single-v1', 'pixal-multiview-v1'), 'Unknown profile')
    multi = profile == 'pixal-multiview-v1'
    name = ('multiview-' if multi and stage in ('geometry', 'appearance') else '') + stage
    graph = read(TEMPLATES / (name + '.json'))
    require(prefix.startswith('headkit/') and '..' not in prefix.split('/'), 'Isolated output prefix required')
    if stage == 'calibrate':
        require(not multi, 'Multiview uses its reviewed fixed rig, not single-view MoGe calibration')
        for node, role in [('1','geometry'), ('2','detail'), ('3','mask')]: graph[node]['inputs']['image'] = images[role]
    elif stage in ('geometry', 'appearance'):
        if multi:
            require(fov == 20, 'Frozen multiview rig FOV is 20 degrees')
            # Smooth-clay views condition the mesh; the matching detailed views condition its texture.
            nodes = ('364','377','378','379') if stage == 'geometry' else ('1001','1002','1003','1004')
            kind = 'geometry' if stage == 'geometry' else 'detail'
            mapping = {node: kind+view for node, view in zip(nodes, MULTIVIEW_VIEWS)}
            require(set(images) == set(mapping.values()), 'Missing or surplus multiview roles')
            for node, role in mapping.items(): graph[node]['inputs']['image'] = images[role]
        else:
            require(type(fov) in (float,int) and 25 <= fov <= 70, 'Reviewed single-view FOV must be 25..70 degrees')
            node, role = ('364','geometry') if stage == 'geometry' else ('1001','detail')
            require(set(images) == {role}, 'Exactly one native single-image input required')
            graph[node]['inputs']['image'] = images[role]
            graph['298']['inputs']['camera_angle_x'] = fov
        if stage == 'appearance':
            verify([shape]); graph['970']['inputs'].update(path=shape['path'], sha256=shape['sha256'])
    else:
        verify([source]); graph['1']['inputs'].update(path=source['path'], sha256=source['sha256'])
        # The comparison/export-only branches are not part of a runtime 20K job.
        graph = {k:v for k,v in graph.items() if k in ('1','241','186','187','188','922')}
    for key, node in graph.items():
        if 'filename_prefix' in node['inputs']: node['inputs']['filename_prefix'] = f'{prefix}/node-{key}'
    # Every edge must point to an included node. Image strings must not replace edges.
    for node in graph.values():
        for key,value in node['inputs'].items():
            if key in ('image','images') and node['class_type']!='LoadImage':
                require(isinstance(value,list),'IMAGE socket must reference an image output')
            if isinstance(value, list) and len(value) == 2:
                require(isinstance(value[0],str) and value[0] in graph and type(value[1]) is int, 'Dangling graph link')
    return graph


class Client:
    def __init__(self, url):
        parsed = urlparse(url)
        require(parsed.scheme == 'http' and parsed.hostname in ('localhost','127.0.0.1') and not parsed.username
                and parsed.path in ('','/'), 'Use the bound local ComfyUI instance')
        self.url = url.rstrip('/')

    def request(self, route, data=None):
        payload = None if data is None else json.dumps(data,allow_nan=False).encode()
        request = urllib.request.Request(self.url + route, data=payload, headers={'Content-Type':'application/json'})
        timeout=300 if route=='/headkit/runtime-identity' else 30
        with urllib.request.urlopen(request, timeout=timeout) as response: return json.load(response)

    def idle(self):
        queue = self.request('/queue')
        return not queue.get('queue_running') and not queue.get('queue_pending')


@contextmanager
def locked(ledger):
    path = Path(str(ledger)+'.lock'); path.parent.mkdir(parents=True,exist_ok=True)
    # Windows mutexes are abandoned automatically when their owning process exits.
    if os.name=='nt':
        import ctypes
        kernel32=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel32.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype=ctypes.c_void_p
        kernel32.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint]
        kernel32.WaitForSingleObject.restype=ctypes.c_uint
        kernel32.ReleaseMutex.argtypes=[ctypes.c_void_p]
        kernel32.CloseHandle.argtypes=[ctypes.c_void_p]
        name='Local\\SRNHeadkit-'+uuid.uuid5(uuid.NAMESPACE_URL,os.path.normcase(str(path.resolve()))).hex
        with _LOCAL_LOCKS_GUARD:
            if name in _LOCAL_LOCKS:raise FileExistsError(f'Ledger is locked: {path}')
        handle=kernel32.CreateMutexW(None,False,name)
        if not handle:raise ctypes.WinError(ctypes.get_last_error())
        acquired=False
        try:
            state=kernel32.WaitForSingleObject(handle,0)
            if state==0x102:raise FileExistsError(f'Ledger is locked: {path}')
            if state not in (0,0x80):raise ctypes.WinError(ctypes.get_last_error())
            acquired=True
            with _LOCAL_LOCKS_GUARD:_LOCAL_LOCKS.add(name)
            yield
        finally:
            if acquired:
                with _LOCAL_LOCKS_GUARD:_LOCAL_LOCKS.discard(name)
                kernel32.ReleaseMutex(handle)
            kernel32.CloseHandle(handle)
        return
    # Keep a stable Unix lock-file inode; flock is released on process exit.
    stream=path.open('a+b');acquired=False
    try:
        stream.seek(0,os.SEEK_END)
        if stream.tell()==0:stream.write(b'\0');stream.flush()
        stream.seek(0)
        try:
            import fcntl
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            acquired=True
        except OSError as exc:
            busy={errno.EACCES,errno.EAGAIN,getattr(errno,'EDEADLK',-1)}
            if exc.errno in busy:raise FileExistsError(f'Ledger is locked: {path}') from exc
            raise
        yield
    finally:
        if acquired:
            import fcntl
            fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
        stream.close()


def initialize_ledger(path, count, evidence):
    require(type(count) is int and 0 <= count <= 100 and evidence.strip(), 'Reconciled generation count and evidence required')
    write(path, {'schemaVersion':1,'priorGenerationAttempts':count,'reconciliation':evidence,'jobs':[]}, fresh=True)


def validate_dispatch_context(client, prepared, runtime_identity, bindings_path):
    require(runtime_identity is not None and prepared.get('runtimeIdentity') == runtime_identity,
            'Active runtime differs from the prepared request; prepare again')
    runtime_pins=[runtime_identity.get(name) for name in ('toolchain','migrationReceipt','python')]
    require(all(isinstance(row,dict) and {'path','sha256'}<=set(row) for row in runtime_pins),
            'Active runtime identity is incomplete; prepare again')
    require(all(row in prepared.get('inputs',[]) for row in runtime_pins),
            'Prepared request omits active runtime pins; prepare again')
    verify(runtime_pins)
    current_bindings = pin(bindings_path)
    require(prepared.get('bindings') == current_bindings and current_bindings in prepared.get('inputs', []),
            'Current bindings differ from the prepared request; prepare again')
    verify([current_bindings])
    require(prepared.get('comfyEndpoint') == client.url,
            'Active ComfyUI endpoint differs from the prepared request; prepare again')


def verify_loader_models(client, prepared):
    models=prepared.get('loaderModels',[])
    require(isinstance(models,list),'Prepared Comfy loader model pins are invalid')
    from .comfy_nodes.model_resolution import model_choices,path_identity,validate_bound_loader_nodes
    choices=model_choices(prepared.get('prompt'))
    require(all(isinstance(item,dict) and set(item)=={'category','name','pathIdentity','sha256'} for item in models),
            'Prepared Comfy loader model pins are malformed')
    require([(item['category'],item['name']) for item in models]==choices,
            'Prepared Comfy loader model pins do not exactly match graph loaders')
    validate_bound_loader_nodes(prepared.get('prompt'),models)
    if not models:return
    checkpoints=read(Path(__file__).parent/'checkpoints.json')
    inputs=prepared.get('inputs',[])
    for item in models:
        require(item['sha256']==checkpoints.get(item['name']),
                'Prepared Comfy loader pin differs from the frozen reviewed checkpoint profile')
        matching=[]
        for row in inputs:
            if not isinstance(row,dict) or row.get('sha256')!=item['sha256']:
                continue
            try:
                if path_identity(row['path'])==item['pathIdentity']:matching.append(row)
            except (KeyError,OSError,RuntimeError):
                continue
        require(len(matching)==1,'Prepared Comfy loader pin is missing its exact verified input file')
        verify(matching)
    result=client.request('/headkit/verify-loader-models',{'models':models,'prompt':prepared.get('prompt')})
    require(result=={'verified':True,'count':len(models)},
            'ComfyUI loader resolved checkpoint paths or bytes different from the reviewed pins; install/restart the current adapter and prepare again')


def verify_comfy_runtime(client, prepared):
    expected=validate_comfy_runtime(prepared.get('comfyRuntimeIdentity'),
                                    prepared.get('comfySourceInventory',{}).get('roots'),
                                    prepared.get('comfySourceInventory'))
    actual=client.request('/headkit/runtime-identity')
    actual=validate_comfy_runtime(actual,expected['coveredSourceRoots'],prepared.get('comfySourceInventory'))
    require(actual==expected,
            'Running ComfyUI Python/Torch/CUDA runtime differs from the prepared request; prepare again')
    return actual


def submit(client, ledger, prepared, output, *, runtime_identity=None, bindings_path=None):
    """An uncertain POST stays counted and blocks subsequent dispatch until reconciled."""
    require(bindings_path is not None, 'Prepared bindings are required for dispatch')
    validate_dispatch_context(client, prepared, runtime_identity, bindings_path)
    verify(prepared['inputs']);request_sources(prepared)
    graph = prepared['prompt']; info = client.request('/object_info')
    require(all(n['class_type'] in info for n in graph.values()), 'Install/restart missing nodes before dispatch')
    with locked(ledger):
        state = read(ledger)
        require(not any(j['state'] in ('intent','submitted','timed-out') for j in state['jobs']), 'Reconcile the outstanding job first')
        require(client.idle(), 'Shared queue is busy; leave its jobs untouched')
        count = state['priorGenerationAttempts'] + sum(j['stage']=='geometry' and j['state']!='preflight-rejected' for j in state['jobs'])
        require(prepared['stage'] != 'geometry' or count < 100, '100 generation attempts reached')
        request_sources(prepared)
        token = prepared['token']
        require(not any(j['token']==token for j in state['jobs']), 'This prepared request was already submitted')
        job = {'token':token,'state':'intent','stage':prepared['stage'],'requestSha256':digest(prepared),'started':time.time()}
        # Reserve the immutable local receipt before publishing a counted ledger intent.
        # Its exclusive create prevents a known path collision from stranding an unsent job.
        write(Path(output)/'submission-intent.json', {'prepared':prepared,'job':job}, fresh=True)
        state['jobs'].append(job); write(ledger,state)
        try:
            verify(prepared['inputs']);request_sources(prepared);verify_comfy_runtime(client,prepared);verify_loader_models(client,prepared)
        except Exception as exc:
            job.update(state='preflight-rejected',preflightError=str(exc))
            write(ledger,state)
            write(Path(output)/'submission-preflight-error.json',{'error':str(exc),'token':token},fresh=True)
            raise
        try:
            response = client.request('/prompt', {'prompt':graph,'client_id':token,'extra_data':{'headkitToken':token}})
        except urllib.error.HTTPError as exc:
            body=exc.read(262144).decode('utf-8',errors='replace')
            write(Path(output)/'submission-http-error.json',{'status':exc.code,'body':body},fresh=True)
            try:failure=json.loads(body)
            except ValueError:failure={}
            if exc.code==400 and isinstance(failure,dict) and failure.get('error') and not failure.get('prompt_id'):
                job.update(state='rejected',httpStatus=400);write(ledger,state)
            raise
        require(response.get('prompt_id') and not response.get('node_errors'), 'Rejected/uncertain request; reconcile intent')
        job.update(state='submitted', promptId=response['prompt_id']); write(ledger,state)
        write(Path(output)/'submission.json',job,fresh=True)
    return job


def _record_collection(ledger, token, output, result):
    # Save immutable evidence before atomically publishing its pin and terminal state.
    with locked(ledger):
        state=read(ledger);job=next(j for j in state['jobs'] if j['token']==token)
        require(job['state'] in ('submitted','timed-out') and not job.get('collection'),
                'Collection already terminal; preserve the original receipt')
        target=output/'collection.json'
        if target.exists():
            existing=read(target)
            stable=('state','token','promptId','error','outputs','inputs','history','memorySamples','comfySourceInventory','comfyRuntimeIdentity')
            require(all(existing.get(key)==result.get(key) for key in stable
                        if key in existing or key in result),'Existing partial collection receipt differs; preserve it for investigation')
            verify([existing['history'],existing['memorySamples'],*existing.get('inputs',[]),*existing.get('outputs',[])])
            result=existing
        else:write(target,result,fresh=True)
        job.update(state=result['state'],collection=pin(target));write(ledger,state)
    return result


def collect(client, ledger, token, output_root, output, *, wait=False):
    output=Path(output).resolve()
    with locked(ledger):
        state=read(ledger); jobs=[j for j in state['jobs'] if j['token']==token]
        require(len(jobs)==1 and jobs[0].get('promptId'), 'Missing prompt acknowledgement; use reconciliation')
        job=jobs[0]
        if job.get('collection'):
            require(Path(job['collection']['path']).resolve()==output/'collection.json',
                    'Use the original collection directory; receipt is immutable')
            verify([job['collection']]);result=read(job['collection']['path'])
            require(result['state']==job['state'] and result['promptId']==job['promptId'] and result['token']==token,
                    'Collection receipt does not match its job')
            verify([result['history'],result['memorySamples'],*result.get('inputs',[]),*result.get('outputs',[])])
            if result['state']!='failed-validation':verify_sources(result.get('comfySourceInventory'))
            return result
        require(job['state'] in ('submitted','timed-out'),
                'Terminal job has no pinned collection; preserve its historical evidence')
    samples=[]
    while True:
        if wait:
            try:
                devices=client.request('/system_stats').get('devices',[])
                samples.append({'timestamp':time.time(),'devices':[{k:d.get(k) for k in ('name','type','vram_total','vram_free','torch_vram_total','torch_vram_free')} for d in devices]})
            except OSError:samples.append({'timestamp':time.time(),'unavailable':True})
        found=client.request('/history/'+job['promptId']).get(job['promptId'])
        if found: break
        if time.time()-job['started'] > 2700:
            with locked(ledger):
                state=read(ledger); next(j for j in state['jobs'] if j['token']==token)['state']='timed-out';write(ledger,state)
            raise ValueError('45-minute deadline; job remains unresolved. Inspect/cancel only your own job before another submission')
        if not wait: return {'state':'running','promptId':job['promptId']}
        time.sleep(5)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    history_path=output/'history.json'
    if history_path.exists():require(read(history_path)==found,'Existing partial Comfy history differs; preserve it for investigation')
    else:write(history_path,found,fresh=True)
    samples_path=output/'memory-samples.json'
    if samples_path.exists():
        memory_evidence=read(samples_path)
        require(isinstance(memory_evidence,dict) and isinstance(memory_evidence.get('samples'),list)
                and memory_evidence.get('scope')=='collect monitoring window only; sampled device occupancy, not exact process peak',
                'Existing partial memory evidence is invalid; preserve it for investigation')
    else:
        memory_evidence={'samples':samples,'scope':'collect monitoring window only; sampled device occupancy, not exact process peak'}
        write(samples_path,memory_evidence,fresh=True)
    try:
        intent=read(output/'submission-intent.json')
        require(intent['job']['token']==token and digest(intent['prepared'])==job['requestSha256'],'Submission receipt mismatch')
        verify(intent['prepared']['inputs']);request_sources(intent['prepared'])
        success=found.get('status',{}).get('status_str')=='success'
        pins=[]
        if success:
            base=Path(output_root).resolve()
            def visit(value):
                if isinstance(value,dict):
                    if set(value)>={'filename','subfolder','type'}:
                        require(value['type']=='output','Only durable output artifacts may be collected')
                        path=(base/value['subfolder']/value['filename']).resolve()
                        require(path.is_relative_to(base/'headkit'/token), 'Output is outside the owned run prefix')
                        require(path.is_file(),'Comfy output missing');pins.append(pin(path))
                    else:
                        for v in value.values():visit(v)
                elif isinstance(value,list):
                    for v in value:visit(v)
            visit(found.get('outputs',{}))
            require(pins,'No exported files found in history')
            expected=intent['prepared'].get('expectedGeometry')
            if expected:
                from .gltf import load,arrays
                import numpy as np
                candidates=[p for p in pins if Path(p['path']).suffix=='.glb' and Path(p['path']).name.startswith('node-961_')]
                require(len(candidates)==1,'Exactly one saved-shape mesh required')
                aa=arrays(*load(Path(expected['path']).read_bytes()))[:2]
                bb=arrays(*load(Path(candidates[0]['path']).read_bytes()))[:2]
                require(all(np.array_equal(a,b) for a,b in zip(aa,bb)),'Saved-shape decode mismatch; do not accept appearance')
    except Exception as exc:
        _record_collection(ledger,token,output,{'state':'failed-validation','token':token,'promptId':job['promptId'],
            'error':str(exc),'history':pin(output/'history.json'),'memorySamples':pin(output/'memory-samples.json')})
        raise
    verify(intent['prepared']['inputs']);verify(pins)
    result={'state':'complete' if success else 'failed','token':token,'promptId':job['promptId'],'outputs':pins,
            'inputs':[pin(output/'submission-intent.json'),*intent['prepared']['inputs']],'history':pin(output/'history.json'),
            'elapsedSinceSubmissionSeconds':time.time()-job['started'],'memorySamples':pin(output/'memory-samples.json'),
            'comfySourceInventory':intent['prepared']['comfySourceInventory'],
            'comfyRuntimeIdentity':intent['prepared']['comfyRuntimeIdentity']}
    return _record_collection(ledger,token,output,result)


def reconcile(client, ledger, token):
    # Search both queues and retained history by the original client token; never resubmit.
    queue=client.request('/queue'); history=client.request('/history?max_items=1000')
    matches=[]
    for row in queue.get('queue_running',[])+queue.get('queue_pending',[]):
        if len(row)>3 and row[3].get('headkitToken')==token:matches.append(row[1])
    for prompt_id,row in history.items():
        prompt=row.get('prompt',[])
        if len(prompt)>3 and prompt[3].get('headkitToken')==token:matches.append(prompt_id)
    matches=sorted(set(matches));require(len(matches)==1,'Cannot uniquely reconcile; retain intent and inspect server evidence manually')
    with locked(ledger):
        state=read(ledger);job=next(j for j in state['jobs'] if j['token']==token)
        require(job['state'] in ('intent','submitted','timed-out'),'Job is already terminal')
        job.update(promptId=matches[0],state='submitted');write(ledger,state)
    return job


def release(client, ledger):
    # Cooperating headkit processes must share this ledger with submit().
    with locked(ledger):
        state=read(ledger)
        require(not any(j['state'] in ('intent','submitted','timed-out') for j in state['jobs']),
                'Reconcile the outstanding job before releasing models')
        require(client.idle(), 'Shared queue is not idle; leave models resident')
        return client.request('/free', {'unload_models':True,'free_memory':True})
