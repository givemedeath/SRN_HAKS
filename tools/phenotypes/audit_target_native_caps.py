"""Read-only native shading diagnostics for original-source-vertex micro caps.

Requires an exact native-part audit first. Samples installed front-face RG/TBN
formulas at neutral identity texture transform; it is not a client render.
"""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

import target_contract as contract
from audit_target_joint_bands import sample_pixels
from audit_target_native_part import decode, tangent_proof
from place_purposebuilt_pelvis import raw_corners, read_glb
from target_part_pipeline import pin, read_target, verify_source_receipt


CAP_SAMPLES = np.asarray([[1,0,0],[0,1,0],[0,0,1],[1/3,1/3,1/3],[.5,.5,0],[0,.5,.5],[.5,0,.5]])


def cap_provenance(archive,triangle_count):
    mask = archive['addedConnectorMask']; ids = archive['sourceTriangleIds']; source_vertices = archive['addedSourceVertexFaces']
    contract.require(mask.dtype == np.bool_ and mask.shape == (triangle_count,) and ids.shape == mask.shape and
                     np.array_equal(mask,ids == -1), 'Explicit micro-cap mask/source IDs differ')
    selected = np.flatnonzero(mask)
    contract.require(1 <= len(selected) <= 6 and source_vertices.shape == (len(selected),3) and
                     np.issubdtype(source_vertices.dtype,np.integer) and (source_vertices >= 0).all(),
                     'Bounded original source-vertex micro-cap provenance required')
    contract.require(np.array_equal(selected,np.arange(triangle_count-len(selected),triangle_count)),
                     'Declared appended ordered micro caps required')
    return selected,source_vertices


def cap_metrics(native,face_ids,normal_map,roughness_map,shade_map,wrap_s=10497,wrap_t=10497):
    p = native['position'][native['faces'][face_ids]].astype(float)
    n = native['normal'][native['faces'][face_ids]].astype(float)
    t = native['tangent'][native['faces'][face_ids]].astype(float)
    sign = native['sign'][native['faces'][face_ids],0].astype(float)
    uv_native = native['uv'][native['faces'][face_ids]].astype(float)
    uv = uv_native.copy(); uv[...,1] = 1-uv[...,1]
    cross = np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]); doubled_area = np.linalg.norm(cross,axis=1)
    contract.require((doubled_area > 0).all(), 'Zero-area native micro cap')
    geometric = cross/doubled_area[:,None]
    sample_uv = np.einsum('bc,tci->tbi',CAP_SAMPLES,uv)
    sample_normal = np.einsum('bc,tci->tbi',CAP_SAMPLES,n)
    sample_tangent = np.einsum('bc,tci->tbi',CAP_SAMPLES,t)
    sample_sign = np.einsum('bc,tc->tb',CAP_SAMPLES,sign)
    nl,tl = np.linalg.norm(sample_normal,axis=2),np.linalg.norm(sample_tangent,axis=2)
    contract.require((nl > 0).all() and (tl > 0).all(), 'Undefined sampled normalize(normal/tangent) on micro cap')
    nn,nt = sample_normal/nl[...,None],sample_tangent/tl[...,None]
    # Installed SetupTSB: normalized tangent, cross(surfaceNormal,tangent),
    # and handedness sign derived with step(0, interpolatedHandedness).
    nb = np.cross(nn,nt)*np.where(sample_sign >= 0,1,-1)[...,None]
    map_rgb = sample_pixels(normal_map,sample_uv.reshape(-1,2),wrap_s,wrap_t).reshape(*sample_uv.shape[:2],3)
    xy = map_rgb[...,:2]/255*2-1; radius = np.sum(xy**2,axis=2)
    z = np.sqrt(np.maximum(1-radius,0))
    fragment = nt*xy[...,0,None]+nb*xy[...,1,None]+nn*z[...,None]
    length = np.linalg.norm(fragment,axis=2)
    contract.require((length > 0).all() and np.isfinite(fragment).all(), 'Undefined sampled normal-map direction on micro cap')
    mapped_cosine = np.einsum('tbi,ti->tb',fragment/length[...,None],geometric)
    authored_cosine = np.einsum('tci,ti->tc',n/np.linalg.norm(n,axis=2)[...,None],geometric)
    rough = sample_pixels(roughness_map,sample_uv.reshape(-1,2),wrap_s,wrap_t).reshape(*sample_uv.shape[:2],-1)[...,0]/255
    shade = sample_pixels(shade_map,sample_uv.reshape(-1,2),wrap_s,wrap_t).reshape(*sample_uv.shape[:2],-1)[...,0]
    delta1,delta2 = uv_native[:,1]-uv_native[:,0],uv_native[:,2]-uv_native[:,0]
    determinant = delta1[:,0]*delta2[:,1]-delta1[:,1]*delta2[:,0]
    rows = []
    for index,face in enumerate(face_ids):
        edges = [p[index,(corner+1)%3]-p[index,corner] for corner in range(3)]
        angles = [np.degrees(np.arccos(np.clip(np.dot(-edges[(corner-1)%3],edges[corner])/
                  (np.linalg.norm(edges[(corner-1)%3])*np.linalg.norm(edges[corner])),-1,1))) for corner in range(3)]
        rows.append({'outputTriangleId':int(face),'nativeVertexIds':native['faces'][face].tolist(),
                     'areaSquareMetres':float(doubled_area[index]/2),
                     'edgeLengthMetres':[float(np.linalg.norm(edge)) for edge in edges],
                     'minimumInteriorAngleDegrees':float(min(angles)),
                     'geometricNormal':geometric[index].tolist(),'uvDeterminant':float(determinant[index]),
                     'uvDegenerate':bool(abs(determinant[index]) <= 1e-12),
                     'authoredCornerNormalVsGeometricCosines':authored_cosine[index].tolist(),
                     'nativeCornerHandedness':sign[index].tolist(),
                     'mixedCornerHandedness':bool(sign[index].min() != sign[index].max()),
                     'sampleRawGltfUv':sample_uv[index].tolist(),
                     'sampleOriginalNormalRgb':map_rgb[index].tolist(),
                     'sampleRgRadiusSquaredMaximum':float(radius[index].max()),
                     'sampleRgOutsideUnitDiskCount':int((radius[index] > 1).sum()),
                     'sampleFragmentNormalLengthRange':[float(length[index].min()),float(length[index].max())],
                     'sampleMappedFrontNormalVsGeometricCosines':mapped_cosine[index].tolist(),
                     'sampleInterpolatedTangentMinimumLength':float(tl[index].min()),
                     'sampleRoughnessRange':[float(rough[index].min()),float(rough[index].max())],
                     'samplePltShadeRange':[float(shade[index].min()),float(shade[index].max())],
                     'visualAccepted':False})
    vertices,indices = np.unique(native['faces'][face_ids],return_inverse=True)
    subset = {key:native[key][vertices] for key in ['position','normal','uv','tangent','sign']}
    subset['faces'] = indices.reshape(-1,3)
    return rows,tangent_proof(subset)


