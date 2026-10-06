"""Build the refreshable SRN gallery without starting an interactive client."""
import argparse
import copy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'heads'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'phenotypes'))
from head_workflow import pin,read,require,verify_pins,write_fresh
from tool_runtime import tool
from catalog import discover,table
from gff import encode


def field(kind,value):return {'type':kind,'value':value}
def document(kind,**values):return {'__data_type':kind,'__struct_id':-1,**values}
def variable(name,value):
    kind='float' if isinstance(value,float) else 'int' if isinstance(value,int) else 'cexostring'
    return {'__struct_id':0,'Name':field('cexostring',name),'Type':field('dword',{'int':1,'float':2,'cexostring':3}[kind]),'Value':field(kind,value)}


def archive(path):
    data=Path(path).read_bytes();require(data[:8] in (b'HAK V1.0',b'MOD V1.0'),'Native archive required')
    count=struct.unpack_from('<I',data,16)[0];keys,resources=struct.unpack_from('<II',data,24)
    require(keys+count*24<=len(data) and resources+count*8<=len(data),'Archive table bounds invalid')
    rows={}
    for i in range(count):
        name,identity,kind=struct.unpack_from('<16sIH',data,keys+i*24);require(identity<count,'Archive resource index invalid')
        offset,size=struct.unpack_from('<II',data,resources+identity*8);require(offset>=160 and offset+size<=len(data),'Archive payload invalid')
        key=(name.split(b'\0')[0].decode('ascii').lower(),kind);require(key not in rows,'Duplicate archive key');rows[key]=data[offset:offset+size]
    return rows


def normalize_archive_date(path,stamp):
    date=datetime.fromisoformat(stamp.replace('Z','+00:00'))
    with Path(path).open('r+b') as stream:
        stream.seek(32);stream.write(struct.pack('<II',date.year-1900,date.timetuple().tm_yday-1))


RESOURCE_TYPES={'.tga':3,'.wav':4,'.plt':6,'.ini':7,'.bmu':8,'.mdl':2002,'.nss':2009,'.ncs':2010,
 '.are':2012,'.set':2013,'.ifo':2014,'.wok':2016,'.2da':2017,'.txi':2022,'.git':2023,'.uti':2025,'.lod':2078,
 '.utc':2027,'.itp':2030,'.dds':2033,'.fac':2038,'.utd':2042,'.utp':2044,'.utm':2051,'.dwk':2052,'.pwk':2053,'.mtr':2072}


def verify_pack(path,resources):
    expected={(Path(row['name']).stem,RESOURCE_TYPES[Path(row['name']).suffix]):row['sha256'] for row in resources}
    actual={}
    with Path(path).open('rb') as stream:
        header=stream.read(160);require(header[:8]==b'HAK V1.0','Native repository HAK required')
        count=struct.unpack_from('<I',header,16)[0];keys,records=struct.unpack_from('<II',header,24)
        stream.seek(keys);key_table=stream.read(count*24);stream.seek(records);resource_table=stream.read(count*8)
        require(len(key_table)==count*24 and len(resource_table)==count*8,'Truncated HAK tables')
        size=Path(path).stat().st_size
        for index in range(count):
            raw,identity,kind=struct.unpack_from('<16sIH',key_table,index*24);require(identity<count,'HAK resource index invalid')
            offset,length=struct.unpack_from('<II',resource_table,identity*8);require(offset>=160 and offset+length<=size,'HAK resource bounds invalid')
            key=(raw.split(b'\0')[0].decode('ascii').lower(),kind);require(key not in actual,'Duplicate repository HAK key')
            stream.seek(offset);digest=hashlib.sha256();remaining=length
            while remaining:
                chunk=stream.read(min(remaining,1024*1024));require(chunk,'Truncated repository HAK payload');digest.update(chunk);remaining-=len(chunk)
            actual[key]=digest.hexdigest()
    require(actual==expected,'Built HAK payload differs from registered sources: '+str(path))
    return {'pack':Path(path).stem,'resourceCount':count,'payloadVerified':True}


