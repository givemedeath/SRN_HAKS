"""Apply the bounded Wave client-fixture corrections to a retained prototype.

Historical: this rebuilds the 10-pair Wave 2 prototype only. It refuses the tracked
15-pair module, which is hand-maintained under test-modules/weapon-waves. Launch it
through launch_shared_tool.py with every file `build` pins declared as an input.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.headkit.common import pin, require, verify
from tools.phenotypes import tool_runtime


def build(source, output, config, controller, start_pair=1, firearm_motion=None):
    source, output = Path(source).resolve(), Path(output).resolve()
    cfg = json.loads(Path(config).read_text(encoding='utf-8-sig'))
    ready = json.loads((source / 'ready.json').read_text(encoding='utf-8-sig'))
    inputs = [pin(config), pin(controller), pin(source / 'ready.json'), ready['module'], cfg['nwscript'],
              pin(source / 'corrected-instances.json'), pin(source / 'inspection-lighting.json')]
    inputs += [pin(p) for p in sorted((source / 'resources').iterdir())]
    if firearm_motion: inputs += [pin(p) for p in sorted(Path(firearm_motion).iterdir())]
    verify(inputs)
    output.mkdir()
    resources = output / 'resources'
    shutil.copytree(source / 'resources', resources)

    tools = {}

    def run(tool, args, cwd=None):
        if tool not in tools: tools[tool] = tool_runtime.tool(tool, inputs=[row['path'] for row in inputs])
        result = subprocess.run([str(tools[tool]), *map(str, args)], cwd=cwd,
                                capture_output=True, timeout=150)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace'))

    def encode(data, target):
        path = output / (target.stem + '.json')
        path.write_text(json.dumps(data))
        run('nwn_gff', ['-i', path, '-o', target])

    def field(kind, value):
        return {'type': kind, 'value': value}

    # Reuse the stock module identity fields already used by phenotype fixtures.
    # Missing Mod_ID leaves invalid identity bytes in native saves.
    phenotype_tools = str(Path(__file__).resolve().parents[1] / 'phenotypes')
    sys.path.insert(0, phenotype_tools)
    try:
        from target_fixture import module_identity
    finally:
        sys.path.remove(phenotype_tools)
    ifo_path = output / 'module.json'
    run('nwn_gff', ['-i', resources / 'module.ifo', '-o', ifo_path])
    ifo = json.loads(ifo_path.read_text(encoding='utf-8-sig'))
    for key, value in module_identity().items():
        ifo.setdefault(key, value)
    encode(ifo, resources / 'module.ifo')

    git = json.loads((source / 'corrected-instances.json').read_text(encoding='utf-8-sig'))
    actors = [a for a in git['Creature List']['value'] if a['Tag']['value'].startswith(('sw1_', 'sw2_'))]
    assert len(actors) == 20
    for actor in actors:
        assert actor['Appearance_Head']['value'] == 1 and actor['BodyPart_Torso']['value'] == 1
        assert any(f['Feat']['value'] == 44 for f in actor['FeatList']['value'])
        actor['ScriptDialogue'] = field('resref', 'sw_review')
        actor['Conversation'] = field('resref', '')
        utc = dict(actor, __data_type='UTC ', __struct_id=-1)
        encode(utc, resources / (actor['Tag']['value'] + '.utc'))
    encode(git, resources / 'sr_it_floor.git')
    area = json.loads((source / 'inspection-lighting.json').read_text(encoding='utf-8-sig'))
    area['SunAmbientColor']['value'] = 0x909090
    area['SunDiffuseColor']['value'] = 0x909090
    area['ShadowOpacity']['value'] = 60
    encode(area, resources / 'sr_it_floor.are')
    # The fixture's sole installed tile (120/ttr01_p03_01) uses this one bitmap.
    # A module-local neutral swatch leaves all weapon/body texture bytes alone.
    assert {t['Tile_ID']['value'] for t in area['Tile_List']['value']} == {120}
    Image.new('RGB', (16, 16), (145, 145, 145)).save(resources / 'ttr01_grass02.tga')
    # Native saves omit module-local SET/2DA/TGA resources. Keep the review
    # tileset in a HAK so a saved game can still resolve its area dependency.
    environment = output / 'environment'
    environment.mkdir()
    for name in ('sr_it_set.set', 'sr_it_set_edge.2da', 'ttr01_grass02.tga'):
        shutil.move(str(resources / name), environment / name)
    run('nwn_erf', ['-c', '-e', 'HAK', '-f', output / 'sw_reviewenv.hak', environment])
    ifo['Mod_HakList']['value'].insert(0, {'__struct_id': 8, 'Mod_Hak': field('cexostring', 'sw_reviewenv')})
    encode(ifo, resources / 'module.ifo')

    script = Path(controller).read_text(encoding='utf-8-sig')
    assert 1 <= start_pair <= 10
    assert script.count('stage=1;') == 1
    script = script.replace('stage=1;', f'stage={start_pair};')
    script = script.replace('SetLocalInt(actor,"SW2_TEST_ACTIVE",0);', 'SetLocalInt(actor,"SW2_TEST_ACTIVE",0);DestroyObject(GetLocalObject(actor,"SW2_TEST_TARGET"));AssignCommand(actor,JumpToLocation(GetLocalLocation(actor,"SW2_START")));')
    script = script.replace('object area=GetArea(actor);vector p=GetPosition(actor);', 'SetLocalLocation(actor,"SW2_START",GetLocation(actor));object area=GetArea(actor);vector p=GetPosition(actor);')
    script = script.replace('DelayCommand(5.0,Finish(actor))', 'DelayCommand(60.0,Finish(actor))')
    script = script.replace('p.x+=2.0', 'int carrier=GetBaseItemType(GetItemInSlot(INVENTORY_SLOT_RIGHTHAND,actor));if(carrier==61||carrier==6||carrier==8||carrier==63)p.y-=6.0;else p.x+=2.0')
    script = script.replace('if(base==8)after=', 'if(base==61)ammo=GetItemInSlot(INVENTORY_SLOT_BULLETS,actor);if(base==6)ammo=GetItemInSlot(INVENTORY_SLOT_BOLTS,actor);if(base==8||base==61||base==6)after=')
    script = script.replace('if(GetBaseItemType(held)==8)before=GetItemStackSize(GetItemInSlot(INVENTORY_SLOT_ARROWS,actor));',
        'if(GetBaseItemType(held)==8)before=GetItemStackSize(GetItemInSlot(INVENTORY_SLOT_ARROWS,actor));if(GetBaseItemType(held)==61)before=GetItemStackSize(GetItemInSlot(INVENTORY_SLOT_BULLETS,actor));if(GetBaseItemType(held)==6)before=GetItemStackSize(GetItemInSlot(INVENTORY_SLOT_BOLTS,actor));')
    script = script.replace('5second bounded action.', '60second bounded visual action.')
    script = script.replace('else {Attack(male);Attack(female);', 'else if(pair!=4) {Attack(male);Attack(female);')
    script = script.replace('void main() {', '''void ShieldRun(object actor) {
 object target=GetLocalObject(actor,"SW2_TEST_TARGET");DestroyObject(target);
 AssignCommand(actor,ClearAllActions(TRUE));location home=GetLocalLocation(actor,"SW2_START");
 vector p=GetPositionFromLocation(home);p.y-=4.0;
 AssignCommand(actor,ActionMoveToLocation(Location(GetArea(actor),p,270.0),TRUE));
 AssignCommand(actor,ActionMoveToLocation(home,TRUE));
}
void ShieldProbe(object actor) {
 SetLocalLocation(actor,"SW2_START",GetLocation(actor));SetLocalInt(actor,"SW2_TEST_ACTIVE",1);
 SetPlotFlag(actor,TRUE);vector p=GetPosition(actor);p.y-=1.5;
 object target=CreateObject(OBJECT_TYPE_CREATURE,"sw2_target",Location(GetArea(actor),p,90.0));
 SetLocalObject(actor,"SW2_TEST_TARGET",target);SetPlotFlag(target,TRUE);SetImmortal(target,TRUE);
 ChangeToStandardFaction(target,STANDARD_FACTION_HOSTILE);SetIsTemporaryEnemy(target,actor);SetIsTemporaryEnemy(actor,target);
 AssignCommand(target,SetCommandable(TRUE));AssignCommand(actor,SetCommandable(TRUE));
 AssignCommand(target,ActionAttack(actor));AssignCommand(actor,ActionAttack(target));DelayCommand(20.0,ShieldRun(actor));
 DelayCommand(35.0,ShieldRun(actor));DelayCommand(60.0,Finish(actor));
 WriteTimestampedLogEntry("SW2_SHIELD_PROBE tag="+GetTag(actor)+" defense_then_run");
}
void main() {''')
    # Keep both reviewers at equal depth; the original camera hid the female
    # behind the PC and cropped the male's hands at the bottom of the window.
    script = script.replace('void main() {', '''void Arrange(object male,object female,object pc,int pair) {
 object m=GetModule();object area=GetArea(male);
 AssignCommand(male,ClearAllActions(TRUE));AssignCommand(female,ClearAllActions(TRUE));
 if(GetLocalInt(m,"SW_PAIR")!=pair+1) {
  object old=GetLocalObject(m,"SW_MALE");if(GetIsObjectValid(old))AssignCommand(old,JumpToLocation(GetLocalLocation(old,"SW_HOME")));
  old=GetLocalObject(m,"SW_FEMALE");if(GetIsObjectValid(old))AssignCommand(old,JumpToLocation(GetLocalLocation(old,"SW_HOME")));
  if(!GetLocalInt(male,"SW_HOME_SET")){SetLocalLocation(male,"SW_HOME",GetLocation(male));SetLocalInt(male,"SW_HOME_SET",1);}
  if(!GetLocalInt(female,"SW_HOME_SET")){SetLocalLocation(female,"SW_HOME",GetLocation(female));SetLocalInt(female,"SW_HOME_SET",1);}
  AssignCommand(male,JumpToLocation(Location(area,Vector(10.8,39.0,0.0),270.0)));
  AssignCommand(female,JumpToLocation(Location(area,Vector(13.2,39.0,0.0),270.0)));
  SetLocalObject(m,"SW_MALE",male);SetLocalObject(m,"SW_FEMALE",female);SetLocalInt(m,"SW_PAIR",pair+1);
 }
 AssignCommand(pc,ClearAllActions(TRUE));AssignCommand(pc,JumpToLocation(Location(area,Vector(12.0,37.0,0.0),90.0)));
 AssignCommand(pc,SetCameraFacing(90.0,5.5,65.0));
}
void main() {''')
    start = script.index('  AssignCommand(pc,ClearAllActions(TRUE));', script.index('if(stage>=1'))
    stop = script.index('\n  if(stage<=10)', start)
    script = script[:start] + '  object male=GetObjectByTag(prefix+"m"+IntToString(index));object female=GetObjectByTag(prefix+"f"+IntToString(index));Arrange(male,female,pc,pair);Report(male);Report(female);' + script[stop:]
    script = script.replace('  if(stage<=10)', '  if(stage>10 && pair==4){DelayCommand(0.5,ShieldProbe(male));DelayCommand(0.5,ShieldProbe(female));}\n  if(stage<=10)')
    assert script.count('ShieldProbe(male)') == 1
    # Defer attacks until queued actor teleports have completed.
    script = script.replace('Attack(male);Attack(female);', 'DelayCommand(0.5,Attack(male));DelayCommand(0.5,Attack(female));')
    script = script.replace('  if(stage<=10)', '''  if(stage>10) {
   DelayCommand(15.0,AssignCommand(pc,SetCameraFacing(45.0,7.0,65.0)));
   DelayCommand(35.0,AssignCommand(pc,SetCameraFacing(135.0,7.0,65.0)));
   DelayCommand(61.0,AssignCommand(pc,SetCameraFacing(90.0,5.5,65.0)));
  }
  if(stage<=10)''')
    if firearm_motion:
        script = '#include "sr_f7_inc"\n' + script
        script = script.replace('void Attack(object actor) {', 'void Attack(object actor) {\n SyncFirearm(actor);')
        # A bounded same-actor swap proves that the custom map is removed for
        # thrown weapons and restored when the Ingram is equipped again.
        script = script.replace('void Finish(object actor) {', '''void RestoreFirearm(object actor) {
 AssignCommand(actor,ClearAllActions(TRUE));
 AssignCommand(actor,ActionEquipItem(GetLocalObject(actor,"SR_F7_ORIGINAL"),INVENTORY_SLOT_RIGHTHAND));
 DelayCommand(0.5,SyncFirearm(actor));
 location home=GetLocalLocation(actor,"SW2_START");vector walk=GetPositionFromLocation(home);walk.y-=3.0;
 DelayCommand(1.0,AssignCommand(actor,ActionMoveToLocation(Location(GetArea(actor),walk,270.0),TRUE)));
 DelayCommand(1.1,AssignCommand(actor,ActionMoveToLocation(home,TRUE)));
}
void SwapToThrow(object actor) {
 SetLocalObject(actor,"SR_F7_ORIGINAL",GetItemInSlot(INVENTORY_SLOT_RIGHTHAND,actor));
 object knife=CreateItemOnObject("sr2273b8c",actor,20);
 AssignCommand(actor,ActionEquipItem(knife,INVENTORY_SLOT_RIGHTHAND));
 DelayCommand(0.5,SyncFirearm(actor));
 DelayCommand(1.0,AssignCommand(actor,ActionPlayAnimation(ANIMATION_LOOPING_PAUSE,1.0,3.0)));
 DelayCommand(5.0,RestoreFirearm(actor));
 if(GetGender(actor)==GENDER_MALE)DelayCommand(7.0,DoSinglePlayerAutoSave());
}
void Finish(object actor) {''')
        script = script.replace('SetLocalInt(actor,"SW2_TEST_ACTIVE",0);DestroyObject',
            'if(base==61 && !GetLocalInt(actor,"SR_F7_SWAP_TEST")){SetLocalInt(actor,"SR_F7_SWAP_TEST",1);DelayCommand(2.0,SwapToThrow(actor));}SetLocalInt(actor,"SW2_TEST_ACTIVE",0);DestroyObject')
    # Module entry can run before the PC has an area. Retry staging without
    # consuming the requested pair; the actors' area owns the review locations.
    anchor = ' if(stage==0) {'
    assert script.count(anchor) == 1
    script = script.replace(anchor, ' if(!GetIsObjectValid(area)){DelayCommand(1.0,ExecuteScript("c",m));return;}\n' + anchor)
    (resources / 'c.nss').write_text(script)
    (resources / 'sw_review.nss').write_text('''void main(){
object m=GetModule();int current=GetLocalInt(m,"SW_PAIR");
if(GetLocalInt(GetLocalObject(m,"SW_MALE"),"SW2_TEST_ACTIVE"))return;
int stage=current+10;
if(OBJECT_SELF==GetLocalObject(m,"SW_MALE"))stage=current%10+1;
else if(OBJECT_SELF!=GetLocalObject(m,"SW_FEMALE")) {
 string tag=GetTag(OBJECT_SELF);stage=StringToInt(GetStringRight(tag,1))+1;
 if(GetStringLeft(tag,4)=="sw2_")stage+=5;
}
SetLocalInt(m,"SW2_FIXED_STAGE",stage);ExecuteScript("c",m);
SendMessageToPC(GetFirstPC(),"Click MALE for next weapon; FEMALE for this pair's 60-second visual action. Shield is visual-only here.");
}''')
    entry = (resources / 'sw2_enter.nss').read_text(encoding='utf-8-sig')
    # The stock TestNewModule Elf wears stock armour over a differently sized
    # custom rig. Use the same supported bare Human Fit assembly as reviewers;
    # unequip, never destroy, the private test character's clothing.
    entry = entry.replace('void main(){', '''void ReviewBody(object pc) {
 SetCreatureAppearanceType(pc,15100);SetPhenoType(0,pc);
 int part;for(part=0;part<18;part++)SetCreatureBodyPart(part,1,pc);
 SetCreatureBodyPart(CREATURE_PART_BELT,0,pc);
 SetCreatureBodyPart(CREATURE_PART_RIGHT_SHOULDER,0,pc);
 SetCreatureBodyPart(CREATURE_PART_LEFT_SHOULDER,0,pc);
}
void main(){''')
    entry = entry.replace('if(!GetIsPC(pc))return;', '''if(!GetIsPC(pc))return;
 if(!GetLocalInt(pc,"SW_REVIEW_BODY")) {
  int slot;for(slot=0;slot<4;slot++) {
   object clothing=GetItemInSlot(slot,pc);if(GetIsObjectValid(clothing))AssignCommand(pc,ActionUnequipItem(clothing));
  }
  object cloak=GetItemInSlot(INVENTORY_SLOT_CLOAK,pc);if(GetIsObjectValid(cloak))AssignCommand(pc,ActionUnequipItem(cloak));
  DelayCommand(0.5,ReviewBody(pc));SetLocalInt(pc,"SW_REVIEW_BODY",1);
 }
''')
    entry = entry.replace('DelayCommand(3.0,ExecuteScript("c",GetModule()));',
        'if(!GetLocalInt(GetModule(),"SW_REVIEW_STARTED")){SetLocalInt(GetModule(),"SW_REVIEW_STARTED",1);DelayCommand(3.0,ExecuteScript("c",GetModule()));}')
    entry = entry.replace('object item=CreateItemOnObject(name,actor', '''if(name=="sre9a211be_3") {object bullets=CreateItemOnObject("nw_wambu001",actor,99);AssignCommand(actor,ActionEquipItem(bullets,INVENTORY_SLOT_BULLETS));}
 if(name=="sra84e4660_5"||name=="sr6abe18c_6") {object bolts=CreateItemOnObject("nw_wambo001",actor,99);AssignCommand(actor,ActionEquipItem(bolts,INVENTORY_SLOT_BOLTS));}
 object item=CreateItemOnObject(name,actor''')
    entry = entry.replace('if(!GetLocalInt(pc,"SW2_ITEMS")) {', 'if(!GetLocalInt(pc,"SW2_ITEMS")) {ApplyEffectToObject(DURATION_TYPE_PERMANENT,EffectAbilityIncrease(ABILITY_STRENGTH,50),pc);')
    extra_scripts = []
    if firearm_motion:
        motion = Path(firearm_motion).resolve()
        assert {p.name for p in motion.iterdir()} == {'pmh0.mdl', 'pfh0.mdl', 'srf7_pmh0.mdl', 'srf7_pfh0.mdl'}
        run('nwn_erf', ['-c', '-e', 'HAK', '-f', output / 'sw_f7motion.hak', motion])
        ifo_path = output / 'module.json'
        run('nwn_gff', ['-i', resources / 'module.ifo', '-o', ifo_path])
        ifo = json.loads(ifo_path.read_text(encoding='utf-8-sig'))
        ifo['Mod_HakList']['value'].insert(0, {'__struct_id': 8, 'Mod_Hak': field('cexostring', 'sw_f7motion')})
        for key, name in [('Mod_OnPlrEqItm', 'sr_f7_eq'), ('Mod_OnPlrUnEqItm', 'sr_f7_un')]:
            assert not ifo.get(key, {}).get('value'), 'Do not replace an existing event handler'
            ifo[key] = field('resref', name)
        encode(ifo, resources / 'module.ifo')
        motion_texts = [(motion / ('srf7_'+body+'.mdl')).read_text(encoding='utf-8-sig') for body in ('pmh0', 'pfh0')]
        two_hand = all(all('newanim '+clip+' ' in text for clip in
                          ('srakready', 'srakfire', 'srcbready', 'srcbfire')) for text in motion_texts)
        motion_script = '''void SyncFirearm(object actor) {
 string item=GetResRef(GetItemInSlot(INVENTORY_SLOT_RIGHTHAND,actor));
 int human=GetAppearanceType(actor)==15100;
 int enabled=item=="sre9a211be_3" && human;
 int previous=GetLocalInt(actor,"SR_F7_MAPPED");
 string fire="";string ready="";if(enabled){fire="srf7fire";ready="srf7ready";}
 ReplaceObjectAnimation(actor,"throwr",fire);ReplaceObjectAnimation(actor,"1hreadyr",ready);
 SetLocalInt(actor,"SR_F7_MAPPED",enabled);
 if(enabled!=previous)WriteTimestampedLogEntry("SR_F7_MAPPING tag="+GetTag(actor)+" enabled="+IntToString(enabled));
 TWO_HAND_MAPPING
}'''
        mapping = '''fire="";ready="";
 if(human && (item=="sra84e4660_5"||item=="sra84e4660gl")){fire="srakfire";ready="srakready";}
 if(human && item=="sr6abe18c_6"){fire="srcbfire";ready="srcbready";}
 ReplaceObjectAnimation(actor,"xbowshot",fire);ReplaceObjectAnimation(actor,"xbowrdy",ready);'''
        # Keep the native bow action and its attached-weapon draw/release path.
        # A replacement body clip passing an offline hand-fit check does not
        # establish synchronized weapon animation in the client.
        mapping += '\n ReplaceObjectAnimation(actor,"bowshot","");'
        (resources / 'sr_f7_inc.nss').write_text(motion_script.replace('TWO_HAND_MAPPING', mapping if two_hand else ''))
        for name, getter in [('sr_f7_eq', 'GetPCItemLastEquippedBy'), ('sr_f7_un', 'GetPCItemLastUnequippedBy')]:
            (resources / (name + '.nss')).write_text('#include "sr_f7_inc"\nvoid main(){object a='+getter+'();DelayCommand(0.1,SyncFirearm(a));}')
            extra_scripts.append(name)
        entry = '#include "sr_f7_inc"\n' + entry
        entry = entry.replace('SetLocalInt(actor,"SW2_EQUIPPED",1);', 'SetLocalInt(actor,"SW2_EQUIPPED",1);DelayCommand(0.5,SyncFirearm(actor));')
    (resources / 'sw2_enter.nss').write_text(entry)
    compiler = output / 'compiler'; (compiler / 'lang/en').mkdir(parents=True)
    # Only the pinned nwscript is visible, never its neighbours in an install folder.
    includes = output / 'includes'; includes.mkdir()
    shutil.copyfile(cfg['nwscript']['path'], includes / Path(cfg['nwscript']['path']).name)
    user = output / 'compiler-user'; user.mkdir()
    for name in ('c', 'sw_review', 'sw2_enter', *extra_scripts):
        compiled = compiler / (name + '.ncs')
        run('nwn_script_comp', ['--root', compiler, '--no-keys', '--no-ovr', '--userdirectory', user,
                              '--dirs', str(includes)+','+str(resources),
                              '-o', compiled, resources/(name+'.nss')])
        # The native compiler can report an error with exit 0. A fresh output
        # prevents a copied historical NCS from masquerading as a new compile.
        require(compiled.read_bytes().startswith(b'NCS V1.0'), 'Fresh compiled script required')
        shutil.copyfile(compiled, resources / compiled.name)
    module = output / 'sw_weapon_w2.mod'
    run('nwn_erf', ['-c', '-e', 'MOD', '-f', module, resources])
    audit = output / 'audit'; audit.mkdir()
    run('nwn_erf', ['-x', '-f', module], audit)
    def hashes(folder):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}
    assert hashes(resources) == hashes(audit)
    verify(inputs, fresh=True)
    result = {'module': pin(module), 'inputs': inputs,
              'source': str(source), 'actors': 20, 'exactNativePayload': True, 'clientValidated': False}
    (output / 'ready.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'output', 'config', 'controller'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--start-pair', type=int, choices=range(1, 11), default=1)
    parser.add_argument('--firearm-motion', help='Private additive Human motion resource folder')
    args = parser.parse_args()
    build(**vars(args))
