"""Package several finished native heads into one top-priority trial HAK and an isolated client test module."""
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'phenotypes'))
from build_test_module import field
from tool_runtime import tool
from head_workflow import model_name,pin,read,require,sha,write_fresh
from verify_head_hak import TYPES,payload,write_hak
import build_head_fixture as fixture

SPEC_KIND='srn-head-trial-spec'
MANIFEST_KIND='srn-head-trial-client-view'
RESREF=re.compile(r'[a-z0-9_]{1,16}')
NAME=re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}')
SLOT=re.compile(r'(p[mf][hedog]0)_head(\d{3})')
EXTENSIONS={kind:suffix for suffix,kind in TYPES.items()}
TEXTURES={TYPES['tga'],TYPES['dds'],TYPES['plt']}
MODULE_TYPES={'git':2023,'uti':2025}
PALETTE_ROWS=176
MAX_HEADS=8
COLUMNS=12
MAX_ROWS=7


def entries(path,signature=b'HAK V1.0'):
    """(name, type, bytes) of a V1.0 HAK/MOD archive; payload() hashes the same table for HAKs."""
    data=Path(path).read_bytes()
    require(len(data)>=160 and data[:8]==signature,'Expected native '+signature[:3].decode('ascii')+' archive: '+str(path))
    count=struct.unpack_from('<I',data,16)[0];keys,resources=struct.unpack_from('<II',data,24)
    require(keys>=160 and resources>=160 and keys+24*count<=len(data) and resources+8*count<=len(data),'Invalid archive table bounds')
    rows=[];seen=set()
    for index in range(count):
        name,identity,kind=struct.unpack_from('<16sIH',data,keys+24*index)
        require(identity<count,'Invalid archive resource ID')
        offset,size=struct.unpack_from('<II',data,resources+8*identity)
        require(offset>=160 and offset+size<=len(data),'Invalid archive payload bounds')
        key=(name.split(b'\0',1)[0].decode('ascii'),kind);require(key not in seen,'Duplicate archive resource')
        seen.add(key);rows.append((*key,data[offset:offset+size]))
    return rows


def _rows(value,label,*,single=False):
    values=[value] if single else value
    require(isinstance(values,list) and values and all(type(v) is int and 0<=v<PALETTE_ROWS for v in values)
            and len(set(values))==len(values),label+' must be '+('a palette row' if single else 'distinct palette rows')+' 0-175')
    return value


def _identity(identity,label):
    require(isinstance(identity,dict) and set(identity)=={'appearanceRow','raceId','visualScale'},
            label+' needs exactly appearanceRow, raceId and visualScale')
    require(type(identity['appearanceRow']) is int and identity['appearanceRow']>=0
            and type(identity['raceId']) is int and 0<=identity['raceId']<=255,'Integer appearance and race rows required')
    require(isinstance(identity['visualScale'],(int,float)) and 0<identity['visualScale']<=3,'Bounded positive visual scale required')


def gender(prefix):
    """Creature gender for a head family: pf* heads load on female actors (1), pm* on male (0)."""
    return 1 if prefix[1]=='f' else 0


def prefixes(spec):
    """Head families of a trial: one prefix, or a list of one race's families so a race's male and female heads share a module."""
    return list(spec['prefix']) if isinstance(spec['prefix'],list) else [spec['prefix']]


