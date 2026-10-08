"""Read-only native audit of one single-PLT-per-part stage (stock-exact Human bodies).

Dispatched by audit_target_native_part.py for stages that declare materialLayout single-plt-per-part-v1. It verifies
the exact stage -> composition -> native compile association, the single-PLT contract (every node's bitmap /
materialname / native texture slots equal the model; MTR binds only <model>n / <model>r; garment texels use their
declared cloth dye layers and skin texels layer 0), exact ordered ASCII -> native corner transport, finite orthogonal
native tangents and, when the stage declares the compiled basis its normal maps were encoded against, that the final
native tangents/signs still equal that basis per corner. It never compiles, edits pixels or accepts visuals.
"""
import json
from pathlib import Path
import shutil

import numpy as np

import single_plt_part_contract as single_plt
import target_contract as contract
from audit_native_limb_shading import float32_ulp_distance
from audit_target_native_part import LAYOUT_COMMIT, LAYOUT_PINS, decode, resolve_float32_ties, tangent_proof
from nwn_ascii_trimesh import AsciiModel
from target_body_inventory import expected_body_resources, flat_hashes
from target_part_pipeline import pin

BASIS_TANGENT_MAX_DEGREES = 10.0
BASIS_TANGENT_OVER_ONE_DEGREE_FRACTION = 0.005


def ascii_corners(text, nodes):
    model = AsciiModel(text); result = {}
    for name in nodes:
        verts, normals, tverts, faces = model.arrays(model.node(name))
        contract.require(normals is not None and len(normals) == len(verts), 'ASCII normals required: '+name)
        result[name] = {'position':verts[faces[:,:3]],'normal':normals[faces[:,:3]],'uv':tverts[faces[:,4:7],:2],
                        'triangles':int(len(faces))}
    return result


def native_transport(text, native_bytes, model, maximum_uv_ulps=0):
    """Exact ordered corner transport from the ASCII source into the compiled binary, per node."""
    nodes = single_plt.node_bindings(text, model)
    meshes, root = decode(native_bytes, model, nodes)
    source = ascii_corners(text, nodes); proof = {}
    for name in nodes:
        native = meshes[name]; faces = native['faces'].astype(np.int64)
        contract.require(len(faces) == source[name]['triangles'], 'Native triangle order/count differs: '+name)
        contract.require(native['layout']['textureSlots'] == [model,'','',model] and native['layout']['shadowFlag'] == 1,
                         'Native texture slots must name the model PLT/material: '+name)
        corners = {key:native[key][faces] for key in ('position','normal','uv')}; ties = {}
        for key in ('position','normal'):
            corners[key],ties[key] = resolve_float32_ties(source[name][key],corners[key])
        position_exact = bool(np.array_equal(corners['position'],source[name]['position'].astype(np.float32)))
        contract.require(position_exact, 'Native ordered positions differ from the ASCII source: '+name)
        normal_ulps = float32_ulp_distance(corners['normal'],source[name]['normal'].astype(np.float32))
        contract.require(int(normal_ulps.max()) == 0, 'Native ordered normals differ from the ASCII source: '+name)
        uv_ulps = float32_ulp_distance(native['uv'][faces],source[name]['uv'].astype(np.float32))
        contract.require(int(uv_ulps.max()) <= maximum_uv_ulps, 'Native ordered UVs differ beyond the declared float32 rounding: '+name)
        proof[name] = {'triangles':int(len(faces)),'vertices':int(native['layout']['vertices']),
                       'positionsExactFloat32':True,'normalMaximumUlps':int(normal_ulps.max()),
                       'normalNonexactValues':int((normal_ulps > 0).sum()),'uvMaximumUlps':int(uv_ulps.max()),
                       'exactFloat32TieResolutions':ties,'textureSlots':native['layout']['textureSlots'],
                       'actualNativeTangentArrays':tangent_proof(native)}
    return proof, meshes, root


