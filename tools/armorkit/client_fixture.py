"""Build an isolated client fixture: a throwaway hak and module in a fresh user directory.

Grown from the Phase 0 spike scripts (docs/armorkit/spikes.md). A fixture never changes the repository
packs or the player's own game folders: everything it needs is placed in its own user directory (packs
as hard links where the volume allows, which the client only reads; their hashes go into the record),
the client is started on it with `-userdirectory <dir> +TestNewModule <name>`, and the scripts write
`ARMORKIT ...` log lines that serve as evidence. The game install is an explicit argument; no machine
path lives here.
"""
import copy
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
from pathlib import Path

from . import registry
from .registry import require

LOG_PREFIX = 'ARMORKIT'
# SRN race rows in srn_2da/appearance.2da and the engine race each one stands on.
SRN_RACES = {'h': {'appearance': 15100, 'race': 6}, 'd': {'appearance': 15101, 'race': 0},
             'e': {'appearance': 15102, 'race': 1}, 'o': {'appearance': 15103, 'race': 5},
             'g': {'appearance': 15104, 'race': 2}}
COLOURS = {'leather1': 0, 'leather2': 1, 'cloth1': 2, 'cloth2': 3, 'metal1': 4, 'metal2': 5}
CREATURE_COLOURS = {'skin': 0, 'hair': 1, 'tattoo1': 2, 'tattoo2': 3}
TEMPLATE_CREATURE = 'nw_humanmerc001.utc'
TEMPLATE_TILESET = 'ttr01'
FLAT_TILE = 120
# Eleven characters: the fixture's own resources add up to five (`<name>_edge`) and resource names stop at 16.
NAME = re.compile(r'[a-z][a-z0-9_]{0,10}')
RESREF = 16
START = 8.0  # seconds after the player enters before the first shot
HOLD = 3.0  # seconds the game stays on each shot before it moves to the next
ACTOR_KEYS = {'label', 'body', 'position', 'facing', 'appearance', 'race', 'head', 'bare', 'item', 'parts', 'colours',
              'partColours', 'bodyColours', 'script', 'vars'}
SHOT_KEYS = {'actor', 'facing', 'distance', 'pitch', 'height'}
NAKED = {slot: 1 if slot in registry.FITTED or slot == 'neck' else 0 for slot in registry.SLOTS}

