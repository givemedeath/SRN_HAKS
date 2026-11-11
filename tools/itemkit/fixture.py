"""Build a private item fixture from a pinned Human test module and UTC donors."""
from pathlib import Path
import copy
import re
import shutil
import struct
import subprocess
from tools.headkit.common import asset, pin, read, require, verify, write
from .routes import PACKAGED_FIREARMS

CHECKS = ('front-rear-sides', 'idle', 'walk', 'run', 'equip-unequip', 'attacks', 'shadows',
          'gloves-armor', 'shield-offhand')
FIREARM_CHECKS = CHECKS + ('ranged-reload', 'projectile-ammunition', 'color-variants-hidden-placeholders')


def audit_module_payload(resources, extracted):
    """Compare every MOD resource after native extraction, including extra entries."""
    def inventory(folder):
        paths = list(Path(folder).iterdir())
        require(paths and all(p.is_file() for p in paths), 'Module payload must contain only resource files')
        require(len({p.name.lower() for p in paths}) == len(paths), 'Case-colliding module resources')
        return {p.name.lower(): pin(p)['sha256'] for p in paths}
    expected, actual = inventory(resources), inventory(extracted)
    require(actual == expected, 'Exact module payload differs')
    return {'exact': True, 'resources': actual}


def packaged_blueprints(native):
    """Select audited package UTIs instead of inventing composite part bytes."""
    if 'blueprints' not in native: return []
    from .firearms import validate_assembly
    from .native import archive_helpers
    if native.get('kind') == 'shield-native-package':
        allocation=native['allocation'];rows=native['blueprints'];name=native['identity']['blueprint']
        require(native['baseItem']==allocation['baseItem']==56 and len(rows)==1
                and allocation['blueprint']==name
                and rows[0]['utiParts']==allocation['utiParts']=={
                    'ModelPart1':allocation['appearance'],'ModelPart2':0,'ModelPart3':0}
                and native['audits'].get('nativePositionNormalUVShadowRoundtrip') is True
                and rows[0]['audit']=={'allFieldsExact':True,'rootStructId':-1},
                'Shield fixture requires its audited single-model appearance')
        bound=rows[0]['file'];verify([native['hak'],native['rigAudit'],bound])
        require(Path(bound['path']).name==name+'.uti'
                and archive_helpers().payload(native['hak']['path']).get((name,2025))==bound['sha256'],
                'Shield blueprint differs from packaged bytes')
        return [(name,bound)]
    require(native.get('kind') == 'firearm-native-package' and native['baseItem'] in (6,61)
            and native['baseItem'] == native['allocation']['baseItem'],
            'Only the audited firearm package supplies multipart variant blueprints')
    allocation = native['allocation']; rows = native['blueprints']
    require(len(rows) == len(allocation['variants']), 'Incomplete firearm blueprint set')
    require([r['colour'] for r in rows] == allocation['colours'], 'Duplicate or unordered firearm Colors')
    verify([native['hak']]+[r['file'] for r in rows])
    payload = archive_helpers().payload(native['hak']['path'])
    result = []
    for variant, row in zip(allocation['variants'], rows):
        validate_assembly(allocation, variant, native['counts'][str(variant['colour'])])
        require(row['utiParts'] == variant['utiParts'], 'Packaged UTI parts differ from exact assembly')
        name = variant['blueprint']
        require(Path(row['file']['path']).name == name+'.uti'
                and payload.get((name, 2025)) == row['file']['sha256'], 'Blueprint differs from packaged bytes')
        result.append((name, row['file']))
    require(native['identity']['blueprint'] == result[0][0], 'Primary variant differs from fixture identity')
    return result


def field(kind, value):
    return {'type': kind, 'value': value}


def blueprint(base_item, allocation, identity=None):
    identity = identity or {}
    item = {'__data_type': 'UTI ', '__struct_id': -1, 'BaseItem': field('int', base_item),
            'Identified': field('byte', 1), 'StackSize': field('word', 1), 'Charges': field('byte', 0),
            'Plot': field('byte', 0), 'Stolen': field('byte', 0), 'Cost': field('dword', 0),
            'AddCost': field('dword', 0), 'PropertiesList': field('list', []),
            'Description': field('cexolocstring', {'0': 'Private itemkit review candidate.'}),
            'DescIdentified': field('cexolocstring', {})}
    for number in (1, 2, 3):
        item['ModelPart'+str(number)] = field('byte', allocation['modelIndex']*10+allocation['colourIndex'])
    item['TemplateResRef'] = field('resref', identity.get('blueprint', 'sr_cougar'))
    item['Tag'] = field('cexostring', identity.get('blueprint', 'sr_cougar'))
    item['LocalizedName'] = field('cexolocstring', {'0':identity.get('displayName','Cougar Fineblade Longblade')})
    return item


