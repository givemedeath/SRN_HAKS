"""Lossless GLB-wrapper similarity placement of one generated Human pelvis.

No Blender round trip or attribute rebake. Original BIN bytes, authored normals,
UVs, indices, embedded maps and materials remain exact. Native double-precision
corner arrays are written separately; undeclared scale is not silently accepted
by existing torso staging. Only one proper rotation/uniform scale/translation.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import struct

import numpy as np

from retarget import nodes, transforms

BASIS = np.asarray([[1., 0, 0], [0, 0, -1.], [0, 1., 0]])
TORSO_HASH = '3ae78d023ba522d94c44d9914bac0b36f35b640c42b9532015575e5572161a50'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_glb(path):
    data = Path(path).read_bytes()
    require(len(data) >= 28, 'Truncated GLB')
    magic, version, total = struct.unpack_from('<III', data)
    require((magic, version, total) == (0x46546c67, 2, len(data)), 'Invalid GLB header')
    chunks = []; offset = 12
    while offset < len(data):
        length, kind = struct.unpack_from('<II', data, offset); offset += 8
        require(offset+length <= len(data), 'Truncated GLB chunk')
        chunks.append((kind, data[offset:offset+length])); offset += length
    require([x[0] for x in chunks] == [0x4e4f534a, 0x004e4942], 'Embedded JSON/BIN GLB required')
    doc = json.loads(chunks[0][1]); binary = chunks[1][1]
    require(len(doc.get('buffers', [])) == 1 and not doc['buffers'][0].get('uri'), 'One embedded buffer required')
    return doc, binary


def write_glb(path, doc, binary):
    text = json.dumps(doc, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    text += b' ' * (-len(text) % 4)
    require(len(binary) % 4 == 0, 'Preserve original padded BIN exactly')
    total = 12+8+len(text)+8+len(binary)
    Path(path).write_bytes(struct.pack('<III', 0x46546c67, 2, total)+struct.pack('<II', len(text), 0x4e4f534a)+text+
        struct.pack('<II', len(binary), 0x004e4942)+binary)


def accessor(doc, binary, index, allow_normalized=False):
    item = doc['accessors'][index]
    require('sparse' not in item and (allow_normalized or not item.get('normalized')), 'Sparse/normalized accessor requires explicit support')
    view = doc['bufferViews'][item['bufferView']]
    require(view.get('buffer', 0) == 0, 'External accessor buffer')
    dtype = np.dtype({5121:'u1', 5123:'<u2', 5125:'<u4', 5126:'<f4'}[item['componentType']])
    width = {'SCALAR':1, 'VEC2':2, 'VEC3':3, 'VEC4':4}[item['type']]
    return np.ndarray((item['count'], width), dtype=dtype, buffer=binary,
        offset=view.get('byteOffset', 0)+item.get('byteOffset', 0),
        strides=(view.get('byteStride', width*dtype.itemsize), dtype.itemsize)).copy()


def node_matrix(node):
    require('skin' not in node, 'Skin rigs are excluded')
    if 'matrix' in node:
        return np.asarray(node['matrix'], dtype=float).reshape(4, 4, order='F')
    x, y, z, w = node.get('rotation', [0, 0, 0, 1])
    require(abs(x*x+y*y+z*z+w*w-1) < 1e-8, 'Nonunit node quaternion')
    r = np.asarray([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
        [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
        [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
    matrix = np.eye(4); matrix[:3,:3] = r@np.diag(node.get('scale', [1,1,1]))
    matrix[:3,3] = node.get('translation', [0,0,0])
    return matrix


def raw_corners(doc, binary, allow_wrapper=False, extra=None):
    require(not doc.get('animations') and not doc.get('skins'), 'Static detached source only')
    require(len(doc.get('scenes', [])) == 1, 'Single source scene required')
    positions=[]; normals=[]; uvs=[]; records=[]
    def visit(index, parent, visited):
        require(index not in visited, 'Node cycle')
        node = doc['nodes'][index]; matrix = parent@node_matrix(node)
        if 'mesh' in node:
            linear=matrix[:3,:3]
            factor=float(np.cbrt(np.linalg.det(linear)))
            require(factor > 0 and np.allclose(linear.T@linear, np.eye(3)*factor**2, atol=1e-9), 'Source node stretch/reflection rejected')
            require(allow_wrapper or abs(factor-1)<1e-9, 'Generated source must have baked unit-scale nodes')
            rotation=linear/factor
            for pindex, primitive in enumerate(doc['meshes'][node['mesh']]['primitives']):
                require(primitive.get('mode',4)==4 and not primitive.get('targets'), 'Static indexed triangles required')
                require(not primitive.get('extensions'), 'Compressed primitive unsupported')
                attr=primitive['attributes']
                require(all(k in attr for k in ['POSITION','NORMAL','TEXCOORD_0']), 'Authored position/normal/UV required')
                require(not set(attr)-{'POSITION','NORMAL','TEXCOORD_0','TANGENT','COLOR_0'}, 'Unknown attribute requires an explicit rotation policy')
                points=accessor(doc,binary,attr['POSITION']).astype(float)
                directions=accessor(doc,binary,attr['NORMAL']).astype(float)
                uv=accessor(doc,binary,attr['TEXCOORD_0']).astype(float)
                ids=accessor(doc,binary,primitive['indices']).reshape(-1,3).astype(int)
                require(points.shape==directions.shape and points.shape[1]==3 and uv.shape==(len(points),2), 'Attribute shape mismatch')
                require(np.isfinite(points).all() and np.isfinite(directions).all() and np.isfinite(uv).all(), 'Nonfinite source values')
                require(ids.min()>=0 and ids.max()<len(points), 'Invalid corner indices')
                placed=(np.c_[points,np.ones(len(points))]@matrix.T)[:,:3]@BASIS.T
                rotated=directions@rotation.T@BASIS.T
                policies={'POSITION':'Recorded similarity','NORMAL':'Proper rotation only; authored length preserved',
                    'TEXCOORD_0':'Raw values unchanged'}
                for semantic in ['TANGENT','COLOR_0']:
                    if semantic not in attr:continue
                    rows=accessor(doc,binary,attr[semantic],allow_normalized=semantic=='COLOR_0')
                    require(len(rows)==len(points) and np.isfinite(rows).all(), 'Extra attribute count/nonfinite values')
                    if semantic=='TANGENT':
                        require(rows.shape[1]==4 and doc['accessors'][attr[semantic]]['componentType']==5126, 'Authored float VEC4 tangent required')
                        transformed=rows.astype(float).copy();transformed[:,:3]=rows[:,:3]@rotation.T@BASIS.T
                        policies[semantic]='XYZ proper rotation only; W handedness unchanged; source accessor bytes retained'
                    else:
                        require(rows.shape[1] in [3,4], 'RGB/RGBA COLOR_0 required')
                        transformed=rows.copy();policies[semantic]='Untransformed authored encoded values, normalization flag and accessor bytes retained'
                    if extra is not None:
                        record=extra.setdefault(semantic,{'rows':[],'triangleIndices':[]})
                        record['rows'].append(transformed[ids]);record['triangleIndices'].extend(range(len(positions),len(positions)+len(ids)))
                positions.extend(placed[ids]);normals.extend(rotated[ids]);uvs.extend(uv[ids])
                records.append({'node':index,'mesh':node['mesh'],'primitive':pindex,'triangles':len(ids),
                    'sourceAttributeAccessors':attr,'indexAccessor':primitive['indices'],'material':primitive.get('material'),
                    'attributePolicies':policies})
        for child in node.get('children',[]):visit(child,matrix,visited|{index})
    for root in doc['scenes'][doc.get('scene',0)]['nodes']:visit(root,np.eye(4),set())
    require(positions, 'No active source mesh')
    return np.asarray(positions),np.asarray(normals),np.asarray(uvs),records


def embedded_maps(doc,binary):
    images=[]
    for index,item in enumerate(doc.get('images',[])):
        require('bufferView' in item and not item.get('uri'), 'Maps must be embedded')
        view=doc['bufferViews'][item['bufferView']];start=view.get('byteOffset',0)
        blob=binary[start:start+view['byteLength']]
        images.append({'index':index,'mimeType':item.get('mimeType'),'byteLength':len(blob),'sha256':hashlib.sha256(blob).hexdigest()})
    return images


def rotation_xyz(degrees):
    x,y,z=np.deg2rad(degrees);cx,sx=np.cos(x),np.sin(x);cy,sy=np.cos(y),np.sin(y);cz,sz=np.cos(z),np.sin(z)
    return np.asarray([[1,0,0],[0,cx,-sx],[0,sx,cx]])@np.asarray([[cy,0,sy],[0,1,0],[-sy,0,cy]])@np.asarray([[cz,-sz,0],[sz,cz,0],[0,0,1]])


def bounds(triangles):
    p=triangles.reshape(-1,3)
    return {'minimum':p.min(0).tolist(),'maximum':p.max(0).tolist(),'extent':np.ptp(p,axis=0).tolist()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['inspect','place'])
    for name in ['source','generation','stock-root','frozen-torso','output']:
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--config',type=Path)
    args=parser.parse_args()
    require(not args.output.exists(),'Fresh output required')
    source=args.source.resolve(); generation=args.generation.resolve(); root=args.stock_root.resolve();torso=args.frozen_torso.resolve()
    job=json.loads(generation.read_text())
    require(job.get('state')=='success' and job.get('promptId'), 'Successful collected job receipt required')
    matches=[o for o in job.get('outputs',[]) if Path(o.get('localPath','')).resolve()==source and o.get('sha256')==sha(source)]
    require(len(matches)==1, 'Selected source must match actual collected job output path/hash')
    require(sha(torso)==TORSO_HASH,'Frozen selected torso changed')
    world=transforms(nodes(root.read_text(encoding='cp1252')))
    pivot=world['pelvis_g'][:3,3]
    source_extra={}
    doc,binary=read_glb(source);p,n,uv,records=raw_corners(doc,binary,extra=source_extra)
    source_maps=embedded_maps(doc,binary)
    inputs={str(path):sha(path) for path in [source,generation,root,torso,Path(__file__).resolve(),Path(__file__).with_name('retarget.py')]}
    result={'schemaVersion':1,'phase':args.phase,'diagnosticOnly':True,'part':'pelvis','modelPrefix':'pmh0',
        'source':str(source),'sourceSha256':sha(source),'jobPromptId':job['promptId'],'frozenInputHashes':inputs,
        'stockPelvisPivotWorld':pivot.tolist(),'stockPelvisJointMatrixWorld':world['pelvis_g'].tolist(),
        'coordinateBasis':'NWN from raw glTF [X,-Z,Y]; front+Y/up+Z', 'sourceBoundsNwnFrame':bounds(p),
        'sourcePrimitives':records,'embeddedMaps':source_maps,'sourceTriangles':len(p),
        'stockRigChanged':False,'frozenTorsoChanged':False,'clientAccepted':False}
    args.output.mkdir(parents=True)
    if args.phase=='place':
        require(args.config is not None,'Recorded placement configuration required')
        config=json.loads(args.config.read_text());inputs[str(args.config.resolve())]=sha(args.config)
        require(config.get('schemaVersion')==1 and config.get('diagnosticOnly') is True,'Explicit diagnostic config required')
        allowed={'schemaVersion','diagnosticOnly','sourceSha256','generationSha256','jobPromptId',
            'stockRootSha256','frozenTorsoSha256','uniformScale','rotationDegreesXYZ','sourceAnchorNwn',
            'targetAnchorPelvisLocal','label','targetDesign','warning','landmarkNotes'}
        require(not set(config)-allowed,'Unknown configuration fields; no implicit secondary fitting controls')
        for key,expected in [('sourceSha256',sha(source)),('generationSha256',sha(generation)),('jobPromptId',job['promptId']),('stockRootSha256',sha(root)),('frozenTorsoSha256',TORSO_HASH)]:
            require(config.get(key)==expected,'Source/stock/job association mismatch '+key)
        scale=float(config['uniformScale']);degrees=np.asarray(config['rotationDegreesXYZ'],dtype=float)
        anchor=np.asarray(config['sourceAnchorNwn'],dtype=float);target=np.asarray(config['targetAnchorPelvisLocal'],dtype=float)
        require(np.isfinite(scale) and 0<scale<10,'Positive finite uniform scale required')
        require(all(a.shape==(3,) and np.isfinite(a).all() for a in [degrees,anchor,target]),'Finite3D transform controls required')
        r=rotation_xyz(degrees);require(abs(np.linalg.det(r)-1)<1e-12,'Proper rotation required')
        matrix=np.eye(4);matrix[:3,:3]=BASIS.T@r@BASIS*scale;matrix[:3,3]=BASIS.T@(target-scale*r@anchor)
        changed=copy.deepcopy(doc);scene=changed['scenes'][changed.get('scene',0)];roots=scene['nodes'][:]
        wrapper=len(changed['nodes']);changed['nodes'].append({'name':'Recorded pelvis uniform placement','matrix':matrix.reshape(-1,order='F').tolist(),'children':roots});scene['nodes']=[wrapper]
        placed=args.output/'placed-local.glb';write_glb(placed,changed,binary)
        actual_doc,actual_bin=read_glb(placed)
        actual_extra={}
        ap,an,au,after_records=raw_corners(actual_doc,actual_bin,allow_wrapper=True,extra=actual_extra)
        expected=(p-anchor)@r.T*scale+target;expected_n=n@r.T
        errp=float(np.max(np.abs(ap-expected)));errn=float(np.max(np.abs(an-expected_n)))
        require(errp<2e-12 and errn<2e-12,'Serialized similarity/corner proof failed')
        require(actual_bin==binary and np.array_equal(au,uv),'Original attribute/image/UV bytes changed')
        require(actual_doc.get('materials')==doc.get('materials') and embedded_maps(actual_doc,actual_bin)==source_maps,'Source material/maps changed')
        before_lengths=np.linalg.norm(p[:,[1,2,0]]-p[:,[0,1,2]],axis=2)
        after_lengths=np.linalg.norm(ap[:,[1,2,0]]-ap[:,[0,1,2]],axis=2)
        edge_error=float(np.max(abs(after_lengths-before_lengths*scale)))
        require(edge_error<2e-12,'Nonuniform triangle change detected')
        native_uv=uv.copy();native_uv[:,:,1]=1-native_uv[:,:,1]
        extra_archive={};extra_proof={}
        for semantic,record in source_extra.items():
            original=np.concatenate(record['rows']);actual=np.concatenate(actual_extra[semantic]['rows'])
            require(record['triangleIndices']==actual_extra[semantic]['triangleIndices'], 'Extra attribute ordered corner association changed')
            expected_extra=original.copy()
            if semantic=='TANGENT':expected_extra[:,:,:3]=original[:,:,:3]@r.T
            extra_error=float(np.max(np.abs(actual.astype(float)-expected_extra.astype(float))))
            require(extra_error<2e-12,'Extra attribute transform mismatch '+semantic)
            extra_proof[semantic]={'maximumTransformError':extra_error,'sourceAccessorBytesExact':True,
                'handednessOrColorExact':bool(np.array_equal(original[:,:,3:],actual[:,:,3:])) if semantic=='TANGENT' else bool(np.array_equal(original,actual))}
            extra_archive['source'+semantic]=original;extra_archive['placed'+semantic]=actual
            extra_archive[semantic+'TriangleIndices']=np.asarray(record['triangleIndices'],dtype=np.int64)
        np.savez_compressed(args.output/'native-corners.npz',sourcePositionsNwn=p,sourceNormalsNwn=n,
            sourceUVGlTF=uv,sourceUVNative=native_uv,placedPositionsPelvisLocal=ap,
            placedNormalsPelvisLocal=an,placedUVGlTF=au,placedUVNative=native_uv,
            sourceSha256=np.asarray(sha(source)),placedSourceSha256=np.asarray(sha(placed)),jobPromptId=np.asarray(job['promptId']),**extra_archive)
        result.update(configuration=config,properRotationMatrixNwn=r.tolist(),rawGlTFWrapperMatrix=matrix.tolist(),
            targetBoundsPelvisLocal=bounds(ap),placedSource=str(placed.resolve()),placedSourceSha256=sha(placed),
            proof={'originalBinByteExact':True,'materialsMapsUVIndicesExact':True,'onlyNodeSceneWrapperAdded':True,
                'maximumCornerPositionErrorMetres':errp,'maximumAuthoredNormalRotationError':errn,
                'maximumTriangleUniformEdgeErrorMetres':edge_error,'normalLengthsPreservedMaximumError':float(abs(np.linalg.norm(an,axis=2)-np.linalg.norm(n,axis=2)).max()),
                'normalPolicy':'Rotate raw authored normals; never normalize, smooth or replace with computed normals.',
                'uvPolicy':'sourceUVGlTF/placedUVGlTF preserve raw GLB values. sourceUVNative/placedUVNative have V=1-rawV exactly once; consumers must not flip native arrays again.',
                'additionalAttributeProof':extra_proof,
                'nativeCornerArchive':{'path':str((args.output/'native-corners.npz').resolve()),'sha256':sha(args.output/'native-corners.npz')}},
            stagingRequirement='Current torso stager rejects implicit node scale. Use recorded native corner arrays or explicit declared-similarity support; no gate is weakened here.')
        replacement={'label':config.get('label','Purpose-built pelvis similarity diagnostic'),'modelPrefix':'pmh0','height':1.9339157,
            'parts':{'pelvis':str(placed.resolve()),'chest':str(torso)},'diagnosticOnly':True,
            'placementReceipt':str((args.output/'placement.json').resolve())}
        (args.output/'stock-replacement.json').write_text(json.dumps(replacement,indent=2)+'\n')
        shutil.copy2(args.config,args.output/'executed-config.json')
    else:
        template={'schemaVersion':1,'diagnosticOnly':True,'sourceSha256':sha(source),'generationSha256':sha(generation),
            'jobPromptId':job['promptId'],'stockRootSha256':sha(root),'frozenTorsoSha256':TORSO_HASH,
            'uniformScale':1,'rotationDegreesXYZ':[0,0,180], 'sourceAnchorNwn':[0,0,0], 'targetAnchorPelvisLocal':[0,0,-.140],
            'label':'Uncalibrated pelvis template; inspect source anatomy before use',
            'targetDesign':{'visibleTopZ':[-.025,-.015],'hiddenInsertHeight':[.015,.025],'roundedBottomZ':-.285,'hipWidthDepth':[.388,.292]},
            'warning':'Template is not a chosen fit. Root must inspect actual source orientation and landmarks.'}
        (args.output/'placement-config-template.json').write_text(json.dumps(template,indent=2)+'\n')
        extra_archive={}
        for semantic,record in source_extra.items():
            extra_archive['source'+semantic]=np.concatenate(record['rows'])
            extra_archive[semantic+'TriangleIndices']=np.asarray(record['triangleIndices'],dtype=np.int64)
        np.savez_compressed(args.output/'source-corners.npz',sourcePositionsNwn=p,sourceNormalsNwn=n,sourceUVGlTF=uv,**extra_archive)
    shutil.copy2(source,args.output/'frozen-source.glb');shutil.copy2(generation,args.output/'frozen-generation.json')
    shutil.copy2(Path(__file__),args.output/'executed-place_purposebuilt_pelvis.py')
    for path,expected_hash in inputs.items():require(sha(path)==expected_hash,'Changed input '+path)
    (args.output/('placement.json' if args.phase=='place' else 'inspection.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'output':str(args.output.resolve()),'phase':args.phase,'sourceInputsPreserved':True,'triangles':len(p),
        'bounds':result.get('targetBoundsPelvisLocal',result['sourceBoundsNwnFrame'])}))


if __name__=='__main__':
    main()
