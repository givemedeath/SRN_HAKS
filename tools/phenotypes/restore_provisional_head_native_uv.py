"""Restore provisional head001 native float32 UV precision through exact corner owners.

Only existing tvert U/V values change. Indices, winding, geometry, normal policy,
materials, palettes, rig transforms and immutable earlier diagnostics remain.
"""
import argparse
import json
from pathlib import Path
import re
import shutil

import numpy as np

import target_contract as contract
import shared_toolchain
from pipeline import save_json
from prepare_provisional_target_head_neck import native_details, corner_correspondence, copy_shading, read, ref
from stage_target_rigid_equipment import mesh_data

ARTIFACT_ROOT = Path(__file__).resolve().parents[2] / 'output/phenotypes'


def uv_owners(native_uv, native_faces, ascii_faces, tverts):
    """Every used source UV index must own one exact original native float32 pair."""
    native_uv = np.asarray(native_uv, dtype=np.float32)
    native_faces = np.asarray(native_faces)
    ascii_faces = np.asarray(ascii_faces)
    tverts = np.asarray(tverts)
    contract.require(native_uv.ndim == 2 and native_uv.shape[1] == 2 and np.isfinite(native_uv).all(), 'Finite native U/V pairs required')
    contract.require(native_faces.ndim == 2 and native_faces.shape[1] == 3 and
        ascii_faces.ndim == 2 and ascii_faces.shape[1] == 8 and native_faces.shape == ascii_faces[:, :3].shape,
        'Exact ordered source/native triangle coverage required')
    contract.require(np.issubdtype(native_faces.dtype, np.integer) and np.issubdtype(ascii_faces.dtype, np.integer), 'Integer corner indices required')
    contract.require(tverts.ndim == 2 and tverts.shape[1] == 3 and np.isfinite(tverts).all(), 'Original three-component tvert table required')
    contract.require(native_faces.size and native_faces.min() >= 0 and native_faces.max() < len(native_uv) and
        ascii_faces[:,4:7].min() >= 0 and ascii_faces[:,4:7].max() < len(tverts), 'Native/tvert corner index out of range')
    owners = {int(index): set() for index in np.unique(ascii_faces[:,4:7])}
    corner_counts = dict.fromkeys(owners, 0)
    for native_ids, uv_ids in zip(native_faces, ascii_faces[:,4:7], strict=True):
        for native_id, uv_id in zip(native_ids, uv_ids, strict=True):
            pair = tuple(int(x) for x in native_uv[native_id].view(np.uint32))
            owners[int(uv_id)].add(pair); corner_counts[int(uv_id)] += 1
    contract.require(all(len(values) == 1 for values in owners.values()), 'Ambiguous original-native UV owner for a reused tvert index')
    restored = tverts.copy()
    for index, values in owners.items():
        restored[index,:2] = np.asarray(next(iter(values)), dtype=np.uint32).view(np.float32)
    contract.require(np.array_equal(restored[:,2], tverts[:,2]), 'Tvert third component changed')
    return restored, {'usedTvertIndices': sorted(owners), 'unusedTvertIndicesPreserved': sorted(set(range(len(tverts))) - set(owners)),
        'uniqueNativeUvBitsByTvertIndex': {str(index): list(next(iter(values))) for index, values in owners.items()},
        'orderedFaceCornerUsesByTvertIndex': {str(index): count for index, count in corner_counts.items()},
        'allReusedTvertIndicesHaveUniqueOriginalNativeUvOwner': True}


def replace_uv_table(text, expected_original, restored, used_indices):
    """Retain literal text outside U/V tokens, including third components and indices."""
    matches = list(re.finditer(r'(?m)^[ \t]*tverts[ \t]+(\d+)[ \t]*\r?\n', text))
    contract.require(len(matches) == 1, 'Exactly one head001 tvert table required')
    match = matches[0]; count = int(match[1]); lines = text[match.end():].splitlines(keepends=True)
    contract.require(count == len(expected_original) == len(restored) and len(lines) >= count, 'UV table coverage/count changed')
    parsed = np.asarray([[float(token) for token in line.split()] for line in lines[:count]])
    contract.require(np.array_equal(parsed, expected_original), 'Base UV table differs from declared source indices')
    used = set(used_indices); result = []
    contract.require(used <= set(range(count)), 'Restoration tvert index outside table')
    for index, line in enumerate(lines[:count]):
        if index not in used:
            result.append(line); continue
        tokens = re.fullmatch(r'([ \t]*)(\S+)([ \t]+)(\S+)([ \t]+\S+[ \t]*(?:\r?\n)?)', line)
        contract.require(tokens is not None, 'Expected exactly three stock tvert components')
        u, v = [format(float(np.float32(value)), '.17g') for value in restored[index,:2]]
        contract.require(np.array_equal(np.asarray([float(u),float(v)],dtype=np.float32).view(np.uint32),
                                       np.asarray(restored[index,:2],dtype=np.float32).view(np.uint32)), 'ASCII float32 roundtrip failed')
        result.append(tokens[1] + u + tokens[3] + v + tokens[5])
    before = text[:match.end()]; after = ''.join(lines[count:])
    converted = before + ''.join(result) + after
    contract.require(converted[:match.end()] == before and converted.endswith(after), 'Text outside UV table changed')
    return converted


