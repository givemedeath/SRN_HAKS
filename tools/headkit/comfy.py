"""Frozen Pixal request compiler and one-at-a-time, crash-safe local dispatch."""
from contextlib import contextmanager
from pathlib import Path
import copy
import json
import os
import time
import urllib.request
import urllib.error
from urllib.parse import urlparse
import uuid
from .common import read, write, require, pin, verify, digest

TEMPLATES = Path(__file__).parent / 'templates'


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
            mapping = {'364':'front','377':'left','378':'back','379':'right'} if stage == 'geometry' else {'1001':'detail'}
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
        with urllib.request.urlopen(request, timeout=30) as response: return json.load(response)

    def idle(self):
        queue = self.request('/queue')
        return not queue.get('queue_running') and not queue.get('queue_pending')


@contextmanager
def locked(ledger):
    path = Path(str(ledger)+'.lock'); path.parent.mkdir(parents=True,exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(descriptor, str(os.getpid()).encode()); os.close(descriptor)
        yield
    finally: path.unlink()


def initialize_ledger(path, count, evidence):
    require(type(count) is int and 0 <= count <= 100 and evidence.strip(), 'Reconciled generation count and evidence required')
    write(path, {'schemaVersion':1,'priorGenerationAttempts':count,'reconciliation':evidence,'jobs':[]}, fresh=True)


def submit(client, ledger, prepared, output):
    """An uncertain POST stays counted and blocks subsequent dispatch until reconciled."""
    verify(prepared['inputs'])
    graph = prepared['prompt']; info = client.request('/object_info')
    require(all(n['class_type'] in info for n in graph.values()), 'Install/restart missing nodes before dispatch')
    with locked(ledger):
        state = read(ledger)
        require(not any(j['state'] in ('intent','submitted','timed-out') for j in state['jobs']), 'Reconcile the outstanding job first')
        require(client.idle(), 'Shared queue is busy; leave its jobs untouched')
        count = state['priorGenerationAttempts'] + sum(j['stage']=='geometry' for j in state['jobs'])
        require(prepared['stage'] != 'geometry' or count < 100, '100 generation attempts reached')
        token = prepared['token']
        require(not any(j['token']==token for j in state['jobs']), 'This prepared request was already submitted')
        job = {'token':token,'state':'intent','stage':prepared['stage'],'requestSha256':digest(prepared),'started':time.time()}
        state['jobs'].append(job); write(ledger,state)
        write(Path(output)/'submission-intent.json', {'prepared':prepared,'job':job}, fresh=True)
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


def collect(client, ledger, token, output_root, output, *, wait=False):
    with locked(ledger):
        state=read(ledger); jobs=[j for j in state['jobs'] if j['token']==token]
        require(len(jobs)==1 and jobs[0].get('promptId'), 'Missing prompt acknowledgement; use reconciliation')
        job=jobs[0]
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
    write(output/'history.json',found)
    write(output/'memory-samples.json',{'samples':samples,'scope':'collect monitoring window only; sampled device occupancy, not exact process peak'})
    try:
        intent=read(output/'submission-intent.json')
        require(intent['job']['token']==token and digest(intent['prepared'])==job['requestSha256'],'Submission receipt mismatch')
        verify(intent['prepared']['inputs'])
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
        with locked(ledger):
            state=read(ledger);next(j for j in state['jobs'] if j['token']==token)['state']='failed-validation';write(ledger,state)
        write(output/'collection.json',{'state':'failed-validation','error':str(exc),'history':pin(output/'history.json')})
        raise
    with locked(ledger):
        state=read(ledger);next(j for j in state['jobs'] if j['token']==token)['state']='complete' if success else 'failed';write(ledger,state)
    result={'state':'complete' if success else 'failed','promptId':job['promptId'],'outputs':pins,'history':pin(output/'history.json'),
            'elapsedSinceSubmissionSeconds':time.time()-job['started'],'memorySamples':pin(output/'memory-samples.json')}
    write(output/'collection.json',result);return result


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
