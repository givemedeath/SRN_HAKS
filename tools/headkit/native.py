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
    require(matrix.shape==(4,4) and np.isfinite(matrix).all() and np.allclose(matrix[3],[0,0,0,1]),'Invalid fit transform')
    gram=matrix[:3,:3].T@matrix[:3,:3]
    require(np.linalg.det(matrix[:3,:3])>0 and np.allclose(gram,np.eye(3)*gram[0,0],atol=1e-8),'Fit must be a positive uniform similarity')
    return matrix,None if errors is None else errors.tolist()


def prepare(source, shades_path, layers_path, fit, model, output):
    require(re.fullmatch(r'[a-z][a-z0-9_]{0,13}',model) is not None,'Safe NWN model resref required')
    source_pin=pin(source);matrix,errors=fit_matrix(fit,source_pin['sha256'])
    head_export,*_=helpers();points,normals,uv=head_export.triangles(source,matrix,maximum=20000)
    shades=np.asarray(Image.open(shades_path).convert('L'));layers=np.asarray(Image.open(layers_path).convert('L'))
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


def compile_and_package(prepared_dir, client, output):
    verify([client]);prepared_dir=Path(prepared_dir);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    from .common import read
    preparation=read(prepared_dir/'prepared.json');verify([preparation[k] for k in ('source','ascii','plt','expected')])
    converted=output/'converted';shutil.copytree(prepared_dir,converted)
    command=[sys.executable,str(ROOT/'tools/phenotypes/native_compile.py'),'--client',client['path'],
             '--user-directory',str(output/'isolated-compiler'),'--converted',str(converted),'--timeout','120']
    result=subprocess.run(command,capture_output=True,text=True,timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    (output/'compiler.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8');require(result.returncode==0,'Native compiler failed; inspect retained log')
    model=preparation['model'];binary=converted/'resources'/f'{model}.mdl'
    clean,audit=audit_native(binary,model,preparation['expected']['path'])
    resources=output/'resources';resources.mkdir();target=resources/f'{model}.mdl';target.write_bytes(clean)
    plt=resources/f'{model}.plt';plt.write_bytes(Path(preparation['plt']['path']).read_bytes())
    _,hak,*_=helpers();archive=output/f'{model}.hak';hak.write_hak(archive,[(model,2002,clean),(model,6,plt.read_bytes())])
    require(hak.payload(archive)=={(model,2002):pin(target)['sha256'],(model,6):pin(plt)['sha256']},'HAK payload mismatch')
    verify([client]);audit.update(compiler=client,source=preparation['source'],mdl=pin(target),plt=pin(plt),hak=pin(archive),
                clientValidated=False,productionAccepted=False)
    write(output/'native.json',audit,fresh=True);return audit