def prepare(args):
    shared_toolchain.load(args.shared_toolchain, args.migration)
    output = args.output.resolve(); parent = args.parent.resolve()
    contract.require(not output.exists() and output != ARTIFACT_ROOT.resolve() and
                     output.is_relative_to(ARTIFACT_ROOT.resolve()), 'Fresh isolated restored-head output required')
    target_path = args.target_contract.resolve(); target = contract.load(target_path)
    contract.require(target['models']['head'] == 'pmg0_head001' and target['rig']['runtimeScale'] == 10/7,
                     'Explicit declared Troll head001 and single runtime conversion required')
    prior = read(parent/'preparation.json'); contract.verify_binding(prior, target_path, target, 'working')
    contract.require(prior.get('kind') == 'target-provisional-head-neck-preparation' and prior['headNeckAccepted'] is False,
                     'Explicit unaccepted provisional parent required')
    pins = {}
    def pin(path, expected=None):
        path = Path(path).resolve(); actual = contract.sha(path)
        contract.require(expected is None or actual == expected, 'Frozen source changed: '+str(path))
        pins[str(path)] = actual; return path
    for path, expected in prior['frozenInputs'].items(): pin(path, expected)
    for path in (target_path, parent/'preparation.json', args.shared_toolchain, args.migration, Path(__file__),
                 Path(__file__).with_name('prepare_provisional_target_head_neck.py'), Path(__file__).with_name('native_compile.py')): pin(path)
    summary = read(pin(parent/'compact-evidence/summary.json'))
    mapping_path = pin(summary['sameSourceNativeCornerMapping']['path'], summary['sameSourceNativeCornerMapping']['sha256'])
    prior_mapping = read(mapping_path)['head']['originalNativeToSourceAscii']
    contract.require(summary['strictNativeAuditPassed'] is False and summary['strictNativeHeadUvDifferenceResolved'] is False,
                     'Historical strict failure must remain explicit')
    source = prior['sourceRecords']['head']
    for entry in (source['ascii'], source['native'], source['palette']): pin(entry['path'], entry['sha256'])
    _, native, _, _ = native_details(source['native']['path'])
    ascii_mesh = next(iter(mesh_data(Path(source['ascii']['path']).read_text(encoding='ascii')).values()))
    faces = np.asarray(ascii_mesh['arrays']['faces'],int); tverts = np.asarray(ascii_mesh['arrays']['tverts'])
    observed = corner_correspondence(native['faces'], faces, native['worldPositions'], ascii_mesh['world'], native['uv'][0], tverts)
    contract.require(observed == prior_mapping, 'Exhaustive original-native source correspondence changed')
    restored, ownership = uv_owners(native['uv'][0], native['faces'], faces, tverts)
    old_client = read(pin(parent/'working/native-compile.json'))
    pin(args.client, old_client['clientSha256'])
    candidates = []
    for space in ('working','runtime'):
        staged = prior['stages'][space]['head']; pin(staged['ascii']['path'],staged['ascii']['sha256']);pin(staged['palette']['path'],staged['palette']['sha256'])
        base = Path(staged['ascii']['path']).read_text(encoding='ascii')
        result = replace_uv_table(base, tverts, restored, ownership['usedTvertIndices'])
        before = next(iter(mesh_data(base).values())); after = next(iter(mesh_data(result).values()))
        contract.require(np.array_equal(before['vertices'], after['vertices']) and np.array_equal(before['normals'],after['normals']) and
            np.array_equal(before['frame'],after['frame']) and before['fields'] == after['fields'], 'Position/normal policy/bind/material changed')
        contract.require({key:value for key,value in before['arrays'].items() if key!='tverts'} ==
                         {key:value for key,value in after['arrays'].items() if key!='tverts'}, 'Face winding/indices or other arrays changed')
        contract.require(np.array_equal(np.asarray(after['arrays']['tverts']),restored), 'Restored table differs')
        candidates.append((space, result, staged))
    output.mkdir(parents=True); stages = {}
    for space, result, staged in candidates:
        stage = output/space; (stage/'ascii').mkdir(parents=True);(stage/'resources').mkdir()
        ascii_path = stage/'ascii/pmg0_head001.mdl';ascii_path.write_text(result,encoding='ascii')
        palette = stage/'resources/pmg0_head001.plt';shutil.copyfile(staged['palette']['path'],palette)
        contract.require(contract.sha(palette)==source['palette']['sha256'],'Palette bytes changed')
        stages[space] = {'target':contract.binding(target_path,target,space),'ascii':ref(ascii_path),'palette':ref(palette),
            'parentAscii':staged['ascii'],'parentNative':ref(pin(parent/space/'resources/pmg0_head001.mdl')),
            'statureApplications':int(space=='runtime'),'geometryNormalPolicyIndicesWindingMaterialsAndBindUnchanged':True}
    (output/'helper-snapshots').mkdir(); snapshots = {}
    for path in list(pins):
        path = Path(path)
        if path.suffix == '.py':
            copy = output/'helper-snapshots'/path.name;shutil.copyfile(path,copy);snapshots[str(path)]=ref(copy)
    for path,expected in pins.items():contract.require(contract.sha(path)==expected,'Input changed during preparation')
    receipt={'schemaVersion':1,'kind':'target-provisional-head-native-uv-restoration',**contract.binding(target_path,target,'working'),
        'parent':ref(parent/'preparation.json'),'parentStrictFailedSummary':ref(parent/'compact-evidence/summary.json'),
        'source':source,'sourceCorrespondence':observed,'originalNativeUvTableOwnership':ownership,'stages':stages,
        'client':ref(args.client),'changes':['existing tvert U/V numeric precision restored to uniquely owned original-native float32 values only'],
        'sourceOrBinaryPatched':False,'normalsPolicyChanged':False,'windingOrIndicesChanged':False,'rigTransformsChanged':False,
        'headAccepted':False,'materialAccepted':False,'equipmentAccepted':False,'clientAccepted':False,'productionAccepted':False,
        'frozenInputs':pins,'helperSnapshots':snapshots}
    save_json(output/'preparation.json',receipt)
    print(json.dumps({'preparation':ref(output/'preparation.json'),'ownedTverts':len(ownership['usedTvertIndices'])}))