def validate_spec(spec):
    """Check a trial spec without touching the filesystem; returns the normalized spec."""
    require(isinstance(spec,dict) and spec.get('kind')==SPEC_KIND,'Explicit '+SPEC_KIND+' required')
    for key in ('trial','hak','module','prefix','identity','base','heads','gameRoot'):
        require(key in spec,'Trial spec omits '+key)
    require(isinstance(spec['trial'],str) and NAME.fullmatch(spec['trial']),'Trial name must be a short plain name')
    for key in ('hak','module'):
        require(isinstance(spec[key],str) and RESREF.fullmatch(spec[key]),key+' must be a lowercase resref of at most 16 characters')
    families=prefixes(spec)
    require(families and all(isinstance(f,str) for f in families) and len(set(families))==len(families),'prefix must be a family or a list of distinct families')
    for family in families:model_name(family,1)
    require(len({f[2] for f in families})==1,'One trial holds one race: prefixes '+', '.join(families)+' mix races')
    _identity(spec['identity'],'identity')
    require(spec.get('lighting') in ('ambient','directional'),'Explicit lighting (ambient or directional) required')
    require(type(spec.get('motion',False)) is bool,'motion must be true or false')
    base=spec['base']
    require(isinstance(base,dict) and isinstance(base.get('haks'),list) and base['haks'] and isinstance(base.get('module'),dict),
            'base needs the fixture module and its HAKs')
    if 'actorIdentity' in base:_identity(base['actorIdentity'],'base actorIdentity')
    names=[]
    for item in base['haks']+[base['module']]:
        require(isinstance(item,dict) and isinstance(item.get('path'),str) and isinstance(item.get('sha256'),str)
                and re.fullmatch(r'[0-9a-f]{64}',item['sha256']),'Base inputs must be sha256 pins')
    for item in base['haks']:
        path=Path(item['path']);require(path.suffix.lower()=='.hak' and RESREF.fullmatch(path.stem),'Base HAK names must be resrefs')
        names.append(path.stem)
    require(len(set(names))==len(names),'Base HAK names repeat')
    require(spec['hak'] not in names,'Trial HAK name collides with a base HAK')
    require(Path(base['module']['path']).suffix.lower()=='.mod','Base module must be a .mod')
    heads=spec['heads']
    require(isinstance(heads,list) and 0<len(heads)<=MAX_HEADS,f'Between 1 and {MAX_HEADS} heads required')
    ids=set();models=set();rows_used=0
    for head in heads:
        require(isinstance(head,dict),'Each head must be an object')
        require(isinstance(head.get('id'),str) and NAME.fullmatch(head['id']) and head['id'] not in ids,'Each head needs a unique plain id')
        ids.add(head['id'])
        match=SLOT.fullmatch(str(head.get('model','')))
        require(match is not None and match[1] in families,head['id']+': model must be '+' or '.join(f+'_headNNN' for f in families))
        slot=int(match[2]);require(model_name(match[1],slot)==head['model'] and head['model'] not in models,head['id']+': head slot repeats or is out of range')
        models.add(head['model'])
        require(('native' in head)!=('resources' in head),head['id']+': give exactly one of native or resources')
        if 'resources' in head:
            require(isinstance(head['resources'],list) and head['resources'] and all(isinstance(p,str) for p in head['resources']),
                    head['id']+': resources must list files')
            require(isinstance(head.get('ascii',''),str),head['id']+': ascii must be the ASCII model path')
        else:require(isinstance(head['native'],str),head['id']+': native must be the native stage folder')
        _rows(head.get('skinRows'),head['id']+': skinRows');_rows(head.get('hairRows'),head['id']+': hairRows')
        _rows(head.get('tattoo1Row'),head['id']+': tattoo1Row',single=True);_rows(head.get('tattoo2Row'),head['id']+': tattoo2Row',single=True)
        require(head.get('metalRow',0)==0,head['id']+': metal shows stock row 0 without armour; metalRow must be 0')
        helmets=head.get('helmets',[1,2])
        require(isinstance(helmets,list) and len(set(helmets))==len(helmets) and set(helmets)<={1,2},head['id']+': helmets must be drawn from 1 and 2')
        external=head.get('externalTextures',[])
        require(isinstance(external,list) and all(isinstance(n,str) and RESREF.fullmatch(n) for n in external),head['id']+': externalTextures must be resrefs')
        count=len(head['skinRows'])*len(head['hairRows'])+len(helmets)
        rows_used=-(-count//COLUMNS)
        require(rows_used<=MAX_ROWS,f"{head['id']}: too many actors for the fixture floor ({rows_used} rows of {COLUMNS}; at most {MAX_ROWS})")
    require(isinstance(spec.get('shared',[]),list) and all(isinstance(p,str) for p in spec.get('shared',[])),'shared must list files')
    require(spec.get('client') is None or isinstance(spec['client'],str),'client must be a path string')
    return {**spec,'shared':spec.get('shared',[]),
            'heads':[{**head,'slot':int(SLOT.fullmatch(head['model'])[2]),'gender':gender(SLOT.fullmatch(head['model'])[1]),'metalRow':0,'helmets':head.get('helmets',[1,2]),
                      'externalTextures':head.get('externalTextures',[])} for head in heads]}


def plan_actors(spec):
    """Actors per head: every skin x hair row pair, then each helmet. The module shows one head's group at a time, so
    every group uses the same floor positions; `row` is the head's index in spec order."""
    actors=[]
    for row,head in enumerate(spec['heads']):
        cases=[(skin,hair,0) for skin in head['skinRows'] for hair in head['hairRows']]
        cases+=[(head['skinRows'][0],head['hairRows'][0],helmet) for helmet in head['helmets']]
        for column,(skin,hair,helmet) in enumerate(cases):
            index=len(actors)
            actors.append({'tag':f'sr_h_actor{index}','headId':head['id'],'model':head['model'],'slot':head['slot'],'gender':head['gender'],
                           'skin':skin,'hair':hair,'tattoo1':head['tattoo1Row'],'tattoo2':head['tattoo2Row'],'metal':0,'helmet':helmet,
                           'name':f"{head['id']} "+(f'helmet{helmet}' if helmet else f'skin{skin} hair{hair}'),
                           'row':row,'x':8+(column%COLUMNS)*5.5,'y':20+(column//COLUMNS)*7})
    return actors


def model_identity(data):
    """Internal model name of a binary (geometry header name at byte 20) or ASCII (newmodel) MDL."""
    if data[:4]==bytes(4):return data[20:84].split(bytes(1),1)[0].decode('ascii',errors='replace').lower()
    match=re.search(r'(?im)^\s*newmodel\s+(\S+)',data.decode('ascii',errors='replace'))
    return match[1].lower() if match else None


def texture_references(text):
    """Required (bitmap/textureN) and optional (materialname) names in an ASCII model."""
    required,optional=set(),set()
    for key,value in re.findall(r'(?im)^\s*(bitmap|texture\d|materialname)\s+(\S+)',text):
        value=value.lower()
        if value!='null':(optional if key.lower()=='materialname' else required).add(value)
    return required,optional


def head_resources(head):
    """Read one head's resources as (name, type, bytes) plus the ASCII model used for dependency checks, if any."""
    if 'native' in head:
        stage=Path(head['native']);record=read(stage/'native.json')
        require(record.get('model')==head['model'],head['id']+': native stage builds '+str(record.get('model')))
        hak=stage/(head['model']+'.hak')
        require(hak.is_file() and sha(hak)==record['hak']['sha256'],head['id']+': native HAK differs from native.json')
        found=entries(hak);hashes=payload(hak)
        for key,kind in (('mdl',TYPES['mdl']),('plt',TYPES['plt'])):
            if key in record:require(hashes.get((head['model'],kind))==record[key]['sha256'],head['id']+': native '+key+' pin differs from its HAK')
        ascii_model=stage/'converted'/'ascii'/(head['model']+'.mdl')
        return found,(ascii_model if ascii_model.is_file() else None),[pin(hak)]
    found=[];pins=[]
    for item in head['resources']:
        path=Path(item);require(path.is_file(),head['id']+': resource missing: '+item)
        require(path.suffix[1:].lower() in TYPES and RESREF.fullmatch(path.stem),head['id']+': unsupported resource '+path.name)
        found.append((path.stem,TYPES[path.suffix[1:].lower()],path.read_bytes()));pins.append(pin(path))
    ascii_model=head.get('ascii')
    return found,(Path(ascii_model) if ascii_model else None),pins


def plan_hak(heads,shared,base):
    """Merge head and shared resources, refusing collisions; returns (name, type, bytes) in head then archive order.

    heads: [(head, [(name,type,bytes)], ascii_text_or_None)]; shared: [(name,type,bytes)];
    base: {hak name: {(name,type): sha256}} for every lower-priority HAK the module also loads."""
    owners={};merged={}
    def family(kind):return 'texture' if kind in TEXTURES else kind
    def add(name,kind,data,owner,*,owned_prefix=None):
        require(RESREF.fullmatch(name),owner+': resource name is not a resref: '+name)
        if owned_prefix:require(name.startswith(owned_prefix),owner+': '+name+'.'+EXTENSIONS[kind]+' is not named for its head model')
        for hak,rows in base.items():
            clash=[f'{n}.{EXTENSIONS.get(k,k)}' for n,k in rows if n==name and family(k)==family(kind)]
            require(not clash,f'{owner}: {name}.{EXTENSIONS[kind]} would shadow {", ".join(clash)} in base HAK {hak}')
        key=(name,family(kind))
        if key in owners:
            other,other_kind=owners[key]
            same=other_kind==kind and merged[(name,kind)]==data and owner=='shared' and other=='shared'
            require(same,f'Resource collision: {name}.{EXTENSIONS[kind]} from {owner} and {name}.{EXTENSIONS[other_kind]} from {other}')
            return
        owners[key]=(owner,kind);merged[(name,kind)]=data
    for head,resources,_ in heads:
        models=[data for name,kind,data in resources if (name,kind)==(head['model'],TYPES['mdl'])]
        require(models,head['id']+': no '+head['model']+'.mdl')
        require(model_identity(models[0])==head['model'],head['id']+': '+head['model']+'.mdl is internally named '+str(model_identity(models[0])))
        for name,kind,data in resources:add(name,kind,data,head['id'],owned_prefix=head['model'])
    for name,kind,data in shared:add(name,kind,data,'shared')
    available={n for n,k in merged if k in TEXTURES}|{n for rows in base.values() for n,k in rows if k in TEXTURES}
    materials={n for n,k in merged if k==TYPES['mtr']}|{n for rows in base.values() for n,k in rows if k==TYPES['mtr']}
    dependencies={}
    for head,_,text in heads:
        if text is None:dependencies[head['id']]={'checked':False};continue
        required,optional=texture_references(text)
        missing=sorted(required-available-set(head['externalTextures']))
        require(not missing,head['id']+': model textures not packaged or declared external: '+', '.join(missing))
        dependencies[head['id']]={'checked':True,'textures':sorted(required),'external':sorted(required&set(head['externalTextures'])),
                                  'materials':sorted(optional&materials),'materialFallbackToBitmap':sorted(optional-materials)}
    for (name,kind),data in merged.items():
        if kind==TYPES['mtr']:
            for texture in re.findall(r'(?m)^texture\d+\s+(\S+)',data.decode('ascii',errors='replace')):
                require(texture.lower() in available,f'{name}.mtr texture not packaged: {texture}')
    return [(name,kind,data) for (name,kind),data in merged.items()],dependencies


def launch_scripts(module,client=None):
    """Launch.cmd/Launch.ps1 for an isolated user directory, matching the troll-male-01 client view."""
    default=("'"+client.replace("'","''")+"'") if client else "''"
    ps1=f'''param([string]$Client = {default})
$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$UserDir = Join-Path $Root 'userdir'
if (!$Client -or !(Test-Path -LiteralPath $Client -PathType Leaf)) {{ throw 'Supply -Client with the path to your installed NWN:EE nwmain.exe.' }}
$Manifest = Get-Content -LiteralPath (Join-Path $Root 'runtime-manifest.json') -Raw | ConvertFrom-Json
foreach ($File in $Manifest.files) {{
  $Path = Join-Path $Root $File.relativePath
  if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $File.sha256) {{ throw "Runtime hash mismatch: $($File.relativePath)" }}
}}
$Lines = @('[Alias]', "hd0=$UserDir")
foreach ($Name in @('hak','modules','override','logs','currentgame','temp','localvault','database')) {{
  $Dir = Join-Path $UserDir $Name
  New-Item -ItemType Directory -Path $Dir -Force | Out-Null
  $Lines += "$Name=$Dir"
}}
$Lines += @('[Game Options]', 'cliententirelog=1')
Set-Content -LiteralPath (Join-Path $UserDir 'nwn.ini') -Value $Lines -Encoding ASCII
Start-Process -FilePath $Client -WorkingDirectory (Split-Path -Parent $Client) -ArgumentList @('-userdirectory', ('"' + $UserDir + '"'), '+TestNewModule', '{module}')
'''
    return '@powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Launch.ps1" %*\r\n',ps1.replace('\n','\r\n')


SWEEP_SECONDS=5.0
ROW_LIBRARY='''void HeadSpawn(string res,float x,float y,int row){
  object area=GetArea(GetObjectByTag("head_target"));
  object o=CreateObject(OBJECT_TYPE_CREATURE,res,Location(area,Vector(x,y,0.0),90.0));
  SetLocalInt(o,"HEAD_ROW",row+1);}
void HeadClear(){
  object area=GetArea(GetObjectByTag("head_target"));object o=GetFirstObjectInArea(area);
  while(GetIsObjectValid(o)){
    if(GetLocalInt(o,"HEAD_ROW")>0){
      if(GetIsDead(o)) ApplyEffectToObject(DURATION_TYPE_INSTANT,EffectResurrection(),o);
      AssignCommand(o,SetIsDestroyable(TRUE,FALSE,FALSE));DestroyObject(o,0.2);}
    o=GetNextObjectInArea(area);}}
'''
ROW_SHOW='''void HeadShow(int row){
  row=((row%HEAD_ROWS)+HEAD_ROWS)%HEAD_ROWS;
  HeadClear();DelayCommand(0.5,HeadSpawnRow(row));SetLocalInt(GetModule(),"HEAD_ROW_SHOWN",row);
  WriteTimestampedLogEntry("HEAD_FIXTURE_ROW shown="+IntToString(row)+" head="+HeadName(row));
  object p=GetFirstPC();
  while(GetIsObjectValid(p)){
    SendMessageToPC(p,"Head "+IntToString(row+1)+"/"+IntToString(HEAD_ROWS)+": "+HeadName(row)+"   (chat: next, prev, head N, sweep)");
    p=GetNextPC();}}
void HeadSweep(){
  int r;for(r=0;r<HEAD_ROWS;r++) DelayCommand(IntToFloat(r)*SWEEP,HeadShow(r));
  DelayCommand(IntToFloat(HEAD_ROWS)*SWEEP,HeadShow(0));}
'''
ROW_ENTER='''void main(){object p=GetEnteringObject();if(!GetIsPC(p))return;
  SetLocalInt(GetModule(),"HEAD_TEST_STARTED",1);
  SendMessageToPC(p,"Head trial: one head on the floor at a time. A start-up sweep shows each head for "+FloatToString(SWEEP,0,0)+" s (it logs every slot), then head 1 stays. Chat: next, prev, head N, sweep. Actors revive 10 s after death.");
  WriteTimestampedLogEntry("HEAD_FIXTURE_CLIENT_ENTER");
  if(!GetLocalInt(GetModule(),"HEAD_SWEPT")){SetLocalInt(GetModule(),"HEAD_SWEPT",1);AssignCommand(GetModule(),HeadSweep());}}
'''
ROW_CHAT='''void main(){
  string m=GetStringLowerCase(GetPCChatMessage());int row=GetLocalInt(GetModule(),"HEAD_ROW_SHOWN");int handled=TRUE;
  if(m=="next") HeadShow(row+1);
  else if(m=="prev") HeadShow(row-1);
  else if(m=="sweep") HeadSweep();
  else if(GetStringLeft(m,5)=="head "){int n=StringToInt(GetStringRight(m,GetStringLength(m)-5));
    if(n>=1 && n<=HEAD_ROWS) HeadShow(n-1); else handled=FALSE;}
  else handled=FALSE;
  if(handled) SetPCChatMessage("");}
'''


def _nss(text):
    require('"' not in text and '\\' not in text,'Script strings must be plain');return text


def row_scripts(spec,actors,sweep=SWEEP_SECONDS):
    """Module enter + player-chat scripts that keep one head's actors on the floor: a start-up sweep spawns every
    head's group for `sweep` seconds (each spawn logs HEAD_FIXTURE_SLOT/COLORS), then head 1 stays; chat next/prev/
    head N/sweep cycles. Actors spawn from per-actor blueprints (resref = tag)."""
    rows=len(spec['heads']);require(rows>=1 and 1<=sweep<=60,'Row sweep needs heads and 1-60 s per head')
    spawn=['void HeadSpawnRow(int row){']
    for index,head in enumerate(spec['heads']):
        group=[a for a in actors if a['row']==index];require(group,head['id']+': no actors in its row')
        spawn.append(f'  if(row=={index}){{'+''.join(f'HeadSpawn("{_nss(a["tag"])}",{a["x"]:.2f},{a["y"]:.2f},{index});' for a in group)+'}')
    spawn.append('}')
    names=['string HeadName(int row){']+[f'  if(row=={i}) return "{_nss(h["id"])} ({_nss(h["model"])})";' for i,h in enumerate(spec['heads'])]+['  return "";}']
    library=f'const int HEAD_ROWS={rows};\nconst float SWEEP={sweep:.1f};\n'+ROW_LIBRARY+'\n'.join(spawn+names)+'\n'+ROW_SHOW
    return {'sr_h_enter':library+ROW_ENTER,'sr_h_chat':library+ROW_CHAT}


def blueprint(creature, motion=False):
    """Per-actor creature blueprint (UTC) from its fixture instance: the same fields without placement. By default trial
    actors stand still for head inspection: no heartbeat animation cycle (the fixture's walk/cast/attack loop) and plot, so a
    stray click cannot start combat. With `motion` (spec "motion": true) they keep the fixture's heartbeat cycle and death
    with a 10 s revive, for idle-and-motion client checks. The spawn script, which logs HEAD_FIXTURE_SLOT/COLORS, stays."""
    item={k:v for k,v in creature.items() if k not in ('__struct_id','XPosition','YPosition','ZPosition','XOrientation','YOrientation')}
    if not motion:item.update(ScriptHeartbeat=field('resref',''),Plot=field('byte',1))
    return {'__data_type':'UTC ','__struct_id':-1,**item}


def readme(spec,actors,hak_order):
    lines=[f"# {spec['trial']} client view (trial)",'',
           f"Run `Launch.cmd` (or `Launch.ps1 -Client <nwmain.exe>`). It opens an isolated user directory straight into the "
           f"`{spec['module']}` test module. HAK order (first wins): {', '.join('`'+n+'`' for n in hak_order)}.",'',
           f"One head's actors stand on the floor at a time. On entry a sweep shows each head for {SWEEP_SECONDS:.0f} s (every spawn is logged "
           "for verification), then head 1 stays. Type in chat: `next`, `prev`, `head N` (the Head row column) or `sweep`.",'',
           '| Head row | Actor | Head | Slot | Skin | Hair | Tattoo1 | Tattoo2 | Helmet |','|---|---|---|---|---|---|---|---|---|']
    lines+=[f"| {a['row']+1} | {a['tag']} | {a['headId']} | {a['model']} | {a['skin']} | {a['hair']} | {a['tattoo1']} | {a['tattoo2']} | {a['helmet'] or '-'} |" for a in actors]
    lines+=['','PLT channels: 0 skin, 1 hair, 2 metal, 8 tattoo1, 9 tattoo2. Metal shows stock row 0 because no armour is worn. '
            'Actors stand still for inspection (no heartbeat animation cycle) and are plot, so they cannot be attacked.','',
            'After a run, check spawns with `verify_head_trial.py --manifest runtime-manifest.json`. Not client-validated or production-accepted.','']
    return '\n'.join(lines)


def input_paths(spec_path):
    """Every file build() reads, for the guarded launcher's frozen input list: the spec, base HAKs and module, each head's
    native.json, HAK and ASCII model (or its declared resources and ASCII), and shared resources."""
    spec=validate_spec(read(spec_path));paths=[Path(spec_path)]
    paths+=[Path(item['path']) for item in spec['base']['haks']+[spec['base']['module']]]
    for head in spec['heads']:
        if 'native' in head:
            stage=Path(head['native']);paths+=[stage/'native.json',stage/(head['model']+'.hak')]
            ascii_model=stage/'converted'/'ascii'/(head['model']+'.mdl')
            if ascii_model.is_file():paths.append(ascii_model)
        else:
            paths+=[Path(item) for item in head['resources']]
            if head.get('ascii'):paths.append(Path(head['ascii']))
    paths+=[Path(item) for item in spec['shared']]
    return [str(path.resolve()) for path in paths]


def build(spec_path,output):
    spec=validate_spec(read(spec_path));output=Path(output)
    require(not output.exists(),'Fresh trial output folder required')
    base_haks=spec['base']['haks'];base_module=spec['base']['module']
    for item in base_haks+[base_module]:
        require(sha(item['path'])==item['sha256'],'Base input changed: '+item['path'])
    base={Path(item['path']).stem:payload(item['path']) for item in base_haks}
    heads=[];consumed=[]
    for head in spec['heads']:
        resources,ascii_model,pins=head_resources(head);consumed+=pins
        if ascii_model is not None:consumed.append(pin(ascii_model))
        heads.append((head,resources,ascii_model.read_text(encoding='ascii',errors='replace') if ascii_model else None))
    shared=[]
    for item in spec['shared']:
        path=Path(item);require(path.suffix[1:].lower() in TYPES,'Unsupported shared resource '+path.name)
        shared.append((path.stem,TYPES[path.suffix[1:].lower()],path.read_bytes()));consumed.append(pin(path))
    planned,dependencies=plan_hak(heads,shared,base)
    user=output/'userdir';work=output/'work';stage=work/'module'
    for folder in (user/'hak',user/'modules',user/'override',stage):folder.mkdir(parents=True)
    trial_hak=user/'hak'/(spec['hak']+'.hak');write_hak(trial_hak,planned)
    expected={(name,kind):hashlib.sha256(data).hexdigest() for name,kind,data in planned}
    require(payload(trial_hak)==expected,'Trial HAK payload differs from its plan')
    for item in base_haks:
        destination=user/'hak'/Path(item['path']).name;shutil.copyfile(item['path'],destination)
        require(sha(destination)==item['sha256'],'Base HAK copy differs: '+destination.name)
    def run(name,arguments):
        result=subprocess.run([str(tool(name)),*map(str,arguments)],capture_output=True)
        if result.returncode:
            raise ValueError(name+' failed: '+result.stderr.decode('utf-8',errors='replace')+' '+result.stdout.decode('utf-8',errors='replace'))
    def gff(name,document):
        path=work/(name+'.json');write_fresh(path,document);run('nwn_gff',['-i',path,'-o',stage/name])
    # The base fixture module supplies the actor template (stock merchant with the protected body identity) and helmet items.
    # A base built for another body declares that body as actorIdentity; the trial actors then take the spec identity.
    base_resources={(name,kind):data for name,kind,data in entries(base_module['path'],signature=b'MOD V1.0')}
    git=base_resources.get(('sr_h_floor',MODULE_TYPES['git']));require(git is not None,'Base module has no fixture GIT')
    (work/'base.git').write_bytes(git);run('nwn_gff',['-i',work/'base.git','-o',work/'base.git.json'])
    creatures=[c for c in read(work/'base.git.json')['Creature List']['value'] if c['Tag']['value'].startswith('sr_h_actor')]
    require(creatures,'Base module has no fixture actors')
    identity=spec['identity'];template_identity=spec['base'].get('actorIdentity',identity);sex=gender(prefixes(spec)[0])  # the camera target
    for creature in creatures:
        scale=[v['Value']['value'] for v in creature['VarTable']['value'] if v['Name']['value']=='BODY_VISUAL_SCALE']
        require(creature['Appearance_Type']['value']==template_identity['appearanceRow'] and creature['Race']['value']==template_identity['raceId']
                and len(scale)==1 and abs(scale[0]-template_identity['visualScale'])<1e-6,'Base fixture actors use another body identity')
    for helmet in sorted({h for head in spec['heads'] for h in head['helmets']}):
        data=base_resources.get((f'sr_h_helm{helmet}',MODULE_TYPES['uti']));require(data is not None,f'Base module lacks sr_h_helm{helmet}.uti')
        (stage/f'sr_h_helm{helmet}.uti').write_bytes(data)
    actors=plan_actors(spec)
    def creature(actor):
        return fixture.make_creature(creatures[0],actor['tag'],actor['name'],actor['x'],actor['y'],actor['slot'],actor['skin'],actor['hair'],
            identity['appearanceRow'],identity['raceId'],identity['visualScale'],actor['helmet'],tattoo=(actor['tattoo1'],actor['tattoo2']),gender=actor['gender'])
    hak_order=[spec['hak']]+[Path(item['path']).stem for item in base_haks]
    target_y=min(76,max(a['y'] for a in actors)+12)
    for actor in actors:gff(actor['tag']+'.utc',blueprint(creature(actor),spec.get('motion',False)))
    documents=fixture.module_documents([fixture.target_creature(creatures[0],identity['appearanceRow'],
        identity['raceId'],identity['visualScale'],40,target_y,gender=sex)],hak_order,spec['lighting'],
        name='SRN head trial '+spec['trial'],description='Trial heads: '+', '.join(h['model'] for h in spec['heads'])+'. Client acceptance pending.',
        events={'Mod_OnPlrChat':'sr_h_chat'})
    for name,document in documents.items():gff(name,document)
    for name,text in {**fixture.module_scripts(tattoo=True),**row_scripts(spec,actors)}.items():
        path=stage/(name+'.nss');path.write_text(text,encoding='ascii')
        run('nwn_script_comp',['--root',spec['gameRoot'],'--userdirectory',user,'--no-ovr',path])
        require(path.with_suffix('.ncs').is_file(),'Script compiler produced no bytecode')
    module=user/'modules'/(spec['module']+'.mod');run('nwn_erf',['-c','-f',module,'-e','MOD',stage])
    cmd,ps1=launch_scripts(spec['module'],spec.get('client'))
    (output/'Launch.cmd').write_bytes(cmd.encode('ascii'));(output/'Launch.ps1').write_bytes(ps1.encode('utf-8'))
    (output/'README.md').write_text(readme(spec,actors,hak_order),encoding='utf-8')
    for item in base_haks+[base_module]+consumed:require(sha(item['path'])==item['sha256'],'Input changed during build: '+item['path'])
    files=[{'relativePath':f'userdir/hak/{name}.hak','sha256':sha(user/'hak'/(name+'.hak'))} for name in hak_order]
    files.append({'relativePath':f"userdir/modules/{spec['module']}.mod",'sha256':sha(module)})
    write_fresh(output/'runtime-manifest.json',{'kind':MANIFEST_KIND,'trial':spec['trial'],'hak':spec['hak'],'module':spec['module'],
        'hakOrder':hak_order,'files':files,'spec':pin(spec_path),'base':{'haks':base_haks,'module':base_module},'inputs':consumed,
        'heads':[{'id':h['id'],'model':h['model'],'slot':h['slot'],'resources':sorted(f'{n}.{EXTENSIONS[k]}' for n,k,_ in r),
                  'dependencies':dependencies[h['id']]} for h,r,_ in heads],
        'trialHakResources':[{'name':f'{n}.{EXTENSIONS[k]}','sha256':expected[(n,k)]} for n,k,_ in planned],
        'identity':identity,'actorIdentity':template_identity,'gender':sex,'prefix':spec['prefix'],'lighting':spec['lighting'],'actors':[{k:v for k,v in a.items() if k not in ('x','y','name')} for a in actors],
        'rows':[{'index':i,'headId':h['id'],'model':h['model'],'actors':[a['tag'] for a in actors if a['row']==i]} for i,h in enumerate(spec['heads'])],
        'rowSweepSeconds':SWEEP_SECONDS,
        'ignoredActors':['head_target'],'colorsLogged':True,'clientObserved':False,'productionAccepted':False,
        'limitation':'Packaging and logged slots are not client or anatomy acceptance; review the heads in the client.'})
    return output/'runtime-manifest.json'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--spec',type=Path,required=True);target=p.add_mutually_exclusive_group(required=True)
    target.add_argument('--output',type=Path);target.add_argument('--inputs',type=Path,help='write the consumed input paths (JSON) and exit')
    a=p.parse_args()
    if a.inputs:write_fresh(a.inputs,input_paths(a.spec));print(a.inputs)
    else:print(build(a.spec,a.output))
