"""Explicit foot-only PLT shade descendant. Original source/ASCII/maps stay frozen."""
import json
from pathlib import Path
from material_patch_contract import hashes, prove_palette
from stage_stock_part import require, sha


def validate_foot_material_stage(root, expected_pin=None, allow_native=False):
    from compose_stock_limb_offline import offline_stage
    root=Path(root).resolve();path=root/'foot-material-patch.json';patch=json.loads(path.read_text())
    require(expected_pin is not None and sha(path)==expected_pin,'Foot shade stage requires explicit pinned material operation')
    require(patch.get('schemaVersion')==1 and patch.get('kind')=='foot-layer0-integer-shade-offset',
            'Unsupported foot material operation')
    part=patch['part'];require(part in ('footl','footr'),'Only explicit foot shade operations supported')
    model='pmh0_'+part+'001';resource=model+'.plt'
    require(patch['resource']==resource,'Foot shade operation addresses another body resource')
    parent=Path(patch['parentStage']).resolve();require(parent!=root,'Foot material parent cannot be itself')
    require(sha(parent/'stock-part-stage.json')==patch['parentStageReceiptSha256'],'Foot material parent receipt changed')
    converted,receipt=offline_stage(parent)
    require(receipt['configuration']['part']==part and receipt['configuration']['model']==model,
            'Foot material parent anatomical association differs')
    child=root/'human_male_fit/converted';prior=hashes(converted/'resources');actual=hashes(child/'resources')
    expected=set(prior)|({model+'.mdl'} if allow_native else set())
    require(set(actual)==expected,'Undeclared/missing foot material descendant resources')
    require(hashes(child/'ascii')==hashes(converted/'ascii'),'Foot material operation changed ASCII geometry/UV/normals')
    require(all(actual[n]==digest for n,digest in prior.items() if n!=resource),
            'Foot material operation changed MTR/normal/other resources')
    require(prior[resource]==patch['originalPltSha256'] and actual[resource]==patch['candidatePltSha256'],
            'Declared foot palette hashes differ')
    proof=prove_palette((converted/'resources'/resource).read_bytes(),(child/'resources'/resource).read_bytes(),patch['shadeOffset'])
    require(proof['skinPixels']==2048*2048,'Foot-only source palette must be entirely skin0')
    require(proof==patch['paletteProof'],'Declared foot palette math differs')
    require(sha(root/'stock-part-stage.json')==patch['parentStageReceiptSha256'],
            'Original stage receipt rewritten in material descendant')
    original=json.loads((converted/'conversion.json').read_text());updated=json.loads((child/'conversion.json').read_text())
    original['ownedResourceHashes'][resource]=actual[resource]
    require(original==updated,'Foot material operation changed rig/height/part/stock/equipment metadata')
    # Copied original-stage payloads stay exact except the one explicitly changed
    # palette and its resource inventory. A future real compiler may add its
    # isolated receipt/binary; it cannot rewrite these staged ancestors.
    for relative,digest in receipt['stagedFiles'].items():
        if relative.replace('\\','/') in ('human_male_fit/converted/resources/'+resource,'human_male_fit/converted/conversion.json'):continue
        require(sha(root/relative)==digest,'Foot material operation changed other staged payload: '+relative)
    calibration=Path(patch['calibrationReceipt']).resolve()
    require(sha(calibration)==patch['calibrationReceiptSha256'],'Foot shade calibration receipt changed')
    measured=json.loads(calibration.read_text());inputs=measured['inputHashes']
    require(inputs.get(str(parent/'stock-part-stage.json'))==patch['parentStageReceiptSha256']
        and inputs.get(str(converted/'resources'/resource))==patch['originalPltSha256']
        and inputs.get(str(converted/'ascii'/(model+'.mdl')))==sha(converted/'ascii'/(model+'.mdl')),
        'Foot shade calibration does not bind actual parent stage/ASCII/palette')
    return child,receipt,{'path':str(path),'sha256':sha(path),'part':part,'resource':resource,
        'shadeOffset':patch['shadeOffset'],'sourceMapPixelsUnchanged':True,'originalAsciiUnchanged':True,
        'parentStageReceiptSha256':patch['parentStageReceiptSha256'],'paletteProof':proof,
        'nativeCompileVerifiedHere':False,'clientValidationPending':True}
