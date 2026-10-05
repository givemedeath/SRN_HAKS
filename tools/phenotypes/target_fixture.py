"""Prepare native fixture sources against a hash-bound v2 phenotype target.

No runtime body resources are selected here. Native GFF/scripts and isolated
userdir layouts are prepared, but HAK selection and actual client observation
remain mandatory. Existing Human fixture defaults are not changed.
"""
import argparse
import copy
import json
from pathlib import Path
import re
import shutil
import subprocess

from build_test_module import field, structure, torso_inspection_script
import target_contract as contract

POSES = ('pause1','pause2','crouch','kneel','conjure1','conjure2','dead-front','dead-back')
ANIMATIONS = ('ANIMATION_LOOPING_PAUSE','ANIMATION_LOOPING_PAUSE2','ANIMATION_LOOPING_GET_LOW',
              'ANIMATION_LOOPING_WORSHIP','ANIMATION_LOOPING_CONJURE1','ANIMATION_LOOPING_CONJURE2',
              'ANIMATION_LOOPING_DEAD_FRONT','ANIMATION_LOOPING_DEAD_BACK')


def save(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def local(name, kind, value):
    return {'__struct_id':0,'Name':field('cexostring',name),'Type':field('dword',kind),
            'Value':field({1:'int',3:'cexostring'}[kind],value)}


def actors(template, target, profile, palette, alternate_palette):
    """Matched eight-actor scenes differ only in selected body family/name."""
    appearance = target['identity']['appearanceRow'] if profile.startswith(('pilot','troll')) else 6
    race = target['identity']['raceId'] if appearance == target['identity']['appearanceRow'] else 6
    result = []
    for index,pose in enumerate(POSES):
        actor = copy.deepcopy(template); actor.pop('__data_type',None); actor['__struct_id'] = 4
        for key in list(actor):
            if key.startswith('Script'): actor[key] = field('resref','')
        skin = alternate_palette if profile.endswith('-palette') and index % 2 else palette
        actor.update({'Appearance_Type':field('word',appearance),'Race':field('byte',race),
            'Gender':field('byte',0),'Phenotype':field('int',0),
            'FirstName':field('cexolocstring',{'0':profile+' '+pose}),'LastName':field('cexolocstring',{}),
            'Tag':field('cexostring','tm_'+str(index)),'TemplateResRef':field('resref','sr_tm_'+str(index)),
            'FactionID':field('word',2),'Plot':field('byte',0),'Conversation':field('resref',''),
            'Equip_ItemList':field('list',[]),'ItemList':field('list',[]),
            'ScriptSpawn':field('resref','sr_tm_spawn'),'ScriptDamaged':field('resref','sr_tm_damage'),
            'ScriptDeath':field('resref','sr_tm_death'),
            'XPosition':field('float',16+(index%4)*6),'YPosition':field('float',16+(index//4)*8),
            'ZPosition':field('float',0),'XOrientation':field('float',0),'YOrientation':field('float',-1),
            'Color_Skin':field('byte',skin),'Color_Hair':field('byte',5),
            'CurrentHitPoints':field('short',100),'MaxHitPoints':field('short',100),'HitPoints':field('short',100),
            'Int':field('byte',14),'ClassList':field('list',[
                {'__struct_id':2,'Class':field('int',4),'ClassLevel':field('short',5)},
                {'__struct_id':2,'Class':field('int',10),'ClassLevel':field('short',5)}]),
            'VarTable':field('list',[local('TM_POSE',1,index),local('TM_PALETTE',1,skin)])})
        result.append(actor)
    return result


def scripts(profile):
    """Arrival-driven movement, bounded actual combat and real death recovery."""
    cases = '\n'.join('  if(pose=='+str(index)+') return '+animation+';' for index,animation in enumerate(ANIMATIONS))
    spawn = '''int PoseAnimation(int pose) {
CASES
  return ANIMATION_LOOPING_PAUSE;
}
void main() {
  int i; for(i=0;i<18;i++) SetCreatureBodyPart(i,1);
  SetCreatureBodyPart(CREATURE_PART_BELT,0);
  SetCreatureBodyPart(CREATURE_PART_RIGHT_SHOULDER,0);
  SetCreatureBodyPart(CREATURE_PART_LEFT_SHOULDER,0);
  SetCreatureBodyPart(CREATURE_PART_HEAD,1);
  SetColor(OBJECT_SELF,COLOR_CHANNEL_SKIN,GetLocalInt(OBJECT_SELF,"TM_PALETTE"));
  SetColor(OBJECT_SELF,COLOR_CHANNEL_HAIR,5);
  SetLocalLocation(OBJECT_SELF,"HOME",GetLocation(OBJECT_SELF));
  SetImmortal(OBJECT_SELF,TRUE); SetIsDestroyable(FALSE,TRUE,TRUE);
  WriteTimestampedLogEntry("TROLL_FIXTURE_SPAWN actor="+GetTag(OBJECT_SELF)+" appearance="+IntToString(GetAppearanceType(OBJECT_SELF))+" size="+IntToString(GetCreatureSize(OBJECT_SELF))+" palette="+IntToString(GetLocalInt(OBJECT_SELF,"TM_PALETTE")));
  if(GetLocalInt(GetModule(),"TM_MATRIX")) ExecuteScript("sr_tm_next",OBJECT_SELF);
  else ActionPlayAnimation(PoseAnimation(GetLocalInt(OBJECT_SELF,"TM_POSE")),1.0,6000.0);
}
'''.replace('CASES',cases)
    next_script = '''void Mark(string state) {
  vector v=GetPosition(OBJECT_SELF);
  WriteTimestampedLogEntry("TROLL_FIXTURE_ACTION actor="+GetTag(OBJECT_SELF)+" state="+state+" phase="+IntToString(GetLocalInt(OBJECT_SELF,"TM_PHASE"))+" action="+IntToString(GetCurrentAction())+" x="+FloatToString(v.x)+" y="+FloatToString(v.y)+" z="+FloatToString(v.z));
}
void Continue(int phase) {
  if(GetLocalInt(OBJECT_SELF,"TM_PHASE")!=phase) return;
  ClearAllActions(TRUE); ExecuteScript("sr_tm_next",OBJECT_SELF);
}
void Recover(int phase) {
  ApplyEffectToObject(DURATION_TYPE_INSTANT,EffectResurrection(),OBJECT_SELF);
  ApplyEffectToObject(DURATION_TYPE_INSTANT,EffectHeal(1000),OBJECT_SELF);
  SetImmortal(OBJECT_SELF,TRUE); JumpToLocation(GetLocalLocation(OBJECT_SELF,"HOME"));
  Mark("resurrected"); Continue(phase);
}
void main() {
  int phase=GetLocalInt(OBJECT_SELF,"TM_PHASE")+1;
  SetLocalInt(OBJECT_SELF,"TM_PHASE",phase); int step=(phase-1)%13;
  ClearAllActions(TRUE); Mark("phase-start");
  if(step==2 || step==3) {
    location home=GetLocalLocation(OBJECT_SELF,"HOME"); vector out=GetPositionFromLocation(home); out.y+=24.0;
    ActionMoveToLocation(Location(GetArea(OBJECT_SELF),out,90.0),step==3);
    ActionDoCommand(Mark("outward-arrived")); ActionMoveToLocation(home,step==3);
    ActionDoCommand(Mark("home-arrived")); ActionWait(12.0);
    ActionDoCommand(ExecuteScript("sr_tm_next",OBJECT_SELF)); return;
  }
  if(step==4 || step==5) {
    object target=GetLocalObject(OBJECT_SELF,"TARGET");
    if(!GetIsObjectValid(target)) {
      vector v=GetPosition(OBJECT_SELF); v.y+=2.0;
      target=CreateObject(OBJECT_TYPE_CREATURE,"sr_tm_target",Location(GetArea(OBJECT_SELF),v,270.0));
      SetLocalObject(OBJECT_SELF,"TARGET",target); SetImmortal(target,TRUE);
      AssignCommand(target,ClearAllActions(TRUE)); SetCommandable(FALSE,target);
    }
    SetIsTemporaryEnemy(target,OBJECT_SELF);
    if(step==4) { ActionCastSpellAtObject(SPELL_MAGIC_MISSILE,target,METAMAGIC_NONE,TRUE); ActionWait(1.0);
      ActionCastSpellAtObject(SPELL_MAGIC_MISSILE,target,METAMAGIC_NONE,TRUE); ActionWait(12.0);
      ActionDoCommand(ExecuteScript("sr_tm_next",OBJECT_SELF)); }
    else { ActionAttack(target); DelayCommand(24.0,Continue(phase)); }
    return;
  }
  if(step==10) {
    SetImmortal(OBJECT_SELF,FALSE); SetPlotFlag(OBJECT_SELF,FALSE);
    ApplyEffectToObject(DURATION_TYPE_INSTANT,EffectDeath(FALSE,FALSE),OBJECT_SELF);
    object corpse=OBJECT_SELF;
    AssignCommand(GetModule(),DelayCommand(18.0,AssignCommand(corpse,Recover(phase)))); return;
  }
  if(step==11) ApplyEffectToObject(DURATION_TYPE_INSTANT,EffectDamage(3,DAMAGE_TYPE_MAGICAL),OBJECT_SELF);
  int animation=ANIMATION_LOOPING_PAUSE;
  if(step==1) animation=ANIMATION_LOOPING_PAUSE2;
  if(step==6) animation=ANIMATION_LOOPING_GET_LOW;
  if(step==7) animation=ANIMATION_LOOPING_WORSHIP;
  if(step==8) animation=ANIMATION_LOOPING_DEAD_FRONT;
  if(step==9) animation=ANIMATION_LOOPING_DEAD_BACK;
  if(step==11) animation=ANIMATION_LOOPING_TALK_NORMAL;
  if(step==12) animation=ANIMATION_FIREFORGET_BOW;
  ActionPlayAnimation(animation,1.0,18.0); ActionWait(2.0);
  ActionDoCommand(ExecuteScript("sr_tm_next",OBJECT_SELF));
}
'''
    enter = '''void main() {
  object pc=GetEnteringObject(); if(!GetIsPC(pc)) return;
  LockCameraPitch(pc,FALSE); LockCameraDistance(pc,FALSE); SetCameraLimits(pc);
  WriteTimestampedLogEntry("TROLL_FIXTURE_ENTER profile=PROFILE pendingAcceptance=1");
  SendMessageToPC(pc,"Troll fixture: package selection and actual observation determine acceptance.");
  SetLocalInt(GetModule(),"TM_MATRIX",MATRIX);
  int i; for(i=0;i<8;i++) { object actor=GetObjectByTag("tm_"+IntToString(i));
    if(GetIsObjectValid(actor)) AssignCommand(actor,ExecuteScript("sr_tm_spawn",actor)); }
}
'''.replace('PROFILE',profile).replace('MATRIX','1' if profile.endswith('-matrix') else '0')
    if profile == 'pilot':
        camera = torso_inspection_script(['target'+str(index) for index in range(8)],'target0',35.0,6.5,1.65)
        camera = camera.replace('pt_','tm_')
        enter = camera + enter.replace('  int i;', '  StartTorsoInspection(pc);\n  int i;',1)
    return {'sr_tm_spawn':spawn,'sr_tm_next':next_script,'sr_tm_enter':enter,
            'sr_tm_damage':'void main() { WriteTimestampedLogEntry("TROLL_FIXTURE_DAMAGE actor="+GetTag(OBJECT_SELF)+" damage="+IntToString(GetTotalDamageDealt())); }\n',
            'sr_tm_death':'void main() { WriteTimestampedLogEntry("TROLL_FIXTURE_DEATH actor="+GetTag(OBJECT_SELF)); }\n'}


def documents(template, target, profile, palette, alternate_palette):
    specimens = actors(template,target,profile,palette,alternate_palette)
    tiles = [{'__struct_id':1,'Tile_ID':field('int',120),'Tile_Height':field('int',0),
              'Tile_Orientation':field('int',0),**{key:field('byte',value) for key,value in
                {'Tile_AnimLoop1':1,'Tile_AnimLoop2':1,'Tile_AnimLoop3':1,'Tile_MainLight1':0,
                 'Tile_MainLight2':0,'Tile_SrcLight1':0,'Tile_SrcLight2':0}.items()}} for _ in range(64)]
    are = structure('ARE ',Tileset=field('resref','sr_tm'),Width=field('int',8),Height=field('int',8),
            Name=field('cexolocstring',{'0':'Troll phenotype validation'}),Tag=field('cexostring','sr_tm_floor'),
            ResRef=field('resref','sr_tm_floor'),Tile_List=field('list',tiles),Version=field('dword',2),
            Flags=field('dword',4),DayNightCycle=field('byte',0),IsNight=field('byte',0),
            SunAmbientColor=field('dword',0xb0b0b0),SunDiffuseColor=field('dword',0xeeeeee),
            MoonAmbientColor=field('dword',0xb0b0b0),MoonDiffuseColor=field('dword',0xeeeeee),
            FogClipDist=field('float',80),SunShadows=field('byte',1),ShadowOpacity=field('byte',20),SkyBox=field('byte',0))
    git = structure('GIT ',**{'Creature List':field('list',specimens),'Door List':field('list',[]),
            'Placeable List':field('list',[]),'TriggerList':field('list',[]),'WaypointList':field('list',[]),'StoreList':field('list',[])})
    ifo = structure('IFO ',Mod_Name=field('cexolocstring',{'0':'SRN Troll '+profile}),
            Mod_Description=field('cexolocstring',{'0':'Incomplete fixture source preparation; actual client acceptance is pending.'}),
            Mod_Tag=field('cexostring','SRN_TROLL_TEST'),Mod_Version=field('dword',3),
            Mod_MinGameVer=field('cexostring','1.69'),Mod_IsSaveGame=field('byte',0),
            Mod_Entry_Area=field('resref','sr_tm_floor'),Mod_Entry_X=field('float',14),Mod_Entry_Y=field('float',13),
            Mod_Entry_Z=field('float',0),Mod_Entry_Dir_X=field('float',0),Mod_Entry_Dir_Y=field('float',1),
            Mod_Area_list=field('list',[{'__struct_id':6,'Area_Name':field('resref','sr_tm_floor')}]),
            Mod_HakList=field('list',[{'__struct_id':8,'Mod_Hak':field('cexostring','srn_troll_test')}]),
            Mod_CustomTlk=field('cexostring',''),Mod_OnClientEntr=field('resref','sr_tm_enter'),
            Mod_StartYear=field('dword',1372),Mod_StartMonth=field('byte',1),Mod_StartDay=field('byte',1),
            Mod_StartHour=field('byte',12),Mod_DawnHour=field('byte',6),Mod_DuskHour=field('byte',18),
            Mod_MinPerHour=field('byte',2),Mod_XPScale=field('byte',10))
    factions = [{'__struct_id':index,'FactionName':field('cexostring',name),'FactionGlobal':field('word',1),
                 'FactionParentID':field('dword',4294967295)} for index,name in enumerate(('PC','Hostile','Commoner','Merchant','Defender'))]
    reps = [{'__struct_id':i*5+j,'FactionID1':field('dword',i),'FactionID2':field('dword',j),
             'FactionRep':field('dword',0 if {i,j} == {1,2} else 50)} for i in range(5) for j in range(5) if i != j]
    dummy = copy.deepcopy(template)
    for key in list(dummy):
        if key.startswith('Script'): dummy[key] = field('resref','')
    dummy.update({'Appearance_Type':field('word',6),'Race':field('byte',6),'Gender':field('byte',0),
                  'Phenotype':field('int',0),'Tag':field('cexostring','sr_tm_target'),
                  'TemplateResRef':field('resref','sr_tm_target'),'FactionID':field('word',1),'Plot':field('byte',0),
                  'CurrentHitPoints':field('short',300),'MaxHitPoints':field('short',300),'HitPoints':field('short',300),
                  'Equip_ItemList':field('list',[]),'ItemList':field('list',[])})
    return {'module.ifo':ifo,'sr_tm_floor.are':are,'sr_tm_floor.git':git,
            'repute.fac':structure('FAC ',FactionList=field('list',factions),RepList=field('list',reps)),
            'sr_tm_target.utc':dummy}


def user_layout(userdir):
    for name in ('hak','modules','override','logs','currentgame','modelcompiler','localvault','saves'):
        (userdir/name).mkdir(parents=True)
    mapping = {'HD0':'','HAK':'hak','MODULES':'modules','OVERRIDE':'override','LOGS':'logs',
               'CURRENTGAME':'currentgame','MODELCOMPILER':'modelcompiler'}
    (userdir/'nwn.ini').write_text('[Alias]\n'+'\n'.join(key+'='+str(userdir/value) for key,value in mapping.items())+'\n',encoding='utf-8')


def prepare(target_path, baseline, tools, game_root, source_userdir, output, palette=3, alternate_palette=11):
    target_path = Path(target_path).resolve(); target = contract.load(target_path)
    output = Path(output).resolve(); baseline = Path(baseline).resolve(); tools = Path(tools).resolve()
    game_root = Path(game_root).resolve(); source_userdir = Path(source_userdir).resolve()
    contract.require(not output.exists(),'Fresh fixture-preparation directory required')
    contract.require(0 <= palette <= 255 and 0 <= alternate_palette <= 255 and palette != alternate_palette,
                     'Two explicit differing palette indices required')
    contract.require((source_userdir/'override').is_dir() and not any((source_userdir/'override').iterdir()),'Template extraction requires empty override')
    pins = {str(tools/(name+'.exe')):contract.sha(tools/(name+'.exe'))
            for name in ('nwn_resman_cat','nwn_gff','nwn_script_comp','nwn_erf')}
    (output/'inputs').mkdir(parents=True)
    base = ['--root',str(game_root),'--userdirectory',str(source_userdir),'--no-ovr']
    template_path = output/'inputs/nw_humanmerc001.utc'
    template_path.write_bytes(subprocess.run([str(tools/'nwn_resman_cat.exe'),*base,'nw_humanmerc001.utc'],check=True,capture_output=True).stdout)
    template_json = template_path.with_suffix('.utc.json')
    subprocess.run([str(tools/'nwn_gff.exe'),'-i',str(template_path),'-o',str(template_json),'-p'],check=True,capture_output=True)
    template = json.loads(template_json.read_text(encoding='utf-8'))
    contract.require(template['Gender']['value'] == 0 and template['Race']['value'] == 6
                     and template['Phenotype']['value'] == 0, 'Installed source template must be male normal Human')
    set_source = baseline/'ttr01.set'; set_target = output/'inputs/sr_tm.set'
    text = set_source.read_text(encoding='cp1252'); text = re.sub(r'(?m)^Name=TTR01$','Name=SR_TM',text)
    text = re.sub(r'(?m)^Density=[^\n]+','Density=0.000',text); set_target.write_text(text,encoding='cp1252')
    edge = output/'inputs/sr_tm_edge.2da'
    edge.write_bytes(subprocess.run([str(tools/'nwn_resman_cat.exe'),*base,'ttr01_edge.2da'],check=True,capture_output=True).stdout)
    table_pins = {}
    for name in ('appearance.2da','racialtypes.2da','phenotype.2da'):
        source = baseline/'raw'/name; destination = output/'inputs'/name
        shutil.copyfile(source,destination)
        table_pins[name] = {'path':str(destination),'sha256':contract.sha(destination)}
    profiles = ('pilot','troll-poses','troll-palette','troll-matrix','stock-human-comparison','published-human-comparison','troll-comparison')
    prepared = []
    for profile in profiles:
        root = output/profile; userdir = root/'userdir'; user_layout(userdir)
        binary = root/'test-module/module-resources'; binary.mkdir(parents=True)
        json_dir = root/'test-module/json'; json_dir.mkdir(); hak_sources = root/'test-module/hak-resources'; hak_sources.mkdir()
        for path in (set_target,edge): shutil.copyfile(path,hak_sources/path.name)
        docs = documents(template,target,profile,palette,alternate_palette)
        for name,data in docs.items():
            path = json_dir/(name+'.json'); save(path,data)
            subprocess.run([str(tools/'nwn_gff.exe'),'-i',str(path),'-o',str(binary/name)],check=True,capture_output=True)
        for name,text in scripts(profile).items():
            path = binary/(name+'.nss'); path.write_text(text,encoding='ascii')
            result = subprocess.run([str(tools/'nwn_script_comp.exe'),'--root',str(game_root),'--userdirectory',str(userdir),'--no-ovr',str(path)],capture_output=True)
            if result.returncode:
                save(root/'test-module/script-compile-failure.json',{'script':str(path),'scriptSha256':contract.sha(path),
                     'returncode':result.returncode,'stdout':result.stdout.decode(errors='replace'),
                     'stderr':result.stderr.decode(errors='replace'),'clientLaunched':False})
                raise RuntimeError('Native fixture script compilation failed: '+result.stderr.decode(errors='replace'))
            contract.require(path.with_suffix('.ncs').is_file(),'Native script compiler output missing: '+name)
        module = userdir/'modules/srn_troll_test.mod'
        subprocess.run([str(tools/'nwn_erf.exe'),'-c','-f',str(module),'-e','MOD',str(binary)],check=True,capture_output=True)
        actual = root/'test-module/decoded-actors.json'
        subprocess.run([str(tools/'nwn_gff.exe'),'-i',str(binary/'sr_tm_floor.git'),'-o',str(actual),'-p'],check=True,capture_output=True)
        decoded = json.loads(actual.read_text(encoding='utf-8'))['Creature List']['value']
        intended = docs['sr_tm_floor.git']['Creature List']['value']
        contract.require(decoded == intended,'Native GIT serialization changed intended actors')
        specimen_info = [{'tag':row['Tag']['value'],'appearance':row['Appearance_Type']['value'],
                          'race':row['Race']['value'],'gender':row['Gender']['value'],'phenotype':row['Phenotype']['value'],
                          'pose':POSES[index],'palette':row['Color_Skin']['value'],
                          'position':[row[key]['value'] for key in ('XPosition','YPosition','ZPosition')]} for index,row in enumerate(decoded)]
        record = {'schemaVersion':2,'kind':'target-fixture-source',**contract.binding(target_path,target,'runtime'),
                  'profile':profile,'module':str(module),'moduleSha256':contract.sha(module),
                  'userDirectory':str(userdir),'actorAreaResref':'sr_tm_floor','specimens':specimen_info,
                  'moduleResourceHashes':{path.name:contract.sha(path) for path in sorted(binary.iterdir())},
                  'fixtureResourceHashes':{path.name:contract.sha(path) for path in sorted(hak_sources.iterdir())},
                  'stockTableBaselines':table_pins,
                  'configuration':{'cameraLock':False,'bodyStyles':{'fleshParts':1,'head':1,'belt':0,'shoulders':0},
                       'skinIndices':[palette,alternate_palette],'normalStrength':1,'effectiveNativeBodyMaterials':True,
                       'renderSettingsRequired':['ordinary','HQ'],'settingsActuallyObserved':False,
                       'equippedItems':[],'equipmentMatrixPending':True,'minimumObservedGameplaySeconds':900,
                       'movementRouteMetres':24,'arrivalDrivenLocomotion':True},
                  'runtimeBodySource':'published-human' if profile.startswith('published') else 'stock-human' if profile.startswith('stock') else 'troll',
                  'runtimeSelectionPending':True,'hakBuilt':False,'preflightPassed':False,'clientLaunched':False,
                  'clientAccepted':False,'complete':False,'rigPilotAccepted':target['rig']['pilotAccepted'],
                  'pending':['selected runtime body/rig/provisional/equipment','target tables and package hashes',
                             'custom TLK binding when target names are allocated',
                             'supported Computer Use','actual palette/render/motion and 15-minute observations',
                             'PC creation and practical-use terrain/doorway checks'],
                  'limitation':'Native source preparation only. Action schedules and decoded GFF fields do not prove visible behavior or performance.'}
        save(root/'test-module/preparation.json',record); prepared.append(record)
    receipt = {'schemaVersion':2,'kind':'target-fixture-preparation',**contract.binding(target_path,target,'runtime'),
               'profiles':[{'profile':row['profile'],'receipt':str(output/row['profile']/'test-module/preparation.json'),
                            'sha256':contract.sha(output/row['profile']/'test-module/preparation.json')} for row in prepared],
               'sourceTemplate':str(template_path),'sourceTemplateSha256':contract.sha(template_path),'toolPins':pins,
               'sourceTemplateIdentity':{name:template[name]['value'] for name in ('Race','Gender','Phenotype','Appearance_Type')},
               'stockTableBaselines':table_pins,
               'frozenInputs':{str(path):contract.sha(path) for path in (target_path,set_source,Path(__file__).resolve(),
                   Path(__file__).with_name('target_contract.py'),Path(__file__).with_name('build_test_module.py'))},
               'nativeSourceModulesPrepared':True,'runtimeResourcesSelected':False,'clientAccepted':False,'complete':False}
    save(output/'preparation.json',receipt)
    return output/'preparation.json'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('target-contract','stock-baseline','tool-directory','game-root','source-userdir','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--skin-index',type=int,default=3); parser.add_argument('--alternate-skin-index',type=int,default=11)
    args = parser.parse_args(); result = prepare(args.target_contract,args.stock_baseline,args.tool_directory,
        args.game_root,args.source_userdir,args.output,args.skin_index,args.alternate_skin_index)
    print(json.dumps({'receipt':str(result),'receiptSha256':contract.sha(result),'clientAccepted':False}))