SPAWN_SCRIPT = '''object Modify(object it,int type,int index,int value) {
  object n=CopyItemAndModify(it,type,index,value,TRUE);
  if(!GetIsObjectValid(n)) { WriteTimestampedLogEntry("ARMORKIT modify-failed actor="+GetName(OBJECT_SELF)+" type="+IntToString(type)+" index="+IntToString(index)+" value="+IntToString(value)); return it; }
  DestroyObject(it); return n;
}
void Report() {
  object c=GetItemInSlot(INVENTORY_SLOT_CHEST,OBJECT_SELF); int i;
  string s="ARMORKIT actor="+GetName(OBJECT_SELF)+" tag="+GetTag(OBJECT_SELF)+" appearance="+IntToString(GetAppearanceType(OBJECT_SELF))
    +" gender="+IntToString(GetGender(OBJECT_SELF))+" phenotype="+IntToString(GetPhenoType(OBJECT_SELF))
    +" head="+IntToString(GetCreatureBodyPart(CREATURE_PART_HEAD,OBJECT_SELF))+" worn="+IntToString(GetIsObjectValid(c))
    +" ac="+IntToString(GetItemACValue(c))+" parts=";
  for(i=0;i<ITEM_APPR_ARMOR_NUM_MODELS;i++) s+=(i>0?",":"")+IntToString(GetItemAppearance(c,ITEM_APPR_TYPE_ARMOR_MODEL,i));
  WriteTimestampedLogEntry(s);
}
void main() {
  int i; int v;
  for(i=0;i<18;i++) SetCreatureBodyPart(i,(i==CREATURE_PART_BELT||i==CREATURE_PART_RIGHT_SHOULDER||i==CREATURE_PART_LEFT_SHOULDER)?0:1);
  v=GetLocalInt(OBJECT_SELF,"AK_HEAD"); if(v>0) SetCreatureBodyPart(CREATURE_PART_HEAD,v);
  for(i=0;i<4;i++) { v=GetLocalInt(OBJECT_SELF,"AK_B"+IntToString(i)); if(v>0) SetColor(OBJECT_SELF,i,v-1); }
  if(GetLocalInt(OBJECT_SELF,"AK_BARE")==0) {
    string res=GetLocalString(OBJECT_SELF,"AK_ITEM"); if(res=="") res="nw_cloth001";
    object it=CreateItemOnObject(res,OBJECT_SELF);
    for(i=0;i<ITEM_APPR_ARMOR_NUM_MODELS;i++) { v=GetLocalInt(OBJECT_SELF,"AK_M"+IntToString(i)); if(v>0) it=Modify(it,ITEM_APPR_TYPE_ARMOR_MODEL,i,v-1); }
    for(i=0;i<ITEM_APPR_ARMOR_NUM_COLORS*(ITEM_APPR_ARMOR_NUM_MODELS+1);i++) { v=GetLocalInt(OBJECT_SELF,"AK_C"+IntToString(i)); if(v>0) it=Modify(it,ITEM_APPR_TYPE_ARMOR_COLOR,i,v-1); }
    ActionEquipItem(it,INVENTORY_SLOT_CHEST);
  }
  string extra=GetLocalString(OBJECT_SELF,"AK_SCRIPT"); if(extra!="") DelayCommand(4.0,ExecuteScript(extra,OBJECT_SELF));
  DelayCommand(3.0,Report());
}
'''


def field(kind, value):
    return {'type': kind, 'value': value}


def gff_float(value):
    """GFF floats are 32-bit; store what a native readback reports."""
    return field('float', struct.unpack('<f', struct.pack('<f', value))[0])


def variable(name, value):
    require(type(value) in (int, float, str), f'Actor variable {name} must be a whole number, a number or text')
    kind, code = {int: ('int', 1), float: ('float', 2), str: ('cexostring', 3)}[type(value)]
    return {'__struct_id': 0, 'Name': field('cexostring', name), 'Type': field('dword', code), 'Value': field(kind, value)}


def model_indices(key):
    """ITEM_APPR_ARMOR_MODEL_* indices for `chest`, `bicep` (both sides), `bicep.l` or `bicep.r`."""
    slot, _, side = key.partition('.')
    require(slot in registry.SLOTS and side in ('', 'l', 'r'), 'Unknown part slot ' + key)
    models = registry.SLOTS[slot]['models']
    require(not side or len(models) == 2, key + ': only paired slots have sides')
    return models if not side else (models['lr'.index(side)],)