def gff_float(value):
    """GFF floats are 32-bit; store what the native readback will report."""
    return field('float', struct.unpack('<f', struct.pack('<f', value))[0])


def place_review_actors(git, area, ifo, actors):
    """Embed the two bound actors in the entry area, before any client event.

    Creatures the template area came with are left out: the floor template carries a 30-body lineup that holds
    nothing and does nothing, and it fills every review picture. An inherited creature that already bears a review
    actor's tag is still a collision."""
    require(len(actors) == 2, 'Both Human review actors required')
    result = copy.deepcopy(git)
    inherited = result.setdefault('Creature List', field('list', []))['value']
    tags = {row.get('Tag', {}).get('value') for row in inherited}
    require(not tags & {actor['Tag']['value'] for actor in actors}, 'Review actor placement collision')
    rows = result['Creature List']['value'] = []; tags = set()
    width, height = (area[key]['value'] * 10 for key in ('Width', 'Height'))
    x, y, z = (ifo['Mod_Entry_' + axis]['value'] for axis in ('X', 'Y', 'Z'))
    dx, dy = (ifo['Mod_Entry_Dir_' + axis]['value'] for axis in ('X', 'Y'))
    length = (dx*dx + dy*dy)**.5
    require(length > 0, 'Entry facing required for visible actor placement')
    dx, dy = dx/length, dy/length
    for actor, gender, side in zip(actors, (0, 1), (-1.5, 1.5)):
        tag = actor['Tag']['value']
        require(tag not in tags, 'Review actor placement collision')
        require(actor['Race']['value'] == 6 and actor['Gender']['value'] == gender,
                'Placed review actors must be the two bound Human bodies')
        px, py = x + 3*dx - side*dy, y + 3*dy + side*dx
        require(1 <= px <= width-1 and 1 <= py <= height-1, 'Review actors fall outside the entry area')
        placed = copy.deepcopy(actor); placed.pop('__data_type', None); placed['__struct_id'] = 4
        placed.update(XPosition=gff_float(px), YPosition=gff_float(py), ZPosition=gff_float(z),
                      XOrientation=gff_float(-dx), YOrientation=gff_float(-dy))
        rows.append(placed); tags.add(tag)
    return result


# Scripted camera shots for an unattended capture run (tools/itemkit/client_capture.py). Each row is
# (heartbeat step, seconds into the step, required check, camera facing, distance, pitch, height). The actors face
# north (90) at their targets, so facing 270 looks at an actor's front and 180 at its right hand from the side.
SHOT_TOGGLE = 'itk_shots'   # a 2DA the capture driver puts in the fixture's override folder; without it nothing changes
SHOT_LEAD, SHOT_HOLD, SHOT_OFFSET, SHOT_CYCLE = 0.7, 1.8, 20, 40
# Times are chosen so that, with the female half a cycle behind, her equip shots (steps 5 and 6) and his armour shots
# (steps 25 and 26) do not want the camera at once. Armour takes most of a step to go on, so it is shot a step later.
SHOTS = ((1, 2.0, 'front-rear-sides', 270, 3.2, 80, 1.0), (1, 5.0, 'front-rear-sides', 90, 3.2, 80, 1.0),
         (2, 2.0, 'front-rear-sides', 180, 3.2, 80, 1.0), (2, 5.0, 'front-rear-sides', 0, 3.2, 80, 1.0),
         (3, 2.0, 'idle', 180, 1.4, 85, 0.95), (3, 5.0, 'shadows', 225, 5.0, 50, 0.5),
         (5, 2.8, 'equip-unequip', 270, 3.0, 80, 1.0), (6, 2.4, 'equip-unequip', 270, 3.0, 80, 1.0),
         (7, 3.0, 'walk', 180, 4.0, 78, 1.0), (9, 2.5, 'run', 180, 5.0, 75, 1.0),
         (11, 3.0, 'attacks', 180, 3.0, 82, 1.1), (12, 2.5, 'attacks', 225, 2.6, 82, 1.1),
         (16, 3.0, 'shield-offhand', 225, 3.0, 82, 1.1), (20, 3.5, 'shield-offhand', 315, 3.0, 82, 1.1),
         (25, 5.4, 'gloves-armor', 225, 2.8, 82, 1.1), (26, 5.0, 'gloves-armor', 180, 1.4, 85, 0.95))
