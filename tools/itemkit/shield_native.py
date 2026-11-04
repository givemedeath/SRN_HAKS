"""Single-model Shield export; opaque fittings and a constant-alpha pane."""
from pathlib import Path
import math
import re
import struct
import numpy as np
from tools.headkit.common import require
from .contracts import resref
from .native import ascii_model, sanitize_and_decode
from .geometry import topology


def allocation(resources, appearance, texture, blueprint):
    require(type(appearance) is int and 1 <= appearance <= 255, 'Shield appearance must fit its native byte')
    model = resref(f'ashlw_{appearance:03d}'); icon = resref('i'+model)
    texture = resref(texture); blueprint = resref(blueprint)
    names = {model+'.mdl', icon+'.tga', icon+'.dds', blueprint+'.uti'}
    names.update(texture+suffix for suffix in ('.tga','.dds','.mtr','.txi'))
    require(not names.intersection(n.lower() for n in resources), 'Shield resource collision')
    return {'baseItem':56, 'appearance':appearance, 'models':{'whole':model},
            'icons':{'whole':icon}, 'texture':texture, 'blueprint':blueprint,
            'utiParts':{'ModelPart1':appearance,'ModelPart2':0,'ModelPart3':0}}


def validate_geometry(geometry):
    p,n,uv = (np.asarray(geometry[k]) for k in ('positions','normals','uv'))
    pane=np.asarray(geometry['paneFaces'])
    require(p.ndim==3 and p.shape[1:]==(3,3) and n.shape==p.shape and uv.shape==(*p.shape[:2],2),
            'Exact per-corner Shield attributes required')
    require(4 <= len(p) <= 10000 and pane.dtype==np.bool_ and pane.shape==(len(p),)
            and pane.any() and (~pane).any(), 'Separate pane and opaque fittings required')
    require(np.isfinite(p).all() and np.isfinite(n).all() and np.isfinite(uv).all()
            and np.allclose(np.linalg.norm(n,axis=2),1,atol=1e-4)
            and (uv>=0).all() and (uv<=1).all(), 'Invalid Shield corner attributes')
    require(topology(p.reshape(-1,3),np.arange(p.size//3).reshape(-1,3))['closedWound'],
            'Closed outward Shield assembly required')
    sv,sf=geometry['shadowVertices'],geometry['shadowFaces']
    require(4 <= len(sf) <= 500 and topology(sv,sf)['closedWound'], 'Closed outward Shield shadow within500 required')
    return p,n,uv,pane


def model_text(name, texture, geometry, impacts, *, alpha=.3):
    p,n,uv,pane=validate_geometry(geometry)
    require(type(alpha) in (float,int) and math.isfinite(alpha) and 0 < alpha < 1,
            'Explicit translucent pane alpha required')
    rigid=ascii_model(name,texture,p[~pane],n[~pane],uv[~pane],geometry['shadowVertices'],geometry['shadowFaces'])
    blocks=re.findall(r'(?ms)^node trimesh .+?^endnode$',rigid)
    glass=ascii_model(name,texture,p[pane],n[pane],uv[pane],geometry['shadowVertices'],geometry['shadowFaces'])
    glass=re.findall(r'(?ms)^node trimesh .+?^endnode$',glass)[0].replace('node trimesh '+name+'v','node trimesh '+name+'p',1)
    glass=glass.replace('  render 1','  alpha '+format(alpha,'.17g')+'\n  render 1',1)
    require(set(impacts)=={'imp_shield_1','imp_shield_2'}, 'Preserve both native shield impact attachments')
    dummy=[]
    for label,row in impacts.items():
        position=np.asarray(row['position'],float);q=np.asarray(row['orientation'],float)
        require(position.shape==(3,) and q.shape==(4,) and np.isfinite(position).all()
                and np.isfinite(q).all() and abs(np.linalg.norm(q)-1)<1e-6, 'Invalid native impact frame')
        s=np.linalg.norm(q[:3]);axis=q[:3]/s if s>1e-12 else np.array([0.,0.,1.])
        angle=2*math.atan2(s,q[3]); values=np.r_[axis,angle]
        dummy.extend([f'node dummy {label}', f'  parent {name}',
                      '  position '+' '.join(format(float(x),'.17g') for x in position),
                      '  orientation '+' '.join(format(float(x),'.17g') for x in values), 'endnode'])
    prefix=rigid[:rigid.index('node trimesh ')];suffix=rigid[rigid.index('endmodelgeom '):]
    return prefix+'\n'.join(dummy+[blocks[0],glass,blocks[1]])+'\n'+suffix


def blueprint(assigned, identity):
    from .fixture import blueprint as base_blueprint, field
    item=base_blueprint(56,{'modelIndex':1,'colourIndex':1},identity)
    for key,value in assigned['utiParts'].items(): item[key]=field('byte',value)
    return item


def audit(binary,name,texture,geometry,*,alpha=.3):
    from tools.phenomorpher.phenomorpher.engine.stock_armor import native_nodes
    p,n,uv,pane=validate_geometry(geometry)
    clean,meshes,changed=sanitize_and_decode(binary,name,allow_constant_alpha=True,apply_rigid_transforms=True)
    by_name={r['name']:r for r in meshes}
    require(len(meshes)==3 and set(by_name)=={name+'v',name+'p',name+'s'}, 'Exact Shield mesh enumeration required')
    flags={}
    for offset,node_flags in native_nodes(clean):
        require(node_flags in (1,33),'Shield must remain a static dummy/trimesh assembly')
        if node_flags!=33:continue
        label=clean[offset+32:offset+64].split(b'\0')[0].decode('ascii')
        shadow,_,render=struct.unpack_from('<III',clean,offset+0xd4)
        flags[label]={'render':render,'shadow':shadow}
    for suffix,selection in [('v',~pane),('p',pane),('s',None)]:
        row=by_name[name+suffix]; visible=selection is not None
        require(flags[name+suffix]=={'render':int(visible),'shadow':int(not visible)}, 'Wrong Shield render/shadow flags')
        require(row['textures'][0].lower()==(texture if visible else 'null')
                and all(t.lower() in ('','null',texture) for t in row['textures']), 'Unexpected Shield material dependency')
        require(abs(row.get('alpha',1)-(alpha if suffix=='p' else 1))<1e-7,'Native pane opacity changed')
        wanted={'position':p[selection],'normal':n[selection],'uv':uv[selection]} if visible else {
            'position':np.asarray(geometry['shadowVertices'])[geometry['shadowFaces']]}
        for key,target in wanted.items():
            actual=row[key][row['faces']]
            require(actual.shape==target.shape and np.allclose(actual,target,atol=2e-6,rtol=0), 'Shield native roundtrip differs: '+key)
        if not visible: require(topology(row['position'],row['faces'])['closedWound'],'Compiled Shield shadow is not closed/outward')
    return clean,{'nativePositionNormalUVShadowRoundtrip':True,'constantPaneAlpha':alpha,
                  'flags':flags,'zeroedTailBytes':changed,'visibleTriangles':len(p),
                  'shadowTriangles':len(geometry['shadowFaces'])}


def specification_inputs(spec_path):
    from tools.headkit.common import pin,read
    from .firearm_package import stack_inputs
    spec=read(spec_path)
    require({'profile','arrays','texture','icon','impacts'}<=set(spec)<={'profile','arrays','texture','icon','impacts','evidence','appearance','alpha'},
            'Explicit Shield specification required')
    return [pin(spec_path)]+stack_inputs(spec['profile'])+[pin(spec[key]) for key in ('arrays','texture','icon')]+spec.get('evidence',[])


def prepare_specification(spec_path, output):
    from tools.headkit.common import read
    spec=read(spec_path)
    return prepare(spec['profile'],spec['arrays'],spec['texture'],spec['icon'],spec['impacts'],spec.get('evidence',[]),output,
                   appearance=spec.get('appearance',14),alpha=spec.get('alpha',.3))


def prepared_inputs(prepared_dir, compiler):
    from tools.headkit.common import pin,read
    from .native import offline_compiler_inputs
    p=read(Path(prepared_dir)/'prepared.json')
    return [pin(Path(prepared_dir)/'prepared.json')]+p['inputs']+p['outputs']+offline_compiler_inputs(compiler)


def prepare(profile_path, arrays, texture, icon, impacts, evidence, output, *, appearance=14, alpha=.3):
    import shutil
    from PIL import Image
    from tools.headkit.common import pin,read,write,verify,verification_pass
    from .contracts import code_pins,family,native_contract,source_version,whole_shield
    from .firearm_package import stack_inputs
    with verification_pass('shield-prepare'):
        profile=family(profile_path,validate_native=False)
        require(whole_shield(profile),'Explicit qualified whole Shield profile required')
        _,resources=native_contract(profile_path,profile)
        inputs=stack_inputs(profile_path)+[pin(p) for p in (arrays,texture,icon)]+evidence+code_pins()
        verify(inputs)
        identity=profile.get('resources',{})
        require(set(identity)=={'texturePrefix','blueprint','displayName','hak','module'},'Explicit Shield asset identity required')
        assigned=allocation(resources,appearance,identity['texturePrefix'],identity['blueprint'])
        with np.load(arrays,allow_pickle=False) as data: geometry={k:data[k] for k in data.files}
        text=model_text(assigned['models']['whole'],assigned['texture'],geometry,impacts,alpha=alpha)
        out=Path(output);(out/'ascii').mkdir(parents=True,exist_ok=False);(out/'resources').mkdir()
        (out/'ascii'/(assigned['models']['whole']+'.mdl')).write_text(text,encoding='ascii')
        with Image.open(texture) as image:
            require(image.size==(profile['runtimeTextureSize'],)*2,'Shield runtime diffuse size differs')
            image.convert('RGB').save(out/'resources'/(assigned['texture']+'.tga'))
        with Image.open(icon) as image:
            # The render is the logical 2x3 footprint; the stock canvas pads it to a power of two.
            require(image.mode=='RGBA' and image.size in ((64,96),(64,128)),'Shield icon needs its 64x96 render or the stock 64x128 RGBA canvas')
            padded=Image.new('RGBA',(64,128),(0,0,0,0));padded.paste(image,(0,0))
            padded.save(out/'resources'/(assigned['icons']['whole']+'.tga'))
        shutil.copyfile(arrays,out/'expected.npz')
        write(out/(identity['blueprint']+'.json'),blueprint(assigned,identity),fresh=True)
        outputs=[pin(p) for folder in ('ascii','resources') for p in sorted((out/folder).iterdir())]
        outputs += [pin(out/'expected.npz'),pin(out/(identity['blueprint']+'.json'))]
    verify(inputs,fresh=True)
    result={'kind':'shield-native-prepared','baseItem':56,'codeVersion':source_version(),'allocation':assigned,'identity':identity,
            'alpha':alpha,'impacts':impacts,'inputs':inputs,'outputs':outputs,'expected':pin(out/'expected.npz')}
    write(out/'prepared.json',result,fresh=True);return result


def compile_package(prepared_dir,compiler,output):
    import shutil
    import subprocess
    import time
    from tools.headkit.common import pin,read,write,verify,verification_pass
    from tools.phenotypes import tool_runtime
    from tools.phenomorpher.phenomorpher.engine.rig_native import compare
    from .contracts import source_version
    from .native import compile_offline,archive_helpers
    from .firearm_native import audit_blueprint_roundtrip
    started=time.monotonic();prepared_dir=Path(prepared_dir);p=read(prepared_dir/'prepared.json')
    require(p.get('kind')=='shield-native-prepared','Expected whole Shield preparation')
    require(p.get('codeVersion')==source_version(),'Stale Shield preparation code')
    inputs=prepared_inputs(prepared_dir,compiler)
    with verification_pass('shield-native-dispatch'):verify(inputs)
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    converted=out/'converted';shutil.copytree(prepared_dir,converted)
    compile_offline(converted,compiler,out)
    name=p['allocation']['models']['whole'];res=converted/'resources';target=res/(name+'.mdl')
    with np.load(p['expected']['path'],allow_pickle=False) as data:geometry={k:data[k] for k in data.files}
    clean,report=audit(target,name,p['allocation']['texture'],geometry,alpha=p['alpha']);target.write_bytes(clean)
    rig=compare(target,converted/'ascii'/(name+'.mdl'));require(rig['passed'],'Shield impact/static controllers changed')
    write(out/'rig-roundtrip.json',rig,fresh=True)
    gff=tool_runtime.tool('nwn_gff',inputs=[r['path'] for r in inputs]);bp=p['identity']['blueprint']
    source=converted/(bp+'.json');binary=res/(bp+'.uti');readback=out/(bp+'-readback.json')
    for a,b in ((source,binary),(binary,readback)):
        done=subprocess.run([str(gff),'-i',str(a),'-o',str(b)],capture_output=True,text=True,timeout=120,
                            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        require(done.returncode==0,'Shield blueprint conversion failed: '+done.stderr[-1000:])
    bp_report=audit_blueprint_roundtrip(binary,read(readback),read(source))
    expected={name+'.mdl',p['allocation']['texture']+'.tga',p['allocation']['icons']['whole']+'.tga',bp+'.uti'}
    require({f.name for f in res.iterdir()}==expected,'Exact Shield payload differs')
    archive=archive_helpers();types={**archive.TYPES,'uti':2025};files=sorted(res.iterdir());hak=out/(p['identity']['hak']+'.hak')
    archive.write_hak(hak,[(f.stem,types[f.suffix[1:]],f.read_bytes()) for f in files])
    require(archive.payload(hak)=={(f.stem,types[f.suffix[1:]]):pin(f)['sha256'] for f in files},'Shield HAK payload mismatch')
    verify(inputs,fresh=True)
    result={'schemaVersion':1,'kind':'shield-native-package','baseItem':56,'allocation':p['allocation'],
            'identity':p['identity'],'hak':pin(hak),'resources':[pin(f) for f in files],'inputs':inputs,
            'audits':report,'rigAudit':pin(out/'rig-roundtrip.json'),
            'blueprints':[{'file':pin(binary),'utiParts':p['allocation']['utiParts'],'audit':bp_report}],
            'compilationBackend':'neverblender-cleanmodels','elapsedSeconds':time.monotonic()-started,
            'clientValidated':False,'productionAccepted':False}
    write(out/'native.json',result,fresh=True);return result
