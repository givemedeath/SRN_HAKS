"""Stage one GLB body-part replacement with raw attributes and stock context.

Bundled Python only; no Blender round trip, native compiler or client launch.
"""
import argparse
from collections import Counter
from io import BytesIO
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

import numpy as np
from PIL import Image

from audit_geometry import arrays
from scale_fitted_body import read_glb
from validate_terminal_fit import accessor
from retarget import nodes, transforms


def require(test, message):
    if not test:raise RuntimeError(message)


def sha(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def raw_triangles(source, color, normal):
    doc, buffer=read_glb(source)
    require(not doc.get('animations') and not doc.get('skins'), 'Detached part must contain no animation/skin rig')
    basis=np.array([[1.,0,0],[0,0,-1.],[0,1.,0]])
    result=[]; uvrows=[]; normalrows=[]; materials=[]
    children={c for n in doc.get('nodes',[]) for c in n.get('children',[])}
    roots=doc.get('scenes',[{}])[doc.get('scene',0)].get('nodes',[i for i in range(len(doc.get('nodes',[]))) if i not in children])
    def image_pixels(texture):
        require(texture.get('texCoord',0)==0 and not texture.get('extensions'), 'Texture must use unchanged TEXCOORD_0')
        tex=doc['textures'][texture['index']]; record=doc['images'][tex['source']]
        require('bufferView' in record and not record.get('uri'), 'Expected embedded common atlas')
        view=doc['bufferViews'][record['bufferView']]
        offset=view.get('byteOffset',0)
        return np.asarray(Image.open(BytesIO(buffer[offset:offset+view['byteLength']])).convert('RGB'))
    expected_color=np.asarray(Image.open(color).convert('RGB'))
    expected_normal=np.asarray(Image.open(normal).convert('RGB'))
    require(expected_color.shape==expected_normal.shape==(2048,2048,3), 'Expected matching common 2K maps')
    def visit(index,parent,seen):
        require(index not in seen,'glTF node cycle')
        node=doc['nodes'][index]
        require('skin' not in node,'Unexpected source skin')
        if 'matrix' in node:
            local=np.asarray(node['matrix'],dtype=float).reshape(4,4,order='F')
        else:
            x,y,z,w=node.get('rotation',[0,0,0,1])
            r=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                        [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                        [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
            local=np.eye(4);local[:3,:3]=r@np.diag(node.get('scale',[1,1,1]));local[:3,3]=node.get('translation',[0,0,0])
        world=parent@local
        require(np.allclose(world[:3,:3].T@world[:3,:3],np.eye(3),atol=1e-9) and abs(np.linalg.det(world[:3,:3])-1)<1e-9,
                'Part staging rejects implicit scale/stretch/reflection; fit explicitly before export')
        if 'mesh' in node:
            for primitive in doc['meshes'][node['mesh']]['primitives']:
                require(primitive.get('mode',4)==4 and not primitive.get('targets'),'Expected static triangle primitives')
                attr=primitive['attributes']
                require(all(k in attr for k in ['POSITION','NORMAL','TEXCOORD_0']),'Missing authored geometry attributes')
                material=doc['materials'][primitive['material']]
                require(material.get('normalTexture',{}).get('scale',1)==1,'Normal-strength change requires its own recorded material operation')
                require(np.array_equal(image_pixels(material['pbrMetallicRoughness']['baseColorTexture']),expected_color),'Primitive color image differs from selected common atlas')
                require(np.array_equal(image_pixels(material['normalTexture']),expected_normal),'Primitive normal image differs from selected common atlas')
                p=accessor(doc,buffer,attr['POSITION']).astype(float)
                n=accessor(doc,buffer,attr['NORMAL']).astype(float)
                uv=accessor(doc,buffer,attr['TEXCOORD_0']).astype(float);uv[:,1]=1-uv[:,1]
                ids=accessor(doc,buffer,primitive['indices']).reshape(-1,3).astype(int)
                p=((world@np.c_[p,np.ones(len(p))].T).T[:,:3])@basis.T
                n=n@np.linalg.inv(world[:3,:3])@basis.T
                require(np.isfinite(p).all() and np.isfinite(n).all() and np.isfinite(uv).all(),'Nonfinite source attributes')
                require(np.min(np.linalg.norm(n,axis=1))>.5,'Invalid authored source normal')
                result.extend(p[ids]);normalrows.extend(n[ids]);uvrows.extend(uv[ids])
                materials.append({'material':primitive['material'],'triangles':len(ids),'commonColorPixelsExact':True,'commonNormalPixelsExact':True})
        for child in node.get('children',[]):visit(child,world,seen|{index})
    for root in roots:visit(root,np.eye(4),set())
    return np.asarray(result),np.asarray(uvrows),np.asarray(normalrows),materials


def write_ascii(path,model,p,uv,n):
    verts=[]; normals=[]; tex=[]; faces=[]; vi={};ti={}
    for triangle,tuv,tn in zip(p,uv,n):
        v=[]; t=[]
        for point,coord,direction in zip(triangle,tuv,tn):
            key=(tuple(point),tuple(direction));texkey=tuple(coord)
            if key not in vi:vi[key]=len(verts);verts.append(key[0]);normals.append(key[1])
            if texkey not in ti:ti[texkey]=len(tex);tex.append((*texkey,0))
            v.append(vi[key]);t.append(ti[texkey])
        faces.append((*v,1,*t,1))
    require(len(verts)<65536,'Source exceeds diagnostic per-mesh 16-bit vertex budget; split explicitly')
    text=[f'newmodel {model}',f'setsupermodel {model} NULL','classification CHARACTER','setanimationscale 1',
          f'beginmodelgeom {model}',f'node dummy {model}','  parent NULL','endnode',
          f'node trimesh {model}p',f'  parent {model}','  position 0 0 0','  orientation 0 0 0 0',
          '  ambient 1 1 1','  diffuse 1 1 1','  specular 0 0 0','  shininess 0',
          f'  bitmap {model}',f'  materialname {model}','  render 1','  shadow 1']
    for label,rows in [('verts',verts),('normals',normals),('tverts',tex),('faces',faces)]:
        text.append(f'  {label} {len(rows)}')
        text.extend('    '+' '.join(str(v) if label=='faces' else format(v,'.17g') for v in row) for row in rows)
    text+=['endnode',f'endmodelgeom {model}',f'donemodel {model}']
    path.write_text('\n'.join(text)+'\n',encoding='ascii')
    body=re.search(r'(?ms)^node trimesh \S+\n(.*?)^endnode',path.read_text())[1]
    ap=np.asarray(arrays(body,'verts'));an=np.asarray(arrays(body,'normals'));au=np.asarray(arrays(body,'tverts'))[:,:2]
    af=np.asarray(arrays(body,'faces'),dtype=int)
    errors={'position':float(abs(ap[af[:,:3]]-p).max()),'normal':float(abs(an[af[:,:3]]-n).max()),'uv':float(abs(au[af[:,4:7]]-uv).max())}
    require(all(v==0 for v in errors.values()),'ASCII serialization changed raw attribute values')
    return {'vertices':len(verts),'triangles':len(faces),'textureVertices':len(tex),'actualAsciiCornerMaximumErrors':errors}


def geometry(p):
    v,ids=np.unique(p.reshape(-1,3),axis=0,return_inverse=True);f=ids.reshape(-1,3)
    edges=np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1)
    _,counts=np.unique(edges,axis=0,return_counts=True)
    coincident=Counter(tuple(sorted(t)) for t in f)
    return {'uniqueCoordinates':len(v),'triangles':len(f),'boundaryEdges':int((counts==1).sum()),
      'nonmanifoldEdges':int((counts>2).sum()),'coincidentTriangles':sum(c-1 for c in coincident.values() if c>1),
      'degenerateTriangles':int((np.linalg.norm(np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]),axis=1)<1e-14).sum()),
      'signedVolume':float(np.einsum('ij,ij->i',p[:,0],np.cross(p[:,1],p[:,2])).sum()/6),
      'minimum':v.min(0).tolist(),'maximum':v.max(0).tolist()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();config=json.loads(args.config.read_text())
    require(config.get('schemaVersion')==1 and config.get('diagnosticOnly') is True,'Current adapter stages explicit diagnostics only')
    require(config.get('normalStrength',1)==1 and config.get('skinLayer',0)==0 and
            config.get('equipmentMode','stock-identity')=='stock-identity',
            'Adapter requires unchanged normal strength, skin-only layer0 and identity equipment')
    model=config['model'];prefix=config['prefix'];part=config['part'];slug=config['slug']
    require(prefix=='pmh0' and config.get('gender')=='male' and config.get('raceId')==6,
            'Current standalone staging supports Human male only; configure/generalize other races explicitly')
    require(part not in ('neck','head'),'Current body workflow preserves stock neck and head')
    require(model==prefix+'_'+part+'001' and re.fullmatch(r'[a-z0-9_]{1,16}',model),'Invalid target model resref')
    require(re.fullmatch(r'[a-z0-9_]+',slug),'Invalid stage slug')
    source,color,normal=[Path(config[k]).resolve() for k in ['source','color','normal']]
    baseline=Path(config['stockBaseline']).resolve();fixture=Path(config['fixtureBaseline']).resolve()
    inventory_path=Path(config['inputInventory']).resolve()
    require(sha(inventory_path)==config['inputInventorySha256'],'Stock/fixture input inventory changed')
    inventory=json.loads(inventory_path.read_text());bank=inventory_path.parent
    require(inventory.get('customBodyAssetsCopied') is False,'Input bank must exclude custom-body artifacts')
    allowed={inventory_path.resolve()}
    for relative,row in inventory['files'].items():
        path=(bank/relative).resolve()
        require(path.is_relative_to(bank),'Input inventory escapes its bank')
        require(sha(path)==row['sha256'],'Stock/fixture input changed: '+relative)
        allowed.add(path)
    require({p.resolve() for p in bank.rglob('*') if p.is_file()}==allowed,'Unexpected artifact in stock/fixture input bank')
    require(baseline==bank/'stock' and fixture==bank/'fixture','Stage inputs must come from the verified stock/fixture bank')
    for key,path in [('source',source),('color',color),('normal',normal)]:
        require(sha(path)==config['expectedInputHashes'][key],'Selected '+key+' changed')
    root=args.output.resolve();root.mkdir(exist_ok=False)
    owned=root/slug/'converted';ascii_dir=owned/'ascii';resources=owned/'resources'
    ascii_dir.mkdir(parents=True);resources.mkdir()
    paths=[args.config.resolve(),source,color,normal,inventory_path,Path(__file__).resolve(),baseline/'ascii'/f'{prefix}.mdl',baseline/'ascii'/f'{model}.mdl']
    inputs={str(p):sha(p) for p in paths}
    p,uv,n,materials=raw_triangles(source,color,normal)
    counts=write_ascii(ascii_dir/(model+'.mdl'),model,p,uv,n)
    g=geometry(p)
    require(not g['degenerateTriangles'] and not g['coincidentTriangles'],'Invalid coincident/degenerate geometry cannot be staged')
    rgb=np.asarray(Image.open(color).convert('RGB'))
    intensity=np.clip(rgb.astype(float)@[.2126,.7152,.0722],0,255).astype(np.uint8)
    pixels=np.stack([intensity,np.zeros_like(intensity)],axis=2)[::-1].copy()
    (resources/(model+'.plt')).write_bytes(b'PLT V1  '+struct.pack('<IIII',10,0,2048,2048)+pixels.tobytes())
    normal_name=model+'n';require(len(normal_name)<=16,'Normal resource resref too long')
    Image.open(normal).convert('RGB').save(resources/(normal_name+'.tga'))
    (resources/(model+'.mtr')).write_text('renderhint NormalTangents\ntexture1 '+normal_name+'\nparameter float Roughness 0.72\nparameter float Specularity 0.04\nparameter float Metallicness 0.001\n',encoding='ascii')
    palette=(resources/(model+'.plt')).read_bytes()
    decoded=np.frombuffer(palette[24:],dtype=np.uint8).reshape(2048,2048,2)[::-1]
    require(np.array_equal(decoded[:,:,0],intensity) and not decoded[:,:,1].any(),'PLT pixel/layer proof failed')
    require(np.array_equal(np.asarray(Image.open(resources/(normal_name+'.tga')).convert('RGB')),np.asarray(Image.open(normal).convert('RGB'))),'Normal TGA pixel conversion changed selected map')
    selected=root/'selected-source';selected.mkdir()
    for path in [source,color,normal]:shutil.copyfile(path,selected/path.name)
    shutil.copyfile(Path(__file__),root/'executed-stage-stock-part.py')
    for name in ['human-template.json','ttr01.set','ttr01_edge.2da']:
        origin=fixture/name;inputs[str(origin)]=sha(origin)
        target=root/'baseline'/name;target.parent.mkdir(exist_ok=True);shutil.copyfile(origin,target)
    manifest={'combinations':[{'slug':slug,'appearance':config.get('appearance',6),'raceId':config.get('raceId',6),
      'gender':config.get('gender','male'),'phenotype':0,'height':config['stockHeightMeters'],'race':'Human','body_type':'Fit'}]}
    save(root/'manifest.json',manifest)
    conversion={'modelPrefix':prefix,'height':config['stockHeightMeters'],'stockReferenceHeight':config['stockHeightMeters'],
      'parts':[{'part':part,'model':model,'counts':counts}], 'textures':{},'geometryStatus':'single-stock-part-diagnostic',
      'rigMode':'stock-exact-game-fallback','stockOtherPartsFromGame':True,'diagnosticOnly':True,'clientAccepted':False}
    conversion['ownedResourceHashes']={p.name:sha(p) for p in resources.iterdir()}
    save(owned/'conversion.json',conversion)
    if config.get('stageHumanStockComparator'):
        require(prefix=='pmh0','Current private stock comparator is Human only')
        helper=Path(__file__).with_name('stock_body_control.py');inputs[str(helper)]=sha(helper)
        subprocess.run([sys.executable,str(helper),'--output',str(root),'--baseline',str(baseline)],check=True)
        aliases=json.loads((root/'stock_human_male_fit/converted/conversion.json').read_text())['stockAliases']
        for row in aliases:
            inputs[row['source']]=row['sourceSha256']
            origin=Path(row['paletteSource']) if row.get('paletteSource') else baseline/'raw'/(Path(row['source']).stem+'.plt')
            if row['paletteSha256']:inputs[str(origin)]=row['paletteSha256']
        inputs[str(baseline/'raw/appearance.2da')]=sha(baseline/'raw/appearance.2da')
    rootworld=transforms(nodes((baseline/'ascii'/f'{prefix}.mdl').read_text(encoding='cp1252')))
    staged={str(path.relative_to(root)):sha(path) for path in sorted(root.rglob('*')) if path.is_file()}
    for path,expected in inputs.items():require(sha(path)==expected,'Frozen input changed: '+path)
    require({f.name for f in ascii_dir.iterdir()}=={model+'.mdl'},'Extra Human part override staged')
    receipt={'source':str(source),'sourceSha256':sha(source),'configuration':config,'frozenInputs':inputs,'stagedFiles':staged,
      'rawAttributeAsciiProof':counts,'primitiveAtlasProofs':materials,'geometry':g,
      'normalPolicy':'Raw GLB NORMAL transformed by proper node axes; no normalization, recomputation or Blender round trip',
      'paletteProof':{'width':2048,'height':2048,'allLayer0Skin':True,'intensityPixelsExact':True},
      'normalTgaPixelsExact':True,'pltDiffuseOverride':False,'stockOtherPartsFromGame':True,
      'stockAttachmentWorld':rootworld[config.get('joint','torso_g')].tolist(),
      'stockControllersModified':False,'equipmentMode':'stock-identity','nativeCompiled':False,'packageBuilt':False,
      'clientLaunched':False,'clientAccepted':False,'diagnosticOnly':True,'productionGeometryGatePassed':False}
    save(root/'stock-part-stage.json',receipt)
    print(json.dumps({'output':str(root),'asciiCounts':counts,'geometry':g,'nativeCompiled':False,'clientLaunched':False},indent=2))


if __name__=='__main__':main()