SHOT_BARE = 30   # the motion sequence's own unequip of armour and gloves does not always complete; the later, idle steps start bare
SHOT_ACTORS = (('sr_it_male', 'human-male'), ('sr_it_female', 'human-female'))


def shot_script(shots=SHOTS):
    """NWScript for the scripted shots: dormant unless the toggle 2DA is present.

    The motion heartbeat already walks each actor through equip, walk, run, attacks, shield, off-hand and armour in
    6-second steps. A watcher follows each actor's step and, at a stated time into a step, attaches the hidden
    player's camera to that actor and logs `ITEMKIT_SHOT shot=<n> ...` for the driver to capture. The female runs
    half a cycle behind the male so the two are rarely wanted at once. Armour, gloves and the off hand are removed
    outright at step 30, so the next cycle's bare-hand shots are bare; a shot that finds the camera in use is left
    for the next cycle, and `ITEMKIT_SHOTS done` is logged when every shot has been taken once."""
    require(shots and {row[2] for row in shots} == set(CHECKS), 'Scripted shots must cover every melee client check')
    by_step = {}
    for step, delay, *_ in shots:
        require(type(step) is int and 0 <= step < SHOT_CYCLE - 1 and SHOT_LEAD <= delay <= 6 - .5,
                'A shot is taken inside its own 6-second step')
        by_step.setdefault(step, []).append(delay)
    require(all(b - a >= SHOT_LEAD + SHOT_HOLD + .3 for row in by_step.values() for a, b in zip(sorted(row), sorted(row)[1:])),
            'Shots of one step need time to aim and hold between them')
    plan = []
    for index, (step, delay, check, facing, distance, pitch, height) in enumerate(shots):
        plan.append(f'  if(n=={step}) DelayCommand({delay - SHOT_LEAD:.1f},ItkTry(pc,t,base+{index},"{check}",n,'
                    f'{float(facing):.1f},{float(distance):.1f},{float(pitch):.1f},{float(height):.2f}));')
    total = len(shots) * len(SHOT_ACTORS)
    return '''void ItkFree() { SetLocalInt(GetModule(),"ITK_BUSY",0); }
void ItkDone() { WriteTimestampedLogEntry("ITEMKIT_SHOTS done"); }
void ItkFire(object pc,object t,int id,string check,int n) {
  object m=GetModule(); SetLocalInt(m,"ITK_D"+IntToString(id),1);
  int fired=GetLocalInt(m,"ITK_FIRED")+1; SetLocalInt(m,"ITK_FIRED",fired);
  WriteTimestampedLogEntry("ITEMKIT_SHOT shot="+IntToString(id)+" target="+GetTag(t)+" check="+check+" step="+IntToString(n)+" valid="+IntToString(GetIsObjectValid(t)));
  DelayCommand(@HOLD@,ItkFree());
  if(fired>=@TOTAL@) DelayCommand(@HOLD@+0.5,ItkDone());
}
void ItkTry(object pc,object t,int id,string check,int n,float facing,float distance,float pitch,float height) {
  object m=GetModule(); if(GetLocalInt(m,"ITK_D"+IntToString(id)) || GetLocalInt(m,"ITK_BUSY")) return;
  SetLocalInt(m,"ITK_BUSY",1); AttachCamera(pc,t); SetCameraHeight(pc,height);
  AssignCommand(pc,SetCameraFacing(facing,distance,pitch,CAMERA_TRANSITION_TYPE_SNAP));
  DelayCommand(@LEAD@,ItkFire(pc,t,id,check,n));
}
void ItkBare(object t) {
  DestroyObject(GetItemInSlot(INVENTORY_SLOT_CHEST,t)); DestroyObject(GetItemInSlot(INVENTORY_SLOT_ARMS,t));
  DestroyObject(GetItemInSlot(INVENTORY_SLOT_LEFTHAND,t));
}
void ItkPlan(object pc,object t,int base,int n) {
  if(n==@BARE@) ItkBare(t);
@PLAN@
}
void ItkWatch(object pc) {
  int i;
  for(i=0;i<2;i++) {
    object t=GetObjectByTag(i==0 ? "@MALE@" : "@FEMALE@"); int s=GetLocalInt(t,"STEP");
    if(s!=GetLocalInt(t,"ITK_SEEN")) { SetLocalInt(t,"ITK_SEEN",s); ItkPlan(pc,t,i*@PER@,s==0 ? @LAST@ : s-1); }
  }
  if(GetLocalInt(GetModule(),"ITK_FIRED")<@TOTAL@) DelayCommand(0.25,ItkWatch(pc));
}
void ItkBegin(object pc,object male,object female) {
  if(Get2DAString("@TOGGLE@","On",0)!="1") return;
  SetCameraLimits(pc,1.0,89.0,0.5,40.0);
  ApplyEffectToObject(DURATION_TYPE_PERMANENT,EffectVisualEffect(VFX_DUR_CUTSCENE_INVISIBILITY),pc);
  SetCutsceneMode(pc,TRUE,FALSE);
  SetLocalInt(male,"STEP",0); SetLocalInt(female,"STEP",@OFFSET@);
  ItkBare(male); ItkBare(female);
  AssignCommand(male,SetFacing(90.0)); AssignCommand(female,SetFacing(90.0));
  WriteTimestampedLogEntry("ITEMKIT_SHOTS enter total="+IntToString(@TOTAL@));
  DelayCommand(4.0,ItkWatch(pc));
}
'''.replace('@PLAN@', chr(10).join(plan)).replace('@TOTAL@', str(total)).replace('@BARE@', str(SHOT_BARE)).replace('@PER@', str(len(shots))).replace(
        '@HOLD@', f'{SHOT_HOLD:.1f}').replace('@LEAD@', f'{SHOT_LEAD:.1f}').replace('@OFFSET@', str(SHOT_OFFSET)).replace(
        '@LAST@', str(SHOT_CYCLE - 1)).replace('@TOGGLE@', SHOT_TOGGLE).replace('@FEMALE@', SHOT_ACTORS[1][0]).replace('@MALE@', SHOT_ACTORS[0][0])