def actor_variables(actor):
    """Local variables the spawn script reads. Values are stored plus one so that zero means unset."""
    require(isinstance(actor, dict) and set(actor) <= ACTOR_KEYS, 'Actor keys are ' + ', '.join(sorted(ACTOR_KEYS)))
    for key in ('parts', 'colours', 'partColours', 'bodyColours', 'vars'):
        require(isinstance(actor.get(key, {}), dict), f'Actor {key} must be an object')
    values = {}
    if 'head' in actor:  # the script reads zero as "keep head 1", so zero is not a head number
        require(type(actor['head']) is int and 1 <= actor['head'] <= 255, 'Actor head must be a head number 1-255')
        values['AK_HEAD'] = actor['head']
    if actor.get('bare'):
        values['AK_BARE'] = 1
    # Every item part is set, so nothing of the stock template outfit shows: bare skin unless `parts` says otherwise.
    # An actor given its own item blueprint wears it as built, apart from the parts named here.
    if actor.get('item'):
        values['AK_ITEM'] = registry_resref(actor['item'])
    for key, number in {**({} if actor.get('bare') or actor.get('item') else NAKED), **actor.get('parts', {})}.items():
        require(type(number) is int and 0 <= number <= registry.LAST_NUMBER, f'{key}: part number out of range')
        for index in model_indices(key):
            values[f'AK_M{index}'] = number + 1
    for channel, shade in actor.get('colours', {}).items():
        require(channel in COLOURS and type(shade) is int and 0 <= shade <= 175, 'Armor colours are channel: 0-175')
        values[f'AK_C{COLOURS[channel]}'] = shade + 1
    for key, colours in actor.get('partColours', {}).items():
        require(isinstance(colours, dict), f'{key}: part colours are channel: 0-175')
        for index in model_indices(key):
            for channel, shade in colours.items():
                require(channel in COLOURS and type(shade) is int and 0 <= shade <= 175, 'Armor colours are channel: 0-175')
                values[f'AK_C{6 + index * 6 + COLOURS[channel]}'] = shade + 1
    for channel, shade in actor.get('bodyColours', {}).items():
        require(channel in CREATURE_COLOURS and type(shade) is int and 0 <= shade <= 175, 'Body colours are channel: 0-175')
        values[f'AK_B{CREATURE_COLOURS[channel]}'] = shade + 1
    if actor.get('script'):
        values['AK_SCRIPT'] = registry_resref(actor['script'])
    for name, value in actor.get('vars', {}).items():
        require(isinstance(name, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,30}', name) and not name.startswith('AK_'),
                'Unsafe actor variable ' + str(name))
        values[name] = value
    return [variable(name, value) for name, value in sorted(values.items())]


def registry_resref(name):
    require(isinstance(name, str) and re.fullmatch(r'[a-z][a-z0-9_]{0,15}', name), 'Resref required: ' + str(name))
    return name


def actor_tag(name, index):
    tag = f'{name}_a{index}'
    require(len(tag) <= RESREF, 'Too many actors for a fixture name this long: ' + tag)
    return tag


def creature(template, actor, name, index):
    """A placed creature from the stock template: no scripts but the fixture's, no gear, plot."""
    require(isinstance(actor, dict) and {'label', 'body', 'position'} <= set(actor), 'An actor needs label, body and position')
    body = actor['body']
    require(isinstance(body, str) and body in registry.BODIES, 'Actor body must be one of the 20 SRN bodies')
    require(isinstance(actor['label'], str) and isinstance(actor['position'], (list, tuple)) and len(actor['position']) == 2,
            'Actor label is text and position is [x, y]')
    race = SRN_RACES[body[2]] | {key: actor[key] for key in ('appearance', 'race') if key in actor}
    c = copy.deepcopy(template)
    c.pop('__data_type', None)
    c['__struct_id'] = 4
    for key in list(c):
        if key.startswith('Script'):
            c[key] = field('resref', '')
    x, y = actor['position']
    facing = math.radians(actor.get('facing', 270.0))
    tag = actor_tag(name, index)
    c.update({'Appearance_Type': field('word', race['appearance']), 'Race': field('byte', race['race']),
              'Gender': field('byte', 'mf'.index(body[1])), 'Phenotype': field('int', int(body[3])),
              'Appearance_Head': field('byte', 1), 'FirstName': field('cexolocstring', {'0': actor['label']}),
              'LastName': field('cexolocstring', {}), 'Tag': field('cexostring', tag), 'TemplateResRef': field('resref', tag),
              'FactionID': field('word', 2), 'Plot': field('byte', 1), 'Conversation': field('resref', ''),
              'Equip_ItemList': field('list', []), 'ItemList': field('list', []), 'ScriptSpawn': field('resref', name + '_sp'),
              'XPosition': gff_float(x), 'YPosition': gff_float(y), 'ZPosition': gff_float(0.0),
              'XOrientation': gff_float(math.cos(facing)), 'YOrientation': gff_float(math.sin(facing)),
              'VarTable': field('list', actor_variables(actor))})
    return c


