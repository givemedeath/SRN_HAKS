"""Discover gallery entries from the registered HAKs and their production tables."""
import hashlib
import json
from pathlib import Path
import shlex


def table(path):
    raw=Path(path).read_bytes()
    try:text=raw.decode('utf-8-sig')
    except UnicodeDecodeError:text=raw.decode('cp1252')
    lines=text.splitlines()
    rows=[shlex.split(v,comments=False,posix=True) for v in lines[1:] if v.strip() and not v.lstrip().startswith('#')]
    if rows and rows[0][0].upper()=='DEFAULT:':rows.pop(0)
    if not rows:return []
    columns=rows.pop(0);result=[]
    for values in rows:
        if not values[0].isdigit():continue
        if len(values)!=len(columns)+1:raise ValueError(f'Malformed 2DA row {path}:{values[0]}')
        result.append({'row':int(values[0]),**dict(zip(columns,values[1:]))})
    return result


def discover(repository, config):
    repository=Path(repository).resolve();builder=json.loads((repository/'hakbuilder.json').read_text(encoding='utf-8-sig'))
    packs=[];resources=[];owners={}
    for pack in builder['HakList']:
        root=(repository/pack['Path']).resolve()
        if not root.is_relative_to(repository):raise ValueError('HAK source escapes repository')
        packs.append(pack['Name'])
        for path in sorted(root.iterdir()):
            if not path.is_file() or path.name.startswith('.'):continue
            row={'pack':pack['Name'],'path':path.relative_to(repository).as_posix(),'name':path.name.lower(),
                 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}
            resources.append(row);owners.setdefault(row['name'],row)
    entries={key:[] for key in ('placeables','doors','items','creatures','music','sounds','skyboxes','tilesets')}
    used=set()
    for category,filename in (('placeables','placeables.2da'),('doors','genericdoors.2da')):
        production=table(repository/'srn_2da'/filename)
        for row in production:
            model=row['ModelName'].lower()
            if model+'.mdl' not in owners or (category,model) in used:continue
            used.add((category,model));entry={'id':category+':'+model,'name':row['Label'],
                'model':model,'appearance':row['row'],'pack':owners[model+'.mdl']['pack'],'kind':category[:-1]}
            if category=='doors':entry.update(productionAppearance=row['row'],appearance=len(entries[category]),testOnlyAppearance=True)
            entries[category].append(entry)
        next_row=len(entries['doors']) if category=='doors' else max((v['row'] for v in production),default=-1)+1
        appearance_packs=config.get('appearancePacks',{'placeables':['srn_placeable'],'doors':['srn_door']})
        for name,owner in sorted(owners.items()):
            model=Path(name).stem
            if not name.endswith('.mdl') or owner['pack'] not in appearance_packs.get(category,[]) or (category,model) in used:continue
            if next_row>(255 if category=='doors' else 65535):raise ValueError('Gallery appearance exceeds the native field range')
            entries[category].append({'id':category+':'+model,'name':model+' (unregistered test appearance)',
                'model':model,'appearance':next_row,'pack':owner['pack'],'kind':category[:-1],'testOnlyAppearance':True})
            used.add((category,model));next_row+=1
    for category,filename,column,extension in (('music','ambientmusic.2da','Resource','.bmu'),('sounds','ambientsound.2da','Resource','.wav')):
        by_resource={row[column].lower():row for row in table(repository/'srn_2da'/filename)}
        for name,owner in sorted(owners.items()):
            if not name.endswith(extension):continue
            resref=Path(name).stem;row=by_resource.get(resref)
            entries[category].append({'id':category+':'+resref,'name':resref,'resref':resref,'row':row['row'] if row else None,'pack':owner['pack'],'kind':category})
    sky=repository/'srn_2da/skyboxes.2da'
    for row in table(sky):
        if any(row.get(key,'****').lower()+'.mdl' in owners for key in ('DAWN','DAY','DUSK','NIGHT')):
            entries['skyboxes'].append({'id':'skyboxes:'+str(row['row']),'name':row['LABEL'],'row':row['row'],'kind':'skybox'})
    for name,owner in sorted(owners.items()):
        suffix=Path(name).suffix
        if suffix in ('.uti','.utc','.utp','.utd'):
            category={'.uti':'items','.utc':'creatures','.utp':'placeables','.utd':'doors'}[suffix]
            identity=category+':'+Path(name).stem+(':blueprint' if suffix in ('.utp','.utd') else '')
            entries[category].append({'id':identity,'name':Path(name).stem,'resref':Path(name).stem,'source':owner['path'],'pack':owner['pack'],'kind':{'items':'item','creatures':'creature','placeables':'placeable','doors':'door'}[category],'existingBlueprint':True})
        if suffix=='.set':
            import configparser
            parser=configparser.ConfigParser(interpolation=None,strict=False);parser.read(repository/owner['path'],encoding='cp1252')
            tile_ids=[int(section[4:]) for section in parser.sections() if section.startswith('TILE') and section[4:].isdigit()]
            if tile_ids:
                tile_ids=sorted(tile_ids)
                for page,start in enumerate(range(0,len(tile_ids),64)):
                    identity='tilesets:'+Path(name).stem+('' if page==0 else ':page'+str(page+1))
                    entries['tilesets'].append({'id':identity,'name':parser.get('GENERAL','Name',fallback=Path(name).stem)+' - page '+str(page+1),'resref':Path(name).stem,'tiles':tile_ids[start:start+64],'tilePage':page+1,'pack':owner['pack'],'kind':'tileset'})
    extra=config.get('additions',[])
    ids={v['id'] for rows in entries.values() for v in rows}
    for row in extra:
        if row['id'] in ids:raise ValueError('Duplicate gallery addition: '+row['id'])
        category=row['category'];entries[category].append(row);ids.add(row['id'])
    for identity in config.get('prestaged',[]):
        if identity not in ids:raise ValueError('Unknown prestaged gallery entry: '+identity)
    return {'kind':'srn-gallery-catalog','schemaVersion':1,'haks':packs,'resources':resources,'entries':entries,
            'counts':{k:len(v) for k,v in entries.items()},'resourceCount':len(resources),'configuration':config}
