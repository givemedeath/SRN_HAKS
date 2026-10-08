"""Read-only v2 target source -> ASCII -> native ordered geometry/material audit.

Supports declared working/runtime detached body parts and skin/garment roles.
The constrained decoder follows the frozen NwnMdlNodes/NwnMdlGeometry layouts.
It never compiles, rescales, modifies pixels or accepts client appearance.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import struct

import numpy as np
from PIL import Image

import target_contract as contract
from audit_geometry import arrays
from audit_native_limb_shading import float32_ulp_distance, maximum_errors, validate_transport
from place_purposebuilt_pelvis import raw_corners, read_glb
from target_body_inventory import expected_body_resources, flat_hashes, skin_atlas_keys
from target_part_pipeline import pin, read_target, verify_source_receipt
from target_part_stage import material_inputs


LAYOUT_COMMIT = 'd9797879f4e2fbb701e923e6ddfeb7869d6b1efe'
LAYOUT_PINS = {'NwnMdlNodes.h': 'a95c1add8f171ce4781c2b2ab0156ee737eaf8bbc0bec9200085a1da054eb1e5',
               'NwnMdlGeometry.h': '4e0566fbfb46e811adb23c49a521b7bf615db4fb8b19d87ca235bfd7ce9629ee'}


def decode(data, model, expected_meshes):
    """Traverse the geometry child arrays, not a search for node-name bytes.

    Compiler pointer-like geometry/parent fields are recorded without interpreting
    them as file offsets. Child arrays and identity controllers prove this supported
    detached tree. Unsupported nested transforms or node kinds fail closed.
    """
    contract.require(len(data) >= 12+0xe8, 'Truncated native model header')
    zero, raw_offset, raw_size = struct.unpack_from('<III', data)
    contract.require(zero == 0 and 12+raw_offset+raw_size == len(data), 'Complete native model/raw sections required')
    model_end = 12+raw_offset; raw_start = model_end

    def region(offset, count, width):
        contract.require(offset >= 0 and count >= 0 and 12+offset+count*width <= model_end,
                         'Native structure exceeds model section')
        return 12+offset

    def u32(at):
        contract.require(at >= 12 and at+4 <= model_end, 'Native field exceeds model section')
        return struct.unpack_from('<I', data, at)[0]

    def name(at, width):
        contract.require(at >= 12 and at+width <= model_end, 'Native string exceeds model section')
        value = data[at:at+width]
        contract.require(b'\0' in value, 'Unterminated native name')
        return value.split(b'\0', 1)[0].decode('ascii')

    def native_array(at, width):
        contract.require(at >= 12 and at+12 <= model_end, 'Native array header exceeds model section')
        offset, count, capacity = struct.unpack_from('<III', data, at)
        contract.require(count == capacity, 'Native array capacity/count differs')
        region(offset, count, width)
        return offset, count

    contract.require(name(12+8,64) == model, 'Native model identity differs')
    contract.require(data[12+0x72] == 4, 'Native CHARACTER classification required')
    contract.require(native_array(12+0x78,4)[1] == 0, 'Animation-bearing body part unsupported')
    contract.require(name(12+0xa8,64).lower() in ('', 'null'), 'Inherited body part unsupported')
    contract.require(struct.unpack_from('<f',data,12+0xa4)[0] == 1, 'Unexpected native animation scale')
    expected_meshes = set(expected_meshes)
    contract.require(expected_meshes and model not in expected_meshes, 'Explicit unique mesh names required')
    node_count = u32(12+0x4c); root = u32(12+0x48)
    contract.require(node_count == len(expected_meshes)+1, 'Undeclared native nodes or missing meshes')
    pending = [(root, None)]; seen_offsets = set(); seen_names = set(); meshes = {}; root_record = None
    while pending:
        offset, parent = pending.pop(0)
        contract.require(offset not in seen_offsets, 'Native hierarchy cycle or shared child')
        seen_offsets.add(offset); at = region(offset,1,0x70)
        node_name = name(at+0x20,32)
        contract.require(node_name not in seen_names, 'Duplicate native node name'); seen_names.add(node_name)
        flags = u32(at+0x6c)
        contract.require((parent is None and node_name == model and flags == 1) or
                         (parent == model and node_name in expected_meshes and flags == 33),
                         'Unsupported native hierarchy/node type/name')
        children, children_count = native_array(at+0x48,4)
        if parent is None:
            contract.require(children_count == len(expected_meshes), 'Native root child inventory differs')
        else:
            contract.require(children_count == 0, 'Nested body transforms unsupported')
        pending.extend((u32(region(children+i*4,1,4)),node_name) for i in range(children_count))
        keys, keys_count = native_array(at+0x54,12)
        values, values_count = native_array(at+0x60,4)
        controller_types = set(); controllers = []
        permitted = {8: [0,0,0], 20: [0,0,0,1], 36: [1], 100: [0,0,0], 128: [1]}
        for index in range(keys_count):
            kind, rows, keyoff, dataoff, columns, pad = struct.unpack_from('<ihhhbb',data,region(keys+index*12,1,12))
            contract.require(kind in permitted and kind not in controller_types and rows == 1 and
                             columns == len(permitted[kind]) and keyoff >= 0 and dataoff >= 0 and
                             keyoff < values_count and dataoff+columns <= values_count,
                             'Unsupported or malformed native static controller')
            controller_types.add(kind)
            time = struct.unpack_from('<f',data,region(values+keyoff*4,1,4))[0]
            value = np.asarray(struct.unpack_from('<'+'f'*columns,data,region(values+dataoff*4,columns,4)))
            if kind == 20 and value[-1] == -1: value = -value
            contract.require(time == 0 and np.array_equal(value,permitted[kind]),
                             'Nonidentity native body transform/material controller')
            controllers.append({'type':kind,'time':time,'values':value.tolist()})
        metadata = {'nodeAbsoluteOffset':at, 'name':node_name, 'parentFromChildTree':parent,
                    'flags':flags,'controllers':controllers,
                    'uninterpretedGeometryField':u32(at+0x40), 'uninterpretedParentField':u32(at+0x44)}
        if parent is None:
            root_record = metadata
            continue
        region(offset,1,0x270)
        face_offset, faces_count = native_array(at+0x78,32)
        vertices, texture_count = struct.unpack_from('<HH',data,at+0x230)
        contract.require(vertices > 0 and faces_count > 0 and texture_count == 1, 'One-UV nonempty triangle mesh required')
        contract.require(u32(at+0x248) == 0xffffffff, 'Native vertex colors require explicit support')
        offsets = {key:u32(at+field) for key,field in
                   [('position',0x22c),('uv',0x234),('normal',0x244),('tangent',0x258),('sign',0x260)]}
        decoded = {}
        for key,width in [('position',3),('uv',2),('normal',3),('tangent',3),('sign',1)]:
            pointer = offsets[key]
            contract.require(pointer != 0xffffffff and pointer+vertices*width*4 <= raw_size,
                             'Missing or out-of-bounds native '+key+' array')
            value = np.frombuffer(data,'<f4',vertices*width,raw_start+pointer).reshape(vertices,width)
            contract.require(np.isfinite(value).all(), 'Nonfinite native '+key+' array'); decoded[key] = value
        faces = np.ndarray((faces_count,3),dtype='<u2',buffer=data,offset=12+face_offset+26,strides=(32,2))
        contract.require(faces.max() < vertices, 'Native triangle index exceeds attribute arrays')
        contract.require(np.isin(decoded['sign'],[-1,1]).all(), 'Invalid native tangent sign')
        decoded['faces'] = faces
        decoded['layout'] = {**metadata, 'vertices':vertices,'triangles':faces_count,
                             'attributeOffsets':offsets,'faceOffset':face_offset,
                             'rawOffset':raw_offset,'rawSize':raw_size,
                             'textureSlots':[name(at+0xe8+index*64,64) for index in range(4)],
                             'shadowFlag':u32(at+0xd4)}
        meshes[node_name] = decoded
    contract.require(len(seen_offsets) == node_count and set(meshes) == expected_meshes,
                     'Native child tree differs from declared mesh inventory')
    return meshes, root_record


def ascii_meshes(text, model, roles, material_names=None):
    nodes = re.findall(r'(?ms)^node (\S+) (\S+)\n(.*?)^endnode\s*$', text)
    role_order = sorted(set(roles))
    expected = {model+'p'+str(index):role for index,role in enumerate(role_order)}
    contract.require(len(nodes) == len(expected)+1 and nodes[0][:2] == ('dummy',model),
                     'Canonical detached ASCII hierarchy required')
    contract.require(re.search(r'(?m)^\s*parent NULL\s*$',nodes[0][2]), 'ASCII root parent differs')
    contract.require(re.search(r'(?m)^setsupermodel '+re.escape(model)+r' NULL$',text) and
                     re.search(r'(?m)^setanimationscale 1$',text) and 'newanim ' not in text,
                     'Canonical isolated ASCII model header required')
    result = {}
    for kind,node_name,body in nodes[1:]:
        contract.require(kind == 'trimesh' and node_name in expected and node_name not in result,
                         'Unsupported or undeclared ASCII mesh')
        role = expected[node_name]; material = material_names[role] if material_names is not None else model+('f' if role == 'garment' else '')
        for text_pattern in [r'parent '+re.escape(model),r'position 0 0 0',r'orientation 0 0 0 0',
                             r'bitmap '+re.escape(material),r'materialname '+re.escape(material),r'render 1',r'shadow 1']:
            contract.require(re.search(r'(?m)^\s*'+text_pattern+r'\s*$',body), 'ASCII transform/material binding differs')
        contract.require(not re.search(r'(?m)^\s*(?:scale|positionkey|orientationkey|scalekey)\b',body),
                         'Unsupported ASCII transform/controller')
        p,n,uv,faces = [np.asarray(arrays(body,key)) for key in ['verts','normals','tverts','faces']]
        contract.require(p.ndim == 2 and p.shape[1] == 3 and n.shape == p.shape and
                         uv.ndim == 2 and uv.shape[1] == 3 and faces.ndim == 2 and faces.shape[1] == 8 and
                         all(np.isfinite(value).all() for value in [p,n,uv,faces]), 'Malformed ASCII arrays')
        contract.require(np.array_equal(faces,faces.astype(int)), 'Noninteger ASCII face data')
        faces = faces.astype(int)
        contract.require(faces.size and faces[:,:3].min() >= 0 and faces[:,:3].max() < len(p) and
                         faces[:,4:7].min() >= 0 and faces[:,4:7].max() < len(uv), 'ASCII face index exceeds attributes')
        result[node_name] = {'role':role,'material':material,'triangles':len(faces),
                             'corners':{'position':p[faces[:,:3]],'normal':n[faces[:,:3]],'uv':uv[faces[:,4:7],:2]}}
    contract.require(set(result) == set(expected), 'ASCII role/mesh inventory differs')
    return result


def tangent_proof(native):
    n,t = native['normal'].astype(float),native['tangent'].astype(float)
    nl,tl = np.linalg.norm(n,axis=1),np.linalg.norm(t,axis=1)
    contract.require(nl.min() > 0 and np.allclose(tl,1,atol=2e-5,rtol=0), 'Invalid native normal/tangent magnitude')
    orthogonality = np.abs(np.einsum('ij,ij->i',n/nl[:,None],t))
    contract.require(orthogonality.max() < 2e-5, 'Native tangent not orthogonal to authored normal')
    faces = native['faces']; p,uv = native['position'][faces].astype(float),native['uv'][faces].astype(float)
    d1,d2 = uv[:,1]-uv[:,0],uv[:,2]-uv[:,0]
    determinant = d1[:,0]*d2[:,1]-d1[:,1]*d2[:,0]
    valid = np.abs(determinant) > 1e-12
    differential = None
    if valid.any():
        dp1,dp2 = p[:,1]-p[:,0],p[:,2]-p[:,0]
        tf = (dp1[valid]*d2[valid,1,None]-dp2[valid]*d1[valid,1,None])/determinant[valid,None]
        bf = (dp2[valid]*d1[valid,0,None]-dp1[valid]*d2[valid,0,None])/determinant[valid,None]
        nt = t[faces][valid]; nb = np.cross(n[faces][valid],nt)*native['sign'][faces][valid]
        def cosine_stats(a,b):
            denominator = np.linalg.norm(a,axis=2)*np.linalg.norm(b,axis=1)[:,None]
            contract.require((denominator > 0).all(), 'Degenerate geometric derivative at nondegenerate UV')
            cosine = np.einsum('tci,tci->tc',a,b[:,None,:])/denominator
            return {'minimum':float(cosine.min()),'p01':float(np.percentile(cosine,1)),
                    'median':float(np.median(cosine)),'negativeCorners':int((cosine < 0).sum()),'corners':int(cosine.size)}
        differential = {'tangent':cosine_stats(nt,tf),'bitangent':cosine_stats(nb,bf)}
    return {'authoredNormalLengthRange':[float(nl.min()),float(nl.max())],
            'tangentLengthRange':[float(tl.min()),float(tl.max())],
            'maximumAbsDotNormalizedNormal':float(orthogonality.max()),
            'positiveHandednessVertices':int((native['sign'] == 1).sum()),
            'negativeHandednessVertices':int((native['sign'] == -1).sum()),
            'nondegenerateUvTriangles':int(valid.sum()),'degenerateUvTriangles':int((~valid).sum()),
            'faceUvDirectionCosinesDiagnosticOnly':differential,'visualAccepted':False}


def resolve_float32_ties(source, native):
    """Exact float32 tie rule (documented transport tolerance, not an error allowance).

    A float64 source value lying exactly halfway between two float32 values may be stored as either neighbour:
    the compiler rounds the ASCII decimal text once (correctly, to the side the 17-digit decimal falls), whereas
    the reference float64->float32 cast applies ties-to-even. Only such proven ties are mapped to the reference;
    every other difference is still rejected by validate_transport. Returns the mapped native array and the count.
    """
    reference = source.astype(np.float32); differ = native != reference
    if not differ.any():
        return native, 0
    s = source[differ].astype(np.float64); r = reference[differ].astype(np.float64); n = native[differ]
    neighbour = np.nextafter(reference[differ], n).astype(np.float64)
    tie = (n.astype(np.float64) == neighbour) & (np.abs(s - r) == np.abs(neighbour - s))
    out = native.copy(); index = np.flatnonzero(differ.reshape(-1))[tie]; out.reshape(-1)[index] = reference.reshape(-1)[index]
    return out, int(tie.sum())


CURRENT_MATERIAL_ADAPTERS = {
    'separately-verified-current-geometry-and-original-calibration-material-inputs':
        ('replayed-current-recipient-source-bound-skin-calibration-inputs','current_skin_calibration_bridge','currentMaterialInputs'),
    'separately-verified-current-geometry-and-pelvis-routed-calibration-material-inputs':
        ('replayed-current-recipient-source-bound-skin-calibration-inputs','current_skin_calibration_bridge','currentMaterialInputs'),
    'separately-verified-current-geometry-and-skin-intensity-descendant-material-inputs':
        ('replayed-current-recipient-source-bound-skin-calibration-inputs','current_skin_calibration_bridge','currentMaterialInputs'),
}


def replay_native_geometry(stage, source, source_receipt, target_path, target, part, space):
    """Re-seal the literal native compiler archive the stage consumed; never trust its copy."""
    from native_compiler_input_bridge import prepare_native_geometry
    doc,binary = read_glb(source)
    ids = [row['material'] for row in raw_corners(doc,binary)[3] for _ in range(row['triangles'])]
    native = prepare_native_geometry(stage['nativeGeometryInputs'],target_path=target_path,target=target,part=part,
                                     source=source,receipt=source_receipt,document_material_ids=ids,space=space)
    native.verify()
    recorded = dict(stage['nativeCompilerInputProof']); archive = recorded.pop('compilerCornerArchive',None)
    contract.require(recorded == dict(native.proof), 'Recorded native compiler input proof differs from independent replay')
    arrays = {key:native.array(key) for key in ('positions','normals','uvNative')}
    if archive is not None:
        with np.load(pin(archive['path'],archive['sha256']),allow_pickle=False) as staged:
            contract.require(all(np.array_equal(staged[key],arrays[key]) for key in arrays), 'Stage compiler corner archive differs from replay')
    return native,arrays


def audit_source_inputs(stage, source, source_receipt, target_path, target, part, space):
    """Independently replay the declared material parent; never infer sidecars."""
    roles = {int(key):value for key,value in stage['materialRoles'].items()}
    derived = stage.get('derivedMaterialProof')
    basis = stage.get('materialInputBasis')
    files = []
    edited = False
    intensity_edited = False
    native_override = None
    if isinstance(derived,dict) and derived.get('kind') in CURRENT_MATERIAL_ADAPTERS:
        expected_basis,module,control = CURRENT_MATERIAL_ADAPTERS[derived['kind']]
        contract.require(basis == expected_basis and control in stage and 'nativeGeometryInputs' in stage,
                         'Explicit current-geometry material basis and native controls required')
        native,arrays = replay_native_geometry(stage,source,source_receipt,target_path,target,part,space)
        adapter = __import__(module)
        replay = adapter.staging_inputs(stage[control],target_path,target,part,space,source,source_receipt,
                                        stage['aoStrength'],native_geometry=native)
        contract.require(derived == replay['proof'], 'Recorded current material proof differs from independent replay')
        contract.require(roles == replay['materialRoles'], 'Recorded current material roles differ')
        contract.require(stage.get('materialSlots') == replay['materialSlots'], 'Recorded typed material slots differ')
        ids = np.asarray(replay['compilerMaterialIds'])
        ownership = Path(stage['asciiModel']).parents[1]/'compiler-material-face-ownership.npz'
        with np.load(ownership,allow_pickle=False) as staged:
            contract.require(np.array_equal(staged['materialIds'],ids), 'Stage compiler face ownership differs from replay')
        doc,binary = replay['document'],replay['binary']
        rows,transport = replay['materialRows'],replay['originalMaterialProof']
        files = [*replay['auditFiles'],ownership]
        native_override = {'positions':arrays['positions'],'normals':arrays['normals'],'nativeUv':arrays['uvNative'],
                           'compilerMaterialIds':ids}
    elif 'materialExecutionInputs' in stage and not (isinstance(derived,dict) and derived.get('kind') == 'replayed-source-bound-skin-calibration-compiler-inputs'):
        contract.require(False, 'Material execution requires source-bound calibration audit')
    elif isinstance(derived,dict) and derived.get('kind') == 'replayed-source-bound-skin-calibration-compiler-inputs':
        contract.require(basis == 'replayed-source-bound-skin-calibration-inputs', 'Explicit source-bound calibration basis required')
        from replay_stage_skin_calibration import staging_inputs
        controls = {'mode':derived['recipeMode'],'recipe':derived['recipe']}
        execution = None
        if 'materialExecutionInputs' in stage:
            from target_part_stage import prepare_material_execution_inputs
            execution = prepare_material_execution_inputs(stage['materialExecutionInputs'],controls,
                          target_path,target,part,space)
        options = {'material_execution':execution} if execution is not None else {}
        replay = staging_inputs(controls,target_path,target,part,space,source,source_receipt,roles,
                                stage['aoStrength'],**options)
        contract.require(derived == replay['proof'], 'Recorded source-bound calibration proof differs from independent replay')
        contract.require(stage['untreatedParentSha256'] == derived['independentUntreatedParent']['sha256'],
                         'Recorded untreated calibration material parent differs')
        contract.require(roles == replay['materialRoles'], 'Recorded calibration material roles differ')
        doc,binary = replay['document'],replay['binary']
        rows,transport = replay['materialRows'],replay['originalMaterialProof']
        original_rows,_ = material_inputs(doc,binary,roles,part,stage['aoStrength'],contract.fixed_garment_parts(target))
        edited = any(not np.array_equal(row['color'],original_rows[role]['color']) for role,row in rows.items())
        intensity_edited = any(not np.array_equal(row['intensity'],original_rows[role]['intensity']) for role,row in rows.items())
        files = replay['auditFiles']
    elif isinstance(derived,dict) and derived.get('kind') == 'replayed-original-source-chart-detail-compiler-inputs':
        contract.require(basis == 'replayed-original-source-chart-detail-inputs', 'Explicit original-source detail basis required')
        from replay_stage_skin_detail import staging_inputs
        replay = staging_inputs({'mode':derived['recipeMode'],'receipt':derived['materialReceipt'],
                                 'sourceManifest':derived['sourceManifest']},
                    target_path,target,part,space,source,source_receipt,roles,stage['aoStrength'])
        contract.require(derived == replay['proof'], 'Recorded original-source detail proof differs from replay')
        contract.require(stage['untreatedParentSha256'] == derived['independentUntreatedParent']['sha256'],
                         'Recorded untreated source-detail material parent differs')
        doc,binary = replay['document'],replay['binary']
        rows,transport = replay['materialRows'],replay['originalMaterialProof']
        original_rows,_ = material_inputs(doc,binary,roles,part,stage['aoStrength'],contract.fixed_garment_parts(target))
        edited = any(not np.array_equal(row['color'],original_rows[role]['color']) for role,row in rows.items())
        intensity_edited = any(not np.array_equal(row['intensity'],original_rows[role]['intensity']) for role,row in rows.items())
        files = replay['auditFiles']
    elif isinstance(derived,dict) and derived.get('kind') == 'replayed-c1-skin-intensity-compiler-inputs':
        contract.require(basis == 'replayed-c1-skin-intensity-inputs', 'Explicit replayed skin intensity basis required')
        from replay_stage_skin_intensity import staging_inputs
        replay = staging_inputs({'receipt':derived['lightingReceipt'],'strength':derived['strength']},
                    target_path,target,part,space,source,source_receipt,roles,stage['aoStrength'])
        contract.require(derived == replay['proof'], 'Recorded skin intensity proof differs from independent replay')
        contract.require(stage['untreatedParentSha256'] == derived['independentUntreatedParent']['sha256'],
                         'Recorded untreated AO/lighting parent differs')
        doc,binary = replay['document'],replay['binary']
        rows,transport = replay['materialRows'],replay['originalMaterialProof']
        files = replay['auditFiles']; intensity_edited = derived['derivedIntensityPixelsEdited']
    elif derived is not None:
        contract.require(isinstance(derived,dict) and derived.get('kind') == 'reviewed-per-face-derived-compiler-inputs'
                         and basis == 'reviewed-per-face-derived-inputs', 'Explicit reviewed derived material basis required')
        pins = []
        for key in ('proposalReceipt','reviewReceipt'):
            row = derived.get(key)
            contract.require(isinstance(row,dict) and set(row) == {'path','sha256'}, 'Exact derived proposal/review pins required')
            pins.append(pin(row['path'],row['sha256']))
        # The current helper reconstructs partition and every color/PLT pixel
        # from the frozen source/config/face decisions; stage proof is not trusted.
        from target_garment_face_ownership import reviewed_staging_inputs
        reviewed = reviewed_staging_inputs(*pins,target_path,target,part,space,source,source_receipt,stage['aoStrength'])
        contract.require(derived == reviewed['proof'], 'Recorded stage derived material proof differs from independent replay')
        contract.require(roles == {int(key):value for key,value in reviewed['materialRoles'].items()}, 'Recorded stage per-face material roles differ')
        doc,binary = reviewed['document'],reviewed['binary']
        rows,transport = reviewed['materialRows'],reviewed['originalMaterialProof']
        original_rows,_ = material_inputs(doc,binary,roles,part,stage['aoStrength'],contract.fixed_garment_parts(target))
        edited = any(not np.array_equal(row['color'],original_rows[role]['color']) for role,row in rows.items())
        proposed = json.loads(pins[0].read_text(encoding='utf-8'))
        files = [*pins,*(Path(name).resolve() for name in {**proposed['frozenInputs'],**proposed['outputHashes']})]
        files.extend(Path(row['path']).resolve() for row in derived['paletteEdgeEvidence'])
    else:
        # Missing basis is supported for historical version-2 original-map stages.
        contract.require(basis in (None,'original-embedded-maps'), 'Derived material basis cannot fall through to original maps')
        doc,binary = read_glb(source)
        slots = stage.get('materialSlots')
        atlas_keys = {int(key):row['atlasKey'] for key,row in slots.items()} if slots else None
        rows,transport = material_inputs(doc,binary,roles,part,stage['aoStrength'],contract.fixed_garment_parts(target),atlas_keys=atlas_keys)
    p,n,uv,primitives = raw_corners(doc,binary)
    active = {row['material'] for row in primitives} if native_override is None else set(map(int,native_override['compilerMaterialIds']))
    contract.require(set(roles) == active, 'Audited active materials differ from stage roles')
    if contract.rig_mode(target) == 'stock-exact' and part in contract.fixed_garment_parts(target):
        contract.require('garment' in roles.values(), 'Fixed garment required for audited owner: '+part)
    if 'materialProof' in stage:
        contract.require(stage['materialProof'] == transport, 'Recorded original material transport differs')
    result = {'document':doc,'binary':binary,'positions':p,'normals':n,'uv':uv,'primitives':primitives,
            'materialRows':rows,'materialTransportPolicy':transport,'derivedMaterialProof':derived,
            'materialInputBasis':('replayed-source-bound-skin-calibration-inputs' if basis == 'replayed-source-bound-skin-calibration-inputs' else
                'replayed-original-source-chart-detail-inputs' if basis == 'replayed-original-source-chart-detail-inputs' else
                'replayed-c1-skin-intensity-inputs' if basis == 'replayed-c1-skin-intensity-inputs' else
                'reviewed-per-face-derived-inputs' if derived else 'original-embedded-maps'),
            'materialColorPixelsEdited':edited,'auditFiles':files}
    if native_override is not None:
        result.update(native_override); result['materialInputBasis'] = basis
    if basis in ('replayed-c1-skin-intensity-inputs','replayed-original-source-chart-detail-inputs','replayed-source-bound-skin-calibration-inputs'):
        result['materialIntensityPixelsEdited'] = intensity_edited
    return result


def audit_material_resources(folder, material, role, pixels, compiled):
    """Compare actual compiled dependencies to independently decoded effective rows."""
    mtr_path = folder/(material+'.mtr'); mtr = mtr_path.read_text(encoding='ascii')
    required_lines = ['renderhint NormalTangents','texture1 '+material+'n','texture3 '+material+'r',
                      'parameter float Roughness 0','parameter float Specularity 0.04',
                      'parameter float Metallicness 0.001']
    if role == 'garment': required_lines.append('texture0 '+material)
    contract.require(mtr.splitlines() == required_lines, 'Unexpected MTR policy or material inputs')
    normal_path,rough_path = folder/(material+'n.tga'),folder/(material+'r.tga')
    contract.require(np.array_equal(np.asarray(Image.open(normal_path).convert('RGB')),pixels['normal']),
                     'Actual native material normal pixels differ from original')
    contract.require(np.array_equal(np.asarray(Image.open(rough_path).convert('RGB')),
                                   np.repeat(pixels['roughness'][...,None],3,axis=-1)), 'Roughness transport differs')
    paths = [mtr_path,normal_path,rough_path]
    if role == 'skin':
        diffuse = folder/(material+'.plt'); data = diffuse.read_bytes()
        contract.require(data[:8] == b'PLT V1  ' and struct.unpack_from('<II',data,16) == (2048,2048) and
                         len(data) == 24+2048*2048*2, 'Unexpected PLT structure')
        decoded = np.frombuffer(data[24:],'u1').reshape(2048,2048,2)[::-1]
        contract.require(np.array_equal(decoded[...,0],pixels['intensity']) and not decoded[...,1].any(),
                         'PLT painted shade or skin layer differs')
    else:
        diffuse = folder/(material+'.tga')
        contract.require(np.array_equal(np.asarray(Image.open(diffuse).convert('RGB')),pixels['color']),
                         'Opaque garment diffuse pixels differ')
    paths.append(diffuse)
    contract.require(all(compiled['materialResourceHashes'].get(path.name) == contract.sha(path) for path in paths),
                     'Native tangent-generation material dependency differs')
    return {'material':material,'mtr':mtr,'normalPixelsExact':True,'roughnessPixelsExact':True,
            'diffusePixelsMatchDeclaredPolicy':True,'compileTimeDependenciesExact':True,
            'skinTexture0Omitted':role == 'skin','opaqueGarment':role == 'garment'},paths


def audit(config_path, output):
    config_path = Path(config_path).resolve(); config = json.loads(config_path.read_text(encoding='utf-8'))
    target_path,target = read_target(config)
    contract.require(config.get('kind') == 'target-native-part-audit', 'Explicit v2 target native audit required')
    part,space = config['part'],config['coordinateSpace']
    contract.require(part in contract.BODY_PARTS and space in ('working','runtime'), 'Declared target body part/space required')
    model = contract.model(target,part); output = Path(output).resolve()
    contract.require(not output.exists(), 'Fresh immutable native audit required')
    stage_path = pin(config['stageReceipt'],config['stageReceiptSha256'])
    stage = json.loads(stage_path.read_text(encoding='utf-8'))
    contract.require(stage.get('schemaVersion') == 2 and stage.get('kind') == 'target-part-stage' and
                     stage['part'] == part and stage['model'] == model, 'Selected target stage owner differs')
    contract.verify_binding(stage,target_path,target,space)
    contract.require(stage['statureApplications'] == (0 if space == 'working' else 1), 'Stature applied incorrectly')
    for name,expected in stage['frozenInputs'].items(): pin(name,expected)
    if stage.get('materialLayout') is not None:
        # Single-PLT-per-part stages own one model-named PLT/MTR; their checks live in a dedicated module.
        from audit_single_plt_native_part import audit_single_plt
        return audit_single_plt(config,config_path,stage,stage_path,target_path,target,part,space,output)
    source = pin(stage['source'],stage['sourceSha256'])
    source_receipt = pin(stage['sourceReceipt'],stage['sourceReceiptSha256'])
    replay_stage,replay_space,identity_files = stage,space,[]
    if 'identityRuntimeConversion' in stage:
        conversion = stage['identityRuntimeConversion']
        contract.require(space == 'runtime' and conversion.get('inputApplications') == 0 and conversion.get('outputApplications') == 1
                         and conversion.get('matrix') == np.eye(4).tolist() and conversion.get('positionsNormalsUVTangentsChanged') is False,
                         'Exactly-once stock-exact identity conversion required')
        working_path = pin(stage['sourceWorkingStage']['path'],stage['sourceWorkingStage']['sha256'])
        replay_stage = json.loads(working_path.read_text(encoding='utf-8'))
        contract.verify_binding(replay_stage,target_path,target,'working')
        contract.require(replay_stage['statureApplications'] == 0 and replay_stage['part'] == part and
                         replay_stage['asciiModelSha256'] == stage['asciiModelSha256'] and
                         replay_stage['materialResourceHashes'] == stage['materialResourceHashes'] and
                         replay_stage.get('materialSlots') == stage.get('materialSlots') and
                         replay_stage['source'] == stage['source'] and replay_stage['sourceSha256'] == stage['sourceSha256'],
                         'Identity conversion changed native bytes, ownership or source')
        for name,expected in replay_stage['frozenInputs'].items(): pin(name,expected)
        replay_space,identity_files = 'working',[working_path]
    if 'nativeGeometryInputs' not in replay_stage and not (isinstance(replay_stage.get('derivedMaterialProof'),dict) and
            replay_stage['derivedMaterialProof'].get('kind') in ('replayed-c1-skin-intensity-compiler-inputs',
                'replayed-original-source-chart-detail-compiler-inputs','replayed-source-bound-skin-calibration-compiler-inputs')):
        verify_source_receipt(source,source_receipt,target_path,target,part,replay_space)
    converted = Path(config['converted']).resolve()
    composition_path = pin(converted/'conversion.json',config['compositionSha256'])
    composition = json.loads(composition_path.read_text(encoding='utf-8'))
    contract.require(composition.get('schemaVersion') == 2 and composition.get('kind') == 'target-body-composition',
                     'Explicit target composition required')
    contract.verify_binding(composition,target_path,target,space)
    for name,expected in composition['frozenInputs'].items(): pin(name,expected)
    matches = [row for row in composition['composition']['sourceReceipts'] if row['part'] == part]
    contract.require(len(matches) == 1 and Path(matches[0]['path']).resolve() == stage_path and
                     matches[0]['sha256'] == contract.sha(stage_path), 'Composition does not select this exact stage')
    native_path = pin(converted/'native-compile.json',config['nativeReceiptSha256'])
    compiled = json.loads(native_path.read_text(encoding='utf-8'))
    contract.require(compiled.get('complete') is True and compiled.get('executionMode') == 'compilemodel' and
                     compiled.get('interactiveClientLaunched') is False, 'Completed offline native compile receipt required')
    pin(compiled['client'],compiled['clientSha256'])
    contract.require(compiled['materialResourceHashes'] == composition['materialResourceHashes'],
                     'Compile-time material dependencies differ from composition')
    contract.require(flat_hashes(converted/'ascii') == composition['asciiModelHashes'], 'Composed ASCII resources changed')
    native_rows = {row['name']:row for row in compiled['models']}
    contract.require(len(native_rows) == len(compiled['models']) and set(native_rows) == set(composition['modelParts']),
                     'Native compilation/model ownership differs')
    actual_hashes = flat_hashes(converted/'resources')
    contract.require(set(actual_hashes) == set(composition['materialResourceHashes'])|set(native_rows),
                     'Native resource inventory includes undeclared or missing resources')
    for name,expected in composition['materialResourceHashes'].items():
        contract.require(actual_hashes[name] == expected, 'Compiled material dependency changed: '+name)
    for name,row in native_rows.items():
        contract.require(row['sourceSha256'] == composition['asciiModelHashes'][name] and
                         row['binarySha256'] == actual_hashes[name] and
                         (converted/'resources'/name).stat().st_size == row['bytes'], 'Native compilation association changed')
    ascii_path = pin(stage['asciiModel'],stage['asciiModelSha256'])
    contract.require(composition['asciiModelHashes'][model+'.mdl'] == contract.sha(ascii_path), 'Source stage ASCII differs')
    for name,expected in stage['materialResourceHashes'].items():
        contract.require(composition['materialResourceHashes'].get(name) == expected, 'Source stage material differs')
    roles = {int(key):value for key,value in stage['materialRoles'].items()}
    expected_resources = expected_body_resources(target,{part},{part} if 'garment' in roles.values() else set(),{part:skin_atlas_keys(stage.get('materialSlots'))})-{model+'.mdl'}
    contract.require(set(stage['materialResourceHashes']) == expected_resources, 'Unexpected stage material ownership')
    layout_paths = [pin(Path(config['layoutDirectory'])/name,expected) for name,expected in LAYOUT_PINS.items()]
    effective = audit_source_inputs(replay_stage,source,source_receipt,target_path,target,part,replay_space)
    doc,binary = effective['document'],effective['binary']
    p,n,uv,primitives = effective['positions'],effective['normals'],effective['uv'],effective['primitives']
    slots = stage.get('materialSlots')
    face_materials = (effective['compilerMaterialIds'] if 'compilerMaterialIds' in effective else
                      [row['material'] for row in primitives for _ in range(row['triangles'])])
    if slots:
        from target_part_stage import material_resref, validate_material_slots
        typed = validate_material_slots(slots)
        contract.require(set(typed) == set(roles) and all(typed[key]['role'] == roles[key] for key in typed), 'Typed slot/role disagreement')
        atlas_roles = {row['atlasKey']:row['role'] for row in typed.values()}
        primitive_roles = np.asarray([typed[int(key)]['atlasKey'] for key in face_materials])
        material_names = {key:material_resref(model,key,role) for key,role in atlas_roles.items()}
    else:
        atlas_roles = {role:role for role in roles.values()}
        primitive_roles = np.asarray([roles[int(key)] for key in face_materials])
        material_names = None
    if 'nativeUv' in effective:
        native_uv = effective['nativeUv']
    else:
        native_uv = uv.copy(); native_uv[:,:,1] = 1-native_uv[:,:,1]
    ascii_rows = ascii_meshes(ascii_path.read_text(encoding='ascii'),model,atlas_roles.keys(),material_names)
    native_model = converted/'resources'/(model+'.mdl')
    meshes,root = decode(native_model.read_bytes(),model,ascii_rows)
    material_rows,material_transport = effective['materialRows'],effective['materialTransportPolicy']
    proof = {}; material_proofs = {}; audit_files = [config_path,target_path,stage_path,source,source_receipt,
        composition_path,native_path,native_model,ascii_path,*identity_files,*layout_paths,*effective['auditFiles']]
    maximum_allowed_ulps = config.get('nativeUvMaximumUlps',0)
    for node_name,row in ascii_rows.items():
        role = row['role']; mask = primitive_roles == role; native = meshes[node_name]
        selected = {'position':p[mask],'normal':n[mask],'uv':native_uv[mask]}
        native_corners = {key:native[key][native['faces']] for key in selected}
        resolved = dict(native_corners); ties = {}
        for key in ('position','normal'):
            resolved[key],ties[key] = resolve_float32_ties(selected[key],native_corners[key])
        ae,be,exact = validate_transport(selected,row['corners'],resolved,maximum_allowed_ulps)
        slots = native['layout']['textureSlots']
        contract.require(slots == [row['material'],'','',row['material']] and native['layout']['shadowFlag'] == 1,
                         'Native bitmap/material slot or shadow flag differs')
        ulps = float32_ulp_distance(native_corners['uv'],selected['uv'])
        proof[node_name] = {'role':role,'nativeLayout':native['layout'],
                            'sourceToAsciiOrderedCornerMaximumErrors':ae,'sourceToNativeOrderedCornerMaximumErrors':be,
                            'nativeCornersExactSourceFloat32':exact,
                            'nativeUvFloat32Rounding':{'explicitMaximumAllowedUlps':maximum_allowed_ulps,
                                'observedMaximumUlps':int(ulps.max()),'nonexactValues':int((ulps > 0).sum())},
                            'actualNativeTangentArrays':tangent_proof(native),
                            'exactFloat32TieResolutions':ties}
        pixels = material_rows[role]
        material_proofs[role],paths = audit_material_resources(converted/'resources',row['material'],atlas_roles[role],pixels,compiled)
        material_proofs[role].update(aoStrength=stage['aoStrength'],untreatedParentSha256=stage['untreatedParentSha256'],
                                    diffuseInputBasis=effective['materialInputBasis'])
        audit_files.extend(paths)
    (output/'layout').mkdir(parents=True)
    for path in layout_paths: shutil.copyfile(path,output/'layout'/path.name)
    helper_names = ['audit_target_native_part.py','audit_native_limb_shading.py','audit_geometry.py',
                    'target_contract.py','target_part_pipeline.py','target_part_stage.py',
                    'target_body_inventory.py','place_purposebuilt_pelvis.py']
    if effective['materialInputBasis'] == 'replayed-current-recipient-source-bound-skin-calibration-inputs':
        helper_names += ['current_skin_calibration_bridge.py','native_compiler_input_bridge.py','diagnostic_descendant_representation.py',
                         'replay_stage_skin_calibration.py','phenotype_material_execution_adoption.py','target_garment_ownership.py']
    elif effective['materialInputBasis'] == 'replayed-source-bound-skin-calibration-inputs':
        helper_names += ['replay_stage_skin_calibration.py','phenotype_material_execution_adoption.py',
                         'phenotype_infrastructure_adoption.py','source_representation_contract.py',
                         'replay_stage_skin_intensity.py','mirror_stock_limb_part.py']
    elif effective['materialInputBasis'] == 'replayed-original-source-chart-detail-inputs':
        helper_names += ['replay_stage_skin_detail.py','source_skin_detail_contract.py','replay_stage_skin_intensity.py',
                         'target_skin_lighting_contract.py','skin_lighting_atlas.py','mirror_stock_limb_part.py']
    elif effective['materialInputBasis'] == 'replayed-c1-skin-intensity-inputs':
        helper_names += ['replay_stage_skin_intensity.py','target_skin_lighting_contract.py','skin_lighting_atlas.py',
                         'diagnose_native_cap_normal.py','diagnose_native_tangent_seam.py','mirror_stock_limb_part.py']
    elif effective['derivedMaterialProof']:
        helper_names += ['target_garment_face_ownership.py','target_garment_ownership.py','conservative_face_selection.py']
    (output/'helpers').mkdir()
    for name in helper_names: shutil.copyfile(Path(__file__).with_name(name),output/'helpers'/name)
    audit_files.extend(path for path in output.rglob('*') if path.is_file())
    receipt = {'schemaVersion':2,'kind':'target-native-part-audit',**contract.binding(target_path,target,space),
               'part':part,'model':model,'statureApplications':stage['statureApplications'],
               'stageReceipt':str(stage_path),'stageReceiptSha256':contract.sha(stage_path),
               'nativeReceipt':str(native_path),'nativeReceiptSha256':contract.sha(native_path),
               'nativeModelSha256':contract.sha(native_model),'root':root,'meshes':proof,'materials':material_proofs,
               'materialTransportPolicy':material_transport,'binaryLayoutSourceCommit':LAYOUT_COMMIT,
               'materialInputBasis':effective['materialInputBasis'],'derivedMaterialProof':effective['derivedMaterialProof'],
               'binaryLayoutPrimarySource':'https://github.com/niv/nwn-tools/blob/'+LAYOUT_COMMIT+'/_NwnLib/NwnMdlNodes.h',
               'frozenInputs':{str(path):contract.sha(path) for path in sorted(set(audit_files))},
               'attributeTransportVerified':True,'materialTransportVerified':True,
               'geometryEdited':False,'materialPixelsEdited':effective['materialColorPixelsEdited'],
               'derivedColorInputsApplied':bool(effective['derivedMaterialProof']),'materialColorPixelsEdited':effective['materialColorPixelsEdited'],
               'originalEmbeddedMapsEdited':False,'normalPixelsEdited':False,'roughnessPixelsEdited':False,
               'auditWritesMaterialPixels':False,'nativeCompilerExecuted':False,
               'rigPilotAccepted':target['rig'].get('pilotAccepted',False),'nativeTangentVisualAccepted':False,
               'productionAccepted':False,'clientAccepted':False,
               'limitations':'Detached root with direct identity unskinned one-UV trimeshes only. Ordered transport and finite orthogonal tangent/sign arrays do not prove rendering; per-face tangent direction comparisons are diagnostic and may differ through vertex averaging.'}
    if effective['materialInputBasis'] in ('replayed-c1-skin-intensity-inputs','replayed-original-source-chart-detail-inputs'):
        receipt['materialIntensityPixelsEdited'] = effective['materialIntensityPixelsEdited']
        receipt['materialPixelsEdited'] = effective['materialIntensityPixelsEdited']
        if effective['materialInputBasis'] == 'replayed-original-source-chart-detail-inputs':
            receipt['materialPixelsEdited'] = bool(effective['materialColorPixelsEdited'] or effective['materialIntensityPixelsEdited'])
    if 'materialExecutionInputs' in stage:
        receipt['materialExecutionInputs'] = stage['materialExecutionInputs']
    result = output/'native-part-audit.json'; result.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True); args = parser.parse_args()
    result = audit(args.config,args.output)
    print(json.dumps({'receipt':str(result),'receiptSha256':contract.sha(result)}))
