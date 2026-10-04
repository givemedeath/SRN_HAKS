"""Extract a fresh closed exterior from an explicitly pinned, measured filled grid.

Marching tetrahedra uses cell-center occupancy at iso0.5. No morphology,
smoothing, placement, source overwrite or implicit adoption occurs here.
The fill/closure proof is a separate required input, not inferred by this tool.
"""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np
from place_purposebuilt_pelvis import write_glb
from stage_stock_part import require,sha,save

CORNERS=np.array([(0,0,0),(1,0,0),(1,1,0),(0,1,0),
                  (0,0,1),(1,0,1),(1,1,1),(0,1,1)],dtype=np.int64)
TETS=np.array([(0,5,1,6),(0,1,2,6),(0,2,3,6),
               (0,3,7,6),(0,7,4,6),(0,4,5,6)])


def extract(filled,origin,pitch):
    require(filled.ndim==3 and min(filled.shape)>=3 and pitch>0
            and np.isfinite(origin).all(),'Finite padded 3D occupancy required')
    require(not any(filled.take([0,-1],axis=axis).any() for axis in range(3)),
            'Filled geometry touches grid boundary; exterior cannot be closed')
    cube_shape=np.array(filled.shape)-1
    count=np.zeros(tuple(cube_shape),np.uint8)
    for offset in CORNERS:
        count+=filled[tuple(slice(int(k),int(k+n)) for k,n in zip(offset,cube_shape))]
    cubes=np.argwhere((count>0)&(count<8));del count
    require(len(cubes)>0,'No filled exterior')
    keys=[];dimensions=np.array(filled.shape,dtype=np.int64)*2
    for start in range(0,len(cubes),100000):
        block=cubes[start:start+100000]
        state=np.stack([filled[tuple((block+corner).T)] for corner in CORNERS],axis=1)
        for tet in TETS:
            local=state[:,tet];code=np.sum(local*np.array([1,2,4,8]),axis=1)
            points=CORNERS[tet]
            for case in range(1,15):
                base=block[code==case]
                if not len(base):continue
                inside=[i for i in range(4) if case&(1<<i)]
                outside=[i for i in range(4) if not case&(1<<i)]
                if len(inside)==1:
                    edges=[(inside[0],j) for j in outside];triangles=[(0,1,2)]
                elif len(outside)==1:
                    edges=[(i,outside[0]) for i in inside];triangles=[(0,1,2)]
                else:
                    i,j=inside;a,b=outside
                    edges=[(i,a),(i,b),(j,a),(j,b)];triangles=[(0,1,3),(0,3,2)]
                offsets=np.array([points[a]+points[b] for a,b in edges])
                direction=points[outside].mean(0)-points[inside].mean(0)
                for triangle in triangles:
                    triplet=offsets[list(triangle)]
                    if np.dot(np.cross(triplet[1]-triplet[0],triplet[2]-triplet[0]),direction)<0:
                        triplet=triplet[[0,2,1]]
                    coords=2*base[:,None,:]+triplet[None,:,:]
                    encoded=(coords[:,:,0]*dimensions[1]+coords[:,:,1])*dimensions[2]+coords[:,:,2]
                    keys.append(encoded)
    flat=np.concatenate(keys).reshape(-1);del keys
    unique,inverse=np.unique(flat,return_inverse=True)
    coordinate=np.column_stack([unique//(dimensions[1]*dimensions[2]),
                               (unique//dimensions[2])%dimensions[1],unique%dimensions[2]])
    position=np.asarray(origin)+(.5+.5*coordinate)*pitch
    faces=inverse.reshape(-1,3).astype(np.uint32)
    normal=np.zeros(position.shape,dtype=np.float64)
    triangles=position[faces];face_normal=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    require(np.all(np.linalg.norm(face_normal,axis=1)>0),'Degenerate extracted face')
    for corner in range(3):np.add.at(normal,faces[:,corner],face_normal)
    length=np.linalg.norm(normal,axis=1)
    require(np.all(length>0),'Undefined extracted normal')
    normal/=length[:,None]
    return position.astype('<f4'),normal.astype('<f4'),faces


def topology(position,faces):
    edges=faces[:,[[0,1],[1,2],[2,0]]].reshape(-1,2)
    ordered=np.sort(edges,axis=1)
    unique,inverse,counts=np.unique(ordered,axis=0,return_inverse=True,return_counts=True)
    winding=np.zeros(len(unique),np.int32)
    np.add.at(winding,inverse,np.where(edges[:,0]<edges[:,1],1,-1))
    result={'vertices':len(position),'triangles':len(faces),
            'boundaryEdges':int(np.count_nonzero(counts==1)),
            'nonmanifoldEdges':int(np.count_nonzero(counts>2)),
            'inconsistentManifoldEdgeWindings':int(np.count_nonzero((counts==2)&(winding!=0)))}
    require(result['boundaryEdges']==result['nonmanifoldEdges']==result['inconsistentManifoldEdgeWindings']==0,
            'Extracted exterior fails closed oriented topology')
    triangle=position[faces].astype(float)
    result['signedVolume']=float(np.sum(np.einsum('ij,ij->i',triangle[:,0],np.cross(triangle[:,1],triangle[:,2])))/6)
    require(result['signedVolume']>0,'Extracted winding not outward')
    return result


def export(path,position,normal,faces):
    arrays=[position,normal,faces.reshape(-1).astype('<u4')]
    binary=bytearray();views=[];accessors=[]
    for index,rows in enumerate(arrays):
        binary.extend(b'\0'*(-len(binary)%4));offset=len(binary);binary.extend(rows.tobytes())
        views.append({'buffer':0,'byteOffset':offset,'byteLength':rows.nbytes})
        item={'bufferView':index,'componentType':5126 if index<2 else 5125,
              'type':'VEC3' if index<2 else 'SCALAR','count':len(rows)}
        if index==0:item.update(min=rows.min(0).astype(float).tolist(),max=rows.max(0).astype(float).tolist())
        accessors.append(item)
    binary.extend(b'\0'*(-len(binary)%4))
    document={'asset':{'version':'2.0','generator':'SRN measured filled exterior'},
              'scene':0,'scenes':[{'nodes':[0]}],'nodes':[{'mesh':0,'name':'filled-exterior'}],
              'meshes':[{'primitives':[{'attributes':{'POSITION':0,'NORMAL':1},'indices':2,'mode':4}]}],
              'buffers':[{'byteLength':len(binary)}],'bufferViews':views,'accessors':accessors}
    write_glb(path,document,binary)


def run(config_path,output):
    require(not output.exists(),'Fresh reconstruction candidate required')
    config=json.loads(config_path.read_text());pins={config['grid']:config['gridSha256'],
        config['source']:config['sourceSha256'],**config['proofs']}
    require(config.get('repairDescription') and config['proofs'],'Explicit measured fill/closure proof required')
    for name,pin in pins.items():require(sha(name)==pin,'Filled reconstruction input changed: '+name)
    with np.load(config['grid'],allow_pickle=False) as grid:
        shape=tuple(int(v) for v in grid['shape']);size=int(np.prod(shape))
        key='filledPacked' if 'filledPacked' in grid else 'outsidePacked'
        filled=np.unpackbits(grid[key],bitorder='big')[:size].reshape(shape).astype(bool)
        if key=='outsidePacked':filled=~filled
        origin=grid['origin'];pitch=float(grid['pitch'])
    p,n,f=extract(filled,origin,pitch);audit=topology(p,f)
    output.mkdir(parents=True);target=output/'exterior-highpoly.glb';export(target,p,n,f)
    shutil.copyfile(__file__,output/'executed-extractor.py');shutil.copyfile(config_path,output/'config.json')
    save(output/'reconstruction.json',{'schemaVersion':1,'kind':'measured-filled-exterior-candidate',
        'frozenInputs':pins,'gridShape':list(shape),'pitchSourceCoordinates':pitch,
        'gridOrigin':origin.tolist(),'geometrySourceFrame':'Original generated GLTF coordinates; identity node.',
        'method':'Cell-center iso0.5 marching tetrahedra; six consistent tetrahedra per cube.',
        'repairDescription':config['repairDescription'],'topology':audit,
        'output':str(target.resolve()),'outputSha256':sha(target),
        'normalPolicy':'Fresh area-weighted normals on the reconstructed exterior; no source normals overwritten.',
        'uvsOrMaterialsReused':False,'sourceModified':False,'sourceAdopted':False,
        'fittingApplied':False,'clientStarted':False,'executedCodeSha256':sha(__file__),
        'remainingGates':['Independent exterior displacement/sections/grip anatomy','Fresh decimation/unwrap/bakes','Stock fitting and native/client proof']})
    print(json.dumps(audit))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    run(args.config.resolve(),args.output.resolve())
