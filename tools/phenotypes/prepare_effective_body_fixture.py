"""Prepare an isolated stock comparator without launching or controlling the game."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from effective_body_contract import validate_effective_body, hashes
from stage_stock_part import require, sha, save


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--converted',type=Path,required=True)
    p.add_argument('--stock-bank',type=Path,required=True)
    p.add_argument('--stock-bank-sha256',required=True)
    p.add_argument('--palette',type=Path,action='append',default=[])
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();source=a.converted.resolve();root=a.output.resolve();bank=a.stock_bank.resolve()
    _,_,current=validate_effective_body(source)
    require(not root.exists(),'Fresh isolated fixture required')
    inventory=bank/'input-inventory.json'
    require(sha(inventory)==a.stock_bank_sha256,'Actual stock/fixture bank changed')
    inputs={str(inventory):sha(inventory),str(source/'effective-material-inventory.json'):sha(source/'effective-material-inventory.json')}
    record=json.loads(inventory.read_text())
    for relative,row in record['files'].items():
        path=(bank/relative).resolve()
        require(path.is_relative_to(bank) and sha(path)==row['sha256'],'Frozen stock bank resource changed')
        inputs[str(path)]=row['sha256']
    root.mkdir();target=root/'human_male_fit/converted';shutil.copytree(source,target)
    palette_bank=root/'stock-palette-supplement';palette_bank.mkdir()
    for path in a.palette:
        path=path.resolve();require(path.suffix=='.plt' and not (palette_bank/path.name).exists(),'Unique actual supplemental palette required')
        inputs[str(path)]=sha(path);shutil.copyfile(path,palette_bank/path.name)
    baseline=root/'baseline';baseline.mkdir()
    for name in ('human-template.json','ttr01.set','ttr01_edge.2da'):
        shutil.copyfile(bank/'fixture'/name,baseline/name)
    save(root/'manifest.json',{'combinations':[{'slug':'human_male_fit','appearance':6,'raceId':6,
        'gender':'male','phenotype':0,'height':1.9339157,'race':'Human','body_type':'Fit'}]})
    helper=Path(__file__).with_name('stock_body_control.py').resolve();inputs[str(helper)]=sha(helper)
    result=subprocess.run([sys.executable,str(helper),'--output',str(root),'--baseline',str(bank/'stock'),
                           '--palette-bank',str(palette_bank)],capture_output=True,text=True)
    require(result.returncode==0,'Stock comparator preparation failed: '+result.stderr.strip())
    require(hashes(target/'resources')==current['resourceHashes'],'Isolated candidate copy changed')
    validate_effective_body(target)
    for path,pin in inputs.items():require(sha(Path(path))==pin,'Fixture input changed during preparation')
    shutil.copyfile(__file__,root/'executed-fixture-preparer.py')
    save(root/'fixture-preparation.json',{'kind':'effective-native-body-stock-fixture','frozenInputs':inputs,
        'candidateInventorySha256':sha(target/'effective-material-inventory.json'),
        'candidateResources':current['resourceHashes'],'completeBodySelected':current['completeBodySelected'],
        'stockComparatorSource':'Actual model bitmap PLTs, with private name-only aliasing',
        'clientLaunched':False,'nativeComparatorPending':True,'overrideEmpty':True,'cameraLocked':False,
        'files':{str(path.relative_to(root)):sha(path) for path in root.rglob('*') if path.is_file()}})
    print(json.dumps({'output':str(root),'candidateParts':len(current['modelParts']),
                      'completeBodySelected':current['completeBodySelected'],'clientLaunched':False}))


if __name__=='__main__':main()
