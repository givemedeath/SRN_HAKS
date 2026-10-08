"""Freeze representative installed held meshes and measure source bounds.

Shared helmet/weapon/shield resources must remain unchanged for other races.
Target socket frames can be reported, but engine item scale and placement
remain client gates rather than assumed geometry acceptance.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import shlex
import subprocess
import numpy as np
from armory_rigid import rigid_frames
from audit_geometry import arrays
from inventory_target_equipment import inspect_model
from pipeline import digest, save_json
import target_contract


def table_rows(path):
    lines=[line.strip() for line in path.read_text(encoding='cp1252').splitlines() if line.strip()]
    if not lines or lines[0]!='2DA V2.0':raise RuntimeError('Unexpected baseitems table')
    start=2 if lines[1].upper().startswith('DEFAULT:') else 1
    headers=shlex.split(lines[start])
    rows={}
    for line in lines[start+1:]:
        values=shlex.split(line)
        if not values or not values[0].isdigit():continue
        if len(values)!=len(headers)+1:raise RuntimeError('Unexpected baseitems row width: '+values[0])
        rows[int(values[0])]={key.lower():value for key,value in zip(headers,values[1:])}
    return rows


def bounds(text):
    _,blocks,frames=rigid_frames(text)
    meshes=[]
    for name,block in blocks.items():
        vertices=np.asarray(arrays(block[3],'verts'),float)
        if not vertices.size:continue
        rendered=re.search(r'(?mi)^\s*render\s+(\S+)',block[3])
        if rendered and rendered[1]=='0':continue
        frame=frames[name];points=vertices@frame[:3,:3].T+frame[:3,3]
        meshes.append(points)
    if not meshes:return None
    points=np.vstack(meshes);low,high=points.min(0),points.max(0)
    return {'minimumModelLocalNwn':low.tolist(),'maximumModelLocalNwn':high.tolist(),
            'extentMeters':(high-low).tolist(),'renderedVertices':len(points)}


def helmet_source_scale(target, inventory, stock_baseline=None):
    gender = target['identity']['gender']
    if stock_baseline is None:
        if gender != 'male' or inventory['sourcePrefix'] != 'pmh0':
            raise ValueError('Female helmet sizing requires fresh installed appearance table measurement')
        return 1.05, None
    baseline_path = Path(stock_baseline).resolve()
    baseline = json.loads(baseline_path.read_text())
    row = next(row for row in baseline['resources'] if row['name'] == 'appearance.2da')
    appearance = baseline_path.parent/'raw/appearance.2da'
    if digest(appearance) != row['sha256']:
        raise ValueError('Installed appearance sizing input changed')
    human = table_rows(appearance)[6]
    key = 'helmet_scale_f' if gender == 'female' else 'helmet_scale_m'
    value = float(human[key])
    if human['label'] != 'Human' or not np.isfinite(value) or value <= 0:
        raise ValueError('Installed Human helmet sizing input invalid')
    return value, {'path':str(appearance),'sha256':digest(appearance),'row':6,'column':key,'value':value}


def freeze(args):
    inventory=json.loads(args.inventory.read_text())
    override=Path(inventory['userDirectory'])/'override'
    if inventory.get('overridesDisabled') is not True or not override.is_dir() or any(override.iterdir()):
        raise ValueError('Held equipment extraction requires an existing empty override directory')
    view=Path(inventory['resourceViewPath'])
    if digest(view)!=inventory['resourceViewSha256']:raise ValueError('Installed source inventory view changed')
    locations={row.split()[0].lower():row for row in view.read_text(encoding='utf-8').splitlines() if row.strip()}
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    raw,ascii_dir=out/'raw',out/'ascii';raw.mkdir();ascii_dir.mkdir()
    baseitems=next(Path(row['rawPath']) for row in inventory['dependencies'] if row['name']=='baseitems.2da')
    declared={row['name']:row for row in inventory['dependencies']}
    if digest(baseitems)!=declared['baseitems.2da']['sha256']:raise RuntimeError('Baseitems input changed')
    rows=table_rows(baseitems)
    weapons=set(inventory['weaponModelInventory'])
    families=[];samples=set()
    for number,row in rows.items():
        prefix=row.get('itemclass','').lower()
        if not prefix.startswith('w') or row.get('modeltype') not in ('1','2'):continue
        names=sorted(name for name in weapons if re.fullmatch(re.escape(prefix)+r'_(?:[bmt]_)?\d{3}\.mdl',name))
        groups={}
        for name in names:
            part=name.split('_')[1] if len(name.split('_'))==3 else 'single'
            groups.setdefault(part,[]).append(name)
        chosen=[min(positive,key=lambda name:int(Path(name).stem.split('_')[-1])) for names in groups.values()
                if (positive:=[name for name in names if int(Path(name).stem.split('_')[-1])>0])]
        families.append({'baseitemRow':number,'label':row['label'],'itemClass':prefix,'modelType':row['modeltype'],
                         'weaponWield':row.get('weaponwield'),'weaponSize':row.get('weaponsize'),
                         'prefAttackDistance':row.get('prefattackdist'),'installedModels':names,'samples':sorted(chosen)})
        samples.update(chosen)
    cat=args.tool_directory/'nwn_resman_cat.exe'
    tools={str(path.resolve()):digest(path) for path in (cat,args.decompiler)}
    base=['--root',inventory['gameRoot'],'--userdirectory',inventory['userDirectory'],'--no-ovr']
    def fetch(name):
        path=raw/name
        data=subprocess.run([str(cat),*base,name],capture_output=True,check=True).stdout
        if not data:raise RuntimeError('Missing held equipment fixture: '+name)
        path.write_bytes(data);target=ascii_dir/name
        if data[:4]==b'\0\0\0\0':subprocess.run([str(args.decompiler),'-d','-e',str(path),str(target)],capture_output=True,check=True)
        else:target.write_bytes(data)
        text=target.read_text(encoding='ascii')
        measured=None;failure=None
        try:measured=bounds(text)
        except RuntimeError as exc:failure=str(exc)
        return {'measurementFailure':failure,'resource':name,'rawPath':str(path),'rawSha256':digest(path),'asciiPath':str(target),
                'asciiSha256':digest(target),'effectiveLocation':locations[name],'bounds':measured,**inspect_model(text)}
    with ThreadPoolExecutor(max_workers=4) as worker:models=list(worker.map(fetch,sorted(samples)))
    shared=[]
    for row in inventory['models']:
        if row['part'] not in ('helmet','shield'):continue
        path=Path(row['asciiPath'])
        if digest(path)!=row['asciiSha256']:raise RuntimeError('Shared equipment source changed: '+path.name)
        measured=None;failure=None
        try:measured=bounds(path.read_text(encoding='ascii'))
        except RuntimeError as exc:failure=str(exc)
        shared.append({'measurementFailure':failure,'resource':row['resource'],'part':row['part'],'sourceSha256':row['asciiSha256'],
                       'bounds':measured})
    target=None
    if args.target_contract:
        data=target_contract.load(args.target_contract)
        if data['rig']['sourcePrefix'] != inventory['sourcePrefix']:raise ValueError('Held inventory and target source families differ')
        helmet_scale,helmet_receipt=helmet_source_scale(data,inventory,getattr(args,'stock_baseline',None))
        socket_names=('head_g','head','lhand_g','rhand_g','lhand','rhand','handconjure','headconjure')
        target={**target_contract.binding(args.target_contract,data,'runtime'),
                'socketFramesNwn':{name:target_contract.frame(data,name,'runtime').tolist() for name in socket_names},
                'rigPilotAccepted':data['rig'].get('pilotAccepted',False),
                'rigMode':target_contract.rig_mode(data),'rigValidated':target_contract.rig_ready(data),
                'helmetScaleRecommendation':{data['identity']['gender']:helmet_scale*data['rig']['runtimeScale'],
                                             'sourceScale':helmet_scale,'installedInput':helmet_receipt,
                                             'basis':'Installed Human '+data['identity']['gender']+' helmet multiplier times declared body runtime scale',
                                             'clientFitAccepted':False},
                'heldItemEngineScale':'unverified','socketPlacementAccepted':False}
    receipt={'schemaVersion':1,'kind':'installed-held-equipment-measurements',
             'sourcePrefix':inventory['sourcePrefix'],'overridesDisabled':True,
             'sourceInventory':{'path':str(args.inventory.resolve()),'sha256':digest(args.inventory)},
             'baseitemsSha256':digest(baseitems),'toolPins':tools,'weaponFamilies':families,'weaponSamples':models,
             'helmetAndShieldBounds':shared,'measurementFailures':[{'resource':row['resource'],'failure':row['measurementFailure']} for row in models+shared if row['measurementFailure']],
             'target':target,'profilesAccepted':False,'clientAccepted':False,
             'limitations':['Bounds are source geometry measurements, not collision or grip proof.',
                            'Shared helmet, weapon and shield model names must not be replaced globally.',
                            'Helmet scaling, weapon grip, shield alignment and inherited motion require literal client review.']}
    for path,value in tools.items():
        if digest(Path(path))!=value:raise RuntimeError('Held fixture tool changed')
    if any(override.iterdir()):raise ValueError('User overrides changed during held extraction')
    save_json(out/'measurements.json',receipt)
    print(json.dumps({'weaponFamilies':len(families),'weaponSamples':len(models),'helmetAndShieldBounds':len(shared),
                      'measurementFailures':len(receipt['measurementFailures']),'targetRevision':target['rigRevision'] if target else None,'profilesAccepted':False}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for field in ('inventory','output','tool-directory','decompiler'):parser.add_argument('--'+field,type=Path,required=True)
    parser.add_argument('--target-contract',type=Path)
    parser.add_argument('--stock-baseline',type=Path,help='Fresh baseline.json supplies actual male/female Human helmet table multiplier')
    freeze(parser.parse_args())


if __name__=='__main__':main()