def entry_script(item_name, comparison=False, previous='', *, equipment_slot='right'):
    from .contracts import resref
    resref(item_name)
    require(equipment_slot in ('right', 'left'), 'Unsupported fixture equipment slot')
    comparisons = tuple(comparison or ())
    require(len(set(comparisons)) == len(comparisons) and item_name not in comparisons, 'Comparison blueprint collision')
    for name in comparisons: resref(name)
    if previous: resref(previous)
    script = '''void ReportEquip(object actor) {
  if(!GetIsObjectValid(actor)) return;
  object item=GetItemInSlot(INVENTORY_SLOT_RIGHTHAND,actor);
  WriteTimestampedLogEntry("ITEMKIT_EQUIPPED actor="+GetTag(actor)+" valid="+IntToString(GetIsObjectValid(item))+" right="+GetResRef(item));
  if(GetIsPC(actor)) SendMessageToPC(actor,"Equipped: "+GetName(item)+" ["+GetResRef(item)+"]. Both Human reviewers are directly ahead.");
}
void GiveBlade(object actor) {
  object item=GetItemPossessedBy(actor,"ITEM_RESREF");
  if(!GetIsObjectValid(item)) item=CreateItemOnObject("ITEM_RESREF",actor);
  if(!GetIsObjectValid(item)) { WriteTimestampedLogEntry("ITEMKIT_ITEM_FAILED actor="+GetTag(actor)); return; }
  AssignCommand(actor,ActionEquipItem(item,INVENTORY_SLOT_RIGHTHAND));
  DelayCommand(1.0,ReportEquip(actor));
}
void StartReview(object pc,int retries) {
  if(!GetIsObjectValid(pc) || !GetIsPC(pc)) return;
  object male=GetObjectByTag("sr_it_male"); object female=GetObjectByTag("sr_it_female");
  object area=GetArea(pc);
  if(!GetIsObjectValid(area) || !GetIsObjectValid(male) || !GetIsObjectValid(female) || GetArea(male)!=area || GetArea(female)!=area) {
    if(retries>0) DelayCommand(0.5,StartReview(pc,retries-1));
    else { WriteTimestampedLogEntry("ITEMKIT_READY_FAILED area="+GetTag(area)+" male="+IntToString(GetIsObjectValid(male))+" female="+IntToString(GetIsObjectValid(female)));
      SendMessageToPC(pc,"Review fixture could not find both placed Human actors; inspect the client log."); }
    return;
  }
  GiveBlade(pc); GiveBlade(male); GiveBlade(female);
  COMPARISON
  WriteTimestampedLogEntry("ITEMKIT_READY area="+GetTag(area)+" male="+GetTag(male)+" female="+GetTag(female));
  ItkBegin(pc,male,female);
}
void main() {
  object pc=GetEnteringObject(); if(!GetIsPC(pc)) return;
  PRIOR
  DelayCommand(0.5,StartReview(pc,20));
}'''
    if equipment_slot == 'left':
        script = script.replace('INVENTORY_SLOT_RIGHTHAND', 'INVENTORY_SLOT_LEFTHAND').replace(' right=', ' left=')
    return (shot_script() + script).replace('ITEM_RESREF', item_name).replace('COMPARISON',
        '\n  '.join('if(!GetIsObjectValid(GetItemPossessedBy(pc,"'+name+'"))) CreateItemOnObject("'+name+'",pc);' for name in comparisons)).replace('PRIOR',
        'ExecuteScript("'+previous+'",GetModule());' if previous else '')