def enter_script(name, shots, start=START, hold=HOLD):
    """The module entry script: hide the player, then step the camera through `shots`.

    Each shot attaches the camera to an actor (by index) and logs `ARMORKIT shot=<n>` once it is set, so
    a driver can capture the window after each line. A shot schedules the next one itself, `hold` seconds
    after it fired, so the game stays that long on every shot even after a stall (shots laid out on the
    clock up front fire back to back once the client catches up). Facing 90 looks north, at the front of
    an actor placed with the default facing."""
    require(isinstance(shots, list) and start >= 3.0 and hold > 0, 'Shots are a list; start is at least 3 s and hold positive')
    lines = ['void Shot(object pc,int n) {',
             f'  if(n>={len(shots)}) {{ WriteTimestampedLogEntry("ARMORKIT done"); return; }}',
             '  string tag; float facing; float distance; float pitch; float height;']
    for index, shot in enumerate(shots):
        require(isinstance(shot, dict) and set(shot) <= SHOT_KEYS and type(shot.get('actor')) is int and shot['actor'] >= 0
                and all(type(shot[key]) in (int, float) for key in SHOT_KEYS - {'actor'} if key in shot),
                'A shot is {actor, facing, distance, pitch, height}')
        facing, distance, pitch, height = (f'{float(shot.get(key, default)):.3f}' for key, default in
                                           (('facing', 90.0), ('distance', 5.0), ('pitch', 84.0), ('height', 0.0)))
        lines.append(f'  if(n=={index}) {{ tag="{actor_tag(name, shot["actor"])}"; facing={facing}; distance={distance}; '
                     f'pitch={pitch}; height={height}; }}')
    lines += ['  object t=GetObjectByTag(tag); if(GetIsObjectValid(t)) AttachCamera(pc,t);',
              '  SetCameraHeight(pc,height); AssignCommand(pc,SetCameraFacing(facing,distance,pitch,CAMERA_TRANSITION_TYPE_SNAP));',
              '  WriteTimestampedLogEntry("ARMORKIT shot="+IntToString(n)+" target="+tag+" valid="+IntToString(GetIsObjectValid(t)));',
              f'  DelayCommand({hold:.1f},Shot(pc,n+1));',
              '}',
              'void main() {', '  object pc=GetEnteringObject(); if(!GetIsPC(pc)) return;',
              '  SetCameraLimits(pc,1.0,89.0,0.5,40.0);',
              '  ApplyEffectToObject(DURATION_TYPE_PERMANENT,EffectVisualEffect(VFX_DUR_CUTSCENE_INVISIBILITY),pc);',
              '  SetCutsceneMode(pc,TRUE,FALSE);',
              '  WriteTimestampedLogEntry("ARMORKIT enter shots=' + str(len(shots)) + '");']
    if shots:  # attach once ahead of the first shot, so its capture is not taken before the camera has moved
        lines.append(f'  DelayCommand({start - 3.0:.1f},AttachCamera(pc,GetObjectByTag("{actor_tag(name, shots[0]["actor"])}")));')
    lines.append(f'  DelayCommand({start:.1f},Shot(pc,0));')
    return '\n'.join(lines + ['}']) + '\n'