def basis_comparison(meshes, reference_meshes):
    """Final compiled tangents/signs per corner against the compiled basis the normal maps were encoded in."""
    stats = {'corners':0,'maxPositionDifference':0.0,'maxNormalDifference':0.0,'maxTangentDegrees':0.0,
             'cornersOver1Degree':0,'signMismatches':0,'nodes':{}}
    for name,mesh in sorted(meshes.items()):
        contract.require(name in reference_meshes, 'Compiled basis lacks node: '+name)
        reference = reference_meshes[name]; faces = mesh['faces'].astype(np.int64); ref_faces = reference['faces'].astype(np.int64)
        contract.require(faces.shape == ref_faces.shape, 'Compiled basis triangle count differs: '+name)
        position = float(np.abs(mesh['position'][faces]-reference['position'][ref_faces]).max())
        normal = float(np.abs(mesh['normal'][faces]-reference['normal'][ref_faces]).max())
        t1 = mesh['tangent'][faces].reshape(-1,3).astype(float); t0 = reference['tangent'][ref_faces].reshape(-1,3).astype(float)
        cosine = (t1*t0).sum(1)/np.linalg.norm(t1,axis=1)/np.linalg.norm(t0,axis=1)
        angle = np.degrees(np.arccos(np.clip(cosine,-1,1)))
        signs = int((mesh['sign'][faces] != reference['sign'][ref_faces]).sum())
        stats['corners'] += int(angle.size); stats['signMismatches'] += signs
        stats['maxPositionDifference'] = max(stats['maxPositionDifference'],position)
        stats['maxNormalDifference'] = max(stats['maxNormalDifference'],normal)
        stats['maxTangentDegrees'] = max(stats['maxTangentDegrees'],float(angle.max()))
        stats['cornersOver1Degree'] += int((angle > 1).sum())
        stats['nodes'][name] = {'corners':int(angle.size),'maxTangentDegrees':round(float(angle.max()),4),
                                'cornersOver1Degree':int((angle > 1).sum()),'signMismatches':signs}
    contract.require(stats['maxPositionDifference'] <= 1e-6 and stats['signMismatches'] == 0 and
                     stats['maxTangentDegrees'] <= BASIS_TANGENT_MAX_DEGREES and
                     stats['cornersOver1Degree'] <= BASIS_TANGENT_OVER_ONE_DEGREE_FRACTION*stats['corners'],
                     'Final compiled tangent basis differs from the basis the normal maps were encoded in')
    stats['limits'] = {'maxPositionDifference':1e-6,'signMismatches':0,'maxTangentDegrees':BASIS_TANGENT_MAX_DEGREES,
                       'cornersOver1DegreeFraction':BASIS_TANGENT_OVER_ONE_DEGREE_FRACTION}
    return stats


def compiled_reference(entry, model):
    """Decode the declared basis compile of this model from its pinned native receipt."""
    receipt_path = pin(entry['path'],entry['sha256']); receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    contract.require(receipt.get('complete') is True and receipt.get('executionMode') == 'compilemodel', 'Complete basis compile required')
    rows = {row['name']:row for row in receipt['models']}; row = rows.get(model+'.mdl')
    contract.require(row is not None, 'Basis compile lacks '+model)
    binary = pin(receipt_path.parent/'resources'/(model+'.mdl'),row['binarySha256'])
    source = pin(receipt_path.parent/'ascii'/(model+'.mdl'),row['sourceSha256'])
    # The basis compile keeps the pre-atlas per-node materials; only its node inventory and tangents matter here.
    nodes = [node.name for node in AsciiModel(source.read_text(encoding='cp1252')).trimeshes()]
    meshes,_ = decode(binary.read_bytes(),model,nodes)
    return meshes,[receipt_path,binary,source]


