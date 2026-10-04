"""Submit/collect one gated clean-source Comfy retexture without uncertain retries."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import urllib.parse
import urllib.request
import uuid

from pipeline import Comfy
from stage_stock_part import require,sha,save


DISPATCH_RESERVATIONS=Path(__file__).resolve().parents[2]/'output/phenotypes/comfy-dispatch-reservations'


def reserve_dispatch(args,graph,record):
    """Reserve the service/prefix operation, even when the POST outcome is lost."""
    prefixes=sorted(graph[node]['inputs']['filename_prefix'].replace('\\','/').strip('/')
                    for node in record['saveNodes'])
    operation={'service':args.service.rstrip('/'),'savePrefixes':prefixes}
    key=hashlib.sha256(json.dumps(operation,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    DISPATCH_RESERVATIONS.mkdir(parents=True,exist_ok=True)
    path=DISPATCH_RESERVATIONS/(key+'.json')
    reservation={'schemaVersion':1,'state':'reserved-before-prompt',**operation,
        'clientId':'srn-clean-retexture-'+uuid.uuid4().hex,
        'preparation':str(args.preparation.resolve()),'preparationSha256':sha(args.preparation),
        'apiSha256':sha(args.preparation.parent/'workflow-api.json'),
        'destination':str(args.output.resolve()),'reservedAt':datetime.now(timezone.utc).isoformat()}
    try:
        with path.open('x',encoding='utf-8') as handle:
            json.dump(reservation,handle,indent=2);handle.write('\n')
    except FileExistsError:
        raise RuntimeError('Prepared operation/prefix already reserved; recover its history and receipt, '
                           'never resubmit through another output: '+str(path)) from None
    return path,reservation


def prepared(path):
    path=Path(path).resolve();record=json.loads(path.read_text());root=path.parent
    require(record['state']=='prepared-not-submitted' and record['cleanSourceAcceptance'],
            'A template or ungated source cannot be dispatched')
    pins={str(path):sha(path),record['parentApi']:record['parentApiSha256'],
          record['parentGeneration']:record['parentGenerationSha256'],**record['installedDependencies']}
    for relative,pin in record['frozenFiles'].items():
        target=(root/relative).resolve();require(target.is_relative_to(root),'Frozen file escapes preparation')
        pins[str(target)]=pin
    contract=record['cleanSourceAcceptance'];source=contract['source'];accept=contract['acceptance']
    require(accept['sourceSha256']==source['sha256'] and all(accept.get(g) is True for g in
        ('topologyPassed','singleExteriorPassed','gripPreserved','anatomyReviewed','coordinateFramePreserved')),
        'Measured clean-source gates incomplete')
    pins.update({source['localPath']:source['sha256'],source['serverPath']:source['sha256']})
    for receipt in contract['verifiedReceipts']:pins[receipt['path']]=receipt['sha256']
    for reference in record['references']:
        pins.update({reference['localPath']:reference['sha256'],reference['serverPath']:reference['sha256']})
    for filename,pin in pins.items():require(sha(filename)==pin,'Prepared retexture input changed: '+filename)
    graph=json.loads((root/'workflow-api.json').read_text())
    require(len(graph)==record['graphNodes'] and graph['2000']['class_type']=='Load3DAdvanced'
            and graph['2000']['inputs']['model_file']==source['modelFileAnnotated']
            and graph['241']['class_type']=='Get3DComponents'
            and graph['241']['inputs']['model_3d']==['2000',0], 'Actual clean-source loader ownership differs')
    require(not any(n['class_type']=='RemeshMesh' for n in graph.values()),'Rejected remesh must not return')
    require(graph['285']['inputs']['mesh']==['210',0] and '260' not in graph,
            'Final export must preserve the fresh baked normal basis')
    require(record['saveNodes']==['372','2002'] and all(graph[k]['class_type']=='Save3DAdvanced' for k in record['saveNodes']),
            'Exactly two declared fresh texture/UV masters required')
    return record,pins,graph


def submit(args):
    require(args.preparation is not None and not args.output.exists(),
            'Fresh prepared dispatch required; inspect uncertain outcomes without resubmitting')
    record,pins,graph=prepared(args.preparation);service=Comfy(args.service)
    queue=service.request('/queue')
    require(not queue['queue_running'] and not queue['queue_pending'],'Comfy queue occupied')
    reservation_path,reservation=reserve_dispatch(args,graph,record)
    args.output.mkdir(parents=True)
    shutil.copyfile(args.preparation,args.output/'preparation.json')
    shutil.copyfile(args.preparation.parent/'workflow-api.json',args.output/'workflow-api.json')
    shutil.copyfile(__file__,args.output/'executed-runner.py')
    receipt={'schemaVersion':1,'state':'submission-started','service':args.service,
        'submittedAt':datetime.now(timezone.utc).isoformat(),'frozenInputs':pins,
        'preparationSha256':sha(args.output/'preparation.json'),'apiSha256':sha(args.output/'workflow-api.json'),
        'saveNodes':record['saveNodes'],'sourceSha256':record['cleanSourceAcceptance']['source']['sha256'],
        'parentPromptId':json.loads(Path(record['parentGeneration']).read_text())['promptId'],
        'clientId':reservation['clientId'],'dispatchReservation':str(reservation_path.resolve()),
        'dispatchReservationSha256':sha(reservation_path),
        'sourceModified':False,'sourceAdopted':False,'clientLaunched':False,'outputs':[]}
    save(args.output/'generation.json',receipt)
    response=service.request('/prompt',{'prompt':graph,'client_id':receipt['clientId']})
    receipt['response']=response
    if response.get('node_errors') or not response.get('prompt_id'):
        receipt['state']='rejected';save(args.output/'generation.json',receipt);raise RuntimeError(str(response))
    receipt.update(state='queued',promptId=response['prompt_id']);save(args.output/'generation.json',receipt)
    print(json.dumps({'state':receipt['state'],'promptId':receipt['promptId']}))


def status(args):
    path=args.output/'generation.json';receipt=json.loads(path.read_text())
    require(sha(args.output/'preparation.json')==receipt['preparationSha256']
            and sha(args.output/'workflow-api.json')==receipt['apiSha256'],'Dispatch evidence changed')
    require(receipt.get('promptId'),'Uncertain dispatch: inspect history and never blindly resubmit')
    service=Comfy(receipt['service']);history=service.request('/history/'+receipt['promptId'])
    if receipt['promptId'] not in history:
        queue=service.request('/queue')
        print(json.dumps({'state':'queued-or-running','promptId':receipt['promptId'],
            'running':[r[1] for r in queue['queue_running']],'pending':[r[1] for r in queue['queue_pending']]}));return
    result=history[receipt['promptId']];save(args.output/'history.json',result)
    receipt['state']=result['status']['status_str']
    if receipt['state']=='success':
        directory=args.output/'generated';directory.mkdir(exist_ok=True);outputs=[]
        graph=json.loads((args.output/'workflow-api.json').read_text())
        for node in receipt['saveNodes']:
            files=[row for group in result['outputs'][node].values() if isinstance(group,list)
                for row in group if isinstance(row,dict) and row.get('filename','').lower().endswith('.glb')]
            require(len(files)==1,'Exactly one GLB master per declared save required')
            row=files[0]
            prefix=graph[node]['inputs']['filename_prefix'].replace('\\','/')
            parent,basename=prefix.rsplit('/',1)
            require(row.get('type')=='output' and row.get('subfolder','').replace('\\','/').strip('/')==parent
                    and row['filename'].startswith(basename+'_'), 'Collected master is outside its fresh declared prefix')
            query=urllib.parse.urlencode({k:row[k] for k in ('filename','subfolder','type') if k in row})
            with urllib.request.urlopen(service.base+'/view?'+query,timeout=60) as response:payload=response.read()
            require(len(payload)>=20 and payload[:4]==b'glTF','Collected master is not a GLB')
            target=directory/Path(row['filename']).name
            require(target.name not in {Path(r['localPath']).name for r in outputs},'Duplicate generated basename')
            if target.exists():require(target.read_bytes()==payload,'Preserved collected master changed')
            else:target.write_bytes(payload)
            outputs.append({**row,'nodeId':node,'localPath':str(target.resolve()),'sha256':sha(target)})
        receipt['outputs']=outputs
    receipt['errors']=[data for event,data in result['status'].get('messages',[]) if event in ('execution_error','execution_interrupted')]
    save(path,receipt)
    print(json.dumps({'state':receipt['state'],'promptId':receipt['promptId'],'outputs':receipt['outputs'],
                     'errors':[{k:v for k,v in row.items() if k in ('node_id','exception_type','exception_message')} for row in receipt['errors']]}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('submit','status'))
    parser.add_argument('--preparation',type=Path);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--service',default='http://127.0.0.1:8188');args=parser.parse_args()
    args.output=args.output.resolve()
    if args.preparation:args.preparation=args.preparation.resolve()
    {'submit':submit,'status':status}[args.action](args)