def placeable(resref,name,appearance,action='',argument=''):
    return document('UTP ',TemplateResRef=field('resref',resref),Tag=field('cexostring',resref),
        LocName=field('cexolocstring',{'0':name}),Appearance=field('dword',appearance),Static=field('byte',0),
        Useable=field('byte',int(bool(action))),Plot=field('byte',1),HasInventory=field('byte',0),
        Faction=field('dword',2),HP=field('short',100),CurrentHP=field('short',100),
        OnUsed=field('resref','sr_g_control' if action else ''),
        VarTable=field('list',[variable('GG_ACTION',action),variable('GG_ARGUMENT',argument)]))


def area(resref,tileset,tile_ids,width=8,height=8):
    tiles=[{'__struct_id':1,'Tile_ID':field('int',identity),'Tile_Height':field('int',0),'Tile_Orientation':field('int',0),
        **{key:field('byte',value) for key,value in {'Tile_AnimLoop1':1,'Tile_AnimLoop2':1,'Tile_AnimLoop3':1,'Tile_MainLight1':0,'Tile_MainLight2':0,'Tile_SrcLight1':0,'Tile_SrcLight2':0}.items()}}
        for identity in tile_ids]
    require(len(tiles)==width*height,'Complete area tile matrix required')
    return document('ARE ',Tileset=field('resref',tileset),Width=field('int',width),Height=field('int',height),
        Name=field('cexolocstring',{'0':resref}),Tag=field('cexostring',resref.upper()),ResRef=field('resref',resref),
        Tile_List=field('list',tiles),Version=field('dword',2),Flags=field('dword',4),DayNightCycle=field('byte',0),IsNight=field('byte',0),
        SunAmbientColor=field('dword',0x909090),MoonAmbientColor=field('dword',0x909090),SunDiffuseColor=field('dword',0xcccccc),
        MoonDiffuseColor=field('dword',0xcccccc),SunShadows=field('byte',1),ShadowOpacity=field('byte',20),FogClipDist=field('float',160),SkyBox=field('byte',0))


def empty_git():
    return document('GIT ',**{key:field('list',[]) for key in ('Creature List','Door List','Placeable List','TriggerList','WaypointList','StoreList')})


def source_inputs(repository,config,binding):
    tools=Path(__file__).resolve().parents[1]
    paths=[Path(config),Path(binding),Path(repository)/'hakbuilder.json',tools/'heads/head_workflow.py',tools/'phenotypes/tool_runtime.py',tools/'shared_tools.py',*Path(__file__).parent.glob('*.py'),*Path(__file__).parent.joinpath('scripts').glob('*.nss')]
    c=read(config);b=read(binding);builder=read(Path(repository)/'hakbuilder.json')
    for pack in builder['HakList']:paths.extend(p for p in (Path(repository)/pack['Path']).iterdir() if p.is_file() and not p.name.startswith('.'))
    paths.extend(Path(p['path']) for p in b['inputs'])
    for f in b.get('fixtures',[]):
        paths.append(Path(f['path']));fixture=read(f['path']);paths.append(Path(fixture['config']['path']));paths.extend(Path(v['path']) for v in fixture['haks']+fixture.get('bodyResources',[]))
        paths.extend(Path(v['path']) for v in read(fixture['config']['path'])['inputs'])
        for key in ('target','rigAudit'):
            if fixture.get(key):paths.append(Path(fixture[key]['path']))
    return sorted(set(p.resolve() for p in paths))


