"""Decode native head candidates and verify geometry and material byte transport."""
import argparse
from pathlib import Path
import struct
import numpy as np
from PIL import Image
from head_workflow import MAX_TRIANGLES,pin,read,require,validate_target,verify_pins,write_fresh
from head_export import triangles,plt_bytes,model_name
from native_reader import decode
from verify_retexture import corner_error


def audit(export_path,output):
    exported=read(export_path); config=read(exported['configuration']['path'])
    verify_pins([exported['configuration'],exported['source'],exported['target'],exported['fit'],exported['ascii']])
    verify_pins(config['inputs']);validate_target(read(config['target']['path']))
    fit=read(exported['fit']['path']); p,n,uv=triangles(exported['source']['path'],fit['localMatrix'])
    folder=Path(export_path).parent; compile_report=read(folder/'native-compile.json')
    require(compile_report['complete'] is True,'Actual complete native compilation required')
    model=model_name(read(config['target']['path'])['prefix'],config['slot'])
    binary=folder/'resources'/(model+'.mdl'); decoded=decode(binary.read_bytes(),model)
    require(len(decoded)==len(config['groups']),'Native material group count changed')
    errors=[]
    for i,(row,group) in enumerate(zip(decoded,config['groups'])):
        require(row['name']==model+f'p{i}','Unexpected native mesh ownership')
        material=model if group['kind']=='palette' else model+group['suffix']
        require(row['textures'][0]==material,'Native diffuse/PLT dependency changed')
        indices=np.asarray(group['triangles']); faces=row['faces']
        error=corner_error((p[indices],n[indices],uv[indices]),
                           (row['position'][faces],row['normal'][faces],row['uv'][faces]),2e-6)
        require(np.allclose(np.linalg.norm(row['normal'],axis=1),1,atol=2e-3),'Nonunit native normals')
        tangent=row['tangent']; lengths=np.linalg.norm(tangent,axis=1)
        require(np.all(lengths>.9) and np.all(lengths<1.1),'Missing or nonunit native normal-map tangents')
        require(np.max(np.abs(np.einsum('ij,ij->i',tangent,row['normal'])))<.02,'Native tangent/normal basis invalid')
        mtr=(folder/'resources'/(material+'.mtr')).read_text(encoding='ascii')
        require('renderhint NormalTangents\n' in mtr and 'parameter float Roughness 0\n' in mtr
                and f'texture1 {material}n\n' in mtr and f'texture3 {material}r\n' in mtr,'Material transport changed')
        for key,suffix in [('normal','n'),('roughness','r')]+([('color','')] if group['kind']=='fixed' else []):
            with Image.open(group[key]) as source,Image.open(folder/'resources'/(material+suffix+'.tga')) as returned:
                require(source.size==returned.size==(1024,1024),'Runtime map dimensions changed')
                require(np.array_equal(np.asarray(source.convert('RGB')),np.asarray(returned.convert('RGB'))),'Runtime map pixels changed')
        errors.append({'mesh':row['name'],'triangles':len(faces),'maximumAttributeError':float(error.max()),'normalMapTangentsVerified':True})
    with Image.open(config['shades']) as a,Image.open(config['layers']) as b:
        require(a.mode==b.mode=='L','Explicit byte palette masks required')
        require((folder/'resources'/(model+'.plt')).read_bytes()==plt_bytes(np.asarray(a),np.asarray(b)),'Native palette byte order or labels differ')
    resources=[pin(path) for path in sorted((folder/'resources').iterdir())]
    verify_pins(resources);verify_pins(config['inputs'])
    require(sum(row['triangles'] for row in errors)==len(p)<=MAX_TRIANGLES,'Native total budget exceeded')
    write_fresh(output,{'kind':'srn-head-native-audit','passed':True,'export':pin(export_path),
        'compilation':pin(folder/'native-compile.json'),'model':pin(binary),'resources':resources,'meshes':errors,
        'triangles':len(p),'textureSize':1024,'geometryUvNormalsVerified':True,'paletteMasksVerified':True,
        'materialTransportVerified':True,'bodyResourcesUnchanged':True,'clientValidated':False,'productionAccepted':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();audit(args.export,args.output)
