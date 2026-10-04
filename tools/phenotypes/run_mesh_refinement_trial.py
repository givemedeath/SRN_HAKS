"""Dispatch/collect one frozen same-source Comfy remesh diagnostic without retries."""
import argparse
import json
from pathlib import Path
import shutil
import urllib.parse
import urllib.request
import uuid

from pipeline import Comfy
from stage_stock_part import require, sha, save


def pinned_request(path):
    record=json.loads(path.read_text())
    pins={record['source']:record['sourceSha256'],record['serverSource']:record['serverSha256'],
          record['generationReceipt']:record['generationSha256'],record['parentApi']:record['parentApiSha256'],
          record['api']:record['apiSha256'],record['loaderProof']:record['loaderProofSha256'],
          record['liveSchemas']:record['liveSchemasSha256'],**record['installedDependencies']}
    require(record['sourceSha256']==record['serverSha256'], 'Server source differs from retained master')
    for source,pin in pins.items(): require(sha(source)==pin,'Frozen refinement input changed: '+source)
    generation=json.loads(Path(record['generationReceipt']).read_text())
    require(generation['state']=='success' and generation['promptId']==record['originalPromptId']
            and any(row['sha256']==record['sourceSha256'] for row in generation['outputs']),
            'Refinement source is not a collected parent master')
    graph=json.loads(Path(record['api']).read_text())
    require([graph[str(i)]['class_type'] for i in range(1,6)]==
            ['Load3DAdvanced','Get3DComponents','RemeshMesh','MeshToFile3D','Save3DAdvanced']
            and set(graph)=={'1','2','3','4','5'},'Expected scoped same-source remesh graph')
    require(graph['3']['inputs']['sign_mode']=='sdf'
            and {k:v for k,v in graph['3']['inputs'].items() if k!='mesh'}==record['settings'],
            'Remesh settings differ from reviewed request')
    require(graph['2']['inputs']['model_3d']==['1',0]
            and graph['3']['inputs']['mesh']==['2',0]
            and graph['4']['inputs']['mesh']==['3',0]
            and graph['5']['inputs']['model_3d']==['4',0],
            'Remesh graph must consume the retained source and save its result')
    parent=next(row for row in generation['outputs'] if row['sha256']==record['sourceSha256'])
    expected=(parent.get('subfolder','').replace('\\','/').strip('/')+'/'
              +parent['filename']+' ['+parent['type']+']').lstrip('/')
    require(graph['1']['inputs']['model_file'].replace('\\','/')==expected,
            'Loader does not select the retained parent master')
    return record,pins,graph


def submit(a):
    require(a.request is not None and not a.output.exists(),'Fresh request/output required; never repeat uncertain dispatch')
    request,pins,graph=pinned_request(a.request)
    service=Comfy(a.service);queue=service.request('/queue')
    require(not queue['queue_running'] and not queue['queue_pending'],'GPU/Comfy queue occupied')
    a.output.mkdir(parents=True)
    shutil.copyfile(a.request,a.output/'request.json');shutil.copyfile(request['api'],a.output/'workflow-api.json')
    shutil.copyfile(__file__,a.output/'executed-runner.py')
    snapshots={}
    for number,(source,pin) in enumerate(pins.items()):
        if Path(source).suffix.lower()=='.py':
            target=a.output/'frozen-tools'/(str(number)+'-'+Path(source).name)
            target.parent.mkdir(exist_ok=True);shutil.copyfile(source,target)
            require(sha(target)==pin,'Dependency archive differs');snapshots[source]={'archive':str(target.resolve()),'sha256':pin}
    receipt={'state':'submission-started','service':a.service,'requestSha256':sha(a.output/'request.json'),
             'apiSha256':sha(a.output/'workflow-api.json'),'frozenInputs':pins,'executedToolOrigins':snapshots,
             'sourceModified':False,'sourceAdopted':False,'outputs':[],'clientLaunched':False}
    save(a.output/'generation.json',receipt)
    response=service.request('/prompt',{'prompt':graph,'client_id':'srn-mesh-trial-'+uuid.uuid4().hex})
    receipt['response']=response
    if response.get('node_errors') or not response.get('prompt_id'):
        receipt['state']='rejected';save(a.output/'generation.json',receipt)
        raise RuntimeError(str(response))
    receipt.update(state='queued',promptId=response['prompt_id']);save(a.output/'generation.json',receipt)
    print(json.dumps({'state':receipt['state'],'promptId':receipt['promptId']}))


def status(a):
    path=a.output/'generation.json';receipt=json.loads(path.read_text())
    require(sha(a.output/'request.json')==receipt['requestSha256']
            and sha(a.output/'workflow-api.json')==receipt['apiSha256'],'Dispatch evidence changed')
    require(receipt.get('promptId'),'Uncertain submission; inspect history without resubmitting')
    service=Comfy(receipt['service']);history=service.request('/history/'+receipt['promptId'])
    if receipt['promptId'] not in history:
        queue=service.request('/queue');print(json.dumps({'state':'queued-or-running','promptId':receipt['promptId'],
             'running':[r[1] for r in queue['queue_running']],'pending':[r[1] for r in queue['queue_pending']]}));return
    result=history[receipt['promptId']];save(a.output/'history.json',result)
    receipt['state']=result['status']['status_str']
    if receipt['state']=='success':
        items=result['outputs']['5']
        files=[row for group in items.values() if isinstance(group,list)
               for row in group if isinstance(row,dict) and row.get('filename','').lower().endswith('.glb')]
        require(len(files)==1,'Expected one remesh diagnostic master')
        row=files[0];query=urllib.parse.urlencode({k:row[k] for k in ('filename','subfolder','type') if k in row})
        with urllib.request.urlopen(service.base+'/view?'+query,timeout=60) as response:payload=response.read()
        directory=a.output/'generated';directory.mkdir(exist_ok=True)
        target=directory/Path(row['filename']).name
        if target.exists(): require(target.read_bytes()==payload,'Preserved collected diagnostic differs')
        else:target.write_bytes(payload)
        receipt['outputs']=[{**row,'localPath':str(target.resolve()),'sha256':sha(target)}]
    receipt['errors']=[data for event,data in result['status'].get('messages',[])
                       if event in ('execution_error','execution_interrupted')]
    save(path,receipt)
    print(json.dumps({'state':receipt['state'],'promptId':receipt['promptId'],'outputs':receipt['outputs'],
                      'errors':[{k:v for k,v in row.items() if k in ('node_id','exception_type','exception_message')}
                                for row in receipt['errors']]}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('submit','status'));p.add_argument('--request',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--service',default='http://127.0.0.1:8188')
    a=p.parse_args();a.output=a.output.resolve();{'submit':submit,'status':status}[a.action](a)
