"""Bake appearance in its original frame, then retain a diffuse textured donor."""
from pathlib import Path
import numpy as np
from tools.headkit.common import require,pin,write,verify
from tools.headkit.gltf import load,arrays,encode,require_textured_uvs


def geometry_frame(source,uv_mesh):
    def canonical(path):
        v,f,_=arrays(*load(Path(path).read_bytes()));corners=v[f]
        order=np.lexsort((corners[:,:,2],corners[:,:,1],corners[:,:,0]),axis=1)
        flat=np.take_along_axis(corners,order[:,:,None],axis=1).reshape(-1,9)
        sequence=np.lexsort(tuple(flat[:,i] for i in range(8,-1,-1)))
        cross=np.cross(corners[:,1]-corners[:,0],corners[:,2]-corners[:,0])
        lengths=np.linalg.norm(cross,axis=1)
        require(np.all(lengths>0),'Degenerate donor source triangle')
        return flat[sequence],(cross/lengths[:,None])[sequence]
    a,an=canonical(source);b,bn=canonical(uv_mesh)
    require(a.shape==b.shape and np.allclose(a,b,atol=2e-6,rtol=0)
            and np.all(np.einsum('ij,ij->i',an,bn)>.999),
            'Source unwrap changed geometry or left the original appearance-field frame')
    return {'originalFieldFrame':True,'maximumCoordinateDifference':float(np.max(np.abs(a-b)))}


def unwrap_source(source,local,output):
    from tools.headkit.gltf import mesh,write_mesh
    from .source_atlas import unwrap
    output=Path(output);output.mkdir(exist_ok=False)
    original=mesh(source)
    from .geometry import topology
    physical=topology(original['positions'],original['faces'])
    require(physical['closedWound'],'Non-manifold or incorrectly wound source blocks UV/bake processing')
    unwrapped,report=unwrap(original,local,output/'atlas')
    path=output/'source-uv.glb'
    write_mesh(path,unwrapped['positions'],unwrapped['faces'],unwrapped['uv'],unwrapped['normals'])
    result={'uvMesh':pin(path),'frame':geometry_frame(source,path),'atlas':report,'physicalTopology':physical,'fitApplied':False}
    write(output/'unwrap.json',result,fresh=True);return result


def embed_diffuse(source,texture,output):
    from PIL import Image
    require_textured_uvs(source)
    with Image.open(texture) as image:require(image.format=='PNG' and image.size==(4096,4096),'4K PNG donor diffuse required')
    d,b,p=load(Path(source).read_bytes());before=arrays(d,b,p)[:2]
    png=Path(texture).read_bytes();offset=len(b);blob=b+png
    d['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':len(png)})
    d['images']=[{'bufferView':len(d['bufferViews'])-1,'mimeType':'image/png'}]
    d['samplers']=[{'magFilter':9729,'minFilter':9987,'wrapS':33071,'wrapT':33071}]
    d['textures']=[{'sampler':0,'source':0}]
    d['materials']=[{'name':'donor-diffuse','pbrMetallicRoughness':{'baseColorTexture':{'index':0},
                     'baseColorFactor':[1,1,1,1],'metallicFactor':0,'roughnessFactor':1},'alphaMode':'OPAQUE'}]
    p['material']=0;d['buffers'][0]['byteLength']=len(blob)
    with Path(output).open('xb') as stream:stream.write(encode(d,blob))
    after=arrays(*load(Path(output).read_bytes()))[:2]
    require(all(np.array_equal(a,b) for a,b in zip(before,after)),'Donor texture embedding changed geometry')
    require_textured_uvs(output);return pin(output)


def field_policy(policy,field_sha256):
    """Legacy explicit bounds remain valid; new ranges bind the reviewed field."""
    legacy={'minimum':-.02,'maximum':1.032,'allowDecoderOvershoot':True}
    require(isinstance(policy,dict) and set(policy) in (set(legacy),set(legacy)|{'fieldSha256'}),
            'Explicit reviewed source-field range policy required')
    low,high=policy['minimum'],policy['maximum']
    require(type(low) in (int,float) and type(high) in (int,float)
            and np.isfinite([low,high]).all() and -.25<=low<=0 and 1<=high<=1.25
            and policy['allowDecoderOvershoot'] is True,
            'Reviewed decoder bounds must be finite within [-0.25,1.25] and include [0,1]')
    if 'fieldSha256' in policy:
        digest=policy['fieldSha256']
        require(isinstance(digest,str) and len(digest)==64 and all(c in '0123456789abcdef' for c in digest)
                and digest==field_sha256,'Source-field range review does not match field bytes')
    else:require(policy==legacy,'A custom source-field range requires its reviewed fieldSha256')
    return dict(policy)


def build(source,uv_mesh,field,policy,output):
    from tools.headkit.textures import bake
    field_pin=pin(field);policy=field_policy(policy,field_pin['sha256'])
    frame=geometry_frame(source,uv_mesh)
    with np.load(field,allow_pickle=False) as archive:
        require(set(archive.files)=={'coords','attrs','resolution'},'Unexpected donor field transport')
        values=archive['attrs']
        require(values.ndim==2 and values.shape[1]==6 and len(values)>0 and np.isfinite(values).all(),
                'Donor field requires nonempty finite six-channel values')
        require(values.min()>=policy['minimum'] and values.max()<=policy['maximum'],
                'Donor field exceeds the reviewed decoder range')
    del values
    output=Path(output);output.mkdir(exist_ok=False)
    maps=bake(uv_mesh,field,output/'maps',allow_decoder_overshoot=True)
    verify([field_pin])
    donor=embed_diffuse(uv_mesh,maps['maps']['basecolor-4096.png']['path'],output/'textured-donor.glb')
    result={'donor':donor,'uvMesh':pin(uv_mesh),'source':pin(source),'field':field_pin,'maps':maps,
            'frame':frame,'fitApplied':False,'fieldPolicy':policy,'visualApproval':False}
    write(output/'donor.json',result,fresh=True);return result
