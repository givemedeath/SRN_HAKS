"""Execute a frozen pose plan serially, keeping preparation and observation separate."""
import argparse, hashlib, json, subprocess, time
from pathlib import Path

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d): Path(p).write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')

p=argparse.ArgumentParser();p.add_argument('--batch',type=Path,required=True)
p.add_argument('--batch-sha256',required=True);p.add_argument('--start',type=int,default=0)
p.add_argument('--count',type=int,required=True);a=p.parse_args()
assert sha(a.batch)==a.batch_sha256
b=json.loads(a.batch.read_text());root=a.batch.parent
for path,pin in b['frozenInputs'].items(): assert sha(path)==pin,path
for index,plan in list(enumerate(b['renderPlans']))[a.start:a.start+a.count]:
    output=Path(plan['expectedReceipt']).parent
    assert not output.exists(),'Preserve previous execution: '+str(output)
    log=root/(str(index).zfill(2)+'-'+plan['id']+'.render.log')
    started=time.time()
    with log.open('w',encoding='utf-8') as stream:
        result=subprocess.run(plan['argv'],stdout=stream,stderr=subprocess.STDOUT)
    receipt={'planIndex':index,'batchSha256':a.batch_sha256,'plan':plan,'exitCode':result.returncode,
             'startedUnix':started,'seconds':time.time()-started,'log':str(log),'logSha256':sha(log),
             'executorSha256':sha(__file__),'fullBodyReviewed':False}
    if result.returncode==0:
        receipt['imageHashes']={path:sha(path) for path in plan['expectedImages']}
        receipt['renderReceiptSha256']=sha(plan['expectedReceipt'])
    save(root/(str(index).zfill(2)+'-'+plan['id']+'.execution.json'),receipt)
    print(json.dumps({'index':index,'id':plan['id'],'exitCode':result.returncode,'seconds':round(receipt['seconds'],1)}),flush=True)
    assert result.returncode==0,'Inspect actual render log before recovery'
for path,pin in b['frozenInputs'].items(): assert sha(path)==pin,path
