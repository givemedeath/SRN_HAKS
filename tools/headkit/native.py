"""Rigid fitting and PLT-only native packaging using maintained repository exporters."""
from pathlib import Path
import re
import subprocess
import shutil
import sys
import numpy as np
from PIL import Image
from .common import ROOT, require, verify, pin, write
from .images import similarity
from .native_reader import decode

MDL_COMPILER = 'mdl-compiler.json'


def helpers():
    sys.path.insert(0,str(ROOT/'tools/heads'))
    import head_export,verify_head_hak
    sys.path.insert(0,str(ROOT/'tools/phenomorpher'))
    from phenomorpher.engine.stock_armor import sanitize_binary,string_fields,leaked_text
    return head_export,verify_head_hak,sanitize_binary,string_fields,leaked_text


def fit_matrix(config, source_sha):
    if 'matrix' in config:
        require(config.get('reviewed') is True and config.get('sourceSha256')==source_sha,
                'Reusing a fit needs review bound to this exact source')
        matrix=np.asarray(config['matrix'],float);errors=None
    else:
        landmarks=config['landmarks']
        a=np.asarray([x['sourceNwnBasis'] for x in landmarks]);b=np.asarray([x['targetNwnLocal'] for x in landmarks])
        scale,rotation,translation,errors=similarity(a,b,config.get('maximumRelativeResidual',.02))
        matrix=np.eye(4);matrix[:3,:3]=scale*rotation.T;matrix[:3,3]=translation
    from .mesh import checked_fit
    return checked_fit(matrix),None if errors is None else errors.tolist()


def prepare(source, shades_path, layers_path, fit, model, output):
    require(re.fullmatch(r'[a-z][a-z0-9_]{0,13}',model) is not None,'Safe NWN model resref required')
    with Image.open(shades_path) as image:
        require(image.mode=='L' and image.size==(1024,1024),'Runtime shades must be 1K eight-bit grayscale')
        shades=np.asarray(image).copy()
    require(np.all(shades<255),'Reserved PLT shade 255 is not permitted')
    with Image.open(layers_path) as image:
        require(image.mode=='L','Ownership masks must be eight-bit L images')
        layers=np.asarray(image).copy()
    require(layers.shape==(1024,1024) and np.all(layers<=9),'Runtime ownership must be 1K channel IDs 0..9')
    source_pin=pin(source);matrix,errors=fit_matrix(fit,source_pin['sha256'])
    head_export,*_=helpers();points,normals,uv=head_export.triangles(source,matrix,maximum=20000)
    # One PLT covers all surfaces, including independently reviewed accessory channels.
    payload=head_export.plt_bytes(shades,layers)
    ascii_text=head_export.ascii_model(model,points,normals,uv,[{'kind':'palette','triangles':list(range(len(points)))}])
    output=Path(output);(output/'ascii').mkdir(parents=True,exist_ok=False);(output/'resources').mkdir()
    (output/'ascii'/f'{model}.mdl').write_text(ascii_text,encoding='ascii')
    (output/'resources'/f'{model}.plt').write_bytes(payload)
    np.savez(output/'expected-native.npz',positions=points,normals=normals,uv=uv)
    result={'source':source_pin,'matrix':matrix.tolist(),'landmarkErrors':errors,'model':model,'triangles':len(points),
            'ascii':pin(output/'ascii'/f'{model}.mdl'),'plt':pin(output/'resources'/f'{model}.plt'),
            'expected':pin(output/'expected-native.npz'),'fitReviewRequired':True,'clientValidated':False}
    write(output/'prepared.json',result,fresh=True);return result


def audit_native(binary, model, expected_path):
    _,_,sanitize,fields,leaks=helpers();original=Path(binary).read_bytes();clean=sanitize(original)
    allowed=np.zeros(len(original),bool)
    for offset,size in fields(original): allowed[offset:offset+size]=True
    changed=np.frombuffer(original,np.uint8)!=np.frombuffer(clean,np.uint8)
    require(not changed[~allowed].any() and sanitize(clean)==clean and not leaks(clean),'Unsafe native sanitization')
    before=decode(original,model,require_tangents=False);after=decode(clean,model,require_tangents=False)
    require(len(before)==len(after)==1,'Exactly one rigid PLT mesh required')
    require(after[0]['textures'][0]==model and all(name.lower() in ('','null',model) for name in after[0]['textures'][1:]),
            'Unexpected native texture dependency')
    result={'model':model,'zeroedTailBytes':int(changed.sum()),'onlyFixedStringFieldsChanged':True}
    with np.load(expected_path,allow_pickle=False) as expected:
        for name,key in [('positions','position'),('normals','normal'),('uv','uv')]:
            old=before[0][key][before[0]['faces']];new=after[0][key][after[0]['faces']]
            require(np.array_equal(old,new),'Sanitizer changed decoded geometry')
            require(expected[name].shape==new.shape and np.allclose(expected[name],new,atol=2e-6,rtol=0),'Native roundtrip mismatch: '+name)
            result[name+'MaximumError']=float(np.max(np.abs(expected[name]-new)))
        require(0<len(expected['positions'])<=20000,'Native triangle budget exceeded')
    return clean,result