def audit(config_path,output):
    config_path = Path(config_path).resolve(); config = json.loads(config_path.read_text(encoding='utf-8'))
    target_path,target = read_target(config); space = config['coordinateSpace']; part = config['part']
    contract.require(config.get('kind') == 'target-native-cap-audit' and space in ('working','runtime') and
                     part in contract.BODY_PARTS,'Explicit target part/space cap audit required')
    geometry_path = pin(config['geometryReceipt'],config['geometryReceiptSha256'])
    geometry = json.loads(geometry_path.read_text(encoding='utf-8'))
    contract.require(geometry.get('operation') == 'face-repair' and geometry['proof']['addedVertexRows'] == 0 and
                     geometry['proof']['normalChanges'] == 0 and geometry['proof']['positionMovement'] == 0,
                     'Original-source-vertex-only repaired descendant required')
    source = pin(geometry['candidate'],geometry['candidateSha256'])
    verify_source_receipt(source,geometry_path,target_path,target,part,space)
    native_audit_path = pin(config['nativeAudit'],config['nativeAuditSha256'])
    native_audit = json.loads(native_audit_path.read_text(encoding='utf-8'))
    contract.require(native_audit.get('kind') == 'target-native-part-audit' and
                     native_audit['attributeTransportVerified'] is True and native_audit['materialTransportVerified'] is True and
                     native_audit['part'] == part, 'Exact native part audit required first')
    contract.verify_binding(native_audit,target_path,target,space)
    for name,expected in native_audit['frozenInputs'].items(): pin(name,expected)
    stage_path = pin(native_audit['stageReceipt'],native_audit['stageReceiptSha256'])
    stage = json.loads(stage_path.read_text(encoding='utf-8'))
    contract.require(stage['sourceReceiptSha256'] == contract.sha(geometry_path) and
                     Path(stage['sourceReceipt']).resolve() == geometry_path and stage['materialRoles'] == {'0':'skin'},
                     'Single-skin stage does not select this repaired descendant')
    native_receipt_path = pin(native_audit['nativeReceipt'],native_audit['nativeReceiptSha256'])
    converted = native_receipt_path.parent; model = contract.model(target,part)
    binary_path = pin(converted/'resources'/(model+'.mdl'),native_audit['nativeModelSha256'])
    meshes,_ = decode(binary_path.read_bytes(),model,native_audit['meshes'])
    contract.require(len(meshes) == 1,'One repaired skin mesh required'); native = next(iter(meshes.values()))
    archive_path = pin(geometry['nativeCornerArchive']['path'],geometry['nativeCornerArchive']['sha256'])
    with np.load(archive_path,allow_pickle=False) as loaded: archive = {key:loaded[key] for key in loaded.files}
    face_ids,source_vertices = cap_provenance(archive,len(native['faces']))
    doc,binary = read_glb(source); p,n,uv,_ = raw_corners(doc,binary)
    contract.require(np.array_equal(native['position'][native['faces']],p.astype('f4')) and
                     np.array_equal(native['normal'][native['faces']],n.astype('f4')) and
                     np.array_equal(native['uv'][native['faces']],np.stack([uv[...,0],1-uv[...,1]],axis=2).astype('f4')),
                     'Actual native ordered source association changed')
    folder = converted/'resources'; normal_path,roughness_path,plt_path = [folder/(model+suffix) for suffix in ['n.tga','r.tga','.plt']]
    normal_map = np.asarray(Image.open(normal_path).convert('RGB')); roughness_map = np.asarray(Image.open(roughness_path).convert('RGB'))
    data = plt_path.read_bytes(); shade = np.frombuffer(data[24:],dtype='u1').reshape(2048,2048,2)[::-1,...,0]
    material = doc['materials'][0]; texture = material['normalTexture']
    contract.require(texture.get('scale',1) == 1 and not texture.get('extensions') and texture.get('texCoord',0) == 0,
                     'Original normal strength/UV binding required')
    item = doc['textures'][texture['index']]
    sampler = doc.get('samplers',[])[item['sampler']] if 'sampler' in item else {}
    # Current source maps share wrapping. Native MTR has no explicit UV transform;
    # base-level diagnostic wrapping is recorded, not a client-state assertion.
    wrap_s,wrap_t = sampler.get('wrapS',10497),sampler.get('wrapT',10497)
    shader_path = pin(config['shaderReceipt'],config['shaderReceiptSha256'])
    shader = json.loads(shader_path.read_text(encoding='utf-8'))
    contract.verify_binding(shader,target_path,target,'working')
    for name,expected in shader['frozenInputs'].items(): pin(name,expected)
    transform = Path(shader['sourceBank'])/'inc_transform.shd'
    text = transform.read_text(encoding='utf-8')
    contract.require('vec3 vTangent = normalize(vVertexTangent);' in text and
                     'cross(vSurfaceNormal, vTangent) * (2.0 * step(0.0, fTextureHandedness) - 1.0)' in text,
                     'Installed tangent basis formula differs')
    rows,tangent = cap_metrics(native,face_ids,normal_map,roughness_map,shade,wrap_s,wrap_t)
    frame = contract.frame(target,contract.PART_JOINTS[part],space)
    for index,row in enumerate(rows):
        row['sourceSerializedVertexIds'] = source_vertices[index].tolist()
        row['workingOrRuntimeWorldCorners'] = (p[face_ids[index]]@frame[:3,:3].T+frame[:3,3]).tolist()
    output = Path(output).resolve(); contract.require(not output.exists(),'Fresh immutable cap audit required')
    output.mkdir(parents=True); shutil.copyfile(__file__,output/'executed-helper.py')
    files = [config_path,target_path,geometry_path,source,native_audit_path,stage_path,native_receipt_path,binary_path,
             archive_path,normal_path,roughness_path,plt_path,shader_path,transform,output/'executed-helper.py']
    # Preserve imported arithmetic/transport implementations as well as the
    # entry point. The native-part receipt freezes its own import set, but the
    # cap audit additionally invokes the joint-band texture sampler.
    helper_folder = output/'helpers'; helper_folder.mkdir()
    for name in ['audit_target_native_caps.py','audit_target_joint_bands.py','audit_target_native_part.py',
                 'target_contract.py','target_part_pipeline.py','place_purposebuilt_pelvis.py',
                 'audit_geometry.py','audit_native_limb_shading.py','target_body_inventory.py',
                 'target_part_stage.py','mirror_stock_limb_part.py','stage_stock_part.py']:
        helper = helper_folder/name; shutil.copyfile(Path(__file__).parent/name,helper); files.append(helper)
    receipt = {'schemaVersion':2,'kind':'target-native-cap-audit',**contract.binding(target_path,target,space),
               'part':part,'model':model,'geometryReceipt':str(geometry_path),'geometryReceiptSha256':contract.sha(geometry_path),
               'nativeAudit':str(native_audit_path),'nativeAuditSha256':contract.sha(native_audit_path),
               'capFaces':rows,'capNativeTangentArrays':tangent,
               'maximumCapPositionDifferenceFromAuthoritativeArchive':float(np.abs(p[face_ids]-archive['positions'][face_ids]).max()),
               'maximumCapNormalDifferenceFromAuthoritativeArchive':float(np.abs(n[face_ids]-archive['normals'][face_ids]).max()),
               'sampleBarycentricWeights':CAP_SAMPLES.tolist(),'mapSampler':sampler,
               'simulationAssumptions':['Front-facing surface','Identity material texture matrix','Neutral detached native mesh',
                                        'Base-level byte-linear texture samples, no client mipmap/lighting evaluation'],
               'sourceGeometryEdited':False,'materialPixelsEdited':False,'nativeCompilerExecuted':False,
               'rigPilotAccepted':target['rig']['pilotAccepted'],'productionAccepted':False,'clientAccepted':False,
               'frozenInputs':{str(path):contract.sha(path) for path in sorted(set(files))},
               'limitation':'Original-vertex micro-cap input/shader arithmetic diagnostics only. Shoulder ownership, posed connectors and actual native/client appearance remain unresolved.'}
    result = output/'native-cap-audit.json'; result.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True); args = parser.parse_args()
    result = audit(args.config,args.output); print(json.dumps({'receipt':str(result),'receiptSha256':contract.sha(result)}))
