"""Partition reviewed pelvis faces only; preserve original attributes and atlas bytes."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
import shared_toolchain
import target_contract as contract
from mirror_stock_limb_part import detached_affine_bake
from place_purposebuilt_pelvis import accessor,embedded_maps,raw_corners,read_glb,write_glb
from target_part_pipeline import generation_source,pin,read_target,verify_source_receipt
from target_part_stage import material_inputs

ARTIFACT_ROOT=Path(__file__).resolve().parents[2]/'output/phenotypes'
ROLES=('skin','garment')
CORNER_KEYS={'positions','normals','uvNative','uvGltf','sourcePositions','sourceNormals','sourceUVNative'}


def active_faces(doc,binary):
    contract.require(doc.get('nodes')==[{'name':'detached_geometry','mesh':0}] and doc.get('scenes')==[{'nodes':[0]}] and doc.get('scene',0)==0 and len(doc.get('meshes',[]))==1,
                     'Canonical identity-node fitted pelvis required')
    # Existing validator checks static indexed triangles, attribute semantics, proper
    # frames and embedded maps. Its returned rebake is discarded; no attributes change.
    detached_affine_bake(doc,binary,np.eye(4))
    rows=[]
    for number,primitive in enumerate(doc['meshes'][0]['primitives']):
        material=primitive.get('material')
        contract.require(type(material) is int and 0<=material<len(doc.get('materials',[])),'Declared source material required')
        faces=accessor(doc,binary,primitive['indices']).reshape(-1,3)
        rows.append((number,primitive,faces))
    contract.require(bool(rows),'Active fitted faces required')
    return rows


def face_layout_sha(rows):
    layout=[{'primitive':number,'attributes':primitive['attributes'],'material':primitive['material'],
             'indexAccessor':primitive['indices'],'faces':faces.astype(np.uint64).tolist()} for number,primitive,faces in rows]
    return hashlib.sha256(json.dumps(layout,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def reviewed_ids(selection,count,primitive_counts,layout):
    allowed={'schemaVersion','kind','diagnosticOnly','targetContract','targetContractSha256','targetId','rigRevision','coordinateSpace','part','joint','model','source','sourceSha256','sourceReceipt','sourceReceiptSha256','faceIdSpace','primitiveFaceCounts','sourceFaceLayoutSha256','skinFaceIds','garmentFaceIds','ambiguousFaceIds','boundaryCrossingFaceIds','review'}
    contract.require(set(selection)<=allowed,'Unknown or automatic face-classification controls are rejected')
    contract.require(type(selection.get('primitiveFaceCounts')) is list and all(type(value) is int and value>0 for value in selection['primitiveFaceCounts']),'Explicit integer primitive face counts required')
    contract.require(selection.get('faceIdSpace')=='parent-active-primitive-order','Explicit parent active face-ID space required')
    contract.require(selection.get('primitiveFaceCounts')==primitive_counts and selection.get('sourceFaceLayoutSha256')==layout,'Reviewed face layout differs from exact fitted parent')
    review=selection.get('review',{})
    contract.require(type(review) is dict and set(review)<={'reviewed','reviewedBy','scope','notes','evidence'},'Unknown review or classification waiver controls rejected')
    contract.require(review.get('reviewed') is True and review.get('reviewedBy')=='root' and review.get('scope')=='whole-face-material-ownership' and isinstance(review.get('notes'),str) and bool(review['notes'].strip()),
                     'Explicit root-reviewed whole-face material ownership required')
    for key in ('ambiguousFaceIds','boundaryCrossingFaceIds'):
        contract.require(selection.get(key)==[], 'Whole-face partition requires reviewed segmentation for ambiguous or boundary-crossing faces: '+key)
    result={}
    for role in ROLES:
        values=selection.get(role+'FaceIds')
        contract.require(type(values) is list and bool(values) and all(type(value) is int for value in values),'Nonempty explicit integer face IDs required for '+role)
        contract.require(all(0<=value<count for value in values),'Out-of-range material face IDs')
        ids=np.asarray(values,dtype=np.int64)
        contract.require(np.all(ids>=0) and np.all(ids<count),'Out-of-range material face IDs')
        contract.require(np.all(np.diff(ids)>0),'Duplicated or unordered material face IDs')
        result[role]=ids
    joined=np.concatenate(list(result.values()))
    contract.require(len(joined)==count and np.array_equal(np.sort(joined),np.arange(count)),'Every active face must be assigned exactly once; missing or duplicated role assignment')
    return result


def partition(doc,binary,selection,part='pelvis'):
    contract.require(part=='pelvis','Fixed garment belongs only to pelvis')
    rows=active_faces(doc,binary);counts=[len(faces) for _,_,faces in rows];count=sum(counts)
    ids=reviewed_ids(selection,count,counts,face_layout_sha(rows));codes=np.empty(count,dtype=np.int8)
    for code,role in enumerate(ROLES):codes[ids[role]]=code
    material_roles={};offset=0
    for _,primitive,faces in rows:
        material_roles.setdefault(primitive['material'],set()).update(ROLES[int(value)] for value in np.unique(codes[offset:offset+len(faces)]));offset+=len(faces)
    new=copy.deepcopy(doc);blob=bytearray(binary);mapping={};roles={};descriptor_proof=[]
    for material,used in sorted(material_roles.items()):
        descriptor=doc['materials'][material]
        contract.require(descriptor.get('alphaMode','OPAQUE')=='OPAQUE' and descriptor.get('pbrMetallicRoughness',{}).get('baseColorFactor',[1,1,1,1])[-1]==1,'Source material must already be opaque; no alpha/material rewrite allowed')
        first=next(role for role in ROLES if role in used)
        mapping[(material,first)]=material;roles[material]=first
        for role in ROLES:
            if role not in used:continue
            if role!=first:
                new['materials'].append(copy.deepcopy(descriptor));mapping[(material,role)]=len(new['materials'])-1;roles[len(new['materials'])-1]=role
            descriptor_proof.append({'sourceMaterial':material,'outputMaterial':mapping[(material,role)],'role':role,'descriptorExact':True})
    primitives=[];records=[];order=[];offset=0
    for number,primitive,faces in rows:
        for code,role in enumerate(ROLES):
            local_ids=np.flatnonzero(codes[offset:offset+len(faces)]==code)
            if not len(local_ids):continue
            indices=np.ascontiguousarray(faces[local_ids].reshape(-1));blob.extend(b'\0'*(-len(blob)%4));start=len(blob);blob.extend(indices.tobytes());blob.extend(b'\0'*(-len(blob)%4))
            new['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':indices.nbytes,'target':34963})
            new['accessors'].append({'bufferView':len(new['bufferViews'])-1,'componentType':doc['accessors'][primitive['indices']]['componentType'],'count':len(indices),'type':'SCALAR'})
            output=copy.deepcopy(primitive);output['indices']=len(new['accessors'])-1;output['material']=mapping[(primitive['material'],role)]
            global_ids=local_ids+offset;order.extend(global_ids.tolist());output_id=len(primitives);primitives.append(output)
            records.append({'sourcePrimitive':number,'outputPrimitive':output_id,'role':role,'sourceMaterial':primitive['material'],'outputMaterial':output['material'],
                            'sourceFaceIds':global_ids.tolist(),'triangles':len(local_ids),'sourceIndexAccessor':primitive['indices'],'outputIndexAccessor':output['indices'],
                            'sourceAttributeAccessors':primitive['attributes'],'outputAttributeAccessors':output['attributes']})
        offset+=len(faces)
    new['meshes'][0]['primitives']=primitives;new['buffers'][0]['byteLength']=len(blob)
    order=np.asarray(order,dtype=np.int64)
    contract.require(np.array_equal(np.sort(order),np.arange(count)),'Output triangles fail exact coverage')
    contract.require(bytes(blob[:len(binary)])==binary and new['accessors'][:len(doc['accessors'])]==doc['accessors'] and new['bufferViews'][:len(doc['bufferViews'])]==doc['bufferViews'],'Original BIN/accessor/view prefix changed')
    for key in ('images','textures','samplers'):
        contract.require(new.get(key)==doc.get(key),'Atlas bindings changed: '+key)
    contract.require(new['materials'][:len(doc['materials'])]==doc['materials'] and embedded_maps(new,blob)==embedded_maps(doc,binary),'Original material descriptor or embedded map changed')
    for record in records:
        old=rows[record['sourcePrimitive']][1];out=primitives[record['outputPrimitive']]
        contract.require(out['attributes']==old['attributes'] and {k:v for k,v in out.items() if k not in ('indices','material')}=={k:v for k,v in old.items() if k not in ('indices','material')},'Primitive attributes or non-index/material settings changed')
        contract.require(new['materials'][out['material']]==doc['materials'][old['material']],'Role descriptor/atlas bindings must be exact duplicates')
    p,n,uv,_=raw_corners(doc,binary);ap,an,au,_=raw_corners(new,bytes(blob))
    contract.require(all(np.array_equal(a,b[order]) for a,b in ((ap,p),(an,n),(au,uv))),'Ordered output position/normal/UV corners differ')
    proof={'originalBinPrefixExact':True,'originalAccessorViewDefinitionsExact':True,'allActiveAttributeAccessorsUnchanged':True,
           'originalMaterialsExact':True,'roleDescriptorsExactDuplicates':True,'atlasBindingsAndMapBytesExact':True,
           'triangles':count,'facesAdded':0,'facesRemoved':0,'verticesAdded':0,'verticesRemoved':0,'positionsNormalsUvsTangentsColorsChanged':False,
           'sourceFaceLayoutSha256':face_layout_sha(rows),'appendOnlyIndexArrays':True,'exhaustiveNonoverlappingFaceCoverage':True,
           'primitiveCorrespondence':records,'materialDescriptorCorrespondence':descriptor_proof,'materialRoles':roles,
           'boundarySegmentationPerformed':False,'visibleMaterialBoundaryAccepted':False}
    return new,bytes(blob),order,proof


def partition_archive(parent,rows,order,proof):
    count=len(order);required=CORNER_KEYS|{'primitiveIds','sourceTriangleIds','sourceCornerOrder'}
    contract.require(required<=set(parent) and set(parent)<=required|{'tangents','tangentTriangleIds'},'Known complete fitted parent corner archive required')
    primitive_ids=np.concatenate([np.full(len(faces),number,dtype=np.int64) for number,_,faces in rows])
    contract.require(np.array_equal(parent['primitiveIds'],primitive_ids) and np.array_equal(parent['sourceTriangleIds'],np.arange(count)) and np.array_equal(parent['sourceCornerOrder'],np.tile([0,1,2],(count,1))),
                     'Unmodified original fitted face/corner provenance required')
    result={}
    for key in CORNER_KEYS:
        value=parent[key]
        width=2 if key in ('uvNative','uvGltf','sourceUVNative') else 3
        contract.require(value.shape==(count,3,width) and np.isfinite(value).all(),'Finite authoritative corner rows required: '+key)
        result[key]=value[order].copy()
    for key in ('sourceTriangleIds','sourceCornerOrder'):result[key]=parent[key][order].copy()
    result['parentTriangleIds']=order.copy();result['parentPrimitiveIds']=parent['primitiveIds'][order].copy()
    result['primitiveIds']=np.concatenate([np.full(record['triangles'],record['outputPrimitive'],dtype=np.int64) for record in proof['primitiveCorrespondence']])
    contract.require(('tangents' in parent)==('tangentTriangleIds' in parent),'Complete tangent provenance required')
    if 'tangents' in parent:
        ids=parent['tangentTriangleIds'];t=parent['tangents']
        contract.require(ids.ndim==1 and np.issubdtype(ids.dtype,np.integer) and len(ids)==len(t) and np.all(ids>=0) and np.all(ids<count) and np.all(np.diff(ids)>0) and t.shape==(len(ids),3,4) and np.isfinite(t).all(),'Invalid authoritative tangents')
        expected=np.concatenate([np.flatnonzero(primitive_ids==number) for number,primitive,_ in rows if 'TANGENT' in primitive['attributes']])
        contract.require(np.array_equal(ids,expected),'Tangent provenance does not cover exact active tangent attributes')
        lookup={int(face):index for index,face in enumerate(ids)};out_ids=[index for index,face in enumerate(order) if int(face) in lookup]
        result['tangentTriangleIds']=np.asarray(out_ids,dtype=np.int64);result['tangents']=np.asarray([t[lookup[int(order[index])]] for index in out_ids],dtype=t.dtype).reshape(-1,3,4)
    else:
        contract.require(all('TANGENT' not in primitive['attributes'] for _,primitive,_ in rows),'Parent lost authoritative tangent rows')
    return result


def current_fitted_parent(source,parent_path,target_path,target,part,space):
    parent=verify_source_receipt(source,parent_path,target_path,target,part,space)
    contract.require(parent.get('diagnosticOnly') is True and parent.get('clientAccepted') is False and parent.get('productionAccepted') is False,'Unaccepted current geometry parent required')
    contract.require(parent['model']==contract.model(target,part) and np.array_equal(parent['attachmentWorld'],contract.frame(target,contract.PART_JOINTS[part],space)),'Parent resource/attachment frame differs')
    contract.require(parent['proof']['reflected'] is False,'Reflected current parent rejected')
    fitted=parent;inputs=[]
    if parent['operation']=='runtime':
        contract.require(space=='runtime' and parent['statureApplications']==1,'Runtime parent must already have exactly one stature conversion')
        fitted_source=pin(parent['source'],parent['sourceSha256']);fitted_path=pin(parent['sourceReceipt'],parent['sourceReceiptSha256']);inputs.extend((fitted_source,fitted_path))
        fitted=verify_source_receipt(fitted_source,fitted_path,target_path,target,part,'working')
        contract.require(np.array_equal(parent['sourceToAttachmentLocal'],np.diag([target['rig']['runtimeScale']]*3+[1.])),'Runtime parent scale matrix differs')
    else:contract.require(space=='working' and parent['statureApplications']==0,'Working fitted parent required')
    contract.require(fitted['operation']=='fit' and fitted['proof']['reflected'] is False and np.isfinite(fitted['proof']['uniformScale']) and fitted['proof']['uniformScale']>0,'Original positive proper uniform fitted lineage required')
    origin=pin(fitted['source'],fitted['sourceSha256']);job=pin(fitted['sourceReceipt'],fitted['sourceReceiptSha256']);generation_source(origin,job);inputs.extend((origin,job))
    return parent,inputs,fitted['frozenInputs']


def execute(config_path,output):
    config_path=Path(config_path).resolve();config=json.loads(config_path.read_text(encoding='utf-8'))
    allowed={'schemaVersion','kind','diagnosticOnly','part','coordinateSpace','targetContract','targetContractSha256','source','sourceSha256','sourceReceipt','sourceReceiptSha256','faceMap','faceMapSha256','sharedToolchain','sharedToolchainSha256','migrationReceipt','migrationReceiptSha256','protectedInputs','notes'}
    contract.require(set(config)<=allowed and config.get('kind')=='target-pelvis-material-partition' and config.get('diagnosticOnly') is True,'Explicit diagnostic pelvis partition controls required')
    target_path,target=read_target(config)
    contract.require(config['part']=='pelvis','Fixed garment belongs only to pelvis')
    contract.require(target['rig'].get('pilotAccepted') is True and target['rig'].get('offlineStructureAccepted') is True and target['rig'].get('pilotAcceptanceScope')=='offline-rig-structure','New frozen offline structural target required; old pilot bindings are not adopted')
    space=config['coordinateSpace'];contract.require(space in ('working','runtime'),'Explicit parent coordinate space required')
    toolchain=pin(config['sharedToolchain'],config['sharedToolchainSha256']);migration=pin(config['migrationReceipt'],config['migrationReceiptSha256']);shared_toolchain.load(toolchain,migration)
    source=pin(config['source'],config['sourceSha256']);parent_path=pin(config['sourceReceipt'],config['sourceReceiptSha256'])
    parent,lineage,fit_inputs=current_fitted_parent(source,parent_path,target_path,target,'pelvis',space)
    map_path=pin(config['faceMap'],config['faceMapSha256']);selection=json.loads(map_path.read_text(encoding='utf-8'))
    contract.require(selection.get('schemaVersion')==2 and selection.get('kind')=='target-pelvis-material-face-map' and selection.get('diagnosticOnly') is True,'Explicit immutable reviewed pelvis face map required')
    contract.verify_binding(selection,target_path,target,space)
    for key in ('part','joint','model'):contract.require(selection.get(key)==parent[key],'Face map target ownership differs: '+key)
    contract.require(Path(selection.get('source','')).resolve()==source and selection.get('sourceSha256')==contract.sha(source) and Path(selection.get('sourceReceipt','')).resolve()==parent_path and selection.get('sourceReceiptSha256')==contract.sha(parent_path),'Face map must review exact current fitted candidate and receipt')
    evidence=selection.get('review',{}).get('evidence');contract.require(isinstance(evidence,list) and evidence,'Pinned root review evidence required')
    dependencies=[config_path,target_path,source,parent_path,map_path,toolchain,migration,*lineage]
    for item in evidence:dependencies.append(pin(item['path'],item['sha256']))
    for name,expected in config.get('protectedInputs',{}).items():dependencies.append(pin(name,expected))
    corner_path=pin(parent['nativeCornerArchive']['path'],parent['nativeCornerArchive']['sha256']);dependencies.append(corner_path)
    doc,binary=read_glb(source);rows=active_faces(doc,binary)
    contract.require(len(parent['proof']['primitives'])==len(rows) and parent['proof']['triangles']==sum(len(faces) for _,_,faces in rows),'Current parent primitive/triangle proof differs')
    for number,primitive,faces in rows:
        record=parent['proof']['primitives'][number]
        contract.require(record['primitive']==number and record['triangles']==len(faces) and record['outputAttributeAccessors']==primitive['attributes'] and record['outputIndexAccessor']==primitive['indices'],'Current fitted attribute/index mapping differs from receipt proof')
    new,blob,order,proof=partition(doc,binary,selection)
    # Exercise existing material guards without modifying their implementation.
    _,material_proof=material_inputs(new,blob,proof['materialRoles'],'pelvis',0)
    with np.load(corner_path,allow_pickle=False) as data:archive=partition_archive({key:data[key] for key in data.files},rows,order,proof)
    p,n,uv,_=raw_corners(doc,binary)
    with np.load(corner_path,allow_pickle=False) as data:
        contract.require(np.max(np.abs(p-data['positions']))<=parent['proof']['maximumPositionFloat32ErrorMetres']+1e-12 and np.max(np.abs(n-data['normals']))<=parent['proof']['maximumNormalFloat32Error']+1e-12 and np.array_equal(uv,data['uvGltf']),'Authoritative archive differs from current fitted geometry')
    for name in ('partition_target_pelvis_materials.py','target_contract.py','target_part_pipeline.py','target_part_stage.py','mirror_stock_limb_part.py','place_purposebuilt_pelvis.py','shared_toolchain.py'):dependencies.append(Path(__file__).with_name(name).resolve())
    inputs={str(path):contract.sha(path) for path in dependencies};inputs.update(fit_inputs);inputs.update(parent['frozenInputs'])
    for name,expected in inputs.items():pin(name,expected)
    output=Path(output).resolve();contract.require(not output.exists() and output.is_relative_to(ARTIFACT_ROOT.resolve()),'Fresh isolated immutable material partition output required')
    output.mkdir(parents=True);candidate=output/'candidate-local.glb';write_glb(candidate,new,blob)
    actual,actual_blob=read_glb(candidate)
    contract.require(actual==new and actual_blob==blob,'Serialized partition JSON/BIN differs')
    corners=output/'native-corners.npz';np.savez_compressed(corners,**archive);shutil.copyfile(__file__,output/'executed-helper.py')
    receipt={'schemaVersion':2,'kind':'target-part-geometry','operation':'material-partition',**contract.binding(target_path,target,space),
             'part':'pelvis','joint':'pelvis_g','model':contract.model(target,'pelvis'),'sourcePart':'pelvis',
             'source':str(source),'sourceSha256':contract.sha(source),'sourceReceipt':str(parent_path),'sourceReceiptSha256':contract.sha(parent_path),
             'faceMap':str(map_path),'faceMapSha256':contract.sha(map_path),'candidate':str(candidate),'candidateSha256':contract.sha(candidate),
             'nativeCornerArchive':{'path':str(corners),'sha256':contract.sha(corners)},'statureApplications':parent['statureApplications'],
             'sourceToAttachmentLocal':np.eye(4).tolist(),'attachmentWorld':parent['attachmentWorld'],'reflectionWorld':None,
             'materialRoles':proof['materialRoles'],'proof':{**proof,'maximumPositionFloat32ErrorMetres':parent['proof']['maximumPositionFloat32ErrorMetres'],
                'maximumNormalFloat32Error':parent['proof']['maximumNormalFloat32Error'],'parentDoublePrecisionCornersExact':True,'parentFitRigAndStatureUnchanged':True},
             'materialBindingProof':material_proof,'frozenInputs':inputs,'diagnosticOnly':True,'rigPilotAccepted':True,
             'geometryAccepted':False,'materialBindingsAccepted':False,'opaqueGarmentClientAccepted':False,'visibleMaterialBoundaryAccepted':False,'clientAccepted':False,'productionAccepted':False,
             'limitation':'Whole-face role assignment only. An apparel boundary crossing a triangle needs separate reviewed segmentation; this operation does not cut geometry or solve visible atlas boundaries.'}
    for name,expected in inputs.items():pin(name,expected)
    path=output/'geometry.json';path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');return path


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=execute(args.config,args.output);print(json.dumps({'receipt':str(result),'sha256':contract.sha(result),'materialBindingsAccepted':False}))