def neverblender():
    sys.path.insert(0,str(ROOT/'tools/phenomorpher'))
    from phenomorpher.engine import neverblender_mdl
    return neverblender_mdl


def mdl_compiler(path):
    """The local Blender + Neverblender binding: mdl-compiler.json beside bindings.json, {"blender": {"path", "sha256"},
    "neverblender": {"path"}} (machine paths, never a portable lock). It sits outside bindings.json because the bindings
    hash binds every stage, and only native compiles with it."""
    from .common import read
    config=read(path);blender=config['blender'];verify([blender])
    addon=Path(config['neverblender']['path']);require(addon.is_absolute(),'Absolute Neverblender add-on path required')
    return {'blender':blender,'neverblender':str(addon)}


def mdl_compiler_files(path):
    """Files a native launch consumes through the binding: the binding, the Blender executable and the add-on tree."""
    config=mdl_compiler(path)
    return [pin(path)]+[pin(p) for p in sorted(neverblender().declared_files(config['blender']['path'],config['neverblender']))]


def precompile(prepared_dirs, mdl, folder):
    """One headless Blender run for several heads' prepared exports (headkit `batch`): each gets folder/NN/converted with
    its binary and its own native-compile.json, which compile_and_package then reuses as that head's `cache`. Returns
    {resolved prepared dir: converted folder}."""
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False);targets=[]
    for index,prepared in enumerate(prepared_dirs):
        target=folder/f'{index:02d}'/'converted';shutil.copytree(prepared,target);targets.append(target)
    neverblender().compile_folders(mdl['blender']['path'],mdl['neverblender'],targets,(),300+60*len(targets))
    return {str(Path(prepared).resolve()):target for prepared,target in zip(prepared_dirs,targets)}


def compile_and_package(prepared_dir, client, output, mdl=None, cache=None):
    """Compile the prepared ASCII model to a binary MDL and package it. With `mdl` (mdl_compiler) the compile runs in
    headless Blender through the Neverblender add-on's bundled cleanmodels compiler; without it, through the EE client's
    compilemodel (kept so earlier receipts replay). `cache` (from precompile) supplies a binary compiled by the same
    compiler from identical sources and lookups; Neverblender reuses it only then, and it is audited like a fresh one."""
    tool=client if mdl is None else mdl['blender']
    require(mdl is not None or cache is None,'A precompiled cache needs the Neverblender compiler')
    verify([tool]);prepared_dir=Path(prepared_dir);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    from .common import read
    preparation=read(prepared_dir/'prepared.json');verify([preparation[k] for k in ('source','ascii','plt','expected')])
    converted=output/'converted';shutil.copytree(prepared_dir,converted)
    if mdl is None:
        command=[sys.executable,str(ROOT/'tools/phenotypes/native_compile.py'),'--client',client['path'],
                 '--user-directory',str(output/'isolated-compiler'),'--converted',str(converted),'--timeout','120']
        result=subprocess.run(command,capture_output=True,text=True,timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        (output/'compiler.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8');require(result.returncode==0,'Native compiler failed; inspect retained log')
        compiler=client
    else:
        try:receipt=neverblender().compile_folder(mdl['blender']['path'],mdl['neverblender'],converted,(),600,cache=cache)
        except Exception as error:
            (output/'compiler.log').write_text(repr(error),encoding='utf-8');raise ValueError('Neverblender compile failed; inspect retained log') from error
        require(receipt.get('complete') is True and receipt.get('compiled',0)+receipt.get('reused',0)==1
                and (cache is not None or receipt.get('compiled')==1),'Neverblender compile incomplete')
        engine=Path(neverblender().__file__).parent
        compiler=dict(receipt['compiler'],mode=receipt['executionMode'],compilerSha256=receipt['compilerSha256'],
                      blenderVersion=receipt['blenderVersion'],receipt=pin(converted/'native-compile.json'),
                      engine=[pin(engine/name) for name in ('neverblender_mdl.py','neverblender_worker.py','rig_native.py')])
        if receipt.get('reused'):compiler['precompiled']=pin(Path(cache)/'native-compile.json')
    model=preparation['model'];binary=converted/'resources'/f'{model}.mdl'
    clean,audit=audit_native(binary,model,preparation['expected']['path'])
    resources=output/'resources';resources.mkdir();target=resources/f'{model}.mdl';target.write_bytes(clean)
    plt=resources/f'{model}.plt';plt.write_bytes(Path(preparation['plt']['path']).read_bytes())
    _,hak,*_=helpers();archive=output/f'{model}.hak';hak.write_hak(archive,[(model,2002,clean),(model,6,plt.read_bytes())])
    require(hak.payload(archive)=={(model,2002):pin(target)['sha256'],(model,6):pin(plt)['sha256']},'HAK payload mismatch')
    verify([tool]);audit.update(compiler=compiler,source=preparation['source'],mdl=pin(target),plt=pin(plt),hak=pin(archive),
                clientValidated=False,productionAccepted=False)
    write(output/'native.json',audit,fresh=True);return audit