def audit(args):
    output=args.output.resolve();record=read(output/'preparation.json')
    shared_toolchain.load(args.shared_toolchain,args.migration)
    for path,expected in record['frozenInputs'].items():contract.require(contract.sha(path)==expected,'Restoration input changed')
    target=contract.load(record['targetContract']);contract.verify_binding(record,record['targetContract'],target,'working')
    contract.require(not (output/'audit.json').exists(),'Fresh exact-native audit required')
    _,source,source_node,source_shading=native_details(record['source']['native']['path'])
    source_pc,source_uv=source['worldPositions'][source['faces']],source['uv'][0][source['faces']]
    source_n=source['normals'][source['faces']]@np.linalg.inv(np.asarray(source_node['worldFrame'])[:3,:3])
    directions=source_n/np.linalg.norm(source_n,axis=-1,keepdims=True)
    results={};arrays={'originalNativeUvCorners':source_uv,'originalNativePositionCorners':source_pc,'originalNativeRawNormalCorners':source_n}
    for space in ('working','runtime'):
        staged=record['stages'][space];stage=output/space;compiler=read(stage/'native-compile.json')
        contract.require(compiler.get('complete') is True and len(compiler['models'])==1 and
            compiler['clientSha256']==record['client']['sha256'] and compiler['executionMode']=='compilemodel' and
            compiler['interactiveClientLaunched'] is False,'Complete pinned single-head compile required')
        model=compiler['models'][0];path=stage/'resources/pmg0_head001.mdl'
        contract.require(model['name']=='pmg0_head001.mdl' and model['sourceSha256']==staged['ascii']['sha256'] and
            model['binarySha256']==contract.sha(path) and compiler['materialResourceHashes']=={'pmg0_head001.plt':staged['palette']['sha256']},'Exact restored native lineage/material closure required')
        contract.require({p.name for p in (stage/'resources').iterdir()}=={'pmg0_head001.mdl','pmg0_head001.plt'},'Unexpected resources')
        _,mesh,node,shading=native_details(path)
        _,old_mesh,old_node,_=native_details(staged['parentNative']['path'])
        contract.require(shading==copy_shading(source_shading,'pmg0_head001'),'Native source shading changed')
        pc,nc,uv=mesh['worldPositions'][mesh['faces']],mesh['normals'][mesh['faces']]@np.linalg.inv(np.asarray(node['worldFrame'])[:3,:3]),mesh['uv'][0][mesh['faces']]
        old_pc,old_nc=old_mesh['worldPositions'][old_mesh['faces']],old_mesh['normals'][old_mesh['faces']]@np.linalg.inv(np.asarray(old_node['worldFrame'])[:3,:3])
        contract.require(pc.shape==source_pc.shape and np.array_equal(pc.astype(np.float32),old_pc.astype(np.float32)) and
            np.array_equal(nc.astype(np.float32),old_nc.astype(np.float32)),'Precision restoration changed native P/N or ordered geometry')
        contract.require(np.array_equal(uv.astype(np.float32).view(np.uint32),source_uv.astype(np.float32).view(np.uint32)),
            'Strict original-native UV corner equality unresolved')
        factor=1. if space=='working' else 10/7
        error=float(np.max(abs(pc-source_pc*factor)));contract.require(error<2e-7,'Geometry scale transport changed')
        frame=contract.frame(target,'head_g',space);actor=pc@frame[:3,:3].T+frame[:3,3]
        normal_direction=nc/np.linalg.norm(nc,axis=-1,keepdims=True)
        angle=np.rad2deg(np.arccos(np.clip(np.sum(directions*normal_direction,axis=-1),-1,1)))
        arrays[space+'PositionCorners']=pc;arrays[space+'RawNormalCorners']=nc;arrays[space+'UvCorners']=uv;arrays[space+'ActorPositionCorners']=actor
        results[space]={'target':staged['target'],'native':ref(path),'compileReceipt':ref(stage/'native-compile.json'),
            'vertices':len(mesh['positions']),'triangles':len(mesh['faces']),'nativeUvCornersBitExactOriginalSource':True,
            'nativePositionCornersFloat32ExactParent':True,'nativeRawNormalCornersFloat32ExactParent':True,
            'sourceNativePositionTransportMaximumDifferenceMeters':error,'statureApplications':staged['statureApplications'],
            'nativeShadingFieldsFlagsAndPaletteExactSource':True,'normalMaximumAngleDegreesVsSource':float(angle.max()),
            'normalMaximumComponentDifferenceVsExplicitDerivedUnitSource':float(np.max(abs(nc-directions))),
            'headAccepted':False,'materialAccepted':False,'clientAccepted':False}
    scale_error=float(np.max(abs(arrays['runtimeActorPositionCorners']-(10/7)*arrays['workingActorPositionCorners'])))
    contract.require(scale_error<2e-7,'Runtime placement applies stature twice')
    archive=output/'literal-exact-native-uv-corners.npz';np.savez_compressed(archive,**arrays)
    for path,expected in record['frozenInputs'].items():contract.require(contract.sha(path)==expected,'Source changed during exact audit')
    receipt={'schemaVersion':1,'kind':'target-provisional-head-exact-native-uv-audit',**contract.binding(record['targetContract'],target,'working'),
        'preparation':ref(output/'preparation.json'),'spaces':results,'literalNativeCornerArchive':ref(archive),
        'runtimeActorSingleScaleMaximumErrorMeters':scale_error,'strictOriginalNativeUvRestorationProved':True,
        'parentStrictFailurePreserved':True,'sourceOrBinaryPatched':False,'normalPolicyOrRigTransformsChanged':False,
        'humanFemaleSharedResourcesModified':False,'headAccepted':False,'materialAccepted':False,'equipmentAccepted':False,
        'clientAccepted':False,'productionAccepted':False,'remainingGates':['Provisional head anatomy, neck/chest connector and palette continuity review.',
            'Literal client rendering, palette binding, motion and helmet visibility/placement; production remains unaccepted.']}
    save_json(output/'audit.json',receipt)
    print(json.dumps({'audit':ref(output/'audit.json'),'strictNativeUvEquality':True,'singleScaleErrorMeters':scale_error}))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('prepare','audit'))
    for name in ('output','parent','target-contract','shared-toolchain','migration','client'):
        parser.add_argument('--'+name,type=Path,required=name in ('output','shared-toolchain','migration'))
    args=parser.parse_args()
    if args.action=='prepare':contract.require(all(getattr(args,key) for key in ('parent','target_contract','client')),'Explicit parent/target/compiler required')
    {'prepare':prepare,'audit':audit}[args.action](args)


if __name__=='__main__':main()

