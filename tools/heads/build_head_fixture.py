"""Build ignored native head/body HAKs and an isolated interactive test module."""
import argparse
import copy
from pathlib import Path
import re
import shutil
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'phenotypes'))
from build_test_module import field,structure
from tool_runtime import tool
from head_workflow import model_name,pin,read,require,sha,validate_target,verify_pins,write_fresh
from verify_head_hak import payload,TYPES


SPAWN='''void main() {
  int i; for(i=0;i<18;i++) SetCreatureBodyPart(i,1);
  SetCreatureBodyPart(CREATURE_PART_BELT,0);
  SetCreatureBodyPart(CREATURE_PART_RIGHT_SHOULDER,0);
  SetCreatureBodyPart(CREATURE_PART_LEFT_SHOULDER,0);
  SetCreatureBodyPart(CREATURE_PART_HEAD,GetLocalInt(OBJECT_SELF,"HEAD_SLOT"));
  SetColor(OBJECT_SELF,COLOR_CHANNEL_SKIN,GetLocalInt(OBJECT_SELF,"SKIN_ROW"));
  SetColor(OBJECT_SELF,COLOR_CHANNEL_HAIR,GetLocalInt(OBJECT_SELF,"HAIR_ROW"));
  float scale=GetLocalFloat(OBJECT_SELF,"BODY_VISUAL_SCALE");
  if(scale>0.0) SetObjectVisualTransform(OBJECT_SELF,OBJECT_VISUAL_TRANSFORM_SCALE,scale);
  SetLocalLocation(OBJECT_SELF,"HOME",GetLocation(OBJECT_SELF));
  int helmet=GetLocalInt(OBJECT_SELF,"HEAD_HELMET");
  if(helmet>0){object item=CreateItemOnObject("sr_h_helm"+IntToString(helmet),OBJECT_SELF);ActionEquipItem(item,INVENTORY_SLOT_HEAD);}
  SetIsDestroyable(FALSE,TRUE,TRUE);
  WriteTimestampedLogEntry("HEAD_FIXTURE_SLOT actor="+GetTag(OBJECT_SELF)+" selected="+IntToString(GetCreatureBodyPart(CREATURE_PART_HEAD)));
}'''
HEARTBEAT='''void main() {
  if(!GetLocalInt(GetModule(),"HEAD_TEST_STARTED")) return;
  int n=GetLocalInt(OBJECT_SELF,"HEAD_STEP")+1; SetLocalInt(OBJECT_SELF,"HEAD_STEP",n);
  WriteTimestampedLogEntry("HEAD_FIXTURE_MOTION actor="+GetTag(OBJECT_SELF)+" step="+IntToString(n)+" action="+IntToString(GetCurrentAction()));
  if(GetLocalInt(OBJECT_SELF,"HEAD_HELMET")>0) WriteTimestampedLogEntry("HEAD_FIXTURE_HELMET actor="+GetTag(OBJECT_SELF)+" worn="+GetResRef(GetItemInSlot(INVENTORY_SLOT_HEAD)));
  if(n==1){ClearAllActions();ActionPlayAnimation(ANIMATION_LOOPING_PAUSE2,1.0,6.0);}
  if(n==2){ClearAllActions();ActionPlayAnimation(ANIMATION_LOOPING_TALK_NORMAL,1.0,6.0);}
  if(n==3 || n==5){ClearAllActions();location h=GetLocalLocation(OBJECT_SELF,"HOME");vector v=GetPositionFromLocation(h);v.y+=3.0;
    ActionMoveToLocation(Location(GetArea(OBJECT_SELF),v,90.0),n==5);ActionMoveToLocation(h,n==5);}
  object target=GetObjectByTag("head_target");
  if(n==7){ClearAllActions();ActionCastSpellAtObject(SPELL_MAGIC_MISSILE,target,METAMAGIC_NONE,TRUE,PROJECTILE_PATH_TYPE_DEFAULT,TRUE);}
  if(n==9){ClearAllActions();ActionAttack(target);}
  if(n==11){ClearAllActions();ActionPlayAnimation(ANIMATION_LOOPING_GET_LOW,1.0,6.0);}
  if(n==12){ClearAllActions();ActionPlayAnimation(ANIMATION_LOOPING_WORSHIP,1.0,6.0);}
  if(n==13){ClearAllActions();ActionPlayAnimation(ANIMATION_LOOPING_DEAD_FRONT,1.0,6.0);}
  if(n==14){ClearAllActions();ApplyEffectToObject(DURATION_TYPE_INSTANT,EffectDeath(),OBJECT_SELF);}
}'''


