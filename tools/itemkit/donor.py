"""Bake appearance in its original frame, then retain a diffuse textured donor."""
from pathlib import Path
import numpy as np
from tools.headkit.common import require,pin,write,verify,read,verification_pass
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


def unwrap_source(source,local,output,*,topology_policy='closed-solid-v1'):
    """Unwrap colour sampling surfaces separately from fitted native solids.

    UDF donors may contain open edges or nested skins. Atlas sampling requires
    finite, nondegenerate faces and unchanged geometry; it does not require a
    closed solid. Native/working/shadow closure gates remain in their stages.
    Legacy callers retain their original closed-solid requirement.
    """
    from tools.headkit.gltf import mesh,write_mesh
    from .source_atlas import unwrap
    require(topology_policy in ('closed-solid-v1','sampling-surface-v1'),'Unknown donor topology policy')
    output=Path(output);output.mkdir(exist_ok=False)
    original=mesh(source)
    from .geometry import topology
    physical=topology(original['positions'],original['faces'])
    sampling_source=Path(source);cleanup=None
    if topology_policy=='closed-solid-v1':
        require(physical['closedWound'],'Non-manifold or incorrectly wound source blocks UV/bake processing')
    else:
        p=np.asarray(original['positions'],float)[original['faces']]
        areas=np.linalg.norm(np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]),axis=1)/2
        # Later area gates see the stored float32 positions, so a face zero there is degenerate too.
        single=np.asarray(original['positions'],np.float32)[original['faces']]
        bad=(areas==0)|(np.linalg.norm(np.cross(single[:,1]-single[:,0],single[:,2]-single[:,0]),axis=1)==0)
        if bad.any():
            require(bad.mean()<.03 and areas.sum()>0,'Degenerate donor surface blocks UV/bake processing')
            keep=np.asarray(original['faces'])[~bad]
            used,indices=np.unique(keep,return_inverse=True)
            normals=original.get('normals')
            original=dict(original,positions=original['positions'][used],faces=indices.reshape(-1,3),
                          normals=normals[used] if normals is not None else None,uv=original['uv'][~bad])
            sampling_source=output/'sampling-source.glb'
            write_mesh(sampling_source,original['positions'],original['faces'],original['uv'],original['normals'])
            cleanup={'removedZeroAreaFaces':int(bad.sum()),'removedSurfaceArea':float(areas[bad].sum()),'remainingCornersExact':True}
    unwrapped,report=unwrap(original,local,output/'atlas')
    path=output/'source-uv.glb'
    write_mesh(path,unwrapped['positions'],unwrapped['faces'],unwrapped['uv'],unwrapped['normals'])
    result={'uvMesh':pin(path),'frame':geometry_frame(sampling_source,path),'atlas':report,'physicalTopology':physical,'fitApplied':False}
    if topology_policy!='closed-solid-v1':
        result.update(topologyPolicy=topology_policy,source=pin(source),samplingSource=pin(sampling_source),nativeGeometryApproved=False)
        if cleanup is not None:result['samplingCleanup']=cleanup
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
    maps=bake(uv_mesh,field,output/'maps',allow_decoder_overshoot=True,derived_surface='diagnostic')
    verify([field_pin], fresh=True)
    donor=embed_diffuse(uv_mesh,maps['maps']['basecolor-4096.png']['path'],output/'textured-donor.glb')
    result={'donor':donor,'uvMesh':pin(uv_mesh),'source':pin(source),'field':field_pin,'maps':maps,
            'frame':frame,'fitApplied':False,'fieldPolicy':policy,'visualApproval':False}
    write(output/'donor.json',result,fresh=True);return result