def audit_single_plt(config, config_path, stage, stage_path, target_path, target, part, space, output):
    contract.require(single_plt.applies(target) and stage.get('materialLayout') == single_plt.LAYOUT,
                     'Single-PLT audit requires a stock-exact single-PLT stage')
    model = contract.model(target,part)
    replay_stage,identity_files = stage,[]
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
                         replay_stage.get('materialLayout') == stage.get('materialLayout') and
                         replay_stage['source'] == stage['source'] and replay_stage['sourceSha256'] == stage['sourceSha256'],
                         'Identity conversion changed native bytes, ownership or source')
        for name,expected in replay_stage['frozenInputs'].items(): pin(name,expected)
        identity_files = [working_path]
    else:
        contract.require(space == 'working', 'Runtime single-PLT stages require their identity conversion record')
    converted = Path(config['converted']).resolve()
    composition_path = pin(converted/'conversion.json',config['compositionSha256'])
    composition = json.loads(composition_path.read_text(encoding='utf-8'))
    contract.require(composition.get('schemaVersion') == 2 and composition.get('kind') == 'target-body-composition' and
                     composition.get('materialLayout') == single_plt.LAYOUT, 'Explicit single-PLT target composition required')
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
    actual = flat_hashes(converted/'resources')
    contract.require(set(actual) == set(composition['materialResourceHashes'])|set(native_rows),
                     'Native resource inventory includes undeclared or missing resources')
    for name,expected in composition['materialResourceHashes'].items():
        contract.require(actual[name] == expected, 'Compiled material dependency changed: '+name)
    for name,row in native_rows.items():
        contract.require(row['sourceSha256'] == composition['asciiModelHashes'][name] and row['binarySha256'] == actual[name] and
                         (converted/'resources'/name).stat().st_size == row['bytes'], 'Native compilation association changed')
    ascii_path = pin(stage['asciiModel'],stage['asciiModelSha256'])
    contract.require(composition['asciiModelHashes'][model+'.mdl'] == contract.sha(ascii_path), 'Source stage ASCII differs')
    roles = set(stage['materialRoles'].values())
    expected = expected_body_resources(target,{part},{part} if 'garment' in roles else set())-{model+'.mdl'}
    contract.require(set(stage['materialResourceHashes']) == expected, 'Unexpected single-PLT stage material ownership')
    for name,digest in stage['materialResourceHashes'].items():
        contract.require(composition['materialResourceHashes'].get(name) == digest, 'Source stage material differs')
    contract.require(composition['partMaterialSlots'].get(part) == single_plt.validate_slots(stage['materialSlots']),
                     'Composition records different single-PLT node slots')
    layout_paths = [pin(Path(config['layoutDirectory'])/name,expected_hash) for name,expected_hash in LAYOUT_PINS.items()]
    text = ascii_path.read_text(encoding='cp1252'); resources = converted/'resources'
    contract_proof = single_plt.check_part(model,text,(resources/(model+'.mtr')).read_text(encoding='cp1252'),
                                           (resources/(model+'.plt')).read_bytes(),stage['materialSlots'])
    native_model = resources/(model+'.mdl')
    transport,meshes,root = native_transport(text,native_model.read_bytes(),model,config.get('nativeUvMaximumUlps',0))
    audit_files = [config_path,target_path,stage_path,composition_path,native_path,native_model,ascii_path,*identity_files,*layout_paths,
                   *(resources/name for name in sorted(expected))]
    basis = None
    encoded = replay_stage.get('encodedNormalBasis')
    if encoded is not None:
        reference,files = compiled_reference(encoded['compileReceipt'],model)
        basis = basis_comparison(meshes,reference); audit_files.extend(files)
    else:
        contract.require(not replay_stage.get('normalMapsEncodedAgainstCompiledBasis'), 'Declared compiled normal basis is missing')
    output = Path(output).resolve(); contract.require(not output.exists(), 'Fresh immutable native audit required')
    (output/'layout').mkdir(parents=True)
    for path in layout_paths: shutil.copyfile(path,output/'layout'/path.name)
    (output/'helpers').mkdir()
    helper_names = ['audit_single_plt_native_part.py','audit_target_native_part.py','audit_native_limb_shading.py','single_plt_part_contract.py',
                    'uv_atlas_raster.py','nwn_ascii_trimesh.py','target_contract.py','target_part_pipeline.py','target_body_inventory.py']
    for name in helper_names: shutil.copyfile(Path(__file__).with_name(name),output/'helpers'/name)
    audit_files.extend(path for path in output.rglob('*') if path.is_file())
    receipt = {'schemaVersion':2,'kind':'target-native-part-audit',**contract.binding(target_path,target,space),
               'part':part,'model':model,'statureApplications':stage['statureApplications'],'materialLayout':single_plt.LAYOUT,
               'stageReceipt':str(stage_path),'stageReceiptSha256':contract.sha(stage_path),
               'nativeReceipt':str(native_path),'nativeReceiptSha256':contract.sha(native_path),
               'nativeModelSha256':contract.sha(native_model),'root':root,'meshes':transport,
               'singlePltContract':contract_proof,'encodedNormalBasisComparison':basis,
               'materialInputBasis':replay_stage.get('materialInputBasis'),'binaryLayoutSourceCommit':LAYOUT_COMMIT,
               'binaryLayoutPrimarySource':'https://github.com/niv/nwn-tools/blob/'+LAYOUT_COMMIT+'/_NwnLib/NwnMdlNodes.h',
               'frozenInputs':{str(Path(path).resolve()):contract.sha(path) for path in sorted(set(map(str,audit_files)))},
               'attributeTransportVerified':True,'materialTransportVerified':True,'singlePltContractVerified':True,
               'auditWritesMaterialPixels':False,'nativeCompilerExecuted':False,
               'rigPilotAccepted':target['rig'].get('pilotAccepted',False),'nativeTangentVisualAccepted':False,
               'productionAccepted':False,'clientAccepted':False,
               'limitations':'Detached root with direct identity unskinned one-UV trimeshes only. Exact transport, contract layers and '
                             'tangent-basis agreement do not prove rendering or approve anatomy; offline sheets and client review remain required.'}
    result = output/'native-part-audit.json'; result.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return result