HEARTBEAT_ITEM = re.compile(r'GetItemPossessedBy\(OBJECT_SELF,"([a-z0-9_]{1,16})"\)')


def retarget_heartbeat(script, item_name):
    """Point the inherited motion heartbeat at this design, whatever donor it held."""
    from .contracts import resref
    item_name = resref(item_name)
    require(len(HEARTBEAT_ITEM.findall(script)) == 1, 'Fixture heartbeat must hold exactly one reviewed item')
    return HEARTBEAT_ITEM.sub('GetItemPossessedBy(OBJECT_SELF,"'+item_name+'")', script)


def build(manifest_path, manifest, native, local, output):
    from tools.phenotypes import tool_runtime
    output = Path(output).resolve(); output.mkdir(); resources = output/'module-resources'; resources.mkdir()
    required = ('fixtureTemplate', 'maleCreature', 'femaleCreature', 'nwscript')
    require(all(key in manifest['inputs'] for key in required), 'Pinned private module and both Human UTC donors required')
    inputs = [asset(manifest_path, manifest['inputs'][key]) for key in required]+[native['hak']]
    from .contracts import resref
    identity = native.get('identity', {})
    item_name = resref(identity.get('blueprint', 'sr_cougar'))
    hak_name = resref(identity.get('hak', 'srn_cougar_test'))
    module_name = resref(identity.get('module', 'sr_cougar_test'))
    variants = packaged_blueprints(native)
    inputs += [bound for _, bound in variants]

    tools = {}

    def run(name, args, cwd=None):
        if name not in tools: tools[name] = tool_runtime.tool(name, inputs=[row['path'] for row in inputs])
        result = subprocess.run([str(tools[name]), *map(str, args)], cwd=cwd, capture_output=True, text=True, timeout=120,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        require(result.returncode == 0, name+' failed: '+result.stderr[-2000:])
        return result.stdout
    inventory = run('nwn_erf', ['-t', '-f', inputs[0]['path']])
    # The recipient template is an explicitly selected isolated fixture, not a live module.
    require('module.ifo' in inventory, 'Private fixture template lacks module.ifo')
    run('nwn_erf', ['-x', '-f', inputs[0]['path']], resources)
    require(not any((resources/name).exists() for name in (item_name+'.uti', 'sr_it_enter.nss', 'sr_it_enter.ncs',
                                                        'sr_it_male.utc', 'sr_it_female.utc')), 'Fixture resource collision')
    ifo_json = output/'module.ifo.json'; run('nwn_gff', ['-i', resources/'module.ifo', '-o', ifo_json])
    ifo = read(ifo_json); previous = ifo.get('Mod_OnClientEntr', {}).get('value', '')
    require(not previous or all(c in 'abcdefghijklmnopqrstuvwxyz0123456789_' for c in previous), 'Unsafe prior entry script')
    haks = ifo.setdefault('Mod_HakList', field('list', []))['value']
    require(not any(row['Mod_Hak']['value'] == hak_name for row in haks), 'Fixture already has candidate HAK')
    for name, bound in local.get('comparisonHaks', {}).items():
        resref(name); verify([bound]); inputs.append(bound)
        require(name != hak_name and not any(row['Mod_Hak']['value']==name for row in haks), 'Comparison HAK collision')
        haks.append({'__struct_id':8,'Mod_Hak':field('cexostring',name)})
    haks.append({'__struct_id': 8, 'Mod_Hak': field('cexostring', hak_name)})
    ifo['Mod_OnClientEntr'] = field('resref', 'sr_it_enter')
    ifo['Mod_Name'] = field('cexolocstring', {'0': identity.get('displayName','Cougar Fineblade')+' private review'})
    write(ifo_json, ifo); run('nwn_gff', ['-i', ifo_json, '-o', resources/'module.ifo'])
    if variants:
        for name, bound in variants:
            require(not (resources/(name+'.uti')).exists(), 'Fixture variant blueprint collision')
            shutil.copyfile(bound['path'], resources/(name+'.uti'))
    else:
        uti_json = output/'cougar.uti.json'; write(uti_json, blueprint(native['baseItem'], native['allocation'], identity), fresh=True)
        run('nwn_gff', ['-i', uti_json, '-o', resources/(item_name+'.uti')])
    actors = []
    for key, name, gender in (('maleCreature', 'sr_it_male', 0), ('femaleCreature', 'sr_it_female', 1)):
        source = asset(manifest_path, manifest['inputs'][key])
        document = output/(name+'.json'); run('nwn_gff', ['-i', source['path'], '-o', document])
        actor = read(document)
        require(actor.get('Gender', {}).get('value') == gender and actor.get('Race', {}).get('value') == 6,
                'Fixture donor must be the declared Human sex')
        actor['TemplateResRef'] = field('resref', name); actor['Tag'] = field('cexostring', name)
        write(document, actor); run('nwn_gff', ['-i', document, '-o', resources/(name+'.utc')])
        actors.append(actor)
    area_name = resref(ifo['Mod_Entry_Area']['value'])
    area_json = output/'entry-area.json'; git_json = output/'entry-instances.json'
    run('nwn_gff', ['-i', resources/(area_name+'.are'), '-o', area_json])
    run('nwn_gff', ['-i', resources/(area_name+'.git'), '-o', git_json])
    placed = place_review_actors(read(git_json), read(area_json), ifo, actors)
    write(git_json, placed)
    run('nwn_gff', ['-i', git_json, '-o', resources/(area_name+'.git')])
    readback = output/'entry-instances-readback.json'
    run('nwn_gff', ['-i', resources/(area_name+'.git'), '-o', readback])
    require(read(readback) == placed, 'Placed actor native GFF roundtrip differs')
    comparisons = [name for name, _ in variants[1:]]
    for role, comparison in manifest['inputs'].items():
        if not re.fullmatch(r'comparisonBlueprint[0-9]*', role): continue
        bound = asset(manifest_path, comparison); inputs.append(bound)
        document = output/(role+'.json'); run('nwn_gff', ['-i', bound['path'], '-o', document])
        data = read(document); name = resref(data['TemplateResRef']['value'])
        require(data['Tag']['value'] == name and name != item_name and name not in comparisons
                and not (resources/(name+'.uti')).exists(), 'Comparison blueprint collision')
        shutil.copyfile(bound['path'], resources/(name+'.uti')); comparisons.append(name)
    # The old item fixture's setup script attaches the player's camera. Review
    # actors are now visible at entry; leave the player's camera under their control.
    script = entry_script(item_name, comparisons, '' if previous == 'sr_it_setup' else previous,
                          equipment_slot='left' if native.get('kind') == 'shield-native-package' else 'right')
    script_path = resources/'sr_it_enter.nss'; script_path.write_text(script, encoding='ascii')
    include = output/'includes'; include.mkdir()
    shutil.copyfile(inputs[3]['path'], include/'nwscript.nss')
    # Resman still requires a root/language directory with --no-keys. Use an
    # isolated empty container so compilation cannot silently read live HAKs,
    # overrides or an unbound installed nwscript.nss.
    compiler_root = output/'compiler-root'; (compiler_root/'lang/en').mkdir(parents=True)
    compiler_user = output/'compiler-user'; compiler_user.mkdir()
    run('nwn_script_comp', ['--root', compiler_root, '--no-keys', '--no-ovr',
                          '--userdirectory', compiler_user, '--dirs', include,
                          '-o', resources/'sr_it_enter.ncs', script_path])
    heartbeat = resources/'sr_it_hb.nss'
    if heartbeat.exists():
        # The inherited motion fixture must re-equip this design, not its donor item
        # (templates have carried both the Cougar sword and the Colt pistol).
        heartbeat.write_text(retarget_heartbeat(heartbeat.read_text(encoding='ascii'), item_name), encoding='ascii')
        run('nwn_script_comp', ['--root', compiler_root, '--no-keys', '--no-ovr', '--userdirectory', compiler_user,
                              '--dirs', include, '-o', resources/'sr_it_hb.ncs', heartbeat])
    userdir = output/'userdir'; (userdir/'modules').mkdir(parents=True); (userdir/'hak').mkdir()
    module = userdir/'modules'/(module_name+'.mod')
    run('nwn_erf', ['-c', '-e', 'MOD', '-f', module, resources])
    extracted = output/'module-audit'; extracted.mkdir()
    run('nwn_erf', ['-x', '-f', module], extracted)
    payload = audit_module_payload(resources, extracted)
    write(output/'module-payload.json', payload, fresh=True)
    shutil.copyfile(native['hak']['path'], userdir/'hak'/(hak_name+'.hak'))
    # Existing fixture HAKs must be bound copies, not borrowed from a live userdir.
    for row in haks[:-1]:
        from .contracts import resref
        name = resref(row['Mod_Hak']['value']); bound = {**local.get('fixtureHaks', {}), **local.get('comparisonHaks', {})}.get(name)
        require(bound is not None, 'Missing bound fixture dependency HAK: '+name); verify([bound]); inputs.append(bound)
        require_unshadowed(native['hak'], bound, name)
        shutil.copyfile(bound['path'], userdir/'hak'/(name+'.hak'))
    verify(inputs, fresh=True)
    # Tools resolve once; this records every input the build came to consume.
    tool_runtime.tool('nwn_erf', inputs=[row['path'] for row in inputs])
    result = {'module': pin(module), 'hak': pin(userdir/'hak'/(hak_name+'.hak')),
              'fixtureHaks': [pin(p) for p in sorted((userdir/'hak').iterdir())],
              'userDirectory': str(userdir), 'clientValidated': False,
              'requiredChecks': {body: list(FIREARM_CHECKS if native.get('kind')=='firearm-native-package' else CHECKS) for body in manifest['clientCoverage']},
              'actorPlacement': pin(readback), 'actorPlacementMode': 'native-entry-area-instances',
              'entryReadiness': 'bounded-area-and-actor-check', 'playerCameraControlled': False}
    result['modulePayloadAudit'] = pin(output/'module-payload.json')
    if variants:
        result['family'] = 'shield' if native.get('kind')=='shield-native-package' else 'firearm-crossbow' if native['baseItem']==6 else 'firearm-sling'
        result['variantBlueprints'] = [bound for _, bound in variants]
    write(output/'fixture.json', result, fresh=True)
    return result


def require_unshadowed(candidate, other, name):
    """The candidate HAK is listed last, so any HAK above it wins a shared resource."""
    from .native import archive_helpers
    archive = archive_helpers()
    shared = sorted(set(archive.payload(candidate['path'])) & set(archive.payload(other['path'])))
    require(not shared, 'Bound HAK '+name+' shadows candidate resources: '+str(shared[:5]))


def validate_evidence(path, fixture):
    evidence = read(path)
    require(evidence.get('module') == fixture['module'] and evidence.get('hak') == fixture['hak']
            and evidence.get('fixtureHaks') == fixture['fixtureHaks'], 'Client evidence belongs to another package')
    verify([fixture['module'], fixture['hak']]+fixture['fixtureHaks'])
    observations = evidence.get('observations', [])
    checks = FIREARM_CHECKS if fixture.get('family') in PACKAGED_FIREARMS else CHECKS
    required = {(body, name) for body in ('human-male', 'human-female') for name in checks}
    require(len(observations) == len(required) and {(r['body'], r['check']) for r in observations} == required,
            'Incomplete or duplicate Human client check matrix')
    for row in observations:
        require(row.get('result') == 'pass' and row.get('reviewedBy') and row.get('notes', '').strip()
                and row.get('screenshots') and row.get('logs'), 'Observed screenshots, logs and review required')
        for source in row['screenshots']+row['logs']: asset(path, source)
    return {'clientValidated': True, 'productionAccepted': False, 'evidence': pin(path), 'checks': len(required)}