def fixture_identity(config):
    if not config.get('target'):
        require(not config.get('rigAudit'), 'Derived rig requires an explicit target')
        return 'pmh0',6,6,1.0
    verify_pins([config['target']]);target=validate_target(read(config['target']['path']))
    require(target['sex']=='male' and target['bodyManifest']==config['bodyManifest'], 'Fixture body target differs')
    rows={'human':6,'dwarf':0,'elf':1,'orc':5,'troll':2};row=rows[target['race']]
    if target['race']!='human':
        require(bool(config.get('rigAudit')), 'Native fixture rig audit required')
        verify_pins([config['rigAudit']]);audit=read(config['rigAudit']['path'])
        require(audit['passed'] is True and audit['maximumFrameError']<2e-6, 'Native fixture rig audit required')
        serialization=read(audit['serialization']['path'])
        verify_pins([audit['serialization'],audit['binary'],serialization['source'],serialization['output']])
        require(serialization['source']==target['rig'] and serialization['nodeTextPreserved'] is True,
                'Fixture rig differs from the protected body contract')
        require(audit['binary'] in config.get('bodyDependencies',[]), 'Compiled contract rig omitted from fixture')
    scale=target.get('runtimeScale',1.0)
    require(isinstance(scale,(float,int)) and 0<scale<=3, 'Bounded positive fixture visual scale required')
    return target['prefix'],row,row,scale


def make_creature(template,tag,name,x,y,slot,skin,hair,appearance,race,visual_scale,helmet=0):
    item=copy.deepcopy(template)
    item.pop('__data_type', None)
    item['__struct_id'] = 4
    for key in list(item):
        if key.startswith('Script'):item[key]=field('resref','')
    item.update({'Appearance_Type':field('word',appearance),'Race':field('byte',race),'Gender':field('byte',0),'Phenotype':field('int',0),
        'Tag':field('cexostring',tag),'TemplateResRef':field('resref',tag),'FirstName':field('cexolocstring',{'0':name}),
        'LastName':field('cexolocstring',{}),'FactionID':field('word',2),'Plot':field('byte',0),
        'CurrentHitPoints':field('short',100),'MaxHitPoints':field('short',100),'HitPoints':field('short',100),
        'XPosition':field('float',x),'YPosition':field('float',y),'ZPosition':field('float',0),
        'XOrientation':field('float',0),'YOrientation':field('float',1),'ItemList':field('list',[]),'Equip_ItemList':field('list',[]),
        'ScriptSpawn':field('resref','sr_h_spawn'),'ScriptHeartbeat':field('resref','sr_h_hb'),
        'VarTable':field('list',[{'__struct_id':0,'Name':field('cexostring',key),'Type':field('dword',1),'Value':field('int',value)}
                               for key,value in (('HEAD_SLOT',slot),('SKIN_ROW',skin),('HAIR_ROW',hair),('HEAD_HELMET',helmet))])})
    item['VarTable']['value'].append({'__struct_id':0,'Name':field('cexostring','BODY_VISUAL_SCALE'),
        'Type':field('dword',2),'Value':field('float',visual_scale)})
    return item


