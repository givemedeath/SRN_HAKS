"""Freeze actual equipment supermodel chains independently of the body baseline."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from audit_geometry import arrays
from pipeline import digest, save_json
from retarget import NODE


def freeze(args):
    inventory = json.loads(args.inventory.read_text())
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    (out/'raw').mkdir(); (out/'ascii').mkdir()
    animations, resources, visiting = {}, [], set()
    def walk(model):
        if model in animations: return
        if model in visiting: raise RuntimeError('Equipment inheritance cycle: '+model)
        visiting.add(model)
        raw, ascii_path = out/'raw'/(model+'.mdl'), out/'ascii'/(model+'.mdl')
        cmd = [str(args.cat), '--root', inventory['gameRoot'], '--userdirectory', inventory['userDirectory'], '--no-ovr', model+'.mdl']
        data = subprocess.run(cmd,capture_output=True,check=True).stdout
        if not data: raise RuntimeError('Missing equipment supermodel '+model)
        raw.write_bytes(data)
        if data[:4] == b'\0\0\0\0':
            subprocess.run([str(args.decompiler), '-d', '-e', str(raw), str(ascii_path)],capture_output=True,check=True)
        else: ascii_path.write_bytes(data)
        text=ascii_path.read_text(encoding='ascii')
        parent=re.search(r'(?mi)^setsupermodel\s+\S+\s+(\S+)',text)
        parent_name=parent[1].lower() if parent else 'null'
        scale=re.search(r'(?mi)^setanimationscale\s+(\S+)',text)
        clips=[]
        for match in re.finditer(r'(?mis)^newanim\s+(\S+)\s+\S+\s*\n(.*?)^doneanim[^\n]*',text):
            body=match[2]
            length=re.search(r'(?mi)^\s*length\s+(\S+)',body);transition=re.search(r'(?mi)^\s*transtime\s+(\S+)',body)
            clips.append({'name':match[1],'length':float(length[1]) if length else None,
                'transition':float(transition[1]) if transition else None,
                'events':[[float(time),name] for time,name in re.findall(r'(?mi)^\s*event\s+(\S+)\s+(\S+)',body)],
                'sha256':hashlib.sha256(match[0].encode()).hexdigest()})
        meshes=[{'name':b[2],'type':b[1].lower(),'vertices':len(arrays(b[3],'verts')),
                 'skinWeightsPresent':bool(re.search(r'(?mi)^\s*weights\s',b[3]))}
                for b in NODE.finditer(text.split('endmodelgeom')[0]) if arrays(b[3],'verts')]
        animations[model]={'supermodel':parent_name,'animationScale':float(scale[1]) if scale else None,
                           'clips':clips,'sha256':digest(ascii_path),'meshGeometry':meshes,
                           'hasSkinGeometry':any(row['type']=='skin' or row['skinWeightsPresent'] for row in meshes)}
        resources.append({'name':raw.name,'bytes':len(data),'sha256':digest(raw),'rawPath':str(raw),
                          'asciiPath':str(ascii_path),'asciiSha256':digest(ascii_path)})
        if parent_name!='null': walk(parent_name)
        visiting.remove(model)
    roots=sorted(set(row['supermodel'].lower() for row in inventory['models'] if row['supermodel'] and row['supermodel'].lower()!='null'))
    for root in roots: walk(root)
    result={'schemaVersion':1,'kind':'installed-equipment-supermodel-baseline','gameRoot':inventory['gameRoot'],
            'resources':sorted(resources,key=lambda row:row['name']),'animations':animations,
            'equipmentDeclaredSupermodels':roots,'sourceInventory':{'path':str(args.inventory.resolve()),'sha256':digest(args.inventory)},
            'toolPins':{str(args.cat.resolve()):digest(args.cat),str(args.decompiler.resolve()):digest(args.decompiler)},
            'engineObserved':False}
    save_json(out/'baseline.json',result)
    print(json.dumps({'chains':len(animations),'clips':sum(len(row['clips']) for row in animations.values()),
                      'roots':roots,'skinSupermodels':[name for name,row in animations.items() if row['hasSkinGeometry']]}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for field in ('inventory','output','cat','decompiler'): parser.add_argument('--'+field,type=Path,required=True)
    freeze(parser.parse_args())


if __name__=='__main__':main()
