"""Read installed GFF resource ownership fields; never repair or accept assets."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
from pipeline import digest, save_json


def equipment_claims(document):
    results=[]
    def walk(value,path):
        if isinstance(value,dict):
            def field(key):
                row=value.get(key)
                return row.get('value') if isinstance(row,dict) else None
            base=field('BaseItem')
            if base is not None:
                fields={key:row for key,row in value.items() if key in ('BaseItem','ModelPart1','ModelPart2','ModelPart3','TemplateResRef','Tag') or key.startswith('ArmorPart_')}
                flags=[]
                if base==16 and field('ArmorPart_Robe')==1:flags.append('robe001')
                if base==16 and any(field(key)==255 for key in ('ArmorPart_LShoul','ArmorPart_RShoul')):flags.append('shoulder255')
                if base==17 and field('ModelPart1')==19:flags.append('helmet019')
                # ModelPart1 is a cloakmodel row, not a direct mesh style.
                if base==80 and field('ModelPart1')==10:flags.append('cloak007-table-row10')
                results.append({'path':path,'fields':fields,'diagnosticFlags':flags})
            for key,row in value.items():walk(row,path+'/'+key)
        elif isinstance(value,list):
            for index,row in enumerate(value):walk(row,path+'/'+str(index))
    walk(document,'')
    return results


def freeze(args):
    inventory=json.loads(args.inventory.read_text());output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    raw,js=output/'raw',output/'json';raw.mkdir();js.mkdir()
    view=args.resource_view.read_text();locations={line.split()[0]:line for line in view.splitlines() if line.strip()}
    names=sorted(name for name in locations if Path(name).suffix in ('.uti','.utc'))
    tools=(args.tool_directory/'nwn_resman_cat.exe',args.tool_directory/'nwn_gff.exe')
    pins={str(path.resolve()):digest(path) for path in tools}
    base=['--root',inventory['gameRoot'],'--userdirectory',inventory['userDirectory'],'--no-ovr']
    def fetch(name):
        source,target=raw/name,js/(name+'.json')
        try:
            data=subprocess.run([str(tools[0]),*base,name],capture_output=True,check=True).stdout
            if not data:raise RuntimeError('Empty installed GFF resource')
            source.write_bytes(data)
            subprocess.run([str(tools[1]),'-i',str(source),'-l','gff','-o',str(target),'-k','json','-p'],capture_output=True,check=True)
            document=json.loads(target.read_text(encoding='utf-8'))
            claims=equipment_claims(document)
            return {'resource':name,'rawSha256':digest(source),'jsonSha256':digest(target),'effectiveLocation':locations[name],
                    'itemClaims':claims,'failure':None}
        except Exception as exc:
            return {'resource':name,'failure':str(exc),'itemClaims':[]}
    records=[]
    with ThreadPoolExecutor(max_workers=4) as worker:
        for index,record in enumerate(worker.map(fetch,names),1):
            records.append(record)
            if index%400==0:print(json.dumps({'scanned':index,'total':len(names)}),flush=True)
    matches=[{'resource':r['resource'],'claims':[c for c in r['itemClaims'] if c['diagnosticFlags']]} for r in records if any(c['diagnosticFlags'] for c in r['itemClaims'])]
    failures=[{'resource':r['resource'],'failure':r['failure']} for r in records if r['failure']]
    for path,value in pins.items():
        if digest(Path(path))!=value:raise RuntimeError('GFF scan tool changed')
    result={'schemaVersion':1,'kind':'installed-equipment-gff-source-diagnosis','resourceViewSha256':digest(args.resource_view),
            'sourceInventorySha256':digest(args.inventory),'scanHelperSha256':digest(Path(__file__)),'toolPins':pins,
            'scope':{'uti':sum(n.endswith('.uti') for n in names),'utc':sum(n.endswith('.utc') for n in names),
                     'moduleArchivesScanned':False,'userOverridesDisabled':True},
            'resources':records,'matches':matches,'failures':failures,'acceptance':False,
            'limitations':['No-reference evidence is scoped to effective installed UTI and UTC resources, excluding module archives and scripted creation.',
                           'A table blank or absent row does not authorize dropping a resource from the applicable-style inventory.',
                           'GFF field usage does not prove live engine size, socket placement or texture binding.']}
    save_json(output/'scan.json',result)
    print(json.dumps({'scanComplete':True,'resources':len(records),'matches':len(matches),'failures':len(failures)}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('inventory','resource-view','output','tool-directory'):parser.add_argument('--'+name,type=Path,required=True)
    freeze(parser.parse_args())