def build(config_path,output):
    config=read(config_path);require(config['kind']=='srn-head-client-fixture','Explicit fixture configuration required')
    verify_pins(config['inputs']); bank=read(config['candidates']['path']);verify_pins([config['candidates'],config['bodyManifest']])
    require(bank['kind']=='srn-head-native-candidates' and bank['nativeValidated'] is True
            and bank['clientValidated'] is False and bank['productionAccepted'] is False,'Native candidate bank required')
    prefix,appearance,race,visual_scale=fixture_identity(config)
    output=Path(output);require(not output.exists(),'Fresh isolated fixture required')
    user=output/'userdir';stage=output/'module-resources';sources=output/'hak-sources'
    for path in (stage,sources,user/'hak',user/'modules',user/'override'):path.mkdir(parents=True,exist_ok=True)
    def run(name,arguments):
        result=subprocess.run([str(tool(name)),*map(str,arguments)],capture_output=True)
        if result.returncode:
            raise ValueError(name+' failed: '+result.stderr.decode('utf-8',errors='replace')+' '+result.stdout.decode('utf-8',errors='replace'))
        return result.stdout
    def gff(name,document):
        path=output/(name+'.json');write_fresh(path,document);run('nwn_gff',['-i',path,'-o',stage/name])
    heads=sources/'heads';body=sources/'body';floor=sources/'floor'
    for folder in (heads,body,floor):folder.mkdir()
    head_pins=[]
    for design in bank['designs']:
        require(design['model']==model_name(prefix,design['slot']),'Head family differs from fixture body target')
        verify_pins(design['resources']);verify_pins([design['nativeAudit']])
        native_audit=read(design['nativeAudit']['path'])
        require(native_audit['passed'] is True,'Native audit did not pass')
        if config.get('target'):
            verify_pins([native_audit['export']])
            require(read(native_audit['export']['path'])['target']==config['target'], 'Native head uses another body contract')
        for resource in design['resources']:
            source=Path(resource['path']);destination=heads/source.name
            require(not destination.exists(),'Candidate resource collision');shutil.copyfile(source,destination);head_pins.append(pin(destination))
    manifest=read(config['bodyManifest']['path']);repo=Path(config['repository']).resolve()
    for resource in manifest['resources']:
        source=(repo/resource['path']).resolve();require(source.is_relative_to(repo) and sha(source)==resource['sha256'],'Protected body changed')
        shutil.copyfile(source,body/source.name)
    verify_pins(config.get('bodyDependencies',[]))
    for resource in config.get('bodyDependencies',[]):
        source=Path(resource['path']);destination=body/source.name
        require(not destination.exists(), 'Additional body dependency collides with protected resource')
        shutil.copyfile(source,destination)
    for material in body.glob('*.mtr'):
        for texture in re.findall(r'(?m)^texture\d+\s+(\S+)',material.read_text(encoding='ascii')):
            require(any((body/(texture+suffix)).is_file() for suffix in ('.tga','.dds','.plt')),
                    'Body material dependency omitted: '+texture)
    stock=Path(config['stock']);text=(stock/'ttr01.set').read_text(encoding='cp1252')
    text=re.sub(r'(?m)^Name=TTR01$','Name=SR_H_FLOOR',text);text=re.sub(r'(?m)^Density=[^\n]+','Density=0.000',text)
    (floor/'sr_h_floor.set').write_text(text,encoding='cp1252');shutil.copyfile(stock/'ttr01_edge.2da',floor/'sr_h_floor_edge.2da')
    haks=[]
    for name,folder in (('srn_head',heads),('srn_body',body),('sr_h_fixture',floor)):
        path=user/'hak'/(name+'.hak')
        if name=='srn_head' and config.get('headHak'):
            verify_pins([config['headHak']]);shutil.copyfile(config['headHak']['path'],path)
        else:run('nwn_erf',['-c','-f',path,'-e','HAK',folder])
        haks.append(pin(path))
    expected={(Path(p['path']).stem,TYPES[Path(p['path']).suffix[1:]]):p['sha256'] for p in head_pins}
    require(payload(user/'hak/srn_head.hak')==expected,'Candidate head HAK payload differs')
    body_pins=[pin(p) for p in sorted(body.iterdir())]
    expected_body={(Path(p['path']).stem,TYPES[Path(p['path']).suffix[1:]]):p['sha256'] for p in body_pins}
    require(payload(user/'hak/srn_body.hak')==expected_body,'Protected body HAK payload differs')
    template=read(stock/'nw_humanmerc001.utc.json');actors=[];catalog=[]
    def creature(tag,name,x,y,slot,skin,hair,helmet=0):
        return make_creature(template,tag,name,x,y,slot,skin,hair,appearance,race,visual_scale,helmet)
    for design in bank['designs']:
        for skin in (0,3,12):
            for hair in (0,5,21):
                index=len(actors);tag=f'sr_h_actor{index}';actors.append(creature(tag,f'{design["id"]} skin{skin} hair{hair}',16+(index%6)*5,25+(index//6)*7,design['slot'],skin,hair))
                catalog.append({'tag':tag,'designId':design['id'],'slot':design['slot'],'skin':skin,'hair':hair})
        for helmet in (1,2):
            index=len(actors);tag=f'sr_h_actor{index}'
            actors.append(creature(tag,f'{design["id"]} helmet{helmet}',16+(index%6)*5,25+(index//6)*7,design['slot'],3,5,helmet))
            catalog.append({'tag':tag,'designId':design['id'],'slot':design['slot'],'skin':3,'hair':5,'helmet':helmet})
    for helmet in (1,2):
        item=read(stock/f'x2_helm_00{helmet}.uti.json');require(item['BaseItem']['value']==17,'Installed helmet template required')
        name=f'sr_h_helm{helmet}';item.update(TemplateResRef=field('resref',name),Tag=field('cexostring',name),
            PropertiesList=field('list',[]),Identified=field('byte',1))
        gff(name+'.uti',item)
    target=creature('head_target','Stationary combat/spell target',44,48,1,3,5);target['Plot']=field('byte',1)
    target['ScriptHeartbeat']=field('resref','');target['FactionID']=field('word',1);actors.append(target)
    tiles=[{'__struct_id':1,'Tile_ID':field('int',120),'Tile_Height':field('int',0),'Tile_Orientation':field('int',0),
        **{key:field('byte',value) for key,value in {'Tile_AnimLoop1':1,'Tile_AnimLoop2':1,'Tile_AnimLoop3':1,
        'Tile_MainLight1':0,'Tile_MainLight2':0,'Tile_SrcLight1':0,'Tile_SrcLight2':0}.items()}} for _ in range(64)]
    require(config['lighting'] in ('ambient','directional'),'Explicit light profile required')
    ambient,diffuse=(0xc0c0c0,0) if config['lighting']=='ambient' else (0x505050,0xeeeeee)
    area=structure('ARE ',Tileset=field('resref','sr_h_floor'),Width=field('int',8),Height=field('int',8),
        Name=field('cexolocstring',{'0':'Head test floor'}),Tag=field('cexostring','sr_h_floor'),ResRef=field('resref','sr_h_floor'),
        Tile_List=field('list',tiles),Version=field('dword',2),Flags=field('dword',4),DayNightCycle=field('byte',0),IsNight=field('byte',0),
        SunAmbientColor=field('dword',ambient),MoonAmbientColor=field('dword',ambient),SunDiffuseColor=field('dword',diffuse),
        MoonDiffuseColor=field('dword',diffuse),SunShadows=field('byte',int(config['lighting']=='directional')),
        ShadowOpacity=field('byte',20),FogClipDist=field('float',80),SkyBox=field('byte',0))
    git=structure('GIT ',**{'Creature List':field('list',actors),'Door List':field('list',[]),'Placeable List':field('list',[]),
        'TriggerList':field('list',[]),'WaypointList':field('list',[]),'StoreList':field('list',[])})
    ifo=structure('IFO ',Mod_Name=field('cexolocstring',{'0':'SRN Head Pilot'}),Mod_Description=field('cexolocstring',{'0':'Pending client review: slots, palettes, helmets and motions.'}),
        Mod_Tag=field('cexostring','SRN_HEAD_PILOT'),Mod_Version=field('dword',3),Mod_MinGameVer=field('cexostring','1.69'),
        Mod_IsSaveGame=field('byte',0),Mod_Entry_Area=field('resref','sr_h_floor'),Mod_Entry_X=field('float',25),Mod_Entry_Y=field('float',18),
        Mod_Entry_Z=field('float',0),Mod_Entry_Dir_X=field('float',0),Mod_Entry_Dir_Y=field('float',1),
        Mod_Area_list=field('list',[{'__struct_id':6,'Area_Name':field('resref','sr_h_floor')}]),
        Mod_HakList=field('list',[{'__struct_id':8,'Mod_Hak':field('cexostring',name)} for name in ('srn_head','srn_body','sr_h_fixture')]),
        Mod_CustomTlk=field('cexostring',''),Mod_OnClientEntr=field('resref','sr_h_enter'))
    factions=[{'__struct_id':i,'FactionName':field('cexostring',name),'FactionGlobal':field('word',1),
               'FactionParentID':field('dword',4294967295)} for i,name in enumerate(('PC','Hostile','Commoner','Merchant','Defender'))]
    reps=[{'__struct_id':i*5+j,'FactionID1':field('dword',i),'FactionID2':field('dword',j),
           'FactionRep':field('dword',0 if {i,j}=={1,2} else 50)} for i in range(5) for j in range(5) if i!=j]
    fac=structure('FAC ',FactionList=field('list',factions),RepList=field('list',reps))
    for name,document in (('module.ifo',ifo),('sr_h_floor.are',area),('sr_h_floor.git',git),('repute.fac',fac)):gff(name,document)
    scripts={'sr_h_spawn':SPAWN,'sr_h_hb':HEARTBEAT,'sr_h_enter':'''void main(){object p=GetEnteringObject();if(!GetIsPC(p))return;
      SetLocalInt(GetModule(),"HEAD_TEST_STARTED",1);SendMessageToPC(p,"Head pilot: native candidates; client acceptance pending. Reload to repeat motion/death sequence.");
      WriteTimestampedLogEntry("HEAD_FIXTURE_CLIENT_ENTER");}'''}
    for name,text in scripts.items():
        path=stage/(name+'.nss');path.write_text(text,encoding='ascii')
        run('nwn_script_comp',['--root',config['gameRoot'],'--userdirectory',user,'--no-ovr',path])
        require(path.with_suffix('.ncs').is_file(),'Script compiler produced no bytecode')
    module=user/'modules/srn_head_pilot.mod';run('nwn_erf',['-c','-f',module,'-e','MOD',stage])
    verify_pins(config['inputs']);verify_pins([config['candidates'],config['bodyManifest']])
    write_fresh(output/'fixture.json',{'kind':'srn-head-client-fixture-build','config':pin(config_path),'module':pin(module),
        'haks':haks,'actors':catalog,'lighting':config['lighting'],'candidatePayloadVerified':True,
        'bodyPayloadVerified':True,'bodyResources':body_pins,
        'helmetTemplates':[pin(stock/'x2_helm_001.uti.json'),pin(stock/'x2_helm_002.uti.json')],
        'prefix':prefix,'appearanceRow':appearance,'raceId':race,'visualScale':visual_scale,
        'target':config.get('target'),'rigAudit':config.get('rigAudit'),
        'bodyDependencies':config.get('bodyDependencies',[]),
        'clientObserved':False,'productionAccepted':False,'limitation':'Script commands and fixture packaging are not client or anatomy acceptance. Inspect actual equipment logs and rendered helmet cases; character-creation slot selection remains a separate client check.'})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();build(a.config,a.output)
