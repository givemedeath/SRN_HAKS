"""Offline selected GLB -> ASCII/map audit. Native TBN and client remain pending."""
import argparse
import json
from pathlib import Path
import re
import struct
import numpy as np
from PIL import Image
from audit_native_limb_shading import validate_target, maximum_errors
from stage_stock_part import arrays, raw_triangles, sha, require, save


def audit(converted, config_path):
    converted=Path(converted).resolve(); config_path=Path(config_path).resolve()
    config=json.loads(config_path.read_text()); part,model=validate_target(config)
    require(config.get('normalStrength',1)==1 and config.get('skinLayer',0)==0,
            'Unchanged all-skin maps required')
    paths={k:Path(config[k]) for k in ('source','color','normal')}
    for k,p in paths.items():require(sha(p)==config['expectedInputHashes'][k],'Selected source/map changed: '+k)
    source_p,source_uv,source_n,_=raw_triangles(paths['source'],paths['color'],paths['normal'])
    ascii_path=converted/'ascii'/(model+'.mdl'); text=ascii_path.read_text()
    require(not re.search(r'(?mi)^\s*newanim\s',text) and re.search(
        r'(?mi)^\s*setsupermodel\s+'+re.escape(model)+r'\s+NULL\s*$',text),'Part changes stock rig/animations')
    p,n,u=[np.asarray(arrays(text,k)) for k in ('verts','normals','tverts')]
    f=np.asarray(arrays(text,'faces'),dtype=int)
    actual={'position':p[f[:,:3]],'normal':n[f[:,:3]],'uv':u[f[:,4:7],:2]}
    source={'position':source_p,'normal':source_n,'uv':source_uv}
    errors={k:maximum_errors(actual[k],source[k]) for k in source}
    require(all(e==0 for e in errors.values()),'ASCII ordered P/N/UV differ from selected source')
    require(np.isfinite(source_n).all() and np.min(np.linalg.norm(source_n,axis=2))>.5,'Invalid authored normals')
    du1=source_uv[:,1]-source_uv[:,0];du2=source_uv[:,2]-source_uv[:,0]
    determinant=du1[:,0]*du2[:,1]-du1[:,1]*du2[:,0]; valid=np.abs(determinant)>1e-12
    require(np.isfinite(determinant).all() and valid.any(),'No finite nondegenerate source UV differential')
    tangent=((source_p[:,1]-source_p[:,0])[valid]*du2[valid,1,None]
             -(source_p[:,2]-source_p[:,0])[valid]*du1[valid,1,None])/determinant[valid,None]
    require(np.isfinite(tangent).all(),'Nonfinite geometric UV tangent')
    resources=converted/'resources';mtr=resources/(model+'.mtr');plt=resources/(model+'.plt');normal=resources/(model+'n.tga')
    mt=mtr.read_text()
    require(re.search(r'(?mi)^\s*renderhint\s+NormalTangents\s*$',mt)
        and re.search(r'(?mi)^\s*texture1\s+'+re.escape(model+'n')+r'\s*$',mt),'Wrong intended normal material binding')
    blob=plt.read_bytes()
    require(blob[:8]==b'PLT V1  ' and struct.unpack_from('<IIII',blob,8)==(10,0,2048,2048)
        and len(blob)==24+2048*2048*2,'Invalid exact2K palette')
    pixels=np.frombuffer(blob,np.uint8,offset=24).reshape(2048,2048,2)[::-1]
    color=np.asarray(Image.open(paths['color']).convert('RGB'))
    expected=np.clip(color.astype(float)@[.2126,.7152,.0722],0,255).astype(np.uint8)
    require(np.array_equal(pixels[:,:,0],expected) and not pixels[:,:,1].any(),'Palette differs from unchanged skin0 material')
    require(np.array_equal(np.asarray(Image.open(normal).convert('RGB')),
        np.asarray(Image.open(paths['normal']).convert('RGB'))),'Normal pixels changed')
    return {'schemaVersion':1,'offlineAsciiMaterialPassed':True,'part':part,'model':model,
        'sourceToAsciiOrderedCornerMaximumErrors':errors,'sourceUvDifferential':{
        'nondegenerateTriangles':int(valid.sum()),'degenerateTriangles':int((~valid).sum()),
        'finiteGeometricTangents':True,'actualNativeTangentArraysVerified':False},
        'plt2KSkin0LuminanceExact':True,'normalTgaPixelsExact':True,'stockRigAnimationPolicyExact':True,
        'nativeCompilePending':True,'nativeTbnPending':True,'clientValidationPending':True,
        'compilerExecuted':False,'clientControlled':False,
        'files':{str(p.resolve()):sha(p) for p in [config_path,ascii_path,mtr,plt,normal,*paths.values(),Path(__file__)]}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('converted','config','output'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();result=audit(args.converted,args.config)
    args.output.mkdir(parents=True,exist_ok=False);save(args.output/'audit.json',result)
    print(json.dumps({'offlineAsciiMaterialPassed':True,'nativeTbnPending':True}))


if __name__=='__main__':main()