def add_source_matched_caps(source, texture, target, fit, diagnostic, local, output, *, part='whole',sampling_triangle_allowance=0):
    """Bounded facing repairs with original baked RGB and unchanged mapped texels.

    Faces come from this target's failed preflight, never a historical ID list.
    New sampling triangles do not modify the visible target or its UVs. Colour
    comes from the original textured donor within3mm, not a transformed field.
    """
    import hashlib,time
    from PIL import Image
    from tools.headkit.common import library
    from tools.headkit.gltf import write_mesh
    from .transfer import sample_image
    from .preflight import target_hash
    rows=[source,texture,target,fit,diagnostic]
    with verification_pass('source-matched-donor-caps'):
        verify(rows);begun=time.monotonic();report=read(diagnostic['path'])
        require(set(report.get('blockers',()))=={'donor-distance-or-facing'},
                'Repair only a measured donor-distance/facing preflight failure')
        ids=np.asarray(report['donorSampling']['failedFaces'])
        require(ids.ndim==1 and len(ids)>0 and np.issubdtype(ids.dtype,np.integer)
                and len(np.unique(ids))==len(ids),'Distinct measured repair faces required')
        ids=np.sort(ids)
        with np.load(target['path'],allow_pickle=False) as archive:
            p,f=archive[part+'_positions'],archive[part+'_faces']
            target_uv=archive[part+'_uv']
        require(report.get('targetHash')==target_hash(p[f],target_uv),
                'Repair diagnostic belongs to different target geometry or UVs')
        require(ids.min()>=0 and ids.max()<len(f),'Repair face outside this target')
        corners=p[f];area=np.linalg.norm(np.cross(corners[:,1]-corners[:,0],corners[:,2]-corners[:,0]),axis=1)/2
        fraction=float(area[ids].sum()/area.sum())
        require(len(ids)<len(f)*.01 and fraction<.005,'Source-matched cap repair exceeded bounded surface scope')
        v,df,attrs=arrays(*load(Path(source['path']).read_bytes()))
        uv=attrs['TEXCOORD_0'][df];normals=attrs['NORMAL'][df]
        require(type(sampling_triangle_allowance)is int and 0<=sampling_triangle_allowance<=128,
                'Bounded auxiliary sampling allowance required')
        # The qualified original donor stays <=200K and unchanged. An explicit
        # allowance covers only measured auxiliary transfer patches, never the
        # visible/native target or the exported source donor contract.
        require(uv[:,:,0].max()<.992 and len(df)<=200000
                and len(df)+len(ids)<=200000+sampling_triangle_allowance,
                'Donor needs the qualified unused colour strip and200K budget')
        matrix=np.asarray(read(fit['path'])['rawToNativeMatrix'],float)
        require(matrix.shape==(4,4) and np.isfinite(matrix).all() and np.allclose(matrix[3],[0,0,0,1])
                and np.linalg.det(matrix[:3,:3])>0 and np.allclose(matrix[:3,:3].T@matrix[:3,:3],
                    np.eye(3)*np.sum(matrix[:3,0]**2),atol=1e-10,rtol=1e-7),'Positive uniform donor fit required')
        fitted=v@matrix[:3,:3].T+matrix[:3,3];points=corners[ids].reshape(-1,3)
        igl=library(local,'igl');distance,nearest,closest=igl.point_mesh_squared_distance(points,fitted,df)
        maximum=float(np.sqrt(distance.max()));require(maximum<=.003,'Repair-cap RGB source exceeds3mm')
        tri=fitted[df[nearest]];a=tri[:,1]-tri[:,0];b=tri[:,2]-tri[:,0];q=closest-tri[:,0]
        aa=(a*a).sum(1);bb=(b*b).sum(1);ab=(a*b).sum(1);aq=(a*q).sum(1);bq=(b*q).sum(1);den=aa*bb-ab*ab
        require(np.all(den>0),'Degenerate repair colour source')
        u=(bb*aq-ab*bq)/den;w=(aa*bq-ab*aq)/den;bary=np.c_[1-u-w,u,w]
        require(bary.min()>=-1e-5 and bary.max()<=1+1e-5,'Repair colour point left its source triangle')
        bary=np.clip(bary,0,1);bary/=bary.sum(1)[:,None];sample_uv=(uv[nearest]*bary[:,:,None]).sum(1)
        with Image.open(texture['path']) as image:
            require(image.size==(4096,4096),'Original4K baked donor colour required')
            original=np.asarray(image.convert('RGB')).copy()
        pixels=np.flipud(original).copy()
        # Raw glTF V runs top-down in the donor PNG; `pixels` is the sampler's bottom-up order.
        colours=sample_image(pixels.astype(float)/255,sample_uv*[1,-1]+[0,1],repeat=False,decode_srgb=True).reshape(-1,3,3)
        changed=np.zeros((4096,4096),bool);patch_uv=[]
        for k,colour in enumerate(colours):
            x0=4074;y0=32+k*32;side=16
            require(y0+side+4<4096,'Bounded cap palette exhausted')
            xx,yy=np.meshgrid(np.arange(x0-3,x0+side+4),np.arange(y0-3,y0+side+4))
            u=np.clip((xx+.5-x0)/side,0,1);w=np.clip((yy+.5-y0)/side,0,1);total=np.maximum(1,u+w);u/=total;w/=total
            linear=colour[0]+u[:,:,None]*(colour[1]-colour[0])+w[:,:,None]*(colour[2]-colour[0])
            srgb=np.where(linear<=.0031308,12.92*linear,1.055*np.power(linear,1/2.4)-.055)
            pixels[yy,xx]=np.rint(np.clip(srgb,0,1)*255).astype(np.uint8);changed[yy,xx]=True
            patch_uv.append([[x0/4096,1-y0/4096],[(x0+side)/4096,1-y0/4096],[x0/4096,1-(y0+side)/4096]])
        require(np.array_equal(pixels[~changed],np.flipud(original)[~changed]),'Healthy donor RGB changed')
        inverse=np.linalg.inv(matrix);raw=(np.c_[points,np.ones(len(points))]@inverse.T)[:,:3]
        added=np.arange(len(v),len(v)+len(raw)).reshape(-1,3)
        caps=raw.reshape(-1,3,3);cn=np.cross(caps[:,1]-caps[:,0],caps[:,2]-caps[:,0]);cn/=np.linalg.norm(cn,axis=1)[:,None]
        out=Path(output);out.mkdir(exist_ok=False);colour_path=out/'donor-diffuse-4096.png'
        Image.fromarray(np.flipud(pixels),'RGB').save(colour_path)
        mesh=out/'sampling-donor.glb';write_mesh(mesh,np.r_[v,raw],np.r_[df,added],
            np.r_[uv,np.asarray(patch_uv)],np.r_[normals,np.repeat(cn[:,None,:],3,axis=1)])
        vv,ff,attributes=arrays(*load(mesh.read_bytes()))
        require(np.array_equal(vv[ff[:len(df)]],v[df])
                and np.array_equal(attributes['TEXCOORD_0'][ff[:len(df)]],uv)
                and np.array_equal(attributes['NORMAL'][ff[:len(df)]],normals),'Original donor attributes changed')
        donor=embed_diffuse(mesh,colour_path,out/'textured-donor.glb');verify(rows,fresh=True)
        result={'donor':donor,'source':source,'originalTexture':texture,'target':target,'fit':fit,'diagnostic':diagnostic,
            'texture':pin(colour_path),'targetCornerHash':hashlib.sha256(np.asarray(corners,dtype='<f8').tobytes()).hexdigest(),
            'explicitRepairCapFaces':ids.tolist(),'capSurfaceFraction':fraction,'maximumLocalColourSampleDistance':maximum,
            'capColourMethod':'linear interpolation of nearby original baked donor RGB',
            'originalMappedTexelsExact':True,'originalGeometryAndUVMappingsExact':True,'targetGeometryAndUVsUnchanged':True,
            'originalFieldUntouched':True,'seconds':time.monotonic()-begun,'visualReviewPending':True}
        result.update(originalDonorTriangles=len(df),auxiliarySamplingTriangles=len(ids),
                      samplingTriangleAllowance=sampling_triangle_allowance,
                      derivedSamplingTriangles=len(df)+len(ids),nativeTargetTriangleAllowance=0)
        write(out/'result.json',result,fresh=True);return result