def build(repository,config,binding,output):
    repository=Path(repository).resolve();output=Path(output).resolve();require(not output.exists(),'Fresh gallery build directory required')
    c=read(config);b=read(binding);require(c['schemaVersion']==1 and 1<=c['pageSize']<=24,'Supported gallery configuration required')
    require(c['startingCategory'] in ('placeables','doors','items','creatures','music','sounds','skyboxes','tilesets'),'Unknown starting category')
    require(len(c['prestaged'])<=24,'Starting area supports at most 24 prestaged entries')
    snapshot_path=os.environ.get('SRN_VERIFIED_INPUTS');snapshot=read(snapshot_path) if snapshot_path else None
    if snapshot:require(snapshot['kind']=='verified-shared-input-snapshot','Wrong launcher snapshot')
    hashes=snapshot['files'] if snapshot else None
    def consumed_pin(path):
        key=str(Path(path).resolve())
        if hashes is None:return pin(path)
        require(key in hashes,'Consumed input missing from launcher declaration: '+key)
        return {'path':key,'sha256':hashes[key]}
    def checked(pins):
        if hashes is None:verify_pins(pins)
        else:
            for row in pins:require(consumed_pin(row['path'])['sha256']==row['sha256'],'Input differs from binding: '+row['path'])
    checked(b['inputs'])
    if b.get('fixtures'):checked(b['fixtures'])
    inputs=[consumed_pin(p) for p in source_inputs(repository,config,binding)]
    catalog=discover(repository,c,hashes);stage=output/'module';overlay=output/'overlay';user=output/'user'
    for p in (stage,overlay,user/'hak',user/'modules'):p.mkdir(parents=True)
    def put(name,doc):(stage/name).write_bytes(encode(doc))
    def run(name,args):
        result=subprocess.run([str(tool(name)),*[str(v) for v in args]],capture_output=True)
        if result.returncode:raise ValueError(name+' failed: '+result.stdout.decode(errors='replace')+' '+result.stderr.decode(errors='replace'))
    stock=Path(b['stock']);floor=(stock/'ttr01.set').read_text(encoding='cp1252')
    floor=re.sub(r'(?m)^Name=TTR01$','Name=SR_G_FLOOR',floor);floor=re.sub(r'(?m)^Density=[^\n]+','Density=0.000',floor)
    (overlay/'sr_g_floor.set').write_text(floor,encoding='cp1252');shutil.copyfile(stock/'ttr01_edge.2da',overlay/'sr_g_floor_edge.2da')
    for category,filename in (('placeables','placeables.2da'),('doors','genericdoors.2da')):
        additions=[v for v in catalog['entries'][category] if v.get('testOnlyAppearance')]
        if additions:
            columns=[k for k in table(repository/'srn_2da'/filename)[0] if k!='row']
            text=('2DA V2.0\n\n'+' '.join(columns)+'\n').encode('ascii') if category=='doors' else (repository/'srn_2da'/filename).read_bytes()
            for row in additions:
                values={'Label':row['model'],'ModelName':row['model'],'BlockSight':'1','VisibleModel':'1','SoundAppType':'0'}
                text+= ('\n'+str(row['appearance'])+' '+' '.join(values.get(k,'****') for k in columns)).encode('ascii')
            (overlay/filename).write_bytes(text+b'\n')
    music_rows=table(repository/'srn_2da/ambientmusic.2da')
    missing_music=[v for v in catalog['entries']['music'] if v['row'] is None]
    if missing_music:
        music_text=(repository/'srn_2da/ambientmusic.2da').read_bytes()
        columns=[k for k in music_rows[0] if k!='row'];next_row=max(v['row'] for v in music_rows)+1
        for entry in missing_music:
            entry['row']=next_row
            music_text+= ('\n'+str(next_row)+' '+ ' '.join(entry['resref'] if key=='Resource' else '****' for key in columns)).encode('ascii')
            next_row+=1
        (overlay/'ambientmusic.2da').write_bytes(music_text+b'\n')
    types={3:'.tga',6:'.plt',2002:'.mdl',2013:'.set',2017:'.2da',2022:'.txi',2033:'.dds',2072:'.mtr'}
    actors=[];template=read(stock/'nw_humanmerc001.utc.json');heads=[];known_heads=set();overlay_pins=[]
    for fixture_pin in b.get('fixtures',[]):
        f=read(fixture_pin['path']);require(f['candidatePayloadVerified'] and not f['productionAccepted'],'Verified test fixture required')
        if f.get('target'):require(f['bodyPayloadVerified'],'Derived body payload proof required')
        else:
            require(all(v['designId'].startswith('human-male-') for v in f['actors']),'Legacy fixture must be the verified Human pilot')
            f={**f,'prefix':'pmh0','appearanceRow':6,'raceId':6,'visualScale':1.0}
        for hak in f['haks']:
            checked([hak])
            if Path(hak['path']).stem not in ('srn_head','srn_body'):continue
            for (name,kind),payload in archive(hak['path']).items():
                require(kind in types,'Unexpected candidate HAK resource type')
                destination=overlay/(name+types[kind])
                if destination.exists():require(destination.read_bytes()==payload,'Candidate overlay conflict: '+destination.name)
                else:destination.write_bytes(payload)
        for record in f['actors']:
            identity=record['designId']
            if identity in known_heads or 'helmet' in record:continue
            known_heads.add(identity);resref='ggh'+str(len(heads)).zfill(5);head=copy.deepcopy(template)
            for key in list(head):
                if key.startswith('Script'):head[key]=field('resref','')
            head.update(TemplateResRef=field('resref',resref),Tag=field('cexostring',resref),FirstName=field('cexolocstring',{'0':identity+' (test candidate)'}),LastName=field('cexolocstring',{}),
                Appearance_Type=field('word',f['appearanceRow']),Race=field('byte',f['raceId']),Gender=field('byte',0),Phenotype=field('int',0),FactionID=field('word',2),
                ItemList=field('list',[]),Equip_ItemList=field('list',[]),Plot=field('byte',1),ScriptSpawn=field('resref','sr_g_actor'),
                VarTable=field('list',[variable(k,v) for k,v in [('HEAD_SLOT',record['slot']),('SKIN_ROW',3),('HAIR_ROW',5),('BODY_VISUAL_SCALE',float(f['visualScale']))]]))
            put(resref+'.utc',head);actor=copy.deepcopy(head);i=len(actors)
            actor.update(XPosition=field('float',14.+i*12.),YPosition=field('float',30.),ZPosition=field('float',0.),XOrientation=field('float',0.),YOrientation=field('float',1.))
            actors.append(actor);heads.append({'id':'creatures:'+identity,'category':'creatures','kind':'creature','name':identity+' (test candidate)','resref':resref,'clientValidated':False})
    catalog['entries']['creatures'].extend(heads);catalog['heads']=heads
    module_vars=[];areas=[]
    for index,row in enumerate(catalog['entries']['tilesets']):
        pages=[]
        for page,start in enumerate(range(0,len(row['tiles']),64)):
            resref=f'ggt{index:03d}_{page:03d}';ids=row['tiles'][start:start+64];ids+=([ids[0]]*(64-len(ids)))
            put(resref+'.are',area(resref,row['resref'],ids));put(resref+'.git',empty_git());areas.append(resref)
            pages.append({'area':resref,'tiles':row['tiles'][start:start+64]})
        row['pages']=pages;row['option']=pages[0]['area'].upper()
    for category,rows in catalog['entries'].items():
        for index,row in enumerate(rows):
            if row.get('existingBlueprint'):
                source=repository/row['source'];decoded_path=output/('blueprint-'+source.name+'.json')
                run('nwn_gff',['-i',source,'-o',decoded_path]);blueprint=read(decoded_path)
                for key,value in blueprint.items():
                    if key.startswith(('Script','On')) and isinstance(value,dict) and value.get('type')=='resref':blueprint[key]=field('resref','')
                if row['kind']!='item':blueprint['Plot']=field('byte',1)
                if row['kind']=='creature':blueprint['FactionID']=field('word',2)
                if row['kind']=='door' and blueprint.get('Appearance',{}).get('value',0)==0:
                    original=blueprint.get('GenericType',{}).get('value',0)
                    alias=next((v for v in rows if v.get('productionAppearance')==original),None)
                    require(alias is not None,'Door blueprint has no custom inspection alias');blueprint['GenericType']=field('byte',alias['appearance'])
                resref='ggb'+str(list(catalog['entries']).index(category))+str(index).zfill(5)
                blueprint['TemplateResRef']=field('resref',resref);blueprint['Tag']=field('cexostring',resref)
                put(resref+source.suffix,blueprint);row['resref']=resref;row['behaviorSuppressed']=True
            if row.get('appearance') is not None:
                resref=('ggp' if category=='placeables' else 'ggd')+str(index).zfill(5);row['resref']=resref
                if category=='placeables':put(resref+'.utp',placeable(resref,row['name']+' ['+row['model']+']',row['appearance']))
                else:
                    require(row['appearance']<=255,'Native GenericType is an eight-bit door field')
                    put(resref+'.utd',document('UTD ',TemplateResRef=field('resref',resref),Tag=field('cexostring',resref),LocName=field('cexolocstring',{'0':row['name']}),GenericType=field('byte',row['appearance']),Appearance=field('dword',0),Plot=field('byte',1),Faction=field('dword',2),HP=field('short',100),CurrentHP=field('short',100),Locked=field('byte',0)))
            kind={'placeable':64,'door':8,'creature':1,'item':2}.get(row['kind'],0)
            option=row.get('option',str(row['row']) if row.get('row') is not None else '-1')
            name=row['name'].replace('|',' ');record='|'.join([str(kind),row.get('resref',''),name,str(option),row['id']])
            module_vars.append(variable(f'gg_{category}_{index}',record))
            module_vars.append(variable('gg_id_'+row['id'],category+'|'+str(index)))
        module_vars.append(variable('gg_count_'+category,len(rows)))
    categories=list(catalog['entries']);module_vars += [variable('gg_category'+str(i),v) for i,v in enumerate(categories)]
    module_vars += [variable('gg_page_size',c['pageSize']),variable('gg_start_category',c['startingCategory']),variable('gg_prestaged_count',len(c['prestaged']))]
    module_vars += [variable('gg_prestaged'+str(i),identity) for i,identity in enumerate(c['prestaged'])]
    module_vars += [variable('gg_area_'+name,1) for name in ['sr_g_start',*areas]]
    put('gg_button.utp',placeable('gg_button','Gallery control',25,'help'))
    git=empty_git();git['Creature List']=field('list',actors);controls=[]
    actions=[('Previous page','previous',''),('Next page','next',''),('Help','help','')]+[(v.title(),'category',v) for v in categories]
    for i,(name,action,argument) in enumerate(actions):
        control=placeable('gg_button',name,25,action,argument)
        control.update(X=field('float',12.+i%6*12.),Y=field('float',8.+i//6*8.),Z=field('float',0.),Bearing=field('float',0.));controls.append(control)
    git['Placeable List']=field('list',controls);put('sr_g_start.git',git);put('sr_g_start.are',area('sr_g_start','sr_g_floor',[120]*256,16,16));areas.insert(0,'sr_g_start')
    ifo=document('IFO ',Mod_Name=field('cexolocstring',{'0':c['moduleName']}),Mod_Description=field('cexolocstring',{'0':c['description']}),
        Mod_Tag=field('cexostring','SRN_GALLERY'),Mod_Version=field('dword',3),Mod_MinGameVer=field('cexostring','1.69'),Mod_IsSaveGame=field('byte',0),
        Mod_Entry_Area=field('resref','sr_g_start'),Mod_Entry_X=field('float',25.),Mod_Entry_Y=field('float',18.),Mod_Entry_Z=field('float',0.),Mod_Entry_Dir_X=field('float',0.),Mod_Entry_Dir_Y=field('float',1.),
        Mod_Area_list=field('list',[{'__struct_id':6,'Area_Name':field('resref',v)} for v in areas]),
        Mod_HakList=field('list',[{'__struct_id':8,'Mod_Hak':field('cexostring',v)} for v in ['srn_gallery_test',*catalog['haks']]]),
        Mod_CustomTlk=field('cexostring',c['customTlk']),Mod_OnClientEntr=field('resref','sr_g_enter'),Mod_OnPlrChat=field('resref','sr_g_chat'),VarTable=field('list',module_vars))
    put('module.ifo',ifo)
    factions=[{'__struct_id':i,'FactionName':field('cexostring',name),'FactionGlobal':field('word',1),'FactionParentID':field('dword',4294967295)} for i,name in enumerate(('PC','Hostile','Commoner','Merchant','Defender'))]
    reps=[{'__struct_id':i*5+j,'FactionID1':field('dword',i),'FactionID2':field('dword',j),'FactionRep':field('dword',50)} for i in range(5) for j in range(5) if i!=j]
    put('repute.fac',document('FAC ',FactionList=field('list',factions),RepList=field('list',reps)))
    for path in Path(__file__).parent.joinpath('scripts').glob('*.nss'):shutil.copyfile(path,stage/path.name)
    for name in ('sr_g_enter','sr_g_chat','sr_g_control','sr_g_actor'):
        run('nwn_script_comp',['--root',b['gameRoot'],'--userdirectory',user,'--no-ovr',stage/(name+'.nss')]);require((stage/(name+'.ncs')).exists(),'Gallery script did not compile')
    test_hak=user/'hak/srn_gallery_test.hak';run('nwn_erf',['-c','-f',test_hak,'-e','HAK',overlay])
    normalize_archive_date(test_hak,c.get('sourceDateUtc','2026-10-05T00:00:00Z'))
    overlay_audit=verify_pack(test_hak,[{'name':p.name.lower(),'sha256':pin(p)['sha256']} for p in overlay.iterdir()])
    pack_audits=[]
    for name in catalog['haks']:
        source=repository/'output'/(name+'.hak');require(source.is_file(),'Build the registered HAKs before building the gallery: '+name)
        require(source.resolve() in {Path(v['path']).resolve() for v in b['inputs']},'Registered built HAK must be pinned in the local binding: '+name)
        pack_audits.append(verify_pack(source,[v for v in catalog['resources'] if v['pack']==name]))
        try:os.link(source,user/'hak'/source.name)
        except OSError:shutil.copyfile(source,user/'hak'/source.name)
    tlk=repository/'output'/(c['customTlk']+'.tlk');require(tlk.is_file(),'Build the custom TLK before gallery assembly')
    require(tlk.resolve() in {Path(v['path']).resolve() for v in b['inputs']},'Custom TLK must be pinned in the local binding')
    (user/'tlk').mkdir();shutil.copyfile(tlk,user/'tlk'/tlk.name)
    module=user/'modules/srn_gallery.mod';run('nwn_erf',['-c','-f',module,'-e','MOD',stage])
    normalize_archive_date(module,c.get('sourceDateUtc','2026-10-05T00:00:00Z'))
    # Round-trip the module's startup data using the independent native decoder.
    run('nwn_gff',['-i',stage/'module.ifo','-o',output/'module-roundtrip.json'])
    returned=read(output/'module-roundtrip.json');require(returned['Mod_Entry_Area']['value']=='sr_g_start','Gallery entry changed')
    require(len(returned['Mod_Area_list']['value'])==len(areas),'Gallery area inventory changed')
    require(len(returned['VarTable']['value'])==len(module_vars),'Gallery catalog locals changed')
    for suffix in ('.are','.git','.utc','.utd','.utp'):
        sample=next(stage.glob('*'+suffix),None)
        if sample:
            destination=output/('roundtrip'+suffix+'.json');run('nwn_gff',['-i',sample,'-o',destination])
            if suffix=='.utd':
                decoded=read(destination);require(decoded['GenericType']['type']=='byte' and decoded['Appearance']['type']=='dword','Door blueprint schema differs from the installed game')
    payload=archive(module)
    extension_types={'.are':2012,'.git':2023,'.ifo':2014,'.fac':2038,'.utc':2027,'.uti':2025,'.utp':2044,'.utd':2042,'.nss':2009,'.ncs':2010}
    expected={(p.stem.lower(),extension_types[p.suffix]):p.read_bytes() for p in stage.iterdir()}
    require(payload==expected,'Gallery module resource payload differs from the generated source')
    if hashes is None:verify_pins(inputs)
    catalog['counts']={k:len(v) for k,v in catalog['entries'].items()};catalog['areas']=areas
    write_fresh(output/'catalog.json',catalog)
    report={'kind':'srn-gallery-build','module':pin(module),'testHak':pin(test_hak),'configuration':pin(config),'binding':pin(binding),
        'counts':catalog['counts'],'resourceCount':catalog['resourceCount'],'areas':len(areas),'prestagedHeads':len(heads),
        'scriptsCompiled':True,'moduleRoundTripVerified':True,'modulePayloadVerified':True,'overlayPayload':overlay_audit,'packPayloads':pack_audits,'clientObserved':False,'productionAccepted':False,'inputs':inputs,
        'inputVerification':'shared-launcher-before-and-after' if hashes is not None else 'builder-before-and-after'}
    write_fresh(output/'build.json',report);print(json.dumps({k:report[k] for k in ('module','counts','areas','prestagedHeads','clientObserved')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('repository','config','binding','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--inputs-only',action='store_true');args=parser.parse_args()
    if args.inputs_only:write_fresh(args.output,[pin(p) for p in source_inputs(args.repository,args.config,args.binding)])
    else:build(args.repository,args.config,args.binding,args.output)