def area_documents(name, creatures, size=8):
    tile = {'__struct_id': 1, 'Tile_ID': field('int', FLAT_TILE), 'Tile_Height': field('int', 0), 'Tile_Orientation': field('int', 0),
            **{key: field('byte', value) for key, value in
               {'Tile_AnimLoop1': 1, 'Tile_AnimLoop2': 1, 'Tile_AnimLoop3': 1, 'Tile_MainLight1': 0, 'Tile_MainLight2': 0,
                'Tile_SrcLight1': 0, 'Tile_SrcLight2': 0}.items()}}
    area = name + '_a'
    return {
        area + '.are': {'__data_type': 'ARE ', 'Tileset': field('resref', name), 'Width': field('int', size), 'Height': field('int', size),
                        'Name': field('cexolocstring', {'0': 'Armorkit fixture'}), 'Tag': field('cexostring', area),
                        'ResRef': field('resref', area), 'Tile_List': field('list', [copy.deepcopy(tile) for _ in range(size * size)]),
                        'Version': field('dword', 2), 'Flags': field('dword', 4), 'DayNightCycle': field('byte', 0),
                        'IsNight': field('byte', 0), 'SunAmbientColor': field('dword', 11579568),
                        'SunDiffuseColor': field('dword', 15658734), 'MoonAmbientColor': field('dword', 11579568),
                        'MoonDiffuseColor': field('dword', 15658734), 'FogClipDist': field('float', 80.0),
                        'SunShadows': field('byte', 1), 'ShadowOpacity': field('byte', 20), 'SkyBox': field('byte', 0)},
        area + '.git': {'__data_type': 'GIT ', 'Creature List': field('list', creatures), 'Door List': field('list', []),
                        'Placeable List': field('list', []), 'TriggerList': field('list', []), 'WaypointList': field('list', []),
                        'StoreList': field('list', [])},
    }


def module_documents(name, haks, tlk, entry=(40.0, 30.0)):
    """module.ifo and repute.fac. The fixture hak is listed first so it wins over the packs under test."""
    area = name + '_a'
    factions = ('PC', 'Hostile', 'Commoner', 'Merchant', 'Defender')
    return {
        'module.ifo': {'__data_type': 'IFO ', 'Mod_Name': field('cexolocstring', {'0': 'Armorkit fixture ' + name}),
                       'Mod_Description': field('cexolocstring', {'0': 'Isolated armorkit client fixture.'}),
                       'Mod_Tag': field('cexostring', name.upper()), 'Mod_Version': field('dword', 3),
                       'Mod_MinGameVer': field('cexostring', '1.69'), 'Mod_IsSaveGame': field('byte', 0),
                       'Mod_Entry_Area': field('resref', area), 'Mod_Entry_X': field('float', entry[0]),
                       'Mod_Entry_Y': field('float', entry[1]), 'Mod_Entry_Z': field('float', 0.0),
                       'Mod_Entry_Dir_X': field('float', 0.0), 'Mod_Entry_Dir_Y': field('float', 1.0),
                       'Mod_Area_list': field('list', [{'__struct_id': 6, 'Area_Name': field('resref', area)}]),
                       'Mod_HakList': field('list', [{'__struct_id': 8, 'Mod_Hak': field('cexostring', hak)} for hak in [name, *haks]]),
                       'Mod_CustomTlk': field('cexostring', tlk or ''), 'Mod_OnClientEntr': field('resref', name + '_en'),
                       'Mod_StartYear': field('dword', 1372), 'Mod_StartMonth': field('byte', 1), 'Mod_StartDay': field('byte', 1),
                       'Mod_StartHour': field('byte', 12), 'Mod_DawnHour': field('byte', 6), 'Mod_DuskHour': field('byte', 18),
                       'Mod_MinPerHour': field('byte', 2), 'Mod_XPScale': field('byte', 10)},
        'repute.fac': {'__data_type': 'FAC ', 'FactionList': field('list', [
            {'__struct_id': i, 'FactionName': field('cexostring', n), 'FactionGlobal': field('word', 1),
             'FactionParentID': field('dword', 4294967295)} for i, n in enumerate(factions)]),
            'RepList': field('list', [{'__struct_id': i * 5 + j, 'FactionID1': field('dword', i), 'FactionID2': field('dword', j),
                                       'FactionRep': field('dword', 0 if {i, j} == {1, 2} else 50)}
                                      for i in range(5) for j in range(5) if i != j])},
    }


