"""Explicit runtime pelvis PLT diagnostic overlay; original compile inputs stay frozen."""
import hashlib,json,struct
from pathlib import Path
import numpy as np

RESOURCE='pmh0_pelvis001.plt'
MODELS={'pmh0_'+part+'001.mdl' for part in ('chest','pelvis','legl','legr','shinl','shinr')}
def require(ok,message):
    if not ok:raise RuntimeError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def hashes(directory):
    require(directory.is_dir() and all(p.is_file() for p in directory.iterdir()),'Missing/nested native resource directory')
    return {p.name:sha(p) for p in sorted(directory.iterdir())}

def prove_palette(original,candidate,offset):
    require(isinstance(offset,int) and -255<offset<0,'Expected explicit negative skin shade offset')
    require(original[:8]==b'PLT V1  ' and len(original)>=24,'Invalid original palette')
    require(struct.unpack_from('<II',original,8)==(10,0),'Invalid supported PLT layer count/reserved header')
    require(struct.unpack_from('<II',original,16)==(2048,2048) and len(original)==24+2048*2048*2,'Expected exact2K palette')
    require(candidate[:24]==original[:24] and len(candidate)==len(original),'Palette header/dimensions/length changed')
    before=np.frombuffer(original, np.uint8, offset=24).reshape(-1,2)
    after=np.frombuffer(candidate,np.uint8,offset=24).reshape(-1,2)
    require(np.all(before[:,1]<10) and np.all(after[:,1]<10),'Invalid PLT material layer index')
    require(np.array_equal(before[:,1],after[:,1]),'Palette material layers changed')
    skin=before[:,1]==0
    expected=before.copy()
    expected[skin,0]=np.clip(before[skin,0].astype(np.int16)+offset,0,255).astype(np.uint8)
    require(np.array_equal(expected,after),'Not the declared layer0-only clamped shade offset')
    require(np.any(before[:,0]!=after[:,0]),'Palette patch has no change')
    return {'width':2048,'height':2048,'skinPixels':int(skin.sum()),'changedShadePixels':int(np.count_nonzero(before[:,0]!=after[:,0])),'layersExact':True,'nonSkinPixelsExact':True,'skinMeanBefore':float(before[skin,0].mean()),'skinMeanAfter':float(after[skin,0].mean()),'offset':offset,'clampedPixels':int(np.count_nonzero(before[skin,0].astype(np.int16)+offset<0))}

def validate_correction_binding(patch,correction):
    require(correction.get('schemaVersion')==1 and correction.get('operation')=='pelvis-layer0-integer-shade-offset','Unsupported source correction operation')
    for source,target in [('originalPltSha256','oldSha256'),('candidateSha256','newSha256'),('skinShadeOffset','shadeOffset'),('parentHakSha256','baseHakSha256')]:
        require(correction.get(source)==patch[target],'Correction-to-package association differs: '+source)
    require(sha(correction['originalPlt'])==patch['oldSha256'] and sha(correction['candidate'])==patch['newSha256'],'Actual correction source/candidate palette bytes changed')

def validate_material_patch(converted):
    """Return effective RUNTIME material hashes without editing native compile receipts."""
    from audit_thigh_package import archive,packed_index,verify_native
    from stock_limb_contract import validate_receipt_lineage
    converted=Path(converted).resolve()
    path=converted/'material-patch.json';patch=read(path)
    if patch.get('kind') == 'inherited-runtime-pelvis-skin-plt-offset':
        return validate_inherited_material_patch(converted, patch)
    require(patch.get('schemaVersion')==1 and patch.get('kind')=='runtime-pelvis-skin-plt-offset','Unsupported material patch contract')
    require(patch.get('resource')==RESOURCE,'Only declared pelvis PLT may be changed')
    base=Path(patch['baseConverted']).resolve()
    require(base!=converted,'Patch cannot point to its own converted directory')
    require(sha(base/'native-compile.json')==patch['baseNativeReceiptSha256'],'Base original compile receipt changed')
    require(sha(converted/'native-compile.json')==patch['baseNativeReceiptSha256'],'Original compile receipt was altered')
    native,basehashes=verify_native(base,MODELS)
    validate_receipt_lineage(native)
    basebuildpath=Path(patch['baseBuildReceipt']).resolve();build=read(basebuildpath)
    require(sha(basebuildpath)==patch['baseBuildReceiptSha256'],'Base build receipt changed')
    require(Path(build['userDirectory']).resolve()==(base.parents[1]/'userdir').resolve(),'Base build stage association differs')
    require(sha(build['hak'])==patch['baseHakSha256']==build['hakSha256'] and sha(build['module'])==build['moduleSha256'],'Base tested package changed')
    packed=packed_index(archive(build['hak']))
    require(len(packed)==68,'Expected selected paired shin 68-resource source HAK')
    require(packed.get(('pmh0_pelvis001',6))==basehashes[RESOURCE],'Source HAK palette not original compiled palette')
    require(hashes(converted/'ascii')==hashes(base/'ascii'),'Geometry/ASCII changed in material-only patch')
    actual=hashes(converted/'resources')
    require(set(actual)==set(basehashes),'Resource namespace changed in material-only patch')
    require({n for n in actual if actual[n]!=basehashes[n]}=={RESOURCE},'Undeclared material/model/normal resource changed')
    require(basehashes[RESOURCE]==patch['oldSha256'] and actual[RESOURCE]==patch['newSha256'],'Declared patch resource hashes differ')
    correction=Path(patch['correctionReceipt']).resolve()
    require(sha(correction)==patch['correctionReceiptSha256'],'Source correction receipt changed')
    validate_correction_binding(patch,read(correction))
    proof=prove_palette((base/'resources'/RESOURCE).read_bytes(),(converted/'resources'/RESOURCE).read_bytes(),patch['shadeOffset'])
    require(proof==patch['paletteProof'],'Palette operation receipt differs')
    original=read(base/'conversion.json');updated=read(converted/'conversion.json')
    original['ownedResourceHashes'][RESOURCE]=actual[RESOURCE]
    require(updated==original,'Material-only conversion changed rig/parts/height/equipment or other metadata')
    expected=dict(native['materialResourceHashes']);expected[RESOURCE]=actual[RESOURCE]
    require(patch['runtimeMaterialResourceHashes']==expected,'Runtime material override inventory differs')
    return expected,{'path':str(path),'sha256':sha(path),'resource':RESOURCE,'originalCompileReceiptUnchanged':True,'compilerInvoked':False,'paletteProof':proof,'baseHakSha256':patch['baseHakSha256']}