def tileset(stock_text, name):
    """The stock tileset under the fixture's own name, with no random decoration."""
    text = stock_text.replace('\r\n', '\n')
    require(re.search(r'(?m)^Name=' + TEMPLATE_TILESET.upper() + '$', text), 'Unexpected stock tileset')
    text = re.sub(r'(?m)^Name=' + TEMPLATE_TILESET.upper() + '$', 'Name=' + name.upper(), text)
    return re.sub(r'(?m)^Density=[^\n]+', 'Density=0.000', text).replace('\n', '\r\n')


def row(actors_per_row, index, spacing=1.9, origin=(34.0, 40.0), depth=4.0):
    """Position of the index-th actor in rows facing south, `actors_per_row` wide."""
    return [origin[0] + (index % actors_per_row) * spacing, origin[1] + (index // actors_per_row) * depth]


def place(source, target):
    """Put a built pack in the fixture: a hard link where the volume allows (the client only reads it), else a copy.

    The target must be new. Copying onto an existing hard link would write through it into the pack it links to."""
    require(not Path(target).exists(), f'Fixture file already exists: {Path(target).name}')
    try:
        os.link(source, target)
    except OSError:
        shutil.copyfile(source, target)


def digest(path):
    """SHA-256 of a file, read in pieces (packs run to hundreds of megabytes)."""
    sha = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for piece in iter(lambda: stream.read(1 << 20), b''):
            sha.update(piece)
    return sha.hexdigest()


def build(spec, output, nwn_root, *, tools_directory=None):
    """Write the fixture's user directory under a fresh `output` folder and return its record.

    spec: name (short resref), resources (folder packed into the fixture hak, may be absent), haks (built
    packs to place in the fixture, lowest priority last), tlk (optional file), actors, shots, scripts
    ({resref: NSS text}), blueprints ({resref: {template: stock item resref, fields: {GFF label: [type, value]}}};
    an actor wears one through its `item` key), start and hold (seconds before the first shot and on each shot).
    Everything that can be checked is checked before the output folder is made.
    """
    from tools.phenotypes import tool_runtime
    require(isinstance(spec, dict) and set(spec) <= {'name', 'resources', 'haks', 'tlk', 'actors', 'shots', 'scripts',
                                                     'blueprints', 'entry', 'size', 'start', 'hold'}, 'Unknown fixture keys')
    name = spec.get('name')
    require(isinstance(name, str) and NAME.fullmatch(name), 'Fixture name must be a lowercase resref of at most 11 characters')
    actors, shots = spec.get('actors'), spec.get('shots', [])
    require(isinstance(actors, list) and actors, 'A fixture needs at least one actor')
    start, hold = spec.get('start', START), spec.get('hold', HOLD)
    require(all(type(value) in (int, float) for value in (start, hold)), 'start and hold are seconds')
    scripts = {name + '_sp': SPAWN_SCRIPT, name + '_en': enter_script(name, shots, start, hold),
               **{registry_resref(key): text for key, text in spec.get('scripts', {}).items()}}
    require(all(shot['actor'] < len(actors) for shot in shots), 'A shot names an actor that does not exist')
    actor_tag(name, len(actors) - 1)
    sources = [Path(source) for source in spec.get('haks', ())]
    for source in sources:
        require(source.suffix == '.hak' and registry_resref(source.stem) != name and source.is_file(),
                f'Fixture haks are existing .hak files with resref names: {source.name}')
    require(len({source.stem for source in sources}) == len(sources), 'Two fixture haks share a name')
    root = Path(nwn_root)
    require((root / 'data').is_dir(), 'The game install folder is required (the one holding data/)')
    output = Path(output).resolve()
    require(not output.exists(), f'A fixture is built into a fresh folder; this one exists (remove a failed build first): {output.name}')
    output.mkdir(parents=True)
    user, staged, documents, binary, stock = (output / part for part in ('userdir', 'hak-resources', 'json', 'module', 'stock'))
    for folder in (user / 'hak', user / 'modules', user / 'override', user / 'tlk', staged, documents, binary, stock):
        folder.mkdir(parents=True)
    common = ['--root', root, '--userdirectory', user, '--no-ovr']
    tools = {}

    def run(tool, args):
        if tool not in tools:
            tools[tool] = tool_runtime.tool(tool, tools_directory)
        result = subprocess.run([str(tools[tool]), *map(str, args)], capture_output=True, timeout=300,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        require(result.returncode == 0, tool + ' failed: ' + result.stderr.decode(errors='replace')[-2000:])
        return result.stdout

    def installed(resource):
        data = run('nwn_resman_cat', [*common, resource])
        (stock / resource).write_bytes(data)
        return data

    haks, digests = [], {}
    for source in sources:
        place(source, user / 'hak' / source.name)
        haks.append(source.stem)
        digests[source.stem] = digest(source)
    tlk = None
    if spec.get('tlk'):
        tlk = registry_resref(Path(spec['tlk']).stem)
        shutil.copyfile(spec['tlk'], user / 'tlk' / Path(spec['tlk']).name)
    if spec.get('resources'):
        for path in sorted(Path(spec['resources']).iterdir()):
            require(path.is_file() and len(path.stem) <= RESREF and path.name == path.name.lower(), 'Hak resources are lowercase resref files: ' + path.name)
            shutil.copyfile(path, staged / path.name)
    (staged / (name + '.set')).write_text(tileset(installed(TEMPLATE_TILESET + '.set').decode('cp1252'), name), encoding='cp1252', newline='')
    (staged / (name + '_edge.2da')).write_bytes(installed(TEMPLATE_TILESET + '_edge.2da'))
    hak = user / 'hak' / (name + '.hak')
    run('nwn_erf', ['-c', '-f', hak, '-e', 'HAK', staged])

    for resref, text in scripts.items():
        source = binary / (resref + '.nss')
        source.write_text(text, encoding='ascii', newline='\n')
        run('nwn_script_comp', [*common, source])
        require(source.with_suffix('.ncs').is_file(), 'Script did not compile: ' + resref)
    for resref, blueprint in spec.get('blueprints', {}).items():
        stock_name = registry_resref(blueprint['template']) + '.uti'
        installed(stock_name)
        run('nwn_gff', ['-i', stock / stock_name, '-o', stock / (stock_name + '.json')])
        item = json.loads((stock / (stock_name + '.json')).read_text(encoding='utf-8'))
        item.update({label: field(kind, value) for label, (kind, value) in blueprint['fields'].items()})
        item.update({'TemplateResRef': field('resref', registry_resref(resref)), 'Tag': field('cexostring', resref)})
        path = documents / (resref + '.uti.json')
        path.write_text(json.dumps(item), encoding='utf-8')
        run('nwn_gff', ['-i', path, '-o', binary / (resref + '.uti')])
    installed(TEMPLATE_CREATURE)
    run('nwn_gff', ['-i', stock / TEMPLATE_CREATURE, '-o', stock / (TEMPLATE_CREATURE + '.json')])
    template = json.loads((stock / (TEMPLATE_CREATURE + '.json')).read_text(encoding='utf-8'))
    creatures = [creature(template, actor, name, index) for index, actor in enumerate(actors)]
    for filename, document in {**area_documents(name, creatures, spec.get('size', 8)),
                               **module_documents(name, haks, tlk, spec.get('entry', (40.0, 30.0)))}.items():
        path = documents / (filename + '.json')
        path.write_text(json.dumps(document), encoding='utf-8')
        run('nwn_gff', ['-i', path, '-o', binary / filename])
    module = user / 'modules' / (name + '.mod')
    run('nwn_erf', ['-c', '-f', module, '-e', 'MOD', binary])
    record = {'name': name, 'userDirectory': str(user), 'module': module.name, 'hak': hak.name, 'haks': haks,
              'hakDigests': digests,
              'actors': [{'tag': actor_tag(name, index), 'label': actor['label'], 'body': actor['body']}
                         for index, actor in enumerate(actors)],
              'shots': len(shots), 'start': start, 'hold': hold, 'clientValidated': False}
    (output / 'fixture.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    return record