def validate_inherited_material_patch(converted, patch):
    """Inherit a proved six-part runtime palette without rewriting compile history.

    This deliberately permits ONLY the next left foot or foot pair. Source
    compiler unions retain their original material hashes. The effective
    runtime inventory differs solely at the already accepted pelvis PLT.
    """
    from stock_limb_contract import validate_receipt_lineage, validate_new_parts
    require(patch.get('schemaVersion') == 1 and patch.get('resource') == RESOURCE,
            'Unsupported inherited runtime patch')
    parent = Path(patch['parentConverted']).resolve()
    require(parent != converted, 'Inherited patch cannot point to itself')
    parent_path = parent / 'material-patch.json'
    require(sha(parent_path) == patch['parentPatchSha256'], 'Accepted parent material patch changed')
    require(read(parent_path).get('kind') == 'runtime-pelvis-skin-plt-offset',
            'Expected original proved six-part runtime patch parent')
    parent_runtime, parent_proof = validate_material_patch(parent)
    native = read(converted / 'native-compile.json')
    require(sha(converted / 'native-compile.json') == patch['nativeReceiptSha256'],
            'Inherited patch native union changed')
    validate_receipt_lineage(native)
    previous = read(parent / 'native-compile.json')
    require(sha(parent / 'native-compile.json') == patch['parentNativeReceiptSha256'],
            'Inherited parent native receipt changed')
    models = {r['name']: r for r in native['models']}
    old_models = {r['name']: r for r in previous['models']}
    require(set(old_models) == MODELS, 'Inherited patch parent is not selected six-part body')
    new_parts = patch['newParts']
    validate_new_parts(new_parts, MODELS)
    require(set(new_parts) in ({'footl'}, {'footl', 'footr'}), 'Only declared feet may extend runtime patch')
    require(set(models) == MODELS | {'pmh0_' + p + '001.mdl' for p in new_parts}
            and all(models[n] == r for n, r in old_models.items()), 'Inherited compiled neighbours changed')
    actual = hashes(converted / 'resources'); parent_actual = hashes(parent / 'resources')
    require(all(actual.get(n) == d for n, d in parent_actual.items()), 'Inherited accepted runtime payload changed')
    require(all(sha(converted / 'ascii' / n) == sha(parent / 'ascii' / n) for n in MODELS),
            'Inherited accepted ASCII changed')
    require(set(hashes(converted / 'ascii')) == set(models), 'Undeclared inherited ASCII')
    deps = native['materialResourceHashes']; effective = dict(deps)
    require(all(deps.get(n) == d for n, d in previous['materialResourceHashes'].items()),
            'Original compile-time dependency history changed')
    new_deps = {'pmh0_' + p + '001' + suffix for p in new_parts for suffix in ('.plt','.mtr','n.tga')}
    require(set(deps) == set(previous['materialResourceHashes']) | new_deps,
            'Inherited feet have undeclared/missing material dependencies')
    effective[RESOURCE] = parent_runtime[RESOURCE]
    require(patch['runtimeMaterialResourceHashes'] == effective and patch['newSha256'] == effective[RESOURCE],
            'Inherited runtime palette inventory differs')
    require(set(actual) == set(models) | set(effective)
            and all(actual[n] == d for n, d in effective.items()), 'Inherited runtime material bytes differ')
    for name, row in models.items():
        binary = converted / 'resources' / name
        require(sha(converted / 'ascii' / name) == row['sourceSha256'] and sha(binary) == row['binarySha256']
                and binary.read_bytes()[:4] == b'\0\0\0\0' and binary.stat().st_size == row['bytes'],
                'Inherited real compiled model changed: ' + name)
    current_conversion=read(converted / 'conversion.json'); previous_conversion=read(parent / 'conversion.json')
    require(current_conversion['ownedResourceHashes'] == actual,
            'Inherited conversion resource inventory differs')
    for field in ('modelPrefix','height','stockReferenceHeight','rigMode','stockOtherPartsFromGame','equipmentMode'):
        require(current_conversion.get(field)==previous_conversion.get(field), 'Inherited conversion changes stock policy: '+field)
    require(current_conversion['parts'][:len(previous_conversion['parts'])] == previous_conversion['parts']
        and len(current_conversion['parts']) == len(models)
        and {r['model']+'.mdl' for r in current_conversion['parts']} == set(models),
        'Inherited conversion changes accepted part records')
    return effective, {'path':str(converted / 'material-patch.json'), 'sha256':sha(converted / 'material-patch.json'),
        'resource':RESOURCE, 'originalCompileReceiptUnchanged':True, 'compilerInvoked':False,
        'parentPatch':parent_proof, 'baseHakSha256':parent_proof['baseHakSha256'],
        'paletteProof':parent_proof['paletteProof'], 'acceptedRuntimeNeighboursBytesExact':True}
